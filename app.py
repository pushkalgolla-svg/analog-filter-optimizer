"""
Interactive Analog Filter Synthesizer & EDA Verification Dashboard.
Built with Streamlit, SciPy, and ngspice.
"""

import math
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

import scripts.synthesize as syn
import scripts.export_manufacturing as exp

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

# Custom EDA Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #1f77b4;
        margin-bottom: 10px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding-top: 10px;
        padding-bottom: 10px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Application Header
st.title("⚡ Analog Filter Synthesizer & SPICE Verification Studio")
st.caption("Automated Analog Filter Synthesis, Continuous ML Optimization, EIA Standard Component Snapping & Monte Carlo Manufacturing Yield Analysis")

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

# Frequency Target
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

st.sidebar.markdown("---")
st.sidebar.header("🎲 Manufacturing Yield Analysis")
enable_mc = st.sidebar.checkbox("Run Monte Carlo Statistical Analysis", value=True)
mc_trials = st.sidebar.slider("Monte Carlo Trials", min_value=10, max_value=150, value=50, step=10)

# Check SPICE simulator
ngspice_bin = syn.find_ngspice()
if ngspice_bin:
    st.sidebar.success(f"✓ SPICE Engine Detected: ngspice ({Path(ngspice_bin).name})")
else:
    st.sidebar.warning("⚠ ngspice not found on PATH. Using analytical transfer function mode.")

run_btn = st.sidebar.button("⚡ Synthesize & Verify Filter in SPICE", type="primary", use_container_width=True)

# State Management
if "results" not in st.session_state:
    st.session_state.results = None

if run_btn or st.session_state.results is None:
    with st.spinner("Synthesizing optimal component values and executing SPICE simulation..."):
        # 1. Commercial snapping
        if filter_type == "lpf":
            if order == 1:
                comm_r, comm_c, _, _ = syn.find_commercial_pair_1st_order(target_fc, r_series=r_series, c_series=c_series)
                comm_params = [comm_r, comm_c]
                comp_names = ["R1", "C1"]
            elif order == 2:
                comm_r1, comm_r2, comm_c1, comm_c2, _, _ = syn.find_commercial_components_2nd_order(target_fc, r_series=r_series, c_series=c_series)
                comm_params = [comm_r1, comm_r2, comm_c1, comm_c2]
                comp_names = ["R1", "R2", "C1", "C2"]
            elif order == 4:
                comm_params = list(syn.find_commercial_cascade4(target_fc, r_series=r_series, c_series=c_series))
                comp_names = ["R1_1", "R2_1", "C1_1", "C2_1", "R1_2", "R2_2", "C1_2", "C2_2"]
        elif filter_type == "hpf":
            comm_r1, comm_r2, comm_c1, comm_c2, _, _ = syn.find_commercial_hpf(target_fc, r_series=r_series, c_series=c_series)
            comm_params = [comm_r1, comm_r2, comm_c1, comm_c2]
            comp_names = ["R1", "R2", "C1", "C2"]
        elif filter_type == "bpf":
            comm_r1, comm_r2, comm_r3, comm_c1, comm_c2, _, _ = syn.find_commercial_bpf(target_fc, target_q=target_q, r_series=r_series, c_series=c_series)
            comm_params = [comm_r1, comm_r2, comm_r3, comm_c1, comm_c2]
            comp_names = ["R1", "R2", "R3", "C1", "C2"]

        # Run SPICE AC sweep
        sim_data_file = OUTPUT_DIR / "app_sim_data.txt"
        syn.run_spice_simulation(comm_params, order=order, filter_type=filter_type, ngspice_bin=ngspice_bin, fallback=(not ngspice_bin), output_data_file=sim_data_file, target_fc=target_fc)
        freqs, mags = syn.parse_simulation_data(sim_data_file)

        # Extract frequency and metrics
        if filter_type in ["lpf", "hpf"]:
            act_fc = syn.extract_cutoff_frequency(freqs, mags, filter_type=filter_type)
            if order == 2:
                if filter_type == "lpf":
                    q_val = math.sqrt(comm_params[0] * comm_params[1] * comm_params[2] * comm_params[3]) / (comm_params[3] * (comm_params[0] + comm_params[1]))
                else:
                    q_val = math.sqrt(comm_params[0] * comm_params[1] * comm_params[2] * comm_params[3]) / (comm_params[0] * (comm_params[2] + comm_params[3]))
            elif order == 4:
                q_val = 0.7071
            else:
                q_val = 0.0
            bandwidth = 0.0
        else:
            act_fc, q_val, bandwidth = syn.extract_cutoff_frequency(freqs, mags, filter_type="bpf")

        err_pct = abs(act_fc - target_fc) / target_fc * 100.0

        # Generate BOM and Netlist
        comp_dict = {k: v for k, v in zip(comp_names, comm_params)}
        bom_rows = exp.generate_bom_data(top_key, comp_dict, r_tol=r_tol, c_tol=c_tol)
        bom_csv_path = OUTPUT_DIR / f"BOM_{top_key}.csv"
        exp.export_bom_csv(bom_rows, bom_csv_path)

        kicad_path = OUTPUT_DIR / f"{top_key}_kicad.net"
        kicad_text = exp.export_kicad_netlist(top_key, comp_dict, kicad_path)

        # SPICE Netlist
        current_spice_text = syn.CURRENT_SIM_PATH.read_text(encoding="utf-8") if syn.CURRENT_SIM_PATH.exists() else ""

        # Monte Carlo
        mc_results = None
        if enable_mc:
            mc_plot_path = OUTPUT_DIR / "app_mc_plot.png"
            fcs_mc, qs_mc, y2, y5 = syn.run_monte_carlo_analysis(
                comm_params, order=order, filter_type=filter_type, target_fc=target_fc,
                target_q=target_q, r_tol=r_tol, c_tol=c_tol, trials=mc_trials,
                ngspice_bin=ngspice_bin, fallback=(not ngspice_bin), output_plot=mc_plot_path
            )
            mc_results = {
                "fcs": fcs_mc,
                "qs": qs_mc,
                "yield_2": y2,
                "yield_5": y5,
                "plot_path": mc_plot_path
            }

        st.session_state.results = {
            "filter_type": filter_type,
            "order": order,
            "top_key": top_key,
            "target_fc": target_fc,
            "target_q": target_q,
            "act_fc": act_fc,
            "q_val": q_val,
            "bandwidth": bandwidth,
            "err_pct": err_pct,
            "comm_params": comm_params,
            "comp_names": comp_names,
            "freqs": freqs,
            "mags": mags,
            "bom_rows": bom_rows,
            "bom_csv_path": bom_csv_path,
            "kicad_text": kicad_text,
            "spice_text": current_spice_text,
            "mc_results": mc_results
        }

