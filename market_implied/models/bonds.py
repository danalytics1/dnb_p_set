"""
Rate-driven asset classes: cash, nominal government bonds and index-linked bonds.

Nominal government bonds
------------------------
Under the affine decomposition of the yield curve, rolling a bond portfolio of
constant maturity :math:`D` earns the expected short rate plus the term premium
at that maturity, so

.. math::  E[R(H)] = r_f(H) + TP(D) + s - EL

with :math:`s` an optional sovereign spread over the reference (swap or Bund)
curve and :math:`EL` the expected sovereign credit loss.

This is exact at :math:`D = H` under the ``rolled_cash`` convention:
:math:`r_f(H) + TP(H) = z(H)`, the horizon-matched spot rate, which is what a
buy-and-hold zero-coupon investor actually earns.  It deliberately contains no
"yield normalisation": deviating from forward-implied rates means overriding
market prices, which is out of scope for a market-implied framework.

Index-linked bonds
------------------
The nominal expected return of an inflation-linked bond is its real yield plus
*realised* inflation.  Since

.. math::  z_{nom}(D) = z_{real}(D) + \\pi_{BE}(D)
           \\quad\\text{and}\\quad \\pi_{BE} = E[\\pi] + IRP - LP

the nominal expected return of a linker equals that of a nominal bond of the
same duration **minus** the inflation risk premium it gives up, **plus** any
liquidity premium it earns:

.. math::  E[R_{ILB}(H)] = r_f(H) + TP(D) - IRP(D) + LP

References
----------
D'Amico, S., Kim, D. & Wei, M. (2018). Tips from TIPS: the informational
content of Treasury inflation-protected security prices. *Journal of Financial
and Quantitative Analysis* 53(1), 395-436.

Grishchenko, O. & Huang, J. (2013). The inflation risk premium: evidence from
the TIPS market. *Journal of Fixed Income* 22(4), 5-30.

Pflueger, C. & Viceira, L. (2016). Return predictability in the Treasury
market: real rates, inflation, and liquidity. In *Handbook of Fixed-Income
Securities*, Wiley.
"""

from __future__ import annotations

from ..blocks import ASSUMPTION, MARKET, BuildingBlock, ReturnBuildUp
from .base import AssetSpec, ModelContext, register

__all__ = ["build_cash", "build_nominal_bond", "build_index_linked_bond"]


@register("cash")
def build_cash(spec: AssetSpec, ctx: ModelContext) -> ReturnBuildUp:
    """Cash / money market.

    By construction the premium is zero: cash *is* the risk-free building
    block.  An optional ``deposit_spread`` captures the fact that an
    institutional depositor typically earns slightly less (or, when placing
    money at €STR-linked repo, slightly more) than the modelled risk-free rate.
    """
    blocks = []
    spread = float(spec.opt("deposit_spread", 0.0))
    if spread != 0.0:
        blocks.append(
            BuildingBlock(
                name="deposit_spread",
                value=spread,
                source=MARKET,
                label="Depositospread",
                note="Verschil tussen feitelijke geldmarktvergoeding en de gemodelleerde risicovrije rente.",
            )
        )
    diagnostics = {
        "spot_rate": ctx.risk_free_model(spec.currency).spot(ctx.horizon),
    }
    return ctx.finish(spec, blocks, diagnostics)


def _sovereign_blocks(spec: AssetSpec, ctx: ModelContext):
    """Spread and expected-loss blocks shared by sovereign bond portfolios."""
    blocks = []
    spread_path = spec.opt("spread_source")
    spread = float(spec.opt("spread", 0.0))
    if spread_path:
        spread = ctx.snapshot.observable(spread_path, "spread", default=spread)
    if spread != 0.0:
        blocks.append(
            BuildingBlock(
                name="sovereign_spread",
                value=spread,
                source=MARKET,
                label="Landenspread",
                note=(
                    "Waargenomen spread van de staatsobligatie-index boven de "
                    "referentiecurve (swap of AAA-staat)."
                ),
            )
        )
    expected_loss = float(spec.opt("expected_credit_loss", 0.0))
    if expected_loss != 0.0:
        blocks.append(
            BuildingBlock(
                name="expected_credit_loss",
                value=-abs(expected_loss),
                source=ASSUMPTION,
                label="Af: verwacht kredietverlies",
                note=(
                    "Verwachte wanbetalingskosten (kans x LGD) op basis van "
                    "historische soevereine defaultstatistieken; niet uit de "
                    "marktprijs af te leiden zonder de risicopremie mee te nemen."
                ),
            )
        )
    return blocks, spread, expected_loss


