# Engineering model and validation contract

## Current drawing-based model (annotated-v2)

The corrected KPAU/EAF/FCU/transfer identities from the user-annotated crop are implemented in a separate geometry version. See [layout review](LAYOUT_REVIEW.md) for registration, dimensions, opening assumptions and unresolved hood positions. Area is unchanged; provisional dimensions are 8.30 × 4.8746988 × 2.9 m. The upper-wall transfer grille replaces the earlier west-wall doorway. Four FCU supply locations and two returns are registered; FCU physics remain local sensible/momentum actuators, with each unit's UA divided between its two supply regions. Grille/body markers above the false ceiling do not add occupied CFD volume.

Numerical criteria below are unchanged. The old reference cases are historical provisional-v1 results, not a validation of the new layout.

## Earlier domain and provisional layout (provisional-v1)

Coordinates are metres: X = 0–7.00, Y = 0–5.78, Z = 0–2.90. Area is exactly 40.46 m²; occupied air volume is 117.334 m³. The structural ceiling at Z = 4.80 is metadata, not meshed occupied space. X/Y aspect ratio is an assumption. A cropped drawing has since been received; see [layout review](LAYOUT_REVIEW.md). The following coordinates belong to the earlier **provisional-v1** model and are not a reconstruction of that crop.

Nominal opening selection boxes are below. Faces are selected by their centres from the actual Cartesian mesh; patch sizes are snapped to the grid, and **actual mesh areas** are reported for every patch. Areas can change with resolution, so use the report when assessing diffuser velocity. All specified volume flows are integrated over the actual faces, not divided by nominal drawing areas.

| Item | Nominal centre(s), m | Nominal selection / model |
|---|---|---|
| KPAU 1, 2 | (1.4,1.2,2.9), (5.6,1.2,2.9) | ceiling, 0.62 × 0.62 m selection boxes; normal downflow |
| EAF 1, 2 | (7,1.5,2.5), (7,4.3,2.5) | east wall, 0.62 × 0.62 m selection boxes |
| Hoods 1–5 | X = 0.8,2.1,3.4,4.7,6.0; Y=5; Z=2.9 | ceiling, 0.78 × 0.62 m boxes; 850 m³/h each when ON |
| Transfer lower / upper | (0,2.89,0.5275), (0,2.89,1.5825) | one west-wall doorway, 0.90 m wide × 2.11 m high, vertically split |
| People | X=1–6, Y=1.8–4.1, Z=0.1–1.9 | uniformly distributed volume source in selected cells |
| Cooking 1–5 | beneath corresponding hoods, Z=0.6–1.2 | local selected-cell heat and moisture sources |
| FCUs | X=1–2 / 5–6, Y=0.2–0.8, Z=2–2.6 | local momentum actuator and sensible UA source |

Room edges and equipment markers in the viewer are simplified annotations. Equipment boxes and humans are **not** meshed solid obstacles. Hood capture surfaces, canopy shape, duct resistance, actual discharge directions and manufacturer fan/coil data remain missing.

## Governing equations

The native solver is OpenCFD OpenFOAM v1912 (`1912.200626`, Debian build), steady incompressible Boussinesq RANS with SIMPLE pressure–velocity coupling and standard k–ε turbulence:

- Continuity: ∇·U = 0.
- Momentum: ∇·(UU) = −∇p_rgh + viscous/turbulent stress + Boussinesq buoyancy + optional FCU momentum source.
- Temperature: ∇·(UT) − ∇·[(ν/Pr + νt/Prt)∇T] = Q/(ρ cp V).
- Dilute humidity ratio: ∇·(Uw) − ∇·[(ν/Sc + νt/Sct)∇w] = water generation/(ρ V).

Here w is kg water / kg dry air. Constants: ρ = 1.2 kg/m³ dry-air approximation, cp = 1006 J/(kg·K), ν = 1.5×10⁻⁵ m²/s, Pr = 0.71, Prt = 0.85, Sc = 0.60, Sct = 0.70, β = 0.003366 K⁻¹. Reference temperature is adjacent-space temperature. Moisture is a passive dilute scalar; its small mass/density contribution is neglected in Boussinesq continuity/buoyancy. This assumption is unsuitable for steam-dominated flows.

`scalarTransport` executes in the native solver at every iteration, with `alphaD=1/Sc`, `alphaDt=1/Sct`, three scalar correctors and cell-zone `scalarSemiImplicitSource` moisture gains. It is not a post-hoc single-zone moisture calculation. Momentum equations use conservative under-relaxation (0.15); pressure is fully corrected (factor 1) so its kinetic-head boundary and the velocity corrector stay consistent. Steady-state upwind finite-volume convection is used; no result smoothing is applied to the numerical export.

Humidity postprocessing uses:

```
pv = P_atm * w / (0.621945 + w)
RH = 100 * pv / p_sat(T)
```

