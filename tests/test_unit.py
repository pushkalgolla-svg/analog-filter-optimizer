"""
Unit tests for Analog Filter Synthesizer & Manufacturing EDA Pipeline.
These tests run in pure Python without requiring an external ngspice binary.
Covers:
  - E-series snapping across decade boundaries (E12, E24, E96)
  - Zero, negative, NaN, Inf, and non-numeric input validation
  - Very small (pF) and very large (MΩ) component values
  - Curated BOM catalogue lookup and verified vs. unverified part labelling
  - BOM CSV generation and KiCad netlist export validation
  - Analytical transfer function evaluation and continuous optimization pipeline
"""

import csv
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add project root and scripts directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from synthesize import (
    snap_to_e_series,
    synthesize_filter,
    find_commercial_pair_1st_order,
    find_commercial_components_2nd_order,
    find_commercial_hpf,
    find_commercial_bpf,
    find_commercial_cascade4,
    run_spice_simulation,
    loss_function,
    E_SERIES,
    TARGET_CUTOFF_HZ,
    BUTTERWORTH_Q,
    SENTINEL_FAILURE_OBJ,
)
from export_manufacturing import (
    find_verified_component,
    generate_bom_data,
    export_bom_csv,
    export_kicad_netlist,
    VERIFIED_COMPONENT_CATALOG,
)


class TestESeriesSnapping(unittest.TestCase):
    """Regression tests for E-series component snapping across decades and edge cases."""

    def test_decade_boundary_9_99k_snaps_to_10k(self):
        """Regression: 9.99 kΩ must snap to 10 kΩ across all standard series (E12, E24, E96)."""
        for series in ["E12", "E24", "E96"]:
            with self.subTest(series=series):
                snapped = snap_to_e_series(9990.0, series)
                self.assertAlmostEqual(snapped, 10000.0, places=4,
                                       msg=f"9.99 kΩ failed to snap to 10 kΩ in {series}")

    def test_decade_boundary_10_01k_snaps_to_10k(self):
        """Values immediately above decade boundary (10.01 kΩ) must snap to 10 kΩ."""
        for series in ["E12", "E24", "E96"]:
            with self.subTest(series=series):
                snapped = snap_to_e_series(10010.0, series)
                self.assertAlmostEqual(snapped, 10000.0, places=4,
                                       msg=f"10.01 kΩ failed to snap to 10 kΩ in {series}")

    def test_decade_boundary_capacitors_around_1nf(self):
        """Capacitor decade boundaries: 0.99 nF and 1.01 nF must snap to 1.0 nF."""
        for series in ["E12", "E24"]:
            with self.subTest(series=series):
                self.assertAlmostEqual(snap_to_e_series(0.99e-9, series), 1.0e-9, places=14)
                self.assertAlmostEqual(snap_to_e_series(1.01e-9, series), 1.0e-9, places=14)

    def test_decade_boundary_resistors_around_100_ohm(self):
        """Resistors around 100 Ω: 99.9 Ω and 100.1 Ω must snap to 100 Ω."""
        for series in ["E12", "E24", "E96"]:
            with self.subTest(series=series):
                self.assertAlmostEqual(snap_to_e_series(99.9, series), 100.0, places=4)
                self.assertAlmostEqual(snap_to_e_series(100.1, series), 100.0, places=4)

    def test_mathematically_nearest_selection(self):
        """Verify that the chosen value is mathematically closest among all decades."""
        # In E12 multipliers: ..., 6.8, 8.2, 10.0, 12.0, ...
        # For 9.2 kΩ: |9.2 - 8.2| = 1.0 kΩ, |9.2 - 10.0| = 0.8 kΩ -> 10.0 kΩ is closer.
        self.assertEqual(snap_to_e_series(9200.0, "E12"), 10000.0)

        # For 8.8 kΩ: |8.8 - 8.2| = 0.6 kΩ, |8.8 - 10.0| = 1.2 kΩ -> 8.2 kΩ is closer.
        self.assertEqual(snap_to_e_series(8800.0, "E12"), 8200.0)

        # In E24 multipliers: ..., 8.2, 9.1, 10.0, 11.0, ...
        # For 9.6 kΩ: |9.6 - 9.1| = 0.5 kΩ, |9.6 - 10.0| = 0.4 kΩ -> 10.0 kΩ is closer.
        self.assertEqual(snap_to_e_series(9600.0, "E24"), 10000.0)

        # In E96: 9.76, 10.0, 10.2
        # For 9.90 kΩ: |9.90 - 9.76| = 0.14 kΩ, |9.90 - 10.0| = 0.10 kΩ -> 10.0 kΩ is closer.
        self.assertEqual(snap_to_e_series(9900.0, "E96"), 10000.0)

    def test_extreme_component_values(self):
        """Very small (pF) and very large (MΩ) component values must snap accurately."""
        # Small capacitance: 1.03 pF -> 1.0 pF
        c_small = snap_to_e_series(1.03e-12, "E12")
        self.assertAlmostEqual(c_small, 1.0e-12, places=17)

        # Large resistance: 9.98 MΩ -> 10.0 MΩ
        r_large = snap_to_e_series(9.98e6, "E24")
        self.assertAlmostEqual(r_large, 10.0e6, places=1)

    def test_invalid_and_non_finite_inputs(self):
        """Zero, negative, NaN, Inf, non-numeric, and unsupported series must raise exceptions."""
        with self.assertRaises(ValueError):
            snap_to_e_series(0.0, "E24")

        with self.assertRaises(ValueError):
            snap_to_e_series(-1000.0, "E24")

        with self.assertRaises(ValueError):
            snap_to_e_series(float("nan"), "E24")

        with self.assertRaises(ValueError):
            snap_to_e_series(float("inf"), "E24")

        with self.assertRaises(ValueError):
            snap_to_e_series(float("-inf"), "E24")

        with self.assertRaises(TypeError):
            snap_to_e_series("10k", "E24")

        with self.assertRaises(ValueError):
            snap_to_e_series(1000.0, "E48")


