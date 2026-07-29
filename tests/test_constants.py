"""Tests for dnb_p_set.constants."""

import pytest
from dnb_p_set.constants import (
    BLOCKS,
    VARIABLE_ALIASES,
    BlockSpec,
    N_SCENARIOS,
    N_TIMESTEPS_LONG,
    N_TIMESTEPS_SHORT,
)


class TestBlockSpec:
    def test_n_rows(self):
        spec = BlockSpec(
            name="test",
            description_nl="Test",
            row_start=1,
            row_end=100_000,
            n_cols=101,
        )
        assert spec.n_rows == 100_000

    def test_slice_rows_zero_based(self):
        spec = BlockSpec(
            name="test",
            description_nl="Test",
            row_start=1,
            row_end=3,
            n_cols=5,
        )
        assert spec.slice_rows == slice(0, 3)

    def test_slice_rows_offset(self):
        spec = BlockSpec(
            name="test",
            description_nl="Test",
            row_start=100_001,
            row_end=200_000,
            n_cols=101,
        )
        assert spec.slice_rows == slice(100_000, 200_000)

    def test_slice_cols(self):
        spec = BlockSpec(
            name="test",
            description_nl="Test",
            row_start=1,
            row_end=10,
            n_cols=5,
        )
        assert spec.slice_cols == slice(0, 5)

    def test_frozen(self):
        spec = BlockSpec(
            name="test",
            description_nl="Test",
            row_start=1,
            row_end=10,
            n_cols=5,
        )
        with pytest.raises(Exception):
            spec.name = "other"  # type: ignore[misc]


class TestBlocks:
    def test_all_expected_blocks_present(self):
        expected = {
            "state_variable_1", "state_variable_2", "state_variable_3",
            "equity_return", "price_inflation_eu", "price_inflation_nl",
            "phi_nominal", "psi_nominal", "phi_real_eu", "psi_real",
            "phi_real_nl", "stochastic_discount_factor",
        }
        assert expected.issubset(set(BLOCKS.keys()))

    def test_stochastic_blocks_have_correct_n_rows(self):
        stochastic = [
            "state_variable_1", "state_variable_2", "state_variable_3",
            "equity_return", "price_inflation_eu", "price_inflation_nl",
        ]
        for name in stochastic:
            assert BLOCKS[name].n_rows == N_SCENARIOS, f"{name} n_rows mismatch"

    def test_state_variable_n_cols(self):
        for i in range(1, 4):
            assert BLOCKS[f"state_variable_{i}"].n_cols == N_TIMESTEPS_LONG

    def test_equity_return_n_cols(self):
        assert BLOCKS["equity_return"].n_cols == N_TIMESTEPS_SHORT

    def test_sdf_only_in_q_set(self):
        spec = BLOCKS["stochastic_discount_factor"]
        assert not spec.p_set
        assert spec.q_set

    def test_row_ranges_non_overlapping(self):
        """Verify that all blocks have non-overlapping row ranges."""
        ranges = [(s.row_start, s.row_end) for s in BLOCKS.values()]
        for i, (s1, e1) in enumerate(ranges):
            for j, (s2, e2) in enumerate(ranges):
                if i == j:
                    continue
                # Check no overlap
                assert e1 < s2 or e2 < s1, (
                    f"Blocks {list(BLOCKS.keys())[i]} and "
                    f"{list(BLOCKS.keys())[j]} overlap"
                )

    def test_row_start_leq_row_end(self):
        for name, spec in BLOCKS.items():
            assert spec.row_start <= spec.row_end, f"{name}: row_start > row_end"


class TestVariableAliases:
    def test_aliases_map_to_valid_blocks(self):
        for alias, canonical in VARIABLE_ALIASES.items():
            assert canonical in BLOCKS, (
                f"Alias '{alias}' maps to '{canonical}' which is not in BLOCKS"
            )

    def test_equity_aliases(self):
        assert VARIABLE_ALIASES["aandelen"] == "equity_return"
        assert VARIABLE_ALIASES["aandelenrendement"] == "equity_return"
        assert VARIABLE_ALIASES["equity"] == "equity_return"

    def test_sdf_alias(self):
        assert VARIABLE_ALIASES["sdf"] == "stochastic_discount_factor"
        assert VARIABLE_ALIASES["discontovoet"] == "stochastic_discount_factor"
