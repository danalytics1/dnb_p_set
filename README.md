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

The loader streams the file **once** and copies each chunk into the blocks it
overlaps (`loader.load_blocks`), so loading a whole 1.1 GB set takes about ten
seconds instead of one full scan per block. Pass `single_pass=False` to
`load_csv` for the older block-at-a-time behaviour.

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

The set ships the affine term-structure parameters, not the curves themselves.
The annually compounded zero rate follows DNB formula (1):

$$y(\tau, t) = \exp\!\left[-\frac{1}{\tau}\Big(\phi(\tau,t) + \sum_{i=1}^{3}\Psi_i(\tau)\,X_i(t)\Big)\right] - 1$$

```python
# Zero-coupon yield curves at time t=0 for all scenarios
yc = ss.yield_curve(
    t=0,
    maturities=[1, 2, 5, 10, 20, 30],
    measure="nominal",   # or "real"
    region="nl",         # or "eu"
)
print(yc.mean())         # mean yield curve

# Convenience wrappers
mean_yc = ss.mean_yield_curve(t=0, maturities=[1, 5, 10, 20, 30])
rates = ss.zero_rates(t=0, maturities=[10])       # raw NumPy array
pv = ss.annuity_pv(t=0)                            # flat 60-year cashflow

# Continuous compounding is available but is NOT the DNB convention
# (it runs roughly 3-5 bp below the annually compounded rate)
yc_cc = ss.yield_curve(t=0, compounding="continuous")
```

The underlying maths lives in `dnb_p_set.curves` and works on plain arrays:

```python
from dnb_p_set import curves

phi, psi = ss.curve_parameters(measure="nominal")
states = ss.state_matrix()                    # (n_scenarios, 3, n_t)

rates = curves.zero_rates(phi, psi, states, t=0, maturities=[1, 10, 30])
prices = curves.discount_factor(phi, psi, states, t=0, maturities=[10])
fwd = curves.forward_rates(phi, psi, states, t=0, maturities=range(1, 11))
dur = curves.macaulay_duration(phi, psi, states, 0, cashflows=np.ones(60))
bei = curves.breakeven_inflation(nominal_rates, real_rates)
```

### Analysis utilities

> **Returns are simple, not log returns.** DNB defines the equity and inflation
> blocks as $(S_{t+1} - S_t)/S_t$, so compounding uses $\prod(1+r)$ rather than
> $\exp(\sum r)$. On the 2026Q3 P-set the two differ materially: 5.52 % versus
> 6.88 % geometric mean. Pass `log_returns=True` if your array really does hold
> log returns.

```python
from dnb_p_set import analysis

arr = ss.get("equity_return")

# Cumulative return factor
cumret = analysis.cumulative_return(arr)

# Annualised geometric return
ann = analysis.annualised_return(arr)

# Geometric mean per year (the figure DNB calibrates: ~5.4% gross)
geo = analysis.geometric_mean_return(arr)

# Monte-Carlo standard error and confidence interval (DNB formulas 2-5)
se = analysis.standard_error(arr[:, 0])
mean, lo, hi = analysis.mean_confidence_interval(arr[:, 0])

# Confidence interval around a percentile (DNB formulas 6-7)
est, lo, hi = analysis.percentile_confidence_interval(arr[:, 0], p=5.0)

# Full one-shot summary of a cross-section
stats = analysis.distribution_stats(arr[:, 0])

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

### Maatmens en lifecycle

`dnb_p_set.lifecycle` turns the simulated returns into the pension capital of a
stylised participant (a *maatmens*).  The capital is split over two portfolios,
both driven by the set:

| Portefeuille | Exposure |
|---|---|
| **Rendementsportefeuille** | the simulated equity return |
| **Beschermingsportefeuille** | a constant-maturity zero-coupon bond priced off the affine term structure |

A `Lifecycle` sets the split per age.  Projection year *t* runs
`V(t+1) = (V(t) + premie(t)) · (1 + w·r_rendement + (1−w)·r_bescherming)`: the
contribution for a year is paid at the start of it and earns that year's
return, and `w` is read off the lifecycle at the age reached at the start of
the year.

> These are modelling assumptions, not DNB prescriptions — the set only
> supplies the returns.

```python
from dnb_p_set import ScenarioSet
from dnb_p_set.lifecycle import (
    DEFAULT_LIFECYCLE, DEFAULT_MAATMENSEN, Lifecycle, Maatmens, project_wealth,
)

ss = ScenarioSet.from_csv("import/CP2022 P scenarioset 100K 2026Q3.csv")

mens = Maatmens(
    naam="Starter",
    geboortejaar=2001,
    pensioenvermogen=5_000,
    pensioengevend_salaris=34_000,
    premiepercentage=0.30,       # of the salary above the franchise
    franchise=18_000,
    pensioenleeftijd=68,
)

projection = project_wealth(ss, mens, DEFAULT_LIFECYCLE, horizon=20, basisjaar=2026)
projection.percentiles().loc[[1, 10, 20]]   # capital after 1, 10 and 20 years
projection.at(20)                            # raw cross-section, one per scenario
projection.schedule                          # age, weights and premium per year
```

Define your own lifecycle from anchor points; weights are linearly
interpolated between them and flat outside:

```python
eigen = Lifecycle(
    key="defensief",
    label="Defensieve lifecycle",
    anchors=((25, 0.80), (45, 0.65), (60, 0.40), (68, 0.25)),
)
eigen.allocation()               # rendement / bescherming per age
eigen.rendement_weight(52)       # 0.5333…
```

The two portfolio definitions are themselves configurable:

```python
from dnb_p_set.lifecycle import Portefeuille, portefeuille_returns, bond_returns

