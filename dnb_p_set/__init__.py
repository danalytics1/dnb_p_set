"""
dnb_p_set – Python package for analyzing DNB P and Q scenario sets.

De Nederlandsche Bank (DNB) publishes quarterly scenario sets (P-set and
Q-set) for use in pension fund projections under the Wet Toekomst Pensioenen
(WTP).  This package provides tools for loading, describing and analysing
those scenario CSV files.

Quick start
-----------
>>> from dnb_p_set import ScenarioSet
>>> ss = ScenarioSet.from_csv("DNB_P_scenarioset_2025Q1.csv")
>>> print(ss.summary())
>>> stats = ss.describe("equity_return")
>>> print(stats.head())

References
----------
* DNB scenariosets page:
  https://www.dnb.nl/voor-de-sector/open-boek-toezicht/sectoren/pensioenfondsen/
  dnb-publiceert-definitieve-scenariosets-bij-wet-toekomst-pensioenen/
"""

from .scenario_set import ScenarioSet
from .loader import load_csv, load_block, detect_set_type
from .constants import BLOCKS, VARIABLE_ALIASES, BlockSpec
from . import analysis
from . import plotting
from .reporting import build_html_report

__all__ = [
    "ScenarioSet",
    "load_csv",
    "load_block",
    "detect_set_type",
    "BLOCKS",
    "VARIABLE_ALIASES",
    "BlockSpec",
    "analysis",
    "plotting",
    "build_html_report",
]

__version__ = "0.1.0"
__author__ = "danalytics1"
