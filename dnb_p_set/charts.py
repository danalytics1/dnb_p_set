"""
Report charts for DNB scenario sets.

Every function here takes one or two :class:`~dnb_p_set.metrics.ScenarioMetrics`
bundles — never the raw arrays — and returns a :class:`matplotlib.figure.Figure`.
The *current* set is always drawn in blue and the *previous* set in orange, so
identity is consistent across the whole report; when a previous set is not
supplied the comparison layer is simply omitted.

For array-level plotting helpers see :mod:`dnb_p_set.plotting`.
"""

from __future__ import annotations

import base64
import io

import numpy as np

from .constants import CURVE_HORIZONS, KEY_MATURITIES

__all__ = [
    "PALETTE",
    "figure_to_data_uri",
    "starting_curve",
    "curve_fan_grid",
    "rate_path_grid",
    "breakeven_curve",
    "return_histogram",
    "annualised_fan",
    "cumulative_fan",
    "annual_moments",
    "correlation_heatmap",
    "kpi_delta_bars",
]

#: Validated palette (see the project data-viz notes).  Slot 1 is the current
#: set, slot 2 the previous set; the blue ramp carries the percentile fan. 
PALETTE = {
    "current": "#2a78d6",
    "previous": "#eb6834",
    "accent": "#1baf7a",
    "fan": ["#cde2fb", "#9ec5f4", "#6da7ec"],
    "positive": "#2a78d6",
    "negative": "#d03b3b",
    "surface": "#fcfcfb",
    "ink": "#0b0b0b",
    "secondary": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "baseline": "#c3c2b7",
}

_BAND_PAIRS = [(5.0, 95.0), (10.0, 90.0), (25.0, 75.0)]


