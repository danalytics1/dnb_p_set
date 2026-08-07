"""Tests for dnb_p_set.lifecycle — portfolios, lifecycle and wealth projection."""

from __future__ import annotations

import numpy as np
import pytest

from dnb_p_set import ScenarioSet
from dnb_p_set.lifecycle import (
    BESCHERMINGSPORTEFEUILLE,
    DEFAULT_LIFECYCLE,
    DEFAULT_MAATMENSEN,
    RENDEMENTSPORTEFEUILLE,
    Lifecycle,
    Maatmens,
    Portefeuille,
    bond_returns,
    portefeuille_returns,
    project_wealth,
)

N_SCEN = 400
N_T = 26   # projection years 0 … 25
N_Y = 25   # 25 one-year returns


def make_set(seed: int = 1) -> ScenarioSet:
    """A small P-set with a realistic affine term structure."""
    rng = np.random.default_rng(seed)

    data = {}
    for i, base in enumerate([0.030, 0.011, 0.012]):
        arr = np.empty((N_SCEN, N_T))
        arr[:, 0] = base
        for t in range(1, N_T):
            arr[:, t] = 0.95 * arr[:, t - 1] + 0.05 * base + rng.normal(0, 0.004, N_SCEN)
        data[f"state_variable_{i + 1}"] = arr

    tau = np.arange(1, 101, dtype=float)
    data["psi_nominal"] = np.column_stack([0.07 * tau, -0.98 * tau, -0.036 * tau])
    data["phi_nominal"] = np.tile((-0.017 * tau)[:, None], (1, N_T))
    data["equity_return"] = rng.normal(0.066, 0.149, (N_SCEN, N_Y))
    data["price_inflation_nl"] = rng.normal(0.021, 0.013, (N_SCEN, N_Y))
    return ScenarioSet(data=data, set_type="P", source_path="test.csv")


@pytest.fixture(scope="module")
def scenario_set():
    return make_set()


class TestPortefeuille:
    def test_weights_sum_to_one(self):
        assert RENDEMENTSPORTEFEUILLE.equity_weight + RENDEMENTSPORTEFEUILLE.bond_weight == 1.0
        assert BESCHERMINGSPORTEFEUILLE.bond_weight == 1.0

    def test_rejects_weight_outside_unit_interval(self):
        with pytest.raises(ValueError, match="equity_weight"):
            Portefeuille(key="x", label="x", equity_weight=1.5)

    def test_rejects_maturity_below_one_year(self):
        with pytest.raises(ValueError, match="bond_maturity"):
            Portefeuille(key="x", label="x", bond_maturity=0)

    def test_description_mentions_both_legs(self):
        mixed = Portefeuille(key="x", label="x", equity_weight=0.4, bond_maturity=15)
        text = mixed.description()
        assert "40% aandelen" in text
        assert "15 jaar" in text


class TestBondReturns:
    def test_shape(self, scenario_set):
        assert bond_returns(scenario_set, 20, 10).shape == (N_SCEN, 10)

    def test_one_year_bond_earns_the_one_year_rate(self, scenario_set):
        # A one-year zero simply matures, so its return is y(1, t) exactly.
        realised = bond_returns(scenario_set, 1, 5)
        expected = np.column_stack(
            [scenario_set.zero_rates(t, [1])[:, 0] for t in range(5)]
        )
        np.testing.assert_allclose(realised, expected)

    def test_long_bond_is_more_volatile_than_short(self, scenario_set):
        short = bond_returns(scenario_set, 2, 20).std()
        long = bond_returns(scenario_set, 30, 20).std()
        assert long > short

    def test_rejects_horizon_beyond_the_curve(self, scenario_set):
        # Rolling the bond needs the curve one year past the last return year.
        with pytest.raises(ValueError, match="time steps"):
            bond_returns(scenario_set, 20, N_T)

    def test_rejects_maturity_outside_the_parameter_block(self, scenario_set):
        with pytest.raises(ValueError, match="maturity"):
            bond_returns(scenario_set, 200, 5)


