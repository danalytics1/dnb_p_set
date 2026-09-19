"""Tests for dnb_p_set.market_data — realised returns, fetching and caching.

Network access is never exercised: every test injects ``http_get`` so the
low-level HTTP call is fully controlled.
"""

from __future__ import annotations

import datetime as _dt
import json

import pandas as pd
import pytest

from dnb_p_set import market_data


def _yahoo_payload(dates: list[str], closes: list[float]) -> bytes:
    timestamps = [
        int(_dt.datetime.fromisoformat(d).replace(tzinfo=_dt.timezone.utc).timestamp())
        for d in dates
    ]
    return json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "timestamp": timestamps,
                        "indicators": {"adjclose": [{"adjclose": closes}]},
                    }
                ]
            }
        }
    ).encode()


def _ecb_payload(
    start: _dt.date, end: _dt.date, rate_pct: float, *, business_days: bool = False
) -> bytes:
    lines = ["TIME_PERIOD,OBS_VALUE"]
    day = start
    while day <= end:
        if not business_days or day.weekday() < 5:
            lines.append(f"{day.isoformat()},{rate_pct}")
        day += _dt.timedelta(days=1)
    return "\n".join(lines).encode()


class TestFetchMsciWorldReturns:
    def test_computes_annual_returns_from_year_end_closes(self, tmp_path):
        payload = _yahoo_payload(
            ["2020-01-01", "2021-01-01", "2022-01-01"], [100.0, 110.0, 121.0]
        )
        series = market_data.fetch_msci_world_returns(
            2021, 2022, cache_dir=tmp_path, http_get=lambda url: payload
        )
        assert series.loc[2021] == pytest.approx(0.10)
        assert series.loc[2022] == pytest.approx(0.10)

    def test_second_call_is_served_entirely_from_cache(self, tmp_path):
        payload = _yahoo_payload(
            ["2020-01-01", "2021-01-01"], [100.0, 110.0]
        )
        market_data.fetch_msci_world_returns(
            2021, 2021, cache_dir=tmp_path, http_get=lambda url: payload
        )

        def boom(url):
            raise AssertionError("network should not be hit when cache covers the range")

        series = market_data.fetch_msci_world_returns(
            2021, 2021, cache_dir=tmp_path, http_get=boom
        )
        assert series.loc[2021] == pytest.approx(0.10)

    def test_refresh_bypasses_the_cache(self, tmp_path):
        payload = _yahoo_payload(["2020-01-01", "2021-01-01"], [100.0, 110.0])
        market_data.fetch_msci_world_returns(
            2021, 2021, cache_dir=tmp_path, http_get=lambda url: payload
        )
        new_payload = _yahoo_payload(["2020-01-01", "2021-01-01"], [100.0, 130.0])
        series = market_data.fetch_msci_world_returns(
            2021, 2021, cache_dir=tmp_path, refresh=True,
            http_get=lambda url: new_payload,
        )
        assert series.loc[2021] == pytest.approx(0.30)

    def test_raises_market_data_error_when_fetch_fails_and_no_cache(self, tmp_path):
        def boom(url):
            raise OSError("no network")

        with pytest.raises(market_data.MarketDataError):
            market_data.fetch_msci_world_returns(2021, 2021, cache_dir=tmp_path, http_get=boom)

    def test_falls_back_to_cache_when_refresh_fails(self, tmp_path):
        payload = _yahoo_payload(["2020-01-01", "2021-01-01"], [100.0, 110.0])
        market_data.fetch_msci_world_returns(
            2021, 2021, cache_dir=tmp_path, http_get=lambda url: payload
        )

        def boom(url):
            raise OSError("no network")

        series = market_data.fetch_msci_world_returns(
            2021, 2021, cache_dir=tmp_path, refresh=True, http_get=boom
        )
        assert series.loc[2021] == pytest.approx(0.10)


