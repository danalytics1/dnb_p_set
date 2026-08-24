"""
Equity and equity-like asset classes.

Two independent routes to a market-implied equity return are provided.  They
are deliberately kept side by side: the first is transparent and additive, the
second is internally consistent with the market price, and disagreement
between them is informative.

1. Grinold-Kroner decomposition
-------------------------------
.. math::

    E[R] \\approx \\underbrace{DY}_{\\text{dividendrendement}}
        + \\underbrace{NBB}_{\\text{netto inkoop eigen aandelen}}
        + \\underbrace{\\pi}_{\\text{verwachte inflatie}}
        + \\underbrace{g_{real}}_{\\text{reële winstgroei p/a}}
        + \\underbrace{\\Delta v}_{\\text{waarderingsverandering}}

Grinold & Kroner (2002).  The first three terms are read off market prices
(dividend and buyback yields from the index, expected inflation from the
breakeven curve net of the inflation risk premium).  Real per-share earnings
growth is an assumption: Bernstein & Arnott (2003) show that per-share growth
lags aggregate economic growth by roughly 2 percentage points a year because of
net issuance and entrepreneurial dilution, and Straehl & Ibbotson (2017)
confirm that long-run real per-share earnings growth has been well below real
GDP growth.  The valuation term is optional and reverts CAPE (or any other
supplied multiple) toward a reference level with a configurable half-life
(Campbell & Shiller, 1988, 1998; Asness, 2012).

2. Implied cost of equity (Damodaran)
-------------------------------------
Solve for the internal rate of return :math:`r` that equates today's index
price to the present value of a two-stage cash-flow stream:

.. math::

    1 = \\sum_{t=1}^{n} \\frac{y (1+g_1)^t}{(1+r)^t}
        + \\frac{y (1+g_1)^n (1+g_\\infty)}{(r - g_\\infty)(1+r)^n}

with :math:`y` the net payout yield (dividends plus net buybacks over price).
Following Damodaran (2024) the terminal growth rate is capped at the long-term
risk-free rate, since no company can grow faster than the economy forever and
the risk-free rate is a reasonable proxy for nominal growth.  The implied
equity risk premium is :math:`r - r_f`.

References
----------
Asness, C. (2012). An old friend: the stock market's Shiller P/E. AQR.

Bernstein, W. & Arnott, R. (2003). Earnings growth: the two percent dilution.
*Financial Analysts Journal* 59(5), 47-55.

Campbell, J. & Shiller, R. (1988). Stock prices, earnings, and expected
dividends. *Journal of Finance* 43(3), 661-676.

Campbell, J. & Shiller, R. (1998). Valuation ratios and the long-run stock
market outlook. *Journal of Portfolio Management* 24(2), 11-26.

Damodaran, A. (2024). *Equity Risk Premiums: Determinants, Estimation and
Implications.* NYU Stern working paper.

Grinold, R. & Kroner, K. (2002). The equity risk premium. *Investment
Insights* 5(3), BGI.

Straehl, P. & Ibbotson, R. (2017). The long-run drivers of stock returns:
total payouts and the real economy. *Financial Analysts Journal* 73(3), 32-52.
"""

from __future__ import annotations

from typing import Optional

from ..blocks import ASSUMPTION, DERIVED, MARKET, BuildingBlock, ReturnBuildUp
from .base import (
    AssetSpec,
    ModelContext,
    ModelError,
    annualise_price_effect,
    register,
    reversion_fraction,
)

__all__ = ["build_grinold_kroner", "implied_cost_of_equity"]


