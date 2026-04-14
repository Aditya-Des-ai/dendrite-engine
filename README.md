# Dendrite Physics Engine
### A Lithium-Ion Battery Degradation Simulator
First-Year Engineering Chemistry Group Project 

---

## What This Is

This is a GPU-accelerated computational physics engine that simulates **dendrite growth** inside lithium-ion battery cells — the primary physical mechanism responsible for battery degradation and thermal runaway (fire) in electric vehicles.

It is not a toy visualizer. The core algorithm (Diffusion-Limited Aggregation) is the same class of model used in real materials science research. Every physical factor modeled here maps to a real electrochemical phenomenon, derived from first principles and calibrated against published literature for a specific commercial cell (LG M50 INR21700, used in the Tesla Model 3 long range pack).

The simplifications made are deliberate, documented, and scientifically justified. This document explains all of them.

---

## The Problem Being Solved

During charging, lithium ions travel from the cathode through liquid electrolyte and deposit onto the graphite anode. Under ideal conditions this is smooth and uniform. Under stress — fast charging, elevated temperature, aged electrolyte — deposition becomes uneven and lithium begins forming **dendrites**: needle-like crystal structures that grow upward from the anode toward the cathode.

Two failure modes result:

1. **Capacity fade** — dendrites trap lithium in unusable crystal structures, permanently reducing available capacity
2. **Short circuit** — if a dendrite bridges the full anode-to-cathode gap, a direct electrical short forms, generating rapid heat and potential thermal runaway

This simulation models the electrolyte space where this occurs, predicts dendrite growth trajectory under parameterized operating conditions, and outputs industry-relevant risk metrics.

**The core scientific question this simulation answers:**

> *Under equivalent initial battery conditions, how many more safe charge cycles does slow charging provide compared to fast charging, and where on the anode does degradation concentrate?*

---

## What Is Being Simulated

A **2D cross-section of the liquid electrolyte gap** in a lithium-ion cell, viewed from the side.

```
TOP:    ══════════════════════════════════════════════
        [ cathode boundary — ion source             ]
        [                                           ]
        [  separator zone (porosity resistance)    ]
        [                                           ]
        [        electrolyte space                 ]
        [     THIS IS THE SIMULATION GRID          ]
        [                                           ]
        [ dendrite growth zone                     ]
BOTTOM: ══════════════════════════════════════════════
        [ graphite anode surface — seed row        ]
```

The cathode is a boundary condition, not a simulated object. The anode bulk is not simulated. The simulation domain is exclusively the electrolyte gap — the space where dendrites form, grow, and eventually cause failure.

**Cell type:** Lithium-ion with liquid electrolyte (1M LiPF6 in EC:DMC).
This is NOT a solid-state battery simulation. DLA models diffusion through liquid media. Solid-state dendrite propagation is crack mechanics in a rigid lattice — a different physical regime entirely.

---

## Complete Physics Model

Every factor below is implemented in the simulation engine. Each maps directly to a real physical mechanism.

### Factor 1 — Diffusion-Limited Aggregation (Core Algorithm)

Each lithium ion is modeled as a random-walking particle (Brownian motion). At each timestep it moves to a random adjacent cell. When it lands adjacent to an existing solid cell, it has probability α of depositing permanently. This is DLA — the same algorithm used in peer-reviewed electrodeposition modeling.

The branching fractal structure is not programmed. It emerges from geometry: dendrite tips intercept more random walkers than valleys, so tips grow faster. This produces needle-like morphology consistent with published SEM cross-sections.

### Factor 2 — Sticking Probability α (Full Electrochemical Derivation)

Alpha is not a tuning knob. It is derived per-cell from first principles via:

```
ΔG_act = ΔG° + (γ × Vm × κ) + (β × z × e × η)
α      = exp(−ΔG_act / (R × T))
```

