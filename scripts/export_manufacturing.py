"""
Manufacturing Exporter for Analog Filter Synthesis.

Generates production-grade Bill of Materials (BOM) in CSV format
using a curated catalog of verified manufacturer part numbers (MPNs),
and KiCad-compatible schematic netlists (.net) for synthesized filters.
"""

import csv
from pathlib import Path


class BOMRow(dict):
    """
    Dictionary representing a BOM item row.
    Provides backward compatibility so accessing row['Tolerance'] returns
    the actual component tolerance without creating duplicate CSV columns.
    """
    def __getitem__(self, key):
        if key == "Tolerance" and "Tolerance" not in self and "Component Tolerance" in self:
            return self["Component Tolerance"]
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key == "Tolerance" and "Tolerance" not in self and "Component Tolerance" in self:
            return self["Component Tolerance"]
        return super().get(key, default)


# Curated catalog of commercially verified industrial SMD components.
# Contains real manufacturer part numbers from manufacturer datasheets and distributor catalogs.
# When a design calls for a value not in this curated list, or if the part's actual tolerance
# is looser than the requested design tolerance, or if the part is obsolete, the exporter
# marks it as 'Generic - MPN not verified' rather than synthesizing a fabricated part number.
VERIFIED_COMPONENT_CATALOG = {
    "resistors": {
        1000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-071KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "1k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        4530.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-074K53L",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "4.53k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        7870.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-077K87L",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "7.87k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        10000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0710KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "10k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        12000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0712KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "12k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        12700.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0712K7L",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "12.7k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        14700.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0714K7L",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "14.7k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        15000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0715KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "15k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        16000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0716KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "16k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        20000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0720KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "20k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        22000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0722KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "22k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        24000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0724KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "24k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        30000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0730KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "30k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        31600.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0731K6L",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "31.6k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        47000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0747KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "47k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        52300.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0752K3L",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "52.3k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        60400.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0760K4L",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "60.4k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        63400.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0763K4L",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "63.4k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        75000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0775KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "75k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        97600.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-0797K6L",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "97.6k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        100000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-07100KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "100k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        },
        150000.0: {
            "mfr": "Yageo",
            "mpn": "RC0805FR-07150KL",
            "package": "0805 SMD",
            "rating": "0.125W 150V",
            "tolerance": "+/-1.0%",
            "tol_pct": 1.0,
            "status": "Active",
            "description": "150k Ohm Thick Film Chip Resistor 0805 1/8W 150V +/-1%",
            "ref": "https://www.yageo.com/upload/files/datasheet/smd/RC_L_2016_v4.pdf",
            "cost": "$0.02"
        }
    },
    "capacitors": {
        1.0e-9: {
            "mfr": "Murata Electronics",
            "mpn": "GRM2165C1H102JA01D",
            "package": "0805 SMD",
            "rating": "50V C0G",
            "tolerance": "+/-5.0%",
            "tol_pct": 5.0,
            "status": "Active",
            "description": "1.0nF (1000pF) Multilayer Ceramic Capacitor 0805 50V C0G +/-5%",
            "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM2165C1H102JA01%23",
            "cost": "$0.08"
        },
        1.5e-9: [
            {
                "mfr": "Murata Electronics",
                "mpn": "GRM2165C1H152JA01D",
                "package": "0805 SMD",
                "rating": "50V C0G",
                "tolerance": "+/-5.0%",
                "tol_pct": 5.0,
                "status": "Active",
                "description": "1.5nF Multilayer Ceramic Capacitor 0805 50V C0G +/-5%",
                "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM2165C1H152JA01%23",
                "cost": "$0.08"
            },
            {
                "mfr": "Murata Electronics",
                "mpn": "GRM216R71H152KA01D",
                "package": "0805 SMD",
                "rating": "50V X7R",
                "tolerance": "+/-10.0%",
                "tol_pct": 10.0,
                "status": "Obsolete",
                "description": "1.5nF Multilayer Ceramic Capacitor 0805 50V X7R +/-10% (NRND/Discontinued)",
                "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM216R71H152KA01%23",
                "cost": "$0.05"
            }
        ],
        2.2e-9: {
            "mfr": "Murata Electronics",
            "mpn": "GRM2165C1H222JA01D",
            "package": "0805 SMD",
            "rating": "50V C0G",
            "tolerance": "+/-5.0%",
            "tol_pct": 5.0,
            "status": "Active",
            "description": "2.2nF Multilayer Ceramic Capacitor 0805 50V C0G +/-5%",
            "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM2165C1H222JA01%23",
            "cost": "$0.08"
        },
        3.3e-9: {
            "mfr": "Murata Electronics",
            "mpn": "GRM2165C1H332JA01D",
            "package": "0805 SMD",
            "rating": "50V C0G",
            "tolerance": "+/-5.0%",
            "tol_pct": 5.0,
            "status": "Active",
            "description": "3.3nF Multilayer Ceramic Capacitor 0805 50V C0G +/-5%",
            "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM2165C1H332JA01%23",
            "cost": "$0.08"
        },
        4.7e-9: {
            "mfr": "Murata Electronics",
            "mpn": "GRM2165C1H472JA01D",
            "package": "0805 SMD",
            "rating": "50V C0G",
            "tolerance": "+/-5.0%",
            "tol_pct": 5.0,
            "status": "Active",
            "description": "4.7nF Multilayer Ceramic Capacitor 0805 50V C0G +/-5%",
            "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM2165C1H472JA01%23",
            "cost": "$0.08"
        },
        6.8e-9: {
            "mfr": "Murata Electronics",
            "mpn": "GRM216R71H682KA01D",
            "package": "0805 SMD",
            "rating": "50V X7R",
            "tolerance": "+/-10.0%",
            "tol_pct": 10.0,
            "status": "Obsolete",
            "description": "6.8nF Multilayer Ceramic Capacitor 0805 50V X7R +/-10% (Obsolete - Discontinued)",
            "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM216R71H682KA01%23",
            "cost": "$0.05"
        },
        1.0e-8: [
            {
                "mfr": "Murata Electronics",
                "mpn": "GRM2195C1H103JA01D",
                "package": "0805 SMD",
                "rating": "50V C0G",
                "tolerance": "+/-5.0%",
                "tol_pct": 5.0,
                "status": "Active",
                "description": "10nF Multilayer Ceramic Capacitor 0805 50V C0G +/-5%",
                "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM2195C1H103JA01%23",
                "cost": "$0.09"
            },
            {
                "mfr": "Murata Electronics",
                "mpn": "GRM21BR71H103KA01L",
                "package": "0805 SMD",
                "rating": "50V X7R",
                "tolerance": "+/-10.0%",
                "tol_pct": 10.0,
                "status": "Active",
                "description": "10nF (0.01uF) Multilayer Ceramic Capacitor 0805 50V X7R +/-10%",
                "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM21BR71H103KA01%23",
                "cost": "$0.06"
            }
        ],
        1.2e-8: {
            "mfr": "Murata Electronics",
            "mpn": "GRM21BR71H123KA01L",
            "package": "0805 SMD",
            "rating": "50V X7R",
            "tolerance": "+/-10.0%",
            "tol_pct": 10.0,
            "status": "Active",
            "description": "12nF Multilayer Ceramic Capacitor 0805 50V X7R +/-10%",
            "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM21BR71H123KA01%23",
            "cost": "$0.06"
        },
        2.2e-8: {
            "mfr": "Murata Electronics",
            "mpn": "GRM21BR71H223KA01L",
            "package": "0805 SMD",
            "rating": "50V X7R",
            "tolerance": "+/-10.0%",
            "tol_pct": 10.0,
            "status": "Active",
            "description": "22nF Multilayer Ceramic Capacitor 0805 50V X7R +/-10%",
            "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM21BR71H223KA01%23",
            "cost": "$0.06"
        },
        3.3e-8: {
            "mfr": "Murata Electronics",
            "mpn": "GRM21BR71H333KA01L",
            "package": "0805 SMD",
            "rating": "50V X7R",
            "tolerance": "+/-10.0%",
            "tol_pct": 10.0,
            "status": "Active",
            "description": "33nF Multilayer Ceramic Capacitor 0805 50V X7R +/-10%",
            "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM21BR71H333KA01%23",
            "cost": "$0.06"
        },
        4.7e-8: {
            "mfr": "Murata Electronics",
            "mpn": "GRM21BR71H473KA01L",
            "package": "0805 SMD",
            "rating": "50V X7R",
            "tolerance": "+/-10.0%",
            "tol_pct": 10.0,
            "status": "Active",
            "description": "47nF Multilayer Ceramic Capacitor 0805 50V X7R +/-10%",
            "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM21BR71H473KA01%23",
            "cost": "$0.06"
        },
        1.0e-7: {
            "mfr": "Murata Electronics",
            "mpn": "GRM21BR71H104KA01L",
            "package": "0805 SMD",
            "rating": "50V X7R",
            "tolerance": "+/-10.0%",
            "tol_pct": 10.0,
            "status": "Active",
            "description": "100nF (0.1uF) Multilayer Ceramic Capacitor 0805 50V X7R +/-10%",
            "ref": "https://www.murata.com/en-global/products/productdetail?partno=GRM21BR71H104KA01%23",
            "cost": "$0.07"
        }
    },
    "opamps": {
        "OPA1678": {
            "mfr": "Texas Instruments",
            "mpn": "OPA1678IDR",
            "package": "SOIC-8",
            "rating": "4.5V to 36V, 16MHz GBW, 4.5nV/rtHz",
            "tolerance": "N/A",
            "tol_pct": None,
            "status": "Active",
            "description": "SoundPlus Dual Low-Distortion Audio Operational Amplifier (SOIC-8)",
            "ref": "https://www.ti.com/lit/ds/symlink/opa1678.pdf",
            "cost": "$0.85"
        },
        "TL072": {
            "mfr": "Texas Instruments",
            "mpn": "TL072CDR",
            "package": "SOIC-8",
            "rating": "+/-5V to +/-15V, 3MHz GBW, 13V/us",
            "tolerance": "N/A",
            "tol_pct": None,
            "status": "Active",
            "description": "Low-Noise JFET-Input Dual Operational Amplifier (SOIC-8)",
            "ref": "https://www.ti.com/lit/ds/symlink/tl072.pdf",
            "cost": "$0.45"
        },
        "LM301A": {
            "mfr": "Texas Instruments",
            "mpn": "LM301AN",
            "package": "PDIP-8",
            "rating": "+/-5V to +/-18V general purpose",
            "tolerance": "N/A",
            "tol_pct": None,
            "status": "Obsolete",
            "description": "Operational Amplifier (Obsolete / Discontinued)",
            "ref": "https://www.ti.com/lit/ds/symlink/lm301a.pdf",
            "cost": "$0.25"
        }
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


def find_verified_component(ref_des, val, tol=None):
    """
    Looks up component in the curated verified catalogue.

    Validation Rules:
    1. Matches nominal value within 0.1% tolerance.
    2. Enforces lifecycle status: obsolete or discontinued parts are never selected
       for manufacturing BOMs.
    3. Enforces tolerance compatibility: when design tolerance `tol` is specified,
       the selected part's actual tolerance (`tol_pct`) must be equal to or tighter
       than the requested tolerance (tol_pct <= tol). A +/-10% part will never satisfy
       a +/-5% requirement.
    4. If no compatible active verified part exists, returns an explicit
       'Generic - MPN not verified' entry to prevent fabrication of non-existent parts.
    """
    ref_upper = str(ref_des).upper()

    # Active ICs / Op-amps
    if ref_upper.startswith("U"):
        opamp_name = str(val).upper()
        catalog = VERIFIED_COMPONENT_CATALOG.get("opamps", {})
        for key, entry in catalog.items():
            if key.upper() in opamp_name or opamp_name in key.upper():
                if entry.get("status", "Active").lower() == "active":
                    return entry.copy()
        return {
            "mfr": "Generic",
            "mpn": "Generic - MPN not verified",
            "package": "SOIC-8",
            "rating": "Dual Op-Amp",
            "tolerance": "N/A",
            "tol_pct": None,
            "status": "Unverified",
            "description": f"{val} Operational Amplifier",
            "ref": "N/A (Generic)",
            "cost": "$0.50"
        }

    try:
        val_f = float(val)
    except (ValueError, TypeError):
        return {
            "mfr": "Generic",
            "mpn": "Generic - MPN not verified",
            "package": "0805 SMD",
            "rating": "Specified by design",
            "tolerance": "Generic - MPN not verified",
            "tol_pct": None,
            "status": "Unverified",
            "description": f"{val} Component",
            "ref": "N/A (Generic)",
            "cost": "$0.05"
        }

    tol_f = float(tol) if tol is not None else None

    # Search resistors or capacitors
    if ref_upper.startswith("R"):
        catalog = VERIFIED_COMPONENT_CATALOG.get("resistors", {})
    elif ref_upper.startswith("C"):
        catalog = VERIFIED_COMPONENT_CATALOG.get("capacitors", {})
    else:
        catalog = {}

    candidates = []
    for cat_val, entry in catalog.items():
        if abs(val_f - cat_val) / cat_val < 0.001:
            entries = entry if isinstance(entry, list) else [entry]
            candidates.extend(entries)

    # Filter candidates:
    # 1. Must be Active (skip Obsolete / Discontinued / NRND)
    # 2. Must satisfy requested tolerance (tol_pct <= tol_f)
    compatible = []
    for cand in candidates:
        if cand.get("status", "Active").lower() != "active":
            continue
        cand_tol = cand.get("tol_pct")
        if tol_f is not None and cand_tol is not None:
            if cand_tol > tol_f:
                continue
        compatible.append(cand)

    if compatible:
        # Prefer tightest tolerance, then lowest cost
        compatible.sort(key=lambda x: (x.get("tol_pct") if x.get("tol_pct") is not None else 999.0, x.get("cost", "$999.0")))
        return compatible[0].copy()

    # Fallback for unverified, obsolete, or tolerance-incompatible values
    val_str = format_eng_unit(val_f, " Ohm") if ref_upper.startswith("R") else format_eng_unit(val_f, "F")
    comp_type = "Resistor" if ref_upper.startswith("R") else "Capacitor"
    rating_str = "1/8W 150V" if ref_upper.startswith("R") else "50V Ceramic"
    tol_label = "Generic - MPN not verified"

    return {
        "mfr": "Generic",
        "mpn": "Generic - MPN not verified",
        "package": "0805 SMD",
        "rating": rating_str,
        "tolerance": tol_label,
        "tol_pct": tol_f,
        "status": "Unverified",
        "description": f"{val_str} {comp_type} (0805 SMD)",
        "ref": "N/A (Generic)",
        "cost": "$0.02" if ref_upper.startswith("R") else "$0.06"
    }


def generate_bom_data(topology_type, components, r_tol=1.0, c_tol=5.0):
    """
    Creates structured BOM rows for a synthesized filter topology.
    components is a dict like {'R1': 97600.0, 'R2': 52300.0, 'C1': 3.3e-9, 'C2': 1.5e-9}

    Each row cleanly distinguishes:
    - Component Tolerance: actual manufacturer component tolerance (e.g. +/-1.0%, +/-5.0%)
    - Design / MC Tolerance: tolerance assumed in Monte Carlo / design specifications
    """
    bom_rows = []
    item_num = 1

    # Add passive components
    for ref_des, val in components.items():
        val_f = float(val)
        is_resistor = ref_des.startswith("R")
        req_tol = float(r_tol) if is_resistor else float(c_tol)
        cat_match = find_verified_component(ref_des, val_f, tol=req_tol)
        val_str = format_eng_unit(val_f, " Ohm") if is_resistor else format_eng_unit(val_f, "F")
        design_tol_str = f"+/-{req_tol:.1f}%"
        actual_tol_str = cat_match["tolerance"]

        bom_rows.append(BOMRow({
            "Item": item_num,
            "RefDes": ref_des,
            "Value": val_str,
            "Component Tolerance": actual_tol_str,
            "Design / MC Tolerance": design_tol_str,
            "Rating": cat_match["rating"],
            "Package": cat_match["package"],
            "Manufacturer": cat_match["mfr"],
            "Manufacturer Part Number": cat_match["mpn"],
            "Description": cat_match["description"],
            "Datasheet / Reference": cat_match["ref"],
            "Est. Unit Cost (USD)": cat_match["cost"]
        }))
        item_num += 1

    # Add active op-amps for active topologies
    if "sallen_key" in topology_type.lower() or "mfb" in topology_type.lower() or "cascade" in topology_type.lower():
        num_opamps = 2 if "cascade" in topology_type.lower() else 1
        ref_opamp = "U1, U2" if num_opamps == 2 else "U1"
        info = find_verified_component("U1", "OPA1678")
        bom_rows.append(BOMRow({
            "Item": item_num,
            "RefDes": ref_opamp,
            "Value": "OPA1678",
            "Component Tolerance": "N/A",
            "Design / MC Tolerance": "N/A",
            "Rating": info["rating"],
            "Package": info["package"],
            "Manufacturer": info["mfr"],
            "Manufacturer Part Number": info["mpn"],
            "Description": info["description"],
            "Datasheet / Reference": info["ref"],
            "Est. Unit Cost (USD)": info["cost"]
        }))

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
        f"(export (version D) (design (source \"AnalogFilterSynthesis\") (tool \"Analog-Filter-Synthesizer\"))",
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
