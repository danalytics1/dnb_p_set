# dnb_p_set

A Python package for **analyzing, describing and using the P and Q set simulations** published by De Nederlandsche Bank (DNB) for the Wet Toekomst Pensioenen (WTP).

> **Official source:** [DNB publiceert definitieve scenariosets bij Wet toekomst pensioenen](https://www.dnb.nl/voor-de-sector/open-boek-toezicht/sectoren/pensioenfondsen/dnb-publiceert-definitieve-scenariosets-bij-wet-toekomst-pensioenen/)

---

## Background

DNB publishes quarterly **scenario sets** for pension funds under the new Dutch pension law.  Two sets are released:

| Set  | Measure          | Description |
|------|-----------------|-------------|
| **P-set** | Real-world (P) | Used for actuarial projections (haalbaarheidstoets) |
| **Q-set** | Risk-neutral (Q) | Used for market-consistent valuations |

Each set is distributed as a large headerless CSV file (~700 k rows) containing stacked variable blocks for 100 000 scenarios and up to 101 time steps (t = 0 … 100 years).

---

## Installation

```bash
pip install dnb-p-set
```

Or install directly from source:

```bash
git clone https://github.com/danalytics1/dnb_p_set.git
cd dnb_p_set
pip install -e .
```

**Requirements:** Python ≥ 3.9, NumPy ≥ 1.24, pandas ≥ 2.0, matplotlib ≥ 3.7, SciPy ≥ 1.10.

---

## CSV file structure

The DNB CSV files have **no header row**.  Variables are stacked vertically in fixed row ranges:

| Variable | Block name | Rows (1-based) | Columns | P-set | Q-set |
|---|---|---|---|---|---|
| Toestandsvariabele 1 | `state_variable_1` | 1 – 100 000 | 101 | ✓ | ✓ |
| Toestandsvariabele 2 | `state_variable_2` | 100 001 – 200 000 | 101 | ✓ | ✓ |
| Toestandsvariabele 3 | `state_variable_3` | 200 001 – 300 000 | 101 | ✓ | ✓ |
| Aandelenrendement | `equity_return` | 300 001 – 400 000 | 100 | ✓ | ✓ |
| Prijsinflatie EU | `price_inflation_eu` | 400 001 – 500 000 | 100 | ✓ | ✓ |
| Prijsinflatie NL | `price_inflation_nl` | 500 001 – 600 000 | 100 | ✓ | ✓ |
| Renteparameter φ_N | `phi_nominal` | 600 001 – 600 100 | 101 | ✓ | ✓ |
| Renteparameter Ψ_N | `psi_nominal` | 600 101 – 600 200 | 3 | ✓ | ✓ |
| Renteparameter φ_R (EU) | `phi_real_eu` | 600 201 – 600 300 | 101 | ✓ | ✓ |
| Renteparameter Ψ_R | `psi_real` | 600 301 – 600 400 | 3 | ✓ | ✓ |
| Renteparameter φ_R (NL) | `phi_real_nl` | 600 401 – 600 500 | 101 | ✓ | ✓ |
| Stochastische discontovoet | `stochastic_discount_factor` | 600 501 – 700 500 | 100 | ✗ | ✓ |

Each stochastic block has shape **(100 000 scenarios × n_columns)**.

---

## Quick start

### Load a scenario set

```python
from dnb_p_set import ScenarioSet

# Load a full P-set CSV (set type is auto-detected from the filename)
ss = ScenarioSet.from_csv("DNB_P_scenarioset_2025Q1.csv")
print(ss.summary())

# Load only specific variables to save memory
ss = ScenarioSet.from_csv(
    "DNB_P_scenarioset_2025Q1.csv",
    variables=["equity_return", "price_inflation_nl"],
)
```

### Access raw arrays

```python
# Get the full 2-D array for a variable (n_scenarios × n_time_steps)
arr = ss.get("equity_return")        # canonical name
arr = ss.get("aandelen")             # Dutch alias also works
arr = ss.get("aandelenrendement")    # another alias

# Get the time series for a single scenario (0-based index)
path = ss.get_scenario("equity_return", scenario_idx=42)
```

### Descriptive statistics

```python
# Per-time-step summary statistics (DataFrame, index = t)
stats = ss.describe("equity_return")
print(stats[["mean", "p5", "p50", "p95"]].head(10))

# Just percentile paths
pct = ss.percentile_paths("equity_return", percentiles=[5, 25, 50, 75, 95])

# Mean path
mean = ss.mean_path("equity_return")
```

### Yield curve

```python
# Zero-coupon yield curves at time t=0 for all scenarios
yc = ss.yield_curve(
    t=0,
    maturities=[1, 2, 5, 10, 20, 30],
    measure="nominal",   # or "real"
    region="nl",         # or "eu"
)
print(yc.mean())         # mean yield curve

# Convenience wrapper
mean_yc = ss.mean_yield_curve(t=0, maturities=[1, 5, 10, 20, 30])
```

### Analysis utilities

```python
from dnb_p_set import analysis

arr = ss.get("equity_return")

# Cumulative return factor
cumret = analysis.cumulative_return(arr)

# Annualised geometric return
ann = analysis.annualised_return(arr)

# Value-at-Risk (loss) at 95% confidence per time step
var95 = analysis.value_at_risk(arr, confidence=0.95)

# Expected Shortfall / CVaR
es95 = analysis.expected_shortfall(arr, confidence=0.95)

# Probability of exceeding a threshold
prob = analysis.probability_exceeds(arr, threshold=0.10)

# Cross-variable correlation at t=5
corr = analysis.correlation_matrix(
    {"equity": ss.get("equity_return"), "infl": ss.get("price_inflation_nl")},
    t=5,
)
```

### Plotting

```python
from dnb_p_set import plotting

arr = ss.get("equity_return")

# Fan chart with percentile bands
fig, ax = plotting.plot_fan_chart(arr, title="Equity return fan chart", ylabel="Log return")
fig.savefig("equity_fan.png")

# Histogram at a specific time step
fig, ax = plotting.plot_histogram(arr, t=10, title="Equity return at t=10")

# Yield curve fan (uses the yield_curve DataFrame)
yc_df = ss.yield_curve(t=0)
fig, ax = plotting.plot_yield_curve(yc_df, t=0)
```

### HTML rapportage

```python
from dnb_p_set import ScenarioSet, build_html_report

current = ScenarioSet.from_csv("DNB_P_scenarioset_2025Q1.csv")
previous = ScenarioSet.from_csv("DNB_P_scenarioset_2024Q4.csv")

html = build_html_report(current, previous_set=previous)

with open("p_set_report.html", "w", encoding="utf-8") as f:
    f.write(html)
```

Het rapport bevat een overzicht van de huidige set en, indien opgegeven, een sectie
met verschillen ten opzichte van de vorige set.

---

## Variable aliases

You can address variables by their canonical name **or** any of the following Dutch/short aliases:

| Alias(es) | Canonical name |
|---|---|
| `sv1`, `toestandsvariabele_1` | `state_variable_1` |
| `sv2`, `toestandsvariabele_2` | `state_variable_2` |
| `sv3`, `toestandsvariabele_3` | `state_variable_3` |
| `aandelen`, `aandelenrendement`, `equity` | `equity_return` |
| `inflatie_eu`, `prijsinflatie_eu` | `price_inflation_eu` |
| `inflatie_nl`, `prijsinflatie_nl` | `price_inflation_nl` |
| `phi_n` | `phi_nominal` |
| `psi_n` | `psi_nominal` |
| `phi_r`, `phi_r_eu` | `phi_real_eu` |
| `psi_r` | `psi_real` |
| `phi_r_nl` | `phi_real_nl` |
| `sdf`, `discontovoet` | `stochastic_discount_factor` |

---

## Development

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=dnb_p_set --cov-report=term-missing
```

---

## License

[MIT](LICENSE)
