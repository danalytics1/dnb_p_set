from __future__ import annotations

import argparse
from pathlib import Path

from .scenario_set import ScenarioSet
from .reporting import build_html_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an HTML report for DNB scenario sets.")
    parser.add_argument("--current", required=True, help="Path to current scenario CSV file")
    parser.add_argument("--output", required=True, help="Path to output HTML report file")
    parser.add_argument("--previous", help="Optional path to previous scenario CSV file")
    parser.add_argument("--title", help="Optional custom report title")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    current = ScenarioSet.from_csv(args.current)
    previous = ScenarioSet.from_csv(args.previous) if args.previous else None

    html = build_html_report(current, previous_set=previous, title=args.title)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"HTML report written to: {output_path}")


if __name__ == "__main__":
    main()
