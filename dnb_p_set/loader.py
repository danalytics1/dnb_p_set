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


def detect_n_columns(path: PathLike) -> int:
    """Return the number of comma-separated fields on the first data row.

    DNB pads every row to the width of the widest block (101 columns), so
    reading this once lets the chunked loader fix its column names up front.
    """
    with open(path, "r", encoding="utf-8") as handle:
        first = handle.readline()
    if not first.strip():
        raise ValueError(f"CSV file appears to be empty: {path}")
    return first.count(",") + 1


def load_blocks(
    path: PathLike,
    blocks: dict[str, BlockSpec],
    dtype: np.dtype = np.float64,
    chunksize: int = 100_000,
) -> dict[str, np.ndarray]:
    """Load several blocks in a **single pass** over the CSV file.

    :func:`load_block` restarts at the top of the file for every block, which
    costs a full scan each time.  DNB files are >1 GB, so loading a whole set
    that way takes minutes.  This function streams the file once and copies
    each chunk into the blocks it overlaps.

    Parameters
    ----------
    path:
        Path to the CSV file.
    blocks:
        Mapping from name to :class:`~dnb_p_set.constants.BlockSpec`.
    dtype:
        NumPy dtype for the arrays.
    chunksize:
        Number of CSV rows read per chunk.  Larger is faster but uses more
        peak memory.

    Returns
    -------
    dict[str, np.ndarray]
        Mapping from block name to a ``(n_rows, n_cols)`` array.
    """
    path = Path(path)
    if not blocks:
        return {}

    n_cols = detect_n_columns(path)
    widest = max(spec.n_cols for spec in blocks.values())
    if widest > n_cols:
        raise ValueError(
            f"Block requires {widest} columns but '{path.name}' has {n_cols}"
        )

    result = {
        name: np.empty((spec.n_rows, spec.n_cols), dtype=dtype)
        for name, spec in blocks.items()
    }
    last_row = max(spec.row_end for spec in blocks.values())

    reader = pd.read_csv(
        path,
        header=None,
        names=range(n_cols),
        dtype=dtype,
        engine="c",
        chunksize=chunksize,
    )

    offset = 0  # 0-based index of the first row in the current chunk
    for chunk in reader:
        values = chunk.to_numpy(dtype=dtype)
        stop = offset + values.shape[0]
        for name, spec in blocks.items():
            begin = spec.row_start - 1  # 0-based, inclusive
            end = spec.row_end          # 0-based, exclusive
            lo = max(begin, offset)
            hi = min(end, stop)
            if lo < hi:
                result[name][lo - begin : hi - begin] = values[
                    lo - offset : hi - offset, : spec.n_cols
                ]
        offset = stop
        if offset >= last_row:
            break

    if offset < last_row:
        raise ValueError(
            f"'{path.name}' has only {offset} rows but the requested blocks "
            f"extend to row {last_row}.  Is this really a "
            f"{'Q' if last_row > 600_500 else 'P'}-set file?"
        )

    return result


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
    single_pass: bool = True,
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
    single_pass:
        Read the file once via :func:`load_blocks` (default).  Set to *False*
        to fall back to one :func:`load_block` call per block, which is
        slower but reads blocks strictly independently.

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

    if single_pass:
        logger.info(
            "Loading %d block(s) from '%s' in a single pass", len(requested), path.name
        )
        return load_blocks(path, requested, dtype=dtype)

    result: dict[str, np.ndarray] = {}
    for name, spec in requested.items():
        result[name] = load_block(path, spec, dtype=dtype)

    return result
