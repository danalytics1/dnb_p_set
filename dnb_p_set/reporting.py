"""
HTML reporting for DNB scenario sets.

The report is a single self-contained file: charts are rendered with
matplotlib and inlined as ``data:`` URIs, so it can be mailed around or
opened straight from disk without any assets alongside it.

Every chart is paired with the table it was drawn from, so the numbers stay
readable when colour is not available.

Example
-------
>>> from dnb_p_set import ScenarioSet, compute_metrics, build_html_report
>>> current = compute_metrics(ScenarioSet.from_csv("2026Q3.csv"), label="2026Q3")
>>> previous = compute_metrics(
...     ScenarioSet.from_csv("2026Q2.csv"), label="2026Q2", reference=current
... )
>>> open("report.html", "w", encoding="utf-8").write(
...     build_html_report(current, previous)
... )
"""

from __future__ import annotations

import datetime as _dt
import logging
from html import escape

import numpy as np
import pandas as pd

from . import charts
from .constants import CURVE_HORIZONS, LIABILITY_HORIZON, RETURN_HORIZONS
from .metrics import CURVE_SPECS, ScenarioMetrics, compute_metrics

logger = logging.getLogger(__name__)

__all__ = ["build_html_report"]

# Percentile columns rendered in the tables
_TABLE_PERCENTILES = ["p5", "p25", "p50", "p75", "p95"]

_CSS = """
:root {
  --surface: #fcfcfb;
  --plane: #f2f2ee;
  --ink: #0b0b0b;
  --secondary: #52514e;
  --muted: #898781;
  --grid: #e1e0d9;
  --baseline: #c3c2b7;
  --up: #2a78d6;
  --down: #d03b3b;
  --accent: #2a78d6;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--plane);
  color: var(--ink);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 15px;
  line-height: 1.55;
}
.wrap { max-width: 1180px; margin: 0 auto; padding: 0 24px 96px; }
header.masthead {
  background: var(--surface);
  border-bottom: 1px solid var(--grid);
  padding: 40px 0 28px;
  margin-bottom: 28px;
}
header.masthead .wrap { padding-bottom: 0; }
h1 { font-size: 30px; line-height: 1.2; margin: 0 0 6px; letter-spacing: -0.01em; }
h2 {
  font-size: 21px; margin: 0 0 4px; letter-spacing: -0.01em;
  scroll-margin-top: 16px;
}
h3 { font-size: 15px; margin: 28px 0 8px; color: var(--secondary); font-weight: 600; }
p.lede { color: var(--secondary); margin: 0 0 4px; max-width: 78ch; }
p.note { color: var(--muted); font-size: 13px; margin: 6px 0 0; max-width: 88ch; }
a { color: var(--accent); }
code {
  font-size: 0.92em; background: var(--plane); padding: 1px 5px; border-radius: 4px;
  overflow-wrap: anywhere;
}

.meta { display: flex; flex-wrap: wrap; gap: 8px 28px; margin-top: 18px; }
.meta div { font-size: 13px; color: var(--muted); }
.meta div b { display: block; color: var(--ink); font-size: 14px; font-weight: 600; }

nav.toc {
  background: var(--surface); border: 1px solid var(--grid); border-radius: 10px;
  padding: 14px 18px; margin-bottom: 28px;
  display: flex; flex-wrap: wrap; gap: 6px 22px; font-size: 13.5px;
}
nav.toc a { text-decoration: none; }
nav.toc a:hover { text-decoration: underline; }

section {
  background: var(--surface); border: 1px solid var(--grid); border-radius: 12px;
  padding: 26px 28px; margin-bottom: 22px;
}

.tiles {
  display: grid; gap: 12px; margin: 20px 0 4px;
  grid-template-columns: repeat(auto-fill, minmax(232px, 1fr));
}
.tile {
  border: 1px solid var(--grid); border-radius: 10px; padding: 14px 16px;
  background: var(--plane);
}
.tile .label { font-size: 12.5px; color: var(--secondary); line-height: 1.35; min-height: 2.7em; }
.tile .value { font-size: 26px; font-weight: 600; margin-top: 6px; letter-spacing: -0.02em; }
.tile .delta { font-size: 13px; margin-top: 2px; font-variant-numeric: tabular-nums; }
.tile .delta.up { color: var(--up); }
.tile .delta.down { color: var(--down); }
.tile .delta.flat { color: var(--muted); }
.tile .foot { font-size: 11.5px; color: var(--muted); margin-top: 6px; }

figure { margin: 22px 0 0; }
figure img { width: 100%; height: auto; display: block; border-radius: 8px; }
figcaption { font-size: 12.5px; color: var(--muted); margin-top: 8px; max-width: 92ch; }

details { margin-top: 10px; }
details > summary {
  cursor: pointer; font-size: 13px; color: var(--accent); list-style: none;
  padding: 5px 0; user-select: none;
}
details > summary::-webkit-details-marker { display: none; }
details > summary::before { content: "▸ "; }
details[open] > summary::before { content: "▾ "; }

.scroll { overflow-x: auto; }
table {
  border-collapse: collapse; width: 100%; font-size: 13px;
  font-variant-numeric: tabular-nums; margin-top: 6px;
}
th, td { padding: 7px 10px; text-align: right; border-bottom: 1px solid var(--grid); white-space: nowrap; }
th { color: var(--secondary); font-weight: 600; background: var(--plane); }
th:first-child, td:first-child { text-align: left; }
tbody tr:hover { background: var(--plane); }
td.up { color: var(--up); }
td.down { color: var(--down); }
td.flat { color: var(--muted); }

.flag {
  display: inline-block; font-size: 11px; padding: 1px 7px; border-radius: 999px;
  border: 1px solid var(--grid); color: var(--muted); background: var(--plane);
}

footer.colophon {
  color: var(--muted); font-size: 12.5px; margin-top: 32px;
  border-top: 1px solid var(--grid); padding-top: 18px;
}

@media print {
  body { background: #fff; }
  section { break-inside: avoid; border-color: #ddd; }
  nav.toc { display: none; }
  details { display: none; }
}
"""


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _dutch(text: str) -> str:
    """Swap English separators for Dutch ones: ``1,234.50`` becomes ``1.234,50``."""
    return text.translate(str.maketrans({",": ".", ".": ","}))