`p_sat(T)` is the ASHRAE Fundamentals saturation-pressure-over-liquid-water relation, with Kelvin temperature and P_atm = 101325 Pa. RH is **not clipped** to 100%; supersaturation causes a failed physical check because condensation is not modelled. The valid input temperatures stay above freezing.

The hydrostatic reference hRef=0.8 m is near the provisional doorway neutral height to reduce numerical cancellation. It does not change the physical external reservoir pressure. Initial T and w use a bounded well-mixed balance only as a starting guess for the full 3D solver; initialization is never displayed as calculated output.

## HVAC and boundary consistency

- Supplies use `flowRateInletVelocity` with inward volume flow = total KPAU / 2; fixed supply temperature and humidity ratio. Default actual flow = 0.290 m³/s, not the 1.250 m³/s design value.
- EAF: two `flowRateInletVelocity` extraction patches, each −0.280 m³/s by default, for **0.560 m³/s total**. Hood flow is never included a second time in EAF.
- Each hood ON extracts −850/3600 m³/s locally. OFF changes that opening into an impermeable wall. Cooking heat/moisture sources stay at their own locations and are independent of the hood state.
- Transfer doorway (two face patches): `prghTotalPressure` with rho=rhok and per-face external kinematic total pressure p0_ext=g*(z−hRef), `pressureNormalInletOutletVelocity`, and temperature/moisture `inletOutlet` using the specified adjacent conditions. Pressure solves the flow split and direction. Gross counterflows are reported in addition to net transfer. No transfer flow is prescribed or allocated algebraically. The adjacent space is an ideal quiescent reservoir: inlet kinetic head is included, outflow matches external static pressure, and no additional door/grille loss coefficient is known.
- Default global balance must produce **270 L/s net transfer inward**. All five hoods ON require an additional 1180.556 L/s makeup at the same supply/EAF values. At 1250 L/s supply with hoods OFF, transfer must reverse to **690 L/s net outward**.
- Outlet scalars have zero normal gradient during outflow and specified adjacent values on backflow. Impermeable walls are adiabatic and have zero vapour flux. Velocity is no-slip, with turbulence wall functions.
- Turbulence inlet values are provisional k=0.003 m²/s² and ε=0.001 m²/s³; manufacturer jet turbulence is unknown.

The exported pressure is static gauge pressure relative to hydrostatic adjacent air, in Pa:

```
rhok = 1 − beta*(T − TRef)
p_gauge = rhoRef * [p_rgh + (rhok − 1)*g*(z − hRef)]
```

OpenFOAM's `p_rgh` is a **kinematic** buoyancy-corrected pressure; it is not directly labelled Pa. Dynamic pressure and the ambient hydrostatic head are not mistakenly displayed as room pressurisation.

## Gains and FCU assumptions

People default to 75 W sensible and 55 W latent each. The provisional 130 W total and split are referenced to **ASHRAE Handbook—Fundamentals (2021), Chapter 18, Table 1, representative standing/light-work, walking-slowly gains**. This is a configurable modelling assumption, not a claim that the activity/temperature correction has been established for this kitchen. Water generation = latent W / 2,450,000 J/kg. Five people therefore supply 375 W sensible and approximately 0.40408 kg/h water. Their body geometry and individual thermal plumes are unresolved by the distributed source region.

Cooking gains default to zero because equipment and cooking schedules were not supplied. Each of five sources can supply the same configurable sensible W and moisture kg/h. This supports local buoyant cooking plumes interacting with each hood's extraction, without inventing equipment loads.

Each enabled FCU adds:

- Momentum relaxation toward the configurable fan speed: +Y in the earlier single-zone actuator model, downward beneath each of two mapped supply diffusers per unit in annotated-v2 (`U` source `target − U`, 1/s). This imparts momentum but no mass; the pressure/continuity solver determines recirculation.
- Sensible heat exchange `Q = UA*(Tcoil − mean local T)`, with UA = nominal kW × 1000 / 10 K. For annotated-v2, each of the two supply regions receives half of the unit UA; the total is not doubled. Both positive and negative actual thermal duties are possible if room air crosses the assumed coil temperature; actual integrated duty is reported. Default nominal duty is 2.5 kW per FCU at ΔT=10 K, coil=14°C, fan target=1 m/s.

This is a preliminary actuator/heat-exchanger representation, not a resolved return/supply plenum, fixed-capacity refrigerator or manufacturer FCU simulation. It has no condensate sink, coil psychrometrics or fan power heat. Confirm these assumptions before using FCU-on cases for humidity decisions.

## Acceptance checks and output provenance

A solver process exiting successfully does not imply convergence. The output status is `numerically_checked` only if **all** these gates pass:

