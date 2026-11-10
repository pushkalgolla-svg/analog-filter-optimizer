"""
Comprehensive automated test suite for the analog filter synthesis pipeline.
Asserts correct SPICE detection, netlist simulation, data parsing, cutoff extraction,
Butterworth Q calculation, commercial E-series component snapping, Monte Carlo yield analysis,
Multi-topology synthesis (LPF, HPF, BPF, 4th-Order Cascade), and BOM/KiCad netlist generation.
"""

import math
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from synthesize import (
    find_ngspice,
    run_spice_simulation,
    parse_simulation_data,
    extract_cutoff_frequency,
    snap_to_e_series,
    find_commercial_pair_1st_order,
    find_commercial_components_2nd_order,
    find_commercial_hpf,
    find_commercial_bpf,
    find_commercial_cascade4,
    run_monte_carlo_analysis,
    TARGET_CUTOFF_HZ,
    BUTTERWORTH_Q
)
from export_manufacturing import generate_bom_data, export_bom_csv, export_kicad_netlist


def run_checks():
    print("[TEST] 1. Checking SPICE binary availability...")
    ngspice = find_ngspice()
    assert ngspice is not None, "ngspice binary was not found!"
    print(f"       Found: {ngspice}")

    print("[TEST] 2. Running isolated 1st-order reference SPICE simulation...")
    test_data_1st = PROJECT_ROOT / "output" / "test_sim_1st.txt"
    c_ref = 10.0e-9
    r_ref = 1.0 / (2.0 * math.pi * TARGET_CUTOFF_HZ * c_ref)
    run_spice_simulation([r_ref, c_ref], order=1, filter_type="lpf", ngspice_bin=ngspice, output_data_file=test_data_1st)
    assert test_data_1st.exists(), f"1st-order simulation output missing: {test_data_1st}"
    freqs_1, mags_1 = parse_simulation_data(test_data_1st)
    fc_1 = extract_cutoff_frequency(freqs_1, mags_1, filter_type="lpf")
    err_1 = abs(fc_1 - TARGET_CUTOFF_HZ)
    print(f"       1st-Order Cutoff: {fc_1:.2f} Hz (Error: {err_1:.4f} Hz < 0.1%). PASS!")
    assert err_1 < 1.0, f"1st-order cutoff error too large: {err_1:.4f} Hz"

    print("[TEST] 3. Running isolated 2nd-order Sallen-Key SPICE simulation...")
    test_data_2nd = PROJECT_ROOT / "output" / "test_sim_2nd.txt"
    params_sk = [14700.0, 7870.0, 22.0e-9, 10.0e-9]
    run_spice_simulation(params_sk, order=2, filter_type="lpf", ngspice_bin=ngspice, output_data_file=test_data_2nd)
    assert test_data_2nd.exists(), f"2nd-order simulation output missing: {test_data_2nd}"
    freqs_2, mags_2 = parse_simulation_data(test_data_2nd)
    fc_2 = extract_cutoff_frequency(freqs_2, mags_2, filter_type="lpf")
    q_2 = math.sqrt(params_sk[0] * params_sk[1] * params_sk[2] * params_sk[3]) / (params_sk[3] * (params_sk[0] + params_sk[1]))

    idx_10k = int(min(range(len(freqs_2)), key=lambda i: abs(freqs_2[i] - 10000.0)))
    atten_10k = mags_2[idx_10k]
    print(f"       2nd-Order Cutoff: {fc_2:.2f} Hz, Q: {q_2:.4f}, Attenuation at 10 kHz: {atten_10k:.2f} dB")
    assert abs(fc_2 - 1000.0) < 10.0, f"2nd-order cutoff deviation too high: {fc_2}"
    assert abs(q_2 - BUTTERWORTH_Q) < 0.02, f"2nd-order Q deviation too high: {q_2}"
    assert atten_10k < -38.0, f"Expected ~ -40 dB roll-off at 10 kHz, got {atten_10k:.2f} dB"
    print("       2nd-Order -40 dB/decade roll-off confirmed. PASS!")

    print("[TEST] 4. Checking EIA E-series snapping across decade boundaries...")
    r_snap = snap_to_e_series(15075.8, "E24")
    assert r_snap in [15000.0, 16000.0]
    # Regression: 9.99 kOhm -> 10.0 kOhm across E12, E24, E96
    for s in ["E12", "E24", "E96"]:
        assert snap_to_e_series(9990.0, s) == 10000.0, f"9.99 kOhm snapping failed for {s}"
        assert snap_to_e_series(10010.0, s) == 10000.0, f"10.01 kOhm snapping failed for {s}"
    print(f"       15075.8 Ohm snapped to E24: {r_snap} Ohm; 9.99k & 10.01k snapped to 10k across all series. PASS!")

    print("[TEST] 5. Checking 1st-order commercial pair search...")
    r_c1, c_c1, fc_c1, err_c1 = find_commercial_pair_1st_order(1000.0, "E24", "E12")
    assert (err_c1 / 1000.0) < 0.01
    print(f"       1st-Order Commercial (E24/E12): R={r_c1} Ohm, C={c_c1*1e9:.1f} nF -> fc={fc_c1:.2f} Hz. PASS!")

    print("[TEST] 6. Checking 2nd-order Sallen-Key commercial component optimization...")
    r1_c2, r2_c2, c1_c2, c2_c2, fc_c2, q_c2 = find_commercial_components_2nd_order(1000.0, "E96", "E12")
    err_fc2 = abs(fc_c2 - 1000.0) / 1000.0
    err_q2 = abs(q_c2 - BUTTERWORTH_Q) / BUTTERWORTH_Q
    assert err_fc2 < 0.01, f"2nd-order commercial cutoff error > 1%: {err_fc2*100:.2f}%"
    assert err_q2 < 0.02, f"2nd-order commercial Q error > 2%: {err_q2*100:.2f}%"
    print(f"       2nd-Order Commercial (E96/E12): R1={r1_c2} R2={r2_c2} C1={c1_c2*1e9:.1f}n C2={c2_c2*1e9:.1f}n")
    print(f"       Achieved fc: {fc_c2:.2f} Hz, Q: {q_c2:.4f}. PASS!")

    print("[TEST] 7. Checking 2nd-Order Sallen-Key High-Pass Filter (HPF)...")
    r1_hpf, r2_hpf, c1_hpf, c2_hpf, fc_hpf, q_hpf = find_commercial_hpf(1000.0, "E96", "E12")
    test_data_hpf = PROJECT_ROOT / "output" / "test_sim_hpf.txt"
    run_spice_simulation([r1_hpf, r2_hpf, c1_hpf, c2_hpf], order=2, filter_type="hpf", ngspice_bin=ngspice, output_data_file=test_data_hpf)
    freqs_h, mags_h = parse_simulation_data(test_data_hpf)
    fc_h_meas = extract_cutoff_frequency(freqs_h, mags_h, filter_type="hpf")
    idx_100 = int(min(range(len(freqs_h)), key=lambda i: abs(freqs_h[i] - 100.0)))
    atten_100 = mags_h[idx_100]
    print(f"       HPF Cutoff: {fc_h_meas:.2f} Hz, Attenuation at 100 Hz: {atten_100:.2f} dB (+40 dB/dec roll-off). PASS!")
    assert abs(fc_h_meas - 1000.0) < 15.0
    assert atten_100 < -35.0

    print("[TEST] 8. Checking 2nd-Order Multiple-Feedback Band-Pass Filter (BPF)...")
    r1_b, r2_b, r3_b, c1_b, c2_b, f0_b, q_b = find_commercial_bpf(1000.0, target_q=2.0, r_series="E96", c_series="E12")
    test_data_bpf = PROJECT_ROOT / "output" / "test_sim_bpf.txt"
    run_spice_simulation([r1_b, r2_b, r3_b, c1_b, c2_b], order=2, filter_type="bpf", ngspice_bin=ngspice, output_data_file=test_data_bpf)
    freqs_b, mags_b = parse_simulation_data(test_data_bpf)
    f_peak, q_meas, bw_meas = extract_cutoff_frequency(freqs_b, mags_b, filter_type="bpf")
    print(f"       BPF Center Frequency: {f_peak:.2f} Hz, Measured Q: {q_meas:.2f}, Bandwidth: {bw_meas:.2f} Hz. PASS!")
    assert abs(f_peak - 1000.0) < 20.0

    print("[TEST] 9. Checking 4th-Order Cascaded Sallen-Key Low-Pass Filter (-80 dB/dec)...")
    c4_params = find_commercial_cascade4(1000.0, "E96", "E12")
    test_data_c4 = PROJECT_ROOT / "output" / "test_sim_c4.txt"
    run_spice_simulation(c4_params, order=4, filter_type="lpf", ngspice_bin=ngspice, output_data_file=test_data_c4)
    freqs_c4, mags_c4 = parse_simulation_data(test_data_c4)
    fc_c4 = extract_cutoff_frequency(freqs_c4, mags_c4, filter_type="lpf")
    idx_10k_c4 = int(min(range(len(freqs_c4)), key=lambda i: abs(freqs_c4[i] - 10000.0)))
    atten_10k_c4 = mags_c4[idx_10k_c4]
    print(f"       4th-Order Cutoff: {fc_c4:.2f} Hz, Attenuation at 10 kHz: {atten_10k_c4:.2f} dB (~ -80 dB/dec). PASS!")
    assert abs(fc_c4 - 1000.0) < 25.0
    assert atten_10k_c4 < -70.0

    print("[TEST] 10. Checking BOM and KiCad netlist exporter...")
    test_bom_data = generate_bom_data("sallen_key_lpf", {"R1": 97600.0, "R2": 52300.0, "C1": 3.3e-9, "C2": 1.5e-9})
    assert len(test_bom_data) == 5, f"Expected 5 BOM items, got {len(test_bom_data)}"
    test_bom_csv = PROJECT_ROOT / "output" / "test_BOM.csv"
    export_bom_csv(test_bom_data, test_bom_csv)
    assert test_bom_csv.exists(), "BOM CSV file was not created!"

    test_kicad_net = PROJECT_ROOT / "output" / "test_kicad.net"
    net_str = export_kicad_netlist("sallen_key_lpf", {"R1": 97600.0, "R2": 52300.0, "C1": 3.3e-9, "C2": 1.5e-9}, test_kicad_net)
    assert test_kicad_net.exists(), "KiCad netlist file was not created!"
    assert "(export (version D)" in net_str
    print("       BOM CSV and KiCad netlist generated successfully. PASS!")

    print("[TEST] 11. Checking Monte Carlo yield analysis...")
    test_mc_plot = PROJECT_ROOT / "output" / "test_mc_plot.png"
    fcs, qs, y2, y5 = run_monte_carlo_analysis([16000.0, 10e-9], order=1, filter_type="lpf", target_fc=1000.0,
                                               r_tol=1.0, c_tol=5.0, trials=10,
                                               ngspice_bin=ngspice, output_plot=test_mc_plot)
    assert len(fcs) == 10, f"Expected 10 Monte Carlo trials, got {len(fcs)}"
    assert test_mc_plot.exists(), f"Monte Carlo test plot missing: {test_mc_plot}"
    print(f"       Monte Carlo executed 10 trials. Yield (+/-5%): {y5:.1f}%. PASS!")

    # Cleanup temporary test files
    for p in [test_data_1st, test_data_2nd, test_data_hpf, test_data_bpf, test_data_c4, test_bom_csv, test_kicad_net, test_mc_plot]:
        if p.exists():
            p.unlink()

    print("\n[ALL 11/11 AUTOMATED CHECKS PASSED SUCCESSFULLY]")


if __name__ == "__main__":
    run_checks()