def _fmt_rate(value: float, decimals: int = 2) -> str:
    if value is None or not np.isfinite(value):
        return "–"
    return _dutch(f"{value * 100:,.{decimals}f}") + "%"


def _fmt_number(value: float, decimals: int = 2) -> str:
    if value is None or not np.isfinite(value):
        return "–"
    return _dutch(f"{value:,.{decimals}f}")


def _fmt_count(value: int) -> str:
    """Format a plain count, e.g. 100000 becomes ``100.000``."""
    return _dutch(f"{int(value):,}")


def _fmt_euro(value: float, decimals: int = 0) -> str:
    if value is None or not np.isfinite(value):
        return "–"
    return "€ " + _dutch(f"{value:,.{decimals}f}")


def _fmt_value(value: float, unit: str) -> str:
    if unit == "rate":
        return _fmt_rate(value)
    if unit == "years":
        return f"{_fmt_number(value, 1)} jr"
    return _fmt_number(value)


def _fmt_delta(delta: float, unit: str) -> str:
    if delta is None or not np.isfinite(delta):
        return "–"
    if unit == "rate":
        return _dutch(f"{delta * 10_000:+,.1f}") + " bp"
    if unit == "years":
        return _dutch(f"{delta:+,.2f}") + " jr"
    return _dutch(f"{delta:+,.3f}")


def _direction(delta: float, tolerance: float = 0.0) -> str:
    if delta is None or not np.isfinite(delta) or abs(delta) <= tolerance:
        return "flat"
    return "up" if delta > 0 else "down"


def _within_noise(kpi, prev_kpi) -> bool | None:
    """True when the change is inside the combined 95 % Monte-Carlo band."""
    if kpi is None or prev_kpi is None:
        return None
    if kpi.se is None or prev_kpi.se is None:
        return None
    combined = float(np.hypot(kpi.se, prev_kpi.se))
    if combined == 0.0:
        return None
    return abs(kpi.value - prev_kpi.value) < 1.96 * combined


def _table(
    rows: list[list[str]],
    headers: list[str],
    classes: list[list[str]] | None = None,
) -> str:
    """Render a pre-formatted table; *classes* optionally styles each cell."""
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = []
    for i, row in enumerate(rows):
        cells = []
        for j, cell in enumerate(row):
            css = ""
            if classes is not None and classes[i][j]:
                css = f' class="{classes[i][j]}"'
            cells.append(f"<td{css}>{cell}</td>")
        body.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<div class="scroll"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def _details(summary: str, content: str) -> str:
    return f"<details><summary>{escape(summary)}</summary>{content}</details>"


