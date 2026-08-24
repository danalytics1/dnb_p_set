"""End-to-end tests on the shipped configuration."""

from __future__ import annotations

import json

import pytest

from market_implied import build_expectations, load_universe
from market_implied.models.base import AssetSpec
from market_implied.universe import Universe


def test_every_build_up_is_internally_consistent(result):
    for build_up in result.build_ups.values():
        build_up.check(tolerance=1e-10)
        assert build_up.expected_return == pytest.approx(
            build_up.risk_free + build_up.risk_premium
        )


def test_the_risk_free_rate_is_identical_across_asset_classes(result):
    for horizon in result.universe.horizons:
        rates = {result.build_up(key, horizon).risk_free for key in result.order}
        assert len(rates) == 1, "the risk-free block must follow one shared logic"


def test_expected_returns_do_not_depend_on_the_reporting_convention(
    snapshot, universe_path
):
    rolled = build_expectations(snapshot, load_universe(universe_path))
    spot = build_expectations(
        snapshot, load_universe(universe_path, risk_free_convention="spot")
    )
    for key in rolled.order:
        for horizon in rolled.universe.horizons:
            assert rolled.build_up(key, horizon).expected_return == pytest.approx(
                spot.build_up(key, horizon).expected_return, abs=1e-12
            )


def test_the_spot_convention_moves_the_term_premium_into_the_risk_free_rate(
    snapshot, universe_path
):
    spot = build_expectations(
        snapshot, load_universe(universe_path, risk_free_convention="spot")
    )
    cash = spot.build_up("cash_eur", 5)
    # Cash now underperforms the horizon-matched zero by exactly the term premium.
    assert cash.risk_premium < 0
    assert cash.risk_free == pytest.approx(snapshot.curve("EUR_nominal").zero(5))


def test_cash_carries_no_risk_premium(result):
    for horizon in result.universe.horizons:
        assert result.build_up("cash_eur", horizon).risk_premium == pytest.approx(0.0)


def test_risky_asset_classes_earn_more_than_cash(result):
    for horizon in result.universe.horizons:
        cash = result.build_up("cash_eur", horizon).expected_return
        for key in ("govt_emu", "credit_ig_eur", "equity_dm", "equity_em"):
            assert result.build_up(key, horizon).expected_return > cash


def test_the_ordering_of_the_premium_stack_is_economically_sensible(result):
    """Government < investment grade < high yield < equity."""
    for horizon in result.universe.horizons:
        premium = lambda key: result.build_up(key, horizon).risk_premium  # noqa: E731
        assert premium("cash_eur") < premium("govt_emu") < premium("credit_ig_eur")
        assert premium("credit_ig_eur") < premium("credit_hy_eur")
        assert premium("credit_hy_eur") < premium("equity_dm")


def test_private_equity_is_levered_developed_equity(result):
    for horizon in result.universe.horizons:
        pe = result.build_up("private_equity", horizon)
        dm = result.build_up("equity_dm", horizon)
        assert pe.risk_premium > dm.risk_premium
        assert pe.value_of("reference_premium") == pytest.approx(dm.risk_premium * 1.25)


def test_both_horizons_are_produced(result):
    assert set(result.universe.horizons) == {5, 15}
    assert len(result.build_ups) == len(result.order) * 2


def test_horizons_can_be_overridden(snapshot, universe):
    other = build_expectations(snapshot, universe, horizons=[3, 7, 20])
    assert list(other.universe.horizons) == [3, 7, 20]
    assert other.build_up("equity_dm", 20).expected_return > 0


def test_switching_off_valuation_removes_the_reversion_blocks(snapshot, universe_path):
    carry = build_expectations(snapshot, load_universe(universe_path, apply_valuation=False))
    blocks = set(carry.blocks_table()["block"])
    assert "spread_valuation" not in blocks
    assert "valuation_change" not in blocks
    assert "yield_shift" not in blocks


def test_summary_table_shape_and_columns(result):
    summary = result.summary_table()
    assert len(summary) == len(result.order) * len(result.universe.horizons)
    assert {
        "asset_class",
        "horizon",
        "risk_free",
        "risk_premium",
        "expected_return",
        "expected_return_arithmetic",
    } <= set(summary.columns)


def test_arithmetic_exceeds_geometric_for_volatile_assets(result):
    row = result.build_up("equity_dm", 5)
    assert row.expected_return_arithmetic > row.expected_return


def test_premium_matrix_has_one_column_per_horizon(result):
    matrix = result.premium_matrix()
    assert list(matrix.columns) == ["risk_premium_5y", "risk_premium_15y"]
    assert len(matrix) == len(result.order)


def test_blocks_table_reconciles_with_the_summary(result):
    blocks = result.blocks_table()
    totals = blocks.groupby(["asset_class", "horizon"])["value"].sum()
    for (key, horizon), total in totals.items():
        assert total == pytest.approx(result.build_up(key, horizon).expected_return)


def test_blocks_matrix_is_wide(result):
    matrix = result.blocks_matrix(5)
    assert "risk_free" in matrix.columns
    assert len(matrix) == len(result.order)


def test_diagnostics_are_exposed(result):
    diagnostics = result.diagnostics_table()
    row = diagnostics[
        (diagnostics.asset_class == "equity_dm") & (diagnostics.horizon == 5)
    ].iloc[0]
    assert row["implied_cost_of_equity"] > 0
    assert row["net_payout_yield"] > 0


def test_dependencies_are_evaluated_first(universe):
    order = [spec.key for spec in universe.evaluation_order()]
    assert order.index("equity_dm") < order.index("private_equity")


def test_cyclic_dependencies_are_detected():
    a = AssetSpec(key="a", name="A", model="cash", depends_on=("b",))
    b = AssetSpec(key="b", name="B", model="cash", depends_on=("a",))
    with pytest.raises(ValueError, match="cyclic"):
        Universe([a, b]).evaluation_order()


def test_unknown_dependency_is_rejected():
    a = AssetSpec(key="a", name="A", model="cash", depends_on=("ghost",))
    with pytest.raises(ValueError, match="unknown"):
        Universe([a])


def test_duplicate_keys_are_rejected():
    a = AssetSpec(key="a", name="A", model="cash")
    with pytest.raises(ValueError, match="duplicate"):
        Universe([a, a])


def test_disabled_asset_classes_are_skipped(tmp_path, universe_path):
    payload = json.loads(universe_path.read_text(encoding="utf-8"))
    payload["asset_classes"][-1]["_disabled"] = True
    path = tmp_path / "universe.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert len(load_universe(path)) == len(payload["asset_classes"]) - 1


def test_unknown_risk_free_convention_is_rejected(universe_path):
    with pytest.raises(ValueError):
        load_universe(universe_path, risk_free_convention="nope")


def test_snapshot_metadata_travels_with_the_result(result):
    assert result.snapshot.as_of == "2026-06-30"
    assert result.snapshot.base_currency == "EUR"