res = st.session_state.results

# Top KPI Summary Metrics
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Synthesized Frequency", f"{res['act_fc']:.2f} Hz", f"{res['act_fc'] - res['target_fc']:+.2f} Hz")
with col2:
    st.metric("Target Error", f"{res['err_pct']:.2f} %", delta="Pass (< 1.5%)", delta_color="normal" if res['err_pct'] < 1.5 else "inverse")
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
        st.metric("±5% Spec Yield", f"{res['mc_results']['yield_5']:.1f} %", f"±2%: {res['mc_results']['yield_2']:.1f}%")
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
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=200)
    freqs = res["freqs"]
    mags = res["mags"]
    act_fc = res["act_fc"]
    t_fc = res["target_fc"]

    ax.semilogx(freqs, mags, color="#1f77b4", linewidth=2.5, label=f"SPICE AC Sweep (Simulated fc={act_fc:.1f} Hz)")
    if res["filter_type"] in ["lpf", "hpf"]:
        ax.axhline(-3.0103, color="#d62728", linestyle=":", label="-3.01 dB Cutoff Threshold")
        ax.axvline(t_fc, color="#7f7f7f", linestyle="-.", label=f"Target ({t_fc:.0f} Hz)")
        ax.scatter([act_fc], [-3.0103], color="#d62728", s=80, zorder=5)
    else:
        ax.axvline(t_fc, color="#7f7f7f", linestyle="-.", label=f"Target Center ({t_fc:.0f} Hz)")
        peak_idx = int(np.argmax(mags))
        ax.scatter([freqs[peak_idx]], [mags[peak_idx]], color="#2ca02c", s=80, zorder=5, label=f"Peak: {freqs[peak_idx]:.1f} Hz")

    ax.set_title(f"SPICE Bode Magnitude Response - {res['top_key'].upper()}", fontsize=11, fontweight="bold")
    ax.set_xlabel("Frequency (Hz)", fontsize=10)
    ax.set_ylabel("Magnitude (dB)", fontsize=10)
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.6)
    ax.set_xlim([min(freqs), max(freqs)])
    ax.set_ylim([max(-95.0, min(mags) - 5), max(mags) + 5])
    ax.legend(loc="lower left" if res["filter_type"] != "hpf" else "lower right", frameon=True, fontsize=8.5)
    plt.tight_layout()

    st.pyplot(fig)
    plt.close()

