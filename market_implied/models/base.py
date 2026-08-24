"""
Shared plumbing for asset-class models.

An *asset-class model* is a function

.. code-block:: python

    def build(spec: AssetSpec, ctx: ModelContext) -> ReturnBuildUp

registered under a name that the universe configuration refers to.  Adding a
new asset class is therefore either a new entry in ``universe.json`` (when an
existing model fits) or one new function plus a ``@register`` decorator.

Currency
--------
All non-base-currency asset classes are assumed to be **currency hedged**,
which is standard for a Dutch pension investor.  Under covered interest parity
the hedged expected return of a foreign asset is

.. math::  E[R^{hedged}_{base}] = E[R_{local}] - r_f^{local} + r_f^{base}

so the *risk premium* is currency invariant and the risk-free block is always
the base-currency one.  That is exactly the structure this package reports, and
it is why every premium block is defined as an excess over **local rolled
cash**: the hedge then contributes exactly zero to the premium and the
base-currency risk-free block can simply be bolted on.  Leaving a position
unhedged does not change the market-implied answer: the FX forward prices in
precisely the rate differential, so the expected currency return under the
forward measure is :math:`r_f^{base} - r_f^{local}` (see the methodology note
on FX).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional

from ..blocks import DERIVED, PREMIUM, BuildingBlock, ReturnBuildUp
from ..marketdata import MarketSnapshot
from ..riskfree import ROLLED_CASH, RiskFreeModel

__all__ = [
    "AssetSpec",
    "ModelContext",
    "ModelError",
    "register",
    "get_model",
    "available_models",
    "reversion_fraction",
    "annualise_price_effect",
]


class ModelError(RuntimeError):
    """Raised when an asset-class model cannot be evaluated."""


@dataclass(frozen=True)
class AssetSpec:
    """Static description of one asset class.

    Parameters
    ----------
    key:
        Stable identifier used in output tables and cross-references.
    name:
        Display name (Dutch).
    model:
        Name of the registered model function.
    currency:
        Currency of the underlying market. Returns are reported in the
        snapshot's base currency, hedged.
    category:
        Grouping used for report ordering, e.g. ``"Vastrentend"``.
    volatility:
        Annualised volatility, used only for the arithmetic conversion.
    params:
        Model-specific parameters.
    depends_on:
        Keys of other asset classes whose build-up this model needs.  The
        engine resolves these before evaluating this asset class.
    """

    key: str
    name: str
    model: str
    currency: str = "EUR"
    category: str = ""
    volatility: Optional[float] = None
    params: Mapping[str, Any] = field(default_factory=dict)
    depends_on: tuple = ()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "AssetSpec":
        return cls(
            key=payload["key"],
            name=payload.get("name", payload["key"]),
            model=payload["model"],
            currency=payload.get("currency", "EUR"),
            category=payload.get("category", ""),
            volatility=payload.get("volatility"),
            params=payload.get("params", {}),
            depends_on=tuple(payload.get("depends_on", ())),
        )

    # Convenience accessors -------------------------------------------------
    def param(self, name: str) -> Any:
        """Required parameter lookup; raises a pointed error when missing."""
        if name not in self.params:
            raise ModelError(
                f"asset class {self.key!r} (model {self.model!r}) needs parameter {name!r}"
            )
        return self.params[name]

    def opt(self, name: str, default: Any = None) -> Any:
        """Optional parameter lookup.

        An explicit ``null`` in the configuration is treated as absent and
        yields *default*.  Where ``null`` has to mean "switch this block off"
        — as it does for the mean-reversion half-lives — models read
        :attr:`params` directly instead.
        """
        value = self.params.get(name, default)
        return default if value is None else value


@dataclass
class ModelContext:
    """Everything a model needs besides its own :class:`AssetSpec`.

    Parameters
    ----------
    snapshot:
        The market snapshot.
    horizon:
        Horizon in years.
    rf_convention:
        Risk-free convention, see :mod:`market_implied.riskfree`.
    apply_valuation:
        When ``False`` all mean-reversion / valuation-normalisation blocks are
        switched off, leaving a strictly market-implied ("carry only") view.
        Useful as a sensitivity and as an honesty check.
    peers:
        Already-evaluated build-ups, keyed by asset-class key.  Populated by
        the engine for models that reference another asset class.
    """

    snapshot: MarketSnapshot
    horizon: float
    rf_convention: str = ROLLED_CASH
    apply_valuation: bool = True
    peers: Dict[str, ReturnBuildUp] = field(default_factory=dict)
    _rf_cache: Dict[str, RiskFreeModel] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    @property
    def base_currency(self) -> str:
        return self.snapshot.base_currency

    def risk_free_model(self, currency: Optional[str] = None) -> RiskFreeModel:
        """Return the :class:`RiskFreeModel` for *currency* (cached)."""
        ccy = currency or self.base_currency
        if ccy not in self._rf_cache:
            curve_name = f"{ccy}_nominal"
            self._rf_cache[ccy] = RiskFreeModel(
                curve=self.snapshot.curve(curve_name),
                term_premium=self.snapshot.term_premium(curve_name),
                convention=self.rf_convention,
            )
        return self._rf_cache[ccy]

    def risk_free(self, currency: Optional[str] = None) -> float:
        """Return :math:`r_f(H)` for *currency*."""
        return self.risk_free_model(currency).rate(self.horizon)

    def base_risk_free_block(self) -> BuildingBlock:
        """The single risk-free block, always in the base currency."""
        return self.risk_free_model(self.base_currency).block(self.horizon)

    def rolled_cash_rate(self, currency: Optional[str] = None) -> float:
        """Expected average short rate over the horizon, ``z(H) - TP(H)``.

        This is the economic cash rate, computed with the ``rolled_cash``
        convention regardless of what :attr:`rf_convention` is set to.  Every
        premium block in this package is an excess over *this* number, which
        is what makes the reported expected returns independent of the
        reporting convention.
        """
        ccy = currency or self.base_currency
        model = self.risk_free_model(ccy)
        return model.spot(self.horizon) - model.term_premium_at(self.horizon)

    def local_rf_offset(self, currency: str) -> BuildingBlock:
        """Block that subtracts the **local rolled-cash** rate.

        Used by models that naturally produce a total expected return (equity,
        real estate): subtracting local cash turns that total into an excess
        return.  Hedging the currency then swaps local cash for base-currency
        cash, which is exactly what :meth:`base_risk_free_block` adds back —
        the covered-interest-parity identity

        .. math::

            E[R^{hedged}_{base}] = E[R_{local}] - r^{cash}_{local} + r^{cash}_{base}
        """
        rf_local = self.rolled_cash_rate(currency)
        same = currency == self.base_currency
        return BuildingBlock(
            name="minus_local_cash",
            value=-rf_local,
            kind=PREMIUM,
            source=DERIVED,
            label="Af: risicovrije rente (lokaal)",
            note=(
                f"-{rf_local:.2%}: verwachte gemiddelde korte rente in {currency} over "
                f"{self.horizon:g} jaar. Het model levert een totaalrendement; door de "
                "lokale kasrente af te trekken blijft de risicopremie over."
                + (
                    ""
                    if same
                    else " Valuta-afdekking ruilt vervolgens de lokale kasrente om voor "
                    "die van de basisvaluta (gedekte rentepariteit)."
                )
            ),
        )

    def convention_adjustment(self) -> Optional[BuildingBlock]:
        """Reconcile the economic cash rate with the reported risk-free block.

        Premium blocks are excesses over rolled cash.  When the risk-free
        block is reported on the ``spot`` convention it already contains the
        horizon term premium, so that term premium has to be taken out of the
        premium again.  Returns ``None`` under the ``rolled_cash`` convention,
        where the adjustment is identically zero.
        """
        value = self.rolled_cash_rate(self.base_currency) - self.risk_free(
            self.base_currency
        )
        if abs(value) < 1e-15:
            return None
        return BuildingBlock(
            name="risk_free_convention_adjustment",
            value=value,
            kind=PREMIUM,
            source=DERIVED,
            label="Correctie risicovrije conventie",
            note=(
                "De risicovrije rente wordt gerapporteerd als horizon-matched zero "
                "rate, die de termijnpremie op de horizon al bevat. Die premie wordt "
                "hier uit de risicopremie gehaald zodat het verwachte rendement niet "
                "van de rapportageconventie afhangt."
            ),
        )

    def expected_inflation(self, currency: str, maturity: Optional[float] = None) -> float:
        """Market breakeven inflation net of the inflation risk premium."""
        return self.snapshot.expected_inflation(currency, maturity or self.horizon)

    def finish(
        self,
        spec: AssetSpec,
        premium_blocks: List[BuildingBlock],
        diagnostics: Optional[dict] = None,
    ) -> ReturnBuildUp:
        """Assemble a validated :class:`ReturnBuildUp`."""
        blocks = [self.base_risk_free_block()] + list(premium_blocks)
        adjustment = self.convention_adjustment()
        if adjustment is not None:
            blocks.append(adjustment)
        build_up = ReturnBuildUp(
            asset_class=spec.key,
            name=spec.name,
            horizon=self.horizon,
            base_currency=self.base_currency,
            blocks=blocks,
            volatility=spec.volatility,
            model=spec.model,
            diagnostics=diagnostics or {},
        )
        build_up.check(tolerance=1e-10)
        return build_up


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------
ModelFn = Callable[[AssetSpec, ModelContext], ReturnBuildUp]
_REGISTRY: Dict[str, ModelFn] = {}


def register(name: str) -> Callable[[ModelFn], ModelFn]:
    """Decorator registering a model function under *name*."""

    def _decorator(fn: ModelFn) -> ModelFn:
        if name in _REGISTRY:
            raise ValueError(f"model {name!r} is already registered")
        _REGISTRY[name] = fn
        return fn

    return _decorator


def get_model(name: str) -> ModelFn:
    """Return the model function registered under *name*."""
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise ModelError(
            f"unknown model {name!r}; available: {sorted(_REGISTRY)}"
        ) from exc


def available_models() -> List[str]:
    """Sorted list of registered model names."""
    return sorted(_REGISTRY)


# ----------------------------------------------------------------------
# Shared maths
# ----------------------------------------------------------------------
def reversion_fraction(horizon: float, half_life: Optional[float]) -> float:
    """Fraction of a valuation gap that closes over *horizon*.

    Assumes exponential decay with the given half-life:

    .. math::  \\theta(H) = 1 - 2^{-H / h_{1/2}}

    ``half_life is None`` disables mean reversion (``theta = 0``); a half-life
    of zero means instantaneous reversion (``theta = 1``).

    Empirically, valuation ratios and credit spreads are strongly but slowly
    mean reverting: CAPE half-lives of roughly a decade (Campbell & Shiller,
    1998; Asness, 2012) and credit-spread half-lives of a few years (Duffee,
    1998; Collin-Dufresne, Goldstein & Martin, 2001).
    """
    if half_life is None:
        return 0.0
    if half_life < 0:
        raise ValueError("half_life must be non-negative or None")
    if half_life == 0:
        return 1.0
    return 1.0 - 2.0 ** (-float(horizon) / float(half_life))


def annualise_price_effect(total_price_change: float, horizon: float) -> float:
    """Turn a cumulative price change into an annualised contribution.

    ``total_price_change`` is the fractional change in price over the whole
    horizon (``-0.05`` for a 5% repricing loss).
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if total_price_change <= -1.0:
        raise ModelError("implied price change wipes out the position (<= -100%)")
    return (1.0 + total_price_change) ** (1.0 / horizon) - 1.0
