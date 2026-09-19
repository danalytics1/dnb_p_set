"""
Realised annual returns for the *gerealiseerd rendement* charts, fetched from
free public sources and cached to disk.

* **Rendementsportefeuille** default: MSCI World (total return), fetched from
  Yahoo Finance.
* **Beschermingsportefeuille** default: the euro risk-free (short) rate,
  fetched from the ECB Data Portal.

Both go through the same two steps: an HTTP call turns a raw response into a
:class:`pandas.Series` of *simple* annual returns indexed by calendar year;
a small on-disk cache stores whatever has already been fetched, so repeat
report builds need network access only for years not seen before — and none
at all once the requested range is fully cached.

Nothing here is a DNB prescription: it is a free, swappable default for
"what does the realised portfolio actually invest in". Point
:class:`~dnb_p_set.lifecycle.GerealiseerdePortefeuille.ophalen` at a
different callable to price the portfolio off another index or curve.
"""

from __future__ import annotations

import datetime as _dt
import io
import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)

__all__ = [
    "MarketDataError",
    "DEFAULT_CACHE_DIR",
    "MSCI_WORLD_TICKER",
    "ECB_RISK_FREE_SERIES",
    "ECB_DATA_API",
    "fetch_msci_world_returns",
    "fetch_risk_free_returns",
    "fetch_realised_returns",
]

#: Where fetched series are cached when no ``cache_dir`` is given explicitly.
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "dnb_p_set" / "market_data"

#: Yahoo Finance ticker for the MSCI World index: the iShares Core MSCI World
#: UCITS ETF, a liquid, free, dividend-reinvesting proxy for the index.
MSCI_WORLD_TICKER = "URTH"

#: ECB Data Portal series key for the euro short-term rate (€STR), used as
#: the risk-free proxy for the beschermingsportefeuille.  Written as the Data
#: Portal displays it, dataflow first: :func:`_ecb_data_url` splits it into
#: the ``<dataflow>/<key>`` path the API actually expects.
ECB_RISK_FREE_SERIES = "EST.B.EU000A2X2A25.WT"

#: Entry point of the ECB Data Portal's SDMX 2.1 data service.
ECB_DATA_API = "https://data-api.ecb.europa.eu/service/data"

_REQUEST_TIMEOUT = 10


class MarketDataError(RuntimeError):
    """Raised when realised returns cannot be fetched or parsed."""


