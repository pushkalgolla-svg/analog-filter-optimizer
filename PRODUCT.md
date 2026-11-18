# Product Brief: Analog Filter Synthesizer & SPICE Verification Studio

## 1. Problem & Mission
Designing analog active and passive filters requires navigating complex mathematical transfer functions, continuous pole-placement optimization, and immediate discretization to commercial EIA standard component values (E12, E24, E96). Furthermore, real-world operational amplifiers introduce finite gain-bandwidth products, input capacitance, and phase delay that cause significant deviations from textbook models.

The **Analog Filter Synthesizer Studio** automates this end-to-end workflow:
1. Translates high-level filter specifications (response type, cutoff frequency, Q factor) into optimal component values.
2. Closes the loop using continuous numerical optimization with genuine SPICE simulations (`ngspice`).
3. Snaps continuous values to standard commercial passive components.
4. Validates manufacturing yield through Monte Carlo tolerance simulations.
5. Generates production-ready KiCad 8 schematic netlists and structured Bills of Materials (BOM).

## 2. Target Users & Operating Mode
* **Users**: Hardware engineers, analog circuit designers, electrical engineering educators, and EDA software architects.
* **Surface Mode**: **Operate** (Engineering instrument dashboard).
* **Key User Values**: Technical precision, scanability, visual clarity under dense data conditions, zero ambiguity in component ratings and tolerances.

## 3. Supported Filter Topologies
1. **1st-Order Passive RC Low-Pass Filter** ($-20\,\text{dB/dec}$)
2. **2nd-Order Active Sallen-Key Low-Pass Filter** ($-40\,\text{dB/dec}$, Butterworth maximally flat $Q = 0.7071$)
3. **2nd-Order Active Sallen-Key High-Pass Filter** ($+40\,\text{dB/dec}$, Butterworth maximally flat $Q = 0.7071$)
4. **2nd-Order Active Multiple-Feedback (MFB) Band-Pass Filter** (Controllable $f_0$, $Q$, bandwidth)
5. **4th-Order Cascaded Sallen-Key Low-Pass Filter** ($-80\,\text{dB/dec}$, $Q_1 = 0.5412$, $Q_2 = 1.3065$)

## 4. Hardware & Simulation Constraints
* **Operational Amplifier**: Genuine Texas Instruments OPA1678 PSpice macro-model (Rev E, May 2021) in SOIC-8 packaging, with idealized VCVS fallback ($A_{OL} = 100{,}000$).
* **Power Supply**: Symmetrical dual-rail $\pm 15.0\,\text{V}$ with dedicated $100\,\text{nF}$ supply decoupling capacitors (`C_DEC1`, `C_DEC2`).
* **External Connectivity**: Standardized pin headers for input (`J_IN`), output (`J_OUT`), and active power (`J_PWR`).
* **Simulation Workspace**: Strict multi-user session isolation with sandboxed execution directories.
