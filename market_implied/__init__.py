"""
market_implied
==============

Market-implied rendementsverwachtingen per beleggingscategorie.

Deze package leidt verwachte rendementen af uit **huidige marktprijzen**, per
beleggingscategorie opgebouwd uit bouwstenen:

.. code-block:: text

    Verwacht rendement = risicovrije rente + risicopremie

waarbij de risicovrije rente voor alle categorieen identiek wordt bepaald
(zie :mod:`market_implied.riskfree`) en de risicopremie per categorie uit
categoriespecifieke bouwstenen wordt opgebouwd, bijvoorbeeld

.. code-block:: text

    High yield = termijnpremie + spread - verwacht kredietverlies - afwaarderingen
    Aandelen   = dividendrendement + inkoop eigen aandelen + inflatie
                 + reele winstgroei + waarderingsverandering - risicovrije rente

De package staat volledig los van :mod:`dnb_p_set`: er is geen import in
beide richtingen en er wordt geen DNB-scenariodata gebruikt.

Quick start
-----------
.. code-block:: python

    from market_implied import build_expectations, load_market_snapshot, load_universe

    snapshot = load_market_snapshot("market_implied/data/market_snapshot_example.json")
    universe = load_universe("market_implied/data/universe_default.json")
    result = build_expectations(snapshot, universe)
    print(result.premium_matrix())

Zie ``market_implied/docs/methodology.md`` voor de onderbouwing en de
literatuurverwijzingen per bouwsteen.
"""

from __future__ import annotations

from .blocks import BuildingBlock, ReturnBuildUp
from .curves import TermStructure, ZeroCurve
from .engine import ExpectationsResult, build_expectations
from .marketdata import MarketSnapshot, load_market_snapshot
from .models import AssetSpec, ModelContext, available_models, get_model, register
from .report import markdown_report, premium_table_text, summary_text, write_csv
from .riskfree import ROLLED_CASH, SPOT, RiskFreeModel
from .universe import Universe, load_universe

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "AssetSpec",
    "BuildingBlock",
    "ExpectationsResult",
    "MarketSnapshot",
    "ModelContext",
    "ReturnBuildUp",
    "RiskFreeModel",
    "ROLLED_CASH",
    "SPOT",
    "TermStructure",
    "Universe",
    "ZeroCurve",
    "available_models",
    "build_expectations",
    "get_model",
    "load_market_snapshot",
    "load_universe",
    "markdown_report",
    "premium_table_text",
    "register",
    "summary_text",
    "write_csv",
]
