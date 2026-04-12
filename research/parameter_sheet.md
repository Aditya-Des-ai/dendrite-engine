# Parameter Sheet — Dendrite Engine
## Research Team Deliverable

Every entry requires: the value, the unit, the paper/source title, and a DOI or URL.
No value without a source. Priorities 1, 2, 3 must be completed before Day 3.
Everything else by Day 5.

---

## Constants You Do NOT Need to Research
These are either universal physical constants or values computed by the Tech Lead.
Do not spend time on these.

| Constant | Symbol | Value | Reason |
|---|---|---|---|
| Boltzmann constant | k_B | 1.380×10⁻²³ J/K | Universal constant |
| Elementary charge | e | 1.602×10⁻¹⁹ C | Universal constant |
| Gas constant | R | 8.314 J/mol·K | Universal constant |
| Faraday constant | F | 96,485 C/mol | Universal constant |
| Charge number of Li⁺ | z | 1 | Always 1 for lithium |
| Molar volume of lithium | Vm | 1.3×10⁻⁵ m³/mol | Computed from density (534 kg/m³) and atomic mass (6.941 g/mol) |
| Absolute temperature | T | — | Computed per-cell from temperature field |
| Applied voltage | V_applied | — | Set by user via charge rate slider |

---

## Priority 1 — Simulation Blocker

| Parameter | Symbol | Unit | Target Range | Search Terms | Value | Source | DOI/URL | Status |
|---|---|---|---|---|---|---|---|---|
| Li⁺ diffusion coefficient in LiPF6 EC:DMC electrolyte at 25°C | D₀ | m²/s | 10⁻¹⁰ to 10⁻⁹ | "lithium ion diffusion coefficient LiPF6 EC DMC" | ~2.6 × 10⁻¹⁰ m²/s at 1 M, 25°C (interpolated estimate); Landesfeind & Gasteiger directly measured range for EC:DMC (1:1 w:w): ~2.3–7.4 × 10⁻¹⁰ m²/s across −7.5°C to +50°C at 0.1 M | Landesfeind & Gasteiger (2019) — binary diffusion coefficient measured directly for 1 M LiPF6 in EC:DMC (1:1 w:w) across concentrations and temperatures. Lundgren et al. (2015) used EC:DEC (not EC:DMC) — values are proxies only. Valøen & Reimers (2005) measured LiPF6 in PC/EC/DMC mixture. | 10.1149/2.0571912jes (Landesfeind & Gasteiger 2019); 10.1149/2.0641503jes (Lundgren 2015, EC:DEC proxy); 10.1149/1.1872737 (Valøen & Reimers 2005) | ⬜ |

---

## Priority 2 — Calibration Blockers
Find all three together — they are in the same datasheet.

| Parameter | Symbol | Unit | Target Range | Search Terms | Value | Source | DOI/URL | Status |
|---|---|---|---|---|---|---|---|---|
| Anode surface area of target cell | A | mm² | — | "LG M50 INR21700 datasheet teardown" |87,200 |  teardown of LG M50 21700; anode strip length ≈ 720 mm, width ≈ 60.8 mm → geometric area ≈ 872 cm² per face. Confirmed in O'Regan et al., Electrochimica Acta 425 (2022) parameter set| O'Regan et al., Electrochimica Acta 425 (2022) parameter set.| ⬜ |
| Fast charge current | I_fast | A | — | "LG M50 INR21700 datasheet" |3.395 A(= 0.7C at 25–50 °C) | LG Chem official datasheet LRB-PS-CY18.2Wh-M50 — "Max. ChargeCurrent 25–50 °C: 0.7C (3,395 mA) |DNKPower.com / batteryspace.com. | ⬜ |
| Slow charge current (standard) | I_slow | A | — | "LG M50 INR21700 datasheet" | 1.455 A(= 0.3C)| LG Chem official datasheet LRB-PS-CY18.2Wh-M50 | LG M50T datasheet (2018) and multiple teardown reviews. | ⬜ |

---

## Priority 3 — Validation Benchmark

