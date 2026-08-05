"""Tests for dnb_p_set.curves — the affine term-structure mathematics."""

from __future__ import annotations

import numpy as np
import pytest

from dnb_p_set import curves

N_TAU = 60
N_T = 20
N_SCEN = 40


@pytest.fixture()
def parameters():
    """A phi/psi/state triple that produces a plausible upward-sloping curve."""
    tau = np.arange(1, N_TAU + 1, dtype=float)
    phi = np.tile((-0.020 * tau)[:, None], (1, N_T))
    psi = np.column_stack([0.07 * tau, -0.98 * tau, -0.036 * tau])
    rng = np.random.default_rng(0)
    states = 0.02 + 0.004 * rng.standard_normal((N_SCEN, 3, N_T))
    return phi, psi, states


class TestZeroRates:
    def test_shape(self, parameters):
        phi, psi, states = parameters
        rates = curves.zero_rates(phi, psi, states, 0, [1, 5, 10])
        assert rates.shape == (N_SCEN, 3)

    def test_matches_dnb_formula(self, parameters):
        """Reproduce formula (1) element-wise for one scenario and maturity."""
        phi, psi, states = parameters
        tau, t, scenario = 7, 3, 11
        inner = phi[tau - 1, t] + psi[tau - 1] @ states[scenario, :, t]
        expected = np.exp(-inner / tau) - 1.0
        rates = curves.zero_rates(phi, psi, states, t, [tau])
        assert rates[scenario, 0] == pytest.approx(expected)

    def test_continuous_is_below_annual(self, parameters):
        phi, psi, states = parameters
        annual = curves.zero_rates(phi, psi, states, 0, [10])
        continuous = curves.zero_rates(
            phi, psi, states, 0, [10], compounding="continuous"
        )
        assert (continuous < annual).all()

    def test_accepts_2d_states(self, parameters):
        phi, psi, states = parameters
        from_3d = curves.zero_rates(phi, psi, states, 4, [10])
        from_2d = curves.zero_rates(phi, psi, states[:, :, 4], 4, [10])
        np.testing.assert_allclose(from_3d, from_2d)

    def test_invalid_compounding(self, parameters):
        phi, psi, states = parameters
        with pytest.raises(ValueError, match="compounding"):
            curves.zero_rates(phi, psi, states, 0, [1], compounding="daily")

    def test_maturity_out_of_range(self, parameters):
        phi, psi, states = parameters
        with pytest.raises(ValueError, match="maturities must lie"):
            curves.zero_rates(phi, psi, states, 0, [N_TAU + 1])

    def test_zero_maturity_rejected(self, parameters):
        phi, psi, states = parameters
        with pytest.raises(ValueError, match="maturities must lie"):
            curves.zero_rates(phi, psi, states, 0, [0])

    def test_mismatched_blocks(self, parameters):
        phi, psi, states = parameters
        with pytest.raises(ValueError, match="same maturities"):
            curves.zero_rates(phi, psi[:-1], states, 0, [1])


class TestDiscountFactor:
    def test_inverts_the_zero_rate(self, parameters):
        phi, psi, states = parameters
        tau = 12
        price = curves.discount_factor(phi, psi, states, 0, [tau])
        rate = curves.zero_rates(phi, psi, states, 0, [tau])
        np.testing.assert_allclose(price, (1.0 + rate) ** -tau)

    def test_positive(self, parameters):
        phi, psi, states = parameters
        price = curves.discount_factor(phi, psi, states, 0, [1, 10, 30])
        assert (price > 0).all()


class TestForwardRates:
    def test_first_forward_equals_one_year_spot(self, parameters):
        phi, psi, states = parameters
        forward = curves.forward_rates(phi, psi, states, 0, [1])
        spot = curves.zero_rates(phi, psi, states, 0, [1])
        np.testing.assert_allclose(forward, spot)

    def test_compounds_back_to_the_spot_curve(self, parameters):
        phi, psi, states = parameters
        maturities = list(range(1, 11))
        forwards = curves.forward_rates(phi, psi, states, 0, maturities)
        spot10 = curves.zero_rates(phi, psi, states, 0, [10])[:, 0]
        compounded = np.prod(1.0 + forwards, axis=1) ** (1 / 10) - 1.0
        np.testing.assert_allclose(compounded, spot10)


class TestAnnuity:
    def test_pv_is_sum_of_discount_factors(self, parameters):
        phi, psi, states = parameters
        cashflows = np.ones(15)
        pv = curves.annuity_pv(phi, psi, states, 0, cashflows)
        prices = curves.discount_factor(phi, psi, states, 0, range(1, 16))
        np.testing.assert_allclose(pv, prices.sum(axis=1))

    def test_pv_falls_when_rates_rise(self, parameters):
        phi, psi, states = parameters
        cashflows = np.ones(30)
        base = curves.annuity_pv(phi, psi, states, 0, cashflows)
        # Lowering phi raises every yield (y = exp(-phi_total/tau) - 1)
        higher_rates = curves.annuity_pv(phi - 0.01, psi, states, 0, cashflows)
        assert (higher_rates < base).all()

    def test_duration_between_first_and_last_maturity(self, parameters):
        phi, psi, states = parameters
        cashflows = np.ones(30)
        duration = curves.macaulay_duration(phi, psi, states, 0, cashflows)
        assert (duration > 1).all()
        assert (duration < 30).all()

    def test_single_cashflow_duration_is_its_maturity(self, parameters):
        phi, psi, states = parameters
        cashflows = np.zeros(20)
        cashflows[14] = 1.0  # pays at tau = 15
        duration = curves.macaulay_duration(phi, psi, states, 0, cashflows)
        np.testing.assert_allclose(duration, 15.0)


class TestBreakevenInflation:
    def test_fisher_relation(self):
        nominal = np.array([0.03, 0.04])
        real = np.array([0.01, 0.015])
        bei = curves.breakeven_inflation(nominal, real)
        np.testing.assert_allclose((1 + real) * (1 + bei), 1 + nominal)

    def test_zero_when_curves_coincide(self):
        rates = np.array([0.02, 0.03, 0.04])
        np.testing.assert_allclose(curves.breakeven_inflation(rates, rates), 0.0)