class TestBOMManufacturingCatalog(unittest.TestCase):
    """Tests for verified BOM catalogue matching, unverified labelling, and exports."""

    def test_verified_resistor_lookup(self):
        """Verified 10 kΩ 0805 1% resistor returns exact Yageo MPN and datasheet link."""
        part = find_verified_component("R1", 10000.0)
        self.assertEqual(part["mfr"], "Yageo")
        self.assertEqual(part["mpn"], "RC0805FR-0710KL")
        self.assertEqual(part["package"], "0805 SMD")
        self.assertIn("yageo.com", part["ref"])

    def test_verified_capacitor_lookup(self):
        """Verified 10 nF 0805 capacitor returns exact Murata MPN and datasheet link."""
        part = find_verified_component("C1", 10.0e-9, tol=5.0)
        self.assertEqual(part["mfr"], "Murata Electronics")
        self.assertEqual(part["mpn"], "GRM2195C1H103JA01D")
        self.assertEqual(part["rating"], "50V C0G")
        self.assertIn("murata.com", part["ref"])

    def test_verified_opamp_lookup(self):
        """Verified active op-amp returns exact TI MPN and datasheet link."""
        part = find_verified_component("U1", "OPA1678")
        self.assertEqual(part["mfr"], "Texas Instruments")
        self.assertEqual(part["mpn"], "OPA1678IDR")
        self.assertEqual(part["package"], "SOIC-8")
        self.assertIn("ti.com", part["ref"])

    def test_unverified_part_labeling(self):
        """Arbitrary component values not in catalogue are cleanly labelled Generic."""
        part = find_verified_component("R1", 1337.0)
        self.assertEqual(part["mfr"], "Generic")
        self.assertEqual(part["mpn"], "Generic - MPN not verified")
        self.assertEqual(part["ref"], "N/A (Generic)")

    def test_no_fabricated_mpn_strings(self):
        """Ensure no string concatenation templates are used to invent part numbers."""
        test_values = [1234.5, 9876.5, 33333.3, 0.123e-9]
        for val in test_values:
            part = find_verified_component("R1", val)
            self.assertFalse(part["mpn"].startswith("RC0805FR-07"),
                             f"Fabricated MPN generated for unverified value {val}: {part['mpn']}")

    def test_10pct_capacitor_does_not_satisfy_5pct_design_tolerance(self):
        """A +/-10% capacitor must not satisfy a +/-5% design tolerance requirement."""
        # 100 nF capacitor in catalogue has tol_pct=10.0 (+/-10% X7R)
        part_fail = find_verified_component("C1", 100.0e-9, tol=5.0)
        self.assertEqual(part_fail["mfr"], "Generic")
        self.assertEqual(part_fail["mpn"], "Generic - MPN not verified")

        # But with tol=10.0, the same 100 nF capacitor matches
        part_pass = find_verified_component("C1", 100.0e-9, tol=10.0)
        self.assertEqual(part_pass["mfr"], "Murata Electronics")
        self.assertEqual(part_pass["mpn"], "GRM21BR71H104KA01L")
        self.assertEqual(part_pass["tolerance"], "+/-10.0%")

    def test_1pct_resistor_does_not_satisfy_half_pct_design_tolerance(self):
        """A +/-1% resistor must not satisfy a +/-0.5% precision design tolerance."""
        # 10 kΩ resistor in catalogue is rated +/-1.0% (tol_pct=1.0)
        part = find_verified_component("R1", 10000.0, tol=0.5)
        self.assertEqual(part["mfr"], "Generic")
        self.assertEqual(part["mpn"], "Generic - MPN not verified")

    def test_1pct_resistor_satisfies_5pct_design_requirement_showing_actual_1pct_rating(self):
        """A +/-1% resistor may satisfy a +/-5% design requirement, but its BOM must show the actual +/-1% rating."""
        part = find_verified_component("R1", 10000.0, tol=5.0)
        self.assertEqual(part["mfr"], "Yageo")
        self.assertEqual(part["mpn"], "RC0805FR-0710KL")
        self.assertEqual(part["tolerance"], "+/-1.0%")
        self.assertEqual(part["tol_pct"], 1.0)

        bom = generate_bom_data("1st_order_rc", {"R1": 10000.0, "C1": 1.0e-8}, r_tol=5.0, c_tol=5.0)
        r_row = next(r for r in bom if r["RefDes"] == "R1")
        self.assertEqual(r_row["Component Tolerance"], "+/-1.0%")
        self.assertEqual(r_row["Design / MC Tolerance"], "+/-5.0%")

    def test_mc_assumed_tolerance_and_actual_bom_component_tolerance_displayed_separately(self):
        """Monte Carlo assumed tolerance and actual BOM component tolerance must be displayed separately."""
        bom = generate_bom_data("sallen_key_lpf", {"R1": 10000.0, "R2": 22000.0, "C1": 10.0e-9, "C2": 4.7e-9}, r_tol=1.0, c_tol=5.0)
        for row in bom:
            self.assertIn("Component Tolerance", row)
            self.assertIn("Design / MC Tolerance", row)
            if row["RefDes"] == "U1":
                self.assertEqual(row["Component Tolerance"], "N/A")
                self.assertEqual(row["Design / MC Tolerance"], "N/A")
            elif row["RefDes"].startswith("R"):
                self.assertEqual(row["Component Tolerance"], "+/-1.0%")
                self.assertEqual(row["Design / MC Tolerance"], "+/-1.0%")
            elif row["RefDes"].startswith("C"):
                self.assertEqual(row["Component Tolerance"], "+/-5.0%")
                self.assertEqual(row["Design / MC Tolerance"], "+/-5.0%")

    def test_obsolete_components_not_automatically_selected(self):
        """Obsolete or discontinued components must not be automatically selected for a new manufacturing BOM."""
        # 6.8 nF capacitor is marked status: 'Obsolete' in catalogue
        part = find_verified_component("C1", 6.8e-9, tol=10.0)
        self.assertEqual(part["mfr"], "Generic")
        self.assertEqual(part["mpn"], "Generic - MPN not verified")

        # Obsolete op-amp LM301A must also fall back to generic
        opamp = find_verified_component("U1", "LM301A")
        self.assertEqual(opamp["mfr"], "Generic")
        self.assertEqual(opamp["mpn"], "Generic - MPN not verified")

    def test_unverified_or_incompatible_parts_use_generic_fallback(self):
        """Unverified values or incompatible tolerances must use explicit Generic fallback."""
        # Unverified arbitrary value
        part = find_verified_component("R1", 7777.7)
        self.assertEqual(part["mfr"], "Generic")
        self.assertEqual(part["mpn"], "Generic - MPN not verified")
        self.assertEqual(part["tolerance"], "Generic - MPN not verified")
        self.assertEqual(part["ref"], "N/A (Generic)")

    def test_bom_csv_generation_and_schema(self):
        """Generate BOM data and verify CSV export schema and parseability."""
        comp_dict = {"R1": 10000.0, "R2": 22000.0, "C1": 10.0e-9, "C2": 4.7e-9}
        bom_rows = generate_bom_data("sallen_key_lpf", comp_dict, r_tol=1.0, c_tol=5.0)
        self.assertEqual(len(bom_rows), 5)  # 2 resistors + 2 caps + 1 op-amp

        out_csv = PROJECT_ROOT / "output" / "test_unit_bom.csv"
        export_bom_csv(bom_rows, out_csv)
        self.assertTrue(out_csv.exists())

        # Validate CSV contents using stdlib csv
        with open(out_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            expected_fields = [
                "Item", "RefDes", "Value", "Component Tolerance", "Design / MC Tolerance", "Rating",
                "Package", "Manufacturer", "Manufacturer Part Number",
                "Description", "Datasheet / Reference", "Est. Unit Cost (USD)"
            ]
            self.assertEqual(reader.fieldnames, expected_fields)
            rows = list(reader)
            self.assertEqual(len(rows), 5)

        if out_csv.exists():
            out_csv.unlink()

    def test_kicad_netlist_syntax(self):
        """Validate KiCad 8 netlist S-expression export."""
        comp_dict = {"R1": 10000.0, "R2": 22000.0, "C1": 10.0e-9, "C2": 4.7e-9}
        out_net = PROJECT_ROOT / "output" / "test_unit_kicad.net"
        net_str = export_kicad_netlist("sallen_key_lpf", comp_dict, out_net)
        self.assertTrue(out_net.exists())
        self.assertIn("(export (version D)", net_str)
        self.assertIn("(components", net_str)
        self.assertIn("(nets", net_str)
        self.assertIn("OPA1678", net_str)

        if out_net.exists():
            out_net.unlink()


class TestAnalyticalSynthesisPipeline(unittest.TestCase):
    """Tests for the unified synthesis engine in analytical mode (no ngspice needed)."""

    def test_1st_order_lpf_analytical_synthesis(self):
        """1st-order RC LPF synthesis via shared synthesize_filter in fallback mode."""
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=1,
            r_series="E24",
            fallback=True
        )
        self.assertTrue(res["success"])
        self.assertAlmostEqual(res["target_fc"], 1000.0, places=1)
        self.assertLess(res["pct_err_comm"], 1.5, f"Cutoff error too high: {res['pct_err_comm']}%")
        self.assertEqual(len(res["comm_params"]), 2)

    def test_2nd_order_sallen_key_lpf_analytical_synthesis(self):
        """2nd-order Sallen-Key LPF synthesis via shared synthesize_filter."""
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=2,
            r_series="E96",
            fallback=True
        )
        self.assertTrue(res["success"])
        self.assertLess(res["pct_err_comm"], 1.5)
        self.assertAlmostEqual(res["final_q_comm"], BUTTERWORTH_Q, delta=0.03)

    def test_2nd_order_sallen_key_hpf_analytical_synthesis(self):
        """2nd-order Sallen-Key HPF synthesis via shared synthesize_filter."""
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="hpf",
            order=2,
            r_series="E96",
            fallback=True
        )
        self.assertTrue(res["success"])
        self.assertLess(res["pct_err_comm"], 1.5)

    def test_2nd_order_bpf_analytical_synthesis(self):
        """2nd-order MFB BPF synthesis via shared synthesize_filter."""
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="bpf",
            order=2,
            target_q=2.0,
            r_series="E96",
            fallback=True
        )
        self.assertTrue(res["success"])
        self.assertLess(res["pct_err_comm"], 2.5)

    def test_4th_order_cascade_lpf_analytical_synthesis(self):
        """4th-order cascaded Sallen-Key LPF synthesis via shared synthesize_filter."""
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=4,
            r_series="E96",
            fallback=True
        )
        self.assertTrue(res["success"])
        self.assertLess(res["pct_err_comm"], 2.5)
        self.assertEqual(len(res["comm_params"]), 8)

    def test_invalid_filter_specifications_raise_error(self):
        """Invalid filter parameters must raise ValueError."""
        with self.assertRaises(ValueError):
            synthesize_filter(target_fc=-500.0, filter_type="lpf", order=1, fallback=True)

        with self.assertRaises(ValueError):
            synthesize_filter(target_fc=1000.0, filter_type="notch", order=1, fallback=True)

        with self.assertRaises(ValueError):
            synthesize_filter(target_fc=1000.0, filter_type="lpf", order=3, fallback=True)