class TestPortefeuilleReturns:
    def test_return_portfolio_is_equity_after_costs(self, scenario_set):
        realised = portefeuille_returns(scenario_set, RENDEMENTSPORTEFEUILLE, 10)
        equity = scenario_set.get("equity_return")[:, :10]
        expected = (1 + equity) * (1 - RENDEMENTSPORTEFEUILLE.cost) - 1
        np.testing.assert_allclose(realised, expected)

    def test_costs_lower_the_mean(self, scenario_set):
        free = Portefeuille(key="free", label="free", equity_weight=1.0, cost=0.0)
        assert (
            portefeuille_returns(scenario_set, RENDEMENTSPORTEFEUILLE, 10).mean()
            < portefeuille_returns(scenario_set, free, 10).mean()
        )

    def test_protection_is_less_volatile_than_equity(self, scenario_set):
        equity = portefeuille_returns(scenario_set, RENDEMENTSPORTEFEUILLE, 20)
        bonds = portefeuille_returns(scenario_set, BESCHERMINGSPORTEFEUILLE, 20)
        assert bonds.std() < equity.std()


class TestLifecycle:
    def test_weights_interpolate_between_anchors(self):
        lc = Lifecycle(key="t", label="t", anchors=((40, 1.0), (60, 0.6)))
        assert lc.rendement_weight(50) == pytest.approx(0.8)

    def test_weights_are_flat_outside_the_anchor_range(self):
        lc = Lifecycle(key="t", label="t", anchors=((40, 1.0), (60, 0.6)))
        assert lc.rendement_weight(20) == pytest.approx(1.0)
        assert lc.rendement_weight(95) == pytest.approx(0.6)

    def test_allocation_rows_sum_to_one(self):
        frame = DEFAULT_LIFECYCLE.allocation()
        np.testing.assert_allclose(frame.sum(axis=1).to_numpy(), 1.0)

    def test_allocation_is_non_increasing_in_return_assets(self):
        weights = DEFAULT_LIFECYCLE.allocation()["rendement"].to_numpy()
        assert np.all(np.diff(weights) <= 1e-12)

    def test_rejects_non_increasing_anchor_ages(self):
        with pytest.raises(ValueError, match="strictly increase"):
            Lifecycle(key="t", label="t", anchors=((60, 1.0), (40, 0.6)))

    def test_rejects_weight_outside_unit_interval(self):
        with pytest.raises(ValueError, match="must lie in"):
            Lifecycle(key="t", label="t", anchors=((40, 1.2), (60, 0.6)))

    def test_rejects_a_single_anchor(self):
        with pytest.raises(ValueError, match="at least two"):
            Lifecycle(key="t", label="t", anchors=((40, 1.0),))


class TestMaatmens:
    def test_grondslag_is_salary_above_the_franchise(self):
        mens = Maatmens("x", 1990, 0, 50_000, franchise=18_000)
        assert mens.pensioengrondslag == pytest.approx(32_000)

    def test_grondslag_never_goes_negative(self):
        mens = Maatmens("x", 1990, 0, 10_000, franchise=18_000)
        assert mens.pensioengrondslag == 0.0
        assert mens.jaarpremie == 0.0

    def test_age_follows_the_base_year(self):
        assert Maatmens("x", 2001, 0, 0).leeftijd(2026) == 25

    def test_rejects_negative_capital(self):
        with pytest.raises(ValueError, match="pensioenvermogen"):
            Maatmens("x", 1990, -1, 50_000)


