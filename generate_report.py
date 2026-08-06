#!/usr/bin/env python3
"""
Standalone script to generate an HTML report for DNB scenario sets.

Runs from the repository root without installing the package.  All options are
handled by :mod:`dnb_p_set.report_cli`.

Usage
-----
Current set only::

    python generate_report.py --current "import/CP2022 P scenarioset 100K 2026Q3.csv" \\
        --output report.html

With comparison to the previous quarter::

    python generate_report.py \\
        --current "import/CP2022 P scenarioset 100K 2026Q3.csv" \\
        --previous "import/CP2022 P scenarioset 100K 2026Q2.csv" \\
        --output report.html

Labels are derived from the filename (e.g. ``2026Q3``); override them with
``--label`` / ``--previous-label``, and the report title with ``--title``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dnb_p_set.report_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
