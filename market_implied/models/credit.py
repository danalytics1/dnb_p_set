"""
Spread products: investment grade, high yield, emerging market debt, mortgages.

The building blocks are the ones the user asked for:

.. math::

    E[R(H)] = \\underbrace{r_f(H)}_{\\text{kasgeld}}
            + \\underbrace{TP(D)}_{\\text{termijnpremie}}
            + \\underbrace{OAS}_{\\text{spread carry}}
            + \\underbrace{\\Delta_{spread}}_{\\text{spreadwaardering}}
            - \\underbrace{p \\cdot LGD}_{\\text{verwacht kredietverlies}}
            - \\underbrace{d}_{\\text{afwaarderingsdrag}}

Why the expected loss is *not* market implied
---------------------------------------------
It is tempting to back the default probability out of the spread itself, but
that mechanically sets the credit risk premium to zero: the spread is the sum
of expected loss **and** the compensation investors demand for bearing default,
downgrade and illiquidity risk.  Empirically the gap is large and persistent —
Giesecke, Longstaff, Schaefer & Strebulaev (2011) document that over 150 years
US corporate bond spreads averaged about twice realised credit losses, and
Elton, Gruber, Agrawal & Mann (2001) show expected default explains only a
small share of the spread.  The expected loss is therefore taken from
actuarial (rating-agency) default and recovery statistics, and everything left
over is reported as premium.

Downgrade drag
--------------
Rating-constrained investment grade indices must sell fallen angels at
distressed prices, which is a persistent negative contribution to index
returns not captured by defaults; Ng & Phelps (2011) estimate the drag and
Ben Dor & Xu (2015) document the subsequent fallen-angel rebound that the
index misses.  High yield indices experience the mirror image on rising stars.

Spread valuation
----------------
Credit spreads mean revert far faster than equity valuations (Duffee, 1998;
Collin-Dufresne, Goldstein & Martin, 2001).  With a spread duration
:math:`SD` and a target spread reached according to
:func:`~market_implied.models.base.reversion_fraction`, the annualised price
effect is derived from the cumulative repricing :math:`-SD \\cdot \\Delta OAS`.
Setting ``spread_reversion_half_life`` to ``null`` — or running with
``apply_valuation=False`` — disables this block and returns a pure carry view.

References
----------
Asvanunt, A. & Richardson, S. (2017). The credit risk premium. *Journal of
Fixed Income* 26(3), 6-24.

Ben Dor, A. & Xu, Z. (2015). Should equity investors care about corporate bond
prices? *Journal of Portfolio Management* 41(4).

Collin-Dufresne, P., Goldstein, R. & Martin, J. (2001). The determinants of
credit spread changes. *Journal of Finance* 56(6), 2177-2207.

Duffee, G. (1998). The relation between Treasury yields and corporate bond
yield spreads. *Journal of Finance* 53(6), 2225-2241.

Elton, E., Gruber, M., Agrawal, D. & Mann, C. (2001). Explaining the rate
spread on corporate bonds. *Journal of Finance* 56(1), 247-277.

Giesecke, K., Longstaff, F., Schaefer, S. & Strebulaev, I. (2011). Corporate
bond default risk: a 150-year perspective. *Journal of Financial Economics*
102(2), 233-250.

Ng, K. & Phelps, B. (2011). Capturing credit spread premium. *Financial
Analysts Journal* 67(3), 63-75.
"""

from __future__ import annotations

from typing import Optional

from ..blocks import ASSUMPTION, MARKET, BuildingBlock, ReturnBuildUp
from .base import (
    AssetSpec,
    ModelContext,
    annualise_price_effect,
    register,
    reversion_fraction,
)

__all__ = ["build_spread_product"]