1. `checkMesh -allGeometry -allTopology` reports `Mesh OK`, with no failed checks.
2. Global signed native face-flux sum / gross boundary outflow <0.1%, and sum of absolute cell continuity imbalances / gross outflow <0.1%. Maximum individual-cell flux imbalance is also reported.
3. Outward sensible heat flux including boundary diffusion agrees with integrated thermal sources/sinks within 2% of the larger of net or positive source magnitude (minimum 1 W).
4. Outward water-vapour flux including diffusion agrees with source within 2% (minimum normalisation 10⁻⁷ kg/s).
5. The **initial equation residuals**, not only final linear-solver residuals, stay below thresholds over the last 20 iterations: U components, k, ε and p_rgh <10⁻⁴; T <10⁻⁵; w <10⁻⁶. The first of the three w correctors is used.
6. Transfer pressure matches the adjacent quiescent hydrostatic reservoir to <0.001 Pa at every boundary face: total pressure on inflow and static pressure on outflow. The native condition evaluates p_rgh=p0_ext−rhok*g*(z−hRef)−0.5*rhok*|U|² on inflow; the kinetic-head term is omitted on outflow. Setting p_rgh=0 everywhere would omit both density and inlet kinetic-head corrections.
7. Exported fields are finite, w≥0, 0<T<60°C, RH≤100%.

Heat and vapour budgets use each actual mesh face, its owner cell, upwind advective value, orthogonal boundary distance, face area and the solver's written boundary diffusivity. Source values and FCU heat exchange are integrated over the selected cells. This is independent of any single-zone heat-balance estimate.

Every exported result includes native output-file SHA-256 hashes, exact inputs, mesh metadata and a validation report. `results.json` stores all cell-centre T, RH, g/kg, U and gauge pressure values, sorted by the actual cell coordinates. Sections show finite-volume cell values. Displayed streamlines are numerical integrations of this exported U, seeded at supply/transfer faces; they are visual postprocessing, not additional CFD solutions.

A `preliminary` case is still real CFD output, but has failed at least one gate; the UI displays that status with the report. Steady buoyant flows may need more iterations or a transient model. Never lower criteria merely to make a case pass. Mesh convergence, wall y+ assessment, actual geometry, calibrated loads, external pressure effects and comparison with measurements are separate outstanding physical validation tasks. No ASHRAE 55 compliance claim is made.

## Source references

- OpenCFD, OpenFOAM v1912: `buoyantBoussinesqSimpleFoam`, `scalarTransport`, `flowRateInletVelocity`, `pressureNormalInletOutletVelocity`, semi-implicit finite-volume sources. The turbulent scalar transport configuration was checked against the packaged upstream source `src/functionObjects/solvers/scalarTransport/scalarTransport.C`.
- ASHRAE Handbook—Fundamentals (2021), Chapter 1 (psychrometrics) and Chapter 18 (nonresidential heating/cooling load calculations and occupant gains). Confirm the adopted gains against the design handbook edition and actual kitchen activity.

## Executed reference cases

The checked reports in this repository are evidence from actual OpenFOAM runs on the provisional mesh, not measured kitchen data:

| Case | Native cells | Iterations | Occupied mean T | Occupied mean RH | Sensible-heat balance error | Water balance error |
|---|---:|---:|---:|---:|---:|---:|
| Requested baseline | 15,225 | 5,000 | 19.965°C | 67.583% | 0.000955% | 0.0000377% |
| Five hoods + two FCUs + 1 kW / 0.3 kg/h per cooking station | 15,225 | 5,000 | 21.839°C | 62.367% | 0.0000225% | 0.00000318% |

Both passed all seven numerical acceptance gates. Full reports: [baseline-validation.json](baseline-validation.json) and [cooking-validation.json](cooking-validation.json). Native generated files are retained in the prepared workspace and available through each case's download; large solver outputs are ignored by Git. A fresh clone regenerates them using the documented runner. The cooking case has 5,375 W positive sensible gains and approximately 2,491 W actual FCU sensible cooling; the reported heat budget uses that actual cooling, not the nominal 5 kW label.

The baseline's low occupied temperature and elevated RH are outputs of the stated provisional geometry and boundary assumptions. They are not a design prediction for the actual Demo Kitchen without registering the supplied HVAC layout and calibrating the loads. No physical validation or mesh-independence claim is made.

## Drawing-based baseline execution

`runs/layout-baseline-v2` completed 15,000 iterations on a 15,750-cell mesh using the user-confirmed terminal identities. All seven numerical gates passed. The final sensible-heat imbalance was 0.00000480%, water-vapour imbalance 0.000000103%, and the net transfer was 270 L/s inward. Occupied-zone means were **17.876°C / 75.246% RH**, with mean speed **0.088 m/s**. These are results under the recorded provisional dimensions, diffuser assumptions and closed-partition model, with five people, hoods OFF, FCUs OFF and cooking gains zero. They are not measurements or a design-validation claim. Report: [annotated-layout-validation.json](annotated-layout-validation.json).

The first 5,000-iteration checkpoint did not satisfy heat/residual criteria; it was continued without changing physical inputs or weakening tolerances. Future fresh cases default to 10,000 iterations. The prior 5,000-step cases in the older table above remain legacy-geometry references.
