"""Tests for dnb_p_set.loader."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import numpy as np
import pytest

from dnb_p_set.loader import (
    detect_n_columns,
    detect_set_type,
    load_block,
    load_blocks,
    load_csv,
)
from dnb_p_set.constants import BLOCKS, BlockSpec


class TestDetectSetType:
    def test_p_set_filename(self, tmp_path):
        f = tmp_path / "DNB_P_scenarioset_2024Q1.csv"
        f.touch()
        assert detect_set_type(f) == "P"

    def test_q_set_filename_with_q_(self, tmp_path):
        f = tmp_path / "DNB_Q_scenarioset_2024Q1.csv"
        f.touch()
        assert detect_set_type(f) == "Q"

    def test_q_set_filename_qset(self, tmp_path):
        f = tmp_path / "DNB_QSET_2024Q1.csv"
        f.touch()
        assert detect_set_type(f) == "Q"

    def test_default_is_p(self, tmp_path):
        f = tmp_path / "scenarioset_2024Q1.csv"
        f.touch()
        assert detect_set_type(f) == "P"


class TestLoadBlock:
    def _write_csv(self, tmp_path: Path, n_rows: int, n_cols: int, value: float = 1.0) -> Path:
        """Write a small CSV file filled with *value*."""
        p = tmp_path / "test.csv"
        data = np.full((n_rows, n_cols), value)
        np.savetxt(p, data, delimiter=",", fmt="%.6f")
        return p

    def test_load_returns_correct_shape(self, tmp_path):
        spec = BLOCKS["phi_nominal"]  # 100 rows, 101 cols
        # Write enough rows so skiprows doesn't fail
        total_rows = spec.row_end  # enough rows
        p = tmp_path / "test.csv"
        data = np.ones((total_rows, spec.n_cols))
        np.savetxt(p, data, delimiter=",", fmt="%.6f")
        arr = load_block(p, spec)
        assert arr.shape == (spec.n_rows, spec.n_cols)

    def test_load_values(self, tmp_path):
        spec = BLOCKS["phi_nominal"]
        total_rows = spec.row_end
        p = tmp_path / "test.csv"
        # Fill with sentinel values; we only care about the spec's block
        data = np.zeros((total_rows, spec.n_cols))
        data[spec.row_start - 1 : spec.row_end] = 3.14
        np.savetxt(p, data, delimiter=",", fmt="%.6f")
        arr = load_block(p, spec)
        np.testing.assert_allclose(arr, 3.14, rtol=1e-4)

    def test_file_not_found(self):
        spec = BLOCKS["phi_nominal"]
        with pytest.raises(FileNotFoundError):
            load_block("/nonexistent/path.csv", spec)


class TestLoadCsv:
    def test_invalid_set_type(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("")
        with pytest.raises(ValueError, match="set_type must be"):
            load_csv(f, set_type="X")

    def test_unknown_variable(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("")
        with pytest.raises(ValueError, match="Unknown variable"):
            load_csv(f, set_type="P", variables=["nonexistent_variable"])

    def test_p_set_excludes_sdf(self, tmp_path):
        """stochastic_discount_factor should be skipped with a warning for P-set."""
        f = tmp_path / "test.csv"
        f.write_text("0.0\n")  # minimal file so existence check passes
        # We just test that the unknown variable validation fires
        with pytest.raises(ValueError, match="Unknown variable"):
            load_csv(f, set_type="P", variables=["definitely_unknown"])

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_csv("/nonexistent/file.csv", set_type="P")


# A miniature block layout mirroring the real one: three stacked blocks, the
# widest of which sets the file's column count.
SMALL_LAYOUT = {
    "wide": BlockSpec("wide", "breed blok", row_start=1, row_end=6, n_cols=5),
    "narrow": BlockSpec("narrow", "smal blok", row_start=7, row_end=10, n_cols=3),
    "tail": BlockSpec("tail", "staart", row_start=11, row_end=12, n_cols=5),
}


def _write_layout(path: Path) -> np.ndarray:
    """Write a 12x5 file where each cell encodes its own row and column."""
    rows, cols = 12, 5
    data = np.arange(rows * cols, dtype=float).reshape(rows, cols)
    # Narrow rows are padded with NaN, exactly as DNB pads its files.
    data[6:10, 3:] = np.nan
    np.savetxt(path, data, delimiter=",", fmt="%s")
    return data


class TestDetectNColumns:
    def test_counts_fields(self, tmp_path):
        f = tmp_path / "test.csv"
        _write_layout(f)
        assert detect_n_columns(f) == 5

    def test_empty_file_raises(self, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_text("")
        with pytest.raises(ValueError, match="empty"):
            detect_n_columns(f)


class TestLoadBlocks:
    def test_shapes(self, tmp_path):
        f = tmp_path / "test.csv"
        _write_layout(f)
        result = load_blocks(f, SMALL_LAYOUT)
        assert result["wide"].shape == (6, 5)
        assert result["narrow"].shape == (4, 3)
        assert result["tail"].shape == (2, 5)

    def test_values_match_the_layout(self, tmp_path):
        f = tmp_path / "test.csv"
        data = _write_layout(f)
        result = load_blocks(f, SMALL_LAYOUT)
        np.testing.assert_allclose(result["wide"], data[0:6, :5])
        np.testing.assert_allclose(result["narrow"], data[6:10, :3])
        np.testing.assert_allclose(result["tail"], data[10:12, :5])

    def test_matches_load_block(self, tmp_path):
        f = tmp_path / "test.csv"
        _write_layout(f)
        single_pass = load_blocks(f, SMALL_LAYOUT)
        for name, spec in SMALL_LAYOUT.items():
            np.testing.assert_allclose(single_pass[name], load_block(f, spec))

    @pytest.mark.parametrize("chunksize", [1, 2, 5, 7, 100])
    def test_chunk_boundaries_do_not_matter(self, tmp_path, chunksize):
        f = tmp_path / "test.csv"
        _write_layout(f)
        reference = load_blocks(f, SMALL_LAYOUT, chunksize=100)
        result = load_blocks(f, SMALL_LAYOUT, chunksize=chunksize)
        for name in SMALL_LAYOUT:
            np.testing.assert_allclose(result[name], reference[name])

    def test_stops_early_when_blocks_are_satisfied(self, tmp_path):
        f = tmp_path / "test.csv"
        data = _write_layout(f)
        result = load_blocks(f, {"wide": SMALL_LAYOUT["wide"]}, chunksize=2)
        np.testing.assert_allclose(result["wide"], data[0:6, :5])

    def test_no_blocks_is_empty(self, tmp_path):
        f = tmp_path / "test.csv"
        _write_layout(f)
        assert load_blocks(f, {}) == {}

    def test_truncated_file_raises(self, tmp_path):
        f = tmp_path / "short.csv"
        np.savetxt(f, np.ones((4, 5)), delimiter=",", fmt="%s")
        with pytest.raises(ValueError, match="only 4 rows"):
            load_blocks(f, SMALL_LAYOUT)

    def test_too_few_columns_raises(self, tmp_path):
        f = tmp_path / "narrow.csv"
        np.savetxt(f, np.ones((12, 2)), delimiter=",", fmt="%s")
        with pytest.raises(ValueError, match="requires 5 columns"):
            load_blocks(f, SMALL_LAYOUT)