@register("spread_product")
def build_spread_product(spec: AssetSpec, ctx: ModelContext) -> ReturnBuildUp:
    """Generic credit / spread building-block model.

    Parameters (``params``)
    -----------------------
    quotes:
        Dotted path into ``snapshot.instruments`` holding at least ``oas``;
        optionally ``effective_duration``, ``spread_duration`` and
        ``long_run_oas``.
    duration:
        Effective duration override (years).
    spread_duration:
        Spread duration override (years); defaults to the effective duration.
    spread_capture:
        Fraction of the quoted OAS actually earned as carry.  Defaults to 1.0.
        Values below one are used for indices where the quoted OAS overstates
        realisable carry (e.g. distressed constituents that will not be held).
    default_rate:
        Expected annual issuer default rate (decimal), through the cycle.
    recovery_rate:
        Expected recovery.  Expected loss is ``default_rate * (1 - recovery)``.
    downgrade_drag:
        Additional annual drag from forced selling of downgraded bonds.
    prepayment_drag:
        Annual drag from negative convexity / prepayments (mortgages).
    illiquidity_premium:
        Extra compensation for a non-traded or thinly traded exposure.
    long_run_oas:
        Spread level the OAS reverts to; defaults to the ``long_run_oas``
        quote in the snapshot.
    spread_reversion_half_life:
        Half-life in years of the spread mean reversion; ``null`` disables it.
    """
    quotes_path: Optional[str] = spec.opt("quotes")
    quotes = ctx.snapshot.instrument(quotes_path) if quotes_path else {}

    def quoted(key: str, default=None):
        if key in quotes:
            return float(quotes[key])
        return default

    duration = float(spec.opt("duration", quoted("effective_duration")) or 0.0)
    if duration <= 0:
        raise ValueError(f"{spec.key}: need a positive effective duration")
    spread_duration = float(
        spec.opt("spread_duration", quoted("spread_duration", duration))
    )
    oas = quoted("oas")
    if oas is None:
        oas = float(spec.param("oas"))
    oas = float(oas)

    rf_model = ctx.risk_free_model(spec.currency)
    blocks = [rf_model.duration_block(ctx.horizon, duration)]

    # ---- spread carry --------------------------------------------------
    capture = float(spec.opt("spread_capture", 1.0))
    blocks.append(
        BuildingBlock(
            name="credit_spread",
            value=oas * capture,
            source=MARKET,
            label="Kredietopslag (OAS)",
            note=(
                f"Waargenomen option-adjusted spread van {oas:.2%}"
                + (f", waarvan {capture:.0%} realiseerbaar geacht" if capture != 1.0 else "")
                + "; dit is de enige component die volledig uit de marktprijs komt."
            ),
        )
    )

    # ---- spread valuation ---------------------------------------------
    half_life = spec.params.get("spread_reversion_half_life", None)
    long_run = spec.opt("long_run_oas", quoted("long_run_oas"))
    if ctx.apply_valuation and half_life is not None and long_run is not None:
        theta = reversion_fraction(ctx.horizon, float(half_life))
        target = oas + theta * (float(long_run) - oas)
        price_effect = -spread_duration * (target - oas)
        value = annualise_price_effect(price_effect, ctx.horizon)
        blocks.append(
            BuildingBlock(
                name="spread_valuation",
                value=value,
                source=ASSUMPTION,
                label="Spreadwaardering",
                note=(
                    f"OAS beweegt van {oas:.2%} naar {target:.2%} "
                    f"({theta:.0%} van de weg naar het langetermijnniveau van "
                    f"{float(long_run):.2%}, halfwaardetijd {float(half_life):g}j); "
                    f"koerseffect -SD x dOAS over {ctx.horizon:g} jaar geannualiseerd."
                ),
            )
        )

    # ---- expected credit loss ------------------------------------------
    default_rate = float(spec.opt("default_rate", 0.0))
    recovery = float(spec.opt("recovery_rate", 0.4))
    expected_loss = default_rate * (1.0 - recovery)
    if expected_loss != 0.0:
        blocks.append(
            BuildingBlock(
                name="expected_credit_loss",
                value=-expected_loss,
                source=ASSUMPTION,
                label="Af: verwacht kredietverlies",
                note=(
                    f"Defaultkans {default_rate:.2%} x (1 - recovery {recovery:.0%}) "
                    "op basis van historische ratingbureau-statistieken; niet uit de "
                    "spread zelf afgeleid omdat de spread ook risicopremie bevat "
                    "(Giesecke e.a., 2011)."
                ),
            )
        )

    # ---- downgrade / index-rule drag -----------------------------------
    for name, label, note in (
        (
            "downgrade_drag",
            "Af: afwaarderingsverlies",
            "Gedwongen verkoop van fallen angels door ratinggrenzen in de index "
            "(Ng & Phelps, 2011; Ben Dor & Xu, 2015).",
        ),
        (
            "prepayment_drag",
            "Af: vervroegde-aflossingskosten",
            "Negatieve convexiteit en vervroegde aflossing bij hypotheken en MBS.",
        ),
    ):
        drag = float(spec.opt(name, 0.0))
        if drag != 0.0:
            blocks.append(
                BuildingBlock(
                    name=name,
                    value=-abs(drag),
                    source=ASSUMPTION,
                    label=label,
                    note=note,
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
                    "Extra vergoeding voor beperkte verhandelbaarheid; niet zichtbaar "
                    "in een genoteerde prijs en daarom een aanname."
                ),
            )
        )

    diagnostics = {
        "oas": oas,
        "index_yield": float(rf_model.curve.zero(duration)) + oas,
        "duration": duration,
        "spread_duration": spread_duration,
        "expected_credit_loss": expected_loss,
        "spread_over_expected_loss": (oas / expected_loss) if expected_loss else float("nan"),
    }
    return ctx.finish(spec, blocks, diagnostics)