mixed = Portefeuille(
    key="rendement", label="Rendementsportefeuille",
    equity_weight=0.85, bond_maturity=10, cost=0.0025,
)
portefeuille_returns(ss, mixed, n_years=20)   # (n_scenarios, 20) net returns
bond_returns(ss, maturity=30, n_years=20)     # rolled 30-year zero
```

`compute_metrics` runs the whole thing for the report and accepts
`maatmensen`, `lifecycle`, `portefeuilles`, `wealth_horizons` and `basisjaar`;
pass `maatmensen=[]` to leave the section out.

### Plotting

`dnb_p_set.plotting` holds generic helpers that take raw arrays:

```python
from dnb_p_set import plotting

arr = ss.get("equity_return")

# Fan chart with percentile bands
fig, ax = plotting.plot_fan_chart(arr, title="Equity return fan chart", ylabel="Return")
fig.savefig("equity_fan.png")

# Histogram at a specific time step
fig, ax = plotting.plot_histogram(arr, t=10, title="Equity return at t=10")

# Yield curve fan (uses the yield_curve DataFrame)
yc_df = ss.yield_curve(t=0)
fig, ax = plotting.plot_yield_curve(yc_df, t=0)
```

`dnb_p_set.charts` holds the report charts, which take metrics bundles and
overlay the current set (blue) against the previous one (orange):

```python
from dnb_p_set import charts

fig = charts.starting_curve(current, previous, key="nominal")
fig = charts.curve_fan_grid(current, previous, key="nominal")
fig = charts.rate_path_grid(current, previous, key="nominal")
fig = charts.return_histogram(current, previous, key="equity", horizon=20)
fig = charts.annualised_fan(current, previous, key="equity")
fig = charts.correlation_heatmap(current, previous)

# Lifecycle charts are built from the current set only
fig = charts.lifecycle_allocation(current)
fig = charts.maatmens_wealth_fan(current)
fig = charts.maatmens_horizon_boxes(current)

uri = charts.figure_to_data_uri(fig)   # inline into HTML
```

---

## HTML report

A single self-contained HTML file (charts inlined as data URIs, no assets
alongside it) covering:

| Section | Contents |
|---|---|
| **Kernbevindingen** | KPI tiles with the change versus the previous set, flagged when the change is inside the combined Monte-Carlo standard error; faceted delta bar chart |
| **Rentetermijnstructuur** | Starting curve per measure (nominal / real EU / real NL) with the change in bp per maturity; cross-sectional curve distribution at t = 0, 1, 5, 10, 20, 40; percentile fans of the 1y/10y/30y/50y rate over the whole projection; implied break-even inflation |
| **Aandelenrendement** | One-year and long-horizon return distributions, annualised-return fan, cumulative index fan (log scale), mean/volatility stability per projection year, distribution statistics per horizon |
| **Prijsinflatie NL & EU** | The same treatment for both inflation blocks |
| **Verplichtingenproxy** | Present value and Macaulay duration of a flat 60-year cashflow on the nominal curve — turns a curve shift into a value |
| **Samenhang** | Year-1 correlation matrix plus its change; automatically flags variable pairs that move in lockstep |
| **Maatmens en lifecycle** | Allocation per age over the return and protection portfolios; the parameters of a handful of maatmensen; their projected capital over the whole horizon and at 1, 10 and 20 years |

Every chart carries the table it was drawn from in a collapsible block.

```bash
dnb-p-set-report --current "import/CP2022 P scenarioset 100K 2026Q3.csv" --output report.html

# With comparison to the previous quarter
dnb-p-set-report \
  --current  "import/CP2022 P scenarioset 100K 2026Q3.csv" \
  --previous "import/CP2022 P scenarioset 100K 2026Q2.csv" \
  --output   report.html
```

Or without installing the package: `python generate_report.py --current … --output …`.

Labels (`2026Q3`, `2026Q2`) are read from the filename; override with `--label`
/ `--previous-label`, and the report title with `--title`.

Each set is loaded, reduced to metrics, then released, so peak memory stays at
roughly one set (~0.5 GB) rather than two. A full two-file run takes about
2.5 minutes on a 1.1 GB pair.

```python
from dnb_p_set import ScenarioSet, compute_metrics, build_html_report

current = compute_metrics(ScenarioSet.from_csv("2026Q3.csv"), label="2026Q3")
previous = compute_metrics(
    ScenarioSet.from_csv("2026Q2.csv"), label="2026Q2", reference=current
)

with open("report.html", "w", encoding="utf-8") as f:
    f.write(build_html_report(current, previous))
```

Passing `reference=current` makes the previous set reuse the current set's
histogram bins, so the two distributions are drawn on identical bins.
`build_html_report` also accepts raw `ScenarioSet` objects and will reduce them
itself.

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

## Changes in 0.2.0

Two corrections change results, so pin `0.1.x` if you depend on the old
behaviour:

- **`yield_curve` now follows DNB formula (1)** and returns an annually
  compounded rate, `exp(-A/τ) - 1`. It previously returned the continuously
  compounded `-A/τ`, roughly 3–5 bp lower. Pass `compounding="continuous"` for
  the old numbers.
- **`cumulative_return` / `annualised_return` now treat the input as simple
  returns**, which is what DNB publishes, compounding with `Π(1+r)` instead of
  `exp(Σ r)`. Pass `log_returns=True` for the old behaviour.

New: `dnb_p_set.curves` (term-structure maths), `dnb_p_set.metrics` (report
metrics bundles), `dnb_p_set.charts` (report charts), `dnb_p_set.lifecycle`
(maatmens wealth projection), a single-pass CSV loader, and a rebuilt HTML
report.

---

## License

[MIT](LICENSE)
