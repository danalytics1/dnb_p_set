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


def cumulative_return(arr: np.ndarray) -> np.ndarray:
    """Convert per-period log returns to cumulative factor.

    The DNB CSV stores period-by-period log returns :math:`r_t`.  The
    cumulative return factor at horizon :math:`T` is:

    .. math::

        F_T = \\exp\\!\\left(\\sum_{t=1}^{T} r_t\\right)

    Parameters
    ----------
    arr:
        2-D array ``(n_scenarios, n_periods)`` of per-period log returns.

    Returns
    -------
    np.ndarray
        2-D array ``(n_scenarios, n_periods)`` of cumulative return factors.
        Column ``t`` represents the cumulative factor after ``t+1`` periods.
    """
    return np.exp(np.cumsum(arr, axis=1))


def annualised_return(arr: np.ndarray) -> np.ndarray:
    """Convert per-period log returns to annualised geometric return.

    Parameters
    ----------
    arr:
        2-D array ``(n_scenarios, n_periods)`` of per-period log returns.

    Returns
    -------
    np.ndarray
        2-D array ``(n_scenarios, n_periods)`` of annualised returns.
        Column ``t`` gives the geometric annualised return over ``t+1`` years.
    """
    cumulative = np.cumsum(arr, axis=1)
    n_years = np.arange(1, arr.shape[1] + 1, dtype=float)
    return np.exp(cumulative / n_years) - 1.0


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
