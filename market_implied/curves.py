"""
Term structures and zero-coupon curves for market-implied return expectations.

Everything in this module is expressed with **annual compounding** and in
**decimal** units (0.0325 == 3.25%), matching the convention used by DNB for
its scenario sets.

The zero curve is the single source of truth for the risk-free building block
(:mod:`market_implied.riskfree`) and for every duration-carry block, so it is
kept deliberately small, pure NumPy and unit-testable.

Interpolation
-------------
Interpolation is linear in the **log discount factor** (equivalently: piecewise
constant instantaneous forward rates).  This is the market standard for
interpolating zero curves because it guarantees strictly positive implied
forward rates and reproduces the input nodes exactly (Hagan & West, 2006,
*Interpolation methods for curve construction*, Applied Mathematical Finance
13(2), 89-129).

Beyond the last input tenor the curve is extrapolated with a **flat forward**
rate equal to the forward implied by the last two nodes; before the first node
the zero rate is held flat.
"""

from __future__ import annotations

from typing import Sequence, Union

import numpy as np

__all__ = ["TermStructure", "ZeroCurve"]

Number = Union[float, np.ndarray]


def _as_array(x) -> np.ndarray:
    return np.atleast_1d(np.asarray(x, dtype=float))


def _scalarise(result: np.ndarray, original) -> Number:
    """Return a Python float when the caller passed a scalar."""
    if np.isscalar(original) or (isinstance(original, np.ndarray) and original.ndim == 0):
        return float(result[0])
    return result


class TermStructure:
    """A maturity-indexed quantity with linear interpolation and flat wings.

    Used for inputs that are naturally a function of maturity but are not
    themselves a discount curve: term premia (Adrian, Crump & Moench, 2013),
    inflation risk premia, liquidity premia.

    Parameters
    ----------
    tenors:
        Strictly increasing maturities in years.
    values:
        Values (decimal) at those maturities.
    name:
        Free-form label used in reporting.

    Examples
    --------
    >>> tp = TermStructure([1, 10], [0.000, 0.010])
    >>> round(tp(5.5), 4)
    0.005
    """

    def __init__(
        self,
        tenors: Sequence[float],
        values: Sequence[float],
        name: str = "",
    ) -> None:
        t = np.asarray(tenors, dtype=float)
        v = np.asarray(values, dtype=float)
        if t.ndim != 1 or t.size == 0:
            raise ValueError("tenors must be a non-empty 1-D sequence")
        if v.shape != t.shape:
            raise ValueError("tenors and values must have the same shape")
        if np.any(np.diff(t) <= 0):
            raise ValueError("tenors must be strictly increasing")
        if np.any(t <= 0):
            raise ValueError("tenors must be strictly positive")
        self.tenors = t
        self.values = v
        self.name = name

    def __call__(self, maturity: Number) -> Number:
        m = _as_array(maturity)
        out = np.interp(m, self.tenors, self.values)
        return _scalarise(out, maturity)

    @classmethod
    def zero(cls, name: str = "") -> "TermStructure":
        """A term structure that is identically zero at every maturity."""
        return cls([1.0, 100.0], [0.0, 0.0], name=name or "zero")

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"TermStructure(name={self.name!r}, n_nodes={self.tenors.size})"


