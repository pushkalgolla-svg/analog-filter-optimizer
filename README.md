# ML-Based Analog Filter Synthesizer & SPICE Verification Studio

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![SPICE](https://img.shields.io/badge/SPICE-ngspice_47-red.svg)](http://ngspice.sourceforge.net/)
[![EDA](https://img.shields.io/badge/EDA-KiCad_8_Ready-green.svg)](https://www.kicad.org/)
[![Streamlit](https://img.shields.io/badge/GUI-Streamlit-orange.svg)](https://streamlit.io/)

An end-to-end analog active and passive filter synthesis engine powered by numerical optimization (`scipy.optimize.minimize`), direct SPICE simulation verification (`ngspice`), automated commercial component snapping (E12, E24, E96), statistical Monte Carlo manufacturing yield analysis, production BOM generation, KiCad schematic export, and an interactive web studio.

> 📄 **Looking for portfolio case study details and resume bullet points?**  
> See the dedicated [PORTFOLIO_CASE_STUDY.md](PORTFOLIO_CASE_STUDY.md) for full circuit derivations, architecture diagrams, and technical interview talking points.

---

## Key Features

- **Multi-Topology Synthesis**:
  - **1st-Order Passive RC Low-Pass Filter** ($-20\text{ dB/decade}$ roll-off)
  - **2nd-Order Active Sallen-Key Low-Pass Filter** ($-40\text{ dB/decade}$ roll-off, Butterworth $Q = 0.7071$)
  - **2nd-Order Active Sallen-Key High-Pass Filter** ($+40\text{ dB/decade}$ roll-off, Butterworth $Q = 0.7071$)
  - **2nd-Order Multiple-Feedback (MFB) Band-Pass Filter** (Center $f_0$, adjustable $Q$ & Bandwidth)
  - **4th-Order Cascaded Sallen-Key Low-Pass Filter** ($-80\text{ dB/decade}$ brickwall roll-off, $Q_1 = 0.5412$, $Q_2 = 1.3065$)
- **Continuous Parameter Optimization**:
  - Nelder-Mead simplex algorithm operating in logarithmic component space ($\log_{10} R, \log_{10} C$) to prevent scaling issues and guarantee positive component values.
- **Coupled Commercial Snapping**:
  - Discrete coupled grid search pairing standard E12/E24 capacitors with closest standard E96 resistors to maintain $< 0.15\%$ cutoff error.
- **Statistical Monte Carlo Sensitivity & Yield Analysis**:
  - $N$-trial batch SPICE simulation modeling component manufacturing tolerances (Gaussian distribution with $3\sigma = \text{tolerance}$).
  - Computes $\mu$, $\sigma$, $95\%$ confidence interval, and manufacturing yield against $\pm 2\%$ and $\pm 5\%$ specification windows.
- **Production BOM & KiCad 8 Export**:
  - Generates CSV Bill of Materials with real manufacturer part numbers (Yageo, Murata, Texas Instruments OPA1678).
  - Generates standard KiCad schematic netlists (`.net`) for PCB design.
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
│   ├── sim_data.txt               # Raw 401-point AC frequency sweep data (continuous ML)
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
