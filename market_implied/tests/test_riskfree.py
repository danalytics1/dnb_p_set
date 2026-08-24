"""Tests for the shared risk-free building block."""

from __future__ import annotations

import pytest

from market_implied.blocks import RISK_FREE
from market_implied.curves import TermStructure, ZeroCurve
from market_implied.riskfree import ROLLED_CASH, SPOT, RiskFreeModel


@pytest.fixture
def curve():
    return ZeroCurve([1, 2, 5, 10, 15, 30], [0.021, 0.0215, 0.024, 0.0275, 0.0295, 0.0285])


@pytest.fixture
def term_premium():
    return TermStructure([1, 2, 5, 10, 15, 30], [0.0, 0.0005, 0.0025, 0.0055, 0.0075, 0.0095])


def test_spot_convention_returns_the_zero_rate(curve, term_premium):
    model = RiskFreeModel(curve, term_premium, convention=SPOT)
    for horizon in (5, 15):
        assert model.rate(horizon) == pytest.approx(curve.zero(horizon))


def test_rolled_cash_strips_the_term_premium(curve, term_premium):
    model = RiskFreeModel(curve, term_premium, convention=ROLLED_CASH)
    assert model.rate(5) == pytest.approx(0.024 - 0.0025)
    assert model.rate(15) == pytest.approx(0.0295 - 0.0075)


def test_conventions_coincide_without_a_term_premium(curve):
    rolled = RiskFreeModel(curve, None, convention=ROLLED_CASH)
    spot = RiskFreeModel(curve, None, convention=SPOT)
    for horizon in (5, 15):
        assert rolled.rate(horizon) == pytest.approx(spot.rate(horizon))


def test_horizon_matched_bond_earns_the_spot_rate(curve, term_premium):
    """rf(H) + TP(H) == z(H): the decomposition has to add back up."""
    model = RiskFreeModel(curve, term_premium)
    for horizon in (5, 15):
        total = model.rate(horizon) + model.duration_carry(horizon, horizon)
        assert total == pytest.approx(curve.zero(horizon))


def test_duration_carry_is_the_term_premium_and_ignores_the_horizon(curve, term_premium):
    for convention in (ROLLED_CASH, SPOT):
        model = RiskFreeModel(curve, term_premium, convention=convention)
        assert model.duration_carry(5, 10) == pytest.approx(0.0055)
        assert model.duration_carry(15, 10) == pytest.approx(0.0055)


def test_longer_duration_earns_more_when_the_term_premium_rises(curve, term_premium):
    model = RiskFreeModel(curve, term_premium)
    assert model.duration_carry(5, 15) > model.duration_carry(5, 2)


def test_block_is_tagged_as_the_risk_free_kind(curve, term_premium):
    block = RiskFreeModel(curve, term_premium).block(5)
    assert block.kind == RISK_FREE
    assert block.name == "risk_free"
    assert block.note


def test_unknown_convention_is_rejected(curve):
    with pytest.raises(ValueError):
        RiskFreeModel(curve, None, convention="whatever")