class ZeroCurve:
    """An annually compounded zero-coupon (spot) curve.

    Parameters
    ----------
    tenors:
        Strictly increasing maturities in years.
    zero_rates:
        Annually compounded zero rates, decimal.
    name:
        Free-form label, e.g. ``"EUR_nominal"``.

    Notes
    -----
    The discount factor is :math:`P(t) = (1 + z(t))^{-t}`, so the log discount
    factor at the input nodes is :math:`-t \\ln(1 + z(t))`.  Interpolation is
    linear in that quantity.
    """

    def __init__(
        self,
        tenors: Sequence[float],
        zero_rates: Sequence[float],
        name: str = "",
    ) -> None:
        t = np.asarray(tenors, dtype=float)
        z = np.asarray(zero_rates, dtype=float)
        if t.ndim != 1 or t.size < 2:
            raise ValueError("a zero curve needs at least two tenors")
        if z.shape != t.shape:
            raise ValueError("tenors and zero_rates must have the same shape")
        if np.any(np.diff(t) <= 0):
            raise ValueError("tenors must be strictly increasing")
        if np.any(t <= 0):
            raise ValueError("tenors must be strictly positive")
        if np.any(z <= -1.0):
            raise ValueError("zero rates must exceed -100%")

        self.tenors = t
        self.zero_rates = z
        self.name = name

        # Node grid for interpolation, anchored at t = 0 where ln P(0) = 0.
        self._grid_t = np.concatenate(([0.0], t))
        self._grid_lnp = np.concatenate(([0.0], -t * np.log1p(z)))
        # Instantaneous forward of the final segment, used for extrapolation.
        self._tail_slope = (self._grid_lnp[-1] - self._grid_lnp[-2]) / (
            self._grid_t[-1] - self._grid_t[-2]
        )

    # ------------------------------------------------------------------
    # Core curve access
    # ------------------------------------------------------------------
    def log_discount(self, maturity: Number) -> Number:
        """Return :math:`\\ln P(t)`, the log discount factor."""
        m = _as_array(maturity)
        if np.any(m < 0):
            raise ValueError("maturity must be non-negative")
        out = np.interp(m, self._grid_t, self._grid_lnp)
        tail = m > self._grid_t[-1]
        if np.any(tail):
            out[tail] = self._grid_lnp[-1] + self._tail_slope * (
                m[tail] - self._grid_t[-1]
            )
        return _scalarise(out, maturity)

    def discount(self, maturity: Number) -> Number:
        """Return the discount factor :math:`P(t)`."""
        return _scalarise(
            np.exp(_as_array(self.log_discount(maturity))), maturity
        )

    def zero(self, maturity: Number) -> Number:
        """Return the annually compounded zero rate :math:`z(t)`."""
        m = _as_array(maturity)
        if np.any(m <= 0):
            raise ValueError("maturity must be strictly positive for a zero rate")
        lnp = _as_array(self.log_discount(m))
        out = np.exp(-lnp / m) - 1.0
        return _scalarise(out, maturity)

    def forward_zero(self, start: float, tenor: float) -> float:
        """Return the *tenor*-year zero rate, *start* years forward.

        This is the rate the market implies today for a zero-coupon bond
        bought at ``start`` and maturing at ``start + tenor``.
        """
        if tenor <= 0:
            raise ValueError("tenor must be strictly positive")
        if start < 0:
            raise ValueError("start must be non-negative")
        p0 = float(self.discount(start))
        p1 = float(self.discount(start + tenor))
        return (p0 / p1) ** (1.0 / tenor) - 1.0

    def forward_short_rates(self, horizon: int) -> np.ndarray:
        """Return the implied one-year forward rates for years ``1 … horizon``.

        The geometric average of these rates equals ``zero(horizon)`` by
        construction, which is the algebraic content of the expectations
        hypothesis.
        """
        h = int(horizon)
        if h < 1:
            raise ValueError("horizon must be at least one year")
        years = np.arange(h + 1, dtype=float)
        dfs = _as_array(self.discount(years))
        return dfs[:-1] / dfs[1:] - 1.0

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_par_rates(
        cls,
        tenors: Sequence[float],
        par_rates: Sequence[float],
        name: str = "",
    ) -> "ZeroCurve":
        """Bootstrap a zero curve from annual-pay par (swap) rates.

        Parameters
        ----------
        tenors:
            Integer maturities in years, strictly increasing, starting at 1.
        par_rates:
            Par swap / par bond rates, decimal, annual coupon frequency.

        Notes
        -----
        Missing intermediate maturities are filled by linear interpolation of
        the par rates before bootstrapping, which is standard practice for
        annual-pay EUR swap curves.
        """
        t = np.asarray(tenors, dtype=float)
        p = np.asarray(par_rates, dtype=float)
        if t.ndim != 1 or t.size < 1:
            raise ValueError("need at least one par rate")
        if p.shape != t.shape:
            raise ValueError("tenors and par_rates must have the same shape")
        if not np.allclose(t, np.round(t)):
            raise ValueError("par bootstrapping requires integer maturities")
        if np.any(np.diff(t) <= 0):
            raise ValueError("tenors must be strictly increasing")
        if t[0] != 1.0:
            raise ValueError("par bootstrapping must start at the 1-year point")

        grid = np.arange(1.0, t[-1] + 1.0)
        par = np.interp(grid, t, p)

        dfs = np.empty_like(grid)
        annuity = 0.0
        for i, (mat, c) in enumerate(zip(grid, par)):
            dfs[i] = (1.0 - c * annuity) / (1.0 + c)
            annuity += dfs[i]
        if np.any(dfs <= 0):
            raise ValueError("bootstrapping produced a non-positive discount factor")
        zeros = dfs ** (-1.0 / grid) - 1.0
        return cls(grid, zeros, name=name)

    @classmethod
    def from_mapping(cls, payload: dict, name: str = "") -> "ZeroCurve":
        """Build a curve from a JSON-style mapping.

        The mapping must contain ``tenors`` plus either ``zero_rates`` or
        ``par_rates``.
        """
        tenors = payload["tenors"]
        label = payload.get("name", name)
        if "zero_rates" in payload:
            return cls(tenors, payload["zero_rates"], name=label)
        if "par_rates" in payload:
            return cls.from_par_rates(tenors, payload["par_rates"], name=label)
        raise KeyError("curve mapping needs 'zero_rates' or 'par_rates'")

    # ------------------------------------------------------------------
    def breakeven_inflation(self, real_curve: "ZeroCurve", maturity: Number) -> Number:
        """Return the breakeven inflation rate versus *real_curve*.

        :math:`\\pi_{BE}(t) = \\frac{1 + z_{nom}(t)}{1 + z_{real}(t)} - 1`.
        """
        nom = _as_array(self.zero(maturity))
        real = _as_array(real_curve.zero(maturity))
        return _scalarise((1.0 + nom) / (1.0 + real) - 1.0, maturity)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"ZeroCurve(name={self.name!r}, tenors={self.tenors[0]:g}"
            f"…{self.tenors[-1]:g}, n_nodes={self.tenors.size})"
        )