def implied_cost_of_equity(
    payout_yield: float,
    growth_near_term: float,
    terminal_growth: float,
    n_years: int = 5,
    lower: float = -0.5,
    upper: float = 1.0,
    tolerance: float = 1e-10,
    max_iter: int = 200,
) -> float:
    """Solve the two-stage DDM for the internal rate of return.

    Parameters
    ----------
    payout_yield:
        Net cash returned to shareholders over price (dividends plus net
        buybacks), i.e. :math:`CF_0 / P_0`.
    growth_near_term:
        Nominal growth of that cash flow during the first stage.
    terminal_growth:
        Perpetual nominal growth after the first stage.  Must be below the
        solved discount rate; Damodaran caps it at the long risk-free rate.
    n_years:
        Length of the first stage.

    Returns
    -------
    float
        The implied cost of equity (nominal, annually compounded).

    Notes
    -----
    Solved by bisection, which needs no external dependency and is robust for
    this monotone problem: present value is strictly decreasing in ``r`` on
    ``(terminal_growth, inf)``.
    """
    if payout_yield <= 0:
        raise ModelError("payout yield must be positive to invert the DDM")
    if n_years < 1:
        raise ModelError("the first stage must span at least one year")

    def present_value(r: float) -> float:
        if r <= terminal_growth:
            return float("inf")
        pv = 0.0
        cf = payout_yield
        for t in range(1, n_years + 1):
            cf *= 1.0 + growth_near_term
            pv += cf / (1.0 + r) ** t
        terminal = cf * (1.0 + terminal_growth) / (r - terminal_growth)
        return pv + terminal / (1.0 + r) ** n_years

    lo = max(lower, terminal_growth + 1e-6)
    hi = upper
    if present_value(hi) > 1.0:
        raise ModelError(
            "no implied cost of equity below the upper bracket; check the inputs"
        )
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if present_value(mid) > 1.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tolerance:
            break
    return 0.5 * (lo + hi)


