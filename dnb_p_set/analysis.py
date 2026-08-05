"""
Statistical analysis utilities for DNB scenario sets.

Functions in this module accept NumPy arrays as returned by
:meth:`~dnb_p_set.ScenarioSet.get` and return standard Python / pandas
objects for easy downstream use.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import DEFAULT_PERCENTILES


def _log_growth(arr: np.ndarray, log_returns: bool) -> np.ndarray:
    """Return per-period log growth rates from *arr*."""
    return np.asarray(arr, dtype=float) if log_returns else np.log1p(arr)


def cumulative_return(arr: np.ndarray, log_returns: bool = False) -> np.ndarray:
    """Convert per-period returns to a cumulative growth factor.

    The DNB CSV stores **simple** period returns
    :math:`r_t = (S_{t+1} - S_t) / S_t` for the equity and inflation blocks
    (DNB *Toelichting scenarioset*), so the cumulative factor at horizon
    :math:`T` is:

    .. math::

        F_T = \\prod_{t=1}^{T} (1 + r_t)

    Parameters
    ----------
    arr:
        2-D array ``(n_scenarios, n_periods)`` of per-period returns.
    log_returns:
        Set to *True* when *arr* holds log returns instead, in which case
        :math:`F_T = \\exp(\\sum_t r_t)` is used.

    Returns
    -------
    np.ndarray
        2-D array ``(n_scenarios, n_periods)`` of cumulative growth factors.
        Column ``t`` represents the cumulative factor after ``t+1`` periods.
    """
    return np.exp(np.cumsum(_log_growth(arr, log_returns), axis=1))


def annualised_return(arr: np.ndarray, log_returns: bool = False) -> np.ndarray:
    """Convert per-period returns to the annualised geometric return.

    Parameters
    ----------
    arr:
        2-D array ``(n_scenarios, n_periods)`` of per-period returns.
    log_returns:
        See :func:`cumulative_return`.

    Returns
    -------
    np.ndarray
        2-D array ``(n_scenarios, n_periods)`` of annualised returns.
        Column ``t`` gives the geometric annualised return over ``t+1`` years.
    """
    cumulative = np.cumsum(_log_growth(arr, log_returns), axis=1)
    n_years = np.arange(1, arr.shape[1] + 1, dtype=float)
    return np.expm1(cumulative / n_years)


def geometric_mean_return(arr: np.ndarray, log_returns: bool = False) -> float:
    """Geometric mean return per period across all scenarios and periods.

    For the DNB P-set equity block this reproduces the calibration target
    quoted by DNB (roughly 5.4 % gross / 5.2 % net of the 20 bp cost load).

    Parameters
    ----------
    arr:
        2-D array ``(n_scenarios, n_periods)`` of per-period returns.
    log_returns:
        See :func:`cumulative_return`.

    Returns
    -------
    float
    """
    return float(np.expm1(_log_growth(arr, log_returns).mean()))


def standard_error(values: np.ndarray, axis: int = 0) -> np.ndarray:
    """Monte-Carlo standard error of a mean estimate (DNB formula 3).

    .. math::

        SE_N = \\sqrt{\\frac{\\overline{x^2} - \\bar{x}^2}{N}}

    Parameters
    ----------
    values:
        Array of realisations; the reduction runs over *axis*.
    axis:
        Axis holding the scenarios.

    Returns
    -------
    np.ndarray
        Standard errors with *axis* removed.
    """
    values = np.asarray(values, dtype=float)
    n = values.shape[axis]
    mean = values.mean(axis=axis)
    mean_sq = (values ** 2).mean(axis=axis)
    variance = np.maximum(mean_sq - mean ** 2, 0.0)
    return np.sqrt(variance / n)


def mean_confidence_interval(
    values: np.ndarray,
    alpha: float = 95.0,
    axis: int = 0,
) -> tuple:
    """Confidence interval around a mean estimate (DNB formulas 4–5).

    Parameters
    ----------
    values:
        Array of realisations.
    alpha:
        Confidence level in percent (default 95, giving ±1.96 SE).
    axis:
        Axis holding the scenarios.

    Returns
    -------
    tuple
        ``(mean, lower, upper)`` arrays.
    """
    if not 0 < alpha < 100:
        raise ValueError(f"alpha must be in (0, 100), got {alpha}")
    from scipy.stats import norm

    values = np.asarray(values, dtype=float)
    mean = values.mean(axis=axis)
    se = standard_error(values, axis=axis)
    z = norm.ppf(0.5 + alpha / 200.0)
    return mean, mean - z * se, mean + z * se


def percentile_confidence_interval(
    values: np.ndarray,
    p: float,
    alpha: float = 95.0,
) -> tuple:
    """Confidence interval around a percentile estimate (DNB formulas 6–7).

    The interval is read off the order statistics at rank
    :math:`Np \\pm z\\sqrt{Np(1-p)}`.

    Parameters
    ----------
    values:
        1-D array of realisations.
    p:
        Percentile in percent (0–100).
    alpha:
        Confidence level in percent.

    Returns
    -------
    tuple
        ``(estimate, lower, upper)`` floats.
    """
    if not 0 < p < 100:
        raise ValueError(f"p must be in (0, 100), got {p}")
    from scipy.stats import norm

    values = np.sort(np.asarray(values, dtype=float).ravel())
    n = values.size
    frac = p / 100.0
    z = norm.ppf(0.5 + alpha / 200.0)
    spread = z * np.sqrt(n * frac * (1.0 - frac))

    def _at(rank: float) -> float:
        idx = int(np.clip(round(rank), 1, n)) - 1
        return float(values[idx])

    return _at(n * frac), _at(n * frac - spread), _at(n * frac + spread)


def describe_variable(
    arr: np.ndarray,
    percentiles: list[float] | None = None,
) -> pd.DataFrame:
    """Compute descriptive statistics per time step.

    Parameters
    ----------
    arr:
        2-D array ``(n_scenarios, n_time_steps)``.
    percentiles:
        Percentiles (0–100) to include.  Defaults to
        :data:`~dnb_p_set.constants.DEFAULT_PERCENTILES`.

    Returns
    -------
    pd.DataFrame
        Index is time step ``t``; columns: ``mean``, ``std``, ``min``,
        ``max``, and one column per percentile ``p<value>``.
    """
    if percentiles is None:
        percentiles = DEFAULT_PERCENTILES

    t_index = pd.Index(range(arr.shape[1]), name="t")
    data: dict[str, np.ndarray] = {
        "mean": arr.mean(axis=0),
        "std": arr.std(axis=0, ddof=1),
        "min": arr.min(axis=0),
        "max": arr.max(axis=0),
    }
    for p in percentiles:
        data[f"p{p:g}"] = np.percentile(arr, p, axis=0)
    return pd.DataFrame(data, index=t_index)


def probability_exceeds(arr: np.ndarray, threshold: float) -> np.ndarray:
    """Estimate the probability of exceeding *threshold* at each time step.

    Parameters
    ----------
    arr:
        2-D array ``(n_scenarios, n_time_steps)``.
    threshold:
        Value to compare against.

    Returns
    -------
    np.ndarray
        1-D array of probabilities, length ``n_time_steps``.
    """
    return (arr > threshold).mean(axis=0)


def probability_below(arr: np.ndarray, threshold: float) -> np.ndarray:
    """Estimate the probability of being below *threshold* at each time step.

    Parameters
    ----------
    arr:
        2-D array ``(n_scenarios, n_time_steps)``.
    threshold:
        Value to compare against.

    Returns
    -------
    np.ndarray
        1-D array of probabilities, length ``n_time_steps``.
    """
    return (arr < threshold).mean(axis=0)


def value_at_risk(
    arr: np.ndarray,
    confidence: float = 0.95,
) -> np.ndarray:
    """Compute Value-at-Risk (VaR) at *confidence* level for each time step.

    The VaR is reported as a *loss* (positive number means a loss), so the
    function returns the ``-(1-confidence)``-quantile of the return
    distribution.

    Parameters
    ----------
    arr:
        2-D array ``(n_scenarios, n_time_steps)`` of returns.
    confidence:
        Confidence level between 0 and 1.

    Returns
    -------
    np.ndarray
        1-D array of VaR values, length ``n_time_steps``.
    """
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    return -np.percentile(arr, (1 - confidence) * 100, axis=0)


def expected_shortfall(
    arr: np.ndarray,
    confidence: float = 0.95,
) -> np.ndarray:
    """Compute Expected Shortfall (CVaR) at *confidence* level per time step.

    Parameters
    ----------
    arr:
        2-D array ``(n_scenarios, n_time_steps)`` of returns.
    confidence:
        Confidence level between 0 and 1.

    Returns
    -------
    np.ndarray
        1-D array of ES values, length ``n_time_steps``.
    """
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    threshold = np.percentile(arr, (1 - confidence) * 100, axis=0)
    es = np.zeros(arr.shape[1])
    for t_idx in range(arr.shape[1]):
        col = arr[:, t_idx]
        below = col[col <= threshold[t_idx]]
        es[t_idx] = -below.mean() if len(below) > 0 else -threshold[t_idx]
    return es


def correlation_matrix(
    arrays: dict[str, np.ndarray],
    t: int,
) -> pd.DataFrame:
    """Compute the cross-variable correlation matrix at time step *t*.

    Parameters
    ----------
    arrays:
        Mapping from variable name to 2-D array ``(n_scenarios, n_time_steps)``.
    t:
        0-based time-step index.

    Returns
    -------
    pd.DataFrame
        Square correlation matrix with variable names as index and columns.
    """
    names = list(arrays.keys())
    columns = {name: arrays[name][:, t] for name in names}
    df = pd.DataFrame(columns)
    return df.corr()


def distribution_stats(
    values: np.ndarray,
    percentiles: list[float] | None = None,
) -> dict[str, float]:
    """Summarise a 1-D sample: moments, percentiles and tail risk.

    Parameters
    ----------
    values:
        1-D array of realisations (e.g. the cross-section of one time step).
    percentiles:
        Percentiles (0–100) to include.  Defaults to
        :data:`~dnb_p_set.constants.DEFAULT_PERCENTILES`.

    Returns
    -------
    dict[str, float]
        Keys: ``mean``, ``se`` (standard error of the mean), ``std``,
        ``skew``, ``kurtosis`` (excess), ``min``, ``max``, ``p<value>``,
        ``var95`` and ``es95``.
    """
    from scipy.stats import kurtosis as _kurtosis, skew as _skew

    if percentiles is None:
        percentiles = DEFAULT_PERCENTILES

    values = np.asarray(values, dtype=float).ravel()
    tail = np.percentile(values, 5.0)
    stats: dict[str, float] = {
        "mean": float(values.mean()),
        "se": float(standard_error(values)),
        "std": float(values.std(ddof=1)),
        "skew": float(_skew(values)),
        "kurtosis": float(_kurtosis(values)),
        "min": float(values.min()),
        "max": float(values.max()),
        "var95": float(-tail),
        "es95": float(-values[values <= tail].mean()),
    }
    for p in percentiles:
        stats[f"p{p:g}"] = float(np.percentile(values, p))
    return stats


def histogram(
    values: np.ndarray,
    bins: int = 120,
    clip_percentiles: tuple = (0.1, 99.9),
    edges: np.ndarray | None = None,
) -> tuple:
    """Compute a density histogram, robust to extreme outliers.

    Parameters
    ----------
    values:
        1-D array of realisations.
    bins:
        Number of bins (ignored when *edges* is given).
    clip_percentiles:
        Percentile range used to place the bin edges, so a handful of
        extreme scenarios cannot flatten the whole picture.
    edges:
        Pre-computed bin edges.  Pass the edges of a reference set to make
        two histograms directly comparable.

    Returns
    -------
    tuple
        ``(edges, density)`` where ``density`` has ``len(edges) - 1``
        entries and integrates to 1 over the plotted range.
    """
    values = np.asarray(values, dtype=float).ravel()
    if edges is None:
        lo, hi = np.percentile(values, list(clip_percentiles))
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            lo, hi = float(values.min()), float(values.max())
        if hi <= lo:  # degenerate (constant) sample
            hi = lo + 1.0
        edges = np.linspace(lo, hi, bins + 1)
    density, edges = np.histogram(values, bins=edges, density=True)
    return edges, density