| Symbol | Meaning | Source |
|---|---|---|
| ΔG° | Standard activation energy for Li deposition on graphite | Literature |
| γ | Surface tension of lithium at electrolyte interface | Literature |
| Vm | Molar volume of lithium (1.3×10⁻⁵ m³/mol) | Computed from density |
| κ | Local surface curvature | Computed from grid geometry |
| β | Symmetry factor (anodic transfer coefficient) | Literature |
| z | Charge number of Li⁺ (always 1) | Known |
| e | Elementary charge (1.602×10⁻¹⁹ C) | Known |
| η | Local overpotential = φ_local − φ_eq | Computed from Laplace solver |
| R | Gas constant (8.314 J/mol·K) | Known |
| T | Local temperature in Kelvin | Computed from temperature field |

### Factor 3 — Electric Potential Field (Laplace Solver)

The electric potential field φ(x,y) is solved at every cycle using a Jacobi iterative solver on the GPU:

```
∇²φ = 0
```

Boundary conditions: anode surface = fixed low potential, cathode boundary = fixed high potential, dendrite surface = equipotential conductor (updated each cycle as dendrite grows).

Local current density at each interface cell: `J = −σ × ∇φ`

This field drives ion migration toward the anode and creates the electric field screening effect — tall dendrite tips sit in a region of higher potential gradient, giving them higher local overpotential η and therefore higher α. This is the key feedback mechanism causing non-linear growth acceleration. It is solved automatically by re-applying boundary conditions each cycle.

The solver runs 30 Jacobi iterations per timestep (lagged potential approximation) — physically justified because the grid changes slowly between timesteps. Full convergence at 100–200 iterations would be 5× slower with negligible accuracy gain.

### Factor 4 — Surface Curvature and Gibbs-Thomson Effect

Sharp dendrite tips have high positive curvature (large κ). Via the Gibbs-Thomson term (γ × Vm × κ) in the ΔG_act formula, high curvature lowers the local equilibrium potential, increasing the effective overpotential, increasing α at tips. This is the self-reinforcing mechanism that makes tips grow faster than flat surfaces.

The same effect correctly slows growth when dendrites enter separator pores — high curvature in a narrow pore raises ΔG_act, reducing α. No separate mechanical model needed.

Curvature is computed from grid geometry at each interface cell:

```
κ = (4.0 − solid_neighbor_count) / (4.0 × dx_physical)
```

Where `dx_physical` = anode_width_meters / W. No external constant needed.

### Factor 5 — Temperature Field and Arrhenius Diffusion Scaling

A 2D temperature field T(x,y) is initialized as a Gaussian hot-center profile — physically consistent with real battery thermal maps where internal resistance heating concentrates in the cell center.

Diffusion rate at each cell scales via Arrhenius:

```
diffusion_rate(x,y) = D₀ × exp(−Eₐ / (R × T(x,y)))
```

Hotter cells: particles take more random walk steps per timestep. Cooler cells: fewer steps. This produces spatially non-uniform dendrite growth concentrated in the hot zone — the primary driver of the spatial degradation patterns visible in the anode profile charts.

### Factor 6 — Ion Concentration Field and Mass Transport

A 2D concentration field C(x,y) is initialized at bulk electrolyte concentration C₀. Every deposition event depletes C in a radius around that cell proportional to the diffusion length scale. Between timesteps, bulk diffusion slowly replenishes the field.

This models the mass transport limitation: fast-growing dendrite tips deplete the local ion supply, reducing the effective particle arrival rate at those cells. Without this, pure DLA overestimates tip growth speed in the post-depletion regime.

### Factor 7 — Separator Geometry and Transport Resistance

The separator is modeled as two effects:

**Transport resistance:** Above a defined y-coordinate threshold (top 15% of grid), particle diffusion rate is multiplied by `f_sep` (separator porosity factor, 0.1–1.0). Ions slow down in this zone.

**Pore entry resistance:** Dendrites entering the separator zone have very high curvature (narrow pore = small radius = large κ), which via Gibbs-Thomson raises ΔG_act and reduces α. Growth slows automatically — no separate mechanical model needed.

The separator is also a hard boundary condition in the Laplace solver, changing the potential field structure above the threshold height.

### Factor 8 — Nucleation Site Heterogeneity

