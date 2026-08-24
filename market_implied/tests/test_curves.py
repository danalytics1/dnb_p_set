"""Tests for :mod:`market_implied.curves`."""

from __future__ import annotations

import numpy as np
import pytest

from market_implied.curves import TermStructure, ZeroCurve


@pytest.fixture
def curve() -> ZeroCurve:
    return ZeroCurve(
        [1, 2, 3, 5, 7, 10, 15, 30],
        [0.021, 0.0215, 0.0225, 0.024, 0.0255, 0.0275, 0.0295, 0.0285],
        name="EUR_nominal",
    )


def test_curve_reproduces_its_nodes(curve):
    assert np.allclose(curve.zero(curve.tenors), curve.zero_rates)


def test_discount_factor_matches_zero_rate(curve):
    for t in (1.0, 4.3, 12.0, 30.0):
        assert curve.discount(t) == pytest.approx((1 + curve.zero(t)) ** -t)


def test_discount_at_zero_is_one(curve):
    assert curve.discount(0.0) == pytest.approx(1.0)


def test_forward_rates_compound_to_the_spot_rate(curve):
    """The geometric average of implied one-year forwards equals the spot rate."""
    for horizon in (1, 5, 12, 25):
        forwards = curve.forward_short_rates(horizon)
        assert len(forwards) == horizon
        implied = np.prod(1.0 + forwards) ** (1.0 / horizon) - 1.0
        assert implied == pytest.approx(curve.zero(horizon))


def test_forward_zero_is_consistent_with_discount_factors(curve):
    fwd = curve.forward_zero(5, 10)
    assert curve.discount(15) == pytest.approx(curve.discount(5) * (1 + fwd) ** -10)


def test_forward_zero_at_zero_start_is_the_spot_rate(curve):
    assert curve.forward_zero(0, 7) == pytest.approx(curve.zero(7))


def test_flat_par_curve_bootstraps_to_a_flat_zero_curve():
    curve = ZeroCurve.from_par_rates([1, 2, 3, 5, 10], [0.03] * 5)
    assert np.allclose(curve.zero(curve.tenors), 0.03)


def test_par_bootstrap_reprices_the_par_bond():
    tenors = [1, 2, 3, 4, 5]
    par = [0.020, 0.022, 0.024, 0.025, 0.026]
    curve = ZeroCurve.from_par_rates(tenors, par)
    for maturity, coupon in zip(tenors, par):
        years = np.arange(1, maturity + 1, dtype=float)
        dfs = np.asarray(curve.discount(years), dtype=float)
        price = coupon * dfs.sum() + dfs[-1]
        assert price == pytest.approx(1.0)


def test_interpolation_keeps_forward_rates_positive(curve):
    grid = np.linspace(0.25, 40.0, 400)
    dfs = np.asarray(curve.discount(grid), dtype=float)
    assert np.all(np.diff(dfs) < 0)


def test_extrapolation_beyond_the_last_node_uses_a_flat_forward(curve):
    tail = curve.forward_zero(30, 10)
    assert tail == pytest.approx(curve.forward_zero(40, 10))


def test_breakeven_inflation():
    nominal = ZeroCurve([1, 10], [0.03, 0.03])
    real = ZeroCurve([1, 10], [0.01, 0.01])
    assert nominal.breakeven_inflation(real, 5) == pytest.approx(1.03 / 1.01 - 1)


def test_curve_validation():
    with pytest.raises(ValueError):
        ZeroCurve([1], [0.02])
    with pytest.raises(ValueError):
        ZeroCurve([2, 1], [0.02, 0.03])
    with pytest.raises(ValueError):
        ZeroCurve([0, 1], [0.02, 0.03])
    with pytest.raises(ValueError):
        ZeroCurve([1, 2], [0.02])


def test_from_mapping_supports_both_input_styles():
    a = ZeroCurve.from_mapping({"tenors": [1, 2], "zero_rates": [0.02, 0.03]})
    b = ZeroCurve.from_mapping({"tenors": [1, 2], "par_rates": [0.02, 0.03]})
    assert a.zero(1) == pytest.approx(0.02)
    assert b.zero(1) == pytest.approx(0.02)
    with pytest.raises(KeyError):
        ZeroCurve.from_mapping({"tenors": [1, 2]})


def test_term_structure_interpolates_and_flattens():
    ts = TermStructure([1, 10], [0.0, 0.01])
    assert ts(1) == pytest.approx(0.0)
    assert ts(5.5) == pytest.approx(0.005)
    assert ts(50) == pytest.approx(0.01)
    assert ts(0.5) == pytest.approx(0.0)


def test_term_structure_zero_helper():
    assert TermStructure.zero()(7) == 0.0


def test_scalar_in_scalar_out(curve):
    assert isinstance(curve.zero(5.0), float)
    assert isinstance(curve.zero(np.array([5.0, 7.0])), np.ndarray)