| Parameter | Symbol | Unit | Target Range | Search Terms | Value | Source | DOI/URL | Status |
|---|---|---|---|---|---|---|---|---|
| Cycle life to 80% capacity retention | N_rated | cycles | 300–800 | "LG M50 cycle life capacity retention" |300 cycles, 500 cycles at C/3 charge and C/3 discharge between 4.2V and 2.85V |LG Energy Solution INR21700 M50 Datasheet |https://www.dnkpower.com/wp-content/uploads/2019/02/LG-INR21700-M50-Datasheet.pdf | ⬜ |

---

## Priority 4 — Alpha Calculation Constants
These four values feed directly into the ΔG_act formula that computes
sticking probability per cell. All four must come from the same electrolyte
system (LiPF6 EC:DMC) and the same anode material (graphite) for consistency.

The formula they feed into:

    ΔG_act = ΔG° + (γ × Vm × κ) + (β × z × e × η)
    α      = exp( −ΔG_act / (R × T) )

Where κ (curvature) is computed by the simulation from grid geometry,
η (overpotential) is computed from the solved potential field,
and everything else in the formula is either a universal constant or from this table.

| Parameter | Symbol | Unit | Target Range | Search Terms | Value | Source | DOI/URL | Status |
|---|---|---|---|---|---|---|---|---|
| Standard activation energy for Li deposition on graphite | ΔG° | J/mol | 30,000–60,000 | "activation energy lithium deposition graphite electrochemical"|~47,500(≈47.5 kJ/mol)|Jow et al., J. Electrochem. Soc. 2018; Colclasure et al., J. Electrochem. Soc. 2020 d. | | ⬜ |
| Surface tension of lithium metal at electrolyte interface | γ | J/m² | 0.3–0.6 | "surface energy lithium metal electrolyte interface electrodeposition" |0.45 |Ely & Garcia, J. Electrochem. Soc. 2013 (classical nucleation model for Li); surface-energy values for Li metal at liquid-electrolyte interface reported in range 0.40–0.53 J/m². Mid-value 0.45 recommended.| | ⬜ |
| Symmetry factor (anodic transfer coefficient) | β (αₐ) | — | 0.3–0.7 | "Butler-Volmer transfer coefficient lithium deposition graphite" |0.5|Standard assumption for single-electron Li⁺/Li redox (Doyle-Fuller-Newman model); validated for graphite in LiPF6/EC:DMC by Ganser et al., JOM 2023 and Butler-Volmer analyses in ScienceDirect Topics. β = 0.5 reflects symmetric energy barrier. | | ⬜ |
| Equilibrium electrode potential of lithium vs SHE | φ_eq | V | −3.04 | "lithium standard electrode potential equilibrium" | −3.040| IUPAC standard reduction potential for Li⁺/Li vs SHE. Confirmed in multiple sources including lithiophilic-materials review (OAE Publishing 2023).|standard electrochemistry references. Value: −3.040 V ± 0.001 V. | ⬜ |

---

## Priority 5 — Butler-Volmer Supporting Constants
Used to validate the alpha values computed above and to cross-check
that the Butler-Volmer current matches expected deposition rates.

| Parameter | Symbol | Unit | Target Range | Search Terms | Value | Source | DOI/URL | Status |
|---|---|---|---|---|---|---|---|---|
| Exchange current density at graphite anode | i₀ | A/m² | — | "Butler-Volmer exchange current density lithium graphite anode" | 0.1 A/m²| Modeling of Galvanostatic Charge and Discharge of the Lithium/Polymer/Insertion Cell| https://doi.org/10.1149/1.2221597| ⬜ |
| Cathodic transfer coefficient | αc | — | ~0.5 | "Butler-Volmer transfer coefficient lithium deposition" | | | | ⬜ |
| Cathodic transfer coefficient | αc | — | ~0.5 | "Butler-Volmer transfer coefficient lithium deposition" | 0.5| Modeling of Galvanostatic Charge and Discharge of the Lithium/Polymer/Insertion Cell|https://doi.org/10.1149/1.2221597 | ⬜ |

---

## Priority 6 — Temperature Physics

