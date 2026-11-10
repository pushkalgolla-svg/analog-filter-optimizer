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
- **Statistical Monte Carlo Sensitivity & Compliance Analysis**:
  - $N$-trial batch SPICE simulation modeling component manufacturing tolerances (Gaussian distribution with $3\sigma = \text{tolerance}$).
  - Computes sample mean ($\mu$), sample standard deviation ($s$), Mean 95% Confidence Interval ($\mu \pm 1.96 \cdot s/\sqrt{N}$), Approximate 95% Distribution Band ($\mu \pm 1.96s$), and Empirical 95% Percentile Interval ($[P_{2.5}, P_{97.5}]$).
  - Evaluates Cutoff Frequency Compliance Yield against $\pm 2\%$ and $\pm 5\%$ specification windows (clearly identified as measuring cutoff frequency tolerance compliance, distinct from full board manufacturing yield).
- **Production BOM & KiCad 8 Export**:
  - Generates CSV Bill of Materials strictly from verified manufacturer part catalogues (Yageo, Murata, Texas Instruments OPA1678) or labels non-catalogue values explicitly as `Generic - MPN not verified` (no fabricated part numbers).
  - Enforces active manufacturer lifecycle status validation (e.g., active 100V C0G Murata capacitors replacing NRND 50V parts).
  - Maps physical multi-unit IC packages accurately: the 4th-order cascaded Sallen-Key LPF maps its two amplifier sections to Units A and B of a single physical dual-channel OPA1678 (`U1`, SOIC-8) in both BOM and KiCad schematic netlists.
  - Generates standard KiCad schematic netlists (`.net`) for PCB layout import.
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

### 3. Run Automated Regression Test Suite
```powershell
.\.venv\Scripts\python.exe scripts/test_pipeline.py
```
All **11/11 automated checks** will run in isolation and verify SPICE detection, netlist generation, frequency parsing, E-series snapping, and multi-topology performance.
