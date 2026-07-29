"""
Fixtures and helpers shared across tests.

The tests do NOT use real DNB CSV files (which are large and cannot be
redistributed).  Instead, helper functions here generate synthetic data
with the same block structure as the real files, but using far fewer
scenarios so tests run fast.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dnb_p_set.constants import BLOCKS, N_SCENARIOS, BlockSpec

# Use a tiny number of scenarios in tests to keep them fast
N_TEST_SCENARIOS = 500
SMALL_BLOCKS: dict[str, BlockSpec] = BLOCKS


def make_block_array(block: BlockSpec, n_scenarios: int = N_TEST_SCENARIOS) -> np.ndarray:
    """Generate a reproducible random array for *block*."""
    rng = np.random.default_rng(seed=hash(block.name) & 0xFFFFFFFF)
    n_rows = n_scenarios if block.n_rows == N_SCENARIOS else block.n_rows
    return rng.standard_normal((n_rows, block.n_cols)).astype(np.float64)


def make_data_dict(
    variables: list[str] | None = None,
    n_scenarios: int = N_TEST_SCENARIOS,
    include_q_only: bool = False,
) -> dict[str, np.ndarray]:
    """Build a synthetic data dict compatible with :class:`~dnb_p_set.ScenarioSet`."""
    result = {}
    for name, spec in BLOCKS.items():
        if variables is not None and name not in variables:
            continue
        if not include_q_only and not spec.p_set:
            continue
        result[name] = make_block_array(spec, n_scenarios=n_scenarios)
    return result


@pytest.fixture()
def p_set_data():
    """Synthetic P-set data dict."""
    return make_data_dict(
        variables=[
            "state_variable_1", "state_variable_2", "state_variable_3",
            "equity_return", "price_inflation_eu", "price_inflation_nl",
            "phi_nominal", "psi_nominal",
        ],
    )


@pytest.fixture()
def q_set_data():
    """Synthetic Q-set data dict with stochastic discount factor."""
    data = make_data_dict(include_q_only=True)
    return data


def write_synthetic_csv(
    path: Path,
    variables: list[str] | None = None,
    n_scenarios: int = N_TEST_SCENARIOS,
    set_type: str = "P",
) -> None:
    """Write a synthetic DNB CSV to *path*.

    The file has no header row.  Blocks are written in row-order matching
    :data:`~dnb_p_set.constants.BLOCKS`.  Blocks that are not in *variables*
    are skipped and the file will therefore be shorter than a real DNB file;
    the loader is not affected because it uses absolute ``skiprows`` offsets.

    .. warning::
        This helper is only suitable for unit tests; it does not produce a
        file layout identical to real DNB files when *variables* is a subset.
    """
    raise NotImplementedError(
        "write_synthetic_csv is not used directly because the loader "
        "requires the full row layout.  Use make_data_dict + ScenarioSet() "
        "instead of loading from CSV in unit tests."
    )
