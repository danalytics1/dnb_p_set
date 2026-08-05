"""Tests for dnb_p_set.reporting.

End-to-end coverage of the rendered report lives in
``tests/test_metrics.py::TestReport``; this file covers the formatting
helpers and the error paths.
"""

from __future__ import annotations

import pandas as pd
import pytest

from dnb_p_set import ScenarioSet
from dnb_p_set.metrics import Kpi
from dnb_p_set.reporting import (
    _direction,
    _fmt_count,
    _fmt_delta,
    _fmt_number,
    _fmt_rate,
    _fmt_value,
    _near_perfect_pairs,
    _table,
    _within_noise,
    build_html_report,
)
from tests.conftest import make_data_dict


class TestNumberFormatting:
    def test_rate_uses_dutch_decimal_comma(self):
        assert _fmt_rate(0.0271) == "2,71%"

    def test_rate_honours_decimals(self):
        assert _fmt_rate(0.0271234, 4) == "2,7123%"

    def test_rate_handles_nan(self):
        assert _fmt_rate(float("nan")) == "–"
        assert _fmt_rate(None) == "–"

    def test_number_uses_dutch_separators(self):
        assert _fmt_number(1234.5) == "1.234,50"

    def test_large_rate_uses_dutch_separators(self):
        assert _fmt_rate(12.3456) == "1.234,56%"

    def test_count_uses_thousands_dots(self):
        assert _fmt_count(100_000) == "100.000"

    def test_value_dispatches_on_unit(self):
        assert _fmt_value(0.03, "rate") == "3,00%"
        assert _fmt_value(21.5, "years") == "21,5 jr"
        assert _fmt_value(21.5, "number") == "21,50"


class TestDeltaFormatting:
    def test_rate_delta_is_basis_points(self):
        assert _fmt_delta(0.0019, "rate") == "+19,0 bp"

    def test_negative_rate_delta(self):
        assert _fmt_delta(-0.0019, "rate") == "-19,0 bp"

    def test_years_delta(self):
        assert _fmt_delta(-0.35, "years") == "-0,35 jr"

    def test_nan_delta(self):
        assert _fmt_delta(float("nan"), "rate") == "–"

    @pytest.mark.parametrize(
        "delta,expected", [(0.01, "up"), (-0.01, "down"), (0.0, "flat")]
    )
    def test_direction(self, delta, expected):
        assert _direction(delta) == expected

    def test_direction_respects_tolerance(self):
        assert _direction(0.5, tolerance=1.0) == "flat"

    def test_direction_of_nan_is_flat(self):
        assert _direction(float("nan")) == "flat"


class TestSignificance:
    def _kpi(self, value, se):
        return Kpi(key="k", label="k", value=value, se=se)

    def test_small_change_is_noise(self):
        assert _within_noise(self._kpi(0.0500, 0.001), self._kpi(0.0505, 0.001)) is True

    def test_large_change_is_signal(self):
        assert _within_noise(self._kpi(0.050, 0.001), self._kpi(0.070, 0.001)) is False

    def test_without_standard_errors_it_is_undecidable(self):
        assert _within_noise(self._kpi(0.05, None), self._kpi(0.06, 0.001)) is None

    def test_missing_kpi_is_undecidable(self):
        assert _within_noise(None, self._kpi(0.06, 0.001)) is None

    def test_zero_standard_error_is_undecidable(self):
        assert _within_noise(self._kpi(0.05, 0.0), self._kpi(0.06, 0.0)) is None


class TestTableRendering:
    def test_renders_headers_and_cells(self):
        html = _table([["a", "1"]], ["kop", "waarde"])
        assert "<th>kop</th>" in html
        assert "<td>a</td>" in html

    def test_applies_cell_classes(self):
        html = _table([["a", "1"]], ["kop", "waarde"], [["", "up"]])
        assert '<td class="up">1</td>' in html

    def test_escapes_headers(self):
        html = _table([["x"]], ["<script>"])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestNearPerfectPairs:
    def _matrix(self, value):
        return pd.DataFrame(
            [[1.0, value], [value, 1.0]], index=["a", "b"], columns=["a", "b"]
        )

    def test_flags_lockstep_pair(self):
        assert _near_perfect_pairs(self._matrix(1.0)) == ["a en b (r = +1,0000)"]

    def test_flags_perfect_negative_pair(self):
        assert _near_perfect_pairs(self._matrix(-1.0)) == ["a en b (r = -1,0000)"]

    def test_ignores_ordinary_correlation(self):
        assert _near_perfect_pairs(self._matrix(0.95)) == []

    def test_never_flags_the_diagonal(self):
        assert _near_perfect_pairs(self._matrix(0.0)) == []

    def test_threshold_is_configurable(self):
        assert _near_perfect_pairs(self._matrix(0.95), threshold=0.9)


class TestIncompleteSets:
    def test_missing_curve_parameters_reports_clearly(self):
        data = make_data_dict(
            variables=[
                "state_variable_1", "state_variable_2", "state_variable_3",
                "equity_return", "price_inflation_eu", "price_inflation_nl",
            ]
        )
        scenario_set = ScenarioSet(data=data, set_type="P", source_path="partial.csv")
        with pytest.raises(KeyError, match="phi_nominal"):
            build_html_report(scenario_set)

    def test_missing_state_variables_reports_clearly(self):
        data = make_data_dict(
            variables=[
                "equity_return", "price_inflation_eu", "price_inflation_nl",
                "phi_nominal", "psi_nominal", "phi_real_eu", "psi_real",
                "phi_real_nl",
            ]
        )
        scenario_set = ScenarioSet(data=data, set_type="P")
        with pytest.raises(KeyError, match="State variables"):
            build_html_report(scenario_set)
