"""
Report metrics for DNB scenario sets.

A DNB scenario set is roughly half a gigabyte in memory, so comparing two
quarters by keeping both :class:`~dnb_p_set.ScenarioSet` objects alive is
wasteful.  Instead, :func:`compute_metrics` reduces a set to a small bundle
of percentiles, moments and histograms — everything the HTML report needs —
after which the raw arrays can be released.

Example
-------
>>> from dnb_p_set import ScenarioSet, compute_metrics
>>> current = compute_metrics(ScenarioSet.from_csv("2026Q3.csv"), label="2026Q3")
>>> previous = compute_metrics(
...     ScenarioSet.from_csv("2026Q2.csv"), label="2026Q2", reference=current
... )
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from . import analysis, curves
from .constants import (
    COST_LOAD,
    CURVE_HORIZONS,
    DEFAULT_MATURITIES,
    DEFAULT_PERCENTILES,
    KEY_MATURITIES,
    LIABILITY_HORIZON,
    RETURN_HORIZONS,
    WEALTH_HORIZONS,
)
from .lifecycle import (
    DEFAULT_LIFECYCLE,
    DEFAULT_MAATMENSEN,
    DEFAULT_PORTEFEUILLES,
    Lifecycle,
    Maatmens,
    Portefeuille,
    portefeuille_returns,
    project_wealth,
)

logger = logging.getLogger(__name__)

__all__ = [
    "Kpi",
    "CurveMetrics",
    "SeriesMetrics",
    "MaatmensMetrics",
    "LifecycleMetrics",
    "ScenarioMetrics",
    "compute_metrics",
]

# Term-structure variants included in the report
CURVE_SPECS: list[tuple[str, str, str, str]] = [
    # (key, label, measure, region)
    ("nominal", "Nominale rentetermijnstructuur", "nominal", "nl"),
    ("real_eu", "Reële rentetermijnstructuur (EU-inflatie)", "real", "eu"),
    ("real_nl", "Reële rentetermijnstructuur (NL-inflatie)", "real", "nl"),
]

# Return/inflation blocks included in the report
SERIES_SPECS: list[tuple[str, str, str]] = [
    # (key, variable, label)
    ("equity", "equity_return", "Aandelenrendement"),
    ("inflation_nl", "price_inflation_nl", "Prijsinflatie NL"),
    ("inflation_eu", "price_inflation_eu", "Prijsinflatie EU"),
]


# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------


@dataclass
class Kpi:
    """One headline figure, comparable across scenario sets.

    Attributes
    ----------
    key:
        Stable identifier used to match the figure against a previous set.
    label:
        Human-readable (Dutch) description.
    value:
        The estimate itself.
    unit:
        ``"rate"`` for decimal fractions rendered as percentages (deltas in
        basis points), ``"pct"`` for values already in percent, ``"years"``,
        or ``"number"``.
    se:
        Monte-Carlo standard error of *value*, when the figure is a mean.
    group:
        Section the figure belongs to.
    panel:
        Magnitude cohort used when charting changes.  ``"niveaus"`` covers
        rates and mean returns (changes of a few basis points); ``"risico"``
        covers volatility and tail measures, whose changes are two orders of
        magnitude larger and would otherwise flatten everything else.
    note:
        Optional short explanation.
    """

    key: str
    label: str
    value: float
    unit: str = "rate"
    se: Optional[float] = None
    group: str = "algemeen"
    panel: str = "niveaus"
    note: str = ""


@dataclass
class CurveMetrics:
    """Percentile summaries of one term-structure variant."""

    key: str
    label: str
    maturities: np.ndarray
    #: Deterministic starting curve (t = 0), indexed by maturity.
    spot: pd.Series
    #: Cross-sectional percentiles by maturity, per projection year.
    by_horizon: dict           # {t: DataFrame(index=maturity, columns=stats)}
    #: Percentiles over the projection horizon, per key maturity.
    paths: dict                # {tau: DataFrame(index=t, columns=stats)}
    #: Whether the t = 0 curve is identical across all scenarios.
    deterministic_start: bool = True


@dataclass
class SeriesMetrics:
    """Percentile summaries of one return or inflation block."""

    key: str
    label: str
    #: Percentiles of the one-year return, per projection year.
    annual: pd.DataFrame       # index = projection year (1-based)
    #: Percentiles of the annualised return over 1 … h years, for every h.
    annualised: pd.DataFrame   # index = horizon in years
    #: Percentiles of the cumulative index (start = 1), for every horizon.
    cumulative: pd.DataFrame   # index = horizon in years
    #: Full distribution statistics of the annualised return, per key horizon.
    stats: dict                # {horizon: dict[str, float]}
    #: Histogram of the one-year return in projection year 1.
    hist_year1: tuple          # (edges, density)
    #: Histograms of the annualised return, per horizon.
    hist_annualised: dict      # {horizon: (edges, density)}
    #: Geometric mean return per year over the full projection.
    geometric_mean: float = 0.0
    #: Arithmetic mean and volatility of the one-year return, pooled.
    arithmetic_mean: float = 0.0
    volatility: float = 0.0


@dataclass
class MaatmensMetrics:
    """Projected wealth of one maatmens, reduced to percentiles."""

    maatmens: Maatmens
    #: Allocation and contribution per projection year.
    schedule: pd.DataFrame
    #: Percentiles of the capital per projection year (index 0 … horizon).
    paths: pd.DataFrame
    #: Full distribution statistics of the capital, per reported horizon.
    horizons: dict             # {horizon: dict[str, float]}
    #: Starting age, i.e. the age at projection year 0.
    startleeftijd: int = 0


@dataclass
class LifecycleMetrics:
    """The lifecycle, the two portfolios, and what they do to the maatmensen."""

    lifecycle: Lifecycle
    #: Calendar year of projection year 0.
    basisjaar: int
    portefeuilles: tuple
    #: Allocation per age, columns ``rendement`` and ``bescherming``.
    allocation: pd.DataFrame
    #: Realised return statistics per portfolio, index = portfolio key.
    returns: pd.DataFrame
    #: One entry per maatmens, in the order they were supplied.
    people: list = field(default_factory=list)        # [MaatmensMetrics]
    #: Horizons (years) at which wealth is reported.
    horizons: list = field(default_factory=list)


@dataclass
class ScenarioMetrics:
    """Everything the HTML report needs about one scenario set."""

    label: str
    source: str
    set_type: str
    n_scenarios: int
    n_years: int
    curves: dict = field(default_factory=dict)        # {key: CurveMetrics}
    series: dict = field(default_factory=dict)        # {key: SeriesMetrics}
    breakeven: pd.DataFrame = field(default_factory=pd.DataFrame)
    liability: pd.DataFrame = field(default_factory=pd.DataFrame)
    correlations: pd.DataFrame = field(default_factory=pd.DataFrame)
    kpis: dict = field(default_factory=dict)          # {key: Kpi}
    lifecycle: Optional[LifecycleMetrics] = None
    generated_at: str = ""

    def kpi(self, key: str) -> Optional[Kpi]:
        """Return the KPI stored under *key*, or *None*."""
        return self.kpis.get(key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentile_frame(
    values: np.ndarray,
    index: pd.Index,
    percentiles: list[float],
) -> pd.DataFrame:
    """Summarise ``(n_scenarios, n_points)`` into mean/SE/percentiles per point."""
    data = {
        "mean": values.mean(axis=0),
        "se": analysis.standard_error(values, axis=0),
        "std": values.std(axis=0, ddof=1),
    }
    for p in percentiles:
        data[f"p{p:g}"] = np.percentile(values, p, axis=0)
    return pd.DataFrame(data, index=index)


def _add_kpi(bundle: dict, kpi: Kpi) -> None:
    bundle[kpi.key] = kpi


# ---------------------------------------------------------------------------
# Term structure
# ---------------------------------------------------------------------------


def _curve_metrics(
    scenario_set,
    states: np.ndarray,
    key: str,
    label: str,
    measure: str,
    region: str,
    maturities: list[int],
    horizons: list[int],
    key_maturities: list[int],
    percentiles: list[float],
) -> CurveMetrics:
    phi, psi = scenario_set.curve_parameters(measure=measure, region=region)
    n_t = states.shape[2]
    tau = np.asarray(maturities, dtype=int)

    horizons = [h for h in horizons if 0 <= h < n_t]

    by_horizon: dict = {}
    for h in horizons:
        rates = curves.zero_rates(phi, psi, states[:, :, h], h, tau)
        by_horizon[h] = _percentile_frame(
            rates, pd.Index(tau, name="looptijd"), percentiles
        )

    # The starting curve is deterministic: every scenario shares X(0).
    spot_rates = curves.zero_rates(phi, psi, states[:, :, 0], 0, tau)
    deterministic = bool(np.allclose(spot_rates, spot_rates[0], atol=1e-12))
    spot = pd.Series(spot_rates[0], index=pd.Index(tau, name="looptijd"), name="spot")

    paths: dict = {}
    time_index = pd.Index(range(n_t), name="projectiejaar")
    for m in key_maturities:
        if m > phi.shape[0]:
            continue
        # log P(m, t) for every scenario and projection year at once.
        log_p = phi[m - 1][None, :] + np.einsum("sit,i->st", states, psi[m - 1])
        path = np.expm1(-log_p / float(m))
        paths[m] = _percentile_frame(path, time_index, percentiles)
        del log_p, path

    return CurveMetrics(
        key=key,
        label=label,
        maturities=tau,
        spot=spot,
        by_horizon=by_horizon,
        paths=paths,
        deterministic_start=deterministic,
    )


# ---------------------------------------------------------------------------
# Returns and inflation
# ---------------------------------------------------------------------------


def _series_metrics(
    arr: np.ndarray,
    key: str,
    label: str,
    horizons: list[int],
    percentiles: list[float],
    reference: Optional[SeriesMetrics],
) -> SeriesMetrics:
    n_years = arr.shape[1]
    horizons = [h for h in horizons if 1 <= h <= n_years]

    annual = _percentile_frame(
        arr, pd.Index(range(1, n_years + 1), name="projectiejaar"), percentiles
    )

    # Annualised and cumulative figures for *every* horizon, so the charts get
    # a smooth curve rather than a handful of points.
    cum_log = np.cumsum(np.log1p(arr), axis=1)
    years = np.arange(1, n_years + 1, dtype=float)
    horizon_index = pd.Index(range(1, n_years + 1), name="horizon")

    ann_values = np.expm1(cum_log / years[None, :])
    annualised = _percentile_frame(ann_values, horizon_index, percentiles)
    cumulative = _percentile_frame(np.exp(cum_log), horizon_index, percentiles)

    stats = {
        h: analysis.distribution_stats(ann_values[:, h - 1], percentiles)
        for h in horizons
    }

    ref_year1 = reference.hist_year1[0] if reference is not None else None
    hist_year1 = analysis.histogram(arr[:, 0], edges=ref_year1)

    hist_annualised = {}
    for h in horizons:
        ref_edges = None
        if reference is not None and h in reference.hist_annualised:
            ref_edges = reference.hist_annualised[h][0]
        hist_annualised[h] = analysis.histogram(ann_values[:, h - 1], edges=ref_edges)

    # Geometric mean per year over the full projection.
    geometric_mean = float(np.expm1(cum_log[:, -1].mean() / n_years))
    del cum_log, ann_values

    return SeriesMetrics(
        key=key,
        label=label,
        annual=annual,
        annualised=annualised,
        cumulative=cumulative,
        stats=stats,
        hist_year1=hist_year1,
        hist_annualised=hist_annualised,
        geometric_mean=geometric_mean,
        arithmetic_mean=float(arr.mean()),
        volatility=float(arr.std(ddof=1)),
    )


# ---------------------------------------------------------------------------
# Lifecycle and maatmensen
# ---------------------------------------------------------------------------


def _basisjaar_from_label(label: str | None) -> int:
    """Read the calendar year out of a set label like ``2026Q3``."""
    match = re.search(r"(20\d{2})", label or "")
    return int(match.group(1)) if match else _dt.date.today().year


def _lifecycle_metrics(
    scenario_set,
    states: np.ndarray,
    maatmensen: Sequence[Maatmens],
    lifecycle: Lifecycle,
    portefeuilles: tuple[Portefeuille, Portefeuille],
    horizons: Sequence[int],
    basisjaar: int,
    percentiles: list[float],
) -> Optional[LifecycleMetrics]:
    """Run every maatmens through the lifecycle and reduce to percentiles."""
    if not maatmensen:
        return None

    n_years = scenario_set.get("equity_return").shape[1]
    # Rolling the bond leg needs the curve one year past the last return year.
    max_horizon = min(n_years, states.shape[2] - 1)
    horizons = sorted({h for h in horizons if 1 <= h <= max_horizon})
    if not horizons:
        return None
    horizon = horizons[-1]

    # Both portfolios are the same for every maatmens, so price them once.
    returns = tuple(
        portefeuille_returns(scenario_set, portefeuille, horizon, states=states)
        for portefeuille in portefeuilles
    )

    return_rows = {}
    for portefeuille, matrix in zip(portefeuilles, returns):
        log_growth = np.log1p(matrix)
        return_rows[portefeuille.key] = {
            "label": portefeuille.label,
            "samenstelling": portefeuille.description(),
            "gemiddelde": float(matrix.mean()),
            "volatiliteit": float(matrix.std(ddof=1)),
            "meetkundig": float(np.expm1(log_growth.mean())),
            "p5": float(np.percentile(matrix, 5.0)),
            "p95": float(np.percentile(matrix, 95.0)),
        }
        del log_growth

    people = []
    for maatmens in maatmensen:
        projection = project_wealth(
            scenario_set,
            maatmens,
            lifecycle=lifecycle,
            portefeuilles=portefeuilles,
            horizon=horizon,
            basisjaar=basisjaar,
            states=states,
            returns=returns,
        )
        people.append(
            MaatmensMetrics(
                maatmens=maatmens,
                schedule=projection.schedule,
                paths=projection.percentiles(percentiles),
                horizons={
                    h: analysis.distribution_stats(projection.at(h), percentiles)
                    for h in horizons
                },
                startleeftijd=maatmens.leeftijd(basisjaar),
            )
        )
        del projection

    del returns

    # Tabulate the schedule over the ages the maatmensen actually pass through,
    # padded to the anchor range so the curve reads as a whole.
    ages = [person.startleeftijd for person in people]
    lo = min(int(lifecycle.anchor_ages[0]), min(ages))
    hi = max(int(lifecycle.anchor_ages[-1]), max(ages) + horizon)

    return LifecycleMetrics(
        lifecycle=lifecycle,
        basisjaar=basisjaar,
        portefeuilles=tuple(portefeuilles),
        allocation=lifecycle.allocation(range(lo, hi + 1)),
        returns=pd.DataFrame(return_rows).T.rename_axis("portefeuille"),
        people=people,
        horizons=list(horizons),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_metrics(
    scenario_set,
    label: str | None = None,
    maturities: list[int] | None = None,
    curve_horizons: list[int] | None = None,
    return_horizons: list[int] | None = None,
    key_maturities: list[int] | None = None,
    percentiles: list[float] | None = None,
    reference: Optional[ScenarioMetrics] = None,
    maatmensen: Sequence[Maatmens] | None = None,
    lifecycle: Lifecycle | None = None,
    portefeuilles: tuple[Portefeuille, Portefeuille] | None = None,
    wealth_horizons: list[int] | None = None,
    basisjaar: int | None = None,
) -> ScenarioMetrics:
    """Reduce a :class:`~dnb_p_set.ScenarioSet` to a report metrics bundle.

    Parameters
    ----------
    scenario_set:
        A loaded :class:`~dnb_p_set.ScenarioSet`.
    label:
        Short name for the set (e.g. ``"2026Q3"``).  Derived from the source
        filename when omitted.
    maturities:
        Maturities shown on curve charts.  Defaults to
        :data:`~dnb_p_set.constants.DEFAULT_MATURITIES`.
    curve_horizons:
        Projection years at which the curve distribution is summarised.
    return_horizons:
        Horizons (in years) for annualised return statistics.
    key_maturities:
        Maturities tracked over the whole projection horizon.
    percentiles:
        Percentiles to compute.
    reference:
        Another bundle whose histogram bin edges should be reused, so the two
        sets can be overlaid on identical bins.  Pass the *current* set's
        bundle when computing the *previous* set.
    maatmensen:
        Participants to project through the lifecycle.  Defaults to
        :data:`~dnb_p_set.lifecycle.DEFAULT_MAATMENSEN`; pass an empty
        sequence to skip the lifecycle section entirely.
    lifecycle:
        Allocation schedule; defaults to
        :data:`~dnb_p_set.lifecycle.DEFAULT_LIFECYCLE`.
    portefeuilles:
        ``(rendementsportefeuille, beschermingsportefeuille)``; defaults to
        :data:`~dnb_p_set.lifecycle.DEFAULT_PORTEFEUILLES`.
    wealth_horizons:
        Horizons (years) at which projected wealth is reported.
    basisjaar:
        Calendar year of projection year 0.  Read from *label* when omitted.

    Returns
    -------
    ScenarioMetrics
    """
    maturities = maturities or DEFAULT_MATURITIES
    curve_horizons = curve_horizons or CURVE_HORIZONS
    return_horizons = return_horizons or RETURN_HORIZONS
    key_maturities = key_maturities or KEY_MATURITIES
    percentiles = percentiles or DEFAULT_PERCENTILES
    lifecycle = lifecycle or DEFAULT_LIFECYCLE
    portefeuilles = portefeuilles or DEFAULT_PORTEFEUILLES
    wealth_horizons = wealth_horizons or WEALTH_HORIZONS
    maatmensen = DEFAULT_MAATMENSEN if maatmensen is None else maatmensen

    source = str(scenario_set.source_path or "in-memory")
    if label is None:
        label = (
            scenario_set.source_path.stem
            if scenario_set.source_path
            else f"{scenario_set.set_type}-set"
        )

    bundle = ScenarioMetrics(
        label=label,
        source=source,
        set_type=scenario_set.set_type,
        n_scenarios=scenario_set.n_scenarios,
        n_years=scenario_set.get("equity_return").shape[1],
        generated_at=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    # The state variables drive every curve, so stack them once and reuse.
    states = scenario_set.state_matrix()  # (n_scenarios, 3, n_t)

    # -- term structures ---------------------------------------------------
    for key, curve_label, measure, region in CURVE_SPECS:
        logger.info("[%s] term structure: %s", label, curve_label)
        bundle.curves[key] = _curve_metrics(
            scenario_set,
            states,
            key=key,
            label=curve_label,
            measure=measure,
            region=region,
            maturities=maturities,
            horizons=curve_horizons,
            key_maturities=key_maturities,
            percentiles=percentiles,
        )

    # -- returns and inflation --------------------------------------------
    for key, variable, series_label in SERIES_SPECS:
        logger.info("[%s] distribution: %s", label, series_label)
        ref = reference.series.get(key) if reference is not None else None
        bundle.series[key] = _series_metrics(
            scenario_set.get(variable),
            key=key,
            label=series_label,
            horizons=return_horizons,
            percentiles=percentiles,
            reference=ref,
        )

    # -- break-even inflation ---------------------------------------------
    nominal_spot = bundle.curves["nominal"].spot
    bundle.breakeven = pd.DataFrame(
        {
            "nominaal": nominal_spot,
            "reeel_eu": bundle.curves["real_eu"].spot,
            "reeel_nl": bundle.curves["real_nl"].spot,
            "bei_eu": curves.breakeven_inflation(
                nominal_spot.to_numpy(), bundle.curves["real_eu"].spot.to_numpy()
            ),
            "bei_nl": curves.breakeven_inflation(
                nominal_spot.to_numpy(), bundle.curves["real_nl"].spot.to_numpy()
            ),
        },
        index=nominal_spot.index,
    )

    # -- liability proxy ---------------------------------------------------
    logger.info("[%s] liability proxy", label)
    bundle.liability = _liability_frame(
        scenario_set, states, curve_horizons, percentiles
    )

    # -- correlations ------------------------------------------------------
    logger.info("[%s] correlations", label)
    bundle.correlations = _correlation_frame(scenario_set, states)

    # -- lifecycle and maatmensen -----------------------------------------
    logger.info("[%s] lifecycle projection", label)
    bundle.lifecycle = _lifecycle_metrics(
        scenario_set,
        states,
        maatmensen=maatmensen,
        lifecycle=lifecycle,
        portefeuilles=portefeuilles,
        horizons=wealth_horizons,
        basisjaar=basisjaar if basisjaar is not None else _basisjaar_from_label(label),
        percentiles=percentiles,
    )

    # -- headline figures --------------------------------------------------
    _build_kpis(bundle)
    return bundle


def _liability_frame(
    scenario_set,
    states: np.ndarray,
    horizons: list[int],
    percentiles: list[float],
) -> pd.DataFrame:
    """PV and duration of a flat 60-year cashflow stream on the nominal curve."""
    cashflows = np.ones(LIABILITY_HORIZON)
    phi, psi = scenario_set.curve_parameters(measure="nominal")
    n_t = states.shape[2]

    rows = {}
    for h in [t for t in horizons if 0 <= t < n_t]:
        x = states[:, :, h]
        pv = curves.annuity_pv(phi, psi, x, h, cashflows)
        dur = curves.macaulay_duration(phi, psi, x, h, cashflows)
        row = {
            "pv_mean": float(pv.mean()),
            "pv_se": float(analysis.standard_error(pv)),
            "duration_mean": float(dur.mean()),
        }
        for p in percentiles:
            row[f"pv_p{p:g}"] = float(np.percentile(pv, p))
        rows[h] = row

    return pd.DataFrame(rows).T.rename_axis("projectiejaar")


def _correlation_frame(scenario_set, states: np.ndarray) -> pd.DataFrame:
    """Correlations between year-1 returns and year-1 rate moves."""
    phi, psi = scenario_set.curve_parameters(measure="nominal")
    tau = np.asarray([1, 10], dtype=int)
    r0 = curves.zero_rates(phi, psi, states[:, :, 0], 0, tau)
    r1 = curves.zero_rates(phi, psi, states[:, :, 1], 1, tau)
    delta = r1 - r0

    columns = {
        "Aandelen": scenario_set.get("equity_return")[:, 0],
        "Inflatie NL": scenario_set.get("price_inflation_nl")[:, 0],
        "Inflatie EU": scenario_set.get("price_inflation_eu")[:, 0],
        "Δ 1j-rente": delta[:, 0],
        "Δ 10j-rente": delta[:, 1],
    }
    return pd.DataFrame(columns).corr()


def _build_kpis(bundle: ScenarioMetrics) -> None:
    """Populate the headline figures used for the KPI tiles and delta table."""
    kpis = bundle.kpis
    nominal = bundle.curves["nominal"]

    for m in (1, 10, 30, 50):
        if m in nominal.spot.index:
            _add_kpi(
                kpis,
                Kpi(
                    key=f"spot_nominal_{m}y",
                    label=f"Nominale {m}-jaarsrente (t=0)",
                    value=float(nominal.spot.loc[m]),
                    unit="rate",
                    group="rentetermijnstructuur",
                ),
            )

    if not bundle.breakeven.empty and 10 in bundle.breakeven.index:
        _add_kpi(
            kpis,
            Kpi(
                key="bei_nl_10y",
                label="Break-even inflatie NL, 10 jaar (t=0)",
                value=float(bundle.breakeven.loc[10, "bei_nl"]),
                unit="rate",
                group="rentetermijnstructuur",
                note="(1+nominaal)/(1+reëel NL) − 1",
            ),
        )

    curve_10y = nominal.paths.get(10)
    if curve_10y is not None and 20 in curve_10y.index:
        _add_kpi(
            kpis,
            Kpi(
                key="nominal_10y_at_20",
                label="Verwachte 10-jaarsrente in jaar 20",
                value=float(curve_10y.loc[20, "mean"]),
                unit="rate",
                se=float(curve_10y.loc[20, "se"]),
                group="rentetermijnstructuur",
            ),
        )

    equity = bundle.series.get("equity")
    if equity is not None:
        _add_kpi(
            kpis,
            Kpi(
                key="equity_geo_mean",
                label="Meetkundig gemiddeld aandelenrendement (bruto)",
                value=equity.geometric_mean,
                unit="rate",
                group="aandelen",
                note="DNB-kalibratiedoel ≈ 5,4 % bruto",
            ),
        )
        _add_kpi(
            kpis,
            Kpi(
                key="equity_geo_mean_net",
                label="Meetkundig gemiddeld aandelenrendement (netto)",
                value=(1.0 + equity.geometric_mean) * (1.0 - COST_LOAD) - 1.0,
                unit="rate",
                group="aandelen",
                note=f"na {COST_LOAD * 10_000:.0f} bp kostenafslag",
            ),
        )
        _add_kpi(
            kpis,
            Kpi(
                key="equity_arith_mean",
                label="Rekenkundig gemiddeld aandelenrendement",
                value=equity.arithmetic_mean,
                unit="rate",
                group="aandelen",
            ),
        )
        _add_kpi(
            kpis,
            Kpi(
                key="equity_vol",
                label="Volatiliteit aandelenrendement (alle projectiejaren)",
                value=equity.volatility,
                unit="rate",
                group="aandelen",
                panel="risico",
            ),
        )
        if 1 in equity.annual.index:
            _add_kpi(
                kpis,
                Kpi(
                    key="equity_vol_year1",
                    label="Volatiliteit aandelenrendement (projectiejaar 1)",
                    value=float(equity.annual.loc[1, "std"]),
                    unit="rate",
                    group="aandelen",
                    panel="risico",
                ),
            )
        if 1 in equity.stats:
            _add_kpi(
                kpis,
                Kpi(
                    key="equity_var95_1y",
                    label="1-jaars VaR 95 % aandelen (verlies)",
                    value=equity.stats[1]["var95"],
                    unit="rate",
                    group="aandelen",
                    panel="risico",
                ),
            )
            _add_kpi(
                kpis,
                Kpi(
                    key="equity_es95_1y",
                    label="1-jaars Expected Shortfall 95 % aandelen",
                    value=equity.stats[1]["es95"],
                    unit="rate",
                    group="aandelen",
                    panel="risico",
                ),
            )
        if 20 in equity.annualised.index:
            _add_kpi(
                kpis,
                Kpi(
                    key="equity_ann20_mean",
                    label="Gemiddeld rendement over 20 jaar (geannualiseerd)",
                    value=float(equity.annualised.loc[20, "mean"]),
                    unit="rate",
                    se=float(equity.annualised.loc[20, "se"]),
                    group="aandelen",
                ),
            )
            _add_kpi(
                kpis,
                Kpi(
                    key="equity_ann20_p5",
                    label="Slecht-weerscenario 20 jaar (p5, geannualiseerd)",
                    value=float(equity.annualised.loc[20, "p5"]),
                    unit="rate",
                    group="aandelen",
                    panel="risico",
                ),
            )

    for key, tile_label in (("inflation_nl", "NL"), ("inflation_eu", "EU")):
        series = bundle.series.get(key)
        if series is None:
            continue
        _add_kpi(
            kpis,
            Kpi(
                key=f"{key}_geo_mean",
                label=f"Meetkundig gemiddelde inflatie {tile_label}",
                value=series.geometric_mean,
                unit="rate",
                group="inflatie",
            ),
        )
        if 20 in series.annualised.index:
            _add_kpi(
                kpis,
                Kpi(
                    key=f"{key}_ann20_mean",
                    label=f"Gemiddelde inflatie {tile_label} over 20 jaar",
                    value=float(series.annualised.loc[20, "mean"]),
                    unit="rate",
                    se=float(series.annualised.loc[20, "se"]),
                    group="inflatie",
                ),
            )

    if not bundle.liability.empty and 0 in bundle.liability.index:
        _add_kpi(
            kpis,
            Kpi(
                key="liability_pv",
                label=f"Contante waarde vlakke kasstroom ({LIABILITY_HORIZON} jaar)",
                value=float(bundle.liability.loc[0, "pv_mean"]),
                unit="number",
                group="verplichtingen",
                note="1 per jaar, verdisconteerd op de nominale curve t=0",
            ),
        )
        _add_kpi(
            kpis,
            Kpi(
                key="liability_duration",
                label="Macaulay-duration van die kasstroom",
                value=float(bundle.liability.loc[0, "duration_mean"]),
                unit="years",
                group="verplichtingen",
            ),
        )
