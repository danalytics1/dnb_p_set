"""
Container and loader for the market snapshot.

A :class:`MarketSnapshot` holds **only observables**: prices, yields, spreads,
dividend yields, futures-curve slopes and published term-premium / risk-premium
decompositions.  Structural assumptions taken from the academic literature
(default rates, loss given default, real growth, illiquidity premia) live in
the *universe* configuration instead, so that a reader can always tell which
part of a number is the market talking and which part is the modeller talking.

The snapshot is stored as JSON so that it can be refreshed from a data vendor
without touching any code.  See ``market_implied/data/market_snapshot_example.json``
for the schema and ``market_implied/docs/methodology.md`` for the sourcing of
each field.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .curves import TermStructure, ZeroCurve

__all__ = ["MarketSnapshot", "load_market_snapshot"]


@dataclass
class MarketSnapshot:
    """Observable market data as of a single date.

    Parameters
    ----------
    as_of:
        Observation date (ISO string).  Purely informational, but it is
        propagated into every report because a market-implied number without
        a date is meaningless.
    base_currency:
        Reporting currency.  Foreign-currency asset classes are assumed to be
        currency hedged; see :meth:`risk_free_currency`.
    curves:
        Zero curves keyed by name, e.g. ``"EUR_nominal"``, ``"EUR_real"``.
    term_premia:
        Yield term-premium term structures keyed by curve name.  These are
        model estimates published by central banks (ACM, Kim-Wright) rather
        than raw prices, but they are estimated *from* the cross-section of
        bond prices and are therefore treated as market data here.
    inflation_risk_premia:
        Inflation risk-premium term structures keyed by currency.
    instruments:
        Free-form nested mapping with per-asset observables (OAS, dividend
        yield, roll yield, …).  Models look these up by dotted path.
    metadata:
        Anything else worth carrying into the report (vendor, index tickers).
    """

    as_of: str
    base_currency: str
    curves: Dict[str, ZeroCurve] = field(default_factory=dict)
    term_premia: Dict[str, TermStructure] = field(default_factory=dict)
    inflation_risk_premia: Dict[str, TermStructure] = field(default_factory=dict)
    instruments: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    def curve(self, name: str) -> ZeroCurve:
        """Return the zero curve called *name*."""
        try:
            return self.curves[name]
        except KeyError as exc:
            raise KeyError(
                f"curve {name!r} not in snapshot; available: {sorted(self.curves)}"
            ) from exc

    def nominal_curve(self, currency: str) -> ZeroCurve:
        """Return the nominal curve for *currency* (``<CCY>_nominal``)."""
        return self.curve(f"{currency}_nominal")

    def real_curve(self, currency: str) -> ZeroCurve:
        """Return the real (inflation-linked) curve for *currency*."""
        return self.curve(f"{currency}_real")

    def term_premium(self, curve_name: str) -> TermStructure:
        """Return the term-premium structure for *curve_name*.

        Falls back to an identically zero term structure, which reduces the
        risk-free block to the pure expectations hypothesis.
        """
        return self.term_premia.get(curve_name, TermStructure.zero(curve_name))

    def inflation_risk_premium(self, currency: str) -> TermStructure:
        """Return the inflation risk premium term structure for *currency*."""
        return self.inflation_risk_premia.get(currency, TermStructure.zero(currency))

    def breakeven_inflation(self, currency: str, maturity: float) -> float:
        """Return market breakeven inflation for *currency* at *maturity*."""
        nom = self.nominal_curve(currency)
        real = self.real_curve(currency)
        return float(nom.breakeven_inflation(real, maturity))

    def expected_inflation(self, currency: str, maturity: float) -> float:
        """Return breakeven inflation net of the inflation risk premium.

        Breakevens are a biased estimate of expected inflation: they embed an
        inflation risk premium and an inflation-linked bond liquidity premium
        (Grishchenko & Huang, 2013; D'Amico, Kim & Wei, 2018).  Subtracting a
        published IRP estimate turns the breakeven into an expectation.
        """
        be = self.breakeven_inflation(currency, maturity)
        irp = float(self.inflation_risk_premium(currency)(maturity))
        return be - irp

    def instrument(self, path: str) -> Mapping[str, Any]:
        """Look up a nested instrument block by dotted *path*.

        ``snapshot.instrument("credit.eur_ig")`` returns
        ``snapshot.instruments["credit"]["eur_ig"]``.
        """
        node: Any = self.instruments
        for part in path.split("."):
            if not isinstance(node, Mapping) or part not in node:
                raise KeyError(f"instrument path {path!r} not found in snapshot")
            node = node[part]
        if not isinstance(node, Mapping):
            raise TypeError(f"instrument path {path!r} does not point to a mapping")
        return node

    def observable(self, path: str, key: str, default: Optional[float] = None) -> float:
        """Return one numeric observable, raising a helpful error when absent."""
        node = self.instrument(path)
        if key in node:
            return float(node[key])
        if default is not None:
            return float(default)
        raise KeyError(
            f"observable {key!r} missing from instrument {path!r}; "
            f"available: {sorted(node)}"
        )


def _load_curves(payload: Mapping[str, Any]) -> Dict[str, ZeroCurve]:
    return {
        name: ZeroCurve.from_mapping(spec, name=name)
        for name, spec in payload.items()
        if not name.startswith("_")
    }


def _load_term_structures(payload: Mapping[str, Any]) -> Dict[str, TermStructure]:
    return {
        name: TermStructure(spec["tenors"], spec["values"], name=name)
        for name, spec in payload.items()
        if not name.startswith("_")
    }


def load_market_snapshot(path: "str | Path") -> MarketSnapshot:
    """Load a :class:`MarketSnapshot` from a JSON file.

    Keys starting with an underscore are treated as comments and ignored,
    which lets the JSON file carry its own documentation.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    missing = {"as_of", "base_currency", "curves"} - set(payload)
    if missing:
        raise KeyError(f"market snapshot {path} is missing keys: {sorted(missing)}")

    return MarketSnapshot(
        as_of=payload["as_of"],
        base_currency=payload["base_currency"],
        curves=_load_curves(payload["curves"]),
        term_premia=_load_term_structures(payload.get("term_premia", {})),
        inflation_risk_premia=_load_term_structures(
            payload.get("inflation_risk_premia", {})
        ),
        instruments=payload.get("instruments", {}),
        metadata={
            k: v
            for k, v in payload.items()
            if k
            not in {
                "as_of",
                "base_currency",
                "curves",
                "term_premia",
                "inflation_risk_premia",
                "instruments",
            }
        },
    )
