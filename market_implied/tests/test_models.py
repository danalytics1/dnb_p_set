"""Tests for the individual asset-class models.

Each test rebuilds the model's arithmetic by hand from the inputs, so a change
in a formula fails loudly rather than silently shifting a premium.
"""

from __future__ import annotations

import pytest

from market_implied.curves import TermStructure, ZeroCurve
from market_implied.marketdata import MarketSnapshot
from market_implied.models import AssetSpec, ModelContext, ModelError, get_model
from market_implied.models.base import annualise_price_effect, reversion_fraction
from market_implied.models.equity import implied_cost_of_equity

NOMINAL = [0.020, 0.022, 0.024, 0.026, 0.028, 0.030]
REAL = [0.002, 0.004, 0.006, 0.008, 0.010, 0.012]
TENORS = [1, 2, 5, 10, 15, 30]
TP = [0.000, 0.001, 0.003, 0.006, 0.008, 0.010]
IRP = [0.000, 0.001, 0.002, 0.003, 0.003, 0.003]


@pytest.fixture
def snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        as_of="2026-06-30",
        base_currency="EUR",
        curves={
            "EUR_nominal": ZeroCurve(TENORS, NOMINAL, name="EUR_nominal"),
            "EUR_real": ZeroCurve(TENORS, REAL, name="EUR_real"),
            "USD_nominal": ZeroCurve(TENORS, [r + 0.01 for r in NOMINAL]),
            "USD_real": ZeroCurve(TENORS, [r + 0.01 for r in REAL]),
        },
        term_premia={
            "EUR_nominal": TermStructure(TENORS, TP),
            "USD_nominal": TermStructure(TENORS, TP),
        },
        inflation_risk_premia={
            "EUR": TermStructure(TENORS, IRP),
            "USD": TermStructure(TENORS, IRP),
        },
        instruments={
            "credit": {
                "test_ig": {
                    "oas": 0.010,
                    "effective_duration": 5.0,
                    "spread_duration": 5.0,
                    "long_run_oas": 0.014,
                }
            },
            "equity": {
                "test": {
                    "dividend_yield": 0.020,
                    "net_buyback_yield": 0.010,
                    "cape": 25.0,
                    "roe": 0.14,
                    "payout_ratio": 0.55,
                }
            },
            "commodities": {"test": {"roll_yield": -0.005}},
            "property": {"test": {"income_yield": 0.05, "long_run_yield": 0.05}},
        },
    )


@pytest.fixture
def ctx(snapshot):
    return ModelContext(snapshot=snapshot, horizon=5.0)


def run(model: str, ctx: ModelContext, **params):
    spec = AssetSpec(
        key="x", name="X", model=model, currency=params.pop("currency", "EUR"), params=params
    )
    return get_model(model)(spec, ctx)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def test_reversion_fraction_follows_the_half_life():
    assert reversion_fraction(5, None) == 0.0
    assert reversion_fraction(5, 0) == 1.0
    assert reversion_fraction(5, 5) == pytest.approx(0.5)
    assert reversion_fraction(10, 5) == pytest.approx(0.75)
    assert reversion_fraction(15, 5) > reversion_fraction(5, 5)


def test_annualise_price_effect_compounds_back():
    annual = annualise_price_effect(-0.05, 5)
    assert (1 + annual) ** 5 - 1 == pytest.approx(-0.05)


def test_annualise_price_effect_rejects_a_total_wipeout():
    with pytest.raises(ModelError):
        annualise_price_effect(-1.0, 5)


# ----------------------------------------------------------------------
# cash and government bonds
# ----------------------------------------------------------------------
def test_cash_has_no_risk_premium(ctx):
    bu = run("cash", ctx)
    assert bu.risk_premium == pytest.approx(0.0)
    assert bu.expected_return == pytest.approx(ctx.risk_free("EUR"))


def test_cash_deposit_spread_flows_through(ctx):
    assert run("cash", ctx, deposit_spread=-0.001).risk_premium == pytest.approx(-0.001)


def test_nominal_bond_is_term_premium_plus_spread_minus_losses(ctx):
    bu = run("nominal_bond", ctx, duration=10.0, spread=0.002, expected_credit_loss=0.0003)
    assert bu.risk_premium == pytest.approx(0.006 + 0.002 - 0.0003)
    bu.check()


def test_horizon_matched_bond_earns_exactly_the_spot_rate(ctx):
    """The single most important consistency check of the whole framework."""
    bu = run("nominal_bond", ctx, duration=ctx.horizon)
    assert bu.expected_return == pytest.approx(
        ctx.snapshot.curve("EUR_nominal").zero(ctx.horizon)
    )


def test_index_linked_bond_gives_up_the_inflation_risk_premium(ctx):
    nominal = run("nominal_bond", ctx, duration=10.0)
    linker = run("index_linked_bond", ctx, duration=10.0)
    assert linker.risk_premium == pytest.approx(nominal.risk_premium - 0.003)


