"""Tests for the reporting layer and the command-line interface."""

from __future__ import annotations

import pytest

from market_implied import markdown_report, premium_table_text, summary_text, write_csv
from market_implied.cli import main
from market_implied.report import format_percent


def test_format_percent():
    assert format_percent(0.0325) == "3.25%"
    assert format_percent(-0.001, 1) == "-0.1%"
    assert format_percent(None) == ""


def test_premium_table_mentions_the_observation_date(result):
    text = premium_table_text(result)
    assert result.snapshot.as_of in text
    assert "Risicopremie 5j" in text and "Risicopremie 15j" in text
    assert "Aandelen ontwikkelde markten" in text


def test_summary_text_has_a_row_per_asset_class_and_horizon(result):
    text = summary_text(result)
    for key in result.order:
        assert result.build_up(key, 5).name in text


def test_markdown_report_contains_the_building_block_tables(result):
    md = markdown_report(result)
    assert md.startswith("# Market-implied rendementsverwachtingen")
    assert "## 1. Risicopremies per beleggingscategorie" in md
    assert "## 2. Opbouw uit bouwstenen" in md
    assert "Kredietopslag (OAS)" in md
    assert "Dividendrendement" in md
    assert "Termijnpremie" in md


def test_markdown_report_states_the_risk_free_rate_per_horizon(result):
    md = markdown_report(result)
    assert "Risicovrije rente (identiek voor alle categorieen)" in md


def test_write_csv_produces_three_files(result, tmp_path):
    paths = write_csv(result, tmp_path)
    assert len(paths) == 3
    assert all(path.exists() and path.stat().st_size > 0 for path in paths)


def test_cli_default_run(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "Risicopremie 5j" in out


@pytest.mark.parametrize("fmt", ["premiums", "summary", "markdown", "blocks"])
def test_cli_supports_every_format(capsys, fmt):
    assert main(["--format", fmt]) == 0
    assert capsys.readouterr().out.strip()


def test_cli_writes_to_a_file(tmp_path):
    out = tmp_path / "nested" / "rapport.md"
    assert main(["--format", "markdown", "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Market-implied")


def test_cli_csv_export(tmp_path):
    assert main(["--csv-dir", str(tmp_path)]) == 0
    assert len(list(tmp_path.glob("*.csv"))) == 3


def test_cli_horizon_and_convention_overrides(capsys):
    assert main(["--horizons", "10", "--rf-convention", "spot", "--no-valuation"]) == 0
    out = capsys.readouterr().out
    assert "Risicopremie 10j" in out
