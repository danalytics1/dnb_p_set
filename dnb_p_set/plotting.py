"""
Visualisation utilities for DNB scenario sets.

These are the generic, array-level helpers: every function takes a NumPy
array or DataFrame and returns the ``(fig, ax)`` tuple so callers can
customise the output further.

For the charts used by the HTML report — which take
:class:`~dnb_p_set.metrics.ScenarioMetrics` bundles and overlay two scenario
sets — see :mod:`dnb_p_set.charts`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import matplotlib.figure
    import matplotlib.axes

from .constants import DEFAULT_PERCENTILES, BLOCKS

_FILL_ALPHA = 0.15
_LINE_WIDTH = 1.5


def _get_mpl():
    """Lazy import of matplotlib to allow the package to be imported without it."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.figure
        return plt
    except ImportError as exc:
        raise ImportError(
            "matplotlib is required for plotting. "
            "Install it with: pip install matplotlib"
        ) from exc


def plot_fan_chart(
    arr: np.ndarray,
    title: str = "",
    ylabel: str = "Value",
    xlabel: str = "Year (t)",
    percentiles: list[float] | None = None,
    n_sample_paths: int = 5,
    sample_seed: int = 42,
    figsize: tuple[float, float] = (10, 5),
) -> tuple:
    """Plot a fan chart with percentile bands and sample paths.

    Parameters
    ----------
    arr:
        2-D array ``(n_scenarios, n_time_steps)``.
    title:
        Plot title.
    ylabel:
        Y-axis label.
    xlabel:
        X-axis label.
    percentiles:
        Outer and inner percentiles for the fan.  Defaults to
        ``[5, 10, 25, 50, 75, 90, 95]``.
    n_sample_paths:
        Number of individual scenario paths to overlay.
    sample_seed:
        Random seed for reproducible path selection.
    figsize:
        Figure size ``(width, height)`` in inches.

    Returns
    -------
    tuple
        ``(fig, ax)`` matplotlib objects.
    """
    plt = _get_mpl()

    if percentiles is None:
        percentiles = DEFAULT_PERCENTILES

    t_axis = np.arange(arr.shape[1])
    pct_data = {p: np.percentile(arr, p, axis=0) for p in percentiles}
    mean_path = arr.mean(axis=0)

    fig, ax = plt.subplots(figsize=figsize)

    # Fan bands (pairs from outside in)
    sorted_pcts = sorted(percentiles)
    n = len(sorted_pcts)
    mid = n // 2
    pairs = list(zip(sorted_pcts[:mid], sorted_pcts[n - mid:][::-1]))

    base_color = "#1f77b4"
    for i, (lo, hi) in enumerate(pairs):
        alpha = _FILL_ALPHA + i * 0.05
        ax.fill_between(
            t_axis,
            pct_data[lo],
            pct_data[hi],
            color=base_color,
            alpha=alpha,
            label=f"p{lo:g}–p{hi:g}",
        )

    # Median
    if 50.0 in pct_data:
        ax.plot(t_axis, pct_data[50.0], color=base_color, lw=_LINE_WIDTH + 0.5,
                label="median (p50)")

    # Mean
    ax.plot(t_axis, mean_path, color="black", lw=_LINE_WIDTH, ls="--", label="mean")

    # Sample paths
    if n_sample_paths > 0 and arr.shape[0] >= n_sample_paths:
        rng = np.random.default_rng(sample_seed)
        idxs = rng.choice(arr.shape[0], size=n_sample_paths, replace=False)
        for idx in idxs:
            ax.plot(t_axis, arr[idx], color="grey", lw=0.5, alpha=0.5)

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    return fig, ax


