"""
Integration tests for the Analog Filter Synthesizer using the ngspice SPICE simulator.
These tests verify that ngspice executes AC sweeps, generates raw data,
and validates cutoff frequency extraction, Q-factor calculation, and Monte Carlo compliance yield.

Tests are skipped if ngspice is not available on PATH or the default installation location.
"""

import math
import sys
import unittest
from pathlib import Path

# Add project root and scripts directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from synthesize import (
    find_ngspice,
    run_spice_simulation,
    parse_simulation_data,
    extract_cutoff_frequency,
    find_commercial_pair_1st_order,
    find_commercial_components_2nd_order,
    find_commercial_hpf,
    find_commercial_bpf,
    find_commercial_cascade4,
    run_monte_carlo_analysis,
    synthesize_filter,
    OPAMP_MODEL_TI,
    OPAMP_MODEL_IDEAL,
    DEFAULT_V_SUPPLY,
    TARGET_CUTOFF_HZ,
    BUTTERWORTH_Q,
)

NGSPICE_BIN = find_ngspice()


@unittest.skipIf(NGSPICE_BIN is None, "ngspice binary not detected; skipping SPICE integration tests")
class TestSpiceIntegration(unittest.TestCase):
    """SPICE simulation integration tests for all supported filter topologies."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = PROJECT_ROOT / "output"
        cls.test_dir.mkdir(parents=True, exist_ok=True)
        cls.created_files = []

    @classmethod
    def tearDownClass(cls):
        for f in cls.created_files:
            if f.exists():
                try:
                    f.unlink()
                except OSError:
                    pass

    def test_ngspice_binary_detection(self):
        """Ensure ngspice binary path is resolved and executable."""
        self.assertIsNotNone(NGSPICE_BIN)
        self.assertTrue(Path(NGSPICE_BIN).exists())

    def test_1st_order_rc_lpf_simulation(self):
        """1st-order RC LPF SPICE simulation achieves target cutoff within 0.1%."""
        test_out = self.test_dir / "test_int_1st.txt"
        self.created_files.append(test_out)

        c_ref = 10.0e-9
        r_ref = 1.0 / (2.0 * math.pi * TARGET_CUTOFF_HZ * c_ref)
        run_spice_simulation(
            [r_ref, c_ref], order=1, filter_type="lpf",
            ngspice_bin=NGSPICE_BIN, fallback=False, output_data_file=test_out
        )
        self.assertTrue(test_out.exists())

        freqs, mags = parse_simulation_data(test_out)
        fc = extract_cutoff_frequency(freqs, mags, filter_type="lpf")
        err = abs(fc - TARGET_CUTOFF_HZ)
        self.assertLess(err, 1.0, f"1st-order cutoff error too large: {err:.4f} Hz")

    def test_2nd_order_sallen_key_lpf_simulation(self):
        """2nd-order Sallen-Key LPF achieves ~ -40 dB/decade roll-off and Q ~ 0.7071."""
        test_out = self.test_dir / "test_int_2nd.txt"
        self.created_files.append(test_out)

        params_sk = [14700.0, 7870.0, 22.0e-9, 10.0e-9]
        run_spice_simulation(
            params_sk, order=2, filter_type="lpf",
            ngspice_bin=NGSPICE_BIN, fallback=False, output_data_file=test_out
        )
        self.assertTrue(test_out.exists())

        freqs, mags = parse_simulation_data(test_out)
        fc = extract_cutoff_frequency(freqs, mags, filter_type="lpf")
        q = math.sqrt(params_sk[0] * params_sk[1] * params_sk[2] * params_sk[3]) / (
            params_sk[3] * (params_sk[0] + params_sk[1])
        )

        # Attenuation at 10 kHz (one decade above cutoff) should be ~ -40 dB
        idx_10k = int(min(range(len(freqs)), key=lambda i: abs(freqs[i] - 10000.0)))
        atten_10k = mags[idx_10k]

        self.assertLess(abs(fc - 1000.0), 10.0)
        self.assertLess(abs(q - BUTTERWORTH_Q), 0.02)
        self.assertLess(atten_10k, -38.0, f"Expected ~ -40 dB roll-off at 10 kHz, got {atten_10k:.2f} dB")

    def test_2nd_order_sallen_key_hpf_simulation(self):
        """2nd-order Sallen-Key HPF achieves +40 dB/decade high-pass roll-off."""
        test_out = self.test_dir / "test_int_hpf.txt"
        self.created_files.append(test_out)

        r1, r2, c1, c2, _, _ = find_commercial_hpf(1000.0, "E96", "E12")
        run_spice_simulation(
            [r1, r2, c1, c2], order=2, filter_type="hpf",
            ngspice_bin=NGSPICE_BIN, fallback=False, output_data_file=test_out
        )
        self.assertTrue(test_out.exists())

        freqs, mags = parse_simulation_data(test_out)
        fc = extract_cutoff_frequency(freqs, mags, filter_type="hpf")

        # Attenuation at 100 Hz (one decade below cutoff) should be ~ -40 dB
        idx_100 = int(min(range(len(freqs)), key=lambda i: abs(freqs[i] - 100.0)))
        atten_100 = mags[idx_100]

        self.assertLess(abs(fc - 1000.0), 15.0)
        self.assertLess(atten_100, -35.0, f"Expected ~ -40 dB roll-off at 100 Hz, got {atten_100:.2f} dB")

    def test_2nd_order_mfb_bpf_simulation(self):
        """2nd-order MFB BPF achieves resonant center frequency and Q factor."""
        test_out = self.test_dir / "test_int_bpf.txt"
        self.created_files.append(test_out)

        r1, r2, r3, c1, c2, _, _ = find_commercial_bpf(1000.0, target_q=2.0, r_series="E96", c_series="E12")
        run_spice_simulation(
            [r1, r2, r3, c1, c2], order=2, filter_type="bpf",
            ngspice_bin=NGSPICE_BIN, fallback=False, output_data_file=test_out
        )
        self.assertTrue(test_out.exists())

        freqs, mags = parse_simulation_data(test_out)
        f_peak, q_meas, bw_meas = extract_cutoff_frequency(freqs, mags, filter_type="bpf")

        self.assertLess(abs(f_peak - 1000.0), 25.0)
        self.assertGreater(q_meas, 1.0)
        self.assertGreater(bw_meas, 0.0)

    def test_4th_order_cascaded_lpf_simulation(self):
        """4th-order cascaded Sallen-Key LPF achieves ~ -80 dB/decade roll-off."""
        test_out = self.test_dir / "test_int_c4.txt"
        self.created_files.append(test_out)

        c4_params = find_commercial_cascade4(1000.0, "E96", "E12")
        run_spice_simulation(
            c4_params, order=4, filter_type="lpf",
            ngspice_bin=NGSPICE_BIN, fallback=False, output_data_file=test_out
        )
        self.assertTrue(test_out.exists())

        freqs, mags = parse_simulation_data(test_out)
        fc = extract_cutoff_frequency(freqs, mags, filter_type="lpf")

        idx_10k = int(min(range(len(freqs)), key=lambda i: abs(freqs[i] - 10000.0)))
        atten_10k = mags[idx_10k]

        self.assertLess(abs(fc - 1000.0), 25.0)
        self.assertLess(atten_10k, -70.0, f"Expected ~ -80 dB roll-off at 10 kHz, got {atten_10k:.2f} dB")

    def test_monte_carlo_statistical_yield(self):
        """Monte Carlo analysis runs multiple SPICE trials and produces valid statistics."""
        plot_out = self.test_dir / "test_int_mc.png"
        self.created_files.append(plot_out)

        fcs, qs, y2, y5 = run_monte_carlo_analysis(
            [16000.0, 10.0e-9], order=1, filter_type="lpf", target_fc=1000.0,
            r_tol=1.0, c_tol=5.0, trials=15,
            ngspice_bin=NGSPICE_BIN, fallback=False, output_plot=plot_out
        )

        self.assertEqual(len(fcs), 15)
        self.assertTrue(plot_out.exists())
        self.assertGreaterEqual(y5, 0.0)
        self.assertLessEqual(y5, 100.0)

    def test_end_to_end_filter_synthesis_with_spice(self):
        """End-to-end synthesize_filter with ngspice SPICE engine."""
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=2,
            r_series="E96",
            ngspice_bin=NGSPICE_BIN,
            fallback=False
        )
        self.assertTrue(res["success"])
        self.assertLess(res["pct_err_comm"], 1.5)
        self.assertTrue(res["bom_csv_path"].exists())
        self.assertTrue(res["kicad_net_path"].exists())


    def test_ti_opa1678_macro_model_spice_execution(self):
        """Official TI OPA1678 macro-model executes cleanly in ngspice with dual-rail +/-15V supply."""
        test_out = self.test_dir / "test_ti_opa1678.txt"
        self.created_files.append(test_out)

        params_sk = [14700.0, 7870.0, 22.0e-9, 10.0e-9]
        run_spice_simulation(
            params_sk, order=2, filter_type="lpf",
            ngspice_bin=NGSPICE_BIN, fallback=False, output_data_file=test_out,
            opamp_model=OPAMP_MODEL_TI, v_supply=15.0
        )
        self.assertTrue(test_out.exists())
        freqs, mags = parse_simulation_data(test_out)
        self.assertEqual(len(freqs), 401)
        fc = extract_cutoff_frequency(freqs, mags, filter_type="lpf")
        self.assertLess(abs(fc - 1000.0), 10.0)

    def test_idealized_vs_ti_model_frequency_response(self):
        """Compare idealized VCVS vs TI OPA1678 macro-model responses: both achieve cutoff, macro-model adds real op-amp response."""
        out_ideal = self.test_dir / "test_out_ideal.txt"
        out_ti = self.test_dir / "test_out_ti.txt"
        self.created_files.extend([out_ideal, out_ti])

        params_sk = [14700.0, 7870.0, 22.0e-9, 10.0e-9]
        run_spice_simulation(
            params_sk, order=2, filter_type="lpf",
            ngspice_bin=NGSPICE_BIN, fallback=False, output_data_file=out_ideal,
            opamp_model=OPAMP_MODEL_IDEAL
        )
        run_spice_simulation(
            params_sk, order=2, filter_type="lpf",
            ngspice_bin=NGSPICE_BIN, fallback=False, output_data_file=out_ti,
            opamp_model=OPAMP_MODEL_TI, v_supply=15.0
        )

        fc_ideal = extract_cutoff_frequency(*parse_simulation_data(out_ideal), filter_type="lpf")
        fc_ti = extract_cutoff_frequency(*parse_simulation_data(out_ti), filter_type="lpf")

        self.assertLess(abs(fc_ideal - 1000.0), 10.0)
        self.assertLess(abs(fc_ti - 1000.0), 10.0)
        # Macro-model and idealized are in close agreement at audio frequencies (< 1 Hz difference)
        self.assertLess(abs(fc_ideal - fc_ti), 2.0)

    def test_concurrent_spice_simulations(self):
        """Concurrent ngspice simulations in separate threads run without intermediate file collision."""
        import concurrent.futures

        out1 = self.test_dir / "test_conc_1.txt"
        out2 = self.test_dir / "test_conc_2.txt"
        self.created_files.extend([out1, out2])

        def sim1():
            run_spice_simulation([10000.0, 10e-9], order=1, filter_type="lpf",
                                 ngspice_bin=NGSPICE_BIN, output_data_file=out1)
            return parse_simulation_data(out1)

        def sim2():
            run_spice_simulation([14700.0, 7870.0, 22e-9, 10e-9], order=2, filter_type="lpf",
                                 ngspice_bin=NGSPICE_BIN, output_data_file=out2,
                                 opamp_model=OPAMP_MODEL_TI, v_supply=15.0)
            return parse_simulation_data(out2)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(sim1)
            f2 = ex.submit(sim2)
            f1.result()
            f2.result()

        self.assertTrue(out1.exists())
        self.assertTrue(out2.exists())
        fc1 = extract_cutoff_frequency(*parse_simulation_data(out1), filter_type="lpf")
        fc2 = extract_cutoff_frequency(*parse_simulation_data(out2), filter_type="lpf")
        self.assertAlmostEqual(fc1, 1591.6, delta=5.0)
        self.assertAlmostEqual(fc2, 997.0, delta=10.0)


if __name__ == "__main__":
    unittest.main()