def test_index_linked_bond_liquidity_premium_adds_back(ctx):
    plain = run("index_linked_bond", ctx, duration=10.0)
    liquid = run("index_linked_bond", ctx, duration=10.0, liquidity_premium=0.001)
    assert liquid.risk_premium == pytest.approx(plain.risk_premium + 0.001)


# ----------------------------------------------------------------------
# credit
# ----------------------------------------------------------------------
def test_spread_product_decomposition(ctx):
    bu = run(
        "spread_product",
        ctx,
        quotes="credit.test_ig",
        default_rate=0.01,
        recovery_rate=0.40,
        downgrade_drag=0.002,
        spread_reversion_half_life=None,
    )
    expected = 0.003 + 0.010 - 0.01 * 0.6 - 0.002  # TP(5) + OAS - EL - drag
    assert bu.risk_premium == pytest.approx(expected)
    assert bu.value_of("spread_valuation") == 0.0
    bu.check()


def test_widening_spreads_reduce_the_premium(ctx):
    tight = run("spread_product", ctx, quotes="credit.test_ig", spread_reversion_half_life=None)
    reverting = run(
        "spread_product", ctx, quotes="credit.test_ig", spread_reversion_half_life=3.0
    )
    # long_run_oas (1.4%) is above the current OAS (1.0%), so reversion costs money
    assert reverting.risk_premium < tight.risk_premium


def test_spread_valuation_matches_the_hand_calculation(ctx):
    bu = run("spread_product", ctx, quotes="credit.test_ig", spread_reversion_half_life=3.0)
    theta = reversion_fraction(5, 3.0)
    target = 0.010 + theta * (0.014 - 0.010)
    expected = annualise_price_effect(-5.0 * (target - 0.010), 5)
    assert bu.value_of("spread_valuation") == pytest.approx(expected)


def test_valuation_can_be_switched_off_globally(snapshot):
    ctx = ModelContext(snapshot=snapshot, horizon=5.0, apply_valuation=False)
    bu = run("spread_product", ctx, quotes="credit.test_ig", spread_reversion_half_life=3.0)
    assert bu.block("spread_valuation") is None


def test_spread_capture_haircuts_the_carry(ctx):
    bu = run(
        "spread_product",
        ctx,
        quotes="credit.test_ig",
        spread_capture=0.8,
        spread_reversion_half_life=None,
    )
    assert bu.value_of("credit_spread") == pytest.approx(0.008)


def test_expected_loss_uses_default_times_loss_given_default(ctx):
    bu = run(
        "spread_product",
        ctx,
        quotes="credit.test_ig",
        default_rate=0.04,
        recovery_rate=0.25,
        spread_reversion_half_life=None,
    )
    assert bu.value_of("expected_credit_loss") == pytest.approx(-0.04 * 0.75)


# ----------------------------------------------------------------------
# equity
# ----------------------------------------------------------------------
def test_grinold_kroner_sums_its_components(ctx):
    bu = run("grinold_kroner", ctx, quotes="equity.test", real_growth=0.015)
    inflation = ctx.expected_inflation("EUR")
    total = 0.020 + 0.010 + inflation + 0.015
    assert bu.expected_return == pytest.approx(total)
    bu.check()


def test_grinold_kroner_valuation_drag_when_expensive(ctx):
    cheapening = run(
        "grinold_kroner",
        ctx,
        quotes="equity.test",
        real_growth=0.015,
        valuation_metric="cape",
        fair_value=20.0,
        valuation_half_life=10.0,
    )
    flat = run("grinold_kroner", ctx, quotes="equity.test", real_growth=0.015)
    assert cheapening.value_of("valuation_change") < 0
    assert cheapening.risk_premium < flat.risk_premium


def test_grinold_kroner_valuation_boost_when_cheap(ctx):
    bu = run(
        "grinold_kroner",
        ctx,
        quotes="equity.test",
        real_growth=0.015,
        fair_value=30.0,
        valuation_half_life=10.0,
    )
    assert bu.value_of("valuation_change") > 0


def test_sustainable_growth_uses_roe_times_retention(ctx):
    bu = run(
        "grinold_kroner",
        ctx,
        quotes="equity.test",
        real_growth_source="sustainable",
    )
    inflation = ctx.expected_inflation("EUR")
    nominal_growth = 0.14 * (1 - 0.55)
    assert bu.value_of("real_growth") == pytest.approx(
        (1 + nominal_growth) / (1 + inflation) - 1
    )


def test_inflation_pass_through_scales_the_inflation_block(ctx):
    bu = run(
        "grinold_kroner", ctx, quotes="equity.test", real_growth=0.0, inflation_pass_through=0.5
    )
    assert bu.value_of("expected_inflation") == pytest.approx(
        0.5 * ctx.expected_inflation("EUR")
    )


def test_grinold_kroner_needs_a_dividend_yield(ctx):
    ctx.snapshot.instruments["equity"]["broken"] = {"cape": 20.0}
    with pytest.raises(ModelError):
        run("grinold_kroner", ctx, quotes="equity.broken", real_growth=0.01)


