"""
Analog Filter Synthesizer, Numerical Optimizer, and Monte Carlo Tolerance Analysis Pipeline.

Synthesizes analog filters to hit target cutoff frequency (fc) and Butterworth damping
using numerical optimization (SciPy Nelder-Mead) with SPICE simulation in the loop,
automated EIA commercial component snapping (E12, E24, E96), statistical Monte Carlo
cutoff frequency yield analysis, BOM generation with verified catalog components, and KiCad export.

Supported topologies:
1. 1st-Order Passive RC Low-Pass Filter (-20 dB/dec)
2. 2nd-Order Active Sallen-Key Low-Pass Filter (-40 dB/dec, Butterworth Q=0.7071)
3. 2nd-Order Active Sallen-Key High-Pass Filter (+40 dB/dec, Butterworth Q=0.7071)
4. 2nd-Order Active Multiple-Feedback (MFB) Band-Pass Filter (center f0, Q, BW)
5. 4th-Order Cascaded Sallen-Key Low-Pass Filter (-80 dB/dec, Butterworth Q1=0.5412, Q2=1.3065)
"""

import argparse
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize

try:
    from scripts.export_manufacturing import generate_bom_data, export_bom_csv, export_kicad_netlist
except ImportError:
    from export_manufacturing import generate_bom_data, export_bom_csv, export_kicad_netlist

# Define project directory paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
OUTPUT_DIR = PROJECT_ROOT / "output"

TEMPLATE_1ST_ORDER = SRC_DIR / "lowpass_template.cir"
TEMPLATE_2ND_ORDER = SRC_DIR / "sallen_key_template.cir"
TEMPLATE_HPF_2ND = SRC_DIR / "hpf_sallen_key_template.cir"
TEMPLATE_BPF_MFB = SRC_DIR / "bpf_mfb_template.cir"
TEMPLATE_CASCADE4 = SRC_DIR / "cascade4_sallen_key_template.cir"

CURRENT_SIM_PATH = SRC_DIR / "current_sim.cir"
SIM_DATA_PATH = OUTPUT_DIR / "sim_data.txt"
COMMERCIAL_SIM_DATA_PATH = OUTPUT_DIR / "sim_data_commercial.txt"
PLOT_PATH = OUTPUT_DIR / "bode_plot.png"
MC_PLOT_PATH = OUTPUT_DIR / "monte_carlo_yield.png"

# Target Specifications
TARGET_CUTOFF_HZ = 1000.0   # 1 kHz (-3dB cutoff point)
BUTTERWORTH_Q = 1.0 / math.sqrt(2.0)  # Q = 0.7071
SENTINEL_FAILURE_OBJ = 1.0e12  # Sentinel objective value returned on simulation / convergence failure

# EIA Standard E-Series Multipliers
E_SERIES = {
    "E12": [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2],
    "E24": [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
            3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1],
    "E96": [1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18, 1.21, 1.24, 1.27, 1.30,
            1.33, 1.37, 1.40, 1.43, 1.47, 1.50, 1.54, 1.58, 1.62, 1.65, 1.69, 1.74,
            1.78, 1.82, 1.87, 1.91, 1.96, 2.00, 2.05, 2.10, 2.15, 2.21, 2.26, 2.32,
            2.37, 2.43, 2.49, 2.55, 2.61, 2.67, 2.74, 2.80, 2.87, 2.94, 3.01, 3.09,
            3.16, 3.24, 3.32, 3.40, 3.48, 3.57, 3.65, 3.74, 3.83, 3.92, 4.02, 4.12,
            4.22, 4.32, 4.42, 4.53, 4.64, 4.75, 4.87, 4.99, 5.11, 5.23, 5.36, 5.49,
            5.62, 5.76, 5.90, 6.04, 6.19, 6.34, 6.49, 6.65, 6.81, 6.98, 7.15, 7.32,
            7.50, 7.68, 7.87, 8.06, 8.25, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76]
}


def snap_to_e_series(value, series="E24"):
    """
    Snaps an arbitrary component value to the nearest standard E-series value.
    Considers candidates across the previous, current, and next decades to correctly
    handle decade boundaries (e.g. 9.99 kOhm -> 10.0 kOhm).
    Safely validates inputs: raises ValueError for non-positive, zero, NaN, or infinite inputs.
    """
    if not isinstance(value, (int, float, np.number)):
        raise TypeError(f"Component value must be numeric, got {type(value).__name__}")
    if math.isnan(value) or math.isinf(value) or value <= 0:
        raise ValueError(f"Invalid component value for E-series snapping: {value}. Must be a finite positive number.")

    series_key = str(series).upper()
    if series_key not in E_SERIES:
        raise ValueError(f"Unsupported E-series: '{series}'. Must be one of {list(E_SERIES.keys())}.")
    table = E_SERIES[series_key]

    d = int(math.floor(math.log10(value)))
    candidates = []
    # Span previous (d-1), current (d), and next (d+1) decades
    for dec_exp in (d - 1, d, d + 1):
        dec = 10.0 ** dec_exp
        for m in table:
            c = float(f"{m * dec:.12g}")
            candidates.append(c)

    candidates = np.array(candidates)
    diffs = np.abs(candidates - value)
    best_idx = int(np.argmin(diffs))
    return float(candidates[best_idx])


def format_eng(val, unit=""):
    """Formats numeric value to human-readable engineering notation."""
    if val >= 1e6:
        return f"{val / 1e6:.3g} M{unit}"
    elif val >= 1e3:
        return f"{val / 1e3:.3g} k{unit}"
    elif val >= 1:
        return f"{val:.3g} {unit}"
    elif val >= 1e-3:
        return f"{val * 1e3:.3g} m{unit}"
    elif val >= 1e-6:
        return f"{val * 1e6:.3g} u{unit}"
    elif val >= 1e-9:
        return f"{val * 1e9:.3g} n{unit}"
    elif val >= 1e-12:
        return f"{val * 1e12:.3g} p{unit}"
    return f"{val:.3e} {unit}"


def find_ngspice(custom_path=None):
    """Locates the ngspice executable, preferring ngspice_con.exe on Windows."""
    candidates = []
    if custom_path:
        candidates.append(Path(custom_path))
    if os.environ.get("NGSPICE_PATH"):
        candidates.append(Path(os.environ["NGSPICE_PATH"]))

    tools_dir = PROJECT_ROOT / "tools"
    if tools_dir.exists():
        candidates.extend(list(tools_dir.rglob("ngspice_con.exe")))
        candidates.extend(list(tools_dir.rglob("ngspice.exe")))

    for name in ["ngspice_con", "ngspice_con.exe", "ngspice", "ngspice.exe"]:
        which_path = shutil.which(name)
        if which_path:
            candidates.append(Path(which_path))

    for base in [Path("C:/Spice64/bin"), Path("C:/Program Files/ngspice/bin"), Path("C:/Program Files (x86)/ngspice/bin")]:
        candidates.append(base / "ngspice_con.exe")
        candidates.append(base / "ngspice.exe")

    for p in candidates:
        if p.is_file():
            return str(p.resolve())

    return None