The anode seed row is not initialized as a perfectly flat line. It is initialized with random surface protrusions of 2–5 cells height at random x-positions, with density controlled by `seed_roughness` (0.0–1.0). This models real anode surface defects where dendrites preferentially nucleate.

Low roughness: sparse, widely spaced, tall dendrites. High roughness: dense, shorter, broader growth. Consistent with published literature on anode surface preparation effects.

### Factor 9 — Charge Rate and Faraday's Law Calibration

Particle injection rate is derived from real current density:

```
particles_per_cycle = (I × A_cell × t_charge) / (n × F × A_grid_cell)
```

Where I is current density (A/m²), A_cell is real anode area, t_charge is charge duration, n=1 for Li⁺, F is Faraday's constant, and A_grid_cell is the physical area of one grid cell.

Fast charge (15 min) and slow charge (60 min) modes use manufacturer-specified currents for the LG M50 INR21700 target cell.

### Factor 10 — Edge Current Enhancement

Current density is not perfectly uniform across the anode — it is higher at the edges due to geometric effects. The injection rate at the left and right 10% of grid columns is multiplied by `f_edge` (1.0–2.0). This produces the edge-concentrated degradation visible in the spatial profile charts.

### Factor 11 — Electrolyte Degradation Over Cycles

At the end of each cycle:

```
alpha_effective += k_deg × cycle_number
C_bulk         *= (1 − k_deg)
```

This makes battery aging emergent — a simulation starting at fresh parameters will naturally transition to degraded behavior over hundreds of cycles. The four age presets (Fresh / Slightly Used / Moderately Used / Heavily Degraded) represent different starting points on this trajectory.

### Factor 12 — Sand's Time (Branching Onset Criterion)

Sand's equation predicts the time at which local ion concentration at the electrode surface drops to zero — the point at which diffusion-layer depletion makes branched dendrite growth inevitable:

```
τ_Sand = π × D₀ × (z × F × C₀)² / (4 × (J − J_lim)²)
```

Computed analytically at simulation initialization for current operating parameters. Before τ_Sand: deposition is orderly, single-needle morphology. After τ_Sand: concentration-depleted regime, branching is inevitable.

The simulation switches behavior at the Sand's Time crossing. This crossing cycle is a primary output metric. Sand's Time also generates Chart 8 — the 2D heatmap of which charge rate × temperature combinations cause branching. This is the most directly actionable engineering output in the dashboard.

### Factor 13 — SEI Layer (Reduced Order Model)

The Solid Electrolyte Interphase is modeled using a parabolic growth law — the standard reduced-order approach in battery modeling literature:

```
L_SEI(N) = L₀ × √N × exp(−E_SEI / (R × T))
```

This captures self-limiting growth, temperature dependence, and cycle-number dependence — without requiring the full 6–12 coupled reaction system of a first-principles SEI model.

Two corrections feed into the simulation each cycle:

**Interfacial resistance:**
```
R_SEI = L_SEI / σ_SEI
η_eff = η − (J_local × R_SEI)
```

**Lithium inventory loss:**
```
effective_injection_rate = base_rate × (1 − k_SEI × L_SEI)
```

SEI_thickness[x,y] is a 2D field updated once per cycle. Its spatial distribution mirrors the temperature field — hotter zones grow SEI faster. SEI contributes to capacity fade independently of dendrite growth — a critical distinction for accurate cycle-life prediction.

---

## Complete Factor Summary

