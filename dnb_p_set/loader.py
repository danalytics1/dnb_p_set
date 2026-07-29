"""
CSV loader for DNB scenario set files.

The DNB scenario set CSV has no header row.  It is a large numeric matrix
where different variable blocks are stacked vertically according to
:mod:`dnb_p_set.constants`.

Usage
-----
>>> from dnb_p_set.loader import load_csv
>>> data = load_csv("path/to/DNB_P_scenarioset_2024Q1.csv")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from .constants import BLOCKS, BlockSpec, N_SCENARIOS

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


def load_block(
    path: PathLike,
    block: BlockSpec,
    dtype: np.dtype = np.float64,
) -> np.ndarray:
    """Load a single variable block from the CSV file.

    Parameters
    ----------
    path:
        Path to the CSV file.
    block:
        :class:`~dnb_p_set.constants.BlockSpec` describing the block to load.
    dtype:
        NumPy dtype for the loaded data.

    Returns
    -------
    np.ndarray
        2-D array with shape ``(n_rows, n_cols)`` as specified in *block*.
    """
    path = Path(path)
    logger.debug(
        "Loading block '%s' from '%s' (rows %d-%d)",
        block.name,
        path.name,
        block.row_start,
        block.row_end,
    )
    df = pd.read_csv(
        path,
        header=None,
        skiprows=block.row_start - 1,
        nrows=block.n_rows,
        usecols=range(block.n_cols),
        dtype=dtype,
        engine="c",
    )
    return df.to_numpy(dtype=dtype)


def detect_set_type(path: PathLike) -> str:
    """Heuristically detect whether a file is a P-set or Q-set.

    The detection is based on the file name.  If the name contains ``"Q_"``
    or ``"_Q"`` (case-insensitive) it is treated as a Q-set; otherwise a
    P-set is assumed.

    Parameters
    ----------
    path:
        Path to the CSV file.

    Returns
    -------
    str
        ``"P"`` or ``"Q"``.
    """
    stem = Path(path).stem.upper()
    if "_Q_" in stem or stem.endswith("_Q") or "_QSET" in stem or "Q-SET" in stem:
        return "Q"
    return "P"


def load_csv(
    path: PathLike,
    set_type: str | None = None,
    variables: list[str] | None = None,
    dtype: np.dtype = np.float64,
) -> dict[str, np.ndarray]:
    """Load a DNB scenario-set CSV file into a dictionary of NumPy arrays.

    Only the requested *variables* (block names) are read from disk, so you
    can keep memory usage low by specifying only what you need.

    Parameters
    ----------
    path:
        Path to the CSV file.
    set_type:
        ``"P"`` or ``"Q"``.  When *None* (default) the type is inferred from
        the file name via :func:`detect_set_type`.
    variables:
        List of block names or aliases to load.  If *None*, all blocks that
        are valid for the detected *set_type* are loaded.
    dtype:
        NumPy dtype for the arrays.

    Returns
    -------
    dict[str, np.ndarray]
        Mapping from canonical variable name to array.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    if set_type is None:
        set_type = detect_set_type(path)
    set_type = set_type.upper()
    if set_type not in ("P", "Q"):
        raise ValueError(f"set_type must be 'P' or 'Q', got '{set_type}'")

    from .constants import VARIABLE_ALIASES  # avoid circular import

    # Resolve requested variables
    if variables is None:
        requested = {
            name: spec
            for name, spec in BLOCKS.items()
            if (set_type == "P" and spec.p_set) or (set_type == "Q" and spec.q_set)
        }
    else:
        requested: dict[str, BlockSpec] = {}
        for var in variables:
            canonical = VARIABLE_ALIASES.get(var.lower(), var.lower())
            if canonical not in BLOCKS:
                raise ValueError(
                    f"Unknown variable '{var}'. "
                    f"Available: {list(BLOCKS.keys())}"
                )
            spec = BLOCKS[canonical]
            if set_type == "P" and not spec.p_set:
                logger.warning(
                    "Variable '%s' is not part of the P-set; skipping.", canonical
                )
                continue
            if set_type == "Q" and not spec.q_set:
                logger.warning(
                    "Variable '%s' is not part of the Q-set; skipping.", canonical
                )
                continue
            requested[canonical] = spec

    result: dict[str, np.ndarray] = {}
    for name, spec in requested.items():
        result[name] = load_block(path, spec, dtype=dtype)

    return result