class TestFetchRiskFreeReturns:
    def test_compounds_a_daily_rate_to_an_annual_return(self, tmp_path):
        payload = _ecb_payload(_dt.date(2020, 1, 1), _dt.date(2021, 12, 31), 3.5)
        series = market_data.fetch_risk_free_returns(
            2020, 2021, cache_dir=tmp_path, http_get=lambda url: payload
        )
        # A constant 3.5%/yr short rate compounds close to (but not exactly)
        # 3.5% simple annual return.
        assert series.loc[2020] == pytest.approx(0.0351, abs=1e-3)
        assert series.loc[2021] == pytest.approx(0.0349, abs=1e-3)

    def test_second_call_is_served_entirely_from_cache(self, tmp_path):
        payload = _ecb_payload(_dt.date(2020, 1, 1), _dt.date(2020, 12, 31), 2.0)
        market_data.fetch_risk_free_returns(
            2020, 2020, cache_dir=tmp_path, http_get=lambda url: payload
        )

        def boom(url):
            raise AssertionError("network should not be hit when cache covers the range")

        series = market_data.fetch_risk_free_returns(
            2020, 2020, cache_dir=tmp_path, http_get=boom
        )
        assert 2020 in series.index

    def test_raises_market_data_error_when_fetch_fails_and_no_cache(self, tmp_path):
        def boom(url):
            raise OSError("no network")

        with pytest.raises(market_data.MarketDataError):
            market_data.fetch_risk_free_returns(2020, 2020, cache_dir=tmp_path, http_get=boom)

    def test_requests_the_dataflow_and_key_as_separate_path_segments(self, tmp_path):
        # The ECB API addresses a series as <dataflow>/<key>; sending the
        # dotted key the Data Portal displays as one segment yields a 404.
        seen = []

        def capture(url):
            seen.append(url)
            return _ecb_payload(_dt.date(2019, 1, 1), _dt.date(2020, 12, 31), 2.0)

        market_data.fetch_risk_free_returns(
            2020, 2020, cache_dir=tmp_path, http_get=capture
        )
        assert seen == [
            "https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT"
            "?format=csvdata&startPeriod=2019-01-01&endPeriod=2020-12-31"
        ]

    def test_series_key_with_a_slash_is_passed_through(self, tmp_path):
        seen = []

        def capture(url):
            seen.append(url)
            return _ecb_payload(_dt.date(2019, 1, 1), _dt.date(2020, 12, 31), 2.0)

        market_data.fetch_risk_free_returns(
            2020,
            2020,
            series_key="EST/B.EU000A2X2A25.WT",
            cache_dir=tmp_path,
            http_get=capture,
        )
        assert seen[0].startswith(
            "https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT?"
        )

    def test_rejects_a_series_key_without_a_dataflow(self, tmp_path):
        with pytest.raises(market_data.MarketDataError):
            market_data.fetch_risk_free_returns(
                2020,
                2020,
                series_key="EST",
                cache_dir=tmp_path,
                http_get=lambda url: b"",
            )

    def test_raises_market_data_error_on_a_response_without_observations(self, tmp_path):
        with pytest.raises(market_data.MarketDataError):
            market_data.fetch_risk_free_returns(
                2020,
                2020,
                cache_dir=tmp_path,
                http_get=lambda url: b"TIME_PERIOD,OBS_VALUE\n",
            )

    def test_business_day_quotes_compound_over_the_weekend(self, tmp_path):
        # €STR is published on business days only; each fixing earns until
        # the next one, so a constant 3.5% must still compound to ~3.5% and
        # not to the ~2.4% that counting 255 single days would give.
        payload = _ecb_payload(
            _dt.date(2019, 1, 1), _dt.date(2021, 12, 31), 3.5, business_days=True
        )
        series = market_data.fetch_risk_free_returns(
            2020, 2021, cache_dir=tmp_path, http_get=lambda url: payload
        )
        assert series.loc[2020] == pytest.approx(0.035, abs=2e-3)
        assert series.loc[2021] == pytest.approx(0.035, abs=2e-3)

    def test_skips_rows_without_an_observation_value(self, tmp_path):
        payload = _ecb_payload(_dt.date(2020, 1, 1), _dt.date(2020, 12, 31), 2.0)
        payload += b"\n2020-12-31,"
        series = market_data.fetch_risk_free_returns(
            2020, 2020, cache_dir=tmp_path, http_get=lambda url: payload
        )
        assert series.loc[2020] == pytest.approx(0.0202, abs=1e-3)


class TestFetchRealisedReturns:
    def test_raises_market_data_error_without_network(self, tmp_path):
        # No http_get override is exposed on fetch_realised_returns; without
        # network access the underlying fetchers must fail cleanly.
        with pytest.raises(market_data.MarketDataError):
            market_data.fetch_realised_returns(2020, 2020, cache_dir=tmp_path)

    def test_uses_the_cache_for_both_legs_when_already_populated(self, tmp_path):
        yahoo = _yahoo_payload(["2019-01-01", "2020-01-01"], [100.0, 105.0])
        ecb = _ecb_payload(_dt.date(2019, 1, 1), _dt.date(2020, 12, 31), 1.0)
        market_data.fetch_msci_world_returns(
            2020, 2020, cache_dir=tmp_path, http_get=lambda url: yahoo
        )
        market_data.fetch_risk_free_returns(
            2020, 2020, cache_dir=tmp_path, http_get=lambda url: ecb
        )
        rendement, bescherming = market_data.fetch_realised_returns(
            2020, 2020, cache_dir=tmp_path
        )
        assert isinstance(rendement, pd.Series)
        assert isinstance(bescherming, pd.Series)
        assert 2020 in rendement.index
        assert 2020 in bescherming.index