class TestProjectWealth:
    @pytest.fixture(scope="class")
    def projection(self, scenario_set):
        return project_wealth(
            scenario_set,
            DEFAULT_MAATMENSEN[0],
            horizon=20,
            basisjaar=2026,
        )

    def test_shape_and_starting_capital(self, projection):
        assert projection.wealth.shape == (N_SCEN, 21)
        assert projection.horizon == 20
        np.testing.assert_allclose(
            projection.wealth[:, 0], DEFAULT_MAATMENSEN[0].pensioenvermogen
        )

    def test_reproduces_the_recursion_by_hand(self, projection):
        premie = projection.schedule["premie"].to_numpy()
        # The default indexes salary on simulated inflation, so the premium is
        # scenario-dependent; check the deterministic first step instead.
        expected = (projection.wealth[:, 0] + premie[0]) * (1 + projection.returns[:, 0])
        np.testing.assert_allclose(projection.wealth[:, 1], expected)

    def test_schedule_weights_follow_the_lifecycle(self, projection):
        schedule = projection.schedule
        expected = DEFAULT_LIFECYCLE.rendement_weight(schedule["leeftijd"].to_numpy())
        np.testing.assert_allclose(schedule["w_rendement"].to_numpy(), expected)
        np.testing.assert_allclose(
            schedule["w_rendement"] + schedule["w_bescherming"], 1.0
        )

    def test_ages_start_at_the_base_year(self, projection):
        assert projection.schedule.loc[0, "leeftijd"] == 25
        assert projection.schedule.loc[0, "kalenderjaar"] == 2026

    def test_percentiles_are_ordered(self, projection):
        frame = projection.percentiles()
        assert (frame["p5"] <= frame["p50"]).all()
        assert (frame["p50"] <= frame["p95"]).all()

    def test_spread_widens_with_the_horizon(self, projection):
        frame = projection.percentiles()
        early = frame.loc[1, "p95"] - frame.loc[1, "p5"]
        late = frame.loc[20, "p95"] - frame.loc[20, "p5"]
        assert late > early

    def test_at_matches_the_wealth_column(self, projection):
        np.testing.assert_array_equal(projection.at(10), projection.wealth[:, 10])

    def test_at_rejects_a_horizon_past_the_projection(self, projection):
        with pytest.raises(ValueError, match="horizon"):
            projection.at(21)

    def test_flat_salary_gives_a_constant_premium(self, scenario_set):
        projection = project_wealth(
            scenario_set,
            DEFAULT_MAATMENSEN[0],
            horizon=10,
            basisjaar=2026,
            loonindexatie="geen",
        )
        premie = projection.schedule["premie"].to_numpy()
        np.testing.assert_allclose(premie, DEFAULT_MAATMENSEN[0].jaarpremie)

    def test_fixed_indexation_compounds(self, scenario_set):
        projection = project_wealth(
            scenario_set,
            DEFAULT_MAATMENSEN[0],
            horizon=10,
            basisjaar=2026,
            loonindexatie=0.02,
        )
        premie = projection.schedule["premie"].to_numpy()
        expected = DEFAULT_MAATMENSEN[0].jaarpremie * 1.02 ** np.arange(10)
        np.testing.assert_allclose(premie, expected)

    def test_contributions_stop_at_retirement(self, scenario_set):
        # Born in 1961, so 65 in 2026 and past the retirement age of 68 in year 3.
        mens = Maatmens("Bijna klaar", 1961, 300_000, 60_000, pensioenleeftijd=68)
        projection = project_wealth(
            scenario_set, mens, horizon=10, basisjaar=2026, loonindexatie="geen"
        )
        premie = projection.schedule["premie"].to_numpy()
        assert (premie[:3] > 0).all()
        np.testing.assert_allclose(premie[3:], 0.0)

    def test_precomputed_returns_match_a_fresh_run(self, scenario_set):
        cached = tuple(
            portefeuille_returns(scenario_set, p, 15)
            for p in (RENDEMENTSPORTEFEUILLE, BESCHERMINGSPORTEFEUILLE)
        )
        with_cache = project_wealth(
            scenario_set, DEFAULT_MAATMENSEN[1], horizon=15,
            basisjaar=2026, returns=cached,
        )
        without = project_wealth(
            scenario_set, DEFAULT_MAATMENSEN[1], horizon=15, basisjaar=2026
        )
        np.testing.assert_allclose(with_cache.wealth, without.wealth)

    def test_rejects_a_horizon_beyond_the_set(self, scenario_set):
        with pytest.raises(ValueError, match="horizon must lie in"):
            project_wealth(scenario_set, DEFAULT_MAATMENSEN[0], horizon=N_Y + 5)

    def test_a_de_risked_maatmens_ends_up_less_dispersed(self, scenario_set):
        """Two identical participants, only their age differs."""
        young = Maatmens("jong", 2001, 100_000, 40_000)
        old = Maatmens("oud", 1966, 100_000, 40_000)
        spread = []
        for mens in (young, old):
            frame = project_wealth(
                scenario_set, mens, horizon=20, basisjaar=2026
            ).percentiles()
            spread.append(
                (frame.loc[20, "p95"] - frame.loc[20, "p5"]) / frame.loc[20, "p50"]
            )
        assert spread[1] < spread[0]