def plot_yield_curve(
    yield_df,
    t: int,
    title: str | None = None,
    figsize: tuple[float, float] = (8, 5),
    percentiles: list[float] | None = None,
) -> tuple:
    """Plot the yield curve (mean + fan) at time step *t*.

    Parameters
    ----------
    yield_df:
        DataFrame as returned by :meth:`~dnb_p_set.ScenarioSet.yield_curve`;
        index = scenarios, columns = maturities.
    t:
        Time step label for the title.
    title:
        Custom title.  Defaults to ``"Yield curve at t=<t>"``.
    figsize:
        Figure size.
    percentiles:
        Percentile bands to show.

    Returns
    -------
    tuple
        ``(fig, ax)`` matplotlib objects.
    """
    plt = _get_mpl()

    if percentiles is None:
        percentiles = [5.0, 25.0, 75.0, 95.0]

    maturities = yield_df.columns.tolist()
    arr = yield_df.to_numpy()

    fig, ax = plt.subplots(figsize=figsize)

    sorted_pcts = sorted(percentiles)
    n = len(sorted_pcts)
    mid = n // 2
    pairs = list(zip(sorted_pcts[:mid], sorted_pcts[n - mid:][::-1]))

    base_color = "#2ca02c"
    for lo, hi in pairs:
        ax.fill_between(
            maturities,
            np.percentile(arr, lo, axis=0),
            np.percentile(arr, hi, axis=0),
            color=base_color,
            alpha=_FILL_ALPHA,
            label=f"p{lo:g}–p{hi:g}",
        )

    ax.plot(maturities, arr.mean(axis=0), color=base_color, lw=_LINE_WIDTH + 0.5,
            label="mean")
    ax.plot(maturities, np.percentile(arr, 50, axis=0), color=base_color,
            lw=_LINE_WIDTH, ls="--", label="median")

    ax.set_title(title or f"Yield curve at t={t}")
    ax.set_xlabel("Maturity (years)")
    ax.set_ylabel("Yield")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig, ax


def plot_histogram(
    arr: np.ndarray,
    t: int,
    title: str = "",
    xlabel: str = "Value",
    bins: int = 100,
    figsize: tuple[float, float] = (8, 4),
) -> tuple:
    """Plot the cross-sectional histogram of *arr* at time step *t*.

    Parameters
    ----------
    arr:
        2-D array ``(n_scenarios, n_time_steps)``.
    t:
        0-based time-step index.
    title:
        Plot title.
    xlabel:
        X-axis label.
    bins:
        Number of histogram bins.
    figsize:
        Figure size.

    Returns
    -------
    tuple
        ``(fig, ax)`` matplotlib objects.
    """
    plt = _get_mpl()

    fig, ax = plt.subplots(figsize=figsize)
    ax.hist(arr[:, t], bins=bins, color="#1f77b4", edgecolor="none", alpha=0.8)
    ax.axvline(arr[:, t].mean(), color="black", lw=1.5, ls="--", label="mean")
    ax.axvline(np.median(arr[:, t]), color="red", lw=1.5, ls=":", label="median")
    ax.set_title(title or f"Distribution at t={t}")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Count")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig, ax


def plot_correlation_heatmap(
    corr_df,
    title: str = "Cross-variable correlation",
    figsize: tuple[float, float] = (8, 6),
) -> tuple:
    """Plot a correlation matrix heatmap.

    Parameters
    ----------
    corr_df:
        Square :class:`pandas.DataFrame` as returned by
        :func:`~dnb_p_set.analysis.correlation_matrix`.
    title:
        Plot title.
    figsize:
        Figure size.

    Returns
    -------
    tuple
        ``(fig, ax)`` matplotlib objects.
    """
    plt = _get_mpl()

    fig, ax = plt.subplots(figsize=figsize)
    mat = corr_df.to_numpy()
    im = ax.imshow(mat, vmin=-1, vmax=1, cmap="RdBu_r")
    plt.colorbar(im, ax=ax)

    labels = list(corr_df.columns)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(labels, fontsize=8)

    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=7)

    ax.set_title(title)
    fig.tight_layout()
    return fig, ax