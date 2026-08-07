"""
Wealth projection for a *maatmens* on a DNB scenario set.

A **maatmens** is a stylised participant: a birth year, the pension capital
already accrued at ``t = 0``, and a pensionable salary.  Their capital is
invested in two portfolios, both driven by the simulated scenarios:

* the **rendementsportefeuille**, exposed to the simulated equity return;
* the **beschermingsportefeuille**, a constant-maturity zero-coupon bond
  position whose return follows from the affine term structure.

A :class:`Lifecycle` sets, per age, how the capital is split between the two.
Projection year *t* then runs:

.. math::

    V_{t+1} = \\bigl(V_t + \\text{premie}_t\\bigr)\\,
              \\bigl(1 + w_t r^{\\text{rend}}_t + (1 - w_t) r^{\\text{besch}}_t\\bigr)

so the contribution for a year is paid at the start of that year and earns
that year's return, and the weight :math:`w_t` is read off the lifecycle at
the age reached at the start of the year.

Everything here is a modelling choice, not a DNB prescription — the set only
supplies the returns.

Example
-------
>>> from dnb_p_set import ScenarioSet
>>> from dnb_p_set.lifecycle import DEFAULT_LIFECYCLE, Maatmens, project_wealth
>>> ss = ScenarioSet.from_csv("2026Q3.csv")
>>> mens = Maatmens("Starter", geboortejaar=2001,
...                 pensioenvermogen=5_000, pensioengevend_salaris=34_000)
>>> projection = project_wealth(ss, mens, DEFAULT_LIFECYCLE, horizon=20,
...                             basisjaar=2026)
>>> projection.percentiles().loc[[1, 10, 20]]
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Sequence, Union

import numpy as np
import pandas as pd

from .constants import (
    COST_LOAD,
    DEFAULT_FRANCHISE,
    DEFAULT_PENSIOENLEEFTIJD,
    DEFAULT_PERCENTILES,
    DEFAULT_PREMIE_PERCENTAGE,
    PROTECTION_MATURITY,
)

__all__ = [
    "Portefeuille",
    "Lifecycle",
    "Maatmens",
    "WealthProjection",
    "RENDEMENTSPORTEFEUILLE",
    "BESCHERMINGSPORTEFEUILLE",
    "DEFAULT_PORTEFEUILLES",
    "DEFAULT_LIFECYCLE",
    "DEFAULT_MAATMENSEN",
    "bond_returns",
    "portefeuille_returns",
    "project_wealth",
]

#: Salary indexation: ``"geen"``/``None`` for a flat salary, a variable name
#: or alias for indexation on a simulated series, or a fixed annual rate.
Indexation = Union[str, float, None]


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Portefeuille:
    """One investment portfolio, defined by its exposure to the scenario set.

    A portfolio is a mix of two legs: the simulated equity return, and a
    constant-maturity zero-coupon bond priced off the term structure.  Two
    legs are enough to place both the return and the protection portfolio on
    a common footing, and both are driven entirely by the set.

    Attributes
    ----------
    key:
        Stable identifier.
    label:
        Human-readable (Dutch) name.
    equity_weight:
        Fraction invested in the simulated equity return; the remainder goes
        into the bond leg.
    bond_maturity:
        Maturity (years) of the zero-coupon bond leg.  A longer maturity
        makes the portfolio more sensitive to rate moves, which is exactly
        what a protection portfolio is for.
    cost:
        Annual cost load applied to the gross portfolio return.
    """

    key: str
    label: str
    equity_weight: float = 0.0
    bond_maturity: int = 1
    cost: float = COST_LOAD

    def __post_init__(self) -> None:
        if not 0.0 <= self.equity_weight <= 1.0:
            raise ValueError(
                f"equity_weight must lie in [0, 1], got {self.equity_weight}"
            )
        if self.bond_maturity < 1:
            raise ValueError(
                f"bond_maturity must be at least 1 year, got {self.bond_maturity}"
            )
        if self.cost < 0.0:
            raise ValueError(f"cost must not be negative, got {self.cost}")

    @property
    def bond_weight(self) -> float:
        """Fraction invested in the zero-coupon bond leg."""
        return 1.0 - self.equity_weight

    def description(self) -> str:
        """Short Dutch description of the composition."""
        parts = []
        if self.equity_weight > 0:
            parts.append(f"{self.equity_weight * 100:.0f}% aandelen")
        if self.bond_weight > 0:
            parts.append(
                f"{self.bond_weight * 100:.0f}% zerocouponobligatie "
                f"{self.bond_maturity} jaar"
            )
        return " + ".join(parts) + f", na {self.cost * 10_000:.0f} bp kosten"


@dataclass(frozen=True)
class Lifecycle:
    """Allocation to the return portfolio as a function of age.

    The lifecycle is stored as anchor points and read with linear
    interpolation; outside the anchor range the nearest anchor's weight
    applies, so the schedule is always defined.

    Attributes
    ----------
    key, label:
        Identifier and human-readable (Dutch) name.
    anchors:
        ``((leeftijd, gewicht_rendementsportefeuille), …)`` with strictly
        increasing ages and weights in ``[0, 1]``.
    """

    key: str
    label: str
    anchors: tuple[tuple[int, float], ...]

    def __post_init__(self) -> None:
        if len(self.anchors) < 2:
            raise ValueError("a lifecycle needs at least two anchor points")
        ages = [age for age, _ in self.anchors]
        if any(b <= a for a, b in zip(ages, ages[1:])):
            raise ValueError(f"anchor ages must strictly increase, got {ages}")
        for age, weight in self.anchors:
            if not 0.0 <= weight <= 1.0:
                raise ValueError(
                    f"weight at age {age} must lie in [0, 1], got {weight}"
                )

    @property
    def anchor_ages(self) -> np.ndarray:
        return np.array([age for age, _ in self.anchors], dtype=float)

    @property
    def anchor_weights(self) -> np.ndarray:
        return np.array([weight for _, weight in self.anchors], dtype=float)

    def rendement_weight(self, age) -> np.ndarray:
        """Weight in the return portfolio at *age* (scalar or array)."""
        return np.interp(
            np.asarray(age, dtype=float), self.anchor_ages, self.anchor_weights
        )

    def allocation(self, ages: Sequence[int] | None = None) -> pd.DataFrame:
        """Allocation per age.

        Parameters
        ----------
        ages:
            Ages to tabulate.  Defaults to every whole year covered by the
            anchors.

        Returns
        -------
        pd.DataFrame
            Index ``leeftijd``; columns ``rendement`` and ``bescherming``,
            which sum to 1.
        """
        if ages is None:
            ages = np.arange(
                int(self.anchor_ages[0]), int(self.anchor_ages[-1]) + 1
            )
        ages = np.asarray(ages)
        weight = self.rendement_weight(ages)
        return pd.DataFrame(
            {"rendement": weight, "bescherming": 1.0 - weight},
            index=pd.Index(ages, name="leeftijd"),
        )


@dataclass(frozen=True)
class Maatmens:
    """A stylised participant.

    Attributes
    ----------
    naam:
        Label used in charts and tables.
    geboortejaar:
        Birth year; combined with the projection's base year it fixes the age
        at every projection year.
    pensioenvermogen:
        Pension capital already accrued at ``t = 0``, in euro.
    pensioengevend_salaris:
        Pensionable salary at ``t = 0``, in euro.
    premiepercentage:
        Annual contribution as a fraction of the pensioengrondslag.
    franchise:
        Salary offset not covered by pension accrual.
    pensioenleeftijd:
        Age at which contributions stop.
    """

    naam: str
    geboortejaar: int
    pensioenvermogen: float
    pensioengevend_salaris: float
    premiepercentage: float = DEFAULT_PREMIE_PERCENTAGE
    franchise: float = DEFAULT_FRANCHISE
    pensioenleeftijd: int = DEFAULT_PENSIOENLEEFTIJD

    def __post_init__(self) -> None:
        if self.pensioenvermogen < 0:
            raise ValueError(
                f"pensioenvermogen must not be negative, got {self.pensioenvermogen}"
            )
        if self.pensioengevend_salaris < 0:
            raise ValueError(
                "pensioengevend_salaris must not be negative, got "
                f"{self.pensioengevend_salaris}"
            )
        if not 0.0 <= self.premiepercentage <= 1.0:
            raise ValueError(
                f"premiepercentage must lie in [0, 1], got {self.premiepercentage}"
            )
        if self.franchise < 0:
            raise ValueError(f"franchise must not be negative, got {self.franchise}")

    def leeftijd(self, jaar: int) -> int:
        """Age reached in calendar year *jaar*."""
        return int(jaar) - self.geboortejaar

    @property
    def pensioengrondslag(self) -> float:
        """Salary above the franchise; the base for the contribution."""
        return max(0.0, self.pensioengevend_salaris - self.franchise)

    @property
    def jaarpremie(self) -> float:
        """Contribution in the first projection year, in euro."""
        return self.premiepercentage * self.pensioengrondslag


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

#: Fully invested in the simulated equity return.
RENDEMENTSPORTEFEUILLE = Portefeuille(
    key="rendement",
    label="Rendementsportefeuille",
    equity_weight=1.0,
    cost=COST_LOAD,
)

#: A long zero-coupon bond, so the portfolio gains value exactly when the rate
#: used to convert capital into pension falls.
BESCHERMINGSPORTEFEUILLE = Portefeuille(
    key="bescherming",
    label="Beschermingsportefeuille",
    equity_weight=0.0,
    bond_maturity=PROTECTION_MATURITY,
    cost=COST_LOAD,
)

DEFAULT_PORTEFEUILLES: tuple[Portefeuille, Portefeuille] = (
    RENDEMENTSPORTEFEUILLE,
    BESCHERMINGSPORTEFEUILLE,
)

#: Fully in return assets until 40, then de-risking towards retirement.
DEFAULT_LIFECYCLE = Lifecycle(
    key="standaard",
    label="Standaard lifecycle",
    anchors=(
        (25, 1.00),
        (40, 1.00),
        (50, 0.85),
        (60, 0.62),
        (68, 0.40),
        (85, 0.30),
    ),
)

#: Three participants spread across a career.  Ages are relative to the base
#: year of the projection (2026 gives 25, 45 and 60).
DEFAULT_MAATMENSEN: tuple[Maatmens, ...] = (
    Maatmens(
        naam="Starter",
        geboortejaar=2001,
        pensioenvermogen=5_000.0,
        pensioengevend_salaris=34_000.0,
    ),
    Maatmens(
        naam="Halverwege",
        geboortejaar=1981,
        pensioenvermogen=95_000.0,
        pensioengevend_salaris=52_000.0,
    ),
    Maatmens(
        naam="Bijna met pensioen",
        geboortejaar=1966,
        pensioenvermogen=285_000.0,
        pensioengevend_salaris=68_000.0,
    ),
)


# ---------------------------------------------------------------------------
# Portfolio returns
# ---------------------------------------------------------------------------


def _log_p_path(
    phi: np.ndarray, psi: np.ndarray, states: np.ndarray, maturity: int
) -> np.ndarray:
    """``log P(maturity, t)`` for every scenario and projection year."""
    if not 1 <= maturity <= phi.shape[0]:
        raise ValueError(
            f"maturity must lie in [1, {phi.shape[0]}], got {maturity}"
        )
    return phi[maturity - 1][None, :] + np.einsum("sit,i->st", states, psi[maturity - 1])


def bond_returns(
    scenario_set,
    maturity: int,
    n_years: int,
    states: np.ndarray | None = None,
    measure: str = "nominal",
    region: str = "nl",
) -> np.ndarray:
    """One-year total return on a constant-maturity zero-coupon bond.

    A zero bought at maturity *m* in year *t* has *m − 1* years left in year
    *t + 1*, so the realised return over that year is

    .. math::

        r_t = \\frac{P(m - 1,\\, t + 1)}{P(m,\\, t)} - 1

    with :math:`P` the bond price implied by the affine parameters.  The
    position is rolled back to maturity *m* at the end of every year, which is
    how a constant-duration mandate behaves.  For ``m = 1`` the bond simply
    matures and the return is the one-year rate.

    Parameters
    ----------
    scenario_set:
        A loaded :class:`~dnb_p_set.ScenarioSet` with the curve parameters
        and state variables.
    maturity:
        Maturity of the bond in years.
    n_years:
        Number of projection years to return.
    states:
        Pre-computed ``(n_scenarios, 3, n_t)`` state matrix; recomputed from
        *scenario_set* when omitted.
    measure, region:
        Term structure to price against; see
        :meth:`~dnb_p_set.ScenarioSet.curve_parameters`.

    Returns
    -------
    np.ndarray
        Array ``(n_scenarios, n_years)`` of simple annual returns.
    """
    phi, psi = scenario_set.curve_parameters(measure=measure, region=region)
    if states is None:
        states = scenario_set.state_matrix()

    n_t = states.shape[2]
    if n_years < 1:
        raise ValueError(f"n_years must be at least 1, got {n_years}")
    if n_years + 1 > n_t:
        raise ValueError(
            f"n_years={n_years} needs {n_years + 1} time steps but the set has {n_t}"
        )

    log_p = _log_p_path(phi, psi, states, maturity)
    if maturity == 1:
        # P(0, t) = 1, so the bond simply pays out at par.
        log_p_shorter = np.zeros_like(log_p)
    else:
        log_p_shorter = _log_p_path(phi, psi, states, maturity - 1)

    return np.expm1(log_p_shorter[:, 1 : n_years + 1] - log_p[:, :n_years])


def portefeuille_returns(
    scenario_set,
    portefeuille: Portefeuille,
    n_years: int | None = None,
    states: np.ndarray | None = None,
) -> np.ndarray:
    """Net annual returns of *portefeuille* per scenario and projection year.

    The gross return is the weighted sum of the equity leg and the bond leg;
    the cost load is then applied multiplicatively,
    ``(1 + r_gross)(1 − cost) − 1``.

    Returns
    -------
    np.ndarray
        Array ``(n_scenarios, n_years)`` of simple annual returns.
    """
    equity = scenario_set.get("equity_return")
    n_years = equity.shape[1] if n_years is None else int(n_years)
    if not 1 <= n_years <= equity.shape[1]:
        raise ValueError(
            f"n_years must lie in [1, {equity.shape[1]}], got {n_years}"
        )

    gross = np.zeros((equity.shape[0], n_years), dtype=float)
    if portefeuille.equity_weight > 0.0:
        gross += portefeuille.equity_weight * equity[:, :n_years]
    if portefeuille.bond_weight > 0.0:
        gross += portefeuille.bond_weight * bond_returns(
            scenario_set, portefeuille.bond_maturity, n_years, states=states
        )

    return (1.0 + gross) * (1.0 - portefeuille.cost) - 1.0


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def _percentile_frame(
    values: np.ndarray, index: pd.Index, percentiles: Sequence[float]
) -> pd.DataFrame:
    """Summarise ``(n_scenarios, n_points)`` into mean/std/percentiles."""
    n = values.shape[0]
    mean = values.mean(axis=0)
    variance = np.maximum((values ** 2).mean(axis=0) - mean ** 2, 0.0)
    data = {
        "mean": mean,
        "se": np.sqrt(variance / n),
        "std": values.std(axis=0, ddof=1),
    }
    for p in percentiles:
        data[f"p{p:g}"] = np.percentile(values, p, axis=0)
    return pd.DataFrame(data, index=index)


def _salary_factor(
    scenario_set,
    n_years: int,
    n_scenarios: int,
    indexation: Indexation,
) -> np.ndarray:
    """Salary in projection year *t* relative to year 0.

    Returns a ``(1, n_years)`` array for a deterministic rule and a
    ``(n_scenarios, n_years)`` array when the salary follows a simulated
    series, so it broadcasts against the wealth path either way.
    """
    if indexation is None or indexation == "geen":
        return np.ones((1, n_years))

    if isinstance(indexation, (int, float)) and not isinstance(indexation, bool):
        return ((1.0 + float(indexation)) ** np.arange(n_years, dtype=float))[None, :]

    factor = np.ones((n_scenarios, n_years))
    if n_years > 1:
        # The salary in year t reflects the inflation of years 0 … t-1.
        series = scenario_set.get(indexation)[:, : n_years - 1]
        factor[:, 1:] = np.cumprod(1.0 + series, axis=1)
    return factor


@dataclass
class WealthProjection:
    """Projected wealth of one maatmens over the scenarios.

    Attributes
    ----------
    maatmens, lifecycle, portefeuilles:
        The inputs the projection was run with.
    basisjaar:
        Calendar year of projection year 0.
    schedule:
        Per projection year: calendar year, age, the two portfolio weights
        and the average contribution.
    wealth:
        Array ``(n_scenarios, horizon + 1)``; column ``t`` is the capital at
        the *end* of projection year ``t``, with column 0 the starting
        capital.
    returns:
        Array ``(n_scenarios, horizon)`` of realised lifecycle returns.
    """

    maatmens: Maatmens
    lifecycle: Lifecycle
    basisjaar: int
    portefeuilles: tuple[Portefeuille, Portefeuille]
    schedule: pd.DataFrame
    wealth: np.ndarray
    returns: np.ndarray

    @property
    def horizon(self) -> int:
        """Number of projected years."""
        return self.wealth.shape[1] - 1

    def at(self, horizon: int) -> np.ndarray:
        """Cross-section of capital after *horizon* years, one value per scenario."""
        if not 0 <= horizon <= self.horizon:
            raise ValueError(
                f"horizon must lie in [0, {self.horizon}], got {horizon}"
            )
        return self.wealth[:, horizon]

    def percentiles(
        self, percentiles: Sequence[float] | None = None
    ) -> pd.DataFrame:
        """Mean, standard error and percentiles of the capital per year.

        Returns
        -------
        pd.DataFrame
            Index ``projectiejaar`` (0 … horizon); an added ``leeftijd``
            column gives the age reached at the end of each year.
        """
        percentiles = list(percentiles or DEFAULT_PERCENTILES)
        index = pd.Index(range(self.horizon + 1), name="projectiejaar")
        frame = _percentile_frame(self.wealth, index, percentiles)
        frame.insert(
            0,
            "leeftijd",
            [self.maatmens.leeftijd(self.basisjaar + t) for t in index],
        )
        return frame


def project_wealth(
    scenario_set,
    maatmens: Maatmens,
    lifecycle: Lifecycle = DEFAULT_LIFECYCLE,
    portefeuilles: tuple[Portefeuille, Portefeuille] | None = None,
    horizon: int | None = None,
    basisjaar: int | None = None,
    loonindexatie: Indexation = "price_inflation_nl",
    states: np.ndarray | None = None,
    returns: tuple[np.ndarray, np.ndarray] | None = None,
) -> WealthProjection:
    """Project the capital of *maatmens* over the scenario set.

    Parameters
    ----------
    scenario_set:
        A loaded :class:`~dnb_p_set.ScenarioSet`.
    maatmens:
        The participant to project.
    lifecycle:
        Allocation schedule; defaults to :data:`DEFAULT_LIFECYCLE`.
    portefeuilles:
        ``(rendementsportefeuille, beschermingsportefeuille)``; defaults to
        :data:`DEFAULT_PORTEFEUILLES`.
    horizon:
        Number of years to project.  Defaults to everything the set allows.
    basisjaar:
        Calendar year of projection year 0, which fixes the starting age.
        Defaults to the current calendar year.
    loonindexatie:
        How the pensionable salary — and with it the contribution — grows.
        A variable name or alias (default ``"price_inflation_nl"``) indexes
        the salary on that simulated series, a number applies a fixed annual
        rate, and ``"geen"`` keeps the salary flat.
    states:
        Pre-computed state matrix, to avoid rebuilding it per maatmens.
    returns:
        Pre-computed ``(rendement, bescherming)`` return matrices covering at
        least *horizon* years, to avoid recomputing them per maatmens.

    Returns
    -------
    WealthProjection
    """
    portefeuilles = portefeuilles or DEFAULT_PORTEFEUILLES
    rendement_p, bescherming_p = portefeuilles
    basisjaar = int(basisjaar) if basisjaar is not None else _dt.date.today().year

    equity = scenario_set.get("equity_return")
    n_scenarios = equity.shape[0]
    n_t = scenario_set.get("state_variable_1").shape[1]
    # Rolling the bond needs the curve one year beyond the last return year.
    max_horizon = min(equity.shape[1], n_t - 1)
    horizon = max_horizon if horizon is None else int(horizon)
    if not 1 <= horizon <= max_horizon:
        raise ValueError(f"horizon must lie in [1, {max_horizon}], got {horizon}")

    if returns is None:
        r_rendement = portefeuille_returns(
            scenario_set, rendement_p, horizon, states=states
        )
        r_bescherming = portefeuille_returns(
            scenario_set, bescherming_p, horizon, states=states
        )
    else:
        r_rendement, r_bescherming = (arr[:, :horizon] for arr in returns)

    # The weight for a year is set by the age reached at the start of it.
    jaren = basisjaar + np.arange(horizon)
    leeftijden = jaren - maatmens.geboortejaar
    weight = lifecycle.rendement_weight(leeftijden)

    r_portefeuille = (
        weight[None, :] * r_rendement + (1.0 - weight)[None, :] * r_bescherming
    )

    contributing = (leeftijden < maatmens.pensioenleeftijd).astype(float)
    premie = (
        maatmens.jaarpremie
        * _salary_factor(scenario_set, horizon, n_scenarios, loonindexatie)
        * contributing[None, :]
    )

    wealth = np.empty((n_scenarios, horizon + 1), dtype=float)
    wealth[:, 0] = float(maatmens.pensioenvermogen)
    for t in range(horizon):
        wealth[:, t + 1] = (wealth[:, t] + premie[:, t]) * (1.0 + r_portefeuille[:, t])

    schedule = pd.DataFrame(
        {
            "kalenderjaar": jaren,
            "leeftijd": leeftijden,
            "w_rendement": weight,
            "w_bescherming": 1.0 - weight,
            "premie": premie.mean(axis=0),
        },
        index=pd.Index(range(horizon), name="projectiejaar"),
    )

    return WealthProjection(
        maatmens=maatmens,
        lifecycle=lifecycle,
        basisjaar=basisjaar,
        portefeuilles=portefeuilles,
        schedule=schedule,
        wealth=wealth,
        returns=r_portefeuille,
    )
