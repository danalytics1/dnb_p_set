"""
HTML reporting utilities for DNB scenario sets.
"""

from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd

from .constants import BLOCKS


def _format_scalar(value: object, decimals: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{decimals}f}"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return escape(str(value))


def _df_to_html(df: pd.DataFrame, decimals: int = 6) -> str:
    formatted = df.copy()
    for col in formatted.columns:
        formatted[col] = formatted[col].map(lambda value: _format_scalar(value, decimals))
    return formatted.to_html(index=False, escape=False)


def _summary_rows(scenario_set) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in scenario_set.variables:
        arr = scenario_set.get(name)
        spec = BLOCKS[name]
        rows.append(
            {
                "Variabele": name,
                "Omschrijving": spec.description_nl,
                "Vorm": f"{arr.shape[0]} × {arr.shape[1]}",
                "Gemiddelde": float(arr.mean()),
                "Standaardafwijking": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
                "Minimum": float(arr.min()),
                "Maximum": float(arr.max()),
            }
        )
    return rows


def _difference_rows(current_set, previous_set) -> list[dict[str, object]]:
    current_variables = set(current_set.variables)
    previous_variables = set(previous_set.variables)
    variables = sorted(current_variables | previous_variables)
    rows: list[dict[str, object]] = []

    for name in variables:
        if name not in current_variables:
            rows.append(
                {
                    "Variabele": name,
                    "Status": "alleen in vorige set",
                    "Huidige vorm": "",
                    "Vorige vorm": f"{previous_set.get(name).shape[0]} × {previous_set.get(name).shape[1]}",
                    "Delta gemiddelde": None,
                    "Max abs delta": None,
                }
            )
            continue

        if name not in previous_variables:
            rows.append(
                {
                    "Variabele": name,
                    "Status": "nieuw in huidige set",
                    "Huidige vorm": f"{current_set.get(name).shape[0]} × {current_set.get(name).shape[1]}",
                    "Vorige vorm": "",
                    "Delta gemiddelde": None,
                    "Max abs delta": None,
                }
            )
            continue

        current_arr = current_set.get(name)
        previous_arr = previous_set.get(name)
        shared_shape = tuple(min(a, b) for a, b in zip(current_arr.shape, previous_arr.shape))
        current_shared = current_arr[: shared_shape[0], : shared_shape[1]]
        previous_shared = previous_arr[: shared_shape[0], : shared_shape[1]]
        delta = current_shared - previous_shared
        rows.append(
            {
                "Variabele": name,
                "Status": "gewijzigd" if current_arr.shape != previous_arr.shape or not np.array_equal(current_shared, previous_shared) else "ongewijzigd",
                "Huidige vorm": f"{current_arr.shape[0]} × {current_arr.shape[1]}",
                "Vorige vorm": f"{previous_arr.shape[0]} × {previous_arr.shape[1]}",
                "Delta gemiddelde": float(delta.mean()),
                "Max abs delta": float(np.abs(delta).max()),
            }
        )
    return rows


def build_html_report(current_set, previous_set=None, title: str | None = None) -> str:
    """Build an HTML report for a current scenario set and optional previous set."""
    title = title or f"DNB {current_set.set_type}-set rapport"

    summary_df = pd.DataFrame(_summary_rows(current_set))
    sections = [
        "<!DOCTYPE html>",
        "<html lang='nl'>",
        "<head>",
        "<meta charset='utf-8'>",
        f"<title>{escape(title)}</title>",
        "<style>body{font-family:Arial,sans-serif;margin:2rem;line-height:1.4}"
        "table{border-collapse:collapse;width:100%;margin-bottom:2rem}"
        "th,td{border:1px solid #ccc;padding:.5rem;text-align:left}"
        "th{background:#f4f4f4}h1,h2{margin-top:1.5rem}</style>",
        "</head>",
        "<body>",
        f"<h1>{escape(title)}</h1>",
        "<h2>Huidige set</h2>",
        "<ul>",
        f"<li>Set type: {escape(current_set.set_type)}</li>",
        f"<li>Bronbestand: {escape(str(current_set.source_path or 'in-memory'))}</li>",
        f"<li>Aantal variabelen: {len(current_set.variables)}</li>",
        f"<li>Aantal scenario's: {current_set.n_scenarios}</li>",
        "</ul>",
        "<h2>Overzicht huidige set</h2>",
        _df_to_html(summary_df),
    ]

    if previous_set is not None:
        diff_df = pd.DataFrame(_difference_rows(current_set, previous_set))
        sections.extend(
            [
                "<h2>Verschillen ten opzichte van de vorige set</h2>",
                "<ul>",
                f"<li>Vorige set type: {escape(previous_set.set_type)}</li>",
                f"<li>Vorige bron: {escape(str(previous_set.source_path or 'in-memory'))}</li>",
                "</ul>",
                _df_to_html(diff_df),
            ]
        )

    sections.extend(["</body>", "</html>"])
    return "\n".join(sections)