@register("nominal_bond")
def build_nominal_bond(spec: AssetSpec, ctx: ModelContext) -> ReturnBuildUp:
    """Constant-duration nominal government bond portfolio.

    Parameters (``params``)
    -----------------------
    duration:
        Effective duration of the index, in years.
    spread / spread_source:
        Optional sovereign spread over the reference curve.
    expected_credit_loss:
        Optional expected annual credit loss.
    """
    duration = float(spec.param("duration"))
    rf_model = ctx.risk_free_model(spec.currency)

    blocks = [rf_model.duration_block(ctx.horizon, duration)]
    sov_blocks, spread, _ = _sovereign_blocks(spec, ctx)
    blocks.extend(sov_blocks)

    diagnostics = {
        "index_yield": float(rf_model.curve.zero(duration)) + spread,
        "spot_rate": rf_model.spot(ctx.horizon),
        "term_premium_at_duration": rf_model.term_premium_at(duration),
        "duration": duration,
    }
    return ctx.finish(spec, blocks, diagnostics)


@register("index_linked_bond")
def build_index_linked_bond(spec: AssetSpec, ctx: ModelContext) -> ReturnBuildUp:
    """Inflation-linked government bonds, expressed as a **nominal** return.

    Parameters (``params``)
    -----------------------
    duration:
        Real (effective) duration of the index.
    liquidity_premium:
        Extra yield the linker market pays for its lower liquidity.  Positive
        values raise the expected return.
    expected_credit_loss:
        Optional expected annual credit loss.
    """
    duration = float(spec.param("duration"))
    rf_model = ctx.risk_free_model(spec.currency)

    blocks = [rf_model.duration_block(ctx.horizon, duration)]

    irp = float(ctx.snapshot.inflation_risk_premium(spec.currency)(duration))
    blocks.append(
        BuildingBlock(
            name="inflation_risk_premium",
            value=-irp,
            source=MARKET,
            label="Af: inflatierisicopremie",
            note=(
                "Een inflatiegekoppelde obligatie draagt geen inflatierisico en "
                "ontvangt de inflatierisicopremie die in de nominale curve zit dus "
                "niet (Grishchenko & Huang, 2013; D'Amico, Kim & Wei, 2018)."
            ),
        )
    )

    liquidity = float(spec.opt("liquidity_premium", 0.0))
    if liquidity != 0.0:
        blocks.append(
            BuildingBlock(
                name="ilb_liquidity_premium",
                value=liquidity,
                source=ASSUMPTION,
                label="Liquiditeitspremie linkers",
                note=(
                    "De markt voor inflatiegekoppelde obligaties is minder liquide "
                    "dan de nominale markt; de breakeven onderschat de verwachte "
                    "inflatie daardoor (Pflueger & Viceira, 2016)."
                ),
            )
        )

    sov_blocks, _, _ = _sovereign_blocks(spec, ctx)
    blocks.extend(b for b in sov_blocks if b.name == "expected_credit_loss")

    diagnostics = {
        "real_yield": float(ctx.snapshot.real_curve(spec.currency).zero(duration)),
        "breakeven_inflation": ctx.snapshot.breakeven_inflation(spec.currency, duration),
        "expected_inflation": ctx.snapshot.expected_inflation(spec.currency, duration),
        "inflation_risk_premium": irp,
        "duration": duration,
    }
    return ctx.finish(spec, blocks, diagnostics)
