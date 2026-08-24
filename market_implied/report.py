"""
Formatting of an :class:`~market_implied.engine.ExpectationsResult`.

Three renderers are provided: a plain-text table for the terminal, a Markdown
document with the full building-block audit trail, and CSV export.  All of
them lead with the ``as_of`` date, because a market-implied expectation
without its observation date is not interpretable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import pandas as pd

from .blocks import ASSUMPTION, MARKET
from .engine import ExpectationsResult
from .riskfree import RiskFreeModel

__all__ = [
    "format_percent",
    "summary_text",
    "premium_table_text",
    "markdown_report",
    "write_csv",
]


def format_percent(value, decimals: int = 2) -> str:
    """Render a decimal as a percentage string, blank for missing values."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return f"{value * 100:.{decimals}f}%"


def _percent_frame(frame: pd.DataFrame, columns: Iterable[str], decimals: int = 2):
    out = frame.copy()
    for col in columns:
        if col in out.columns:
            out[col] = out[col].map(lambda v: format_percent(v, decimals))
    return out


def premium_table_text(result: ExpectationsResult) -> str:
    """The headline deliverable: risk premium per asset class per horizon."""
    horizons = list(result.universe.horizons)

    rows = []
    for key in result.order:
        spec = result.universe.get(key)
        row = {"Beleggingscategorie": result.build_up(key, horizons[0]).name,
               "Categorie": spec.category}
        for h in horizons:
            bu = result.build_up(key, h)
            row[f"Risicopremie {int(h)}j"] = format_percent(bu.risk_premium)
        for h in horizons:
            bu = result.build_up(key, h)
            row[f"Verwacht rendement {int(h)}j"] = format_percent(bu.expected_return)
        rows.append(row)

    table = pd.DataFrame(rows)
    header = [
        f"Market-implied rendementsverwachtingen per {result.snapshot.as_of}",
        f"Basisvaluta: {result.snapshot.base_currency} (valuta-afgedekt)",
        "Verwacht rendement = risicovrije rente + risicopremie, meetkundig, per jaar.",
        "",
    ]
    for h in horizons:
        rf = result.build_up(result.order[0], h).risk_free
        header.append(f"Risicovrije rente {int(h)}j: {format_percent(rf)}")
    header.append("")
    return "\n".join(header) + table.to_string(index=False)


def summary_text(result: ExpectationsResult, decimals: int = 2) -> str:
    """Full summary table including arithmetic returns and volatility."""
    summary = result.summary_table()
    cols = [
        "name",
        "category",
        "horizon",
        "risk_free",
        "risk_premium",
        "expected_return",
        "expected_return_arithmetic",
        "volatility",
        "assumption_share",
    ]
    out = _percent_frame(
        summary[cols],
        [
            "risk_free",
            "risk_premium",
            "expected_return",
            "expected_return_arithmetic",
            "volatility",
        ],
        decimals,
    )
    out["assumption_share"] = out["assumption_share"].map(lambda v: f"{v:.0%}")
    out = out.rename(
        columns={
            "name": "Beleggingscategorie",
            "category": "Categorie",
            "horizon": "Horizon",
            "risk_free": "Risicovrij",
            "risk_premium": "Risicopremie",
            "expected_return": "E[R] meetkundig",
            "expected_return_arithmetic": "E[R] rekenkundig",
            "volatility": "Volatiliteit",
            "assumption_share": "Aandeel aanname",
        }
    )
    return out.to_string(index=False)


def _blocks_section(result: ExpectationsResult, horizon: float) -> List[str]:
    lines: List[str] = []
    for key in result.order:
        bu = result.build_up(key, horizon)
        lines.append(f"#### {bu.name}")
        lines.append("")
        lines.append("| Bouwsteen | Bijdrage | Herkomst | Toelichting |")
        lines.append("| --- | ---: | --- | --- |")
        for block in bu.blocks:
            herkomst = {
                MARKET: "markt",
                ASSUMPTION: "aanname",
            }.get(block.source, "afgeleid")
            note = block.note.replace("|", "\\|")
            lines.append(
                f"| {block.display_label} | {format_percent(block.value)} | {herkomst} | {note} |"
            )
        lines.append(
            f"| **Verwacht rendement** | **{format_percent(bu.expected_return)}** | | "
            f"risicovrij {format_percent(bu.risk_free)} + risicopremie "
            f"{format_percent(bu.risk_premium)} |"
        )
        lines.append("")
        if bu.diagnostics:
            diag = ", ".join(
                f"{k} = {v:.4g}" if isinstance(v, (int, float)) else f"{k} = {v}"
                for k, v in bu.diagnostics.items()
            )
            lines.append(f"*Diagnostiek:* {diag}")
            lines.append("")
    return lines


