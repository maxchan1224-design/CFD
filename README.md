# Demo Kitchen CFD workbench

A local browser application backed by **OpenFOAM v1912**. Each run creates a native finite-volume mesh, executes `buoyantBoussinesqSimpleFoam` and a turbulent water-vapour `scalarTransport` equation, audits native face fluxes, and exports cell-centre fields to Three.js. There is no synthetic-field fallback.

## Start

Prerequisites: Linux, Python 3.12+, Node 20+, Docker with access to its local socket, and approximately 2 GB free disk space. Use the existing checkout; cloud tasks are already isolated and do not require a Git worktree.

```bash
cd /workspace/CFD  # or your checkout
bash scripts/setup.sh
bash scripts/start.sh
```

Open the application on port **8000** in your local browser. The server binds to **127.0.0.1** because its trusted local API controls Docker. Do not expose this API on a public interface. `KITCHEN_PORT` overrides the port. For remote use, provide an authenticated application gateway or tunnel. There is no public deployment configured.

For frontend development, start the API above, then `cd frontend && npm run dev`; Vite proxies `/api` to port 8000. No external font or visualization API is needed.

`FOAM_MODE=native` selects an installed OpenFOAM v1912; otherwise the API uses the local Docker image `demo-kitchen-openfoam:1912`. `FOAM_IMAGE` overrides the image name, **not** the solver version compatibility requirement. The build uses Debian's signed OpenFOAM packages with TLS/signature verification intact. Live solver processes must restart after environment restoration; dependencies and generated cases can be retained.

## Run the requested baseline

The UI defaults to annotated-v2 with 290 L/s KPAU at 15°C / 86% RH, total 560 L/s EAF, all five hoods OFF, both FCUs OFF, five people, and 24°C / 55% RH adjacent transfer air. Press **Run simulation**. The annotated layout uses 15,750 coarse cells or 61,776 medium cells (the earlier layout used 15,225 / 61,824). Allow approximately 6–10 minutes on one CPU core for the default 10,000 SIMPLE iterations; more difficult cases can remain preliminary at the iteration limit.

Alternatively:

```bash
.venv/bin/python scripts/run_case.py --scenario examples/annotated-baseline.json --case runs/my-baseline
# Returns 0 only when every numerical acceptance check passes.
# Returns 2 after solver success if any acceptance check fails.
```

Existing solved case directories are preserved; choose a new path to rerun. A complete case contains `constant/polyMesh`, `0`, a final time directory (`T`, `w`, `U`, `p_rgh`, `p`, `phi`, turbulence fields and `C`), solver/mesh logs, a `kitchen.foam` marker for ParaView, `results.json`, `fields.csv`, `validation.json`, and exact scenario/geometry inputs. The UI downloads a ZIP of these files. Fields displayed by the viewer come exclusively from `results.json` exported from those native files; their SHA-256 hashes are recorded in the export.

To prepare a case on a machine without OpenFOAM:

```bash
.venv/bin/python scripts/run_case.py --generate-only --scenario examples/baseline.json --case runs/unverified
# Transfer that directory to an OpenFOAM v1912 machine:
cd runs/unverified && bash Allrun
```

Generating dictionaries does **not** verify execution. The UI exposes the same **Export runnable case** action when the solver is unavailable. Non-v1912 OpenFOAM releases have incompatible dictionary variants; they have not been tested.

## Physics and boundary conditions

See [engineering model](docs/ENGINEERING.md) for equations, assumptions, coordinates, limitations, references, acceptance criteria and pressure convention. A cropped HVAC layout has now been supplied. [Review the identified labels and candidate grilles](docs/LAYOUT_REVIEW.md). The user-annotated terminal mapping is implemented as **annotated-v2** with provisional dimensions and grille sizes/heights. Earlier **provisional-v1** cases are preserved separately; hood/cooking positions are still unmarked. The 2.9–4.8 m false-ceiling void is excluded from the CFD domain.

Two prescribed KPAU supply patches share the selected flow equally. Two EAF patches share **one** total exhaust setting. Each enabled hood adds 850 m³/h at its own local extraction patch. Disabled hood patches are solid walls. The annotated model uses an upper-wall transfer grille, split into pressure face groups, with pressure conditions and `pressureNormalInletOutletVelocity`; their inflow, outflow and possible simultaneous counterflow are calculated by the pressure/continuity solution.

People contribute sensible heat and water-vapour sources. Cooking heat/moisture settings apply separately to each of five stations; hood toggles do not change cooking gains. FCUs are provisional local momentum-actuator and sensible heat-exchanger models with independent switches. These recirculate room air without adding mass; they do not simulate coil condensation or an actual fan curve.

## Viewer and scenarios

- Orbit/zoom the provisional room; slice solved temperature, RH, humidity ratio or pressure on X/Y/Z sections.
- Velocity arrows use native cell velocities. Streamlines integrate the solved 3D `U` field with trilinear interpolation and midpoint/RK2 stepping; no animated invented flow is shown.
- Saved scenarios retain input sets on the API filesystem. Completed runs retain their original settings, field data and numerical reports. The comparison table shows occupied-zone metrics from completed cases.
- Editing settings does not change existing fields. The footer flags that a new run is needed.
- **Engineering checks** reports mesh status, residual histories, global and local continuity, sensible heat and water-vapour budgets, gross/net opening flows, and assumptions. Failed checks remain visible as **preliminary**.
- Comfort is a volume-fraction screen (22–26°C, 40–65% RH, air speed ≤0.25 m/s), not PMV/PPD or ASHRAE 55 certification. Mean radiant temperature, clothing and confirmed activity are missing.

## Tests

```bash
.venv/bin/python -m pytest -m 'not integration' -q
# After executing and exporting the baseline:
.venv/bin/python -m pytest -q
# With the API running; use the installed system Chromium or set CHROMIUM_PATH:
cd frontend
npx playwright test
npm run build
```

The integration test reads the **actual native baseline files**, checks all numerical gates and verifies supply/exhaust/transfer conservation. It is explicitly skipped if no real output exists; a skipped integration test is not CFD validation. Browser tests exercise native-field loading, sections, humidity ratio, vectors, streamlines, reports, scenario saving, equipment switches and mobile controls.

Numerical checks establish consistency of the discretised model only. They do not establish design accuracy without registering the supplied drawing, boundary measurements, a mesh-independence study and measured-data comparison.

The Physical layout selector distinguishes annotated-v2 from the earlier provisional-v1. Hood/cooking runs in annotated-v2 are blocked until the five positions are supplied; the earlier assumed-hood model remains selectable. Both versions retain their own geometry with their results. See [layout review](docs/LAYOUT_REVIEW.md).