class TestOptimizerFailureHandling(unittest.TestCase):
    """
    Regression tests for optimizer convergence checks, sentinel rejection,
    and simulation verification failure handling in synthesize_filter().
    """

    def test_successful_optimization_reporting(self):
        """Standard Nelder-Mead optimization succeeds and accurately reports method and metrics."""
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=2,
            r_series="E96",
            fallback=True
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["optimization_method"], "nelder_mead")
        self.assertGreater(res["opt_iterations"], 0)
        self.assertTrue(all(p > 0 and math.isfinite(p) for p in res["opt_params"]))
        self.assertTrue(all(p > 0 and math.isfinite(p) for p in res["comm_params"]))
        self.assertTrue(math.isfinite(res["final_fc_opt"]) and res["final_fc_opt"] > 0)
        self.assertTrue(math.isfinite(res["final_fc_comm"]) and res["final_fc_comm"] > 0)
        self.assertLess(res["pct_err_comm"], 1.5)

    def test_fourth_order_analytical_closed_form_sizing_path(self):
        """4th-order cascaded LPF uses analytical closed-form sizing, distinct from Nelder-Mead."""
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=4,
            r_series="E96",
            fallback=True
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["optimization_method"], "analytical_closed_form")
        self.assertEqual(res["opt_iterations"], 0)
        self.assertEqual(len(res["opt_params"]), 8)
        self.assertTrue(all(p > 0 and math.isfinite(p) for p in res["opt_params"]))
        self.assertIn("Analytical closed-form", res["opt_message"])
        self.assertLess(res["pct_err_comm"], 2.5)

    @patch("synthesize.minimize")
    def test_optimizer_returning_success_false(self, mock_minimize):
        """When optimizer returns success=False, synthesize_filter reports failure with clear error."""
        from scipy.optimize import OptimizeResult
        mock_minimize.return_value = OptimizeResult(
            success=False,
            message="Maximum iterations reached without convergence",
            fun=150.0,
            x=[4.0, 4.0, -8.0, -8.0],
            nit=300
        )
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=2,
            fallback=True
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["failure_stage"], "continuous_optimization")
        self.assertIn("failed to converge", res["error"])
        self.assertIn("Maximum iterations reached", res["error"])

    @patch("synthesize.minimize")
    def test_optimizer_returning_non_finite_objective_nan(self, mock_minimize):
        """When optimizer returns NaN objective, synthesize_filter rejects it."""
        from scipy.optimize import OptimizeResult
        mock_minimize.return_value = OptimizeResult(
            success=True,
            message="Optimization terminated successfully",
            fun=float("nan"),
            x=[4.0, 4.0, -8.0, -8.0],
            nit=25
        )
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=2,
            fallback=True
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["failure_stage"], "continuous_optimization")
        self.assertIn("non-finite objective value", res["error"])

    @patch("synthesize.minimize")
    def test_optimizer_returning_non_finite_objective_inf(self, mock_minimize):
        """When optimizer returns Inf objective, synthesize_filter rejects it."""
        from scipy.optimize import OptimizeResult
        mock_minimize.return_value = OptimizeResult(
            success=True,
            message="Optimization terminated successfully",
            fun=float("inf"),
            x=[4.0, 4.0, -8.0, -8.0],
            nit=25
        )
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=2,
            fallback=True
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["failure_stage"], "continuous_optimization")
        self.assertIn("non-finite objective value", res["error"])

    @patch("synthesize.minimize")
    def test_all_evaluations_returning_failure_sentinel(self, mock_minimize):
        """When objective evaluates to failure sentinel (1e12), synthesize_filter rejects it."""
        from scipy.optimize import OptimizeResult
        mock_minimize.return_value = OptimizeResult(
            success=True,
            message="Optimization terminated successfully",
            fun=1.0e12,
            x=[4.0, 4.0, -8.0, -8.0],
            nit=25
        )
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=2,
            fallback=True
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["failure_stage"], "continuous_optimization")
        self.assertIn("failure sentinel", res["error"])

    @patch("synthesize.minimize")
    def test_optimizer_returning_non_positive_components(self, mock_minimize):
        """When optimizer produces non-positive or NaN component values, synthesize_filter rejects it."""
        from scipy.optimize import OptimizeResult
        mock_minimize.return_value = OptimizeResult(
            success=True,
            message="Optimization terminated successfully",
            fun=0.01,
            x=[float("nan"), 4.0, -8.0, -8.0],
            nit=25
        )
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=2,
            fallback=True
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["failure_stage"], "continuous_optimization")
        self.assertIn("non-physical, non-finite, or non-positive", res["error"])

    @patch("synthesize.loss_function")
    def test_invalid_final_simulation_frequency(self, mock_loss):
        """When final simulated cutoff frequency is non-positive or sentinel, synthesize_filter reports verification failure."""
        mock_loss.side_effect = [
            (1000.0, 0.7071, 0.0),    # init_fc
            (0.0, 0.0, 1.0e12),       # final_fc_opt verification failure
        ]
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=4,  # analytical closed-form path directly reaches verification
            fallback=True
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["failure_stage"], "continuous_verification")
        self.assertIn("invalid cutoff frequency", res["error"])

    @patch("synthesize.parse_simulation_data")
    def test_empty_or_unusable_simulation_response_data(self, mock_parse):
        """When simulation data parsing returns empty or insufficient points, synthesize_filter reports failure."""
        import numpy as np
        mock_parse.return_value = (np.array([]), np.array([]))
        res = synthesize_filter(
            target_fc=1000.0,
            filter_type="lpf",
            order=4,
            fallback=True
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["failure_stage"], "continuous_verification")
        self.assertIn("insufficient", res["error"])

    def test_raise_on_error_mode(self):
        """When raise_on_error=True, failure raises RuntimeError instead of returning dictionary."""
        with patch("synthesize.minimize") as mock_minimize:
            from scipy.optimize import OptimizeResult
            mock_minimize.return_value = OptimizeResult(
                success=False,
                message="Convergence failure",
                fun=999.0,
                x=[4.0, 4.0, -8.0, -8.0],
                nit=100
            )
            with self.assertRaises(RuntimeError) as ctx:
                synthesize_filter(
                    target_fc=1000.0,
                    filter_type="lpf",
                    order=2,
                    fallback=True,
                    raise_on_error=True
                )
            self.assertIn("failed to converge", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