def markdown_report(result: ExpectationsResult) -> str:
    """Render the full report, including the per-asset building-block tables."""
    horizons = list(result.universe.horizons)
    lines: List[str] = [
        "# Market-implied rendementsverwachtingen",
        "",
        f"- **Marktopname:** {result.snapshot.as_of}",
        f"- **Basisvaluta:** {result.snapshot.base_currency} (buitenlandse categorieen valuta-afgedekt)",
        f"- **Universum:** {result.universe.name}",
        f"- **Risicovrije conventie:** `{result.universe.risk_free_convention}`",
        f"- **Waarderingsconvergentie actief:** {'ja' if result.universe.apply_valuation else 'nee'}",
        "",
        "Alle rendementen zijn meetkundig en per jaar, tenzij anders vermeld.",
        "",
        "## 1. Risicopremies per beleggingscategorie",
        "",
    ]

    header = "| Beleggingscategorie | Categorie |"
    divider = "| --- | --- |"
    for h in horizons:
        header += f" Risicopremie {int(h)}j | E[R] {int(h)}j |"
        divider += " ---: | ---: |"
    lines += [header, divider]

    for key in result.order:
        spec = result.universe.get(key)
        row = f"| {result.build_up(key, horizons[0]).name} | {spec.category} |"
        for h in horizons:
            bu = result.build_up(key, h)
            row += f" {format_percent(bu.risk_premium)} | {format_percent(bu.expected_return)} |"
        lines.append(row)
    lines.append("")

    lines.append("### Risicovrije rente (identiek voor alle categorieen)")
    lines.append("")
    lines.append("| Horizon | Zero rate | Termijnpremie | Risicovrije rente |")
    lines.append("| --- | ---: | ---: | ---: |")
    curve_name = f"{result.snapshot.base_currency}_nominal"
    rf_model = RiskFreeModel(
        curve=result.snapshot.curve(curve_name),
        term_premium=result.snapshot.term_premium(curve_name),
        convention=result.universe.risk_free_convention,
    )
    for h in horizons:
        lines.append(
            f"| {int(h)} jaar | {format_percent(rf_model.spot(h))} | "
            f"{format_percent(rf_model.term_premium_at(h))} | "
            f"{format_percent(rf_model.rate(h))} |"
        )
    lines.append("")

    lines.append("## 2. Opbouw uit bouwstenen")
    lines.append("")
    for h in horizons:
        lines.append(f"### Horizon {int(h)} jaar")
        lines.append("")
        lines += _blocks_section(result, h)

    lines.append("## 3. Volledigheid en beperkingen")
    lines.append("")
    lines.append(
        "De kolom *aandeel aanname* geeft per categorie aan welk deel van de "
        "risicopremie niet uit marktprijzen komt maar uit de literatuur. "
        "Hoe hoger dit getal, hoe minder de uitkomst 'market implied' is."
    )
    lines.append("")
    lines.append("| Beleggingscategorie | Aandeel aanname |")
    lines.append("| --- | ---: |")
    for key in result.order:
        bu = result.build_up(key, horizons[0])
        lines.append(f"| {bu.name} | {bu.assumption_share():.0%} |")
    lines.append("")
    return "\n".join(lines)


def write_csv(result: ExpectationsResult, directory: "str | Path") -> List[Path]:
    """Write the summary, blocks and diagnostics tables as CSV files."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, frame in (
        ("summary", result.summary_table()),
        ("blocks", result.blocks_table()),
        ("diagnostics", result.diagnostics_table()),
    ):
        path = directory / f"market_implied_{name}_{result.snapshot.as_of}.csv"
        frame.to_csv(path, index=False)
        written.append(path)
    return written
