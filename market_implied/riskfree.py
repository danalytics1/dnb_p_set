"""
The risk-free building block, shared by **every** asset class.

Design requirement
------------------
The risk-free rate must follow identical logic for all asset classes, so that
the reported risk premia are mutually comparable and

.. math::  E[R_i(H)] = r_f(H) + RP_i(H)

holds by construction.  This module is therefore the only place where
:math:`r_f(H)` is defined.

Two conventions
---------------
``"rolled_cash"`` (default)
    :math:`r_f(H)` is the expected average **short** rate over the horizon,
    i.e. the return on rolling one-year deposits.  It is obtained from the
    market zero rate by stripping the term premium:

    .. math::  r_f(H) = z(H) - TP(H)

    This uses the standard affine decomposition of a nominal yield into an
    average-expected-short-rate component and a term premium (Adrian, Crump &
    Moench, 2013; Kim & Wright, 2005).  Because the expectations hypothesis is
    firmly rejected in the data (Fama & Bliss, 1987; Campbell & Shiller, 1991;
    Cochrane & Piazzesi, 2005), a zero term premium is a *stronger*
    assumption than a published estimate, not a weaker one.

``"spot"``
    :math:`r_f(H) = z(H)`, the horizon-matched zero-coupon rate.  This is the
    genuinely riskless payoff for an investor with a fixed horizon *H*
    (Campbell & Viceira, 2002, ch. 3): a zero-coupon bond maturing at *H* has
    no reinvestment risk.  Under this convention duration exposure carries no
    premium at the matched maturity, and the whole term premium is folded into
    the risk-free rate rather than into the bond premia.

Both conventions coincide when the term premium is zero.  ``rolled_cash`` is
the default because it makes the reported premium table interpretable as
*compensation for risk taken relative to cash*, which is the usual reading.

References
----------
Adrian, T., Crump, R. & Moench, E. (2013). Pricing the term structure with
linear regressions. *Journal of Financial Economics* 110(1), 110-138.

Campbell, J. & Shiller, R. (1991). Yield spreads and interest rate movements:
a bird's eye view. *Review of Economic Studies* 58(3), 495-514.

Campbell, J. & Viceira, L. (2002). *Strategic Asset Allocation.* OUP.

Cochrane, J. & Piazzesi, M. (2005). Bond risk premia. *American Economic
Review* 95(1), 138-160.

Fama, E. & Bliss, R. (1987). The information in long-maturity forward rates.
*American Economic Review* 77(4), 680-692.

Kim, D. & Wright, J. (2005). An arbitrage-free three-factor term structure
model and the recent behavior of long-term yields. FEDS 2005-33.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .blocks import DERIVED, MARKET, RISK_FREE, BuildingBlock
from .curves import TermStructure, ZeroCurve

__all__ = ["RiskFreeModel", "ROLLED_CASH", "SPOT"]

ROLLED_CASH = "rolled_cash"
SPOT = "spot"


@dataclass(frozen=True)
class RiskFreeModel:
    """Horizon-dependent risk-free rate derived from one nominal curve.

    Parameters
    ----------
    curve:
        Nominal zero curve of the currency in question.
    term_premium:
        Yield term-premium term structure.  Defaults to identically zero,
        in which case both conventions collapse to the spot rate.
    convention:
        ``"rolled_cash"`` or ``"spot"``; see the module docstring.

    Examples
    --------
    >>> from market_implied.curves import ZeroCurve, TermStructure
    >>> curve = ZeroCurve([1, 5, 15], [0.02, 0.025, 0.030])
    >>> tp = TermStructure([1, 5, 15], [0.000, 0.004, 0.012])
    >>> rf = RiskFreeModel(curve, tp)
    >>> round(rf.rate(5), 4)
    0.021
    """

    curve: ZeroCurve
    term_premium: Optional[TermStructure] = None
    convention: str = ROLLED_CASH

    def __post_init__(self) -> None:
        if self.convention not in (ROLLED_CASH, SPOT):
            raise ValueError(
                f"convention must be {ROLLED_CASH!r} or {SPOT!r}, got {self.convention!r}"
            )

    # ------------------------------------------------------------------
    def spot(self, horizon: float) -> float:
        """The horizon-matched zero rate :math:`z(H)`."""
        return float(self.curve.zero(horizon))

    def term_premium_at(self, maturity: float) -> float:
        """Term premium at *maturity*; zero when no estimate is configured."""
        if self.term_premium is None:
            return 0.0
        return float(self.term_premium(maturity))

    def rate(self, horizon: float) -> float:
        """Return :math:`r_f(H)` under the configured convention."""
        z = self.spot(horizon)
        if self.convention == SPOT:
            return z
        return z - self.term_premium_at(horizon)

    def block(self, horizon: float) -> BuildingBlock:
        """Return :math:`r_f(H)` packaged as a :class:`BuildingBlock`."""
        value = self.rate(horizon)
        if self.convention == SPOT:
            note = (
                f"z({horizon:g}y) van {self.curve.name}: horizon-matched "
                "zerocoupon rente (Campbell & Viceira, 2002)."
            )
            source = MARKET
        else:
            note = (
                f"z({horizon:g}y) - TP({horizon:g}y) van {self.curve.name}: "
                "verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013)."
            )
            source = DERIVED
        return BuildingBlock(
            name="risk_free",
            value=value,
            kind=RISK_FREE,
            source=source,
            label="Risicovrije rente",
            note=note,
        )

    def duration_carry(self, horizon: float, duration: float) -> float:
        """Expected annualised excess return of *duration* exposure over cash.

        Under the affine decomposition, holding a bond of maturity ``D`` and
        rolling it earns the expected short rate plus the term premium at
        ``D``, so the excess over rolling cash is simply :math:`TP(D)`.

        This is deliberately **independent of** :attr:`convention`.  Every
        premium block in this package is defined as an excess over *local
        rolled cash*; the reporting convention only changes how that same
        total is split between the risk-free block and a single explicit
        reconciliation block (see
        :meth:`~market_implied.models.base.ModelContext.finish`).  Keeping the
        economics and the presentation separate is what makes the two
        conventions produce identical expected returns.
        """
        del horizon  # the excess over cash does not depend on the horizon
        return self.term_premium_at(duration)

    def duration_block(self, horizon: float, duration: float) -> BuildingBlock:
        """Package :meth:`duration_carry` as a premium block."""
        return BuildingBlock(
            name="term_premium",
            value=self.duration_carry(horizon, duration),
            source=MARKET,
            label="Termijnpremie (duration)",
            note=(
                f"Termijnpremie bij duration {duration:g}j op {self.curve.name}; "
                "verwacht meerrendement van duratierisico boven doorgerold kasgeld "
                "(Adrian, Crump & Moench, 2013)."
            ),
        )