| Factor | Implementation | Physics Mechanism |
|---|---|---|
| Ion diffusion rate | Random walk step count via D₀ + Arrhenius | Brownian motion of Li⁺ in electrolyte |
| Temperature spatial variation | Gaussian field, Arrhenius scaling | Internal resistance heating |
| Sticking probability α | ΔG_act formula → Arrhenius | Butler-Volmer electrodeposition kinetics |
| Surface curvature (Gibbs-Thomson) | Neighbor count → κ → ΔG_act correction | Surface energy advantage at sharp tips |
| Electric potential field | Laplace solver, Jacobi iteration, GPU | Electrostatic driving force on ions |
| Local overpotential | φ_local − φ_eq from potential field | Thermodynamic driving force for deposition |
| Electric field screening | Laplace BCs updated each cycle | Tall tips sit in higher field gradient |
| Ion concentration depletion | concentration_field, depletes on deposit | Mass transport limitation near tips |
| Separator transport resistance | Diffusion rate × f_sep above threshold | Pore tortuosity slows ion transport |
| Separator pore entry resistance | Curvature term in ΔG_act (automatic) | High κ in narrow pore raises ΔG_act |
| Nucleation heterogeneity | Non-uniform seed row initialization | Real anode surface defects |
| Electrolyte degradation | k_deg raises α, lowers C_bulk per cycle | Electrolyte decomposition over cycles |
| Charge rate | Particle injection via Faraday's Law | Applied current density |
| Edge current enhancement | f_edge multiplier at anode boundaries | Geometric current non-uniformity |
| Battery age preset | Parameter bundle (α, temp, k_deg, etc.) | Cumulative prior damage state |
| SEI growth (reduced order) | Parabolic law L_SEI = L₀√N × Arrhenius | Electrolyte reduction at anode interface |
| SEI interfacial resistance | R_SEI = L_SEI / σ_SEI → corrects η | Ion tunneling resistance through SEI |
| SEI lithium consumption | Loss fraction reduces injection rate | Irreversible Li⁺ consumed by SEI |
| Sand's Time branching threshold | Analytical formula, switches regime | Diffusion layer depletion → branching |

---

## What This Simulation Cannot Model

These are deliberate scope exclusions, not oversights.

| Limitation | Why Excluded |
|---|---|
| Full SEI chemistry (6–12 coupled reactions) | Requires a second complete simulation engine. Reduced order model used instead. |
| Mechanical stress and anode expansion | Requires Finite Element Analysis — entirely different mathematical framework. |
| 3D volumetric dendrite structure | 200× memory increase, different renderer, different analysis. 2D matches published SEM morphology adequately. |
| Full Nernst-Planck ion transport (convection term) | Requires coupled PDE system. DLA with concentration field captures diffusion and migration adequately at this scale. |
| Solid-state electrolyte dendrite propagation | DLA is invalid for crack-mechanics-driven growth in rigid ceramic lattices. |
| Absolute time predictions with high precision | D₀ calibration uncertainty propagates linearly. Relative comparisons are robust; absolute numbers carry documented uncertainty. |
| Post-short-circuit thermal behavior | Thermal runaway modeling requires thermodynamic + fluid dynamics coupling. |

---

## Inputs

| Parameter | Symbol | Physical Meaning | Source |
|---|---|---|---|
| Sticking probability | α | Baseline deposition aggressiveness | ΔG_act formula |
| Charge rate | — | Particle injection rate | Faraday's Law + datasheet |
| Temperature gradient | — | Spatial heat distribution intensity | Published thermal maps |
| Number of cycles | N | Charge events to simulate | User-defined |
| Ensemble runs | — | Repeated runs for statistical averaging | Default: 50 |
| Degradation rate | k_deg | Electrolyte decay per cycle | Literature |
| Separator factor | f_sep | Pore resistance to ion transport | Literature |
| Edge enhancement | f_edge | Current non-uniformity at edges | Literature |
| Seed roughness | — | Anode surface defect density | User-defined |
| SEI growth rate | — | SEI thickening speed | Literature |
| Battery age preset | — | Fresh / Slight / Moderate / Degraded | Calibrated bundle |

---

## Outputs

