"""
Command-line entry point for the DNB scenario-set HTML report.

Installed as ``dnb-p-set-report``; also reachable as
``python -m dnb_p_set.report_cli`` or via the ``generate_report.py`` script in
the repository root.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from .metrics import ScenarioMetrics, compute_metrics
from .reporting import build_html_report
from .scenario_set import ScenarioSet

logger = logging.getLogger("dnb_p_set.report")

# Blocks the report needs.  The stochastic discount factor (Q-set only) is not
# used, so it is never read from disk.
REPORT_VARIABLES = [
    "state_variable_1",
    "state_variable_2",
    "state_variable_3",
    "equity_return",
    "price_inflation_eu",
    "price_inflation_nl",
    "phi_nominal",
    "psi_nominal",
    "phi_real_eu",
    "psi_real",
    "phi_real_nl",
]


def _label_for(path: Path, override: str | None) -> str:
    """Use the explicit label, else a quarter tag from the filename, else the stem."""
    if override:
        return override
    import re

    match = re.search(r"(20\d{2})\s*[-_ ]?\s*(Q[1-4])", path.stem, re.IGNORECASE)
    if match:
        return f"{match.group(1)}{match.group(2).upper()}"
    return path.stem


def _prepare(
    path: Path,
    label: str | None,
    reference: ScenarioMetrics | None = None,
) -> ScenarioMetrics:
    """Load one set, reduce it to metrics, and release the raw arrays."""
    resolved = _label_for(path, label)
    started = time.time()
    logger.info("Loading %s (%s)", path.name, resolved)
    scenario_set = ScenarioSet.from_csv(path, variables=REPORT_VARIABLES)
    logger.info("Loaded in %.1fs; computing metrics", time.time() - started)

    metrics = compute_metrics(scenario_set, label=resolved, reference=reference)
    del scenario_set
    logger.info("Metrics for %s ready in %.1fs", resolved, time.time() - started)
    return metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an HTML report for DNB scenario sets.",
    )
    parser.add_argument(
        "--current", required=True, metavar="CSV",
        help="Path to the current scenario CSV file.",
    )
    parser.add_argument(
        "--output", required=True, metavar="HTML",
        help="Path where the HTML report will be written.",
    )
    parser.add_argument(
        "--previous", metavar="CSV",
        help="Optional previous scenario CSV file to compare against.",
    )
    parser.add_argument(
        "--label", metavar="TEXT",
        help="Short name for the current set (default: quarter from the filename).",
    )
    parser.add_argument(
        "--previous-label", metavar="TEXT",
        help="Short name for the previous set.",
    )
    parser.add_argument("--title", metavar="TEXT", help="Custom report title.")
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress progress logging."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    current_path = Path(args.current)
    if not current_path.exists():
        print(f"Error: current file not found: {current_path}", file=sys.stderr)
        return 1

    previous_path = Path(args.previous) if args.previous else None
    if previous_path is not None and not previous_path.exists():
        print(f"Error: previous file not found: {previous_path}", file=sys.stderr)
        return 1

    # One set at a time: a DNB set is ~0.5 GB in memory, and the metrics
    # bundle that replaces it is a few hundred kilobytes.
    current = _prepare(current_path, args.label)
    previous = None
    if previous_path is not None:
        previous = _prepare(previous_path, args.previous_label, reference=current)

    logger.info("Rendering report")
    html = build_html_report(current, previous_set=previous, title=args.title)

    output_path = Path(args.output)
    if output_path.parent != Path(""):
        output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    size_mb = output_path.stat().st_size / 1e6
    print(f"HTML report written to: {output_path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
