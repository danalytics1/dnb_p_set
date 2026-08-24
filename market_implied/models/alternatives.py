"""
Asset classes priced off another asset class: private equity, listed proxies.

Private markets have no observable market price, so their expected return
cannot be read off a screen.  The defensible market-implied approach is to
price them **relative** to the listed market they are economically equivalent
to, and to add only those components that are genuinely different: leverage,
sector/size tilt and illiquidity.

.. math::

    RP_{PE} = \\beta \\cdot RP_{listed} + illiquiditeitspremie - kostenverschil

The evidence for the beta approach is strong.  L'Her, Stoyanova, Shaw, Scott &
Lai (2016) show that buyout returns are closely matched by a levered small/mid
cap public equity portfolio.  Harris, Jenkinson & Kaplan (2014) find buyout
funds have outperformed public equity by roughly 20-27% over a fund's life
(about 3% a year), while Phalippou (2020) argues that measured against a small
cap index the outperformance largely disappears once fee reporting is treated
consistently.  The default configuration therefore uses a leverage-driven beta
above one and a modest, explicitly flagged illiquidity premium, and the fee
term is exposed so a user can move between gross and net.

References
----------
Harris, R., Jenkinson, T. & Kaplan, S. (2014). Private equity performance:
what do we know? *Journal of Finance* 69(5), 1851-1882.

L'Her, J.-F., Stoyanova, R., Shaw, K., Scott, W. & Lai, C. (2016). A bottom-up
approach to the risk-adjusted performance of the buyout fund market.
*Financial Analysts Journal* 72(4), 36-48.

Phalippou, L. (2020). An inconvenient fact: private equity returns and the
billionaire factory. *Journal of Investing* 30(1), 11-39.

Ang, A., Papanikolaou, D. & Westerfield, M. (2014). Portfolio choice with
illiquid assets. *Management Science* 60(11), 2737-2761.
"""

from __future__ import annotations

from ..blocks import ASSUMPTION, DERIVED, BuildingBlock, ReturnBuildUp
from .base import AssetSpec, ModelContext, ModelError, register

__all__ = ["build_levered_beta"]


@register("levered_beta")
def build_levered_beta(spec: AssetSpec, ctx: ModelContext) -> ReturnBuildUp:
    """Price an asset class as a levered claim on a listed reference.

    Parameters (``params``)
    -----------------------
    reference:
        Key of the asset class whose risk premium is the starting point.  Must
        also appear in ``depends_on`` so the engine evaluates it first.
    beta:
        Multiplier applied to the reference risk premium.
    illiquidity_premium:
        Additional premium for the lock-up.
    fee_drag:
        Net fee difference versus the listed reference, subtracted.
    """
    reference = spec.param("reference")
    if reference not in ctx.peers:
        raise ModelError(
            f"{spec.key}: reference asset class {reference!r} has not been evaluated; "
            "add it to 'depends_on'"
        )
    ref = ctx.peers[reference]
    beta = float(spec.opt("beta", 1.0))

    # Scale the *economic* premium (excess over rolled cash), not the reported
    # one: under the "spot" reporting convention the reported premium carries a
    # convention adjustment that must not be levered up.
    ref_premium = ref.risk_premium - ref.value_of("risk_free_convention_adjustment")

    blocks = [
        BuildingBlock(
            name="reference_premium",
            value=ref_premium * beta,
            source=DERIVED,
            label="Beta x risicopremie referentie",
            note=(
                f"{beta:.2f} x de risicopremie van '{ref.name}' ({ref_premium:.2%} "
                "boven doorgerold kasgeld). "
                "Beta boven 1 weerspiegelt de hogere financiële hefboom en de small/mid "
                "cap tilt van buyouts (L'Her e.a., 2016)."
            ),
        )
    ]

    illiquidity = float(spec.opt("illiquidity_premium", 0.0))
    if illiquidity != 0.0:
        blocks.append(
            BuildingBlock(
                name="illiquidity_premium",
                value=illiquidity,
                source=ASSUMPTION,
                label="Illiquiditeitspremie",
                note=(
                    "Vergoeding voor het niet kunnen verhandelen gedurende de looptijd "
                    "(Ang, Papanikolaou & Westerfield, 2014). De omvang is omstreden: "
                    "Phalippou (2020) vindt na correctie voor small caps nauwelijks "
                    "meerrendement."
                ),
            )
        )

    fee_drag = float(spec.opt("fee_drag", 0.0))
    if fee_drag != 0.0:
        blocks.append(
            BuildingBlock(
                name="fee_drag",
                value=-abs(fee_drag),
                source=ASSUMPTION,
                label="Af: extra kosten",
                note=(
                    "Verschil in beheer- en prestatievergoeding ten opzichte van de "
                    "genoteerde referentie. Zet op 0 als de referentiepremie al netto is."
                ),
            )
        )

    diagnostics = {
        "reference": reference,
        "reference_premium": ref_premium,
        "beta": beta,
    }
    return ctx.finish(spec, blocks, diagnostics)
