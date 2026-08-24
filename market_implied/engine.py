"""
The engine: turn a market snapshot plus a universe into the premium table.

Public entry point is :func:`build_expectations`, which returns a
:class:`ExpectationsResult` holding both the wide summary table (the deliverable:
one risk premium per asset class per horizon) and the long block table (the
audit trail behind every number).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import pandas as pd

from .blocks import ReturnBuildUp
from .marketdata import MarketSnapshot
from .models.base import ModelContext, get_model
from .universe import Universe

__all__ = ["ExpectationsResult", "build_expectations"]


@dataclass
class ExpectationsResult:
    """Everything a run produces.

    Parameters
    ----------
    build_ups:
        All :class:`~market_implied.blocks.ReturnBuildUp` objects, keyed by
        ``(asset_class, horizon)``.
    snapshot:
        The snapshot used, so the ``as_of`` date travels with the numbers.
    universe:
        The universe used.
    """

    build_ups: Dict[tuple, ReturnBuildUp]
    snapshot: MarketSnapshot
    universe: Universe
    order: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    def summary_table(self) -> pd.DataFrame:
        """One row per asset class per horizon: the requested deliverable."""
        rows = []
        for key in self.order:
            for horizon in self.universe.horizons:
                bu = self.build_ups[(key, horizon)]
                spec = self.universe.get(key)
                rows.append(
                    {
                        "asset_class": key,
                        "name": bu.name,
                        "category": spec.category,
                        "currency": bu.base_currency,
                        "horizon": horizon,
                        "risk_free": bu.risk_free,
                        "risk_premium": bu.risk_premium,
                        "expected_return": bu.expected_return,
                        "expected_return_arithmetic": bu.expected_return_arithmetic,
                        "volatility": bu.volatility,
                        "model": bu.model,
                        "assumption_share": bu.assumption_share(),
                    }
                )
        return pd.DataFrame(rows)

    def premium_matrix(self) -> pd.DataFrame:
        """Risk premia with asset classes as rows and horizons as columns."""
        summary = self.summary_table()
        wide = summary.pivot(index="name", columns="horizon", values="risk_premium")
        wide.columns = [f"risk_premium_{int(h)}y" for h in wide.columns]
        order = [self.build_ups[(k, self.universe.horizons[0])].name for k in self.order]
        return wide.reindex(order)

    def blocks_table(self) -> pd.DataFrame:
        """Long-format table with every building block of every build-up."""
        records: List[dict] = []
        for key in self.order:
            for horizon in self.universe.horizons:
                records.extend(self.build_ups[(key, horizon)].to_records())
        return pd.DataFrame(records)

    def blocks_matrix(self, horizon: Optional[float] = None) -> pd.DataFrame:
        """Blocks as a wide table (asset classes x block names) for one horizon."""
        h = horizon if horizon is not None else self.universe.horizons[0]
        long = self.blocks_table()
        long = long[long["horizon"] == h]
        wide = long.pivot_table(
            index="name", columns="block", values="value", aggfunc="sum"
        )
        order = [self.build_ups[(k, h)].name for k in self.order]
        return wide.reindex(order)

    def diagnostics_table(self) -> pd.DataFrame:
        """Model diagnostics (current yields, implied cost of equity, ...)."""
        rows = []
        for key in self.order:
            for horizon in self.universe.horizons:
                bu = self.build_ups[(key, horizon)]
                rows.append(
                    {"asset_class": key, "name": bu.name, "horizon": horizon, **bu.diagnostics}
                )
        return pd.DataFrame(rows)

    def build_up(self, asset_class: str, horizon: float) -> ReturnBuildUp:
        """Return one build-up."""
        return self.build_ups[(asset_class, horizon)]


def build_expectations(
    snapshot: MarketSnapshot,
    universe: Universe,
    horizons: Optional[Sequence[float]] = None,
) -> ExpectationsResult:
    """Evaluate every asset class at every horizon.

    Parameters
    ----------
    snapshot:
        Market observables.
    universe:
        Asset classes and their models.
    horizons:
        Override the universe horizons.

    Returns
    -------
    ExpectationsResult
    """
    if horizons is not None:
        universe = Universe(
            asset_classes=universe.asset_classes,
            horizons=tuple(horizons),
            risk_free_convention=universe.risk_free_convention,
            apply_valuation=universe.apply_valuation,
            name=universe.name,
            description=universe.description,
            metadata=universe.metadata,
        )

    order = universe.evaluation_order()
    build_ups: Dict[tuple, ReturnBuildUp] = {}

    for horizon in universe.horizons:
        ctx = ModelContext(
            snapshot=snapshot,
            horizon=float(horizon),
            rf_convention=universe.risk_free_convention,
            apply_valuation=universe.apply_valuation,
        )
        for spec in order:
            model = get_model(spec.model)
            build_up = model(spec, ctx)
            ctx.peers[spec.key] = build_up
            build_ups[(spec.key, horizon)] = build_up

    return ExpectationsResult(
        build_ups=build_ups,
        snapshot=snapshot,
        universe=universe,
        order=[spec.key for spec in universe.asset_classes],
    )
