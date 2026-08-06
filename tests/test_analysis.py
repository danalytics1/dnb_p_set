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
    """Plausible simple annual equity returns (DNB calibration order of magnitude)."""
    raw = make_block_array(BLOCKS["equity_return"], n_scenarios=N_TEST_SCENARIOS)
    return 0.066 + 0.15 * raw


class TestCumulativeReturn:
    def test_shape(self, equity_arr):
        result = analysis.cumulative_return(equity_arr)
        assert result.shape == equity_arr.shape

    def test_positive(self, equity_arr):
        # cumulative factor must be positive
        result = analysis.cumulative_return(equity_arr)
        assert (result > 0).all()

    def test_first_column_is_simple_compounding(self, equity_arr):
        # DNB stores simple returns, so the first factor is 1 + r
        expected = 1.0 + equity_arr[:, 0]
        np.testing.assert_allclose(
            analysis.cumulative_return(equity_arr)[:, 0], expected
        )

    def test_log_returns_opt_in(self, equity_arr):
        expected = np.exp(equity_arr[:, 0])
        np.testing.assert_allclose(
            analysis.cumulative_return(equity_arr, log_returns=True)[:, 0], expected
        )

    def test_second_column_compounds(self, equity_arr):
        expected = (1.0 + equity_arr[:, 0]) * (1.0 + equity_arr[:, 1])
        np.testing.assert_allclose(
            analysis.cumulative_return(equity_arr)[:, 1], expected
        )


class TestAnnualisedReturn:
    def test_shape(self, equity_arr):
        result = analysis.annualised_return(equity_arr)
        assert result.shape == equity_arr.shape

    def test_first_year(self, equity_arr):
        # At horizon 1 the annualised return is just the period return
        np.testing.assert_allclose(
            analysis.annualised_return(equity_arr)[:, 0], equity_arr[:, 0]
        )

    def test_matches_cumulative(self, equity_arr):
        cumulative = analysis.cumulative_return(equity_arr)
        annualised = analysis.annualised_return(equity_arr)
        horizon = 10
        np.testing.assert_allclose(
            (1.0 + annualised[:, horizon - 1]) ** horizon,
            cumulative[:, horizon - 1],
        )


class TestGeometricMeanReturn:
    def test_below_arithmetic_mean(self, equity_arr):
        # Volatility drag: the geometric mean sits below the arithmetic mean
        assert analysis.geometric_mean_return(equity_arr) < equity_arr.mean()

    def test_constant_return(self):
        arr = np.full((10, 5), 0.05)
        assert analysis.geometric_mean_return(arr) == pytest.approx(0.05)


class TestStandardError:
    def test_shrinks_with_sample_size(self):
        rng = np.random.default_rng(7)
        small = analysis.standard_error(rng.standard_normal((100, 1)))
        large = analysis.standard_error(rng.standard_normal((10_000, 1)))
        assert large[0] < small[0]

    def test_matches_closed_form(self):
        rng = np.random.default_rng(3)
        values = rng.standard_normal((5_000, 1))
        expected = values.std(ddof=0) / np.sqrt(values.shape[0])
        np.testing.assert_allclose(analysis.standard_error(values)[0], expected)


class TestConfidenceIntervals:
    def test_mean_interval_brackets_the_mean(self):
        rng = np.random.default_rng(11)
        values = rng.standard_normal((2_000, 3))
        mean, lower, upper = analysis.mean_confidence_interval(values)
        assert (lower < mean).all()
        assert (mean < upper).all()

    def test_mean_interval_covers_truth(self):
        rng = np.random.default_rng(12)
        values = rng.normal(0.05, 0.15, (50_000, 1))
        _, lower, upper = analysis.mean_confidence_interval(values)
        assert lower[0] < 0.05 < upper[0]

    def test_invalid_alpha(self):
        with pytest.raises(ValueError):
            analysis.mean_confidence_interval(np.zeros((10, 1)), alpha=0.0)

    def test_percentile_interval_brackets_estimate(self):
        rng = np.random.default_rng(13)
        values = rng.standard_normal(20_000)
        estimate, lower, upper = analysis.percentile_confidence_interval(values, 5.0)
        assert lower <= estimate <= upper

    def test_percentile_invalid_p(self):
        with pytest.raises(ValueError):
            analysis.percentile_confidence_interval(np.zeros(10), p=0.0)


class TestDistributionStats:
    def test_expected_keys(self, equity_arr):
        stats = analysis.distribution_stats(equity_arr[:, 0])
        for key in ("mean", "se", "std", "skew", "kurtosis", "var95", "es95", "p50"):
            assert key in stats

    def test_es_at_least_var(self, equity_arr):
        stats = analysis.distribution_stats(equity_arr[:, 0])
        assert stats["es95"] >= stats["var95"]

    def test_normal_sample_has_small_skew(self):
        rng = np.random.default_rng(5)
        stats = analysis.distribution_stats(rng.standard_normal(50_000))
        assert abs(stats["skew"]) < 0.1
        assert abs(stats["kurtosis"]) < 0.1


class TestHistogram:
    def test_density_integrates_to_one(self, equity_arr):
        edges, density = analysis.histogram(equity_arr[:, 0], bins=50)
        assert len(density) == 50
        widths = np.diff(edges)
        assert (density * widths).sum() == pytest.approx(1.0, abs=0.02)

    def test_reuses_supplied_edges(self, equity_arr):
        edges, _ = analysis.histogram(equity_arr[:, 0], bins=30)
        other_edges, density = analysis.histogram(equity_arr[:, 1], edges=edges)
        np.testing.assert_array_equal(edges, other_edges)
        assert len(density) == 30

    def test_constant_sample(self):
        edges, density = analysis.histogram(np.full(100, 0.02), bins=10)
        assert len(density) == 10
        assert np.isfinite(edges).all()


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
