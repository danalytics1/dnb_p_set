"""Tests for dnb_p_set.reporting."""

from __future__ import annotations

import numpy as np

from dnb_p_set import ScenarioSet
from dnb_p_set.reporting import build_html_report
from tests.conftest import make_data_dict


def test_build_html_report_includes_current_set_details():
    data = make_data_dict(variables=["equity_return", "price_inflation_nl"])
    ss = ScenarioSet(data=data, set_type="P", source_path="current.csv")

    html = build_html_report(ss)

    assert "Huidige set" in html
    assert "current.csv" in html
    assert "equity_return" in html
    assert "price_inflation_nl" in html


def test_build_html_report_includes_difference_section():
    current = make_data_dict(variables=["equity_return"])
    previous = make_data_dict(variables=["equity_return"])
    current["equity_return"] = current["equity_return"] + 1.0

    current_ss = ScenarioSet(data=current, set_type="P", source_path="current.csv")
    previous_ss = ScenarioSet(data=previous, set_type="P", source_path="previous.csv")

    html = build_html_report(current_ss, previous_ss)

    assert "Verschillen ten opzichte van de vorige set" in html
    assert "previous.csv" in html
    assert "gewijzigd" in html
    assert "Delta gemiddelde" in html


def test_build_html_report_marks_new_and_removed_variables():
    current = make_data_dict(variables=["equity_return", "price_inflation_nl"])
    previous = make_data_dict(variables=["equity_return", "price_inflation_eu"])

    html = build_html_report(
        ScenarioSet(data=current, set_type="P"),
        ScenarioSet(data=previous, set_type="P"),
    )

    assert "nieuw in huidige set" in html
    assert "alleen in vorige set" in html
