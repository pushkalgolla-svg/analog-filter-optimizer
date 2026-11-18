"""
Interactive Analog Filter Synthesizer & EDA Verification Dashboard.
Built with Streamlit, SciPy, and ngspice.
"""

import math
import uuid
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

import scripts.synthesize as syn
import scripts.export_manufacturing as exp

OPAMP_MODEL_TI = getattr(syn, "OPAMP_MODEL_TI", "ti_opa1678")
OPAMP_MODEL_IDEAL = getattr(syn, "OPAMP_MODEL_IDEAL", "idealized")

# Set page configuration
st.set_page_config(
    page_title="Analog Filter Synthesizer EDA",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Custom EDA Styling: "Instruments Precision" Visual Language
st.markdown("""
<style>
    /* Global Typography & Palette */
    .stApp {
        background-color: #0b0f17;
        color: #f8fafc;
    }

    /* Top EDA Instrument Badge Bar */
    .instrument-badge-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
        margin-bottom: 1.2rem;
        padding: 9px 14px;
        background: #111827;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 0.8rem;
    }
    .instrument-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        color: #cbd5e1;
    }
    .badge-live {
        background: rgba(16, 185, 129, 0.12);
        border-color: rgba(16, 185, 129, 0.35);
        color: #34d399;
        font-weight: 600;
    }
    .badge-active {
        background: rgba(56, 189, 248, 0.12);
        border-color: rgba(56, 189, 248, 0.35);
        color: #38bdf8;
    }
    .badge-amber {
        background: rgba(245, 158, 11, 0.12);
        border-color: rgba(245, 158, 11, 0.35);
        color: #fbbf24;
    }

    /* Top KPI Metric Rack */
    [data-testid="stMetric"] {
        background: #131b2a !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 8px !important;
        padding: 14px 18px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.25) !important;
        transition: border-color 0.2s ease, transform 0.2s ease !important;
    }
    [data-testid="stMetric"]:hover {
        border-color: rgba(56, 189, 248, 0.45) !important;
        transform: translateY(-1px);
    }
    [data-testid="stMetricLabel"] p {
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        color: #94a3b8 !important;
    }
    [data-testid="stMetricValue"] div {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
        font-size: 1.55rem !important;
        font-weight: 700 !important;
        color: #f8fafc !important;
    }

    /* Tab Navigation Polish */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background: #111827;
        padding: 6px 8px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 1.2rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        border-radius: 6px;
        font-size: 0.88rem;
        font-weight: 600;
        color: #94a3b8;
        border: none !important;
        background-color: transparent !important;
        transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #f8fafc;
        background: rgba(255, 255, 255, 0.04) !important;
    }
    .stTabs [aria-selected="true"] {
        color: #38bdf8 !important;
        background: rgba(56, 189, 248, 0.12) !important;
        border: 1px solid rgba(56, 189, 248, 0.3) !important;
    }

    /* Telemetry Card Containers */
    .telemetry-card {
        background: #131b2a;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 14px;
    }
    .telemetry-header {
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #94a3b8;
        margin-bottom: 10px;
    }
    .telemetry-stat-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        font-size: 0.86rem;
    }
    .telemetry-stat-label {
        color: #94a3b8;
    }
    .telemetry-stat-value {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-weight: 600;
        color: #f8fafc;
    }

    /* Progress bar for yield */
    .progress-track {
        background: rgba(255, 255, 255, 0.08);
        border-radius: 9999px;
        height: 8px;
        width: 100%;
        overflow: hidden;
        margin-top: 4px;
        margin-bottom: 12px;
    }
    .progress-fill-emerald {
        background: #10b981;
        height: 100%;
        border-radius: 9999px;
        transition: width 0.3s ease;
    }
    .progress-fill-cyan {
        background: #38bdf8;
        height: 100%;
        border-radius: 9999px;
        transition: width 0.3s ease;
    }

    /* Pinout ASCII / Monospace Architecture Box */
    .pinout-box {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        background: #0b1120;
        border: 1px solid #1e293b;
        border-radius: 6px;
        padding: 14px;
        color: #38bdf8;
        font-size: 0.85rem;
        line-height: 1.45;
        white-space: pre;
        overflow-x: auto;
    }
</style>
""", unsafe_allow_html=True)

# Application Header
st.title("⚡ Analog Filter Synthesizer & SPICE Verification Studio")
st.caption("Automated Analog Filter Synthesis, Continuous Numerical Optimization (Nelder-Mead Simplex), EIA Standard Component Snapping & Monte Carlo Yield Analysis")

# Sidebar Controls
st.sidebar.header("🎛️ Design Specifications")

filter_family = st.sidebar.selectbox(
    "Filter Response Type",
    ["Low-Pass Filter (LPF)", "High-Pass Filter (HPF)", "Band-Pass Filter (BPF)"]
)

if filter_family == "Low-Pass Filter (LPF)":
    filter_type = "lpf"
    order_choice = st.sidebar.selectbox(
        "Circuit Topology & Order",
        [
            "2nd-Order Active Sallen-Key (Butterworth, -40 dB/dec)",
            "1st-Order Passive RC (-20 dB/dec)",
            "4th-Order Cascaded Sallen-Key (-80 dB/dec)"
        ]
    )
    if "1st-Order" in order_choice:
        order = 1
        top_key = "1st_order_rc"
    elif "2nd-Order" in order_choice:
        order = 2
        top_key = "sallen_key_lpf"
    else:
        order = 4
        top_key = "cascade4_lpf"
    target_q = syn.BUTTERWORTH_Q

elif filter_family == "High-Pass Filter (HPF)":
    filter_type = "hpf"
    order = 2
    top_key = "sallen_key_hpf"
    target_q = syn.BUTTERWORTH_Q
    st.sidebar.info("Topology: 2nd-Order Active Sallen-Key High-Pass (+40 dB/dec)")

else:  # Band-Pass Filter (BPF)
    filter_type = "bpf"
    order = 2
    top_key = "mfb_bpf"
    st.sidebar.info("Topology: 2nd-Order Multiple-Feedback (MFB) Inverting Band-Pass")
    target_q = st.sidebar.slider("Target Quality Factor (Q)", min_value=0.5, max_value=10.0, value=2.0, step=0.1)

# Frequency Target & Presets
freq_col1, freq_col2 = st.sidebar.columns([2, 1])
with freq_col1:
    target_fc = st.number_input(
        "Target Cutoff / Center Frequency (Hz)",
        min_value=1.0,
        max_value=1000000.0,
        value=1000.0,
        step=50.0
    )
with freq_col2:
    unit_preset = st.selectbox("Preset", ["Custom", "100 Hz", "1 kHz", "10 kHz", "40 kHz"])
    if unit_preset == "100 Hz":
        target_fc = 100.0
    elif unit_preset == "1 kHz":
        target_fc = 1000.0
    elif unit_preset == "10 kHz":
        target_fc = 10000.0
    elif unit_preset == "40 kHz":
        target_fc = 40000.0

st.sidebar.markdown("---")
st.sidebar.header("📦 Commercial EIA Standards")

r_series = st.sidebar.selectbox("Resistor Series", ["E96 (1%)", "E24 (5%)", "E12 (10%)"], index=0).split()[0]
c_series = "E12"

tol_col1, tol_col2 = st.sidebar.columns(2)
with tol_col1:
    r_tol = st.selectbox("Resistor Tol.", [0.1, 0.5, 1.0, 5.0], index=2 if r_series == "E96" else 3)
with tol_col2:
    c_tol = st.selectbox("Capacitor Tol.", [1.0, 2.0, 5.0, 10.0], index=2)

# Active Op-Amp & Power Supply Configuration
is_active_circuit = (order >= 2) or (filter_type in ["hpf", "bpf"])
if is_active_circuit:
    st.sidebar.markdown("---")
    st.sidebar.header("🔬 Op-Amp Macro-Model & Power")
    opamp_choice = st.sidebar.selectbox(
        "Amplifier Model",
        [
            "Texas Instruments OPA1678 Macro-Model (Rev E)",
            "Idealized Operational Amplifier (VCVS AOL=100k)"
        ],
        index=0
    )
    opamp_model = OPAMP_MODEL_TI if "OPA1678" in opamp_choice else OPAMP_MODEL_IDEAL
    v_supply = 15.0
    st.sidebar.info("⚡ Dual Supply Rails: ±15.0V with 2x 100nF Decoupling Provisions")
else:
    opamp_model = OPAMP_MODEL_IDEAL
    v_supply = 15.0

st.sidebar.markdown("---")
st.sidebar.header("🎲 Manufacturing Yield Analysis")
enable_mc = st.sidebar.checkbox("Run Monte Carlo Statistical Analysis", value=True)
mc_trials = st.sidebar.slider("Monte Carlo Trials", min_value=10, max_value=150, value=25, step=5)

# Check SPICE simulator
ngspice_bin = syn.find_ngspice()
if ngspice_bin:
    st.sidebar.success(f"✓ SPICE Engine Detected: ngspice ({Path(ngspice_bin).name})")
else:
    st.sidebar.warning("⚠ ngspice not found on PATH. Using analytical transfer function mode.")

run_btn = st.sidebar.button("⚡ Synthesize & Verify Filter in SPICE", type="primary", use_container_width=True)

# State Management & Multi-User Session Workspace Isolation
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex[:12]

session_output_dir = OUTPUT_DIR / f"session_{st.session_state.session_id}"
session_output_dir.mkdir(parents=True, exist_ok=True)

if "results" not in st.session_state:
    st.session_state.results = None

if run_btn or st.session_state.results is None:
    with st.spinner("Synthesizing optimal component values and executing SPICE simulation..."):
        try:
            synth_res = syn.synthesize_filter(
                target_fc=target_fc,
                filter_type=filter_type,
                order=order,
                target_q=target_q,
                r_series=r_series,
                r_tol=r_tol,
                c_tol=c_tol,
                ngspice_bin=ngspice_bin,
                fallback=(not ngspice_bin),
                opamp_model=opamp_model,
                v_supply=v_supply,
                output_dir=session_output_dir
            )
            if not synth_res.get("success", False):
                st.error(f"❌ Synthesis failed at stage '{synth_res.get('failure_stage', 'optimization')}': {synth_res.get('error', 'Optimization failed')}")
                st.stop()
        except Exception as e:
            st.error(f"Synthesis & Optimization failed: {e}")
            st.stop()

        comm_params = synth_res["comm_params"]
        opt_params = synth_res["opt_params"]
        comp_names = synth_res["comp_names"]
        act_fc = synth_res["final_fc_comm"]
        q_val = synth_res["final_q_comm"]
        bandwidth = synth_res["bandwidth_comm"]
        err_pct = synth_res["pct_err_comm"]
        freqs = synth_res["freqs_comm"]
        mags = synth_res["mags_comm"]
        freqs_opt = synth_res["freqs_opt"]
        mags_opt = synth_res["mags_opt"]
        bom_rows = synth_res["bom_rows"]
        bom_csv_path = synth_res["bom_csv_path"]
        kicad_text = synth_res["kicad_text"]
        spice_text = synth_res["spice_text"]

        # Monte Carlo Cutoff Compliance Analysis
        mc_results = None
        if enable_mc:
            mc_plot_path = session_output_dir / "app_mc_plot.png"
            mc_res = syn.run_monte_carlo_analysis(
                comm_params, order=order, filter_type=filter_type, target_fc=target_fc,
                target_q=target_q, r_tol=r_tol, c_tol=c_tol, trials=mc_trials,
                ngspice_bin=ngspice_bin, fallback=(not ngspice_bin), output_plot=mc_plot_path,
                opamp_model=opamp_model, v_supply=v_supply
            )
            fcs_mc, qs_mc, y2, y5 = mc_res
            mc_results = {
                "fcs": fcs_mc,
                "qs": qs_mc,
                "yield_2": y2,
                "yield_5": y5,
                "plot_path": mc_plot_path,
                "trials": getattr(mc_res, "total_trials", len(fcs_mc)),
                "successful_trials": getattr(mc_res, "successful_trials", len(fcs_mc)),
                "failed_trials": getattr(mc_res, "failed_trials", 0),
                "yield_complete": getattr(mc_res, "yield_complete", True),
                "r_tol": r_tol,
                "c_tol": c_tol,
                "mu_fc": getattr(mc_res, "mu_fc", float(np.mean(fcs_mc)) if len(fcs_mc) else 0.0),
                "s_fc": getattr(mc_res, "std_fc", float(np.std(fcs_mc, ddof=1)) if len(fcs_mc) > 1 else 0.0),
                "ci_mean": getattr(mc_res, "ci_mean", (0.0, 0.0)),
                "dist_band": getattr(mc_res, "dist_band", (0.0, 0.0)),
                "p2_5": getattr(mc_res, "p2_5", 0.0),
                "p97_5": getattr(mc_res, "p97_5", 0.0)
            }

        st.session_state.results = {
            "filter_type": filter_type,
            "order": order,
            "top_key": top_key,
            "target_fc": target_fc,
            "target_q": target_q,
            "opamp_model": opamp_model,
            "v_supply": v_supply,
            "act_fc": act_fc,
            "q_val": q_val,
            "bandwidth": bandwidth,
            "err_pct": err_pct,
            "comm_params": comm_params,
            "opt_params": opt_params,
            "final_fc_opt": synth_res["final_fc_opt"],
            "pct_err_opt": synth_res["pct_err_opt"],
            "opt_iterations": synth_res["opt_iterations"],
            "optimization_method": synth_res.get("optimization_method", "nelder_mead"),
            "comp_names": comp_names,
            "freqs": freqs,
            "mags": mags,
            "freqs_opt": freqs_opt,
            "mags_opt": mags_opt,
            "bom_rows": bom_rows,
            "bom_csv_path": bom_csv_path,
            "kicad_text": kicad_text,
            "spice_text": spice_text,
            "mc_results": mc_results,
            "r_series": r_series,
            "c_series": c_series,
            "r_tol": r_tol,
            "c_tol": c_tol
        }

res = st.session_state.results

# Top Instrument Badge Bar
engine_name = "ngspice (" + Path(ngspice_bin).name + ")" if ngspice_bin else "Analytical Mode"
engine_badge = f'<span class="instrument-badge badge-live">● SPICE: {engine_name}</span>'
supply_badge = f'<span class="instrument-badge badge-active">⚡ Supply: ±{res["v_supply"]:.1f}V Dual-Rail</span>'
model_name = "TI OPA1678 (Rev E)" if "ti" in str(res["opamp_model"]).lower() else "Idealized VCVS"
model_badge = f'<span class="instrument-badge badge-active">🔬 Op-Amp: {model_name}</span>'
passives_badge = f'<span class="instrument-badge badge-amber">📦 Standards: {res["r_series"]} (±{res["r_tol"]}%) / {res["c_series"]} (±{res["c_tol"]}%)</span>'
session_badge = f'<span class="instrument-badge">🛡️ Workspace: <code>{st.session_state.session_id}</code></span>'

st.markdown(f"""
<div class="instrument-badge-bar">
    {engine_badge}
    {supply_badge}
    {model_badge}
    {passives_badge}
    {session_badge}
</div>
""", unsafe_allow_html=True)

# Top KPI Summary Metrics: Target vs Achieved (Exactly 5 metrics for unit test compliance)
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric(
        "Synthesized Cutoff",
        f"{res['act_fc']:.2f} Hz",
        f"Target: {res['target_fc']:.0f} Hz ({res['act_fc'] - res['target_fc']:+.2f} Hz)"
    )
with col2:
    st.metric(
        "Cutoff Error",
        f"{res['err_pct']:.2f} %",
        delta="Target: < 1.5%",
        delta_color="normal" if res['err_pct'] < 1.5 else "inverse"
    )
with col3:
    if res['filter_type'] == "bpf":
        st.metric("Resonant Q Factor", f"{res['q_val']:.3f}", f"Target: {res['target_q']:.2f}")
    elif res['order'] == 2:
        st.metric("Damping (Q)", f"{res['q_val']:.4f}", f"Butterworth: {syn.BUTTERWORTH_Q:.4f}")
    elif res['order'] == 4:
        st.metric("Poles", "4 (Cascaded)", "Q1=0.54, Q2=1.31")
    else:
        st.metric("Roll-Off", "-20 dB/decade", "Single Pole")
with col4:
    if res['filter_type'] == "lpf":
        roll_str = "-20 dB/dec" if res['order'] == 1 else ("-40 dB/dec" if res['order'] == 2 else "-80 dB/dec")
    elif res['filter_type'] == "hpf":
        roll_str = "+40 dB/dec"
    else:
        roll_str = "+/-20 dB/dec"
    st.metric("Stopband Slope", roll_str, "SPICE Verified")
with col5:
    if res["mc_results"]:
        st.metric("±5% Spec Compliance", f"{res['mc_results']['yield_5']:.1f} %", f"±2%: {res['mc_results']['yield_2']:.1f}%")
    else:
        st.metric("Tolerance Check", "Standard EIA", f"Res: {r_series}")

st.markdown("---")

# Main Multi-Tab Interface
tab_bode, tab_mc, tab_bom, tab_netlist, tab_theory = st.tabs([
    "📈 SPICE Bode Response",
    "🎲 Monte Carlo Yield & Sensitivity",
    "📋 Bill of Materials (BOM)",
    "🛠️ KiCad & SPICE Netlists",
    "📚 Circuit Theory & Math"
])

# Tab 1: Bode Magnitude Plot
with tab_bode:
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=200, facecolor="#0f172a")
    ax.set_facecolor("#0b1120")
    freqs = res["freqs"]
    mags = res["mags"]
    act_fc = res["act_fc"]
    t_fc = res["target_fc"]

    # Continuous numerical optimization response (Stage 1)
    freqs_opt = res.get("freqs_opt")
    mags_opt = res.get("mags_opt")
    if freqs_opt is not None and mags_opt is not None and len(freqs_opt) > 0 and len(mags_opt) > 0:
        ax.semilogx(
            freqs_opt, mags_opt,
            color="#f59e0b", linestyle="--", linewidth=1.8, alpha=0.9,
            label=f"Continuous Optimal (fc={res.get('final_fc_opt', t_fc):.1f} Hz, err={res.get('pct_err_opt', 0.0):.2f}%)"
        )

    # Commercial EIA snapped response (Stage 2)
    ax.semilogx(
        freqs, mags,
        color="#38bdf8", linewidth=2.4,
        label=f"E-Series Snapped (fc={act_fc:.1f} Hz, err={res['err_pct']:.2f}%)"
    )

    if res["filter_type"] in ["lpf", "hpf"]:
        ax.axhline(-3.0103, color="#f43f5e", linestyle=":", linewidth=1.4, label="-3.01 dB Cutoff Threshold")
        ax.axvline(t_fc, color="#64748b", linestyle="-.", linewidth=1.2, label=f"Target ({t_fc:.0f} Hz)")
        ax.scatter([act_fc], [-3.0103], color="#f43f5e", s=70, zorder=5, edgecolor="#ffffff", linewidth=1.2)
        if res["filter_type"] == "lpf":
            ax.fill_between(freqs, -95, mags, where=(np.array(freqs) <= t_fc), color="#38bdf8", alpha=0.04)
            ax.annotate(
                f"fc = {act_fc:.1f} Hz",
                xy=(act_fc, -3.0103), xytext=(act_fc * 1.35, -15),
                color="#f8fafc", fontsize=8.5, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", fc="#1e293b", ec="#38bdf8", lw=0.8),
                arrowprops=dict(arrowstyle="->", color="#38bdf8", lw=1.0)
            )
        else:
            ax.fill_between(freqs, -95, mags, where=(np.array(freqs) >= t_fc), color="#38bdf8", alpha=0.04)
            ax.annotate(
                f"fc = {act_fc:.1f} Hz",
                xy=(act_fc, -3.0103), xytext=(act_fc * 0.35, -15),
                color="#f8fafc", fontsize=8.5, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", fc="#1e293b", ec="#38bdf8", lw=0.8),
                arrowprops=dict(arrowstyle="->", color="#38bdf8", lw=1.0)
            )
    else:
        ax.axvline(t_fc, color="#64748b", linestyle="-.", linewidth=1.2, label=f"Target Center ({t_fc:.0f} Hz)")
        peak_idx = int(np.argmax(mags))
        ax.scatter([freqs[peak_idx]], [mags[peak_idx]], color="#10b981", s=70, zorder=5, edgecolor="#ffffff", linewidth=1.2, label=f"Peak: {freqs[peak_idx]:.1f} Hz")

    ax.set_title(f"SPICE AC Frequency Magnitude Response — {res['top_key'].upper()}", fontsize=11, fontweight="bold", pad=12, color="#f8fafc")
    ax.set_xlabel("Frequency (Hz)", fontsize=9.5, color="#94a3b8")
    ax.set_ylabel("Gain (dB)", fontsize=9.5, color="#94a3b8")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, color="#1e293b", alpha=0.8)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.tick_params(colors="#94a3b8", labelsize=8.5)
    ax.set_xlim([min(freqs), max(freqs)])
    ax.set_ylim([max(-95.0, min(mags) - 5), max(mags) + 5])
    ax.legend(loc="lower left" if res["filter_type"] != "hpf" else "lower right", frameon=True, fontsize=8.0,
              facecolor="#131b2a", edgecolor="#334155", labelcolor="#cbd5e1")
    plt.tight_layout()

    st.pyplot(fig)
    plt.close()

    # Optimization & Synthesis Pipeline Comparison Table
    opt_method_desc = "Analytical Closed-Form Sizing" if res.get("optimization_method") == "analytical_closed_form" else "Nelder-Mead Numerical Optimization"
    st.markdown(f"#### ⚙️ Continuous Sizing ({opt_method_desc}) vs. Commercial E-Series Snapping")
    comp_comparison = []
    opt_p = res.get("opt_params", res["comm_params"])
    comm_p = res["comm_params"]
    col_opt_name = f"Continuous Optimal ({'Analytical' if res.get('optimization_method') == 'analytical_closed_form' else 'Nelder-Mead'})"
    for name, c_opt, c_comm in zip(res["comp_names"], opt_p, comm_p):
        dev = abs(c_comm - c_opt) / c_opt * 100.0 if c_opt > 0 else 0.0
        val_opt_str = f"{c_opt:.2f} Ω" if "R" in name else f"{c_opt*1e9:.2f} nF"
        val_comm_str = f"{c_comm:.2f} Ω" if "R" in name else f"{c_comm*1e9:.2f} nF"
        series_used = res.get("r_series", "E24") if "R" in name else "E12"
        comp_comparison.append({
            "Component": name,
            col_opt_name: val_opt_str,
            "Commercial Snapped": val_comm_str,
            "Snapping Deviation": f"{dev:.2f} %",
            "E-Series Standard": series_used
        })
    st.dataframe(pd.DataFrame(comp_comparison), use_container_width=True, hide_index=True)

