"""Tests for the building-block primitives."""

from __future__ import annotations

import pytest

from market_implied.blocks import (
    ASSUMPTION,
    MARKET,
    PREMIUM,
    RISK_FREE,
    BuildingBlock,
    ReturnBuildUp,
    compound,
)


def make(blocks, volatility=None):
    return ReturnBuildUp(
        asset_class="test",
        name="Test",
        horizon=5,
        base_currency="EUR",
        blocks=blocks,
        volatility=volatility,
    )


def test_expected_return_is_risk_free_plus_premium():
    bu = make(
        [
            BuildingBlock("risk_free", 0.02, RISK_FREE),
            BuildingBlock("spread", 0.03),
            BuildingBlock("losses", -0.01),
        ]
    )
    assert bu.risk_free == pytest.approx(0.02)
    assert bu.risk_premium == pytest.approx(0.02)
    assert bu.expected_return == pytest.approx(0.04)
    bu.check()


def test_arithmetic_return_adds_half_the_variance():
    bu = make([BuildingBlock("risk_free", 0.02, RISK_FREE)], volatility=0.20)
    assert bu.expected_return_arithmetic == pytest.approx(0.02 + 0.5 * 0.04)


def test_arithmetic_return_is_none_without_a_volatility():
    assert make([BuildingBlock("risk_free", 0.02, RISK_FREE)]).expected_return_arithmetic is None


def test_exactly_one_risk_free_block_is_required():
    with pytest.raises(ValueError):
        make([BuildingBlock("spread", 0.01)])
    with pytest.raises(ValueError):
        make(
            [
                BuildingBlock("risk_free", 0.02, RISK_FREE),
                BuildingBlock("risk_free_2", 0.02, RISK_FREE),
            ]
        )


def test_assumption_share_measures_non_market_content():
    bu = make(
        [
            BuildingBlock("risk_free", 0.02, RISK_FREE),
            BuildingBlock("spread", 0.03, PREMIUM, MARKET),
            BuildingBlock("losses", -0.01, PREMIUM, ASSUMPTION),
        ]
    )
    assert bu.assumption_share() == pytest.approx(0.01 / 0.04)


def test_assumption_share_is_zero_without_premium_blocks():
    assert make([BuildingBlock("risk_free", 0.02, RISK_FREE)]).assumption_share() == 0.0


def test_lookup_helpers():
    bu = make([BuildingBlock("risk_free", 0.02, RISK_FREE), BuildingBlock("spread", 0.03)])
    assert bu.block("spread").value == pytest.approx(0.03)
    assert bu.block("nope") is None
    assert bu.value_of("spread") == pytest.approx(0.03)
    assert bu.value_of("nope", 0.5) == pytest.approx(0.5)


def test_records_carry_the_full_audit_trail():
    bu = make([BuildingBlock("risk_free", 0.02, RISK_FREE), BuildingBlock("spread", 0.03)])
    records = bu.to_records()
    assert len(records) == 2
    assert {"asset_class", "horizon", "block", "kind", "source", "value"} <= set(records[0])


def test_invalid_kind_and_source_are_rejected():
    with pytest.raises(ValueError):
        BuildingBlock("x", 0.0, kind="something")
    with pytest.raises(ValueError):
        BuildingBlock("x", 0.0, source="somewhere")


def test_compound_multiplies():
    assert compound([0.02, 0.01]) == pytest.approx(1.02 * 1.01 - 1)
    assert compound([]) == pytest.approx(0.0)