def _plt():
    """Lazy matplotlib import with a helpful error message."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "matplotlib is required to build report charts. "
            "Install it with: pip install matplotlib"
        ) from exc
    return plt


def _style_axes(ax, xlabel: str = "", ylabel: str = "", title: str = "") -> None:
    """Apply the recessive grid / hairline axis treatment used report-wide."""
    ax.set_facecolor(PALETTE["surface"])
    ax.grid(True, color=PALETTE["grid"], lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(PALETTE["baseline"])
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=PALETTE["muted"], labelsize=9, length=0)
    if xlabel:
        ax.set_xlabel(xlabel, color=PALETTE["secondary"], fontsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, color=PALETTE["secondary"], fontsize=9)
    if title:
        ax.set_title(title, color=PALETTE["ink"], fontsize=11, loc="left", pad=8)


def _new_figure(plt, figsize, nrows: int = 1, ncols: int = 1, **kwargs):
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, **kwargs)
    fig.patch.set_facecolor(PALETTE["surface"])
    return fig, axes


def _as_percent(ax, axis: str = "y", decimals: int = 1) -> None:
    from matplotlib.ticker import FuncFormatter

    fmt = FuncFormatter(lambda v, _: f"{v * 100:.{decimals}f}%")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def _legend(ax, **kwargs) -> None:
    legend = ax.legend(
        frameon=False, fontsize=8.5, labelcolor=PALETTE["secondary"], **kwargs
    )
    return legend


def _draw_fan(ax, x, frame, color_ramp=None, label_prefix: str = "") -> None:
    """Draw nested percentile bands plus the median line."""
    ramp = color_ramp or PALETTE["fan"]
    for (lo, hi), color in zip(_BAND_PAIRS, ramp):
        lo_col, hi_col = f"p{lo:g}", f"p{hi:g}"
        if lo_col not in frame or hi_col not in frame:
            continue
        ax.fill_between(
            x,
            frame[lo_col],
            frame[hi_col],
            color=color,
            lw=0,
            zorder=2,
            label=f"{label_prefix}p{lo:g}–p{hi:g}",
        )
    if "p50" in frame:
        ax.plot(
            x,
            frame["p50"],
            color=PALETTE["current"],
            lw=2.0,
            zorder=4,
            label=f"{label_prefix}mediaan",
        )


def figure_to_data_uri(fig, dpi: int = 130, fmt: str = "png") -> str:
    """Serialise *fig* to a self-contained ``data:`` URI and close it.

    Parameters
    ----------
    fig:
        The figure to render.
    dpi:
        Raster resolution; ignored for ``fmt="svg"``.
    fmt:
        ``"png"`` (default) or ``"svg"``.

    Returns
    -------
    str
        A ``data:image/…;base64,…`` string that can be dropped straight into
        an ``<img src=…>`` attribute.
    """
    buffer = io.BytesIO()
    fig.savefig(
        buffer,
        format=fmt,
        dpi=dpi,
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
    )
    _plt().close(fig)
    payload = base64.b64encode(buffer.getvalue()).decode("ascii")
    mime = "image/svg+xml" if fmt == "svg" else "image/png"
    return f"data:{mime};base64,{payload}"


# ---------------------------------------------------------------------------
# Term structure
# ---------------------------------------------------------------------------


def starting_curve(current, previous=None, key: str = "nominal"):
    """Starting (t = 0) term structure with the change versus the previous set.

    Parameters
    ----------
    current:
        :class:`~dnb_p_set.metrics.ScenarioMetrics` for the current set.
    previous:
        Optional bundle for the previous set.
    key:
        Curve key: ``"nominal"``, ``"real_eu"`` or ``"real_nl"``.

    Returns
    -------
    matplotlib.figure.Figure
    """
    plt = _plt()
    curve = current.curves[key]
    prev_curve = previous.curves[key] if previous is not None else None

    has_delta = prev_curve is not None
    heights = [3, 1] if has_delta else [1]
    fig, axes = _new_figure(
        plt,
        (9.5, 5.4 if has_delta else 4.2),
        nrows=2 if has_delta else 1,
        sharex=True,
        gridspec_kw={"height_ratios": heights, "hspace": 0.12},
    )
    axes = np.atleast_1d(axes)
    ax = axes[0]

    x = curve.spot.index.to_numpy()
    ax.plot(
        x,
        curve.spot.to_numpy(),
        color=PALETTE["current"],
        lw=2.2,
        marker="o",
        ms=4,
        label=current.label,
        zorder=4,
    )
    if prev_curve is not None:
        ax.plot(
            prev_curve.spot.index.to_numpy(),
            prev_curve.spot.to_numpy(),
            color=PALETTE["previous"],
            lw=2.0,
            ls="--",
            marker="o",
            ms=3.5,
            label=previous.label,
            zorder=3,
        )

    _style_axes(ax, ylabel="Zero-coupon rente", title=f"{curve.label} — startcurve (t=0)")
    _as_percent(ax, decimals=2)
    # Outside the axes: a curve can slope either way, so no in-plot corner is
    # reliably free.
    _legend(ax, loc="upper left", bbox_to_anchor=(1.01, 1.0))

    if has_delta:
        aligned = curve.spot.reindex(prev_curve.spot.index)
        delta_bp = (aligned - prev_curve.spot).dropna() * 10_000
        x_delta = delta_bp.index.to_numpy(dtype=float)
        y_delta = delta_bp.to_numpy()

        # Maturities are unevenly spaced, so a signed area reads better than
        # bars: no width has to be invented for the gaps.
        ax2 = axes[1]
        for sign, colour in ((1, PALETTE["positive"]), (-1, PALETTE["negative"])):
            ax2.fill_between(
                x_delta,
                0,
                y_delta,
                where=(y_delta * sign >= 0),
                interpolate=True,
                color=colour,
                alpha=0.35,
                lw=0,
                zorder=3,
            )
        ax2.plot(x_delta, y_delta, color=PALETTE["secondary"], lw=1.4, zorder=4)
        ax2.scatter(
            x_delta,
            y_delta,
            s=16,
            zorder=5,
            color=[
                PALETTE["positive"] if v >= 0 else PALETTE["negative"] for v in y_delta
            ],
        )
        ax2.axhline(0, color=PALETTE["baseline"], lw=1.0, zorder=2)
        _style_axes(ax2, xlabel="Looptijd (jaren)", ylabel="Δ in bp")
        ax2.set_xlim(ax.get_xlim())

    return fig


def curve_fan_grid(current, previous=None, key: str = "nominal", horizons=None):
    """Cross-sectional curve distribution at several projection years.

    Each panel shows the percentile fan of the current set with the previous
    set's median overlaid, so both the level and the spread are comparable.
    """
    plt = _plt()
    curve = current.curves[key]
    prev_curve = previous.curves[key] if previous is not None else None

    horizons = [
        h for h in (horizons or CURVE_HORIZONS) if h in curve.by_horizon
    ]
    if not horizons:
        raise ValueError("no projection years available for this curve")

    ncols = min(3, len(horizons))
    nrows = int(np.ceil(len(horizons) / ncols))
    fig, axes = _new_figure(
        plt, (4.4 * ncols, 3.2 * nrows), nrows=nrows, ncols=ncols, squeeze=False
    )
    flat = axes.ravel()

    for ax, h in zip(flat, horizons):
        frame = curve.by_horizon[h]
        x = frame.index.to_numpy()
        _draw_fan(ax, x, frame)
        ax.plot(
            x,
            frame["mean"],
            color=PALETTE["ink"],
            lw=1.2,
            ls=":",
            zorder=5,
            label="gemiddelde",
        )
        if prev_curve is not None and h in prev_curve.by_horizon:
            prev_frame = prev_curve.by_horizon[h]
            ax.plot(
                prev_frame.index.to_numpy(),
                prev_frame["p50"],
                color=PALETTE["previous"],
                lw=1.8,
                ls="--",
                zorder=6,
                label=f"mediaan {previous.label}",
            )
        label = "startcurve (t=0)" if h == 0 else f"projectiejaar {h}"
        _style_axes(ax, xlabel="Looptijd (jaren)", ylabel="Rente", title=label)
        _as_percent(ax, decimals=1)

    for ax in flat[len(horizons):]:
        ax.set_visible(False)

    handles, labels = flat[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        frameon=False,
        fontsize=8.5,
        labelcolor=PALETTE["secondary"],
        loc="lower center",
        ncol=min(6, len(labels)),
        bbox_to_anchor=(0.5, -0.04),
    )
    fig.suptitle(
        f"{curve.label} — verdeling over scenario's",
        color=PALETTE["ink"],
        fontsize=12,
        x=0.02,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    return fig


def rate_path_grid(current, previous=None, key: str = "nominal", maturities=None):
    """Percentile fan of key maturities over the whole projection horizon."""
    plt = _plt()
    curve = current.curves[key]
    prev_curve = previous.curves[key] if previous is not None else None

    maturities = [m for m in (maturities or KEY_MATURITIES) if m in curve.paths]
    if not maturities:
        raise ValueError("no key maturities available for this curve")

    ncols = min(2, len(maturities))
    nrows = int(np.ceil(len(maturities) / ncols))
    fig, axes = _new_figure(
        plt, (5.6 * ncols, 3.3 * nrows), nrows=nrows, ncols=ncols, squeeze=False
    )
    flat = axes.ravel()

    for ax, m in zip(flat, maturities):
        frame = curve.paths[m]
        x = frame.index.to_numpy()
        _draw_fan(ax, x, frame)
        if prev_curve is not None and m in prev_curve.paths:
            ax.plot(
                prev_curve.paths[m].index.to_numpy(),
                prev_curve.paths[m]["p50"],
                color=PALETTE["previous"],
                lw=1.8,
                ls="--",
                zorder=6,
                label=f"mediaan {previous.label}",
            )
        _style_axes(
            ax,
            xlabel="Projectiejaar",
            ylabel="Rente",
            title=f"{m}-jaarsrente",
        )
        _as_percent(ax, decimals=1)

    for ax in flat[len(maturities):]:
        ax.set_visible(False)

    handles, labels = flat[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        frameon=False,
        fontsize=8.5,
        labelcolor=PALETTE["secondary"],
        loc="lower center",
        ncol=min(6, len(labels)),
        bbox_to_anchor=(0.5, -0.03),
    )
    fig.suptitle(
        f"{curve.label} — ontwikkeling per looptijd",
        color=PALETTE["ink"],
        fontsize=12,
        x=0.02,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    return fig


def breakeven_curve(current, previous=None):
    """Break-even inflation implied by the nominal and real starting curves."""
    plt = _plt()
    fig, ax = _new_figure(plt, (9.5, 4.2))

    frame = current.breakeven
    x = frame.index.to_numpy()
    ax.plot(
        x,
        frame["bei_nl"].to_numpy(),
        color=PALETTE["current"],
        lw=2.2,
        marker="o",
        ms=4,
        label=f"NL — {current.label}",
        zorder=4,
    )
    ax.plot(
        x,
        frame["bei_eu"].to_numpy(),
        color=PALETTE["accent"],
        lw=2.0,
        marker="s",
        ms=3.5,
        label=f"EU — {current.label}",
        zorder=4,
    )
    if previous is not None and not previous.breakeven.empty:
        prev = previous.breakeven
        ax.plot(
            prev.index.to_numpy(),
            prev["bei_nl"].to_numpy(),
            color=PALETTE["current"],
            lw=1.6,
            ls="--",
            alpha=0.55,
            label=f"NL — {previous.label}",
            zorder=3,
        )
        ax.plot(
            prev.index.to_numpy(),
            prev["bei_eu"].to_numpy(),
            color=PALETTE["accent"],
            lw=1.6,
            ls="--",
            alpha=0.55,
            label=f"EU — {previous.label}",
            zorder=3,
        )

    _style_axes(
        ax,
        xlabel="Looptijd (jaren)",
        ylabel="Break-even inflatie",
        title="Impliciete break-even inflatie op de startcurve (t=0)",
    )
    _as_percent(ax, decimals=2)
    _legend(ax, loc="best", ncol=2)
    return fig


# ---------------------------------------------------------------------------
# Returns and inflation
# ---------------------------------------------------------------------------


def return_histogram(current, previous=None, key: str = "equity", horizon=None):
    """Cross-sectional distribution of a return, current versus previous.

    Parameters
    ----------
    current, previous:
        Metrics bundles.
    key:
        Series key (``"equity"``, ``"inflation_nl"``, ``"inflation_eu"``).
    horizon:
        When *None*, plot the one-year return in projection year 1.  Otherwise
        plot the annualised return over *horizon* years.
    """
    plt = _plt()
    series = current.series[key]

    if horizon is None:
        edges, density = series.hist_year1
        subtitle = "1-jaarsrendement, projectiejaar 1"
    else:
        edges, density = series.hist_annualised[horizon]
        subtitle = f"geannualiseerd rendement over {horizon} jaar"

    fig, ax = _new_figure(plt, (9.5, 4.2))
    centres = 0.5 * (edges[:-1] + edges[1:])

    ax.fill_between(
        centres,
        density,
        color=PALETTE["fan"][1],
        lw=0,
        zorder=2,
        label=f"{current.label}",
    )
    ax.plot(centres, density, color=PALETTE["current"], lw=1.8, zorder=4)

    if previous is not None and key in previous.series:
        prev_series = previous.series[key]
        prev = (
            prev_series.hist_year1
            if horizon is None
            else prev_series.hist_annualised.get(horizon)
        )
        if prev is not None:
            prev_centres = 0.5 * (prev[0][:-1] + prev[0][1:])
            ax.plot(
                prev_centres,
                prev[1],
                color=PALETTE["previous"],
                lw=1.8,
                ls="--",
                zorder=5,
                label=f"{previous.label}",
            )

    source = series.annual.loc[1] if horizon is None else series.annualised.loc[horizon]
    ax.axvline(
        source["mean"],
        color=PALETTE["ink"],
        lw=1.2,
        ls=":",
        zorder=6,
        label=f"gemiddelde {current.label} ({source['mean'] * 100:.2f}%)",
    )

    _style_axes(
        ax,
        xlabel="Rendement",
        ylabel="Kansdichtheid",
        title=f"{series.label} — {subtitle}",
    )
    _as_percent(ax, axis="x", decimals=0)
    _legend(ax, loc="upper right")
    return fig


def annualised_fan(current, previous=None, key: str = "equity"):
    """Percentile fan of the annualised return as the horizon lengthens."""
    plt = _plt()
    series = current.series[key]
    frame = series.annualised
    x = frame.index.to_numpy()

    fig, ax = _new_figure(plt, (9.5, 4.6))
    _draw_fan(ax, x, frame)
    ax.plot(
        x, frame["mean"], color=PALETTE["ink"], lw=1.3, ls=":", zorder=5,
        label="gemiddelde",
    )
    if previous is not None and key in previous.series:
        prev = previous.series[key].annualised
        ax.plot(
            prev.index.to_numpy(),
            prev["p50"],
            color=PALETTE["previous"],
            lw=1.8,
            ls="--",
            zorder=6,
            label=f"mediaan {previous.label}",
        )

    _style_axes(
        ax,
        xlabel="Horizon (jaren)",
        ylabel="Geannualiseerd rendement",
        title=f"{series.label} — geannualiseerd rendement per horizon",
    )
    _as_percent(ax, decimals=0)
    _legend(ax, loc="upper right", ncol=2)
    return fig


def cumulative_fan(current, previous=None, key: str = "equity"):
    """Percentile fan of the cumulative index (start = 1) on a log scale."""
    plt = _plt()
    series = current.series[key]
    frame = series.cumulative
    x = frame.index.to_numpy()

    fig, ax = _new_figure(plt, (9.5, 4.6))
    _draw_fan(ax, x, frame)
    if previous is not None and key in previous.series:
        prev = previous.series[key].cumulative
        ax.plot(
            prev.index.to_numpy(),
            prev["p50"],
            color=PALETTE["previous"],
            lw=1.8,
            ls="--",
            zorder=6,
            label=f"mediaan {previous.label}",
        )

    ax.set_yscale("log")
    _style_axes(
        ax,
        xlabel="Projectiejaar",
        ylabel="Cumulatieve index (start = 1, log-schaal)",
        title=f"{series.label} — cumulatieve ontwikkeling",
    )
    _legend(ax, loc="upper left", ncol=2)
    return fig


def annual_moments(current, previous=None, key: str = "equity"):
    """Mean and volatility of the one-year return per projection year.

    A flat pair of lines confirms the calibration is stationary; a drift
    between two sets shows up immediately as a vertical shift.
    """
    plt = _plt()
    series = current.series[key]
    fig, axes = _new_figure(plt, (10.5, 3.4), ncols=2)

    panels = [
        (axes[0], "mean", "Gemiddeld 1-jaarsrendement"),
        (axes[1], "std", "Volatiliteit 1-jaarsrendement"),
    ]
    for ax, column, title in panels:
        frame = series.annual
        ax.plot(
            frame.index.to_numpy(),
            frame[column].to_numpy(),
            color=PALETTE["current"],
            lw=1.8,
            label=current.label,
            zorder=4,
        )
        if previous is not None and key in previous.series:
            prev = previous.series[key].annual
            ax.plot(
                prev.index.to_numpy(),
                prev[column].to_numpy(),
                color=PALETTE["previous"],
                lw=1.6,
                ls="--",
                label=previous.label,
                zorder=3,
            )
        _style_axes(ax, xlabel="Projectiejaar", title=title)
        _as_percent(ax, decimals=1)
        _legend(ax, loc="best")

    fig.suptitle(
        f"{series.label} — stabiliteit over de projectie",
        color=PALETTE["ink"],
        fontsize=12,
        x=0.02,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return fig


# ---------------------------------------------------------------------------
# Cross-variable
# ---------------------------------------------------------------------------


def _diverging_cmap():
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(
        "dnb_diverging",
        [PALETTE["negative"], "#f0efec", PALETTE["positive"]],
    )


def correlation_heatmap(current, previous=None):
    """Year-1 correlation matrix, plus its change versus the previous set."""
    plt = _plt()
    matrix = current.correlations
    show_delta = (
        previous is not None
        and not previous.correlations.empty
        and list(previous.correlations.columns) == list(matrix.columns)
    )

    fig, axes = _new_figure(
        plt, (11.5 if show_delta else 6.0, 4.8), ncols=2 if show_delta else 1,
        squeeze=False,
    )
    flat = axes.ravel()
    labels = list(matrix.columns)

    def _draw(ax, values, vmax, title, fmt):
        image = ax.imshow(values, vmin=-vmax, vmax=vmax, cmap=_diverging_cmap())
        bar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        bar.outline.set_visible(False)
        bar.ax.tick_params(colors=PALETTE["muted"], labelsize=8, length=0)
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8.5)
        ax.set_yticklabels(labels, fontsize=8.5)
        ax.tick_params(colors=PALETTE["secondary"], length=0)
        ax.grid(False)
        for side in ax.spines.values():
            side.set_visible(False)
        for i in range(len(labels)):
            for j in range(len(labels)):
                value = values[i, j]
                shade = PALETTE["ink"] if abs(value) < 0.6 * vmax else "#ffffff"
                ax.text(
                    j, i, fmt.format(value), ha="center", va="center",
                    fontsize=8, color=shade,
                )
        ax.set_title(title, color=PALETTE["ink"], fontsize=11, loc="left", pad=8)

    _draw(flat[0], matrix.to_numpy(), 1.0, f"Correlaties {current.label}", "{:.2f}")

    if show_delta:
        delta = (matrix - previous.correlations).to_numpy()
        scale = max(0.02, float(np.abs(delta).max()))
        _draw(
            flat[1], delta, scale,
            f"Verschil t.o.v. {previous.label}", "{:+.3f}",
        )

    fig.tight_layout()
    return fig


#: Titles for the magnitude cohorts of :func:`kpi_delta_bars`.
_PANEL_TITLES = {
    "niveaus": "Niveaus — rentes, rendementen en inflatie",
    "risico": "Risicomaatstaven — volatiliteit en staartrisico",
}


def kpi_delta_bars(current, previous, keys=None):
    """Diverging bar chart of the change in every rate-like headline figure.

    Level changes run to a few basis points while tail-risk changes run to
    hundreds, so the figures are faceted by magnitude cohort — one panel per
    cohort, each on its own scale, rather than one panel on which the small
    changes would be invisible.
    """
    plt = _plt()

    cohorts: dict = {}
    for key, kpi in current.kpis.items():
        if keys is not None and key not in keys:
            continue
        if kpi.unit != "rate":
            continue
        prev_kpi = previous.kpis.get(key)
        if prev_kpi is None:
            continue
        cohorts.setdefault(kpi.panel, []).append(
            (kpi.label, (kpi.value - prev_kpi.value) * 10_000)
        )

    if not cohorts:
        raise ValueError("no comparable rate figures between the two sets")

    order = [p for p in _PANEL_TITLES if p in cohorts] + [
        p for p in cohorts if p not in _PANEL_TITLES
    ]
    for rows in cohorts.values():
        rows.sort(key=lambda item: item[1])

    counts = [len(cohorts[p]) for p in order]
    fig, axes = _new_figure(
        plt,
        (9.5, 0.38 * sum(counts) + 1.15 * len(order)),
        nrows=len(order),
        squeeze=False,
        layout="constrained",
        gridspec_kw={"height_ratios": counts},
    )
    flat = axes.ravel()

    for ax, panel in zip(flat, order):
        rows = cohorts[panel]
        labels = [row[0] for row in rows]
        values = [row[1] for row in rows]
        colors = [
            PALETTE["positive"] if v >= 0 else PALETTE["negative"] for v in values
        ]
        ax.barh(range(len(rows)), values, color=colors, height=0.62, zorder=3)
        ax.axvline(0, color=PALETTE["baseline"], lw=1.0, zorder=2)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels(labels, fontsize=9)
        ax.set_ylim(-0.7, len(rows) - 0.3)

        span = max(max(abs(v) for v in values), 1.0)
        for i, value in enumerate(values):
            offset = span * 0.02
            ax.text(
                value + (offset if value >= 0 else -offset),
                i,
                f"{value:+.1f}",
                va="center",
                ha="left" if value >= 0 else "right",
                fontsize=8.5,
                color=PALETTE["secondary"],
            )
        ax.set_xlim(-span * 1.3, span * 1.3)
        _style_axes(
            ax,
            xlabel="Verandering in basispunten",
            title=_PANEL_TITLES.get(panel, panel),
        )
        ax.tick_params(axis="y", colors=PALETTE["secondary"])

    fig.suptitle(
        f"Kernmaatstaven: {current.label} minus {previous.label}",
        color=PALETTE["ink"],
        fontsize=12,
    )
    return fig