def _http_get(url: str, timeout: int = _REQUEST_TIMEOUT) -> bytes:
    """Thin wrapper around :mod:`urllib` so tests can swap out the network call."""
    request = urllib.request.Request(url, headers={"User-Agent": "dnb-p-set/0.2"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        return response.read()


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _cache_file(cache_dir: Optional[Path], name: str) -> Path:
    directory = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{name}.csv"


def _load_cache(path: Path) -> Optional[pd.Series]:
    if not path.exists():
        return None
    try:
        frame = pd.read_csv(path)
        return pd.Series(
            frame["rendement"].to_numpy(dtype=float),
            index=frame["jaar"].to_numpy(dtype=int),
            name="rendement",
        )
    except Exception:  # pragma: no cover - a corrupt cache is simply ignored
        logger.warning("kon cache %s niet lezen, wordt genegeerd", path)
        return None


def _save_cache(path: Path, series: pd.Series) -> None:
    series.sort_index().rename_axis("jaar").rename("rendement").to_frame().to_csv(path)


def _merge_series(cached: Optional[pd.Series], fresh: pd.Series) -> pd.Series:
    """Combine a freshly fetched series with the cache, fresh values winning."""
    if cached is None:
        return fresh.sort_index()
    return fresh.combine_first(cached).sort_index()


def _covers(series: pd.Series, start_year: int, end_year: int) -> bool:
    return set(range(start_year, end_year + 1)).issubset(set(series.index))


# ---------------------------------------------------------------------------
# MSCI World (Yahoo Finance)
# ---------------------------------------------------------------------------


def _annual_returns_from_close(prices: pd.Series) -> pd.Series:
    """Simple annual returns from prices indexed by timestamp.

    Uses the last available price of each calendar year: the final trading
    day for completed years, and the most recent available price for the
    current, still incomplete year — so a report built mid-year gets a
    year-to-date figure for the current year rather than nothing at all.
    """
    prices = prices.dropna().sort_index()
    year_end = prices.groupby(prices.index.year).last()
    returns = year_end.pct_change().dropna()
    returns.index = returns.index.astype(int)
    returns.index.name = None
    returns.name = "rendement"
    return returns


def fetch_msci_world_returns(
    start_year: int,
    end_year: Optional[int] = None,
    *,
    ticker: str = MSCI_WORLD_TICKER,
    cache_dir: Optional[Path] = None,
    refresh: bool = False,
    http_get: Callable[[str], bytes] = _http_get,
) -> pd.Series:
    """Realised annual returns of the rendementsportefeuille default.

    Parameters
    ----------
    start_year, end_year:
        Calendar years to cover (inclusive); *end_year* defaults to the
        current year, which yields a year-to-date return for it.
    ticker:
        Yahoo Finance ticker to fetch.
    cache_dir:
        Directory the on-disk cache lives in; defaults to
        :data:`DEFAULT_CACHE_DIR`.
    refresh:
        Bypass the cache and re-fetch everything.
    http_get:
        Low-level HTTP call; override in tests to avoid real network access.

    Returns
    -------
    pandas.Series
        Simple annual returns indexed by calendar year.
    """
    end_year = int(end_year) if end_year is not None else _dt.date.today().year
    path = _cache_file(cache_dir, f"msci_world_{ticker.lower()}")
    cached = _load_cache(path)
    if not refresh and cached is not None and _covers(cached, start_year, end_year):
        return cached.loc[start_year:end_year]

    period1 = int(_dt.datetime(start_year - 1, 1, 1).timestamp())
    period2 = int(_dt.datetime(end_year, 12, 31).timestamp())
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{ticker}?period1={period1}&period2={period2}&interval=1mo"
    )
    try:
        raw = http_get(url)
        payload = json.loads(raw)
        result = payload["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["adjclose"][0]["adjclose"]
    except Exception as exc:
        if cached is not None:
            logger.warning(
                "kon MSCI World-koersen niet verversen (%s); gecachte data gebruikt",
                exc,
            )
            return cached.loc[cached.index.intersection(range(start_year, end_year + 1))]
        raise MarketDataError(
            f"kon MSCI World-koersen niet ophalen via Yahoo Finance "
            f"({ticker}): {exc}"
        ) from exc

    prices = pd.Series(closes, index=pd.to_datetime(timestamps, unit="s"))
    fresh = _annual_returns_from_close(prices)
    merged = _merge_series(cached, fresh)
    _save_cache(path, merged)
    return merged.loc[merged.index.intersection(range(start_year, end_year + 1))]


# ---------------------------------------------------------------------------
# Risk-free rate (ECB Data Portal)
# ---------------------------------------------------------------------------


def _ecb_data_url(series_key: str, start_period: str, end_period: str) -> str:
    """Build an ECB Data Portal data URL for a series key.

    The API addresses a series as ``<dataflow>/<key>``, while the Data Portal
    shows the same series as one dotted string with the dataflow in front
    (``EST.B.EU000A2X2A25.WT``).  Sending that dotted string as a single path
    segment asks for a dataflow that does not exist and the API answers 404,
    so split off the leading dataflow here.  A key that already contains a
    slash is passed through unchanged.
    """
    if "/" in series_key:
        path = series_key.strip("/")
    else:
        dataflow, _, key = series_key.partition(".")
        if not key:
            raise MarketDataError(
                f"ongeldige ECB-reekssleutel {series_key!r}: verwacht "
                "<dataflow>.<reekssleutel>, bijvoorbeeld EST.B.EU000A2X2A25.WT"
            )
        path = f"{dataflow}/{key}"
    return (
        f"{ECB_DATA_API}/{path}?format=csvdata"
        f"&startPeriod={start_period}&endPeriod={end_period}"
    )


def _short_rate_from_csv(raw: bytes) -> pd.Series:
    """Parse the ECB ``csvdata`` response into a short rate in decimal."""
    frame = pd.read_csv(io.BytesIO(raw))
    missing = {"TIME_PERIOD", "OBS_VALUE"} - set(frame.columns)
    if missing:
        raise ValueError(
            "onverwacht antwoord van de ECB Data Portal, kolommen ontbreken: "
            + ", ".join(sorted(missing))
        )
    rate = pd.Series(
        pd.to_numeric(frame["OBS_VALUE"], errors="coerce").to_numpy(dtype=float)
        / 100.0,
        index=pd.to_datetime(frame["TIME_PERIOD"]),
    ).dropna()
    if rate.empty:
        raise ValueError("de ECB Data Portal gaf geen waarnemingen terug")
    return rate


def _annual_returns_from_short_rate(rate: pd.Series) -> pd.Series:
    """Compound a daily annualised short rate (e.g. €STR, in decimal) to
    simple annual returns, ACT/365.

    The rate is published on business days only, but it earns over the
    calendar days until the next publication: Friday's fixing covers the
    weekend.  Each observation is therefore compounded over that gap — the
    same convention as the ECB's own compounded €STR index — because
    treating every observation as a single day would drop roughly a hundred
    days of interest a year.
    """
    rate = rate.dropna().sort_index()
    if rate.empty:
        empty = pd.Series(dtype=float, name="rendement")
        return empty
    days = pd.Series(
        rate.index.to_series().diff().shift(-1).dt.days.fillna(1.0).to_numpy(),
        index=rate.index,
    ).clip(lower=1.0)
    growth = (1.0 + rate) ** (days / 365.0)
    annual = growth.groupby(growth.index.year).prod() - 1.0
    annual.index = annual.index.astype(int)
    annual.index.name = None
    annual.name = "rendement"
    return annual


def fetch_risk_free_returns(
    start_year: int,
    end_year: Optional[int] = None,
    *,
    series_key: str = ECB_RISK_FREE_SERIES,
    cache_dir: Optional[Path] = None,
    refresh: bool = False,
    http_get: Callable[[str], bytes] = _http_get,
) -> pd.Series:
    """Realised annual returns of the beschermingsportefeuille default.

    Parameters
    ----------
    start_year, end_year:
        Calendar years to cover (inclusive); *end_year* defaults to the
        current year, which yields a year-to-date figure for it.
    series_key:
        ECB Data Portal series key for the short rate, annualised (per cent).
    cache_dir, refresh, http_get:
        See :func:`fetch_msci_world_returns`.

    Returns
    -------
    pandas.Series
        Simple annual returns indexed by calendar year.
    """
    end_year = int(end_year) if end_year is not None else _dt.date.today().year
    path = _cache_file(cache_dir, "ecb_risk_free")
    cached = _load_cache(path)
    if not refresh and cached is not None and _covers(cached, start_year, end_year):
        return cached.loc[start_year:end_year]

    url = _ecb_data_url(
        series_key, f"{start_year - 1}-01-01", f"{end_year}-12-31"
    )
    try:
        raw = http_get(url)
        rate = _short_rate_from_csv(raw)
    except Exception as exc:
        if cached is not None:
            logger.warning(
                "kon risicovrije rente niet verversen (%s); gecachte data gebruikt",
                exc,
            )
            return cached.loc[cached.index.intersection(range(start_year, end_year + 1))]
        raise MarketDataError(
            f"kon risicovrije rente niet ophalen via ECB Data Portal "
            f"({series_key}): {exc}"
        ) from exc

    fresh = _annual_returns_from_short_rate(rate)
    merged = _merge_series(cached, fresh)
    _save_cache(path, merged)
    return merged.loc[merged.index.intersection(range(start_year, end_year + 1))]


def fetch_realised_returns(
    start_year: int,
    end_year: Optional[int] = None,
    *,
    cache_dir: Optional[Path] = None,
    refresh: bool = False,
) -> tuple[pd.Series, pd.Series]:
    """Fetch both legs' realised annual returns in one call.

    Returns
    -------
    tuple[pandas.Series, pandas.Series]
        ``(rendement, bescherming)``, both indexed by calendar year.
    """
    rendement = fetch_msci_world_returns(
        start_year, end_year, cache_dir=cache_dir, refresh=refresh
    )
    bescherming = fetch_risk_free_returns(
        start_year, end_year, cache_dir=cache_dir, refresh=refresh
    )
    return rendement, bescherming
