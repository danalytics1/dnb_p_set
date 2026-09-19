"""Tests for dnb_p_set.metrics and the HTML report it feeds."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dnb_p_set import ScenarioSet, build_html_report, compute_metrics
from dnb_p_set.constants import RETURN_HORIZONS
from dnb_p_set.lifecycle import DEFAULT_MAATMENSEN, Maatmens
from dnb_p_set.metrics import ScenarioMetrics

N_SCEN = 300
N_T = 21   # projection years 0 … 20
N_Y = 20   # 20 one-year returns


def make_set(seed: int, shift: float = 0.0, label: str = "set") -> ScenarioSet:
    """Build a small but structurally realistic synthetic P-set."""
    rng = np.random.default_rng(seed)

    data = {}
    for i, base in enumerate([0.030, 0.011, 0.012]):
        arr = np.empty((N_SCEN, N_T))
        arr[:, 0] = base + shift          # deterministic start, as in real sets
        for t in range(1, N_T):
            arr[:, t] = 0.95 * arr[:, t - 1] + 0.05 * base + rng.normal(0, 0.004, N_SCEN)
        data[f"state_variable_{i + 1}"] = arr

    tau = np.arange(1, 101, dtype=float)
    psi = np.column_stack([0.07 * tau, -0.98 * tau, -0.036 * tau])
    phi = np.tile((-0.017 * tau)[:, None], (1, N_T))
    data["phi_nominal"] = phi
    data["psi_nominal"] = psi
    data["phi_real_eu"] = phi * 0.55
    data["phi_real_nl"] = phi * 0.52
    data["psi_real"] = psi * 0.6

    data["equity_return"] = rng.normal(0.066 + shift, 0.149, (N_SCEN, N_Y))
    data["price_inflation_eu"] = rng.normal(0.020 + shift, 0.012, (N_SCEN, N_Y))
    data["price_inflation_nl"] = rng.normal(0.021 + shift, 0.013, (N_SCEN, N_Y))
    return ScenarioSet(data=data, set_type="P", source_path=f"{label}.csv")


@pytest.fixture(scope="module")
def current():
    return compute_metrics(make_set(1, label="current"), label="2026Q3")


@pytest.fixture(scope="module")
def previous(current):
    return compute_metrics(
        make_set(2, shift=-0.002, label="previous"), label="2026Q2", reference=current
    )


class TestBundle:
    def test_is_scenario_metrics(self, current):
        assert isinstance(current, ScenarioMetrics)

    def test_label_and_shape(self, current):
        assert current.label == "2026Q3"
        assert current.n_scenarios == N_SCEN
        assert current.n_years == N_Y

    def test_label_falls_back_to_filename(self):
        bundle = compute_metrics(make_set(3, label="fallback"))
        assert bundle.label == "fallback"

    def test_all_curves_present(self, current):
        assert set(current.curves) == {"nominal", "real_eu", "real_nl"}

    def test_all_series_present(self, current):
        assert set(current.series) == {"equity", "inflation_nl", "inflation_eu"}


class TestCurveMetrics:
    def test_start_is_deterministic(self, current):
        assert current.curves["nominal"].deterministic_start

    def test_spot_matches_yield_curve_method(self, current):
        scenario_set = make_set(1, label="current")
        curve = current.curves["nominal"]
        expected = scenario_set.yield_curve(
            t=0, maturities=list(curve.maturities)
        ).iloc[0]
        np.testing.assert_allclose(curve.spot.to_numpy(), expected.to_numpy())

    def test_percentiles_are_ordered(self, current):
        frame = current.curves["nominal"].by_horizon[10]
        assert (frame["p5"] <= frame["p50"]).all()
        assert (frame["p50"] <= frame["p95"]).all()

    def test_paths_cover_every_projection_year(self, current):
        for frame in current.curves["nominal"].paths.values():
            assert len(frame) == N_T

    def test_horizons_beyond_the_projection_are_dropped(self, current):
        assert max(current.curves["nominal"].by_horizon) < N_T


class TestSeriesMetrics:
    def test_annualised_covers_every_horizon(self, current):
        assert list(current.series["equity"].annualised.index) == list(range(1, N_Y + 1))

    def test_first_horizon_equals_first_year(self, current):
        series = current.series["equity"]
        assert series.annualised.loc[1, "mean"] == pytest.approx(
            series.annual.loc[1, "mean"]
        )

    def test_geometric_below_arithmetic(self, current):
        series = current.series["equity"]
        assert series.geometric_mean < series.arithmetic_mean

    def test_spread_narrows_with_horizon(self, current):
        annualised = current.series["equity"].annualised
        short = annualised.loc[1, "p95"] - annualised.loc[1, "p5"]
        long = annualised.loc[N_Y, "p95"] - annualised.loc[N_Y, "p5"]
        assert long < short

    def test_stats_for_each_key_horizon(self, current):
        expected = {h for h in RETURN_HORIZONS if h <= N_Y}
        assert set(current.series["equity"].stats) == expected

    def test_histogram_bins_are_shared_with_reference(self, current, previous):
        np.testing.assert_array_equal(
            current.series["equity"].hist_year1[0],
            previous.series["equity"].hist_year1[0],
        )


class TestDerivedFrames:
    def test_breakeven_satisfies_fisher(self, current):
        frame = current.breakeven
        np.testing.assert_allclose(
            (1 + frame["reeel_nl"]) * (1 + frame["bei_nl"]), 1 + frame["nominaal"]
        )

    def test_liability_pv_and_duration_are_sensible(self, current):
        row = current.liability.loc[0]
        assert 0 < row["pv_mean"] < 60
        assert 1 < row["duration_mean"] < 60

    def test_correlation_matrix_is_square_with_unit_diagonal(self, current):
        matrix = current.correlations
        assert matrix.shape[0] == matrix.shape[1]
        np.testing.assert_allclose(np.diag(matrix.to_numpy()), 1.0)


class TestLifecycleMetrics:
    def test_bundle_is_present(self, current):
        assert current.lifecycle is not None

    def test_basisjaar_is_read_from_the_label(self, current):
        assert current.lifecycle.basisjaar == 2026

    def test_one_entry_per_maatmens(self, current):
        assert len(current.lifecycle.people) == len(DEFAULT_MAATMENSEN)

    def test_horizons_are_capped_by_the_projection(self, current):
        assert max(current.lifecycle.horizons) <= N_Y

    def test_every_person_covers_every_horizon(self, current):
        for person in current.lifecycle.people:
            assert set(person.horizons) == set(current.lifecycle.horizons)

    def test_allocation_spans_every_starting_age(self, current):
        allocation = current.lifecycle.allocation
        for person in current.lifecycle.people:
            assert person.startleeftijd in allocation.index

    def test_protection_earns_less_than_return_portfolio(self, current):
        returns = current.lifecycle.returns
        assert returns.loc["bescherming", "meetkundig"] < returns.loc[
            "rendement", "meetkundig"
        ]

    def test_wealth_starts_at_the_opening_capital(self, current):
        for person in current.lifecycle.people:
            assert person.paths.loc[0, "p50"] == pytest.approx(
                person.maatmens.pensioenvermogen
            )

    def test_empty_maatmensen_skips_the_bundle(self):
        bundle = compute_metrics(make_set(5, label="leeg"), maatmensen=[])
        assert bundle.lifecycle is None

    def test_gerealiseerd_is_none_without_realised_returns(self, current):
        # The `current` fixture never supplies gerealiseerde_returns, so any
        # network fetch fails in this offline test environment and every
        # person's realised path stays unset rather than crashing the build.
        for person in current.lifecycle.people:
            assert person.gerealiseerd is None
        assert current.lifecycle.gerealiseerd_note

    def test_gerealiseerd_wealth_when_returns_are_supplied(self):
        jaren = range(2018, 2027)
        rendement = pd.Series({j: 0.08 for j in jaren})
        bescherming = pd.Series({j: 0.02 for j in jaren})
        maatmens = Maatmens(
            "Starter", 2001, 5_000, 34_000, invaardatum="2020-01-01"
        )
        bundle = compute_metrics(
            make_set(6, label="gerealiseerd"),
            maatmensen=[maatmens],
            gerealiseerde_returns=(rendement, bescherming),
            basisjaar=2026,
        )
        person = bundle.lifecycle.people[0]
        assert person.gerealiseerd is not None
        assert person.gerealiseerd.loc[0, "vermogen"] == pytest.approx(5_000)
        assert person.gerealiseerd["vermogen"].is_monotonic_increasing
        assert bundle.lifecycle.gerealiseerd_note == ""
        assert len(bundle.lifecycle.gerealiseerde_portefeuilles) == 2

    def test_projection_is_anchored_on_the_last_realised_point(self):
        # Invaardatum 1-1-2026 with one realised year (2026): the projection
        # must start where the realised path stops, not at the opening
        # capital, so the fan continues the line instead of restarting it.
        rendement = pd.Series({2026: 0.08})
        bescherming = pd.Series({2026: 0.02})
        maatmens = Maatmens(
            "Starter", 2001, 5_000, 34_000, invaardatum="2026-01-01"
        )
        bundle = compute_metrics(
            make_set(10, label="anker"),
            maatmensen=[maatmens],
            gerealiseerde_returns=(rendement, bescherming),
            basisjaar=2026,
        )
        person = bundle.lifecycle.people[0]
        laatste = person.gerealiseerd.iloc[-1]

        assert person.ankerjaar == int(laatste["kalenderjaar"]) == 2027
        assert person.ankervermogen == pytest.approx(float(laatste["vermogen"]))
        assert person.paths.loc[0, "p50"] == pytest.approx(person.ankervermogen)
        assert person.startleeftijd == maatmens.leeftijd(2027)

    def test_anchor_falls_back_to_the_base_year_without_realised_data(self):
        bundle = compute_metrics(
            make_set(11, label="geen-anker"), fetch_gerealiseerd_rendement=False
        )
        for person in bundle.lifecycle.people:
            assert person.ankerjaar == bundle.lifecycle.basisjaar
            assert person.ankervermogen == pytest.approx(
                person.maatmens.pensioenvermogen
            )

    def test_fetch_disabled_skips_gerealiseerd_without_a_note(self):
        bundle = compute_metrics(
            make_set(7, label="geen-fetch"), fetch_gerealiseerd_rendement=False
        )
        for person in bundle.lifecycle.people:
            assert person.gerealiseerd is None
        assert bundle.lifecycle.gerealiseerd_note == ""


class TestMaatmensGerealiseerdRendementChart:
    def test_raises_without_any_realised_data(self, current):
        from dnb_p_set import charts

        with pytest.raises(ValueError):
            charts.maatmens_gerealiseerd_rendement(current)

    def test_returns_a_figure_with_injected_data(self):
        from dnb_p_set import charts

        jaren = range(2018, 2027)
        rendement = pd.Series({j: 0.08 for j in jaren})
        bescherming = pd.Series({j: 0.02 for j in jaren})
        bundle = compute_metrics(
            make_set(9, label="gerealiseerd-chart"),
            maatmensen=[
                Maatmens("Starter", 2001, 5_000, 34_000, invaardatum="2020-01-01")
            ],
            gerealiseerde_returns=(rendement, bescherming),
            basisjaar=2026,
        )
        fig = charts.maatmens_gerealiseerd_rendement(bundle)
        assert fig.axes[0].lines


class TestMaatmensWealthFan:
    def test_no_realised_line_without_realised_data(self, current):
        # Offline the fetch fails, so the fan starts at the base year and no
        # realised line is drawn.
        from dnb_p_set import charts

        fig = charts.maatmens_wealth_fan(current)
        ax = fig.axes[0]
        assert ax.get_xlabel() == "Kalenderjaar"
        assert "gerealiseerd" not in ax.get_legend_handles_labels()[1]
        person = current.lifecycle.people[0]
        assert ax.lines[0].get_xdata()[0] == person.ankerjaar

    def test_realised_line_precedes_the_fan(self):
        from dnb_p_set import charts

        rendement = pd.Series({2026: 0.08})
        bescherming = pd.Series({2026: 0.02})
        bundle = compute_metrics(
            make_set(12, label="waaier-gerealiseerd"),
            maatmensen=[
                Maatmens("Starter", 2001, 5_000, 34_000, invaardatum="2026-01-01")
            ],
            gerealiseerde_returns=(rendement, bescherming),
            basisjaar=2026,
        )
        person = bundle.lifecycle.people[0]
        fig = charts.maatmens_wealth_fan(bundle)
        ax = fig.axes[0]

        assert ax.get_xlabel() == "Kalenderjaar"
        lines = dict(zip(*reversed(ax.get_legend_handles_labels())))
        assert "gerealiseerd" in lines

        realised_x = lines["gerealiseerd"].get_xdata()
        assert realised_x[0] == person.maatmens.invaardatum.year
        assert realised_x[-1] == person.ankerjaar
        # The fan picks up exactly where the realised line ends.
        assert lines["mediaan"].get_xdata()[0] == person.ankerjaar
        assert lines["gerealiseerd"].get_ydata()[-1] == pytest.approx(
            lines["mediaan"].get_ydata()[0]
        )


class TestKpis:
    def test_kpis_exist(self, current):
        assert current.kpis

    def test_known_keys_present(self, current):
        for key in ("spot_nominal_10y", "equity_geo_mean", "liability_duration"):
            assert current.kpi(key) is not None

    def test_unknown_key_returns_none(self, current):
        assert current.kpi("does_not_exist") is None

    def test_net_return_is_below_gross(self, current):
        assert (
            current.kpi("equity_geo_mean_net").value
            < current.kpi("equity_geo_mean").value
        )

    def test_both_sets_expose_the_same_keys(self, current, previous):
        assert set(current.kpis) == set(previous.kpis)


# Rendering a full report means drawing a dozen matplotlib figures, so both
# variants are built once for the whole module.
@pytest.fixture(scope="module")
def comparison_html(current, previous):
    return build_html_report(current, previous)


@pytest.fixture(scope="module")
def single_html(current):
    return build_html_report(current)


class TestReport:
    def test_comparison_report_is_valid_html(self, comparison_html):
        assert comparison_html.startswith("<!DOCTYPE html>")
        assert comparison_html.rstrip().endswith("</html>")

    def test_report_embeds_charts(self, comparison_html):
        assert comparison_html.count("data:image/png;base64,") >= 10

    def test_report_mentions_both_labels(self, comparison_html):
        assert "2026Q3" in comparison_html
        assert "2026Q2" in comparison_html

    def test_report_shows_basis_point_deltas(self, comparison_html):
        assert " bp" in comparison_html

    def test_report_without_previous_set(self, single_html):
        assert "geen vergelijking" in single_html
        assert single_html.rstrip().endswith("</html>")

    def test_single_report_has_no_delta_columns(self, single_html):
        assert "Δ (bp)" not in single_html

    def test_custom_title(self, current):
        html = build_html_report(current, title="Mijn rapport")
        assert "<title>Mijn rapport</title>" in html

    def test_accepts_raw_scenario_sets(self):
        html = build_html_report(make_set(4, label="raw"))
        assert html.startswith("<!DOCTYPE html>")

    def test_every_section_is_present(self, comparison_html):
        for anchor in (
            "kern", "rente", "aandelen", "inflatie-nl", "inflatie-eu",
            "verplichtingen", "correlaties", "maatmens",
        ):
            assert f'id="{anchor}"' in comparison_html

    def test_lifecycle_section_names_every_maatmens(self, comparison_html):
        for mens in DEFAULT_MAATMENSEN:
            assert mens.naam in comparison_html

    def test_lifecycle_section_reports_every_horizon(self, comparison_html):
        section = comparison_html[comparison_html.index('id="maatmens"'):]
        for horizon in (1, 10, 20):
            assert f"{horizon} jaar" in section
            # The horizon column also names the calendar year it lands in.
            assert f"<td>{horizon} jr (" in section

    def test_lifecycle_section_shows_euro_amounts(self, comparison_html):
        assert "€ " in comparison_html

    def test_lifecycle_section_is_last(self, comparison_html):
        assert comparison_html.index('id="maatmens"') > comparison_html.index(
            'id="correlaties"'
        )

    def test_lockstep_pairs_are_flagged(self, comparison_html):
        # The fixture's psi is proportional to the maturity, so every point on
        # the curve moves identically and the 1y/10y changes are perfectly
        # correlated.  The report must say so rather than show a silent 1.00.
        assert "bewegen vrijwel" in comparison_html
        assert "10j-rente" in comparison_html

    def test_gerealiseerd_section_shows_fallback_note_without_network(
        self, comparison_html
    ):
        # `comparison_html` is built from the module-scoped `current`/`previous`
        # fixtures, which never inject gerealiseerde_returns; offline in this
        # test environment the fetch fails and the report must show the note
        # instead of crashing.
        section = comparison_html[comparison_html.index('id="maatmens"'):]
        assert "Gerealiseerd rendement" in section

    def test_gerealiseerd_section_renders_chart_and_table_with_injected_data(self):
        jaren = range(2018, 2027)
        rendement = pd.Series({j: 0.08 for j in jaren})
        bescherming = pd.Series({j: 0.02 for j in jaren})
        bundle = compute_metrics(
            make_set(8, label="gerealiseerd-report"),
            maatmensen=[
                Maatmens("Starter", 2001, 5_000, 34_000, invaardatum="2020-01-01")
            ],
            gerealiseerde_returns=(rendement, bescherming),
            basisjaar=2026,
        )
        html = build_html_report(bundle)
        section = html[html.index('id="maatmens"'):]
        assert "Gerealiseerd rendement" in section
        assert "MSCI World" in section
        assert "risicovrije rente" in section.lower()