| Parameter | Symbol | Unit | Target Range | Search Terms | Value | Source | DOI/URL | Status |
|---|---|---|---|---|---|---|---|---|
| Activation energy for Li⁺ diffusion (Arrhenius) | Eₐ | kJ/mol | 15–30 | "activation energy Li diffusion electrolyte Arrhenius" |26.1 kJ/mol |Determination of the Solid-State Diffusion Coefficient of Lithium in Graphite| [https://doi.org/10.1016/j.jpowsour.2020.228659](https://doi.org/10.1149/1.1838036)| ⬜ |
| Internal temperature rise during fast charge | ΔT | °C | 3–8 | "battery internal temperature fast charging thermal imaging" | 4.8 °C|Thermal behavior of cylindrical lithium-ion batteries during fast charging|[https://doi.org/10.1016/j.jpowsour.2020.228659](https://doi.org/10.1016/j.jpowsour.2013.06.040) | ⬜ |

---

## Priority 7 — Degradation Dynamics

| Parameter | Symbol | Unit | Target Range | Search Terms | Value | Source | DOI/URL | Status |
|---|---|---|---|---|---|---|---|---|
| Electrolyte degradation rate per cycle | k_deg | per cycle | 0.001–0.005 | "electrolyte degradation rate capacity fade lithium ion cycle" | 0.0022| Development of Experimental Techniques for Parameterization of Multi-scale Li-ion Battery Models| 10.1149/1945-7111/ab9050| ⬜ |
| Current density edge enhancement factor | f_edge | — | 1.1–1.4 | "current distribution non-uniformity lithium ion anode edge" |1.35 | Impact of Non-uniform Current Distribution on Lithium Plating in Cylindrical Cells|10.1016/j.jpowsour.2021.230044 | ⬜ |

---

## Priority 8 — Separator Physics

| Parameter | Symbol | Unit | Target Range | Search Terms | Value | Source | DOI/URL | Status |
|---|---|---|---|---|---|---|---|---|
| Separator porosity resistance factor | f_sep | — | 0.3–0.7 | "separator porosity resistance lithium ion dendrite growth" | 0.4| Development of Experimental Techniques for Parameterization of Multi-scale Li-ion Battery Models|10.1149/1945-7111/ab9050| ⬜ |

---

## Priority 9 — Report Evidence
No code impact. For the written report and presentation only.

| Parameter | Symbol | Unit | Notes | Search Terms | Found | Source | DOI/URL | Status |
|---|---|---|---|---|---|---|---|---|
| SEM images of Li dendrites on graphite anode | — | — | Cross-section images from fast-charge abuse studies | "lithium dendrite SEM graphite anode fast charge" |Observed @ 1C+ charging |A Physical, Chemical, and Electrochemical Analysis... (Stapf et al.)|10.1149/1945-7111/ac0f49 | ⬜ |
| Electrolyte ionic conductivity vs temperature | σ(T) | S/m | Table or graph preferred | "LiPF6 EC DMC conductivity temperature dependence" |0.84 (@ 25°C) |Thermal-electrochemical parameters... (Schmitt et al.) |10.1016/j.electacta.2022.140700 | ⬜ |

---

## How to Fill This In

1. Find the value from a published paper or official manufacturer datasheet
2. Write the exact numeric value and unit in the Value column
3. Write the paper title or datasheet name in the Source column
4. Paste the DOI (e.g. `10.1016/j.electacta.2019.xx`) or full URL in the DOI/URL column
5. Change ⬜ to ✅ when complete

---

## Target Cell

**LG M50 INR21700** — used in Tesla Model 3 long range pack.
Well-documented in public literature and third-party teardown studies.
All Priority 2 parameters should come from the same source for consistency.

---

## Notes for the Research Team

- D₀ varies with temperature. Find the value at 25°C specifically.
- I_fast and I_slow are in Amperes for the full cell, not current density.
  The Tech Lead will convert to current density using anode surface area.
- For Priority 4, try to find ΔG° and γ from the same paper or the same
  electrolyte system. Mixing values from different systems introduces
  inconsistency into the alpha calculation.
- β and αₐ are the same thing — different papers use different notation.
  If a paper reports αₐ ≈ 0.5, that is your β value.
- φ_eq for lithium is well-established at −3.04 V vs SHE. If you find a
  paper that reports a slightly different value for a specific electrolyte
  system, use that more specific value and cite it.
- For Butler-Volmer (Priority 5), the same paper will usually report
  i₀, αₐ, and αc together. Find one good source for all three.
- SEM images do not need a numeric value — just a citable source
  with a figure we can reference in the report.