def _figure(fig, caption: str, table_html: str = "", table_label: str = "") -> str:
    """Inline a matplotlib figure with its caption and optional data table."""
    uri = charts.figure_to_data_uri(fig)
    parts = [
        "<figure>",
        f'<img src="{uri}" alt="{escape(caption)}">',
        f"<figcaption>{caption}</figcaption>",
    ]
    if table_html:
        parts.append(_details(table_label or "Toon onderliggende cijfers", table_html))
    parts.append("</figure>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _masthead(current: ScenarioMetrics, previous: ScenarioMetrics | None, title: str) -> str:
    comparison = (
        f"Vergeleken met <b>{escape(previous.label)}</b>"
        if previous is not None
        else "Geen vergelijkingsset opgegeven"
    )
    lede = (
        "Verdelingen van de rentetermijnstructuur, aandelenrendementen en inflatie "
        "in de DNB-scenarioset, en hoe die zijn verschoven ten opzichte van de "
        "vorige publicatie."
    )
    meta = [
        ("Huidige set", escape(current.label)),
        ("Vorige set", escape(previous.label) if previous else "–"),
        ("Set-type", f"{escape(current.set_type)}-set"),
        ("Scenario's", _fmt_count(current.n_scenarios)),
        ("Projectiejaren", str(current.n_years)),
        ("Gegenereerd", _dt.datetime.now().strftime("%d-%m-%Y %H:%M")),
    ]
    tiles = "".join(f"<div><b>{value}</b>{escape(label)}</div>" for label, value in meta)
    return (
        '<header class="masthead"><div class="wrap">'
        f"<h1>{escape(title)}</h1>"
        f'<p class="lede">{lede}</p>'
        f'<p class="note">{comparison}. Bron: <code>{escape(current.source)}</code></p>'
        f'<div class="meta">{tiles}</div>'
        "</div></header>"
    )


def _toc(sections: list[tuple[str, str]]) -> str:
    links = "".join(
        f'<a href="#{anchor}">{escape(label)}</a>' for anchor, label in sections
    )
    return f'<nav class="toc">{links}</nav>'


def _headline_box_table(current: ScenarioMetrics) -> str:
    """Percentile table backing :func:`charts.headline_boxplots`."""
    headers = ["Maatstaf", "Gemiddelde", "p5", "p25", "Mediaan", "p75", "p95"]
    rows = []
    for kind, key, maturity, label, _group in charts._HEADLINE_BOX_SPECS:
        if kind == "series":
            series = current.series.get(key)
            frame = series.annual if series is not None else None
        else:
            curve = current.curves.get(key)
            frame = curve.paths.get(maturity) if curve is not None else None
        if frame is None or 1 not in frame.index:
            continue
        row = frame.loc[1]
        rows.append(
            [label.replace("\n", " ")]
            + [
                _fmt_rate(row[col])
                for col in ("mean", "p5", "p25", "p50", "p75", "p95")
            ]
        )
    return _table(rows, headers)


def _headline_section(current: ScenarioMetrics, previous: ScenarioMetrics | None) -> str:
    tiles = []
    for kpi in current.kpis.values():
        prev_kpi = previous.kpis.get(kpi.key) if previous is not None else None
        delta_html = '<div class="delta flat">geen vergelijking</div>'
        if prev_kpi is not None:
            delta = kpi.value - prev_kpi.value
            noise = _within_noise(kpi, prev_kpi)
            suffix = " · binnen standaardfout" if noise else ""
            delta_html = (
                f'<div class="delta {_direction(delta)}">'
                f"{_fmt_delta(delta, kpi.unit)}{suffix}</div>"
            )
        foot = f'<div class="foot">{escape(kpi.note)}</div>' if kpi.note else ""
        tiles.append(
            '<div class="tile">'
            f'<div class="label">{escape(kpi.label)}</div>'
            f'<div class="value">{_fmt_value(kpi.value, kpi.unit)}</div>'
            f"{delta_html}{foot}"
            "</div>"
        )

    body = [
        '<section id="kern">',
        "<h2>Kernbevindingen</h2>",
        '<p class="lede">Kernmaatstaven van de huidige set met de verandering ten '
        "opzichte van de vorige set. Blauw betekent hoger, rood lager — dat is een "
        "richting, geen oordeel.</p>",
        f'<div class="tiles">{"".join(tiles)}</div>',
    ]

    try:
        box_fig = charts.headline_boxplots(current)
    except ValueError:
        box_fig = None
    if box_fig is not None:
        body.append(
            _figure(
                box_fig,
                "Verdeling van de kernmaatstaven in projectiejaar 1, huidige set "
                f"({escape(current.label)}). Box toont p25–p75 en mediaan, "
                "whiskers p5–p95, stip het gemiddelde.",
                _headline_box_table(current),
            )
        )

    if previous is not None:
        body.append(
            '<p class="note">Bij maatstaven die een verwachtingswaarde zijn wordt '
            "de verandering vergeleken met de gecombineerde Monte-Carlo-standaardfout "
            "(DNB-formules 2–5). Staat er <i>binnen standaardfout</i> bij, dan is het "
            "verschil niet te onderscheiden van simulatieruis.</p>"
        )
    body.append("</section>")
    return "".join(body)


def _curve_table(current: ScenarioMetrics, previous: ScenarioMetrics | None, key: str) -> str:
    curve = current.curves[key]
    prev_curve = previous.curves[key] if previous is not None else None

    headers = ["Looptijd", f"{current.label}"]
    if prev_curve is not None:
        headers += [f"{previous.label}", "Δ (bp)"]

    rows, classes = [], []
    for maturity, value in curve.spot.items():
        row = [f"{maturity} jr", _fmt_rate(value, 3)]
        css = ["", ""]
        if prev_curve is not None and maturity in prev_curve.spot.index:
            prev_value = float(prev_curve.spot.loc[maturity])
            delta = value - prev_value
            row += [_fmt_rate(prev_value, 3), _fmt_delta(delta, "rate")]
            css += ["", _direction(delta)]
        elif prev_curve is not None:
            row += ["–", "–"]
            css += ["", ""]
        rows.append(row)
        classes.append(css)
    return _table(rows, headers, classes)


def _percentile_table(
    frame: pd.DataFrame,
    index_label: str,
    as_rate: bool = True,
    decimals: int = 2,
    rows_limit: int | None = None,
) -> str:
    columns = ["mean"] + [c for c in _TABLE_PERCENTILES if c in frame.columns]
    headers = [index_label, "gemiddelde"] + columns[1:]
    frame = frame if rows_limit is None else frame.iloc[:rows_limit]
    rows = []
    for idx, record in frame.iterrows():
        cells = [str(idx)]
        for column in columns:
            value = float(record[column])
            cells.append(_fmt_rate(value, decimals) if as_rate else _fmt_number(value, 3))
        rows.append(cells)
    return _table(rows, headers)


def _term_structure_section(
    current: ScenarioMetrics, previous: ScenarioMetrics | None
) -> str:
    body = [
        '<section id="rente">',
        "<h2>Rentetermijnstructuur</h2>",
        '<p class="lede">De set bevat geen kant-en-klare curves maar de affiene '
        "parameters φ en Ψ. De zero-coupon rente volgt uit DNB-formule (1): "
        "<code>y(τ,t) = exp(−(φ(τ,t) + Σ Ψᵢ(τ)·Xᵢ(t)) / τ) − 1</code>, "
        "een jaarlijks samengestelde rente.</p>",
    ]

    start_note = (
        "De startcurve geldt bij aanvang van de projectie en is in alle scenario's "
        "gelijk, omdat de toestandsvariabelen op t=0 vastliggen."
        if current.curves["nominal"].deterministic_start
        else "Let op: de startcurve verschilt per scenario, wat niet wordt verwacht "
        "voor een DNB-set."
    )

    for key, label, _measure, _region in CURVE_SPECS:
        if key not in current.curves:
            continue
        body.append(f"<h3>{escape(label)}</h3>")
        body.append(
            _figure(
                charts.starting_curve(current, previous, key=key),
                f"Startcurve op t=0. {start_note if key == 'nominal' else ''} "
                "Het onderste paneel toont de verandering per looptijd in basispunten.",
                _curve_table(current, previous, key),
                "Toon curveniveaus per looptijd",
            )
        )

    nominal = current.curves["nominal"]
    horizon_tables = "".join(
        f"<h4 style='font-size:13px;color:#52514e;margin:14px 0 0'>"
        f"{'Startcurve (t=0)' if h == 0 else f'Projectiejaar {h}'}</h4>"
        + _percentile_table(nominal.by_horizon[h], "Looptijd")
        for h in CURVE_HORIZONS
        if h in nominal.by_horizon
    )
    body.append(
        _figure(
            charts.curve_fan_grid(current, previous, key="nominal"),
            "Spreiding van de nominale curve over de scenario's, per projectiejaar. "
            "De banden zijn de 5–95, 10–90 en 25–75 percentielintervallen; de "
            "oranje stippellijn is de mediaan van de vorige set."
            if previous is not None
            else "Spreiding van de nominale curve over de scenario's, per "
            "projectiejaar (5–95, 10–90 en 25–75 percentielintervallen).",
            horizon_tables,
            "Toon percentielen per projectiejaar",
        )
    )

    path_tables = "".join(
        f"<h4 style='font-size:13px;color:#52514e;margin:14px 0 0'>{m}-jaarsrente</h4>"
        + _percentile_table(
            nominal.paths[m].iloc[:: max(1, len(nominal.paths[m]) // 25)],
            "Projectiejaar",
        )
        for m in sorted(nominal.paths)
    )
    body.append(
        _figure(
            charts.rate_path_grid(current, previous, key="nominal"),
            "Ontwikkeling van vier kernlooptijden over de hele projectie. Hieruit "
            "blijkt hoe snel de set van de huidige curve naar het "
            "evenwichtsniveau beweegt.",
            path_tables,
            "Toon percentielen per projectiejaar (elke ~4 jaar)",
        )
    )

    bei_rows = []
    for maturity, record in current.breakeven.iterrows():
        bei_rows.append(
            [
                f"{maturity} jr",
                _fmt_rate(record["nominaal"], 3),
                _fmt_rate(record["reeel_nl"], 3),
                _fmt_rate(record["bei_nl"], 3),
                _fmt_rate(record["reeel_eu"], 3),
                _fmt_rate(record["bei_eu"], 3),
            ]
        )
    body.append(
        _figure(
            charts.breakeven_curve(current, previous),
            "Break-even inflatie is de inflatie waarbij de nominale en reële curve "
            "dezelfde uitkomst geven: <code>(1+y_nominaal)/(1+y_reëel) − 1</code>. "
            "Het is de inflatieverwachting die in de startcurves besloten ligt.",
            _table(
                bei_rows,
                ["Looptijd", "Nominaal", "Reëel NL", "BEI NL", "Reëel EU", "BEI EU"],
            ),
            "Toon nominale, reële en break-even niveaus",
        )
    )
    body.append("</section>")
    return "".join(body)


def _stats_table(
    current: ScenarioMetrics,
    previous: ScenarioMetrics | None,
    key: str,
) -> str:
    """Distribution statistics of the annualised return, per horizon."""
    series = current.series[key]
    prev_series = previous.series.get(key) if previous is not None else None

    fields = [
        ("mean", "Gemiddelde", "rate"),
        ("std", "Standaardafwijking", "rate"),
        ("p5", "p5", "rate"),
        ("p50", "Mediaan", "rate"),
        ("p95", "p95", "rate"),
    ]
    # Expected Shortfall says something p5 does not — the average *beyond* the
    # 5th percentile — but only where a downside tail is what matters.  VaR is
    # exactly -p5, so it would only repeat a row that is already there.
    if key == "equity":
        fields.append(("es95", "Expected Shortfall 95 % (verlies)", "rate"))
    fields += [
        ("skew", "Scheefheid", "plain"),
        ("kurtosis", "Kurtosis (excess)", "plain"),
    ]

    horizons = [h for h in RETURN_HORIZONS if h in series.stats]
    headers = ["Maatstaf"] + [f"{h} jr" for h in horizons]
    if prev_series is not None:
        headers += [f"Δ {h} jr" for h in horizons]

    rows, classes = [], []
    for field, label, kind in fields:
        row = [label]
        css = [""]
        for h in horizons:
            value = series.stats[h][field]
            row.append(_fmt_rate(value) if kind == "rate" else _fmt_number(value, 3))
            css.append("")
        if prev_series is not None:
            for h in horizons:
                if h not in prev_series.stats:
                    row.append("–")
                    css.append("")
                    continue
                delta = series.stats[h][field] - prev_series.stats[h][field]
                row.append(
                    _fmt_delta(delta, "rate")
                    if kind == "rate"
                    else _dutch(f"{delta:+.3f}")
                )
                css.append(_direction(delta))
        rows.append(row)
        classes.append(css)
    return _table(rows, headers, classes)


def _series_section(
    current: ScenarioMetrics,
    previous: ScenarioMetrics | None,
    key: str,
    anchor: str,
    heading: str,
    lede: str,
) -> str:
    series = current.series[key]
    body = [
        f'<section id="{anchor}">',
        f"<h2>{escape(heading)}</h2>",
        f'<p class="lede">{lede}</p>',
    ]

    body.append(
        _figure(
            charts.return_histogram(current, previous, key=key),
            "Verdeling van het rendement over het eerste projectiejaar, over alle "
            f"{_fmt_count(current.n_scenarios)} scenario's.",
            _percentile_table(series.annual.iloc[:20], "Projectiejaar"),
            "Toon percentielen per projectiejaar (eerste 20)",
        )
    )

    long_horizon = max(h for h in RETURN_HORIZONS if h in series.hist_annualised)
    body.append(
        _figure(
            charts.return_histogram(current, previous, key=key, horizon=long_horizon),
            f"Verdeling van het geannualiseerde rendement over {long_horizon} jaar. "
            "Diversificatie over de tijd maakt deze verdeling veel smaller dan die "
            "van één jaar.",
        )
    )

    body.append(
        _figure(
            charts.annualised_fan(current, previous, key=key),
            "Geannualiseerd rendement per horizon. De banden krimpen naarmate de "
            "horizon langer wordt; de mediaan convergeert naar het meetkundig "
            "gemiddelde van de kalibratie.",
            _percentile_table(
                series.annualised.loc[
                    [h for h in RETURN_HORIZONS if h in series.annualised.index]
                ],
                "Horizon (jr)",
            ),
            "Toon percentielen per horizon",
        )
    )

    body.append(
        _figure(
            charts.cumulative_fan(current, previous, key=key),
            "Cumulatieve ontwikkeling van een startwaarde 1, op logaritmische "
            "schaal zodat gelijke verticale afstanden gelijke procentuele "
            "verschillen zijn.",
            _percentile_table(
                series.cumulative.loc[
                    [h for h in RETURN_HORIZONS if h in series.cumulative.index]
                ],
                "Horizon (jr)",
                as_rate=False,
            ),
            "Toon cumulatieve indexniveaus",
        )
    )

    body.append(
        _figure(
            charts.annual_moments(current, previous, key=key),
            "Gemiddelde en volatiliteit van het 1-jaarsrendement per projectiejaar. "
            "Vlakke lijnen bevestigen dat de kalibratie stationair is over de "
            "projectie.",
        )
    )

    body.append("<h3>Verdelingsstatistieken per horizon</h3>")
    body.append(_stats_table(current, previous, key))
    body.append("</section>")
    return "".join(body)


def _liability_section(
    current: ScenarioMetrics, previous: ScenarioMetrics | None
) -> str:
    frame = current.liability
    if frame.empty:
        return ""
    prev_frame = previous.liability if previous is not None else None

    headers = ["Projectiejaar", "Contante waarde", "Standaardfout", "Duration"]
    if prev_frame is not None and not prev_frame.empty:
        headers += ["Δ waarde", "Δ waarde (%)", "Δ duration"]

    rows, classes = [], []
    for year, record in frame.iterrows():
        row = [
            "t=0 (startcurve)" if year == 0 else f"jaar {int(year)}",
            _fmt_number(record["pv_mean"], 3),
            _fmt_number(record["pv_se"], 4),
            f"{_fmt_number(record['duration_mean'], 2)} jr",
        ]
        css = ["", "", "", ""]
        if prev_frame is not None and year in prev_frame.index:
            delta = record["pv_mean"] - prev_frame.loc[year, "pv_mean"]
            pct = delta / prev_frame.loc[year, "pv_mean"]
            d_dur = record["duration_mean"] - prev_frame.loc[year, "duration_mean"]
            row += [
                _dutch(f"{delta:+,.3f}"),
                _dutch(f"{pct * 100:+,.2f}") + "%",
                _dutch(f"{d_dur:+,.2f}") + " jr",
            ]
            css += [_direction(delta), _direction(delta), _direction(d_dur)]
        elif prev_frame is not None and not prev_frame.empty:
            row += ["–", "–", "–"]
            css += ["", "", ""]
        rows.append(row)
        classes.append(css)

    return (
        '<section id="verplichtingen">'
        "<h2>Verplichtingenproxy</h2>"
        '<p class="lede">Een renteverandering is pas tastbaar als je hem vertaalt '
        "naar een waarde. Hieronder de contante waarde van een vlakke kasstroom van "
        f"1 per jaar gedurende {LIABILITY_HORIZON} jaar, verdisconteerd op de "
        "nominale curve, plus de Macaulay-duration van diezelfde kasstroom.</p>"
        + _table(rows, headers, classes)
        + '<p class="note">De duration geeft aan hoe gevoelig die waarde is: bij een '
        "duration van D daalt de waarde ruwweg D basispunten per basispunt "
        "rentestijging.</p>"
        "</section>"
    )


def _near_perfect_pairs(matrix: pd.DataFrame, threshold: float = 0.999) -> list[str]:
    """Variable pairs that move in lockstep, so they offer no diversification."""
    names = list(matrix.columns)
    pairs = []
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            value = float(matrix.loc[left, right])
            if abs(value) >= threshold:
                pairs.append(f"{left} en {right} (r = {_dutch(f'{value:+.4f}')})")
    return pairs


def _correlation_section(
    current: ScenarioMetrics, previous: ScenarioMetrics | None
) -> str:
    if current.correlations.empty:
        return ""
    matrix = current.correlations
    rows = [
        [escape(str(name))] + [_fmt_number(v, 3) for v in record]
        for name, record in matrix.iterrows()
    ]

    lockstep = _near_perfect_pairs(matrix)
    lockstep_note = ""
    if lockstep:
        listed = "; ".join(escape(pair) for pair in lockstep)
        lockstep_note = (
            '<p class="note"><b>Let op:</b> de volgende paren bewegen vrijwel '
            f"exact samen: {listed}. Tussen die variabelen valt in deze set geen "
            "diversificatie te behalen — de een is een (bijna) deterministische "
            "functie van de ander.</p>"
        )

    return (
        '<section id="correlaties">'
        "<h2>Samenhang tussen variabelen</h2>"
        '<p class="lede">Correlaties over het eerste projectiejaar tussen de '
        "rendementen, de inflaties en de renteverandering. Deze samenhang bepaalt "
        "hoeveel diversificatie een portefeuille in de set kan halen.</p>"
        + lockstep_note
        + _figure(
            charts.correlation_heatmap(current, previous),
            "Links de correlatiematrix van de huidige set; rechts het verschil met "
            "de vorige set op een fijnere schaal."
            if previous is not None
            else "Correlatiematrix van de huidige set.",
            _table(rows, ["Variabele"] + [escape(str(c)) for c in matrix.columns]),
            "Toon correlatiematrix als tabel",
        )
        + "</section>"
    )


def _maatmens_table(bundle) -> str:
    """The parameters every maatmens was projected with."""
    headers = [
        "Maatmens", "Geboortejaar", "Leeftijd op t=0", "Vermogen op t=0",
        "Pensioengevend salaris", "Franchise", "Premie", "Pensioenleeftijd",
        "Start-allocatie rendement", "Invaardatum",
    ]
    rows = []
    for person in bundle.people:
        mens = person.maatmens
        weight = float(bundle.lifecycle.rendement_weight(person.startleeftijd))
        rows.append(
            [
                escape(mens.naam),
                str(mens.geboortejaar),
                f"{person.startleeftijd} jr",
                _fmt_euro(mens.pensioenvermogen),
                _fmt_euro(mens.pensioengevend_salaris),
                _fmt_euro(mens.franchise),
                f"{_fmt_euro(mens.jaarpremie)} ({_fmt_rate(mens.premiepercentage, 0)} "
                "van de grondslag)",
                f"{mens.pensioenleeftijd} jr",
                _fmt_rate(weight, 1),
                mens.invaardatum.strftime("%d-%m-%Y"),
            ]
        )
    return _table(rows, headers)


def _portefeuille_table(bundle) -> str:
    """Composition and realised statistics of the two portfolios."""
    headers = [
        "Portefeuille", "Samenstelling", "Rekenkundig gemiddelde",
        "Meetkundig gemiddelde", "Volatiliteit", "p5", "p95",
    ]
    rows = []
    for portefeuille in bundle.portefeuilles:
        if portefeuille.key not in bundle.returns.index:
            continue
        record = bundle.returns.loc[portefeuille.key]
        rows.append(
            [
                escape(str(record["label"])),
                escape(str(record["samenstelling"])),
                _fmt_rate(float(record["gemiddelde"])),
                _fmt_rate(float(record["meetkundig"])),
                _fmt_rate(float(record["volatiliteit"])),
                _fmt_rate(float(record["p5"])),
                _fmt_rate(float(record["p95"])),
            ]
        )
    return _table(rows, headers)


def _allocation_table(bundle) -> str:
    """Allocation per age, thinned to every fifth year plus the anchor ages."""
    frame = bundle.allocation
    anchors = {age for age, _ in bundle.lifecycle.anchors}
    ages = [
        age for age in frame.index
        if age % 5 == 0 or age in anchors or age == frame.index[-1]
    ]
    rows = [
        [
            f"{age} jr",
            _fmt_rate(float(frame.loc[age, "rendement"]), 1),
            _fmt_rate(float(frame.loc[age, "bescherming"]), 1),
        ]
        for age in ages
    ]
    return _table(rows, ["Leeftijd", "Rendementsportefeuille", "Beschermingsportefeuille"])


def _wealth_path_table(bundle) -> str:
    """Percentiles of the capital per projection year, per maatmens."""
    parts = []
    for person in bundle.people:
        frame = person.paths
        rows = [
            [
                f"jaar {int(year)} ({int(record['leeftijd'])} jr)",
                _fmt_euro(record["mean"]),
                _fmt_euro(record["p5"]),
                _fmt_euro(record["p25"]),
                _fmt_euro(record["p50"]),
                _fmt_euro(record["p75"]),
                _fmt_euro(record["p95"]),
            ]
            for year, record in frame.iterrows()
        ]
        parts.append(
            f"<h4 style='font-size:13px;color:#52514e;margin:14px 0 0'>"
            f"{escape(person.maatmens.naam)}</h4>"
            + _table(
                rows,
                ["Projectiejaar", "Gemiddelde", "p5", "p25", "Mediaan", "p75", "p95"],
            )
        )
    return "".join(parts)


def _wealth_horizon_table(bundle) -> str:
    """Capital at each reported horizon, per maatmens."""
    headers = [
        "Maatmens", "Horizon", "Leeftijd", "Gemiddelde", "p5", "p25",
        "Mediaan", "p75", "p95", "Totale inleg (gemiddeld)",
    ]
    rows = []
    for person in bundle.people:
        mens = person.maatmens
        for horizon in bundle.horizons:
            record = person.horizons.get(horizon)
            if record is None:
                continue
            schedule = person.schedule.iloc[:horizon]
            inleg = mens.pensioenvermogen + float(schedule["premie"].sum())
            rows.append(
                [
                    escape(mens.naam),
                    f"{horizon} jr",
                    f"{person.startleeftijd + horizon} jr",
                    _fmt_euro(record["mean"]),
                    _fmt_euro(record["p5"]),
                    _fmt_euro(record["p25"]),
                    _fmt_euro(record["p50"]),
                    _fmt_euro(record["p75"]),
                    _fmt_euro(record["p95"]),
                    _fmt_euro(inleg),
                ]
            )
    return _table(rows, headers)


def _gerealiseerde_portefeuille_table(bundle) -> str:
    """Where the realised rendement- and beschermingsportefeuille invest."""
    headers = ["Portefeuille", "Bron", "Kosten"]
    rows = [
        [
            escape(portefeuille.label),
            escape(portefeuille.bron_label),
            _fmt_rate(portefeuille.cost, 2),
        ]
        for portefeuille in bundle.gerealiseerde_portefeuilles
    ]
    return _table(rows, headers)


def _gerealiseerd_wealth_table(bundle) -> str:
    """Realised cumulative wealth per calendar year, per maatmens."""
    parts = []
    for person in bundle.people:
        if person.gerealiseerd is None:
            continue
        rows = [
            [
                f"{int(record['kalenderjaar'])} ({int(record['leeftijd'])} jr)",
                _fmt_euro(record["vermogen"]),
            ]
            for _, record in person.gerealiseerd.iterrows()
        ]
        parts.append(
            f"<h4 style='font-size:13px;color:#52514e;margin:14px 0 0'>"
            f"{escape(person.maatmens.naam)}</h4>"
            + _table(rows, ["Kalenderjaar", "Vermogen"])
        )
    return "".join(parts)


def _lifecycle_section(current: ScenarioMetrics) -> str:
    """Lifecycle, maatmensen and their projected wealth.

    Built only from *current*: the projection is a modelling exercise on top
    of one set, and overlaying a second set would say more about the model
    than about the difference between the quarters.
    """
    bundle = current.lifecycle
    if bundle is None or not bundle.people:
        return ""

    rendement, bescherming = bundle.portefeuilles[0], bundle.portefeuilles[1]
    horizons = ", ".join(f"{h} jaar" for h in bundle.horizons)

    body = [
        '<section id="maatmens">',
        "<h2>Maatmens en lifecycle</h2>",
        '<p class="lede">Wat de set voor een deelnemer betekent, hangt af van hoe '
        "die belegt. Hieronder wordt het vermogen van een aantal maatmensen "
        f"doorgerekend over {escape(horizons)}, met projectiejaar 0 in "
        f"{bundle.basisjaar}. Het vermogen wordt verdeeld over een "
        "<b>rendementsportefeuille</b> en een <b>beschermingsportefeuille</b>, "
        "die beide hun rendement uit deze scenarioset halen; de lifecycle bepaalt "
        "per leeftijd de verdeling.</p>",
        '<p class="note">Dit zijn modelaannames, geen DNB-voorschriften. De set '
        "levert alleen de rendementen. Per projectiejaar geldt "
        "<code>V(t+1) = (V(t) + premie(t)) · (1 + w·r_rendement + (1−w)·r_bescherming)</code>: "
        "de premie van een jaar wordt aan het begin van dat jaar ingelegd en "
        "deelt in het rendement van datzelfde jaar. Het salaris — en daarmee de "
        "premie — groeit mee met de gesimuleerde Nederlandse prijsinflatie. "
        "Premie-inleg stopt op de pensioenleeftijd.</p>",
        "<h3>Portefeuilles</h3>",
        _portefeuille_table(bundle),
        '<p class="note">De rendementsportefeuille volgt het gesimuleerde '
        f"aandelenrendement. De beschermingsportefeuille is een zerocouponobligatie "
        f"van {bescherming.bond_maturity} jaar die elk jaar wordt teruggerold naar "
        "die looptijd; het rendement volgt uit de nominale curve als "
        "<code>P(m−1, t+1) / P(m, t) − 1</code>. Die portefeuille wint dus juist "
        "waarde als de rente daalt — precies wanneer pensioen inkopen duurder "
        "wordt.</p>",
        "<h3>Lifecycle</h3>",
        _figure(
            charts.lifecycle_allocation(current),
            f"{escape(bundle.lifecycle.label)}: het aandeel in de "
            "rendementsportefeuille per leeftijd, met de rest in bescherming. "
            "De stippellijnen markeren de leeftijd van elke maatmens op t=0.",
            _allocation_table(bundle),
            "Toon allocatie per leeftijd",
        ),
        "<h3>Maatmensen</h3>",
        _maatmens_table(bundle),
        "<h3>Doorrekening van het vermogen</h3>",
        _figure(
            charts.maatmens_wealth_fan(current),
            "Ontwikkeling van het pensioenvermogen per maatmens over alle "
            f"{_fmt_count(current.n_scenarios)} scenario's. De banden zijn de "
            "5–95, 10–90 en 25–75 percentielintervallen. Elk paneel heeft een "
            "eigen schaal.",
            _wealth_path_table(bundle),
            "Toon vermogens per projectiejaar",
        ),
        _figure(
            charts.maatmens_horizon_boxes(current),
            f"Het vermogen na {escape(horizons)}. Box toont p25–p75 en mediaan, "
            "whiskers p5–p95, stip het gemiddelde. De verticale as is "
            "logaritmisch omdat de bedragen twee ordes van grootte uiteenlopen.",
            _wealth_horizon_table(bundle),
            "Toon vermogens per horizon",
        ),
        '<p class="note">De spreiding groeit met de horizon in euro\'s, maar de '
        "geannualiseerde spreiding krimpt — hetzelfde effect dat in de "
        "rendementsfan zichtbaar is. Voor de oudste maatmens dempt de lifecycle "
        "die spreiding bovendien actief, doordat het gewicht in de "
        f"{escape(rendement.label.lower())} met de leeftijd afloopt.</p>",
    ]

    people_met_gerealiseerd = [p for p in bundle.people if p.gerealiseerd is not None]
    body.append("<h3>Gerealiseerd rendement</h3>")
    if people_met_gerealiseerd:
        body.append(
            '<p class="lede">Naast de doorrekening op basis van deze scenarioset '
            "volgt dit ook het <b>gerealiseerde</b> rendement sinds de "
            "invaardatum: voor ieder verstreken kalenderjaar wordt het historische "
            "rendement van de rendements- en beschermingsportefeuille genomen en met "
            "de lifecycle-gewichten van dat jaar gecombineerd, op dezelfde manier als "
            "de doorrekening hierboven — maar met een enkel, feitelijk pad in plaats "
            "van een waaier aan scenario's.</p>"
        )
        body.append(_gerealiseerde_portefeuille_table(bundle))
        body.append(
            _figure(
                charts.maatmens_gerealiseerd_rendement(current),
                "Cumulatieve vermogensgroei sinds de invaardatum van elke maatmens, "
                "op basis van het werkelijk gerealiseerde rendement.",
                _gerealiseerd_wealth_table(bundle),
                "Toon gerealiseerd vermogen per jaar",
            )
        )
    else:
        note = escape(bundle.gerealiseerd_note) or (
            "geen van de maatmensen heeft nog een verstreken jaar sinds de "
            "invaardatum, of de brondata kon niet worden opgehaald."
        )
        body.append(
            f'<p class="note">Gerealiseerd rendement kon niet getoond worden: '
            f"{note}.</p>"
        )

    body.append("</section>")
    return "".join(body)


def _colophon(current: ScenarioMetrics, previous: ScenarioMetrics | None) -> str:
    lines = [
        "<footer class='colophon'>",
        "<p><b>Verantwoording.</b> Rentes volgen DNB-formule (1) en zijn jaarlijks "
        "samengesteld. Aandelenrendementen en inflaties zijn enkelvoudige "
        "jaarrendementen <code>(S(t+1) − S(t)) / S(t)</code>; cumulatieve cijfers "
        "worden daarom met <code>Π(1 + r)</code> berekend, niet met "
        "<code>exp(Σ r)</code>. Standaardfouten volgen DNB-formule (3) en "
        "betrouwbaarheidsintervallen formule (4)–(5).</p>",
        "<p>Aandelenrendementen zijn bruto weergegeven, tenzij anders vermeld. Voor "
        "netto-rendementen hanteert DNB een kostenafslag van 20 bp. De φ-parameters "
        "in de set zijn door DNB al gladgestreken voor rentesprongen (formules "
        "16–18); daar is hier niets extra's op toegepast.</p>",
        f"<p>Huidige set: <code>{escape(current.source)}</code>"
        + (f" · vorige set: <code>{escape(previous.source)}</code>" if previous else "")
        + f" · rapport gegenereerd op {_dt.datetime.now():%d-%m-%Y %H:%M}.</p>",
        "</footer>",
    ]
    return "".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _coerce(bundle, reference=None, label=None) -> ScenarioMetrics | None:
    """Accept either a ScenarioMetrics bundle or a raw ScenarioSet."""
    if bundle is None or isinstance(bundle, ScenarioMetrics):
        return bundle
    logger.info("Computing metrics for %s", getattr(bundle, "source_path", bundle))
    return compute_metrics(bundle, label=label, reference=reference)


def build_html_report(
    current_set,
    previous_set=None,
    title: str | None = None,
) -> str:
    """Build the full HTML report for a scenario set.

    Parameters
    ----------
    current_set:
        A :class:`~dnb_p_set.metrics.ScenarioMetrics` bundle, or a
        :class:`~dnb_p_set.ScenarioSet` which will be reduced to one.
    previous_set:
        Optional bundle or scenario set for the previous quarter.  When given,
        every chart, tile and table gains a comparison layer.
    title:
        Report title.  Defaults to a title derived from the set labels.

    Returns
    -------
    str
        A complete, self-contained HTML document.
    """
    current = _coerce(current_set)
    previous = _coerce(previous_set, reference=current)

    if title is None:
        title = f"DNB {current.set_type}-set — {current.label}"
        if previous is not None:
            title += f" versus {previous.label}"

    sections = [("kern", "Kernbevindingen"), ("rente", "Rentetermijnstructuur")]
    body = [_headline_section(current, previous), _term_structure_section(current, previous)]

    series_specs = [
        (
            "equity",
            "aandelen",
            "Aandelenrendement",
            "De set bevat enkelvoudige jaarrendementen. Het meetkundig gemiddelde "
            "is de maatstaf die DNB kalibreert (circa 5,4 % bruto); het "
            "rekenkundig gemiddelde ligt daar ongeveer een halve variantie boven.",
        ),
        (
            "inflation_nl",
            "inflatie-nl",
            "Prijsinflatie Nederland",
            "De Nederlandse prijsinflatie bepaalt samen met de nominale curve de "
            "reële NL-rentetermijnstructuur en daarmee de koopkracht van "
            "toekomstige uitkeringen.",
        ),
        (
            "inflation_eu",
            "inflatie-eu",
            "Prijsinflatie Europa",
            "De Europese prijsinflatie hoort bij de reële EU-curve en wijkt "
            "doorgaans licht af van de Nederlandse.",
        ),
    ]
    for key, anchor, heading, lede in series_specs:
        if key not in current.series:
            continue
        sections.append((anchor, heading))
        body.append(_series_section(current, previous, key, anchor, heading, lede))

    liability = _liability_section(current, previous)
    if liability:
        sections.append(("verplichtingen", "Verplichtingenproxy"))
        body.append(liability)

    correlations = _correlation_section(current, previous)
    if correlations:
        sections.append(("correlaties", "Samenhang"))
        body.append(correlations)

    lifecycle = _lifecycle_section(current)
    if lifecycle:
        sections.append(("maatmens", "Maatmens en lifecycle"))
        body.append(lifecycle)

    return (
        "<!DOCTYPE html>\n<html lang='nl'>\n<head>\n"
        "<meta charset='utf-8'>\n"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        f"<title>{escape(title)}</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        + _masthead(current, previous, title)
        + '<div class="wrap">'
        + _toc(sections)
        + "".join(body)
        + _colophon(current, previous)
        + "</div>\n</body>\n</html>\n"
    )