def run_spice_simulation(params, order=1, filter_type="lpf", ngspice_bin=None, fallback=False, output_data_file=SIM_DATA_PATH, target_fc=TARGET_CUTOFF_HZ):
    """Injects component values into the netlist template and executes SPICE."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SRC_DIR.mkdir(parents=True, exist_ok=True)

    f_start = max(1.0, target_fc / 100.0)
    f_stop = min(1e8, target_fc * 100.0)
    f_start_str = f"{f_start:.2f}"
    f_stop_str = f"{f_stop:.2f}"

    if filter_type == "lpf":
        if order == 1:
            r_val, c_val = params
            template_code = TEMPLATE_1ST_ORDER.read_text(encoding="utf-8")
            sim_code = (template_code
                        .replace("{R_VAL}", f"{r_val:.8e}")
                        .replace("{C_VAL}", f"{c_val:.8e}")
                        .replace("{F_START}", f_start_str)
                        .replace("{F_STOP}", f_stop_str))
        elif order == 2:
            r1, r2, c1, c2 = params
            template_code = TEMPLATE_2ND_ORDER.read_text(encoding="utf-8")
            sim_code = (template_code
                        .replace("{R1_VAL}", f"{r1:.8e}")
                        .replace("{R2_VAL}", f"{r2:.8e}")
                        .replace("{C1_VAL}", f"{c1:.8e}")
                        .replace("{C2_VAL}", f"{c2:.8e}")
                        .replace("{F_START}", f_start_str)
                        .replace("{F_STOP}", f_stop_str))
        elif order == 4:
            r1_1, r2_1, c1_1, c2_1, r1_2, r2_2, c1_2, c2_2 = params
            template_code = TEMPLATE_CASCADE4.read_text(encoding="utf-8")
            sim_code = (template_code
                        .replace("{R1_1_VAL}", f"{r1_1:.8e}")
                        .replace("{R2_1_VAL}", f"{r2_1:.8e}")
                        .replace("{C1_1_VAL}", f"{c1_1:.8e}")
                        .replace("{C2_1_VAL}", f"{c2_1:.8e}")
                        .replace("{R1_2_VAL}", f"{r1_2:.8e}")
                        .replace("{R2_2_VAL}", f"{r2_2:.8e}")
                        .replace("{C1_2_VAL}", f"{c1_2:.8e}")
                        .replace("{C2_2_VAL}", f"{c2_2:.8e}")
                        .replace("{F_START}", f_start_str)
                        .replace("{F_STOP}", f_stop_str))
    elif filter_type == "hpf":
        r1, r2, c1, c2 = params
        template_code = TEMPLATE_HPF_2ND.read_text(encoding="utf-8")
        sim_code = (template_code
                    .replace("{R1_VAL}", f"{r1:.8e}")
                    .replace("{R2_VAL}", f"{r2:.8e}")
                    .replace("{C1_VAL}", f"{c1:.8e}")
                    .replace("{C2_VAL}", f"{c2:.8e}")
                    .replace("{F_START}", f_start_str)
                    .replace("{F_STOP}", f_stop_str))
    elif filter_type == "bpf":
        r1, r2, r3, c1, c2 = params
        template_code = TEMPLATE_BPF_MFB.read_text(encoding="utf-8")
        sim_code = (template_code
                    .replace("{R1_VAL}", f"{r1:.8e}")
                    .replace("{R2_VAL}", f"{r2:.8e}")
                    .replace("{R3_VAL}", f"{r3:.8e}")
                    .replace("{C1_VAL}", f"{c1:.8e}")
                    .replace("{C2_VAL}", f"{c2:.8e}")
                    .replace("{F_START}", f_start_str)
                    .replace("{F_STOP}", f_stop_str))
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")

    CURRENT_SIM_PATH.write_text(sim_code, encoding="utf-8")

    if fallback or not ngspice_bin:
        # Analytical AC Transfer Function Simulation
        freqs = np.logspace(np.log10(f_start), np.log10(f_stop), 401)
        w = 2.0 * np.pi * freqs
        s = 1j * w

        if filter_type == "lpf":
            if order == 1:
                h = 1.0 / (1.0 + s * params[0] * params[1])
            elif order == 2:
                r1, r2, c1, c2 = params
                h = 1.0 / ((s**2) * (r1 * r2 * c1 * c2) + s * (c2 * (r1 + r2)) + 1.0)
            elif order == 4:
                r1_1, r2_1, c1_1, c2_1, r1_2, r2_2, c1_2, c2_2 = params
                h1 = 1.0 / ((s**2) * (r1_1 * r2_1 * c1_1 * c2_1) + s * (c2_1 * (r1_1 + r2_1)) + 1.0)
                h2 = 1.0 / ((s**2) * (r1_2 * r2_2 * c1_2 * c2_2) + s * (c2_2 * (r1_2 + r2_2)) + 1.0)
                h = h1 * h2
        elif filter_type == "hpf":
            r1, r2, c1, c2 = params
            num = (s**2) * (r1 * r2 * c1 * c2)
            denom = (s**2) * (r1 * r2 * c1 * c2) + s * (r1 * (c1 + c2)) + 1.0
            h = num / denom
        elif filter_type == "bpf":
            r1, r2, r3, c1, c2 = params
            num = -s * (1.0 / (r1 * c1))
            denom = (s**2) + s * ((c1 + c2) / (r3 * c1 * c2)) + ((r1 + r2) / (r1 * r2 * r3 * c1 * c2))
            h = num / denom

        vdb = 20.0 * np.log10(np.maximum(np.abs(h), 1e-12))
        with open(output_data_file, "w", encoding="utf-8") as f:
            for fr, db in zip(freqs, vdb):
                f.write(f"{fr:15.8e}  {db:15.8e}\n")
        return

    cmd = [ngspice_bin, "-b", str(CURRENT_SIM_PATH)]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ngspice failed:\n{result.stderr}")

    if output_data_file != SIM_DATA_PATH and SIM_DATA_PATH.exists():
        shutil.copyfile(SIM_DATA_PATH, output_data_file)


def parse_simulation_data(data_path=SIM_DATA_PATH):
    """Parses frequency and magnitude columns from ngspice wrdata export."""
    if not data_path.exists():
        raise FileNotFoundError(f"Simulation data file missing: {data_path}")

    freqs, mags = [], []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    freqs.append(float(parts[0]))
                    mags.append(float(parts[1]))
                except ValueError:
                    continue
    return np.array(freqs), np.array(mags)


def extract_cutoff_frequency(freqs, mags, filter_type="lpf", db_drop=3.0103):
    """Calculates continuous -3dB cutoff frequency using linear interpolation."""
    if len(freqs) == 0 or len(mags) == 0:
        return (0.0, 0.0, 0.0) if filter_type == "bpf" else 0.0

    if filter_type == "lpf":
        passband_mag = mags[0]
        cutoff_mag = passband_mag - db_drop
        if cutoff_mag > mags[0]:
            return freqs[0]
        if cutoff_mag < mags[-1]:
            return freqs[-1]
        return float(np.interp(cutoff_mag, mags[::-1], freqs[::-1]))
    elif filter_type == "hpf":
        passband_mag = mags[-1]
        cutoff_mag = passband_mag - db_drop
        if cutoff_mag > mags[-1]:
            return freqs[-1]
        if cutoff_mag < mags[0]:
            return freqs[0]
        return float(np.interp(cutoff_mag, mags, freqs))
    elif filter_type == "bpf":
        peak_idx = int(np.argmax(mags))
        f_peak = float(freqs[peak_idx])
        peak_val = mags[peak_idx]
        below = np.where(mags >= peak_val - db_drop)[0]
        if len(below) >= 2:
            f_l = float(freqs[below[0]])
            f_h = float(freqs[below[-1]])
            bw = max(1.0, f_h - f_l)
            q = f_peak / bw
        else:
            bw = f_peak / 2.0
            q = 2.0
        return f_peak, q, bw
    return freqs[0]


def loss_function(params, order=1, filter_type="lpf", ngspice_bin=None, fallback=False, target_fc=TARGET_CUTOFF_HZ, target_q=BUTTERWORTH_Q, output_data_file=SIM_DATA_PATH):
    """Evaluates filter loss: cutoff error + damping penalty."""
    try:
        run_spice_simulation(params, order=order, filter_type=filter_type, ngspice_bin=ngspice_bin, fallback=fallback, output_data_file=output_data_file, target_fc=target_fc)
        freqs, mags = parse_simulation_data(output_data_file)
        if len(freqs) < 2 or len(mags) < 2:
            return 0.0, 0.0, SENTINEL_FAILURE_OBJ

        if filter_type == "lpf":
            actual_fc = extract_cutoff_frequency(freqs, mags, filter_type="lpf")
            if not np.isfinite(actual_fc) or actual_fc <= 0:
                return 0.0, 0.0, SENTINEL_FAILURE_OBJ
            if order == 1:
                error = (actual_fc - target_fc) ** 2
                return actual_fc, 0.0, error
            elif order == 2:
                r1, r2, c1, c2 = params
                denom = c2 * (r1 + r2)
                prod = r1 * r2 * c1 * c2
                if denom <= 0 or prod <= 0:
                    return 0.0, 0.0, SENTINEL_FAILURE_OBJ
                q_actual = math.sqrt(prod) / denom
                error = (actual_fc - target_fc) ** 2 + 1000.0 * (q_actual - BUTTERWORTH_Q) ** 2
                return actual_fc, q_actual, error
            elif order == 4:
                error = (actual_fc - target_fc) ** 2
                return actual_fc, 0.7071, error
        elif filter_type == "hpf":
            actual_fc = extract_cutoff_frequency(freqs, mags, filter_type="hpf")
            if not np.isfinite(actual_fc) or actual_fc <= 0:
                return 0.0, 0.0, SENTINEL_FAILURE_OBJ
            r1, r2, c1, c2 = params
            denom = r1 * (c1 + c2)
            prod = r1 * r2 * c1 * c2
            if denom <= 0 or prod <= 0:
                return 0.0, 0.0, SENTINEL_FAILURE_OBJ
            q_actual = math.sqrt(prod) / denom
            error = (actual_fc - target_fc) ** 2 + 1000.0 * (q_actual - BUTTERWORTH_Q) ** 2
            return actual_fc, q_actual, error
        elif filter_type == "bpf":
            f_peak, q_actual, _ = extract_cutoff_frequency(freqs, mags, filter_type="bpf")
            if not np.isfinite(f_peak) or f_peak <= 0:
                return 0.0, 0.0, SENTINEL_FAILURE_OBJ
            error = (f_peak - target_fc) ** 2 + 500.0 * (q_actual - target_q) ** 2
            return f_peak, q_actual, error
    except Exception:
        return 0.0, 0.0, SENTINEL_FAILURE_OBJ
    return 0.0, 0.0, SENTINEL_FAILURE_OBJ


# Commercial Snapping Algorithms
def find_commercial_pair_1st_order(target_fc, r_series="E24", c_series="E12"):
    """Finds best commercial (R, C) pair for 1st-order passive RC filter."""
    c_table = E_SERIES.get(c_series.upper(), E_SERIES["E12"])
    best = None
    min_err = float("inf")
    c_candidates = [m * (10.0 ** exp) for exp in range(-10, -5) for m in c_table]
    for c in c_candidates:
        r_ideal = 1.0 / (2.0 * math.pi * target_fc * c)
        if 500.0 <= r_ideal <= 500000.0:
            r_std = snap_to_e_series(r_ideal, r_series)
            fc = 1.0 / (2.0 * math.pi * r_std * c)
            err = abs(fc - target_fc)
            if err < min_err:
                min_err = err
                best = (r_std, c, fc, err)
    return best


def find_commercial_components_2nd_order(target_fc, r_series="E96", c_series="E12"):
    """Finds standard components (R1, R2, C1, C2) for 2nd-order Sallen-Key Butterworth LPF."""
    c_table = E_SERIES.get(c_series.upper(), E_SERIES["E12"])
    c2_candidates = [m * (10.0 ** exp) for exp in range(-10, -6) for m in c_table]
    best = None
    min_cost = float("inf")
    for c2 in c2_candidates:
        c1 = snap_to_e_series(2.2 * c2, c_series)
        k = c1 / c2
        if 2.0 * (k - 1) < 2.0:
            continue
        disc = 4.0 * ((k - 1) ** 2) - 4.0
        if disc < 0:
            continue
        ratio = (2.0 * (k - 1) + math.sqrt(disc)) / 2.0
        r_geom = 1.0 / (2.0 * math.pi * target_fc * math.sqrt(c1 * c2))
        r2_ideal = r_geom / math.sqrt(ratio)
        r1_ideal = r2_ideal * ratio
        if 500.0 <= r1_ideal <= 500000.0 and 500.0 <= r2_ideal <= 500000.0:
            r1_std = snap_to_e_series(r1_ideal, r_series)
            r2_std = snap_to_e_series(r2_ideal, r_series)
            fc_act = 1.0 / (2.0 * math.pi * math.sqrt(r1_std * r2_std * c1 * c2))
            q_act = math.sqrt(r1_std * r2_std * c1 * c2) / (c2 * (r1_std + r2_std))
            cost = abs(fc_act - target_fc) / target_fc + abs(q_act - BUTTERWORTH_Q) / BUTTERWORTH_Q
            if cost < min_cost:
                min_cost = cost
                best = (r1_std, r2_std, c1, c2, fc_act, q_act)
    return best


def find_commercial_hpf(target_fc, r_series="E96", c_series="E12"):
    """Finds standard components (R1, R2, C1, C2) for 2nd-order Sallen-Key Butterworth HPF."""
    c_table = E_SERIES.get(c_series.upper(), E_SERIES["E12"])
    c_candidates = [m * (10.0 ** exp) for exp in range(-10, -6) for m in c_table]
    best = None
    min_cost = float("inf")
    for c in c_candidates:
        r1_ideal = 1.0 / (2.0 * math.sqrt(2.0) * math.pi * target_fc * c)
        r2_ideal = 2.0 * r1_ideal
        if 500.0 <= r1_ideal <= 500000.0 and 500.0 <= r2_ideal <= 500000.0:
            r1_std = snap_to_e_series(r1_ideal, r_series)
            r2_std = snap_to_e_series(r2_ideal, r_series)
            fc_act = 1.0 / (2.0 * math.pi * math.sqrt(r1_std * r2_std * c * c))
            q_act = math.sqrt(r1_std * r2_std) / (2.0 * r1_std)
            cost = abs(fc_act - target_fc) / target_fc + abs(q_act - BUTTERWORTH_Q) / BUTTERWORTH_Q
            if cost < min_cost:
                min_cost = cost
                best = (r1_std, r2_std, c, c, fc_act, q_act)
    return best


def find_commercial_bpf(target_fc, target_q=2.0, r_series="E96", c_series="E12"):
    """Finds standard components (R1, R2, R3, C1, C2) for 2nd-order MFB Band-Pass filter."""
    c_table = E_SERIES.get(c_series.upper(), E_SERIES["E12"])
    c_candidates = [m * (10.0 ** exp) for exp in range(-10, -6) for m in c_table]
    best = None
    min_cost = float("inf")
    for c in c_candidates:
        r3_ideal = target_q / (math.pi * target_fc * c)
        r1_ideal = r3_ideal / 2.0
        denom = 2.0 * (target_q ** 2) - 1.0
        if denom <= 0:
            continue
        r2_ideal = r1_ideal / denom
        if 500.0 <= r1_ideal <= 500000.0 and 500.0 <= r2_ideal <= 500000.0 and 500.0 <= r3_ideal <= 500000.0:
            r1_std = snap_to_e_series(r1_ideal, r_series)
            r2_std = snap_to_e_series(r2_ideal, r_series)
            r3_std = snap_to_e_series(r3_ideal, r_series)
            f0_act = (1.0 / c) * math.sqrt((1.0 / r3_std) * ((1.0 / r1_std) + (1.0 / r2_std))) / (2.0 * math.pi)
            bw_act = 1.0 / (math.pi * r3_std * c)
            q_act = f0_act / bw_act
            cost = abs(f0_act - target_fc) / target_fc + abs(q_act - target_q) / target_q
            if cost < min_cost:
                min_cost = cost
                best = (r1_std, r2_std, r3_std, c, c, f0_act, q_act)
    return best


def find_commercial_cascade4(target_fc, r_series="E96", c_series="E12"):
    """Finds standard components for 4th-order cascaded Sallen-Key Butterworth LPF."""
    q1 = 0.5412
    q2 = 1.3065

    # Stage 1: Q1 = 0.5412
    c2_1 = 10e-9
    c1_1 = snap_to_e_series(4.0 * (q1 ** 2) * c2_1, c_series)
    r_1_ideal = 1.0 / (2.0 * math.pi * target_fc * math.sqrt(c1_1 * c2_1))
    r1_1 = snap_to_e_series(r_1_ideal, r_series)
    r2_1 = r1_1

    # Stage 2: Q2 = 1.3065
    c2_2 = 4.7e-9
    c1_2 = snap_to_e_series(4.0 * (q2 ** 2) * c2_2, c_series)
    r_2_ideal = 1.0 / (2.0 * math.pi * target_fc * math.sqrt(c1_2 * c2_2))
    r1_2 = snap_to_e_series(r_2_ideal, r_series)
    r2_2 = r1_2

    return (r1_1, r2_1, c1_1, c2_1, r1_2, r2_2, c1_2, c2_2)


def synthesize_filter(filter_type="lpf", order=2, target_fc=TARGET_CUTOFF_HZ, target_q=None,
                      r_series="E96", c_series="E12", ngspice_bin=None, fallback=False,
                      r_tol=None, c_tol=5.0, progress_callback=None, raise_on_error=False):
    """
    Unified synthesis and optimization pipeline shared by both CLI and Streamlit GUI.
    1. Validates input specifications safely.
    2. Runs continuous component optimization:
       - 4th-order LPF: Exact analytical closed-form Butterworth pole-placement sizing.
       - 1st-order, 2nd-order LPF, HPF, BPF: SciPy Nelder-Mead simplex numerical optimization in log10 space.
    3. Validates optimizer convergence, objective value, and component physical sanity.
    4. Simulates and verifies the continuous optimal design against target specs.
    5. Performs coupled EIA standard commercial component snapping (E12, E24, E96).
    6. Simulates and verifies the snapped commercial design against target specs.
    7. Exports verified Bill of Materials (BOM) and KiCad schematic netlists.
    """
    if not isinstance(target_fc, (int, float, np.number)) or math.isnan(target_fc) or math.isinf(target_fc) or target_fc <= 0:
        raise ValueError(f"Target frequency must be a finite positive number, got: {target_fc}")

    filter_type = str(filter_type).lower()
    if filter_type not in ["lpf", "hpf", "bpf"]:
        raise ValueError(f"Unsupported filter type: '{filter_type}'. Must be 'lpf', 'hpf', or 'bpf'.")

    order = int(order)
    if filter_type == "lpf" and order not in [1, 2, 4]:
        raise ValueError(f"Unsupported order for LPF: {order}. Must be 1, 2, or 4.")
    if filter_type in ["hpf", "bpf"]:
        order = 2

    r_series = str(r_series).upper()
    if r_series not in E_SERIES:
        raise ValueError(f"Unsupported resistor series: '{r_series}'. Must be E12, E24, or E96.")
    c_series = "E12"

    if target_q is None:
        target_q = 2.0 if filter_type == "bpf" else BUTTERWORTH_Q

    if r_tol is None:
        r_tol = 1.0 if r_series == "E96" else 5.0

    if ngspice_bin is None:
        ngspice_bin = find_ngspice()
    use_fallback = fallback or not ngspice_bin

    # Initial parameter configuration
    if filter_type == "lpf":
        if order == 1:
            initial_params = [10000.0, 10.0e-9]
            comp_names = ["R1", "C1"]
            top_key = "1st_order_rc"
        elif order == 2:
            initial_params = [10000.0, 10000.0, 22.0e-9, 10.0e-9]
            comp_names = ["R1", "R2", "C1", "C2"]
            top_key = "sallen_key_lpf"
        elif order == 4:
            initial_params = [15000.0, 15000.0, 12e-9, 10e-9, 20000.0, 20000.0, 33e-9, 4.7e-9]
            comp_names = ["R1_1", "R2_1", "C1_1", "C2_1", "R1_2", "R2_2", "C1_2", "C2_2"]
            top_key = "cascade4_lpf"
    elif filter_type == "hpf":
        initial_params = [12000.0, 24000.0, 10.0e-9, 10.0e-9]
        comp_names = ["R1", "R2", "C1", "C2"]
        top_key = "sallen_key_hpf"
    elif filter_type == "bpf":
        initial_params = [30000.0, 4500.0, 60000.0, 10.0e-9, 10.0e-9]
        comp_names = ["R1", "R2", "R3", "C1", "C2"]
        top_key = "mfb_bpf"

    x0 = [np.log10(p) for p in initial_params]
    init_fc, init_q, init_err = loss_function(
        initial_params, order=order, filter_type=filter_type,
        ngspice_bin=ngspice_bin, fallback=use_fallback, target_fc=target_fc, target_q=target_q
    )

    # Stage 1: Continuous Sizing / Numerical Optimization
    iteration_count = [0]
    if filter_type == "lpf" and order == 4:
        optimization_method = "analytical_closed_form"
        # 4th-order cascaded Butterworth uses exact closed-form stage pole-placement
        q1 = 0.5412
        q2 = 1.3065
        c2_1 = 10e-9
        c1_1 = 4.0 * (q1 ** 2) * c2_1
        r_1 = 1.0 / (4.0 * math.pi * target_fc * q1 * c2_1)
        c2_2 = 4.7e-9
        c1_2 = 4.0 * (q2 ** 2) * c2_2
        r_2 = 1.0 / (4.0 * math.pi * target_fc * q2 * c2_2)
        opt_params = [r_1, r_1, c1_1, c2_1, r_2, r_2, c1_2, c2_2]
        opt_iterations = 0
        opt_message = "Analytical closed-form Butterworth cascaded pole-placement sizing succeeded."
        opt_cost = 0.0
    else:
        optimization_method = "nelder_mead"

        def optimizer_objective(log_params):
            iteration_count[0] += 1
            if any(not np.isfinite(p) for p in log_params):
                return SENTINEL_FAILURE_OBJ
            params = [10.0 ** p for p in log_params]
            if any(not np.isfinite(p) or p <= 0 for p in params):
                return SENTINEL_FAILURE_OBJ
            fc, q, err = loss_function(
                params, order=order, filter_type=filter_type,
                ngspice_bin=ngspice_bin, fallback=use_fallback, target_fc=target_fc, target_q=target_q
            )
            if not np.isfinite(err):
                err = SENTINEL_FAILURE_OBJ
            if progress_callback:
                progress_callback(iteration_count[0], fc, q, err)
            return err

        res = minimize(
            optimizer_objective, x0, method="Nelder-Mead",
            options={"maxiter": 300, "xatol": 1e-4, "fatol": 1e-4}
        )

        # 1. Validate optimizer convergence
        if not getattr(res, "success", False):
            err_msg = f"Nelder-Mead continuous optimization failed to converge: {getattr(res, 'message', 'Optimization unsuccessful')}."
            if raise_on_error:
                raise RuntimeError(err_msg)
            return {
                "success": False,
                "error": err_msg,
                "failure_stage": "continuous_optimization",
                "optimizer_message": getattr(res, "message", ""),
                "filter_type": filter_type,
                "order": order,
                "target_fc": float(target_fc),
                "target_q": float(target_q),
                "optimization_method": optimization_method,
            }

        # 2. Reject non-finite objective
        if not np.isfinite(res.fun):
            err_msg = f"Nelder-Mead optimizer produced a non-finite objective value: {res.fun}."
            if raise_on_error:
                raise RuntimeError(err_msg)
            return {
                "success": False,
                "error": err_msg,
                "failure_stage": "continuous_optimization",
                "optimizer_message": getattr(res, "message", ""),
                "filter_type": filter_type,
                "order": order,
                "target_fc": float(target_fc),
                "target_q": float(target_q),
                "optimization_method": optimization_method,
            }

        # 3. Reject failure sentinel objective (>= 1e11)
        if res.fun >= 1e11:
            err_msg = (f"Nelder-Mead optimizer failed to find a feasible solution: "
                       f"objective reached failure sentinel ({res.fun:.2e}). "
                       f"Please verify circuit specifications and simulator configuration.")
            if raise_on_error:
                raise RuntimeError(err_msg)
            return {
                "success": False,
                "error": err_msg,
                "failure_stage": "continuous_optimization",
                "optimizer_message": getattr(res, "message", ""),
                "filter_type": filter_type,
                "order": order,
                "target_fc": float(target_fc),
                "target_q": float(target_q),
                "optimization_method": optimization_method,
            }

        # 4. Validate component values are finite and strictly positive
        opt_params = [float(10.0 ** p) for p in res.x]
        if any(not np.isfinite(p) or p <= 0.0 for p in opt_params):
            err_msg = "Nelder-Mead optimizer produced non-physical, non-finite, or non-positive component values."
            if raise_on_error:
                raise RuntimeError(err_msg)
            return {
                "success": False,
                "error": err_msg,
                "failure_stage": "continuous_optimization",
                "optimizer_message": getattr(res, "message", ""),
                "filter_type": filter_type,
                "order": order,
                "target_fc": float(target_fc),
                "target_q": float(target_q),
                "optimization_method": optimization_method,
            }

        opt_iterations = res.nit
        opt_message = res.message
        opt_cost = float(res.fun)

    # Stage 1 Verification: Simulate continuous optimal parameters
    final_fc_opt, final_q_opt, err_opt = loss_function(
        opt_params, order=order, filter_type=filter_type,
        ngspice_bin=ngspice_bin, fallback=use_fallback, target_fc=target_fc, target_q=target_q,
        output_data_file=SIM_DATA_PATH
    )
    freqs_opt, mags_opt = parse_simulation_data(SIM_DATA_PATH)

    if len(freqs_opt) < 2 or len(mags_opt) < 2 or any(not np.isfinite(f) for f in freqs_opt) or any(not np.isfinite(m) for m in mags_opt):
        err_msg = "Continuous optimal simulation verification generated insufficient, non-finite, or empty frequency response data."
        if raise_on_error:
            raise RuntimeError(err_msg)
        return {
            "success": False,
            "error": err_msg,
            "failure_stage": "continuous_verification",
            "filter_type": filter_type,
            "order": order,
            "target_fc": float(target_fc),
            "target_q": float(target_q),
            "optimization_method": optimization_method,
        }

    if not np.isfinite(final_fc_opt) or final_fc_opt <= 0.0 or err_opt >= 1e11:
        err_msg = f"Continuous optimal simulation verification produced invalid cutoff frequency: {final_fc_opt} Hz."
        if raise_on_error:
            raise RuntimeError(err_msg)
        return {
            "success": False,
            "error": err_msg,
            "failure_stage": "continuous_verification",
            "filter_type": filter_type,
            "order": order,
            "target_fc": float(target_fc),
            "target_q": float(target_q),
            "optimization_method": optimization_method,
        }

    # Stage 2: Hardware E-Series Snapping
    if filter_type == "lpf":
        if order == 1:
            comm_r, comm_c, _, _ = find_commercial_pair_1st_order(target_fc, r_series=r_series, c_series=c_series)
            comm_params = [comm_r, comm_c]
        elif order == 2:
            comm_r1, comm_r2, comm_c1, comm_c2, _, _ = find_commercial_components_2nd_order(target_fc, r_series=r_series, c_series=c_series)
            comm_params = [comm_r1, comm_r2, comm_c1, comm_c2]
        elif order == 4:
            comm_params = list(find_commercial_cascade4(target_fc, r_series=r_series, c_series=c_series))
    elif filter_type == "hpf":
        comm_r1, comm_r2, comm_c1, comm_c2, _, _ = find_commercial_hpf(target_fc, r_series=r_series, c_series=c_series)
        comm_params = [comm_r1, comm_r2, comm_c1, comm_c2]
    elif filter_type == "bpf":
        comm_r1, comm_r2, comm_r3, comm_c1, comm_c2, _, _ = find_commercial_bpf(target_fc, target_q=target_q, r_series=r_series, c_series=c_series)
        comm_params = [comm_r1, comm_r2, comm_r3, comm_c1, comm_c2]

    # Stage 2 Verification: Simulate snapped commercial parameters
    final_fc_comm, final_q_comm, err_comm = loss_function(
        comm_params, order=order, filter_type=filter_type,
        ngspice_bin=ngspice_bin, fallback=use_fallback, target_fc=target_fc, target_q=target_q,
        output_data_file=COMMERCIAL_SIM_DATA_PATH
    )
    freqs_comm, mags_comm = parse_simulation_data(COMMERCIAL_SIM_DATA_PATH)

    if len(freqs_comm) < 2 or len(mags_comm) < 2 or any(not np.isfinite(f) for f in freqs_comm) or any(not np.isfinite(m) for m in mags_comm):
        err_msg = "Commercial snapped simulation verification generated insufficient, non-finite, or empty frequency response data."
        if raise_on_error:
            raise RuntimeError(err_msg)
        return {
            "success": False,
            "error": err_msg,
            "failure_stage": "commercial_verification",
            "filter_type": filter_type,
            "order": order,
            "target_fc": float(target_fc),
            "target_q": float(target_q),
            "optimization_method": optimization_method,
        }

    if not np.isfinite(final_fc_comm) or final_fc_comm <= 0.0 or err_comm >= 1e11:
        err_msg = f"Commercial snapped simulation verification produced invalid cutoff frequency: {final_fc_comm} Hz."
        if raise_on_error:
            raise RuntimeError(err_msg)
        return {
            "success": False,
            "error": err_msg,
            "failure_stage": "commercial_verification",
            "filter_type": filter_type,
            "order": order,
            "target_fc": float(target_fc),
            "target_q": float(target_q),
            "optimization_method": optimization_method,
        }

    if filter_type == "bpf":
        _, _, bandwidth_comm = extract_cutoff_frequency(freqs_comm, mags_comm, filter_type="bpf")
    else:
        bandwidth_comm = 0.0

    pct_err_opt = abs(final_fc_opt - target_fc) / target_fc * 100.0
    pct_err_comm = abs(final_fc_comm - target_fc) / target_fc * 100.0

    # Stage 3: Export BOM & KiCad Netlist
    comp_dict = {name: val for name, val in zip(comp_names, comm_params)}
    bom_rows = generate_bom_data(top_key, comp_dict, r_tol=r_tol, c_tol=c_tol)
    bom_csv_path = OUTPUT_DIR / f"BOM_{top_key}.csv"
    export_bom_csv(bom_rows, bom_csv_path)

    kicad_net_path = OUTPUT_DIR / f"{top_key}_kicad.net"
    kicad_text = export_kicad_netlist(top_key, comp_dict, kicad_net_path)

    current_spice_text = CURRENT_SIM_PATH.read_text(encoding="utf-8") if CURRENT_SIM_PATH.exists() else ""

    return {
        "success": True,
        "optimization_method": optimization_method,
        "filter_type": filter_type,
        "order": order,
        "top_key": top_key,
        "target_fc": float(target_fc),
        "target_q": float(target_q),
        "r_series": r_series,
        "c_series": c_series,
        "r_tol": float(r_tol),
        "c_tol": float(c_tol),
        "comp_names": comp_names,
        "initial_params": initial_params,
        "init_fc": float(init_fc),
        "init_q": float(init_q),
        "opt_iterations": opt_iterations,
        "opt_message": opt_message,
        "opt_params": [float(p) for p in opt_params],
        "final_fc_opt": float(final_fc_opt),
        "final_q_opt": float(final_q_opt),
        "pct_err_opt": float(pct_err_opt),
        "freqs_opt": freqs_opt,
        "mags_opt": mags_opt,
        "comm_params": [float(p) for p in comm_params],
        "final_fc_comm": float(final_fc_comm),
        "final_q_comm": float(final_q_comm),
        "bandwidth_comm": float(bandwidth_comm),
        "pct_err_comm": float(pct_err_comm),
        "freqs_comm": freqs_comm,
        "mags_comm": mags_comm,
        "bom_rows": bom_rows,
        "bom_csv_path": bom_csv_path,
        "kicad_net_path": kicad_net_path,
        "kicad_text": kicad_text,
        "spice_text": current_spice_text,
        "sim_engine": "ngspice" if not use_fallback else "analytical",
    }


def generate_bode_plot(freqs_opt, mags_opt, target_fc, achieved_fc_opt,
                       freqs_comm=None, mags_comm=None, achieved_fc_comm=None,
                       order=1, filter_type="lpf", output_path=PLOT_PATH):
    """Generates comparative Bode magnitude plot."""
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=300)

    if filter_type == "lpf":
        if order == 1:
            slope_label = "-20 dB/dec"
            title_name = "1st-Order Passive RC Low-Pass"
        elif order == 2:
            slope_label = "-40 dB/dec"
            title_name = "2nd-Order Sallen-Key Low-Pass"
        else:
            slope_label = "-80 dB/dec"
            title_name = "4th-Order Cascaded Sallen-Key Low-Pass"
    elif filter_type == "hpf":
        slope_label = "+40 dB/dec"
        title_name = "2nd-Order Sallen-Key High-Pass"
    elif filter_type == "bpf":
        slope_label = "+/-20 dB/dec"
        title_name = "2nd-Order MFB Band-Pass"

    ax.semilogx(freqs_opt, mags_opt, color="#1f77b4", linewidth=2.5,
                label=f"Continuous Optimal: {achieved_fc_opt:.1f} Hz ({slope_label})")

    if freqs_comm is not None and mags_comm is not None:
        ax.semilogx(freqs_comm, mags_comm, color="#2ca02c", linestyle="--", linewidth=2.0,
                    label=f"Commercial Standard: {achieved_fc_comm:.1f} Hz")

    if filter_type in ["lpf", "hpf", "cascade4"]:
        cutoff_db = -3.0103
        ax.axhline(cutoff_db, color="#d62728", linestyle=":", alpha=0.8, label=f"-3 dB Cutoff ({cutoff_db:.2f} dB)")
        ax.axvline(target_fc, color="#7f7f7f", linestyle="-.", alpha=0.7, label=f"Target ({target_fc:.0f} Hz)")
        ax.scatter([achieved_fc_opt], [cutoff_db], color="#1f77b4", s=90, zorder=5)
    else:
        ax.axvline(target_fc, color="#7f7f7f", linestyle="-.", alpha=0.7, label=f"Target Center ({target_fc:.0f} Hz)")

    ax.set_title(
        f"Bode Magnitude Plot - {title_name}\n"
        f"Target = {target_fc:.0f} Hz | Stopband Roll-Off: {slope_label}",
        fontsize=12, pad=15
    )
    ax.set_xlabel("Frequency (Hz)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Magnitude (dB)", fontsize=11, fontweight="bold")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_xlim([min(freqs_opt), max(freqs_opt)])
    ax.set_ylim([max(-95.0, min(mags_opt) - 5), max(mags_opt) + 5])
    ax.legend(loc="lower left" if filter_type != "hpf" else "lower right", frameon=True, fontsize=9.5)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300)
    plt.close()


def run_monte_carlo_analysis(comm_params, order=1, filter_type="lpf", target_fc=TARGET_CUTOFF_HZ,
                             r_tol=1.0, c_tol=5.0, trials=100, target_q=BUTTERWORTH_Q,
                             ngspice_bin=None, fallback=False, output_plot=MC_PLOT_PATH):
    """
    Executes N statistical Monte Carlo SPICE simulations with Gaussian component variations.
    Accurately computes cutoff-frequency compliance yield and statistical coverage intervals.
    """
    print(f"\nRunning {trials} Monte Carlo statistical SPICE simulations...", flush=True)
    print(f"Assumed Component Tolerances: Resistors = +/-{r_tol}%, Capacitors = +/-{c_tol}%", flush=True)

    mc_temp_file = OUTPUT_DIR / "mc_temp_sim.txt"
    fcs = []
    qs = []

    r_sigma = (r_tol / 100.0) / 3.0
    c_sigma = (c_tol / 100.0) / 3.0
    np.random.seed(42)

    for i in range(trials):
        samp_params = []
        for p_idx, val in enumerate(comm_params):
            if filter_type == "lpf" and order == 1:
                sig = r_sigma if p_idx == 0 else c_sigma
            elif filter_type in ["lpf", "hpf"] and order == 2:
                sig = r_sigma if p_idx < 2 else c_sigma
            elif filter_type == "bpf":
                sig = r_sigma if p_idx < 3 else c_sigma
            elif filter_type == "lpf" and order == 4:
                sig = r_sigma if p_idx in [0, 1, 4, 5] else c_sigma
            else:
                sig = r_sigma
            samp_params.append(val * (1.0 + np.random.normal(0, sig)))

        fc, q, _ = loss_function(samp_params, order=order, filter_type=filter_type, ngspice_bin=ngspice_bin,
                                 fallback=fallback, target_fc=target_fc, target_q=target_q, output_data_file=mc_temp_file)
        fcs.append(fc)
        if order == 2 or filter_type == "bpf":
            qs.append(q)

        if (i + 1) % 25 == 0 or (i + 1) == trials:
            print(f"  Completed {i + 1:3d}/{trials} trials...", flush=True)

    if mc_temp_file.exists():
        mc_temp_file.unlink()

    fcs = np.array(fcs)
    qs = np.array(qs) if (order == 2 or filter_type == "bpf") else None

    # Cutoff Frequency Compliance Yield
    yield_2pct = float(np.sum(np.abs(fcs - target_fc) <= 0.02 * target_fc) / trials * 100.0)
    yield_5pct = float(np.sum(np.abs(fcs - target_fc) <= 0.05 * target_fc) / trials * 100.0)

    # Statistical intervals
    mu_fc = float(np.mean(fcs))
    std_fc = float(np.std(fcs, ddof=1)) if len(fcs) > 1 else float(np.std(fcs))
    se_fc = std_fc / math.sqrt(trials)
    ci_mean_low = mu_fc - 1.96 * se_fc
    ci_mean_high = mu_fc + 1.96 * se_fc
    dist_band_low = mu_fc - 1.96 * std_fc
    dist_band_high = mu_fc + 1.96 * std_fc
    p2_5 = float(np.percentile(fcs, 2.5))
    p97_5 = float(np.percentile(fcs, 97.5))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)

    # Histogram 1: Cutoff / Center Frequency
    ax1.hist(fcs, bins=22, color="#1f77b4", edgecolor="black", alpha=0.7, density=True)
    std_safe = max(std_fc, 1e-6)
    x_grid = np.linspace(min(fcs) - 20, max(fcs) + 20, 200)
    pdf = (1.0 / (std_safe * np.sqrt(2.0 * np.pi))) * np.exp(-0.5 * ((x_grid - mu_fc) / std_safe) ** 2)
    ax1.plot(x_grid, pdf, color="#0b407a", linewidth=2.0, label=f"Gaussian Fit ($\\mu$={mu_fc:.1f}Hz, s={std_fc:.1f}Hz)")

    ax1.axvline(target_fc, color="#d62728", linestyle="--", linewidth=2.0, label=f"Target ({target_fc:.0f} Hz)")
    ax1.axvspan(target_fc * 0.98, target_fc * 1.02, color="#2ca02c", alpha=0.25, label=f"±2% Spec Band (Compliance: {yield_2pct:.1f}%)")
    ax1.axvspan(target_fc * 0.95, target_fc * 1.05, color="#2ca02c", alpha=0.10, label=f"±5% Spec Band (Compliance: {yield_5pct:.1f}%)")

    ax1.set_title(f"Monte Carlo Frequency Distribution ({trials} Runs)\nAssumed Tolerances: Resistors ±{r_tol}%, Capacitors ±{c_tol}%", fontsize=11, pad=12)
    ax1.set_xlabel("Frequency (Hz)", fontsize=10, fontweight="bold")
    ax1.set_ylabel("Probability Density", fontsize=10, fontweight="bold")
    ax1.legend(loc="upper right", frameon=True, fontsize=8.5)
    ax1.grid(True, linestyle="--", alpha=0.6)

    # Subplot 2: Q factor or CDF
    if qs is not None:
        ax2.hist(qs, bins=22, color="#ff7f0e", edgecolor="black", alpha=0.7, density=True)
        mu_q = float(np.mean(qs))
        std_q = float(np.std(qs, ddof=1)) if len(qs) > 1 else float(np.std(qs))
        std_q_safe = max(std_q, 1e-6)
        xq_grid = np.linspace(min(qs) - 0.05, max(qs) + 0.05, 200)
        pdf_q = (1.0 / (std_q_safe * np.sqrt(2.0 * np.pi))) * np.exp(-0.5 * ((xq_grid - mu_q) / std_q_safe) ** 2)
        ax2.plot(xq_grid, pdf_q, color="#b35400", linewidth=2.0, label=f"Gaussian Fit ($\\mu_Q$={mu_q:.4f}, $s_Q$={std_q:.4f})")
        ax2.axvline(target_q, color="#d62728", linestyle="--", linewidth=2.0, label=f"Target Q ({target_q:.4f})")
        ax2.set_title(f"Monte Carlo Quality Factor (Q) Distribution\n$\\mu_Q$ = {mu_q:.4f}, $s_Q$ = {std_q:.4f}", fontsize=11, pad=12)
        ax2.set_xlabel("Quality Factor (Q)", fontsize=10, fontweight="bold")
        ax2.set_ylabel("Probability Density", fontsize=10, fontweight="bold")
        ax2.legend(loc="upper right", frameon=True, fontsize=8.5)
        ax2.grid(True, linestyle="--", alpha=0.6)
    else:
        sorted_fcs = np.sort(fcs)
        cdf = np.arange(1, len(sorted_fcs) + 1) / len(sorted_fcs) * 100.0
        ax2.plot(sorted_fcs, cdf, color="#2ca02c", linewidth=2.5, label="Empirical CDF")
        ax2.axvline(target_fc, color="#d62728", linestyle="--", label=f"Target ({target_fc:.0f} Hz)")
        ax2.axhline(50.0, color="#7f7f7f", linestyle=":", alpha=0.7)
        ax2.set_title("Cumulative Frequency Distribution Curve", fontsize=11, pad=12)
        ax2.set_xlabel("Frequency (Hz)", fontsize=10, fontweight="bold")
        ax2.set_ylabel("Cumulative Probability (%)", fontsize=10, fontweight="bold")
        ax2.legend(loc="lower right", frameon=True, fontsize=9.0)
        ax2.grid(True, linestyle="--", alpha=0.6)

    plt.tight_layout()
    output_plot.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_plot, dpi=300)
    plt.close()

    print("\n" + "=" * 76, flush=True)
    print("       MONTE CARLO COMPONENT TOLERANCE & FREQUENCY YIELD REPORT            ", flush=True)
    print("=" * 76, flush=True)
    print(f"Number of Statistical Trials:   {trials} SPICE simulations", flush=True)
    print(f"Assumed Component Tolerances:   Resistors: +/-{r_tol:.1f}% | Capacitors: +/-{c_tol:.1f}%", flush=True)
    print(f"Cutoff Frequency Mean (mu):     {mu_fc:.2f} Hz", flush=True)
    print(f"Cutoff Sample Std Dev (s):      {std_fc:.2f} Hz", flush=True)
    print(f"Mean 95% Confidence Interval:   [{ci_mean_low:.2f} Hz, {ci_mean_high:.2f} Hz] (mu +/- 1.96*s/sqrt(N))", flush=True)
    print(f"Approx. 95% Distribution Band:  [{dist_band_low:.2f} Hz, {dist_band_high:.2f} Hz] (mu +/- 1.96*s)", flush=True)
    print(f"Empirical 95% Interval:         [{p2_5:.2f} Hz, {p97_5:.2f} Hz] (2.5th to 97.5th percentile)", flush=True)
    print(f"Extreme Frequency Range:        [{np.min(fcs):.2f} Hz, {np.max(fcs):.2f} Hz]", flush=True)
    if qs is not None:
        print(f"Quality Factor Q Mean (mu):     {np.mean(qs):.4f} (Target: {target_q:.4f})", flush=True)
        print(f"Quality Factor Q Sample Std Dev:{np.std(qs, ddof=1):.4f}", flush=True)
    print("-" * 76, flush=True)
    print(f"Cutoff Compliance Yield (+/-2% Spec Band): {yield_2pct:6.2f} %", flush=True)
    print(f"Cutoff Compliance Yield (+/-5% Spec Band): {yield_5pct:6.2f} %", flush=True)
    print("(Note: Yield evaluates cutoff-frequency tolerance compliance only;", flush=True)
    print(" does not model PCB parasitics, component derating, or assembly defects.)", flush=True)
    print(f"Monte Carlo Yield Plot Saved:   {output_plot}", flush=True)
    print("=" * 76 + "\n", flush=True)

    return fcs, qs, yield_2pct, yield_5pct


def main():
    parser = argparse.ArgumentParser(description="Analog Filter Synthesizer via SPICE and SciPy Numerical Optimization")
    parser.add_argument("--type", type=str, default="lpf", choices=["lpf", "hpf", "bpf"], help="Filter type: lpf, hpf, bpf (default: lpf)")
    parser.add_argument("--order", type=int, default=1, choices=[1, 2, 4], help="Filter order (1, 2, or 4 for LPF; 2 for HPF/BPF)")
    parser.add_argument("--target-fc", type=float, default=TARGET_CUTOFF_HZ, help="Target cutoff / center frequency in Hz")
    parser.add_argument("--q", type=float, default=None, help="Target Quality Factor Q (default: 0.7071 for Butterworth, 2.0 for BPF)")
    parser.add_argument("--series", type=str, default="E24", choices=["E12", "E24", "E96"],
                        help="Resistor EIA standard series for commercial snapping (default: E24)")
    parser.add_argument("--ngspice", help="Path to ngspice binary", default=None)
    parser.add_argument("--fallback", action="store_true", help="Use analytical SPICE fallback simulator")
    parser.add_argument("--monte-carlo", action="store_true", help="Run statistical Monte Carlo tolerance analysis")
    parser.add_argument("--mc-trials", type=int, default=100, help="Number of Monte Carlo statistical trials (default: 100)")
    parser.add_argument("--r-tol", type=float, default=None, help="Resistor tolerance in percent (e.g. 1.0 or 5.0)")
    parser.add_argument("--c-tol", type=float, default=5.0, help="Capacitor tolerance in percent (default: 5.0)")
    args = parser.parse_args()

    filter_type = args.type.lower()
    order = args.order
    target_fc = args.target_fc
    r_series = args.series.upper()
    c_series = "E12"
    target_q = args.q if args.q is not None else (2.0 if filter_type == "bpf" else BUTTERWORTH_Q)

    if args.r_tol is not None:
        r_tol = args.r_tol
    else:
        r_tol = 1.0 if r_series == "E96" else 5.0
    c_tol = args.c_tol

    ngspice_bin = find_ngspice(args.ngspice)
    use_fallback = args.fallback or not ngspice_bin

    if ngspice_bin and not use_fallback:
        print(f"[INFO] Using SPICE simulator: {ngspice_bin}", flush=True)
    else:
        print("[INFO] Running in analytical SPICE mode.", flush=True)

    print("\n" + "=" * 76, flush=True)
    if filter_type == "lpf":
        type_title = f"{order}TH-ORDER PASSIVE RC" if order == 1 else f"{order}ND-ORDER ACTIVE SALLEN-KEY (BUTTERWORTH)" if order == 2 else "4TH-ORDER CASCADED SALLEN-KEY (BUTTERWORTH)"
    elif filter_type == "hpf":
        type_title = "2ND-ORDER ACTIVE SALLEN-KEY HIGH-PASS (BUTTERWORTH)"
    elif filter_type == "bpf":
        type_title = f"2ND-ORDER ACTIVE MULTIPLE-FEEDBACK BAND-PASS (Q={target_q:.2f})"
    print(f"      NUMERICAL OPTIMIZATION-BASED {type_title} FILTER SYNTHESIZER      ", flush=True)
    print("=" * 76, flush=True)
    print(f"Target Frequency (-3dB or Center): {target_fc:.2f} Hz", flush=True)
    print(f"Commercial Series Selection:       Resistors: {r_series} | Capacitors: {c_series}", flush=True)

    def print_progress(step, fc, q, err):
        if step % 10 == 0 or step == 1:
            print(f"  Step {step:3d} | fc = {fc:8.2f} Hz | Q = {q:.3f} | Error = {err:10.2e}", flush=True)

    print("-" * 76, flush=True)
    if filter_type == "lpf" and order == 4:
        print("Stage 1: Running exact analytical closed-form Butterworth pole-placement sizing...", flush=True)
    else:
        print("Stage 1: Running continuous numerical optimization (Nelder-Mead simplex)...", flush=True)

    result = synthesize_filter(
        filter_type=filter_type, order=order, target_fc=target_fc, target_q=target_q,
        r_series=r_series, c_series=c_series, ngspice_bin=ngspice_bin, fallback=use_fallback,
        r_tol=r_tol, c_tol=c_tol, progress_callback=print_progress
    )

    if not result.get("success", False):
        print(f"\n[ERROR] Filter synthesis failed at stage '{result.get('failure_stage', 'optimization')}':", file=sys.stderr)
        print(f"        {result.get('error')}", file=sys.stderr)
        sys.exit(1)

    print("-" * 76, flush=True)
    if result["optimization_method"] == "analytical_closed_form":
        print(f"Analytical closed-form sizing completed successfully!", flush=True)
    else:
        print(f"Continuous optimization completed (Iterations: {result['opt_iterations']})!", flush=True)
    print(f"Stage 2: Snapped to standard commercial components ({r_series} / {c_series}).", flush=True)

    generate_bode_plot(
        result["freqs_opt"], result["mags_opt"], target_fc, result["final_fc_opt"],
        freqs_comm=result["freqs_comm"], mags_comm=result["mags_comm"],
        achieved_fc_comm=result["final_fc_comm"],
        order=order, filter_type=filter_type, output_path=PLOT_PATH
    )

    print("\n" + "=" * 76, flush=True)
    print(f"          FINAL SYNTHESIS & HARDWARE SNAPPING REPORT ({type_title})          ", flush=True)
    print("=" * 76, flush=True)
    print(f"{'Specification':<26} | {'Initial Guess':<15} | {'Continuous Optimal':<18} | {'Commercial (' + r_series + ')':<15}", flush=True)
    print("-" * 76, flush=True)
    for name, init_v, opt_v, comm_v in zip(result["comp_names"], result["initial_params"], result["opt_params"], result["comm_params"]):
        unit = "Ohm" if name.startswith("R") else "F"
        print(f"{name:<26} | {format_eng(init_v, unit):>15} | {format_eng(opt_v, unit):>18} | {format_eng(comm_v, unit):>15}", flush=True)
    print("-" * 76, flush=True)
    print(f"{'Frequency':<26} | {result['init_fc']:>12.2f} Hz | {result['final_fc_opt']:>15.2f} Hz | {result['final_fc_comm']:>12.2f} Hz", flush=True)
    print(f"{'Target Frequency':<26} | {target_fc:>12.2f} Hz | {target_fc:>15.2f} Hz | {target_fc:>12.2f} Hz", flush=True)
    print(f"{'Percentage Error':<26} | {abs(result['init_fc']-target_fc)/target_fc*100:>11.2f} %  | {result['pct_err_opt']:>14.4f} %  | {result['pct_err_comm']:>11.2f} %", flush=True)
    if order == 2 or filter_type == "bpf":
        print(f"{'Quality Factor (Q)':<26} | {result['init_q']:>15.4f} | {result['final_q_opt']:>18.4f} | {result['final_q_comm']:>15.4f}", flush=True)
        print(f"{'Target Q':<26} | {target_q:>15.4f} | {target_q:>18.4f} | {target_q:>15.4f}", flush=True)
    print("=" * 76, flush=True)
    print(f"Bill of Materials (BOM):       {result['bom_csv_path']}", flush=True)
    print(f"KiCad Schematic Netlist:       {result['kicad_net_path']}", flush=True)
    print(f"SPICE Netlist (Final):         {CURRENT_SIM_PATH}", flush=True)
    print(f"Comparative Bode Plot:         {PLOT_PATH}", flush=True)
    print("=" * 76 + "\n", flush=True)

    if args.monte_carlo:
        run_monte_carlo_analysis(
            result["comm_params"],
            order=order,
            filter_type=filter_type,
            target_fc=target_fc,
            target_q=target_q,
            r_tol=r_tol,
            c_tol=c_tol,
            trials=args.mc_trials,
            ngspice_bin=ngspice_bin,
            fallback=use_fallback,
            output_plot=MC_PLOT_PATH
        )


if __name__ == "__main__":
    main()
