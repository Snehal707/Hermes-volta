# CRITICAL — PYTHON INTERPRETER

Do not rely on distro `/usr/bin/python3` unless PySpice works there.

1. Prefer `VOLTA_PYTHON` (explicit path), then `<repo>/hermes-agent/.venv/bin/python3` (Hermes Agent checkout), then `<repo>/.venv/bin/python3` (from `install_deps.sh`).
2. Set `VOLTA_PROJECT_ROOT` when the checkout is symlinked or not under the default inferred layout (`sim/volta_paths.py` derives the repo root from this env or file location).

Example on a maintainer WSL machine (paths vary by clone):

```bash
VOLTA_PYTHON="/mnt/c/Users/ASUS/HermesVolta/hermes-agent/.venv/bin/python3"
"$VOLTA_PYTHON" -c "from PySpice.Spice.Netlist import Circuit; print('PySpice OK')"
```

HermesVolta resolves packages via bundled venv site-packages where present; pinned deps live in `requirements.txt`.

# Hermes Volta Project Context

## Project

Hermes Volta is a circuit design agent built on Hermes Agent. It converts plain-English analog circuit requests into component values, PySpice/Ngspice simulations, KiCad/SKiDL artifacts, Bode plots, waveform plots, JLCPCB-oriented BOMs, and reusable verified design recipes.

## Environment

- Runtime: Hermes Agent
- OS target: WSL2
- Circuit simulation: PySpice + Ngspice
- EDA/export: KiCad + `kicad-cli`
- Netlist generation: SKiDL first, manual KiCad legacy netlist fallback
- Project root: set via `VOLTA_PROJECT_ROOT`, or inferred from repo layout (`sim/`).
- Python: `VOLTA_PYTHON`, or `./hermes-agent/.venv/bin/python3`, or `./.venv/bin/python3`.
- Webhook URL: set `VOLTA_WEBHOOK_URL` in `~/.hermes/.env` to enable automatic design logging to external systems (Zapier, Notion, Airtable, Google Sheets).
- Honcho memory provider: set `HONCHO_API_KEY` and `HONCHO_APP_ID=hermes-volta` in `~/.hermes/.env`, then configure `memory.provider: honcho` and `memory.honcho_app_id: hermes-volta` in `~/.hermes/config.yaml` to enable deeper cross-session Volta personalization.
- After every session, trajectory saved to `outputs/trajectories/`. Submit with: `python3 tools/submit_trajectory.py`

## Conventions

- All generated artifacts go to `./outputs/`.
- Default passive footprint: SMD 0402.
- Default supply voltage: 5 V.
- Preferred component source: JLCPCB Basic Parts.
- Prefer E24 resistor values for practical RC designs unless precision demands otherwise.
- Treat generated KiCad boards as starting points, not production-approved layouts.

## Simulation Settings

- AC sweep: `dec 100 1Hz 1MEGHz`
- Transient: `step=1µs`, `end=5ms`
- Temperature: `25°C`
- Plots: Matplotlib Agg backend, dark theme
- Output plots: `outputs/frequency_response.png`, `outputs/waveform.png`

## After Every Successful Design

1. Save a concise verified recipe to `~/.hermes/memories/MEMORY.md`.
2. Patch `skills/volta/SKILL.md` if the design reveals a durable workflow improvement or scaling rule.
3. Keep artifacts in `outputs/`.
4. Report theory `fc`, actual simulated `fc`, error percentage, pass/fail, BOM strings, and output paths.

## Key Files

- `sim/simulate.py`: PySpice + Ngspice headless simulation engine. Builds supported circuits, runs AC/transient analysis, writes Bode and waveform PNGs, returns `actual_fc`, `bode_path`, and `wave_path`.
- `sim/netlist.py`: KiCad netlist generator. Tries SKiDL first, falls back to manual KiCad legacy `.net`, supports JLCPCB 0402 footprints, writes `outputs/circuit.net`.
- `sim/pcb_export.py`: Headless KiCad export wrapper. Uses `kicad-cli` via subprocess to create `outputs/circuit.kicad_pcb`, `outputs/pcb_view.png`, `outputs/gerbers/`, and `outputs/gerbers.zip`; returns `None` gracefully if KiCad is unavailable.
- `sim/report.py`: Plain-text design report writer. Writes `outputs/cutoff_report.txt` with circuit type, date, component values, target/theory/actual cutoff, error percentage, pass/fail, BOM search strings, output files, and Hermes memory entry.
- `sim/faraday_pipeline.py`: Main Hermes `execute_code` entry point. Exposes `run(circuit_type, R, C, supply_v, L, fc, description)` and orchestrates simulation, netlist, PCB export, and report generation.
- `sim/sweep_optimizer.py`: E24 resistor sweep tool for minimum RC cutoff error. Takes `--fc` and `--C`, prints best resistor and top 5 candidates.
- `sim/monte_carlo.py`: RC tolerance simulation tool. Takes `--R`, `--C`, `--fc`, `--n`, applies 5% resistor and 10% capacitor three-sigma normal distributions, and reports cutoff spread.
- `sim/__init__.py`: Marks `sim` as an importable Python package.
- `skills/volta/SKILL.md`: Publishable Hermes skill definition, workflow, supported circuit types, memory/skill update process, and contribution notes.
- `skills/volta/references/component_recipes.md`: Empty community-maintained verified recipe tables.
- `skills/volta/references/filter_math.md`: Transfer functions, E24 values, capacitor values, scaling rules, and filter-family notes.
- `skills/volta/references/kicad_footprints.md`: Preferred JLCPCB/KiCad footprints and two-layer PCB design rules.
- `skills/volta/scripts/install_deps.sh`: Linux/macOS setup script for Ngspice, KiCad, Python dependencies, outputs directory, and Hermes skill copy.
- `outputs/`: Generated simulation plots, reports, netlists, PCB previews, and Gerbers.
- `tools/`: Future helper tools for supplier checks, automation, and integrations.

## Hermes Features Used

- `skills`: Loads Volta's workflow, references, and procedures into Hermes.
- `execute_code`: Runs `sim.faraday_pipeline.run(...)` for a full design in one turn.
- `memory`: Stores verified circuit recipes and durable design observations.
- `skill_manage`: Patches Volta's skill and references after verified improvements.
- `session_search`: Finds previous related designs from the active conversation/session.
- `delegate_task`: Runs sweep, visual/report review, and Monte Carlo tolerance checks in parallel subagents.
- `cronjob`: Automates recurring checks such as weekly BOM availability.
- `send_message`: Sends design/report notifications through configured Hermes messaging integrations.
- `vision_analyze`: Interprets uploaded hand-drawn schematics before converting them into supported circuit types.

## Design Discipline

Volta never guesses where computation is possible. It computes first, simulates second, verifies third, then exports and records the result.
