"""Shared fixtures for the market-implied test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from market_implied import build_expectations, load_market_snapshot, load_universe

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="session")
def snapshot_path() -> Path:
    return DATA_DIR / "market_snapshot_example.json"


@pytest.fixture(scope="session")
def universe_path() -> Path:
    return DATA_DIR / "universe_default.json"


@pytest.fixture
def snapshot(snapshot_path):
    return load_market_snapshot(snapshot_path)


@pytest.fixture
def universe(universe_path):
    return load_universe(universe_path)


@pytest.fixture
def result(snapshot, universe):
    return build_expectations(snapshot, universe)
