"""
Manufacturing Exporter for Analog Filter Synthesis.

Generates production-grade Bill of Materials (BOM) in CSV format
and KiCad-compatible schematic/SPICE netlists (.net) for synthesized filters.
"""

import csv
from pathlib import Path

# Common industrial SMD components (Yageo RC0805, Murata GRM 0805, TI Op-Amps)
MPN_LOOKUP = {
    "opamp": {
        "part_number": "OPA1678IDR",
        "mfr": "Texas Instruments",
        "description": "SoundPlus Dual Low-Distortion Audio Operational Amplifier (SOIC-8)",
        "package": "SOIC-8",
        "est_cost": "$0.85"
    },
    "resistor": {
        "mfr": "Yageo",
        "series": "RC0805FR-07",
        "package": "0805 SMD",
        "description": "Thick Film Chip Resistor 1/8W 150V 100ppm/C",
        "est_cost": "$0.02"
    },
    "capacitor": {
        "mfr": "Murata Electronics",
        "series": "GRM21BR71H",
        "package": "0805 SMD",
        "description": "Multilayer Ceramic Capacitor 50V C0G/X7R",
        "est_cost": "$0.06"
    }
}


def format_eng_unit(val, unit=""):
    """Formats numeric value to human-readable engineering notation."""
    if val >= 1e6:
        return f"{val / 1e6:.4g}M{unit}"
    elif val >= 1e3:
        return f"{val / 1e3:.4g}k{unit}"
    elif val >= 1:
        return f"{val:.4g}{unit}"
    elif val >= 1e-3:
        return f"{val * 1e3:.4g}m{unit}"
    elif val >= 1e-6:
        return f"{val * 1e6:.4g}u{unit}"
    elif val >= 1e-9:
        return f"{val * 1e9:.4g}n{unit}"
    elif val >= 1e-12:
        return f"{val * 1e12:.4g}p{unit}"
    return f"{val:.4e}{unit}"


def generate_bom_data(topology_type, components, r_tol=1.0, c_tol=5.0):
    """
    Creates structured BOM rows for a synthesized filter topology.
    components is a dict like {'R1': 97600.0, 'R2': 52300.0, 'C1': 3.3e-9, 'C2': 1.5e-9}
    """
    bom_rows = []
    item_num = 1

    # Add passive components
    for ref_des, val in components.items():
        if ref_des.startswith("R"):
            val_str = format_eng_unit(val, " Ohm")
            tol_str = f"+/-{r_tol:.1f}%"
            info = MPN_LOOKUP["resistor"]
            mpn = f"{info['series']}{int(val)}RL" if val < 1000000 else f"{info['series']}CUSTOM"
            bom_rows.append({
                "Item": item_num,
                "RefDes": ref_des,
                "Value": val_str,
                "Tolerance": tol_str,
                "Package": info["package"],
                "Manufacturer": info["mfr"],
                "Manufacturer Part Number": mpn,
                "Description": f"{val_str} {info['description']}",
                "Est. Unit Cost (USD)": info["est_cost"]
            })
            item_num += 1
        elif ref_des.startswith("C"):
            val_str = format_eng_unit(val, "F")
            tol_str = f"+/-{c_tol:.1f}%"
            info = MPN_LOOKUP["capacitor"]
            mpn = f"{info['series']}CUSTOM"
            bom_rows.append({
                "Item": item_num,
                "RefDes": ref_des,
                "Value": val_str,
                "Tolerance": tol_str,
                "Package": info["package"],
                "Manufacturer": info["mfr"],
                "Manufacturer Part Number": mpn,
                "Description": f"{val_str} {info['description']}",
                "Est. Unit Cost (USD)": info["est_cost"]
            })
            item_num += 1

    # Add active op-amps for active topologies
    if "sallen_key" in topology_type.lower() or "mfb" in topology_type.lower() or "cascade" in topology_type.lower():
        num_opamps = 2 if "cascade" in topology_type.lower() else 1
        ref_opamp = "U1, U2" if num_opamps == 2 else "U1"
        info = MPN_LOOKUP["opamp"]
        bom_rows.append({
            "Item": item_num,
            "RefDes": ref_opamp,
            "Value": "OPA1678",
            "Tolerance": "N/A",
            "Package": info["package"],
            "Manufacturer": info["mfr"],
            "Manufacturer Part Number": info["part_number"],
            "Description": info["description"],
            "Est. Unit Cost (USD)": info["est_cost"]
        })

    return bom_rows


def export_bom_csv(bom_rows, file_path):
    """Writes BOM dictionary rows to a clean CSV file."""
    if not bom_rows:
        return
    fieldnames = list(bom_rows[0].keys())
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in bom_rows:
            writer.writerow(row)


