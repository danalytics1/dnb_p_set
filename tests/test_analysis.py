"""Tests for dnb_p_set.analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dnb_p_set import analysis
from tests.conftest import make_block_array, N_TEST_SCENARIOS
from dnb_p_set.constants import BLOCKS


@pytest.fixture()
def equity_arr():
    return make_block_array(BLOCKS["equity_return"], n_scenarios=N_TEST_SCENARIOS)


class TestCumulativeReturn:
    def test_shape(self, equity_arr):
        result = analysis.cumulative_return(equity_arr)
        assert result.shape == equity_arr.shape

    def test_positive(self, equity_arr):
        # cumulative factor must be positive
        result = analysis.cumulative_return(equity_arr)
        assert (result > 0).all()

    def test_first_column(self, equity_arr):
        # First col = exp(first period log return)
        expected = np.exp(equity_arr[:, 0])
        np.testing.assert_allclose(
            analysis.cumulative_return(equity_arr)[:, 0], expected
        )


class TestAnnualisedReturn:
    def test_shape(self, equity_arr):
        result = analysis.annualised_return(equity_arr)
        assert result.shape == equity_arr.shape

    def test_first_year(self, equity_arr):
        # At t=0 (year 1): annualised == period return
        expected = np.exp(equity_arr[:, 0]) - 1.0
        np.testing.assert_allclose(
            analysis.annualised_return(equity_arr)[:, 0], expected
        )


class TestDescribeVariable:
    def test_returns_dataframe(self, equity_arr):
        df = analysis.describe_variable(equity_arr)
        assert isinstance(df, pd.DataFrame)

    def test_index_length(self, equity_arr):
        df = analysis.describe_variable(equity_arr)
        assert len(df) == equity_arr.shape[1]

    def test_required_columns_present(self, equity_arr):
        df = analysis.describe_variable(equity_arr)
        for col in ("mean", "std", "min", "max"):
            assert col in df.columns

    def test_custom_percentiles(self, equity_arr):
        df = analysis.describe_variable(equity_arr, percentiles=[1.0, 99.0])
        assert "p1" in df.columns
        assert "p99" in df.columns

    def test_min_leq_max(self, equity_arr):
        df = analysis.describe_variable(equity_arr)
        assert (df["min"] <= df["max"]).all()


class TestProbabilityExceeds:
    def test_above_max_is_zero(self, equity_arr):
        threshold = equity_arr.max() + 1
        result = analysis.probability_exceeds(equity_arr, threshold)
        assert (result == 0).all()

    def test_below_min_is_one(self, equity_arr):
        threshold = equity_arr.min() - 1
        result = analysis.probability_exceeds(equity_arr, threshold)
        assert (result == 1).all()

    def test_shape(self, equity_arr):
        result = analysis.probability_exceeds(equity_arr, 0.0)
        assert result.shape == (equity_arr.shape[1],)


class TestProbabilityBelow:
    def test_complementary(self, equity_arr):
        """P(X > t) + P(X < t) should sum to ≈ 1 for continuous distributions."""
        threshold = 0.0
        above = analysis.probability_exceeds(equity_arr, threshold)
        below = analysis.probability_below(equity_arr, threshold)
        total = above + below
        # Not exact because the threshold may be hit
        assert (total <= 1.0 + 1e-9).all()


class TestValueAtRisk:
    def test_shape(self, equity_arr):
        result = analysis.value_at_risk(equity_arr)
        assert result.shape == (equity_arr.shape[1],)

    def test_invalid_confidence(self, equity_arr):
        with pytest.raises(ValueError):
            analysis.value_at_risk(equity_arr, confidence=1.5)

    def test_var_95_geq_var_99(self, equity_arr):
        var95 = analysis.value_at_risk(equity_arr, confidence=0.95)
        var99 = analysis.value_at_risk(equity_arr, confidence=0.99)
        # Higher confidence → larger (worse) VaR
        assert (var99 >= var95 - 1e-9).all()


class TestExpectedShortfall:
    def test_shape(self, equity_arr):
        result = analysis.expected_shortfall(equity_arr)
        assert result.shape == (equity_arr.shape[1],)

    def test_es_geq_var(self, equity_arr):
        var = analysis.value_at_risk(equity_arr, confidence=0.95)
        es = analysis.expected_shortfall(equity_arr, confidence=0.95)
        # ES ≥ VaR by construction
        assert (es >= var - 1e-9).all()

    def test_invalid_confidence(self, equity_arr):
        with pytest.raises(ValueError):
            analysis.expected_shortfall(equity_arr, confidence=0.0)


class TestCorrelationMatrix:
    def test_is_dataframe(self):
        rng = np.random.default_rng(0)
        arrays = {
            "a": rng.standard_normal((N_TEST_SCENARIOS, 10)),
            "b": rng.standard_normal((N_TEST_SCENARIOS, 10)),
        }
        df = analysis.correlation_matrix(arrays, t=0)
        assert isinstance(df, pd.DataFrame)

    def test_diagonal_is_one(self):
        rng = np.random.default_rng(0)
        arrays = {
            "a": rng.standard_normal((N_TEST_SCENARIOS, 10)),
            "b": rng.standard_normal((N_TEST_SCENARIOS, 10)),
        }
        df = analysis.correlation_matrix(arrays, t=0)
        np.testing.assert_allclose(np.diag(df.values), 1.0)

    def test_symmetric(self):
        rng = np.random.default_rng(1)
        arrays = {
            "x": rng.standard_normal((N_TEST_SCENARIOS, 10)),
            "y": rng.standard_normal((N_TEST_SCENARIOS, 10)),
        }
        df = analysis.correlation_matrix(arrays, t=0)
        np.testing.assert_allclose(df.values, df.values.T)
