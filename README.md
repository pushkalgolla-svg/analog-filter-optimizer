# Analog Filter Synthesizer & SPICE Verification Studio

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![SPICE](https://img.shields.io/badge/SPICE-ngspice_47-red.svg)](http://ngspice.sourceforge.net/)
[![EDA](https://img.shields.io/badge/EDA-KiCad_8_Ready-green.svg)](https://www.kicad.org/)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://pushkal-filter-studio.streamlit.app/)

An end-to-end analog active and passive filter synthesis engine powered by continuous numerical optimization (SciPy Nelder-Mead simplex), direct SPICE simulation verification (`ngspice`), automated commercial component snapping across decade boundaries (E12, E24, E96), statistical Monte Carlo cutoff frequency compliance analysis, verified manufacturing BOM generation, KiCad schematic export, and an interactive web studio.

🌐 **Live Web Application**: [https://pushkal-filter-studio.streamlit.app/](https://pushkal-filter-studio.streamlit.app/)

> 📄 **Looking for portfolio case study details and resume bullet points?**  
> See the dedicated [PORTFOLIO_CASE_STUDY.md](PORTFOLIO_CASE_STUDY.md) for full circuit derivations, architecture diagrams, and technical interview talking points.

---

## Key Features

- **Multi-Topology Synthesis & Tailored Sizing Methods**:
  - **1st-Order Passive RC Low-Pass Filter** ($-20\text{ dB/decade}$ roll-off) — *Nelder-Mead simplex optimization in logarithmic space*
  - **2nd-Order Active Sallen-Key Low-Pass Filter** ($-40\text{ dB/decade}$ roll-off, Butterworth $Q = 0.7071$) — *Nelder-Mead simplex numerical optimization with joint cutoff and damping penalty*
  - **2nd-Order Active Sallen-Key High-Pass Filter** ($+40\text{ dB/decade}$ roll-off, Butterworth $Q = 0.7071$) — *Nelder-Mead simplex numerical optimization with high-pass damping penalty*
  - **2nd-Order Multiple-Feedback (MFB) Band-Pass Filter** (Center $f_0$, adjustable $Q$ & Bandwidth) — *Nelder-Mead simplex numerical optimization targeting resonance and selectivity*
  - **4th-Order Cascaded Sallen-Key Low-Pass Filter** ($-80\text{ dB/decade}$ brickwall roll-off) — ***Analytical Closed-Form Sizing Path*** *decomposing the 4th-order Butterworth polynomial into exact cascaded biquad pole-placements ($Q_1 = 0.5412$, $Q_2 = 1.3065$)*
- **Continuous Parameter Optimization & Failure Validation**:
  - Nelder-Mead simplex algorithm operating in logarithmic component space ($\log_{10} R, \log_{10} C$) to prevent scaling issues and guarantee positive component values.
  - Full optimizer validation: checks convergence status (`res.success`, `res.message`), rejects non-finite objective values, rejects failure sentinel objectives ($10^{12}$), and validates positive physical component values before SPICE verification.
- **Coupled Commercial Snapping**:
  - Discrete coupled grid search pairing standard E12/E24 capacitors with closest standard E96 resistors to maintain $< 0.15\%$ cutoff error.
- **High-Accuracy Op-Amp Simulation Models**:
  - **Texas Instruments OPA167x PSpice Macro-Model (Rev E)**: Integrated natively into `ngspice` using isolated directory `.spiceinit` with `set ngbehavior=pslt` compatibility mode without altering pristine vendor source code. Model revision: Texas Instruments OPA167x PSpice Model Rev E (released 2016, revised May 2021); distinct from the hardware electrical datasheet revision (Texas Instruments OPA1678/OPA1679 Datasheet SBOS855D, revised 2023).
  - **Idealized VCVS Fallback**: High-gain voltage-controlled voltage source ($A_{OL} = 100,000$) explicitly retained and labeled as an idealized benchmark.
  - **Model Provenance**: Pristine vendor model preserved in `src/models/OPA167x.LIB` with recorded SHA-256 integrity checksum (`a4a2f63b714c799bd4ccbf52fa71922d2786f93fcdfcc10f0b11377194beef77`) and full provenance tracking.
- **Preliminary KiCad 8 EDA Netlist Export & Power Architecture**:
  - **Preliminary EDA Netlist Disclaimer**: Generates schematic netlists (`.net`) for PCB design import, explicitly disclaimed as preliminary EDA exports subject to PCB DRC, ERC, routing parasitics, and board-level hardware validation before physical fabrication.
  - **External Signal & Power Connectors**:
    - Input Signal Header (`J_IN`, 2-pin 2.54mm header): Pin 1 = `IN` (signal), Pin 2 = `GND`.
    - Output Signal Header (`J_OUT`, 2-pin 2.54mm header): Pin 1 = `OUT` (signal), Pin 2 = `GND`.
    - Dual Rail Power Header (`J_PWR`, 3-pin 2.54mm header for active topologies): Pin 1 = `V+` (+15V), Pin 2 = `GND` (ground reference), Pin 3 = `V-` (-15V). Passive 1st-order RC circuits omit `J_PWR`.
  - **True Dual-Rail Supplies**: Configurable $\pm 15\text{ V}$ dual supply architecture matching OPA1678 recommended operating conditions ($4.5\text{ V}$ to $36\text{ V}$).
  - **Accurate SOIC-8 Pin Mapping**: Pin 1 (OUT A), Pin 2 (-IN A), Pin 3 (+IN A), Pin 4 (V-), Pin 5 (+IN B), Pin 6 (-IN B), Pin 7 (OUT B), Pin 8 (V+). Pin 4 connects strictly to V- and is never grounded.
  - **Power Decoupling Provisions**: Dedicated $100\text{ nF}$ 50V X7R ceramic capacitors (`C_DEC1` on V+, `C_DEC2` on V-) included in both KiCad netlists and BOM exports.
  - **Unused Section B Termination**: Single-stage 2nd-order filters terminate unused Channel B per Texas Instruments Application Report SLOA067 (Pin 5 tied to GND, Pins 6-7 shorted to prevent oscillation and excess supply current).
  - **Multi-Unit Package Mapping**: 4th-order cascaded filters accurately map both stages to Sections A and B of a single physical dual-channel OPA1678 (`U1`, SOIC-8).
- **Multi-User Session Isolation & Concurrent Execution**:
  - **Thread-Safe Workspace Isolation**: Every synthesis and Monte Carlo simulation executes within an ephemeral temporary directory (`tempfile.TemporaryDirectory`), completely eliminating race conditions and file collisions under multi-user concurrency.
  - **Request-Scoped Output Isolation**: The Streamlit web studio and synthesis pipeline assign unique output directories (`output/session_<id>/`) per synthesis run, eliminating reliance on shared static file writes (`current_sim.cir`, `sim_data.txt`) across concurrent sessions.
  - **Portable SPICE Relative Pathing**: Committed SPICE templates and generated simulation netlists use portable relative include and output paths, preventing machine-specific absolute path contamination across operating systems.
  - **Non-Convergent Trial Tracking**: Robust `MonteCarloResult` separates valid converged measurements from failed/non-convergent trials, calculating statistics and yield strictly over valid trials and flagging yield completion when non-convergent runs occur.
- **Statistical Monte Carlo Sensitivity & Compliance Analysis**:
  - $N$-trial batch SPICE simulation modeling component manufacturing tolerances (Gaussian distribution with $3\sigma = \text{tolerance}$).
  - Computes sample mean ($\mu$), sample standard deviation ($s$), Mean 95% Confidence Interval ($\mu \pm 1.96 \cdot s/\sqrt{N}$), Approximate 95% Distribution Band ($\mu \pm 1.96s$), and Empirical 95% Percentile Interval ($[P_{2.5}, P_{97.5}]$).
  - Evaluates Cutoff Frequency Compliance Yield against $\pm 2\%$ and $\pm 5\%$ specification windows (clearly identified as measuring cutoff frequency tolerance compliance, distinct from full board manufacturing yield).
- **Preliminary Bill of Materials (BOM) & Sourcing**:
  - Generates CSV Bill of Materials strictly from verified manufacturer part catalogues (Yageo, Murata, Texas Instruments OPA1678) or labels generic/unverified components (such as generic pin headers) explicitly as `Generic - MPN not verified` with lifecycle status `Unverified` (no fabricated part numbers).
  - Clearly identified as preliminary engineering documentation requiring physical mechanical enclosure, connector qualification, and layout design verification before production release.
  - Enforces active manufacturer lifecycle status validation (e.g., active 100V C0G Murata capacitors replacing NRND 50V parts).
  - Maps physical multi-unit IC packages accurately: the 4th-order cascaded Sallen-Key LPF maps its two amplifier sections to Units A and B of a single physical dual-channel OPA1678 (`U1`, SOIC-8) in both BOM and KiCad schematic netlists.
- **Interactive Web Studio**:
  - Modern Streamlit UI with live frequency tuning, interactive Bode plots, Monte Carlo yield gauges, and one-click BOM/netlist downloads.

---

## Directory Structure

```
analog_filter_synthesis/
├── .venv/                         # Python 3.11 virtual environment
├── app.py                         # Streamlit interactive web studio dashboard
├── PORTFOLIO_CASE_STUDY.md        # Comprehensive portfolio case study & resume guide
├── src/
│   ├── lowpass_template.cir       # 1st-order passive RC template
│   ├── sallen_key_template.cir    # 2nd-order active Sallen-Key Butterworth template
│   ├── hpf_sallen_key_template.cir# 2nd-order active Sallen-Key High-Pass template
│   ├── bpf_mfb_template.cir       # 2nd-order active MFB Band-Pass template
│   ├── cascade4_sallen_key_template.cir # 4th-order cascaded Butterworth template
│   └── current_sim.cir            # Active netlist evaluated during optimization/Monte Carlo
├── scripts/
│   ├── synthesize.py              # Main CLI synthesizer & Monte Carlo engine
│   ├── export_manufacturing.py    # BOM CSV and KiCad netlist exporter
│   └── test_pipeline.py           # Self-contained regression test suite (11 automated checks)
├── output/
│   ├── sim_data.txt               # Raw 401-point AC frequency sweep data (continuous optimal Nelder-Mead)
│   ├── sim_data_commercial.txt    # Raw 401-point AC frequency sweep data (commercial EIA)
│   ├── bode_plot.png              # Bode magnitude response plot
│   ├── monte_carlo_yield.png      # Monte Carlo yield distribution histogram
│   ├── BOM_*.csv                  # Production Bill of Materials
│   └── *_kicad.net                # KiCad 8 schematic netlists
└── tools/
    └── Spice64/bin/ngspice_con.exe# Portable 64-bit ngspice console executable
```

---

## Quickstart & CLI Commands

### 1. Launch the Interactive Web Studio
```powershell
.\.venv\Scripts\streamlit.exe run app.py
```
Open `http://localhost:8501` in your browser to interactively select filter topologies, tune frequencies, run SPICE simulations, inspect Monte Carlo histograms, and download BOMs and netlists.

---

### 2. Synthesize via Command Line

#### 2nd-Order Active Sallen-Key Low-Pass Filter ($1\text{ kHz}$, E96 resistors, with Monte Carlo):
```powershell
.\.venv\Scripts\python.exe scripts/synthesize.py --type lpf --order 2 --target-fc 1000 --series E96 --monte-carlo --mc-trials 50
```

#### 2nd-Order Active Sallen-Key High-Pass Filter ($1\text{ kHz}$):
```powershell
.\.venv\Scripts\python.exe scripts/synthesize.py --type hpf --target-fc 1000 --series E96
```

#### 2nd-Order Multiple-Feedback (MFB) Band-Pass Filter ($1\text{ kHz}$, $Q=2.0$):
```powershell
.\.venv\Scripts\python.exe scripts/synthesize.py --type bpf --target-fc 1000 --q 2.0 --series E96
```

#### 4th-Order Cascaded Sallen-Key Low-Pass Filter ($-80\text{ dB/decade}$ roll-off):
```powershell
.\.venv\Scripts\python.exe scripts/synthesize.py --type lpf --order 4 --target-fc 1000 --series E96
```

#### 1st-Order Passive RC Low-Pass Filter ($1\text{ kHz}$, E24):
```powershell
.\.venv\Scripts\python.exe scripts/synthesize.py --type lpf --order 1 --target-fc 1000 --series E24
```

---

### 3. Run Automated Regression Test Suites

#### Full Unit Test Suite (50 Automated Tests):
```powershell
.\.venv\Scripts\python.exe -m unittest tests/test_unit.py
```
Validates optimizer convergence, failure handling, tolerance matching, active BOM lifecycle status, KiCad power net assertions, workspace isolation, and Streamlit dashboard rendering.

#### Full SPICE Integration Test Suite (11 Integration Tests):
```powershell
.\.venv\Scripts\python.exe -m unittest tests/test_integration_spice.py
```
Executes genuine `ngspice` simulations across all five filter topologies with both the official Texas Instruments OPA167x macro-model and idealized VCVS, confirming convergence, frequency accuracy, and thread-safe concurrent simulation.
