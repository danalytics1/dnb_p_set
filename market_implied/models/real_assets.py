"""
Real assets: commodities and yield-plus-growth exposures (unlisted property,
core infrastructure, farmland).

Commodities
-----------
A fully collateralised commodity futures position earns

.. math::  E[R] = \\underbrace{r_f}_{\\text{onderpand}}
                + \\underbrace{y_{roll}}_{\\text{rolrendement}}
                + \\underbrace{E[\\Delta S]}_{\\text{spotprijsverandering}}
                + \\underbrace{\\delta}_{\\text{herbalanceringsrendement}}

The roll yield is the one genuinely market-implied component: it is the
annualised slope of today's futures curve, i.e. how much the position gains or
loses as contracts converge to spot.  Erb & Harvey (2006) show that the shape
of the futures curve is the dominant driver of the cross-section of commodity
returns, and Gorton & Rouwenhorst (2006) document the historical futures risk
premium.  Bhardwaj, Gorton & Rouwenhorst (2015) revisit both after the
post-2004 financialisation of the asset class and find much weaker realised
premia, which is why the default configuration is conservative.

The expected spot change is an assumption.  The default is that spot commodity
prices keep pace with inflation and no more — i.e. a zero *real* spot return,
consistent with Erb & Harvey (2006) and with the long-run evidence that real
commodity prices are trendless to mildly declining.

The rebalancing (or "diversification") return is the well-documented gap
between the geometric return of an equally weighted rebalanced basket and the
average geometric return of its constituents (Erb & Harvey, 2006, section on
the diversification return; Willenbrock, 2011).  It is real but modest and is
tagged as an assumption.

Yield and growth
----------------
For unlisted real estate and core infrastructure the observable is a cash
yield (net initial yield, cap rate, or distribution yield) rather than a
traded multiple:

.. math::  E[R] = NIY - capex + \\pi \\cdot \\rho + g_{real}
                + \\Delta_{yield} + illiquiditeitspremie

with :math:`\\rho` the inflation pass-through of rents or regulated tariffs.
The yield-shift block treats the cap rate the way the credit model treats the
OAS: a gap versus a reference level closes with a half-life.  Because appraisal-
based valuations are smoothed and lag transaction prices (Geltner, 1991;
Marcato & Key, 2007), the note on this block flags that the starting yield is
less "market implied" than a screen price.

References
----------
Bhardwaj, G., Gorton, G. & Rouwenhorst, K. G. (2015). Facts and fantasies about
commodity futures ten years later. NBER working paper 21243.

Erb, C. & Harvey, C. (2006). The strategic and tactical value of commodity
futures. *Financial Analysts Journal* 62(2), 69-97.

Geltner, D. (1991). Smoothing in appraisal-based returns. *Journal of Real
Estate Finance and Economics* 4(3), 327-345.

Gorton, G. & Rouwenhorst, K. G. (2006). Facts and fantasies about commodity
futures. *Financial Analysts Journal* 62(2), 47-68.

Marcato, G. & Key, T. (2007). Smoothing and implications for asset allocation
choices. *Journal of Portfolio Management* 33(5), 85-98.

Willenbrock, S. (2011). Diversification return, portfolio rebalancing, and the
commodity return puzzle. *Financial Analysts Journal* 67(4), 42-49.
"""

from __future__ import annotations

from ..blocks import ASSUMPTION, DERIVED, MARKET, BuildingBlock, ReturnBuildUp
from .base import (
    AssetSpec,
    ModelContext,
    ModelError,
    annualise_price_effect,
    register,
    reversion_fraction,
)

__all__ = ["build_commodities", "build_yield_and_growth"]


@register("commodities")
def build_commodities(spec: AssetSpec, ctx: ModelContext) -> ReturnBuildUp:
    """Fully collateralised commodity futures.

    Parameters (``params``)
    -----------------------
    quotes:
        Dotted path with ``roll_yield`` (annualised slope of the futures
        curve, negative in contango).
    real_spot_growth:
        Expected **real** spot price change per year; default 0.
    rebalancing_return:
        Diversification return of the index rebalancing rule.
    inflation_pass_through:
        Fraction of expected inflation passed into spot prices; default 1.
    """
    quotes = ctx.snapshot.instrument(spec.param("quotes"))
    if "roll_yield" not in quotes:
        raise ModelError(f"{spec.key}: quotes need a roll_yield")
    roll = float(quotes["roll_yield"])

    blocks = [
        BuildingBlock(
            name="roll_yield",
            value=roll,
            source=MARKET,
            label="Rolrendement",
            note=(
                "Geannualiseerde helling van de huidige termijnmarktcurve; negatief "
                "bij contango, positief bij backwardation (Erb & Harvey, 2006)."
            ),
        )
    ]

    pass_through = float(spec.opt("inflation_pass_through", 1.0))
    inflation = ctx.expected_inflation(spec.currency) * pass_through
    real_spot = float(spec.opt("real_spot_growth", 0.0))
    blocks.append(
        BuildingBlock(
            name="spot_price_change",
            value=inflation + real_spot,
            source=DERIVED if real_spot == 0.0 else ASSUMPTION,
            label="Spotprijsontwikkeling",
            note=(
                f"Verwachte inflatie x doorwerking {pass_through:.0%} plus een reële "
                f"spotgroei van {real_spot:.2%}. De aanname van nul reële spotgroei "
                "sluit aan bij het langetermijnbewijs voor trendloze reële "
                "grondstofprijzen (Erb & Harvey, 2006)."
            ),
        )
    )

    rebalancing = float(spec.opt("rebalancing_return", 0.0))
    if rebalancing != 0.0:
        blocks.append(
            BuildingBlock(
                name="rebalancing_return",
                value=rebalancing,
                source=ASSUMPTION,
                label="Herbalanceringsrendement",
                note=(
                    "Meetkundig voordeel van periodiek herwegen van een mandje met "
                    "lage onderlinge correlatie (Willenbrock, 2011)."
                ),
            )
        )

    diagnostics = {"roll_yield": roll, "expected_inflation": inflation}
    return ctx.finish(spec, blocks, diagnostics)


