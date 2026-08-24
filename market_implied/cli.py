"""
Command-line interface.

.. code-block:: console

    $ python -m market_implied                       # standaardtabel
    $ python -m market_implied --format markdown -o rapport.md
    $ python -m market_implied --horizons 5 10 15 --rf-convention spot
    $ python -m market_implied --no-valuation        # pure carry, geen convergentie
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from .engine import build_expectations
from .marketdata import load_market_snapshot
from .report import markdown_report, premium_table_text, summary_text, write_csv
from .universe import load_universe

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_SNAPSHOT = DATA_DIR / "market_snapshot_example.json"
DEFAULT_UNIVERSE = DATA_DIR / "universe_default.json"

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="market-implied",
        description=(
            "Bepaal market-implied rendementsverwachtingen per beleggingscategorie, "
            "opgebouwd uit bouwstenen met een gemeenschappelijke risicovrije rente."
        ),
    )
    parser.add_argument(
        "--market",
        type=Path,
        default=DEFAULT_SNAPSHOT,
        help="JSON met de marktopname (default: het meegeleverde voorbeeld).",
    )
    parser.add_argument(
        "--universe",
        type=Path,
        default=DEFAULT_UNIVERSE,
        help="JSON met de beleggingscategorieen en hun modelparameters.",
    )
    parser.add_argument(
        "--horizons",
        type=float,
        nargs="+",
        default=None,
        help="Horizons in jaren (default: uit het universumbestand, 5 en 15).",
    )
    parser.add_argument(
        "--rf-convention",
        choices=("rolled_cash", "spot"),
        default=None,
        help=(
            "rolled_cash: risicovrij = verwachte gemiddelde korte rente (zero minus "
            "termijnpremie). spot: risicovrij = horizon-matched zero rate."
        ),
    )
    parser.add_argument(
        "--no-valuation",
        action="store_true",
        help="Zet alle waarderings- en spreadconvergentiebouwstenen uit (pure carry).",
    )
    parser.add_argument(
        "--format",
        choices=("premiums", "summary", "markdown", "blocks"),
        default="premiums",
        help="Uitvoerformaat.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Schrijf de uitvoer naar dit bestand in plaats van naar stdout.",
    )
    parser.add_argument(
        "--csv-dir",
        type=Path,
        default=None,
        help="Schrijf daarnaast summary/blocks/diagnostics als CSV naar deze map.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point.  Returns a shell exit code."""
    args = build_parser().parse_args(argv)

    snapshot = load_market_snapshot(args.market)
    universe = load_universe(
        args.universe,
        risk_free_convention=args.rf_convention,
        apply_valuation=False if args.no_valuation else None,
    )
    result = build_expectations(snapshot, universe, horizons=args.horizons)

    if args.format == "premiums":
        text = premium_table_text(result)
    elif args.format == "summary":
        text = summary_text(result)
    elif args.format == "markdown":
        text = markdown_report(result)
    else:
        text = result.blocks_table().to_string(index=False)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Geschreven naar {args.output}", file=sys.stderr)
    else:
        print(text)

    if args.csv_dir:
        paths: List[Path] = write_csv(result, args.csv_dir)
        for path in paths:
            print(f"Geschreven naar {path}", file=sys.stderr)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
