"""
Core :class:`ScenarioSet` class.

This is the primary entry point for working with DNB scenario sets.

Example
-------
>>> from dnb_p_set import ScenarioSet
>>> ss = ScenarioSet.from_csv("DNB_P_scenarioset_2025Q1.csv")
>>> ss.describe("equity_return")
>>> ss.plot_fan_chart("equity_return")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from .constants import (
    BLOCKS,
    DEFAULT_PERCENTILES,
    N_SCENARIOS,
    VARIABLE_ALIASES,
    BlockSpec,
)

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


class ScenarioSet:
    """Container for a DNB P- or Q-set scenario simulation.

    Attributes
    ----------
    set_type : str
        ``"P"`` for the real-world measure set, ``"Q"`` for the risk-neutral
        measure set.
    source_path : Path | None
        Path to the CSV file this object was loaded from.
    n_scenarios : int
        Number of scenarios stored in the stochastic blocks.

    Notes
    -----
    The DNB scenario sets are published quarterly as large CSV files.  Each
    file contains several variable blocks stacked vertically.  See
    :mod:`dnb_p_set.constants` for the full block specification.
    """

    def __init__(
        self,
        data: dict[str, np.ndarray],
        set_type: str = "P",
        source_path: PathLike | None = None,
    ) -> None:
        self._data: dict[str, np.ndarray] = data
        self.set_type: str = set_type.upper()
        self.source_path: Path | None = Path(source_path) if source_path else None

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_csv(
        cls,
        path: PathLike,
        set_type: str | None = None,
        variables: list[str] | None = None,
    ) -> "ScenarioSet":
        """Create a :class:`ScenarioSet` from a DNB CSV file.

        Parameters
        ----------
        path:
            Path to the DNB CSV scenario-set file.
        set_type:
            ``"P"`` or ``"Q"``.  Inferred from the filename when *None*.
        variables:
            Subset of variable names/aliases to load.  Loads all valid
            variables for the set type when *None*.

        Returns
        -------
        ScenarioSet
        """
        from .loader import detect_set_type, load_csv

        resolved_type = set_type or detect_set_type(path)
        data = load_csv(path, set_type=resolved_type, variables=variables)
        return cls(data=data, set_type=resolved_type, source_path=path)

    # ------------------------------------------------------------------
    # Variable access
    # ------------------------------------------------------------------

    def _resolve(self, variable: str) -> str:
        """Return canonical block name for *variable* (name or alias)."""
        key = variable.lower()
        canonical = VARIABLE_ALIASES.get(key, key)
        if canonical not in self._data:
            available = list(self._data.keys())
            raise KeyError(
                f"Variable '{variable}' not loaded.  "
                f"Loaded variables: {available}"
            )
        return canonical

    @property
    def variables(self) -> list[str]:
        """List of loaded variable names."""
        return list(self._data.keys())

    @property
    def n_scenarios(self) -> int:
        """Number of stochastic scenarios."""
        for name, arr in self._data.items():
            if BLOCKS[name].n_rows == N_SCENARIOS:
                return arr.shape[0]
        return N_SCENARIOS

    def get(self, variable: str) -> np.ndarray:
        """Return the raw NumPy array for *variable*.

        Parameters
        ----------
        variable:
            Block name or recognised alias (see :data:`~dnb_p_set.constants.VARIABLE_ALIASES`).

        Returns
        -------
        np.ndarray
            2-D array ``(n_rows, n_cols)``.
        """
        return self._data[self._resolve(variable)]

    def get_scenario(self, variable: str, scenario_idx: int) -> np.ndarray:
        """Return the time series for a single scenario.

        Parameters
        ----------
        variable:
            Variable name or alias.
        scenario_idx:
            0-based scenario index (0 … n_scenarios-1).

        Returns
        -------
        np.ndarray
            1-D array of length ``n_cols``.
        """
        arr = self.get(variable)
        if scenario_idx < 0 or scenario_idx >= arr.shape[0]:
            raise IndexError(
                f"scenario_idx={scenario_idx} out of range "
                f"[0, {arr.shape[0] - 1}]"
            )
        return arr[scenario_idx]

    # ------------------------------------------------------------------
    # Descriptive statistics
    # ------------------------------------------------------------------

    def describe(
        self,
        variable: str,
        percentiles: list[float] | None = None,
    ) -> pd.DataFrame:
        """Return a DataFrame of descriptive statistics over all scenarios.

        Each row corresponds to a time step (column in the raw array),
        i.e. ``t = 0, 1, ..., T``.

        Parameters
        ----------
        variable:
            Variable name or alias.
        percentiles:
            Percentiles (0–100) to compute.  Defaults to
            ``[5, 10, 25, 50, 75, 90, 95]``.

        Returns
        -------
        pd.DataFrame
            Index is the time step ``t``; columns include ``mean``, ``std``,
            ``min``, ``max`` and one column per percentile.
        """
        if percentiles is None:
            percentiles = DEFAULT_PERCENTILES

        arr = self.get(variable)
        t_index = pd.Index(range(arr.shape[1]), name="t")

        rows = {
            "mean": arr.mean(axis=0),
            "std": arr.std(axis=0, ddof=1),
            "min": arr.min(axis=0),
            "max": arr.max(axis=0),
        }
        for p in percentiles:
            rows[f"p{p:g}"] = np.percentile(arr, p, axis=0)

        return pd.DataFrame(rows, index=t_index)

    def percentile_paths(
        self,
        variable: str,
        percentiles: list[float] | None = None,
    ) -> pd.DataFrame:
        """Return percentile paths over time for *variable*.

        Parameters
        ----------
        variable:
            Variable name or alias.
        percentiles:
            Percentiles (0–100) to compute.  Defaults to
            ``[5, 10, 25, 50, 75, 90, 95]``.

        Returns
        -------
        pd.DataFrame
            Columns are percentile labels; index is time step ``t``.
        """
        if percentiles is None:
            percentiles = DEFAULT_PERCENTILES

        arr = self.get(variable)
        t_index = pd.Index(range(arr.shape[1]), name="t")
        data = {
            f"p{p:g}": np.percentile(arr, p, axis=0) for p in percentiles
        }
        return pd.DataFrame(data, index=t_index)

    def mean_path(self, variable: str) -> pd.Series:
        """Return the mean path over time for *variable*.

        Returns
        -------
        pd.Series
            Index is time step ``t``.
        """
        arr = self.get(variable)
        return pd.Series(arr.mean(axis=0), index=range(arr.shape[1]), name="mean")

    # ------------------------------------------------------------------
    # Yield-curve helpers
    # ------------------------------------------------------------------

    def yield_curve(
        self,
        t: int,
        maturities: list[int] | None = None,
        measure: str = "nominal",
        region: str = "nl",
    ) -> pd.DataFrame:
        """Compute the zero-coupon yield curve at time step *t*.

        The yield curve is derived from the affine term-structure parameters
        (phi, psi) stored in the scenario set using:

        .. math::

            y(t, \\tau) = -\\frac{1}{\\tau}
                         \\left( \\phi(t, \\tau)
                                + \\sum_{i=1}^{3} \\psi_i(\\tau) \\cdot x_i(t)
                         \\right)

        where :math:`x_i(t)` are the state variables at time *t*.

        Parameters
        ----------
        t:
            Time step index (0-based).
        maturities:
            List of maturities (in years) to compute.  Defaults to
            ``[1, 2, 5, 10, 20, 30, 40, 50]``.
        measure:
            ``"nominal"`` or ``"real"``.
        region:
            ``"nl"`` (default) or ``"eu"``.  Only relevant for the real
            measure (phi_real_eu vs phi_real_nl).

        Returns
        -------
        pd.DataFrame
            Columns are maturities; index is scenario index.
        """
        if maturities is None:
            maturities = [1, 2, 5, 10, 20, 30, 40, 50]

        if measure == "nominal":
            phi_key = "phi_nominal"
            psi_key = "psi_nominal"
        elif measure == "real":
            phi_key = "phi_real_nl" if region.lower() == "nl" else "phi_real_eu"
            psi_key = "psi_real"
        else:
            raise ValueError(f"measure must be 'nominal' or 'real', got '{measure}'")

        if phi_key not in self._data or psi_key not in self._data:
            raise KeyError(
                f"'{phi_key}' and/or '{psi_key}' not loaded.  "
                "Load the phi/psi blocks to compute yield curves."
            )

        phi = self._data[phi_key]  # shape (n_tau, n_t)
        psi = self._data[psi_key]  # shape (n_tau, 3)

        sv1 = self._data.get("state_variable_1")
        sv2 = self._data.get("state_variable_2")
        sv3 = self._data.get("state_variable_3")
        if sv1 is None or sv2 is None or sv3 is None:
            raise KeyError(
                "State variables (state_variable_1/2/3) must be loaded "
                "to compute yield curves."
            )

        # x_i shape: (n_scenarios,)
        x1 = sv1[:, t]
        x2 = sv2[:, t]
        x3 = sv3[:, t]

        results = {}
        for tau in maturities:
            if tau < 1 or tau > phi.shape[0]:
                raise ValueError(
                    f"Maturity {tau} out of range [1, {phi.shape[0]}]"
                )
            tau_idx = tau - 1  # 0-based
            # phi(t, tau): time step t for this maturity
            phi_val = phi[tau_idx, t]
            # psi[tau_idx, :] has shape (3,)
            psi_row = psi[tau_idx]
            # affine term structure: log price = phi + psi @ x
            log_price = phi_val + psi_row[0] * x1 + psi_row[1] * x2 + psi_row[2] * x3
            # zero-coupon yield y = -log_price / tau
            yield_val = -log_price / tau
            results[tau] = yield_val

        df = pd.DataFrame(results)
        df.index.name = "scenario"
        df.columns.name = "maturity"
        return df

    def mean_yield_curve(
        self,
        t: int,
        maturities: list[int] | None = None,
        measure: str = "nominal",
        region: str = "nl",
    ) -> pd.Series:
        """Return the mean yield curve across all scenarios at time *t*.

        Returns
        -------
        pd.Series
            Index is maturity (years).
        """
        df = self.yield_curve(t=t, maturities=maturities, measure=measure, region=region)
        return df.mean()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a short human-readable summary of the scenario set."""
        lines = [
            f"DNB {'P' if self.set_type == 'P' else 'Q'}-set ScenarioSet",
            f"  Source : {self.source_path or 'in-memory'}",
            f"  Loaded variables ({len(self.variables)}):",
        ]
        for name in self.variables:
            spec = BLOCKS[name]
            arr = self._data[name]
            lines.append(f"    {name:30s}  shape={arr.shape}  ({spec.description_nl})")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"ScenarioSet(set_type='{self.set_type}', "
            f"variables={self.variables}, "
            f"source_path='{self.source_path}')"
        )