def export_kicad_netlist(topology_type, components, file_path):
    """
    Generates a KiCad 8 / SPICE compatible schematic netlist.
    """
    lines = [
        f"(export (version D) (design (source \"AnalogFilterSynthesis\") (tool \"ML-Filter-Synthesizer\"))",
        f"  (components",
    ]

    for ref_des, val in components.items():
        if ref_des.startswith("R"):
            val_str = format_eng_unit(val, " Ohm")
            lines.append(f"    (comp (ref {ref_des}) (value \"{val_str}\") (footprint Resistor_SMD:R_0805_2012Metric))")
        elif ref_des.startswith("C"):
            val_str = format_eng_unit(val, "F")
            lines.append(f"    (comp (ref {ref_des}) (value \"{val_str}\") (footprint Capacitor_SMD:C_0805_2012Metric))")

    if "sallen_key" in topology_type.lower() or "mfb" in topology_type.lower() or "cascade" in topology_type.lower():
        num_opamps = 2 if "cascade" in topology_type.lower() else 1
        for i in range(1, num_opamps + 1):
            lines.append(f"    (comp (ref U{i}) (value \"OPA1678\") (footprint Package_SO:SOIC-8_3.9x4.9mm_P1.27mm))")

    lines.append("  )")
    lines.append("  (nets")

    # Generate topological nets
    if "1st_order" in topology_type.lower():
        lines.extend([
            "    (net (code 1) (name \"IN\") (node (ref R1) (pin 1)))",
            "    (net (code 2) (name \"OUT\") (node (ref R1) (pin 2)) (node (ref C1) (pin 1)))",
            "    (net (code 3) (name \"GND\") (node (ref C1) (pin 2)))",
        ])
    elif "sallen_key_lpf" in topology_type.lower():
        lines.extend([
            "    (net (code 1) (name \"IN\") (node (ref R1) (pin 1)))",
            "    (net (code 2) (name \"Net-(R1-Pad2)\") (node (ref R1) (pin 2)) (node (ref R2) (pin 1)) (node (ref C1) (pin 1)))",
            "    (net (code 3) (name \"Net-(R2-Pad2)\") (node (ref R2) (pin 2)) (node (ref C2) (pin 1)) (node (ref U1) (pin 3)))",
            "    (net (code 4) (name \"OUT\") (node (ref C1) (pin 2)) (node (ref U1) (pin 1)) (node (ref U1) (pin 2)))",
            "    (net (code 5) (name \"GND\") (node (ref C2) (pin 2)) (node (ref U1) (pin 4)))",
        ])
    elif "sallen_key_hpf" in topology_type.lower():
        lines.extend([
            "    (net (code 1) (name \"IN\") (node (ref C1) (pin 1)))",
            "    (net (code 2) (name \"Net-(C1-Pad2)\") (node (ref C1) (pin 2)) (node (ref C2) (pin 1)) (node (ref R1) (pin 1)))",
            "    (net (code 3) (name \"Net-(C2-Pad2)\") (node (ref C2) (pin 2)) (node (ref R2) (pin 1)) (node (ref U1) (pin 3)))",
            "    (net (code 4) (name \"OUT\") (node (ref R1) (pin 2)) (node (ref U1) (pin 1)) (node (ref U1) (pin 2)))",
            "    (net (code 5) (name \"GND\") (node (ref R2) (pin 2)) (node (ref U1) (pin 4)))",
        ])
    elif "mfb_bpf" in topology_type.lower():
        lines.extend([
            "    (net (code 1) (name \"IN\") (node (ref R1) (pin 1)))",
            "    (net (code 2) (name \"Net-(R1-Pad2)\") (node (ref R1) (pin 2)) (node (ref R2) (pin 1)) (node (ref C1) (pin 1)) (node (ref C2) (pin 1)))",
            "    (net (code 3) (name \"Net-(C1-Pad2)\") (node (ref C1) (pin 2)) (node (ref R3) (pin 1)) (node (ref U1) (pin 2)))",
            "    (net (code 4) (name \"OUT\") (node (ref C2) (pin 2)) (node (ref R3) (pin 2)) (node (ref U1) (pin 1)))",
            "    (net (code 5) (name \"GND\") (node (ref R2) (pin 2)) (node (ref U1) (pin 3)) (node (ref U1) (pin 4)))",
        ])
    elif "cascade4" in topology_type.lower():
        lines.extend([
            "    (net (code 1) (name \"IN\") (node (ref R1_1) (pin 1)))",
            "    (net (code 2) (name \"STAGE1_NODE\") (node (ref R1_1) (pin 2)) (node (ref R2_1) (pin 1)) (node (ref C1_1) (pin 1)))",
            "    (net (code 3) (name \"STAGE1_INP\") (node (ref R2_1) (pin 2)) (node (ref C2_1) (pin 1)) (node (ref U1) (pin 3)))",
            "    (net (code 4) (name \"STAGE1_OUT\") (node (ref C1_1) (pin 2)) (node (ref U1) (pin 1)) (node (ref U1) (pin 2)) (node (ref R1_2) (pin 1)))",
            "    (net (code 5) (name \"STAGE2_NODE\") (node (ref R1_2) (pin 2)) (node (ref R2_2) (pin 1)) (node (ref C1_2) (pin 1)))",
            "    (net (code 6) (name \"STAGE2_INP\") (node (ref R2_2) (pin 2)) (node (ref C2_2) (pin 1)) (node (ref U2) (pin 3)))",
            "    (net (code 7) (name \"OUT\") (node (ref C1_2) (pin 2)) (node (ref U2) (pin 1)) (node (ref U2) (pin 2)))",
            "    (net (code 8) (name \"GND\") (node (ref C2_1) (pin 2)) (node (ref C2_2) (pin 2)) (node (ref U1) (pin 4)) (node (ref U2) (pin 4)))",
        ])

    lines.append("  )")
    lines.append(")")

    netlist_text = "\n".join(lines)
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(netlist_text)
    return netlist_text