def test_hedged_foreign_equity_follows_covered_interest_parity(ctx):
    """E[R_hedged] == local total return - local cash + base cash."""
    bu = run("grinold_kroner", ctx, quotes="equity.test", real_growth=0.015, currency="USD")
    assert bu.risk_free == pytest.approx(ctx.risk_free("EUR"))

    local_total = 0.020 + 0.010 + ctx.expected_inflation("USD") + 0.015
    hedged = local_total - ctx.rolled_cash_rate("USD") + ctx.rolled_cash_rate("EUR")
    assert bu.expected_return == pytest.approx(hedged)
    bu.check()


def test_implied_cost_of_equity_round_trip():
    """Price a known two-stage DDM, then invert it and recover the discount rate."""
    r, g1, g_inf, n = 0.08, 0.05, 0.03, 5
    pv_per_unit = sum((1 + g1) ** t / (1 + r) ** t for t in range(1, n + 1))
    pv_per_unit += (1 + g1) ** n * (1 + g_inf) / ((r - g_inf) * (1 + r) ** n)
    payout_yield = 1.0 / pv_per_unit
    assert implied_cost_of_equity(payout_yield, g1, g_inf, n) == pytest.approx(r, abs=1e-6)


def test_implied_cost_of_equity_rises_when_the_price_falls():
    low = implied_cost_of_equity(0.03, 0.04, 0.02, 5)
    high = implied_cost_of_equity(0.05, 0.04, 0.02, 5)
    assert high > low


def test_implied_cost_of_equity_rejects_a_non_positive_yield():
    with pytest.raises(ModelError):
        implied_cost_of_equity(0.0, 0.04, 0.02, 5)


# ----------------------------------------------------------------------
# real assets
# ----------------------------------------------------------------------
def test_commodities_are_roll_plus_spot_plus_rebalancing(ctx):
    bu = run("commodities", ctx, quotes="commodities.test", rebalancing_return=0.004)
    inflation = ctx.expected_inflation("EUR")
    assert bu.risk_premium == pytest.approx(-0.005 + inflation + 0.004)
    bu.check()


def test_commodity_contango_hurts(ctx):
    ctx.snapshot.instruments["commodities"]["backwardated"] = {"roll_yield": 0.01}
    contango = run("commodities", ctx, quotes="commodities.test")
    backwardation = run("commodities", ctx, quotes="commodities.backwardated")
    assert backwardation.risk_premium > contango.risk_premium


def test_yield_and_growth_decomposition(ctx):
    bu = run(
        "yield_and_growth",
        ctx,
        quotes="property.test",
        capex_drag=0.008,
        real_growth=0.002,
        illiquidity_premium=0.003,
    )
    inflation = ctx.expected_inflation("EUR")
    total = 0.05 - 0.008 + inflation + 0.002 + 0.003
    assert bu.expected_return == pytest.approx(total)
    bu.check()


def test_rising_cap_rate_costs_the_full_yield_duration(ctx):
    ctx.snapshot.instruments["property"]["widening"] = {
        "income_yield": 0.05,
        "long_run_yield": 0.06,
    }
    bu = run(
        "yield_and_growth",
        ctx,
        quotes="property.widening",
        yield_reversion_half_life=5.0,
    )
    theta = reversion_fraction(5, 5.0)
    target = 0.05 + theta * 0.01
    expected = annualise_price_effect(-(1 / 0.05) * (target - 0.05), 5)
    assert bu.value_of("yield_shift") == pytest.approx(expected)
    assert bu.value_of("yield_shift") < 0


# ----------------------------------------------------------------------
# alternatives
# ----------------------------------------------------------------------
def test_levered_beta_scales_the_reference_premium(ctx):
    reference = run("grinold_kroner", ctx, quotes="equity.test", real_growth=0.015)
    ctx.peers["equity"] = reference
    spec = AssetSpec(
        key="pe",
        name="PE",
        model="levered_beta",
        depends_on=("equity",),
        params={"reference": "equity", "beta": 1.3, "illiquidity_premium": 0.008},
    )
    bu = get_model("levered_beta")(spec, ctx)
    assert bu.risk_premium == pytest.approx(reference.risk_premium * 1.3 + 0.008)
    bu.check()


def test_levered_beta_requires_its_reference_to_exist(ctx):
    spec = AssetSpec(key="pe", name="PE", model="levered_beta", params={"reference": "nope"})
    with pytest.raises(ModelError):
        get_model("levered_beta")(spec, ctx)


def test_fee_drag_reduces_the_premium(ctx):
    ctx.peers["equity"] = run("grinold_kroner", ctx, quotes="equity.test", real_growth=0.015)
    base = AssetSpec(
        key="pe", name="PE", model="levered_beta", depends_on=("equity",),
        params={"reference": "equity", "beta": 1.0},
    )
    with_fee = AssetSpec(
        key="pe", name="PE", model="levered_beta", depends_on=("equity",),
        params={"reference": "equity", "beta": 1.0, "fee_drag": 0.01},
    )
    model = get_model("levered_beta")
    assert model(with_fee, ctx).risk_premium == pytest.approx(
        model(base, ctx).risk_premium - 0.01
    )


def test_unknown_model_name_is_rejected():
    with pytest.raises(ModelError):
        get_model("does_not_exist")