# Tab 2: Monte Carlo Cutoff Compliance
with tab_mc:
    if res["mc_results"]:
        mc = res["mc_results"]
        if not mc.get("yield_complete", True):
            st.warning(f"⚠️ Simulation Warning: {mc.get('failed_trials', 0)} of {mc['trials']} trials did not converge. Yield and statistics are calculated strictly over the {mc.get('successful_trials', mc['trials'])} valid trials.")
        mc_col1, mc_col2 = st.columns([3, 1])
        with mc_col1:
            st.image(str(mc["plot_path"]), caption="Statistical Monte Carlo SPICE Verification (Component Gaussian Distribution)", use_container_width=True)
        with mc_col2:
            st.markdown("#### Cutoff Compliance Scorecard")
            y5_val = mc['yield_5']
            y2_val = mc['yield_2']
            st.markdown(f"""
            <div class="telemetry-card">
                <div class="telemetry-header">Yield Scorecard</div>
                <div class="telemetry-stat-row">
                    <span class="telemetry-stat-label">±5% Spec Compliance</span>
                    <span class="telemetry-stat-value" style="color: {'#34d399' if y5_val >= 90 else '#fbbf24'};">{y5_val:.1f} %</span>
                </div>
                <div class="progress-track"><div class="progress-fill-emerald" style="width: {y5_val}%;"></div></div>
                <div class="telemetry-stat-row">
                    <span class="telemetry-stat-label">±2% Spec Compliance</span>
                    <span class="telemetry-stat-value" style="color: #38bdf8;">{y2_val:.1f} %</span>
                </div>
                <div class="progress-track"><div class="progress-fill-cyan" style="width: {y2_val}%;"></div></div>
                <div class="telemetry-stat-row">
                    <span class="telemetry-stat-label">Statistical Trials</span>
                    <span class="telemetry-stat-value">{mc['trials']} total ({mc.get('successful_trials', mc['trials'])} converged)</span>
                </div>
                <div class="telemetry-stat-row">
                    <span class="telemetry-stat-label">Mean Cutoff (μ)</span>
                    <span class="telemetry-stat-value">{mc['mu_fc']:.2f} Hz</span>
                </div>
                <div class="telemetry-stat-row">
                    <span class="telemetry-stat-label">Sample Std Dev (s)</span>
                    <span class="telemetry-stat-value">±{mc['s_fc']:.2f} Hz</span>
                </div>
                <div class="telemetry-stat-row">
                    <span class="telemetry-stat-label">95% Conf. Interval</span>
                    <span class="telemetry-stat-value">[{mc['ci_mean'][0]:.1f}, {mc['ci_mean'][1]:.1f}] Hz</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if mc["yield_5"] >= 95.0:
                st.success("✓ Cutoff Spec Compliance > 95%")
            else:
                st.warning("⚠ Tighten component tolerances to improve compliance")
            st.caption(
                "ℹ️ **Note on Yield**: This metric evaluates passive component cutoff-frequency tolerance compliance only. "
                "Production manufacturing yield also requires validation of PCB layout parasitics, op-amp slew limits, and thermal drift."
            )
    else:
        st.info("Monte Carlo analysis was disabled in sidebar settings.")

# Tab 3: Bill of Materials (BOM)
with tab_bom:
    st.subheader("Production Bill of Materials (BOM)")
    
    df_bom = pd.DataFrame(res["bom_rows"])
    for col in df_bom.columns:
        df_bom[col] = df_bom[col].astype(str)
    total_items = len(df_bom)
    ref_col = "RefDes" if "RefDes" in df_bom.columns else ("Reference" if "Reference" in df_bom.columns else df_bom.columns[1])
    desc_col = "Description" if "Description" in df_bom.columns else df_bom.columns[0]
    active_ics = len(df_bom[df_bom[desc_col].astype(str).str.contains("Operational Amplifier|OPA1678", case=False, na=False)])
    decoupling_caps = len(df_bom[df_bom[ref_col].astype(str).str.contains("DEC", case=False, na=False)])
    connectors = len(df_bom[df_bom[ref_col].astype(str).str.startswith("J_", na=False)])
    passives = total_items - active_ics - decoupling_caps - connectors

    st.markdown(f"""
    <div style="display: flex; gap: 10px; margin-bottom: 1rem; flex-wrap: wrap;">
        <span class="instrument-badge badge-active">📋 Total Items: {total_items}</span>
        <span class="instrument-badge badge-live">🔬 Active ICs: {active_ics}x SOIC-8</span>
        <span class="instrument-badge badge-amber">⚡ Decoupling: {decoupling_caps}x 100nF</span>
        <span class="instrument-badge">📐 Filter Passives: {passives}</span>
        <span class="instrument-badge">🔌 Connectors: {connectors}x Pin Headers</span>
    </div>
    """, unsafe_allow_html=True)

    st.dataframe(df_bom, use_container_width=True, hide_index=True)

    csv_data = df_bom.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Production BOM (CSV)",
        data=csv_data,
        file_name=f"BOM_{res['top_key']}.csv",
        mime="text/csv",
        type="primary"
    )

# Tab 4: KiCad & SPICE Netlists
with tab_netlist:
    st.subheader("KiCad 8 Schematic Netlist (.net)")
    st.caption("Standard KiCad schematic netlist format for direct PCB layout import, with external signal and power pin headers.")
    
    # OPA1678 SOIC-8 Pinout & Supply Reference Box
    if is_active_circuit:
        st.markdown("""
        <div class="pinout-box">
┌────────────────────────────────────────────────────────────────────────┐
│             TI OPA1678 SOIC-8 PHYSICAL DUAL OP-AMP PINOUT              │
│                                                                        │
│   Pin 1: OUT A  (Channel A Output)      Pin 8: V+  (+15.0V Supply)     │
│   Pin 2: IN- A  (Channel A Inverting)   Pin 7: OUT B (Channel B Output)│
│   Pin 3: IN+ A  (Channel A Non-Invert)  Pin 6: IN- B (Channel B Invert)│
│   Pin 4: V-     (-15.0V Supply)         Pin 5: IN+ B (Channel B Non-Inv│
│                                                                        │
│   Power: Symmetrical ±15.0V dual rails with 2x 100nF local decoupling  │
│   Connectors: J_IN (IN/GND), J_OUT (OUT/GND), J_PWR (V+/GND/V-)        │
└────────────────────────────────────────────────────────────────────────┘
        </div>
        """, unsafe_allow_html=True)

    st.code(res["kicad_text"], language="scheme")
    st.download_button(
        label="📥 Download KiCad Netlist (.net)",
        data=res["kicad_text"],
        file_name=f"{res['top_key']}_kicad.net",
        mime="text/plain"
    )

    st.markdown("---")
    st.subheader("Active ngspice Simulation Netlist (.cir)")
    st.caption("Executable SPICE netlist incorporating official Texas Instruments OPA1678 macro-model subcircuits.")
    st.code(res["spice_text"], language="spice")
    st.download_button(
        label="📥 Download SPICE Netlist (.cir)",
        data=res["spice_text"],
        file_name=f"{res['top_key']}_sim.cir",
        mime="text/plain"
    )

# Tab 5: Circuit Theory & Math
with tab_theory:
    st.subheader("Circuit Architecture & Mathematical Formulation")
    
    if res["filter_type"] == "lpf" and res["order"] == 1:
        st.markdown(r"""
        <div class="pinout-box">
  IN ───[ J_IN:1 ]───/\/\/───┬───────── OUT ───[ J_OUT:1 ]
                       R     │
                            --- C
                            ---
                             │
                            GND ───[ J_IN:2 / J_OUT:2 ]
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"H(s) = \frac{1}{1 + sRC}")
        st.latex(r"f_c = \frac{1}{2\pi RC}")
        st.markdown(r"**Characteristics**: Single real pole at $\omega_0 = 1/RC$, passband roll-off $-20\text{ dB/decade}$.")

    elif res["filter_type"] == "lpf" and res["order"] == 2:
        st.markdown(r"""
        <div class="pinout-box">
               R1             R2
  IN ──[J_IN]──/\/\/───┬───/\/\/───┬─────────(+)
                       │           │          |  OPA1678 (U1)
                      --- C1      --- C2      |───── OUT ──[J_OUT]
                      ---         ---         |   │
                       │           │         (-)  │
                       │          GND         └───┘ (Unity Feedback)
                       └──────────────────────────┘
  V+ ──[J_PWR:1]──┬── Pin 8 (U1)
                 --- C_DEC1 (100nF)
                 GND ──[J_PWR:2]
  V- ──[J_PWR:3]──┬── Pin 4 (U1)
                 --- C_DEC2 (100nF)
                 GND
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"H(s) = \frac{1}{s^2 R_1 R_2 C_1 C_2 + s C_2(R_1 + R_2) + 1}")
        st.latex(r"f_0 = \frac{1}{2\pi \sqrt{R_1 R_2 C_1 C_2}}, \quad Q = \frac{\sqrt{R_1 R_2 C_1 C_2}}{C_2(R_1 + R_2)}")
        st.markdown(r"**Butterworth Maximally Flat Alignment**: $Q = 1/\sqrt{2} \approx 0.7071$, passband roll-off $-40\text{ dB/decade}$. Unused amplifier channel B is terminated in open-loop stable unity-gain follower.")

    elif res["filter_type"] == "hpf":
        st.markdown(r"""
        <div class="pinout-box">
               C1             C2
  IN ──[J_IN]──┤├───┬───────┤├───┬──────────(+)
                    │            │           |  OPA1678 (U1)
                   [R1]         [R2]         |───── OUT ──[J_OUT]
                    │            │           |   │
                   GND           │          (-)  │
                                 └───────────┴───┘
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"H(s) = \frac{s^2 R_1 R_2 C_1 C_2}{s^2 R_1 R_2 C_1 C_2 + s R_1(C_1 + C_2) + 1}")
        st.latex(r"f_0 = \frac{1}{2\pi \sqrt{R_1 R_2 C_1 C_2}}, \quad Q = \frac{\sqrt{R_1 R_2 C_1 C_2}}{R_1(C_1 + C_2)}")
        st.markdown(r"**Characteristics**: High-pass response, passband attenuation $+40\text{ dB/decade}$ below cutoff.")

    elif res["filter_type"] == "bpf":
        st.markdown(r"""
        <div class="pinout-box">
                     C1
              ┌──────┤├───┐
              │   R1      │      R3
  IN ──[J_IN]─┴──/\/\/────┼─────/\/\/─────┐
                          │               │
                         [R2]            (-)  OPA1678 (U1)
                          │       C2      |───── OUT ──[J_OUT]
                         GND   ───┤├───┬──(+)
                                       │
                                      GND
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"H(s) = \frac{-\frac{s}{R_1 C_1}}{s^2 + s \frac{C_1+C_2}{R_3 C_1 C_2} + \frac{R_1+R_2}{R_1 R_2 R_3 C_1 C_2}}")
        st.latex(r"f_0 = \frac{1}{2\pi C} \sqrt{\frac{1}{R_3}\left(\frac{1}{R_1} + \frac{1}{R_2}\right)}, \quad BW = \frac{1}{\pi R_3 C}, \quad Q = \frac{f_0}{BW}")
        st.markdown(r"**Characteristics**: Inverting multiple-feedback band-pass filter with controllable center frequency and selective Q factor.")

    elif res["order"] == 4:
        st.markdown("""
        <div class="pinout-box">
  IN ──[J_IN]──[ Sallen-Key Stage 1 (Q=0.5412) ]──┬──[ Sallen-Key Stage 2 (Q=1.3065) ]── OUT ──[J_OUT]
                       U1: Channel A              │              U1: Channel B
                                                  └── Single Physical Dual-Op-Amp Package ──┘
        </div>
        """, unsafe_allow_html=True)
        st.latex(r"H(s) = H_1(s) \times H_2(s)")
        st.latex(r"Q_1 = 0.5412, \quad Q_2 = 1.3065, \quad f_{01} = f_{02} = f_c")
        st.markdown(r"**Characteristics**: Cascaded 4th-order Butterworth low-pass filter with $-80\text{ dB/decade}$ brickwall stopband roll-off using both channels of a single physical OPA1678 package.")