| Output | Physical Meaning | Application |
|---|---|---|
| Live dendrite visualization | Real-time GPU-rendered crystal growth | Demonstration |
| Max dendrite height per cycle | Growth trajectory — primary time series | All quantitative analysis |
| Short-circuit risk score | (max_height / gap_height) × 100 | BMS lookup table, warranty modeling |
| Ensemble mean spatial profile | Averaged height across anode width | Hotspot identification |
| Fast vs slow charge comparison | Growth rate ratio between strategies | Engineering decision support |
| Ion concentration over cycles | Mean tip concentration — depletion timeline | Mass transport analysis |
| SEI thickness over cycles | Parabolic growth curve per preset | Capacity fade attribution |
| Lithium loss to SEI | Cumulative % of Li⁺ permanently consumed | Separate from dendrite capacity loss |
| Sand's Time crossing cycle | Cycle when branching becomes inevitable | Critical safety threshold |
| Sand's Time heatmap | Charge rate × temperature → branching map | Safe charging operational envelope |
| Spatial snapshots every 10 cycles | Anode state at each checkpoint | Cycle scrubber in dashboard |
| Simulation summary report | Auto-generated plain text | LaTeX report conversion |

---

## Real-World Calibration

### Constants Computed from First Principles (no paper needed)

| Constant | Value | Derivation |
|---|---|---|
| Molar volume of lithium Vm | 1.3×10⁻⁵ m³/mol | Density (534 kg/m³) ÷ atomic mass (6.941 g/mol) |
| Charge number z | 1 | Li⁺ carries one charge |
| Elementary charge e | 1.602×10⁻¹⁹ C | Universal constant |
| Gas constant R | 8.314 J/mol·K | Universal constant |
| Faraday constant F | 96,485 C/mol | Universal constant |
| Grid cell size dx | anode_width_m / W | Derived from anode dimensions |

### Constants Requiring Literature

Full parameter sheet with search terms, target ranges, and status tracking is in `research/parameter_sheet.md`. Priority 1–3 due before Day 3. All others by Day 5. Every entry requires value, unit, paper title, and DOI or URL.

**Target cell:** LG M50 INR21700 — used in Tesla Model 3 long range pack.

---

## Architecture

```
parameters.json
      │
      ▼
core/simulation.py  ←──────────────── core/shared_fields.py
      │                                (all Taichi GPU fields,
      │                                 imported by simulation
      │                                 AND renderer — same GPU memory)
      ├──────────────────────────────────────┐
      ▼                                      ▼
renderer/taichi_renderer.py      data/simulation_output.csv
(reads shared fields live,        (written after each run)
 GPU render pipeline)                        │
                                             ▼
                                   ui/analytics_dashboard.py
                                   (8 charts, export, report)

ui/control_panel.py
      │ writes
      ▼
data/parameters.json  ←── simulation reads this at start of each run
```

The simulation and dashboard are **decoupled through files**. The dashboard reads CSVs. It never imports the simulation. The UI was built and tested against `mock_output.csv` independently and swaps to real output on integration day with zero code changes.

### Parallelization

All computation runs on the RTX 4050 via Taichi CUDA kernels: particle walks, Laplace solver, curvature computation, alpha calculation, concentration depletion, SEI update. Each particle's random walk is fully independent — N particles step simultaneously across GPU cores.

A stale-read buffer (`pending_grid`) prevents race conditions: particles write to a separate array during their step, merged into `grid` once per timestep via vectorized max. Zero computational cost.

**Performance target:** 400×600 grid, 25,000 particles, 30 Laplace iterations per timestep → ~6–7ms per timestep → ~150 timesteps/second → 200-cycle run completes in under 2 minutes.

---

## Renderer Visual Design

The renderer produces a 2D simulation that reads as 3D through five techniques applied in Taichi GGUI:

**Depth color mapping** — crystal base cells are deep blue, tips are white-yellow. Color encodes height as a third visual dimension.

**Ambient occlusion** — buried cells are darker, exposed tips are brighter. Mimics real light behavior on 3D surfaces via 8-neighbor solid count.

**Ion glow** — floating particles rendered as radial light halos using additive blending. Creates the impression of a luminous, active electrolyte medium.

**SEI tint** — interface cells (solid cells adjacent to liquid) tinted golden proportional to local SEI thickness. Makes the invisible SEI layer visible.

**Temperature overlay** — electrolyte background tinted orange-red in hot zones, deep blue in cool zones, without obscuring the crystal.

**HUD** — live cycle count, risk score (green/amber/red), max dendrite height, Sand's Time status (cyan = safe, red = branching active).

---

## Dashboard — Eight Output Charts

