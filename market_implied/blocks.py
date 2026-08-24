"""
Building blocks: the atoms of a market-implied return expectation.

Every expected return in this package is written as

.. math::

    E[R] = r_f(H) \;+\; \\underbrace{\\sum_{i} b_i}_{\\text{risk premium}}

where :math:`r_f(H)` is the horizon-*H* risk-free building block (identical
across all asset classes by construction, see :mod:`market_implied.riskfree`)
and the :math:`b_i` are asset-class specific premium blocks.

Blocks are added **arithmetically** to an annualised compound (geometric)
return.  That is the standard convention in building-block capital market
assumptions and is exact in continuous compounding; the cross-product terms it
ignores are second order (Grinold & Kroner, 2002).  The helper
:func:`compound` is provided where an exact multiplicative combination is
wanted instead.

References
----------
Grinold, R. & Kroner, K. (2002). *The Equity Risk Premium.* Investment
Insights 5(3), Barclays Global Investors.

Ilmanen, A. (2011). *Expected Returns: An Investor's Guide to Harvesting
Market Rewards.* Wiley. Chapter 2 on the arithmetic/geometric wedge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

__all__ = [
    "RISK_FREE",
    "PREMIUM",
    "MARKET",
    "ASSUMPTION",
    "DERIVED",
    "BuildingBlock",
    "ReturnBuildUp",
    "compound",
]

#: Block kinds.
RISK_FREE = "risk_free"
PREMIUM = "premium"

#: Provenance tags.  ``MARKET`` blocks are observable in today's prices,
#: ``ASSUMPTION`` blocks come from the literature and are *not* market implied,
#: ``DERIVED`` blocks are a deterministic function of the other two.
MARKET = "market"
ASSUMPTION = "assumption"
DERIVED = "derived"


def compound(components: Iterable[float]) -> float:
    """Combine return components multiplicatively.

    ``compound([0.02, 0.01]) == 1.02 * 1.01 - 1``.
    """
    total = 1.0
    for c in components:
        total *= 1.0 + c
    return total - 1.0


@dataclass(frozen=True)
class BuildingBlock:
    """One additive component of an expected return.

    Parameters
    ----------
    name:
        Machine-friendly identifier, e.g. ``"credit_spread"``.
    value:
        Annualised contribution in decimal terms.
    kind:
        Either :data:`RISK_FREE` or :data:`PREMIUM`.  Exactly one risk-free
        block is allowed per build-up.
    source:
        Provenance: :data:`MARKET`, :data:`ASSUMPTION` or :data:`DERIVED`.
    label:
        Human-readable (Dutch) label used in reporting.
    note:
        Short explanation of the formula and/or the reference behind it.
    """

    name: str
    value: float
    kind: str = PREMIUM
    source: str = MARKET
    label: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if self.kind not in (RISK_FREE, PREMIUM):
            raise ValueError(f"unknown block kind {self.kind!r}")
        if self.source not in (MARKET, ASSUMPTION, DERIVED):
            raise ValueError(f"unknown block source {self.source!r}")

    @property
    def display_label(self) -> str:
        return self.label or self.name.replace("_", " ")


@dataclass
class ReturnBuildUp:
    """The full decomposition of one asset class at one horizon.

    Parameters
    ----------
    asset_class:
        Key of the asset class.
    name:
        Display name of the asset class.
    horizon:
        Horizon in years (5 or 15 in the default configuration).
    base_currency:
        Currency the expected return is expressed in.
    blocks:
        Ordered building blocks.  Exactly one must have kind
        :data:`RISK_FREE`.
    volatility:
        Annualised return volatility, used only for the geometric/arithmetic
        conversion.  ``None`` suppresses the arithmetic column.
    model:
        Name of the model that produced the build-up.
    diagnostics:
        Free-form model diagnostics (current yield, implied cost of equity,
        …) that are reported next to the build-up but are not blocks.
    """

    asset_class: str
    name: str
    horizon: float
    base_currency: str
    blocks: List[BuildingBlock] = field(default_factory=list)
    volatility: Optional[float] = None
    model: str = ""
    diagnostics: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        n_rf = sum(1 for b in self.blocks if b.kind == RISK_FREE)
        if n_rf != 1:
            raise ValueError(
                f"{self.asset_class!r}: expected exactly one risk-free block, got {n_rf}"
            )

    # ------------------------------------------------------------------
    @property
    def risk_free(self) -> float:
        """The horizon-*H* expected risk-free rate."""
        return next(b.value for b in self.blocks if b.kind == RISK_FREE)

    @property
    def premium_blocks(self) -> List[BuildingBlock]:
        return [b for b in self.blocks if b.kind == PREMIUM]

    @property
    def risk_premium(self) -> float:
        """Sum of all premium blocks: the deliverable of this package."""
        return sum(b.value for b in self.premium_blocks)

    @property
    def expected_return(self) -> float:
        """Annualised **geometric** expected return, ``risk_free + risk_premium``."""
        return self.risk_free + self.risk_premium

    @property
    def expected_return_arithmetic(self) -> Optional[float]:
        """Annualised arithmetic expected return.

        Uses the standard lognormal wedge :math:`\\mu \\approx g + \\sigma^2/2`
        (Ilmanen, 2011, ch. 2).  Returns ``None`` when no volatility is
        configured.
        """
        if self.volatility is None:
            return None
        return self.expected_return + 0.5 * self.volatility**2

    def block(self, name: str) -> Optional[BuildingBlock]:
        """Return the block called *name*, or ``None``."""
        for b in self.blocks:
            if b.name == name:
                return b
        return None

    def value_of(self, name: str, default: float = 0.0) -> float:
        """Return the value of block *name*, or *default* when absent."""
        b = self.block(name)
        return default if b is None else b.value

    def assumption_share(self) -> float:
        """Absolute size of assumption-driven blocks over all premium blocks.

        A crude but useful honesty metric: how much of the risk premium is
        *not* read off market prices.  Ranges from 0 (fully market implied)
        to 1 (fully judgemental).
        """
        prem = self.premium_blocks
        total = sum(abs(b.value) for b in prem)
        if total == 0.0:
            return 0.0
        assumed = sum(abs(b.value) for b in prem if b.source == ASSUMPTION)
        return assumed / total

    def to_records(self) -> List[dict]:
        """Return one record per block, for a long-format DataFrame."""
        return [
            {
                "asset_class": self.asset_class,
                "name": self.name,
                "horizon": self.horizon,
                "model": self.model,
                "block": b.name,
                "label": b.display_label,
                "kind": b.kind,
                "source": b.source,
                "value": b.value,
                "note": b.note,
            }
            for b in self.blocks
        ]

    def check(self, tolerance: float = 1e-12) -> None:
        """Assert internal consistency of the decomposition."""
        total = sum(b.value for b in self.blocks)
        if abs(total - self.expected_return) > tolerance:
            raise AssertionError(
                f"{self.asset_class}: blocks sum to {total:.10f} but expected "
                f"return is {self.expected_return:.10f}"
            )