@register("yield_and_growth")
def build_yield_and_growth(spec: AssetSpec, ctx: ModelContext) -> ReturnBuildUp:
    """Cash-yield driven real assets: unlisted property, core infrastructure.

    Parameters (``params``)
    -----------------------
    quotes:
        Dotted path with ``income_yield`` and optionally ``long_run_yield``.
    capex_drag:
        Annual capital expenditure needed to maintain the income stream, as a
        fraction of value.  Subtracted from the income yield.
    real_growth:
        Real growth of net income beyond inflation.
    inflation_pass_through:
        Fraction of inflation that flows into rents or tariffs.
    yield_reversion_half_life:
        Half-life of the reversion of the income yield to ``long_run_yield``.
    yield_duration:
        Sensitivity of value to a change in the income yield.  Defaults to
        ``1 / income_yield``, the Gordon-growth duration of a perpetuity.
    illiquidity_premium:
        Compensation for the lock-up.
    """
    quotes = ctx.snapshot.instrument(spec.param("quotes"))
    if "income_yield" not in quotes:
        raise ModelError(f"{spec.key}: quotes need an income_yield")
    income_yield = float(quotes["income_yield"])

    blocks = [
        BuildingBlock(
            name="income_yield",
            value=income_yield,
            source=MARKET,
            label="Direct rendement",
            note=(
                "Netto aanvangsrendement / cap rate op basis van actuele taxatie- of "
                "transactiewaarden. Taxatiewaarden lopen achter op transactieprijzen "
                "(Geltner, 1991), dus dit is minder 'marktprijs' dan een beursnotering."
            ),
        )
    ]

    capex = float(spec.opt("capex_drag", 0.0))
    if capex != 0.0:
        blocks.append(
            BuildingBlock(
                name="capex_drag",
                value=-abs(capex),
                source=ASSUMPTION,
                label="Af: onderhoudsinvesteringen",
                note="Investeringen nodig om het inkomen in stand te houden; verlagen het netto rendement.",
            )
        )

    pass_through = float(spec.opt("inflation_pass_through", 1.0))
    inflation = ctx.expected_inflation(spec.currency) * pass_through
    blocks.append(
        BuildingBlock(
            name="expected_inflation",
            value=inflation,
            source=MARKET,
            label="Verwachte inflatie",
            note=(
                f"Breakeven-inflatie minus inflatierisicopremie, x doorwerking "
                f"{pass_through:.0%} in huren/tarieven."
            ),
        )
    )

    real_growth = float(spec.opt("real_growth", 0.0))
    if real_growth != 0.0:
        blocks.append(
            BuildingBlock(
                name="real_growth",
                value=real_growth,
                source=ASSUMPTION,
                label="Reële inkomensgroei",
                note="Reële groei van de netto huur- of tariefinkomsten bovenop inflatie.",
            )
        )

    half_life = spec.params.get("yield_reversion_half_life", None)
    long_run_yield = spec.opt("long_run_yield", quotes.get("long_run_yield"))
    if ctx.apply_valuation and half_life is not None and long_run_yield is not None:
        theta = reversion_fraction(ctx.horizon, float(half_life))
        target = income_yield + theta * (float(long_run_yield) - income_yield)
        yield_duration = float(spec.opt("yield_duration", 1.0 / income_yield))
        value = annualise_price_effect(
            -yield_duration * (target - income_yield), ctx.horizon
        )
        blocks.append(
            BuildingBlock(
                name="yield_shift",
                value=value,
                source=ASSUMPTION,
                label="Waarderingsverandering (yield shift)",
                note=(
                    f"Aanvangsrendement beweegt van {income_yield:.2%} naar "
                    f"{target:.2%} ({theta:.0%} van de weg naar "
                    f"{float(long_run_yield):.2%}); waardegevoeligheid "
                    f"{yield_duration:.1f}."
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
                note=(
                    "Vergoeding voor de lock-up. Niet af te lezen uit een prijs en "
                    "empirisch omstreden van omvang."
                ),
            )
        )

    blocks.append(ctx.local_rf_offset(spec.currency))

    diagnostics = {
        "income_yield": income_yield,
        "expected_inflation": inflation,
        "local_risk_free": ctx.risk_free(spec.currency),
    }
    return ctx.finish(spec, blocks, diagnostics)