@register("grinold_kroner")
def build_grinold_kroner(spec: AssetSpec, ctx: ModelContext) -> ReturnBuildUp:
    """Grinold-Kroner build-up for equity, listed real estate and infrastructure.

    Parameters (``params``)
    -----------------------
    quotes:
        Dotted path into ``snapshot.instruments`` with the market observables:
        ``dividend_yield``, ``net_buyback_yield``, and optionally ``cape``,
        ``forward_pe``, ``price_to_book``, ``roe``, ``payout_ratio``.
    real_growth:
        Assumed real per-share earnings/dividend growth.
    real_growth_source:
        ``"assumption"`` (default) or ``"sustainable"``.  The latter uses the
        fundamental growth identity ``g = ROE x (1 - payout ratio)`` deflated
        by expected inflation (Damodaran, 2024).
    valuation_metric:
        Which quote to mean revert (``"cape"`` by default).
    fair_value:
        Reference level of that metric.
    valuation_half_life:
        Half-life of the reversion in years; ``null`` disables the block.
    inflation_pass_through:
        Fraction of expected inflation that feeds into nominal earnings.
        Defaults to 1.0.
    illiquidity_premium:
        Optional add-on for unlisted variants.
    """
    quotes = ctx.snapshot.instrument(spec.param("quotes"))
    currency = spec.currency
    blocks = []

    def quoted(key: str, default=None) -> Optional[float]:
        return float(quotes[key]) if key in quotes else default

    # ---- cash returned to shareholders ---------------------------------
    dividend_yield = quoted("dividend_yield")
    if dividend_yield is None:
        raise ModelError(f"{spec.key}: quotes need a dividend_yield")
    blocks.append(
        BuildingBlock(
            name="dividend_yield",
            value=dividend_yield,
            source=MARKET,
            label="Dividendrendement",
            note="Dividend over de huidige indexkoers; direct waarneembaar.",
        )
    )

    buyback = quoted("net_buyback_yield", 0.0)
    if buyback != 0.0:
        blocks.append(
            BuildingBlock(
                name="net_buyback_yield",
                value=buyback,
                source=MARKET,
                label="Netto inkoop eigen aandelen",
                note=(
                    "Netto verandering van het aantal uitstaande aandelen. Negatief "
                    "bij verwatering. Samen met dividend het totale payout yield "
                    "(Straehl & Ibbotson, 2017)."
                ),
            )
        )

    # ---- inflation ------------------------------------------------------
    pass_through = float(spec.opt("inflation_pass_through", 1.0))
    inflation = ctx.expected_inflation(currency) * pass_through
    blocks.append(
        BuildingBlock(
            name="expected_inflation",
            value=inflation,
            source=MARKET,
            label="Verwachte inflatie",
            note=(
                f"Breakeven-inflatie op {ctx.horizon:g} jaar minus de "
                "inflatierisicopremie"
                + (f", x doorwerking {pass_through:.0%}" if pass_through != 1.0 else "")
                + "."
            ),
        )
    )

    # ---- real growth ----------------------------------------------------
    growth_source = spec.opt("real_growth_source", "assumption")
    if growth_source == "sustainable":
        roe = quoted("roe")
        payout_ratio = quoted("payout_ratio")
        if roe is None or payout_ratio is None:
            raise ModelError(
                f"{spec.key}: sustainable growth needs 'roe' and 'payout_ratio' quotes"
            )
        nominal_growth = roe * (1.0 - payout_ratio)
        real_growth = (1.0 + nominal_growth) / (1.0 + inflation) - 1.0
        growth_note = (
            f"Fundamentele groei g = ROE {roe:.1%} x (1 - payout {payout_ratio:.0%}) "
            f"= {nominal_growth:.2%} nominaal, gedefleerd met de verwachte inflatie "
            "(Damodaran, 2024)."
        )
        growth_kind = DERIVED
    else:
        real_growth = float(spec.param("real_growth"))
        growth_note = (
            "Aangenomen reële winstgroei per aandeel. Per-aandeel groei blijft "
            "structureel achter bij economische groei door netto uitgifte en "
            "verwatering (Bernstein & Arnott, 2003; Straehl & Ibbotson, 2017)."
        )
        growth_kind = ASSUMPTION
    blocks.append(
        BuildingBlock(
            name="real_growth",
            value=real_growth,
            source=growth_kind,
            label="Reële winstgroei",
            note=growth_note,
        )
    )

    # ---- valuation ------------------------------------------------------
    half_life = spec.params.get("valuation_half_life", None)
    metric = spec.opt("valuation_metric", "cape")
    fair_value = spec.params.get("fair_value")
    current = quoted(metric)
    if ctx.apply_valuation and half_life is not None and fair_value and current:
        theta = reversion_fraction(ctx.horizon, float(half_life))
        target = current + theta * (float(fair_value) - current)
        value = annualise_price_effect(target / current - 1.0, ctx.horizon)
        blocks.append(
            BuildingBlock(
                name="valuation_change",
                value=value,
                source=ASSUMPTION,
                label="Waarderingsverandering",
                note=(
                    f"{metric.upper()} beweegt van {current:.1f} naar {target:.1f} "
                    f"({theta:.0%} van de weg naar {float(fair_value):.1f}, "
                    f"halfwaardetijd {float(half_life):g}j); geannualiseerd over "
                    f"{ctx.horizon:g} jaar (Campbell & Shiller, 1998)."
                ),
            )
        )

    illiquidity = float(spec.opt("illiquidity_premium", 0.0))
    if illiquidity != 0.0:
        blocks.append(
            BuildingBlock(
                name="illiquidity_premium",
                value=illiquidity,
                source=ASSUMPTION,
                label="Illiquiditeitspremie",
                note="Vergoeding voor beperkte verhandelbaarheid van niet-genoteerde varianten.",
            )
        )

    # ---- convert total return into a premium ----------------------------
    blocks.append(ctx.local_rf_offset(currency))

    diagnostics = {
        "dividend_yield": dividend_yield,
        "net_payout_yield": dividend_yield + (buyback or 0.0),
        "expected_inflation": inflation,
        "real_growth": real_growth,
        "local_risk_free": ctx.risk_free(currency),
    }
    if metric in quotes:
        diagnostics[metric] = float(quotes[metric])

    # Cross-check against the implied cost of equity where possible.
    payout_yield = dividend_yield + max(buyback or 0.0, 0.0)
    if payout_yield > 0:
        try:
            long_rf = float(ctx.risk_free_model(currency).curve.zero(30))
            ice = implied_cost_of_equity(
                payout_yield=payout_yield,
                growth_near_term=float(spec.opt("near_term_growth", inflation + real_growth)),
                terminal_growth=min(long_rf, inflation + real_growth),
                n_years=int(spec.opt("first_stage_years", 5)),
            )
            diagnostics["implied_cost_of_equity"] = ice
            diagnostics["implied_erp_vs_long_rf"] = ice - long_rf
        except ModelError:
            pass

    return ctx.finish(spec, blocks, diagnostics)
