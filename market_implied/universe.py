"""
Loader for the asset-class universe configuration.

The universe file says *which* asset classes exist, which model prices each of
them and with which structural parameters.  Together with a market snapshot it
fully determines the output table, so a reproduction of any published number
needs exactly these two JSON files plus a git hash.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from .models.base import AssetSpec
from .riskfree import ROLLED_CASH, SPOT

__all__ = ["Universe", "load_universe"]


@dataclass
class Universe:
    """A set of asset classes plus the global run settings.

    Parameters
    ----------
    asset_classes:
        Ordered specifications.
    horizons:
        Horizons in years to evaluate, e.g. ``[5, 15]``.
    risk_free_convention:
        ``"rolled_cash"`` or ``"spot"``.
    apply_valuation:
        Whether mean-reversion blocks are active.
    name, description:
        Documentation carried into reports.
    """

    asset_classes: List[AssetSpec]
    horizons: Sequence[float] = (5, 15)
    risk_free_convention: str = ROLLED_CASH
    apply_valuation: bool = True
    name: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        keys = [a.key for a in self.asset_classes]
        duplicates = {k for k in keys if keys.count(k) > 1}
        if duplicates:
            raise ValueError(f"duplicate asset class keys: {sorted(duplicates)}")
        if self.risk_free_convention not in (ROLLED_CASH, SPOT):
            raise ValueError(
                f"unknown risk_free_convention {self.risk_free_convention!r}"
            )
        known = set(keys)
        for spec in self.asset_classes:
            unknown = set(spec.depends_on) - known
            if unknown:
                raise ValueError(
                    f"{spec.key!r} depends on unknown asset classes: {sorted(unknown)}"
                )

    def __iter__(self):
        return iter(self.asset_classes)

    def __len__(self) -> int:
        return len(self.asset_classes)

    def get(self, key: str) -> AssetSpec:
        for spec in self.asset_classes:
            if spec.key == key:
                return spec
        raise KeyError(f"asset class {key!r} not in universe")

    def evaluation_order(self) -> List[AssetSpec]:
        """Topologically sort the asset classes on their dependencies.

        Raises
        ------
        ValueError
            When the dependency graph contains a cycle.
        """
        remaining = list(self.asset_classes)
        done: List[AssetSpec] = []
        resolved: set = set()
        while remaining:
            ready = [s for s in remaining if set(s.depends_on) <= resolved]
            if not ready:
                stuck = sorted(s.key for s in remaining)
                raise ValueError(f"cyclic dependency between asset classes: {stuck}")
            for spec in ready:
                done.append(spec)
                resolved.add(spec.key)
                remaining.remove(spec)
        return done


def load_universe(path: "str | Path", **overrides: Any) -> Universe:
    """Load a :class:`Universe` from a JSON file.

    Any keyword override replaces the corresponding file setting, which is how
    the CLI implements ``--horizons``, ``--rf-convention`` and
    ``--no-valuation``.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        payload: Mapping[str, Any] = json.load(fh)

    if "asset_classes" not in payload:
        raise KeyError(f"universe file {path} has no 'asset_classes'")

    specs = [
        AssetSpec.from_mapping(item)
        for item in payload["asset_classes"]
        if not item.get("_disabled", False)
    ]
    settings: Dict[str, Any] = {
        "horizons": tuple(payload.get("horizons", (5, 15))),
        "risk_free_convention": payload.get("risk_free_convention", ROLLED_CASH),
        "apply_valuation": payload.get("apply_valuation", True),
        "name": payload.get("name", path.stem),
        "description": payload.get("description", ""),
        "metadata": {
            k: v
            for k, v in payload.items()
            if k.startswith("_") or k in {"sources", "version"}
        },
    }
    settings.update({k: v for k, v in overrides.items() if v is not None})
    return Universe(asset_classes=specs, **settings)
