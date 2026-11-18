# Design System: Analog Filter Synthesizer EDA ("Instruments Precision")

## 1. Design Direction & Mode
* **Surface Mode**: **Operate** (Precision Engineering Tool).
* **Atmosphere**: Professional EDA instrument aesthetic (inspired by modern digital oscilloscopes, spectrum analyzers, and Keysight/Tektronix test bench interfaces).
* **Guiding Principles**:
  - **High Information Density with Visual Restraint**: Maximize screen real estate for technical plots and telemetry without clutter.
  - **Zero Visual Jarring**: Cohesive dark-theme canvas across Streamlit widgets, code viewers, and embedded Matplotlib frequency plots.
  - **Monospace Readouts**: All scientific values, units, tolerances, and reference designators use crisp monospace typography.

## 2. Color Palette & Semantic Tokens
* **Base & Surface**:
  - Background Canvas: `#0B0F17` (Deep obsidian)
  - Card & Container Surface: `#131B2A` (Elevated slate blue)
  - Card Border / Dividers: `#1E293B` / `rgba(255, 255, 255, 0.08)`
  - Elevated Highlight: `#1E293B`
* **Signal Traces & Data**:
  - Primary / Physical Snapped: `#38BDF8` (Vibrant electric cyan)
  - Target / Continuous Optimal: `#F59E0B` (Warm amber gold)
  - Passband Fill: `rgba(56, 189, 248, 0.06)`
  - Cutoff / Threshold Line: `#F43F5E` (Rose / Crimson)
  - Butterworth Reference: `#A855F7` (Purple)
  - Success / Compliance: `#10B981` (Emerald green)
* **Text Hierarchy**:
  - Primary Text: `#F8FAFC` (Pure bright slate)
  - Secondary / Units: `#94A3B8` (Cool muted slate)
  - Microcopy / Footnotes: `#64748B` (Deep muted slate)

## 3. Typography & Sizing
* **Interface Font**: System UI sans-serif (`Inter`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `Roboto`).
* **Telemetry Font**: High-legibility tabular monospace (`ui-monospace`, `SFMono-Regular`, `Menlo`, `Monaco`, `Consolas`, `monospace`).
* **KPI Metrics**:
  - Micro-label: 11px uppercase, letter-spacing +0.05em, text-transform uppercase.
  - Metric Value: 24px bold tabular monospace.
  - Delta / Target: 12px pill badge with semi-transparent tinted background.

## 4. Plot Styling Guidelines
* All embedded Matplotlib plots must inherit the studio dark theme:
  - Figure background: `#0F172A`
  - Axes background: `#0B1120`
  - Grid: Semi-transparent dashed `#1E293B` (alpha 0.7)
  - Spines: `#334155`
  - Text & Ticks: `#94A3B8` (fontsize 9–10)
  - Legends: Semi-transparent dark background (`#131B2A`), 1px subtle border.