| Chart | Content | Key Scientific Output |
|---|---|---|
| 1 | Dendrite growth curves, fast vs slow, all presets | When each scenario crosses short-circuit threshold |
| 2 | Short-circuit risk score over cycles | Risk trajectory per battery age state |
| 3 | Anode spatial profile, height across width | Where on the anode failure concentrates |
| 4 | Cycle-life comparison bar chart | Side-by-side safe cycle count per scenario |
| 5 | Degradation acceleration (rolling derivative) | Non-linear growth acceleration, Sand's Time marker |
| 6 | Ion concentration depletion over cycles | Mass transport limitation timeline |
| 7 | SEI thickness + lithium loss (dual axis) | Capacity fade attribution: SEI vs dendrite |
| 8 | Sand's Time heatmap (charge rate × temperature) | Safe charging operational envelope |

---

## Repository Structure

```
dendrite-engine/
│
├── core/
│   ├── shared_fields.py       # All Taichi GPU fields — defined once, imported by all
│   └── simulation.py          # Full physics engine
│
├── renderer/
│   └── taichi_renderer.py     # GPU renderer — depth color, AO, ion glow, SEI, HUD
│
├── ui/
│   ├── control_panel.py       # 10 sliders, 4 presets, Sand's Time display, run controls
│   └── analytics_dashboard.py # 8 charts, cycle scrubber, export, report generator
│
├── data/
│   ├── parameters.json        # Active simulation config
│   ├── generate_mock.py       # Generates all mock CSVs for UI development
│   ├── mock_output.csv        # 200-cycle synthetic data (27 columns)
│   ├── mock_spatial.csv       # Anode spatial profiles (13 columns)
│   ├── mock_sands_map.csv     # 20×20 Sand's Time heatmap grid
│   └── simulation_output.csv  # Written by simulation after each run
│
├── research/
│   └── parameter_sheet.md     # Physical constants — research team deliverable
│
├── report/
│   ├── findings.md            # Plain-text findings for LaTeX conversion
│   └── simulation_summary.txt # Auto-generated by dashboard after each run
│
├── outputs/                   # PNG chart exports, frame screenshots
└── main.py                    # Entry point — wires all components
```

---

## Getting Started

### Prerequisites

```bash
conda create -n dendrite python=3.11
conda activate dendrite
pip install taichi numpy numba matplotlib pandas scipy
```

### Verify GPU

```bash
python core/shared_fields.py
```

Expected: `[Taichi] Starting on arch=cuda` and all field dimensions printed.

### Generate mock data

```bash
python data/generate_mock.py
```

### Run UI in development mode (no simulation needed)

```bash
python ui/analytics_dashboard.py --mock
python ui/control_panel.py
```

### Run full simulation

```bash
python main.py
```

---

## Team Structure

| Role | Owns | Does NOT touch |
|---|---|---|
| Tech Lead / Architect | `core/`, repo, Notion, LaTeX | Renderer internals |
| Co-Coder | `renderer/taichi_renderer.py` | Simulation physics |
| UI / Visuals | `ui/` | Taichi, core physics |
| Scientific Validator 1 | Parameter sheet, literature sourcing | Code |
| Scientific Validator 2 | Output vs reference comparison, report analysis | Code |
| PPT / Executive Summary | Slide deck, 2-page summary | Code |

---

## Academic Context

Built as a first-year engineering chemistry project in one week. DLA for electrodeposition modeling has direct precedent in peer-reviewed materials science research. The SEI reduced order model follows the parabolic growth law standard in battery modeling literature. Sand's Time is a well-established analytical criterion in electrochemical engineering.

The simulation is an approximation. It is presented as one, documented as one, and should be evaluated as a physically motivated, parameterized model producing comparative predictions with clearly bounded uncertainty — not a replacement for experimental characterization or industrial battery modeling software.

The core defensible scientific result is the **ratio** of fast-charge to slow-charge cycle life under equivalent initial conditions. All other outputs are supporting evidence for this primary finding.

---

*Python + Taichi. RTX 4050. Six people. One week.*
