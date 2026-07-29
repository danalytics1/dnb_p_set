"""Tests for dnb_p_set.ScenarioSet."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dnb_p_set import ScenarioSet
from dnb_p_set.constants import BLOCKS, N_TIMESTEPS_LONG, N_TIMESTEPS_SHORT
from tests.conftest import make_data_dict, N_TEST_SCENARIOS


@pytest.fixture()
def minimal_data():
    """Minimal data dict with a few variables."""
    return make_data_dict(
        variables=[
            "state_variable_1", "state_variable_2", "state_variable_3",
            "equity_return", "price_inflation_nl",
            "phi_nominal", "psi_nominal",
        ]
    )


@pytest.fixture()
def ss(minimal_data):
    return ScenarioSet(data=minimal_data, set_type="P")


class TestScenarioSetConstruction:
    def test_set_type(self, ss):
        assert ss.set_type == "P"

    def test_variables(self, ss):
        assert "equity_return" in ss.variables

    def test_n_scenarios(self, ss):
        assert ss.n_scenarios == N_TEST_SCENARIOS

    def test_repr(self, ss):
        r = repr(ss)
        assert "ScenarioSet" in r
        assert "P" in r


class TestGet:
    def test_get_by_canonical_name(self, ss):
        arr = ss.get("equity_return")
        assert isinstance(arr, np.ndarray)
        assert arr.ndim == 2
        assert arr.shape[0] == N_TEST_SCENARIOS
        assert arr.shape[1] == N_TIMESTEPS_SHORT

    def test_get_by_alias(self, ss):
        arr1 = ss.get("equity_return")
        arr2 = ss.get("aandelen")
        np.testing.assert_array_equal(arr1, arr2)

    def test_get_unknown_raises(self, ss):
        with pytest.raises(KeyError):
            ss.get("unknown_variable")

    def test_get_not_loaded_raises(self, ss):
        with pytest.raises(KeyError):
            ss.get("price_inflation_eu")  # not in minimal_data

    def test_get_scenario(self, ss):
        row = ss.get_scenario("equity_return", 0)
        assert row.shape == (N_TIMESTEPS_SHORT,)

    def test_get_scenario_out_of_range(self, ss):
        with pytest.raises(IndexError):
            ss.get_scenario("equity_return", N_TEST_SCENARIOS + 1)


class TestDescribe:
    def test_returns_dataframe(self, ss):
        df = ss.describe("equity_return")
        assert isinstance(df, pd.DataFrame)

    def test_index_is_time(self, ss):
        df = ss.describe("equity_return")
        assert df.index.name == "t"
        assert len(df) == N_TIMESTEPS_SHORT

    def test_has_mean_std_min_max(self, ss):
        df = ss.describe("equity_return")
        for col in ("mean", "std", "min", "max"):
            assert col in df.columns

    def test_has_percentile_columns(self, ss):
        df = ss.describe("equity_return", percentiles=[25.0, 75.0])
        assert "p25" in df.columns
        assert "p75" in df.columns

    def test_mean_between_min_max(self, ss):
        df = ss.describe("equity_return")
        assert (df["mean"] >= df["min"]).all()
        assert (df["mean"] <= df["max"]).all()


class TestPercentilePaths:
    def test_returns_dataframe(self, ss):
        df = ss.percentile_paths("equity_return")
        assert isinstance(df, pd.DataFrame)

    def test_columns_match_percentiles(self, ss):
        pcts = [10.0, 90.0]
        df = ss.percentile_paths("equity_return", percentiles=pcts)
        assert list(df.columns) == ["p10", "p90"]


class TestMeanPath:
    def test_returns_series(self, ss):
        s = ss.mean_path("equity_return")
        assert isinstance(s, pd.Series)
        assert len(s) == N_TIMESTEPS_SHORT


class TestYieldCurve:
    @pytest.fixture()
    def ss_with_phi_psi(self):
        data = make_data_dict(
            variables=[
                "state_variable_1", "state_variable_2", "state_variable_3",
                "phi_nominal", "psi_nominal",
            ]
        )
        return ScenarioSet(data=data, set_type="P")

    def test_yield_curve_returns_dataframe(self, ss_with_phi_psi):
        df = ss_with_phi_psi.yield_curve(t=0, maturities=[1, 5, 10])
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == [1, 5, 10]
        assert df.shape[0] == N_TEST_SCENARIOS

    def test_mean_yield_curve_returns_series(self, ss_with_phi_psi):
        s = ss_with_phi_psi.mean_yield_curve(t=0, maturities=[1, 5, 10])
        assert isinstance(s, pd.Series)
        assert list(s.index) == [1, 5, 10]

    def test_invalid_measure_raises(self, ss_with_phi_psi):
        with pytest.raises(ValueError, match="measure must be"):
            ss_with_phi_psi.yield_curve(t=0, measure="invalid")

    def test_missing_state_vars_raises(self):
        data = make_data_dict(variables=["phi_nominal", "psi_nominal"])
        ss = ScenarioSet(data=data, set_type="P")
        with pytest.raises(KeyError, match="State variables"):
            ss.yield_curve(t=0)

    def test_missing_phi_raises(self):
        data = make_data_dict(
            variables=[
                "state_variable_1", "state_variable_2", "state_variable_3",
            ]
        )
        ss = ScenarioSet(data=data, set_type="P")
        with pytest.raises(KeyError):
            ss.yield_curve(t=0)


class TestSummary:
    def test_summary_contains_set_type(self, ss):
        s = ss.summary()
        assert "P-set" in s or "P" in s

    def test_summary_contains_variables(self, ss):
        s = ss.summary()
        assert "equity_return" in s
