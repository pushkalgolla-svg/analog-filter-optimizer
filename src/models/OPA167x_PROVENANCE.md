# Texas Instruments OPA167x Macro-Model Provenance & SPICE Specification

## 1. Component & Vendor Identification
- **Manufacturer**: Texas Instruments Incorporated
- **Device Family**: OPA1678 (Dual), OPA1677 (Single), OPA1679 (Quad) SoundPlus™ Low-Distortion, Low-Noise Audio Operational Amplifiers
- **Official Product Page**: [https://www.ti.com/product/OPA1678](https://www.ti.com/product/OPA1678)
- **Official Datasheet**: [https://www.ti.com/lit/ds/symlink/opa1678.pdf](https://www.ti.com/lit/ds/symlink/opa1678.pdf) (Document: `SBOS855D`, Revised December 2021)
- **Vendor Model Identifier**: `SBOMAC3`
- **Vendor Source Download URL**: [https://www.ti.com/lit/zip/sbomac3](https://www.ti.com/lit/zip/sbomac3)

---

## 2. Model File Details
- **File Name**: `OPA167x.LIB`
- **Model Revision**: Final 1.7 (Release Date: 24-AUG-2022)
- **File Size**: 16,754 bytes
- **SHA-256 Checksum**: `a4a2f63b714c799bd4ccbf52fa71922d2786f93fcdfcc10f0b11377194beef77`
- **Architecture**: Green-Williams-Lis Op Amp Macro-model Architecture
- **Origin**: Unmodified vendor library extracted directly from Texas Instruments' official `sbomac3.zip` distribution.

---

## 3. Subcircuit Interface & Pin Assignment
```spice
.SUBCKT OPA167x IN+ IN- VCC VEE OUT
```
| Subcircuit Pin | Function | Description | Physical Package Pin (OPA1678 SOIC-8 Unit A) | Physical Package Pin (OPA1678 SOIC-8 Unit B) |
| :---: | :---: | :--- | :---: | :---: |
| **IN+** | Non-Inverting Input | Positive differential input | Pin 3 (`+IN A`) | Pin 5 (`+IN B`) |
| **IN-** | Inverting Input | Negative differential input | Pin 2 (`-IN A`) | Pin 6 (`-IN B`) |
| **VCC** | Positive Supply Rail | Operational range: $+2.25\text{ V}$ to $+18\text{ V}$ (referenced to midpoint) | Pin 8 (`V+`) | Pin 8 (`V+`) |
| **VEE** | Negative Supply Rail | Operational range: $-2.25\text{ V}$ to $-18\text{ V}$ (referenced to midpoint) | Pin 4 (`V-`) | Pin 4 (`V-`) |
| **OUT** | Amplifier Output | Single-ended analog output | Pin 1 (`OUT A`) | Pin 7 (`OUT B`) |

---

## 4. ngspice Compatibility & Execution Strategy
The official OPA167x macro-model is authored for Cadence PSpice / TINA-TI and incorporates:
1. Voltage-controlled switches with `VSWITCH` model definitions.
2. Ternary conditional expressions `IF(condition, true_val, false_val)`.
3. Arithmetic evaluation in curly braces `{...}`.

### Compatibility Implementation
ngspice natively executes the OPA167x macro-model **without any syntax modifications to the vendor file** when PSpice/LTspice compatibility mode is enabled:
```spice
* ngspice configuration (.spiceinit or initialization block)
set ngbehavior=pslt
```
In this mode:
- ngspice translates PSpice `VSWITCH` syntax to internal voltage-controlled switches.
- ngspice enables PSpice `IF(...)` evaluation functions.
- Global parameter `TEMP` is resolved accurately at $27^\circ\text{C}$ (300.15 K).

---

## 5. Recommended Operating Conditions & Supply Configuration
Per the Texas Instruments OPA1678 datasheet:
- **Recommended Supply Range**: Dual supply $\pm 2.25\text{ V}$ to $\pm 18\text{ V}$ (or single supply $+4.5\text{ V}$ to $+36\text{ V}$).
- **Default System Configuration**: Balanced dual supply $\mathbf{\pm 15.0\text{ V}}$ ($V_{CC} = +15\text{ V}$, $V_{EE} = -15\text{ V}$). This is the industry-standard rail voltage for high-fidelity audio signal processing, ensuring $> 28\text{ V}_{p-p}$ output dynamic range without rail clipping.
- **Supply Decoupling**: High-frequency ceramic decoupling capacitors ($0.1\ \mu\text{F} / 100\text{ nF}$, $50\text{ V}$, X7R, 0805 SMD) must be placed between $V_{CC}$ and $GND$, and between $V_{EE}$ and $GND$, immediately adjacent to pins 8 and 4.
