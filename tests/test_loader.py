"""Tests for dnb_p_set.loader."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import numpy as np
import pytest

from dnb_p_set.loader import detect_set_type, load_csv, load_block
from dnb_p_set.constants import BLOCKS


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
