#!/usr/bin/env python3
"""
Standalone script to generate an HTML report for DNB scenario sets.

Usage
-----
Basic (current set only):
    python generate_report.py --current DNB_P_scenarioset_2025Q1.csv --output report.html

With comparison to a previous set:
    python generate_report.py \\
        --current DNB_P_scenarioset_2025Q1.csv \\
        --previous DNB_P_scenarioset_2024Q4.csv \\
        --output report.html

With a custom title:
    python generate_report.py \\
        --current DNB_P_scenarioset_2025Q1.csv \\
        --output report.html \\
        --title "DNB P-set rapport Q1 2025"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent))

from dnb_p_set.scenario_set import ScenarioSet
from dnb_p_set.reporting import build_html_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an HTML report for DNB scenario sets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--current",
        required=True,
        metavar="CSV",
        help="Path to the current scenario CSV file.",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="HTML",
        help="Path where the HTML report will be written.",
    )
    parser.add_argument(
        "--previous",
        metavar="CSV",
        help="Optional path to a previous scenario CSV file for comparison.",
    )
    parser.add_argument(
        "--title",
        metavar="TEXT",
        help="Optional custom report title.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    current_path = Path(args.current)
    if not current_path.exists():
        print(f"Error: current file not found: {current_path}", file=sys.stderr)
        sys.exit(1)

    current = ScenarioSet.from_csv(current_path)

    previous = None
    if args.previous:
        previous_path = Path(args.previous)
        if not previous_path.exists():
            print(f"Error: previous file not found: {previous_path}", file=sys.stderr)
            sys.exit(1)
        previous = ScenarioSet.from_csv(previous_path)

    html = build_html_report(current, previous_set=previous, title=args.title)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"HTML report written to: {output_path}")


if __name__ == "__main__":
    main()
