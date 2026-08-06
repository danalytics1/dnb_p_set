"""
Term-structure (rentetermijnstructuur) mathematics for DNB scenario sets.

The DNB scenario sets do not ship full yield curves; they ship the affine
term-structure parameters :math:`\\phi` and :math:`\\Psi` together with the
three state variables :math:`X_1, X_2, X_3`.  The annually compounded
zero-coupon rate for maturity :math:`\\tau` in projection year :math:`t` is
(DNB *Toelichting scenarioset*, formula 1):

.. math::

    y(\\tau, t) = \\exp\\!\\left[
        -\\frac{1}{\\tau}\\Big(
            \\phi(\\tau, t)
            + \\Psi(\\tau, 1) X_1(t)
            + \\Psi(\\tau, 2) X_2(t)
            + \\Psi(\\tau, 3) X_3(t)
        \\Big)
    \\right] - 1

Note that the bracketed term is the log discount factor, so the zero-coupon
bond price follows directly as
:math:`P(\\tau, t) = \\exp\\!\\big(\\phi(\\tau,t) + \\Psi(\\tau,\\cdot) X(t)\\big)`.

Functions in this module are pure NumPy and take the raw blocks, so they can
be unit-tested without loading a full scenario set.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "log_discount_factor",
    "discount_factor",
    "zero_rates",
    "forward_rates",
    "annuity_pv",
    "macaulay_duration",
    "breakeven_inflation",
]


def _as_maturity_index(maturities: np.ndarray, n_tau: int) -> np.ndarray:
    """Validate *maturities* (in years, 1-based) and return 0-based indices."""
    tau = np.asarray(maturities, dtype=int)
    if tau.ndim != 1 or tau.size == 0:
        raise ValueError("maturities must be a non-empty 1-D sequence")
    if tau.min() < 1 or tau.max() > n_tau:
        raise ValueError(
            f"maturities must lie in [1, {n_tau}], got "
            f"[{tau.min()}, {tau.max()}]"
        )
    return tau - 1


def log_discount_factor(
    phi: np.ndarray,
    psi: np.ndarray,
    states: np.ndarray,
    t: int,
    maturities: np.ndarray,
) -> np.ndarray:
    """Return :math:`\\log P(\\tau, t)` for every scenario and maturity.

    Parameters
    ----------
    phi:
        Block ``(n_tau, n_timesteps)`` of :math:`\\phi` parameters; row
        ``i`` corresponds to maturity ``i + 1``.
    psi:
        Block ``(n_tau, 3)`` of :math:`\\Psi` parameters.
    states:
        Array ``(n_scenarios, 3, n_timesteps)`` or ``(n_scenarios, 3)`` of
        state variables.  When 3-D, time step *t* is selected.
    t:
        0-based projection year.
    maturities:
        Maturities in years (1-based, i.e. ``1`` is the one-year point).

    Returns
    -------
    np.ndarray
        Array ``(n_scenarios, n_maturities)``.
    """
    phi = np.asarray(phi, dtype=float)
    psi = np.asarray(psi, dtype=float)
    states = np.asarray(states, dtype=float)

    if psi.shape[1] != 3:
        raise ValueError(f"psi must have 3 columns, got {psi.shape[1]}")
    if phi.shape[0] != psi.shape[0]:
        raise ValueError(
            f"phi and psi must describe the same maturities, got "
            f"{phi.shape[0]} and {psi.shape[0]}"
        )

    if states.ndim == 3:
        x = states[:, :, t]
    elif states.ndim == 2:
        x = states
    else:
        raise ValueError("states must be 2-D or 3-D")
    if x.shape[1] != 3:
        raise ValueError(f"states must have 3 state variables, got {x.shape[1]}")

    tau_idx = _as_maturity_index(maturities, phi.shape[0])

    # phi(tau, t): (n_maturities,) ; psi @ x: (n_scenarios, n_maturities)
    return phi[tau_idx, t][None, :] + x @ psi[tau_idx].T


def discount_factor(
    phi: np.ndarray,
    psi: np.ndarray,
    states: np.ndarray,
    t: int,
    maturities: np.ndarray,
) -> np.ndarray:
    """Zero-coupon bond price :math:`P(\\tau, t)` per scenario and maturity."""
    return np.exp(log_discount_factor(phi, psi, states, t, maturities))


def zero_rates(
    phi: np.ndarray,
    psi: np.ndarray,
    states: np.ndarray,
    t: int,
    maturities: np.ndarray,
    compounding: str = "annual",
) -> np.ndarray:
    """Zero-coupon rates following DNB formula (1).

    Parameters
    ----------
    phi, psi, states, t, maturities:
        See :func:`log_discount_factor`.
    compounding:
        ``"annual"`` (default, the DNB convention) returns
        :math:`\\exp(-A/\\tau) - 1`.  ``"continuous"`` returns
        :math:`-A/\\tau`, which is roughly 3–5 bp lower.

    Returns
    -------
    np.ndarray
        Array ``(n_scenarios, n_maturities)`` of zero rates as decimals.
    """
    tau = np.asarray(maturities, dtype=float)
    log_p = log_discount_factor(phi, psi, states, t, maturities)
    cc = -log_p / tau[None, :]
    if compounding == "continuous":
        return cc
    if compounding == "annual":
        return np.expm1(cc)
    raise ValueError(
        f"compounding must be 'annual' or 'continuous', got '{compounding}'"
    )


def forward_rates(
    phi: np.ndarray,
    psi: np.ndarray,
    states: np.ndarray,
    t: int,
    maturities: np.ndarray,
) -> np.ndarray:
    """One-year forward rates implied by the zero curve.

    The forward covering year :math:`[\\tau-1, \\tau]` is
    :math:`P(\\tau-1)/P(\\tau) - 1`.  Maturity ``1`` uses :math:`P(0) = 1`.

    Returns
    -------
    np.ndarray
        Array ``(n_scenarios, n_maturities)``.
    """
    tau = np.asarray(maturities, dtype=int)
    log_p = log_discount_factor(phi, psi, states, t, tau)

    prev = np.where(tau > 1, tau - 1, 1)
    log_p_prev = log_discount_factor(phi, psi, states, t, prev)
    # P(0) = 1 -> log P(0) = 0
    log_p_prev = np.where(tau[None, :] > 1, log_p_prev, 0.0)

    return np.expm1(log_p_prev - log_p)


def annuity_pv(
    phi: np.ndarray,
    psi: np.ndarray,
    states: np.ndarray,
    t: int,
    cashflows: np.ndarray,
) -> np.ndarray:
    """Present value of a deterministic cashflow stream on the zero curve.

    Parameters
    ----------
    phi, psi, states, t:
        See :func:`log_discount_factor`.
    cashflows:
        1-D array of cashflows paid at :math:`\\tau = 1, 2, \\ldots, n`.

    Returns
    -------
    np.ndarray
        1-D array of present values, one per scenario.
    """
    cf = np.asarray(cashflows, dtype=float)
    maturities = np.arange(1, cf.size + 1)
    p = discount_factor(phi, psi, states, t, maturities)
    return p @ cf


def macaulay_duration(
    phi: np.ndarray,
    psi: np.ndarray,
    states: np.ndarray,
    t: int,
    cashflows: np.ndarray,
) -> np.ndarray:
    """Macaulay duration (in years) of *cashflows* on the zero curve."""
    cf = np.asarray(cashflows, dtype=float)
    maturities = np.arange(1, cf.size + 1)
    p = discount_factor(phi, psi, states, t, maturities)
    weighted = p * cf[None, :]
    return (weighted @ maturities.astype(float)) / weighted.sum(axis=1)


def breakeven_inflation(
    nominal_rates: np.ndarray,
    real_rates: np.ndarray,
) -> np.ndarray:
    """Break-even inflation implied by a nominal and a real curve.

    Uses the exact Fisher relation
    :math:`(1 + y_{nom}) / (1 + y_{real}) - 1` rather than the linear
    approximation.
    """
    return (1.0 + np.asarray(nominal_rates)) / (1.0 + np.asarray(real_rates)) - 1.0
