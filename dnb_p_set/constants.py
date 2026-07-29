"""
Constants describing the block structure of DNB scenario set CSV files.

The DNB CSV files use a large matrix format where different economic variables
occupy specific row ranges.  All row/column indices below are **1-based** as
published in the official DNB documentation; the loader converts them to
0-based Python/pandas indices.

Reference
---------
DNB toelichting CSV scenarioset
https://www.dnb.nl/voor-de-sector/open-boek-toezicht/sectoren/pensioenfondsen/
dnb-publiceert-definitieve-scenariosets-bij-wet-toekomst-pensioenen/
"""

from dataclasses import dataclass
from typing import Optional

# Number of scenarios (rows per variable block for stochastic variables)
N_SCENARIOS: int = 100_000

# Number of projection time steps (t = 0 … 100 → 101 columns)
N_TIMESTEPS_LONG: int = 101   # columns for state variables and phi parameters
N_TIMESTEPS_SHORT: int = 100  # columns for return / inflation / discount variables


@dataclass(frozen=True)
class BlockSpec:
    """Specification of one variable block inside the CSV.

    Parameters
    ----------
    name:
        Human-readable English name used as key in the package API.
    description_nl:
        Dutch description matching DNB documentation.
    row_start:
        First 1-based row of the block.
    row_end:
        Last 1-based row of the block (inclusive).
    n_cols:
        Number of columns (time steps) in this block.
    p_set:
        Whether the block is present in the P-set.
    q_set:
        Whether the block is present in the Q-set.
    """

    name: str
    description_nl: str
    row_start: int
    row_end: int
    n_cols: int
    p_set: bool = True
    q_set: bool = True

    @property
    def n_rows(self) -> int:
        return self.row_end - self.row_start + 1

    # Convenience 0-based slice helpers
    @property
    def slice_rows(self) -> slice:
        return slice(self.row_start - 1, self.row_end)

    @property
    def slice_cols(self) -> slice:
        return slice(0, self.n_cols)


# ---------------------------------------------------------------------------
# Block definitions (1-based row numbers, matching DNB documentation)
# ---------------------------------------------------------------------------

BLOCKS: dict[str, BlockSpec] = {
    "state_variable_1": BlockSpec(
        name="state_variable_1",
        description_nl="Toestandsvariabele 1",
        row_start=1,
        row_end=100_000,
        n_cols=N_TIMESTEPS_LONG,
    ),
    "state_variable_2": BlockSpec(
        name="state_variable_2",
        description_nl="Toestandsvariabele 2",
        row_start=100_001,
        row_end=200_000,
        n_cols=N_TIMESTEPS_LONG,
    ),
    "state_variable_3": BlockSpec(
        name="state_variable_3",
        description_nl="Toestandsvariabele 3",
        row_start=200_001,
        row_end=300_000,
        n_cols=N_TIMESTEPS_LONG,
    ),
    "equity_return": BlockSpec(
        name="equity_return",
        description_nl="Aandelenrendement",
        row_start=300_001,
        row_end=400_000,
        n_cols=N_TIMESTEPS_SHORT,
    ),
    "price_inflation_eu": BlockSpec(
        name="price_inflation_eu",
        description_nl="Prijsinflatie EU",
        row_start=400_001,
        row_end=500_000,
        n_cols=N_TIMESTEPS_SHORT,
    ),
    "price_inflation_nl": BlockSpec(
        name="price_inflation_nl",
        description_nl="Prijsinflatie NL",
        row_start=500_001,
        row_end=600_000,
        n_cols=N_TIMESTEPS_SHORT,
    ),
    "phi_nominal": BlockSpec(
        name="phi_nominal",
        description_nl="Renteparameter phi_N (nominaal)",
        row_start=600_001,
        row_end=600_100,
        n_cols=N_TIMESTEPS_LONG,
    ),
    "psi_nominal": BlockSpec(
        name="psi_nominal",
        description_nl="Renteparameter Psi_N (nominaal)",
        row_start=600_101,
        row_end=600_200,
        n_cols=3,
    ),
    "phi_real_eu": BlockSpec(
        name="phi_real_eu",
        description_nl="Renteparameter phi_R (reëel EU)",
        row_start=600_201,
        row_end=600_300,
        n_cols=N_TIMESTEPS_LONG,
    ),
    "psi_real": BlockSpec(
        name="psi_real",
        description_nl="Renteparameter Psi_R (reëel)",
        row_start=600_301,
        row_end=600_400,
        n_cols=3,
    ),
    "phi_real_nl": BlockSpec(
        name="phi_real_nl",
        description_nl="Renteparameter phi_R_NL (reëel NL)",
        row_start=600_401,
        row_end=600_500,
        n_cols=N_TIMESTEPS_LONG,
    ),
    "stochastic_discount_factor": BlockSpec(
        name="stochastic_discount_factor",
        description_nl="Stochastische discontovoet (alleen Q-scenario's)",
        row_start=600_501,
        row_end=700_500,
        n_cols=N_TIMESTEPS_SHORT,
        p_set=False,
        q_set=True,
    ),
}

# Mapping of user-friendly aliases to canonical block names
VARIABLE_ALIASES: dict[str, str] = {
    # state variables
    "sv1": "state_variable_1",
    "sv2": "state_variable_2",
    "sv3": "state_variable_3",
    "toestandsvariabele_1": "state_variable_1",
    "toestandsvariabele_2": "state_variable_2",
    "toestandsvariabele_3": "state_variable_3",
    # returns
    "aandelen": "equity_return",
    "aandelenrendement": "equity_return",
    "equity": "equity_return",
    # inflation
    "inflatie_eu": "price_inflation_eu",
    "prijsinflatie_eu": "price_inflation_eu",
    "inflatie_nl": "price_inflation_nl",
    "prijsinflatie_nl": "price_inflation_nl",
    # term structure
    "phi_n": "phi_nominal",
    "psi_n": "psi_nominal",
    "phi_r": "phi_real_eu",
    "phi_r_eu": "phi_real_eu",
    "psi_r": "psi_real",
    "phi_r_nl": "phi_real_nl",
    # discount
    "sdf": "stochastic_discount_factor",
    "discontovoet": "stochastic_discount_factor",
}

# Standard percentiles used for fan-chart / descriptive statistics
DEFAULT_PERCENTILES: list[float] = [5.0, 10.0, 25.0, 50.0, 75.0, 90.0, 95.0]