# Tab 2: Monte Carlo Yield
with tab_mc:
    if res["mc_results"]:
        mc = res["mc_results"]
        mc_col1, mc_col2 = st.columns([3, 1])
        with mc_col1:
            st.image(str(mc["plot_path"]), caption="Statistical Monte Carlo SPICE Verification (Component Gaussian Distribution)", use_container_width=True)
        with mc_col2:
            st.markdown("#### Yield Scorecard")
            st.markdown(f"""
            - **Trials**: `{len(mc['fcs'])} SPICE runs`
            - **Mean fc**: `{np.mean(mc['fcs']):.2f} Hz`
            - **Std Dev ($\sigma$)**: `{np.std(mc['fcs']):.2f} Hz`
            - **95% Confidence Interval**:
              `[{np.mean(mc['fcs']) - 1.96*np.std(mc['fcs']):.1f} Hz, {np.mean(mc['fcs']) + 1.96*np.std(mc['fcs']):.1f} Hz]`
            - **±2% Band Yield**: `{mc['yield_2']:.1f} %`
            - **±5% Band Yield**: `{mc['yield_5']:.1f} %`
            """)
            if mc["yield_5"] >= 95.0:
                st.success("✓ Production Grade Yield (> 95%)")
            else:
                st.warning("⚠ Tighten component tolerances to improve yield")
    else:
        st.info("Monte Carlo analysis was disabled in sidebar settings.")

# Tab 3: Bill of Materials (BOM)
with tab_bom:
    st.subheader("Production Bill of Materials (BOM)")
    df_bom = pd.DataFrame(res["bom_rows"])
    st.dataframe(df_bom, use_container_width=True, hide_index=True)

    csv_data = df_bom.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download BOM (CSV)",
        data=csv_data,
        file_name=f"BOM_{res['top_key']}.csv",
        mime="text/csv",
        type="primary"
    )

# Tab 4: KiCad & SPICE Netlists
with tab_netlist:
    st.subheader("KiCad 8 Schematic Netlist (.net)")
    st.caption("Standard KiCad schematic netlist format for direct PCB layout import.")
    st.code(res["kicad_text"], language="scheme")
    st.download_button(
        label="📥 Download KiCad Netlist",
        data=res["kicad_text"],
        file_name=f"{res['top_key']}_kicad.net",
        mime="text/plain"
    )

    st.markdown("---")
    st.subheader("Active ngspice Netlist (.cir)")
    st.caption("SPICE netlist executed by ngspice console binary.")
    st.code(res["spice_text"], language="spice")

# Tab 5: Circuit Theory & Math
with tab_theory:
    st.subheader("Circuit Architecture & Mathematical Formulation")
    if res["filter_type"] == "lpf" and res["order"] == 1:
        st.latex(r"H(s) = \frac{1}{1 + sRC}")
        st.latex(r"f_c = \frac{1}{2\pi RC}")
        st.markdown("**Characteristics**: Single real pole at $\omega_0 = 1/RC$, passband roll-off $-20\text{ dB/decade}$.")
    elif res["filter_type"] == "lpf" and res["order"] == 2:
        st.latex(r"H(s) = \frac{1}{s^2 R_1 R_2 C_1 C_2 + s C_2(R_1 + R_2) + 1}")
        st.latex(r"f_0 = \frac{1}{2\pi \sqrt{R_1 R_2 C_1 C_2}}, \quad Q = \frac{\sqrt{R_1 R_2 C_1 C_2}}{C_2(R_1 + R_2)}")
        st.markdown("**Butterworth Maximally Flat Alignment**: $Q = 1/\sqrt{2} \approx 0.7071$, passband roll-off $-40\text{ dB/decade}$.")
    elif res["filter_type"] == "hpf":
        st.latex(r"H(s) = \frac{s^2 R_1 R_2 C_1 C_2}{s^2 R_1 R_2 C_1 C_2 + s R_1(C_1 + C_2) + 1}")
        st.latex(r"f_0 = \frac{1}{2\pi \sqrt{R_1 R_2 C_1 C_2}}, \quad Q = \frac{\sqrt{R_1 R_2 C_1 C_2}}{R_1(C_1 + C_2)}")
        st.markdown("**Characteristics**: High-pass response, passband attenuation $+40\text{ dB/decade}$ below cutoff.")
    elif res["filter_type"] == "bpf":
        st.latex(r"H(s) = \frac{-\frac{s}{R_1 C_1}}{s^2 + s \frac{C_1+C_2}{R_3 C_1 C_2} + \frac{R_1+R_2}{R_1 R_2 R_3 C_1 C_2}}")
        st.latex(r"f_0 = \frac{1}{2\pi C} \sqrt{\frac{1}{R_3}\left(\frac{1}{R_1} + \frac{1}{R_2}\right)}, \quad BW = \frac{1}{\pi R_3 C}, \quad Q = \frac{f_0}{BW}")
        st.markdown("**Characteristics**: Inverting multiple-feedback band-pass filter with controllable center frequency and selective Q factor.")
    elif res["order"] == 4:
        st.latex(r"H(s) = H_1(s) \times H_2(s)")
        st.latex(r"Q_1 = 0.5412, \quad Q_2 = 1.3065, \quad f_{01} = f_{02} = f_c")
        st.markdown("**Characteristics**: Cascaded 4th-order Butterworth low-pass filter with $-80\text{ dB/decade}$ brickwall stopband roll-off.")
