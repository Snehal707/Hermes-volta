# Hermes Volta

Natural-language analog circuit design for Hermes Agent.

Hermes Volta turns a plain-English filter request into computed component values, real PySpice/Ngspice simulation, validation plots, KiCad-compatible EDA artifacts, Gerbers, reports, Telegram delivery, and a live cyber-green dashboard.

> Demo prompt: `design a 2kHz high-pass filter for a microphone at 5V`

## Why It Matters

Most AI circuit demos stop at explanation. Hermes Volta produces artifacts an engineer can inspect:

- Theory values and practical E24 component choices
- Real AC and transient simulation through PySpice/Ngspice
- Bode response, transient validation, and VIN vs VOUT effect plots
- KiCad legacy netlist, starter `.kicad_pcb`, Gerber zip, and PCB preview
- Text report with cutoff error, BOM strings, and output paths
- Telegram delivery and an OpenAI-compatible dashboard API

## Hackathon Demo Flow

1. Open the live dashboard at `http://localhost:8765`.
2. Enter a prompt such as:

   ```text
   design a 7kHz low-pass filter at 3.3V
   ```

3. Watch the Hermes Stream panel show pipeline progress:

   ```text
   [Volta] Starting RC_LOWPASS...
   [Volta] Running PySpice/Ngspice simulation...
   [Volta] Simulation actual_fc=7234.21 Hz, error=3.346%
   [Volta] Generating KiCad netlist...
   [Volta] Exporting PCB artifacts with kicad-cli...
   [Volta] Writing cutoff report...
   [Volta] Done.
   ```

4. The dashboard refreshes with:

   - Bode plot
   - PCB visual
   - Full-width transient validation plot
   - Filter effect plot showing VIN, VOUT, and rejected/difference content
   - Cutoff report

5. If Hermes Telegram is configured, Volta also sends the summary and artifacts to Telegram.

## Current EDA Truth

Hermes Volta currently generates **KiCad-compatible starter artifacts**, not a production-routed PCB.

Generated EDA artifacts include:

- `circuit.net`: KiCad legacy XML netlist with components, footprints, and nets
- `circuit.kicad_pcb`: minimal starter board file with board outline
- `gerbers.zip`: Gerbers exported by `kicad-cli`
- `pcb_view.png`: Matplotlib PCB preview generated from the netlist

Generated boards are starting points for engineering review, not production-approved layouts.

## Supported Circuits

| Circuit type | Purpose | Formula |
| --- | --- | --- |
| `RC_LOWPASS` | Pass low frequencies, attenuate high-frequency noise | `fc = 1 / (2*pi*R*C)` |
| `RC_HIGHPASS` | Block DC/slow drift, pass higher-frequency signals | `fc = 1 / (2*pi*R*C)` |
| `RLC_BANDPASS` | Pass a resonant center frequency | `f0 = 1 / (2*pi*sqrt(L*C))` |
| `RLC_NOTCH` | Reject a resonant center frequency | `f0 = 1 / (2*pi*sqrt(L*C))` |

## Repository Layout

```text
dashboard/        FastAPI dashboard and live artifact UI
sim/              Simulation, netlist, PCB export, report, compare plots
skills/volta/     Hermes Agent skill and references
tests/            Smoke test suite
tools/            Trajectory, webhook, BOM helper tools
outputs/          Generated artifacts, ignored by git
```

## Quick Start

This project was developed under WSL2. For the checked-in project path, use the package-complete venv:

```bash
cd /mnt/c/Users/ASUS/HermesVolta
/mnt/c/Users/ASUS/HermesVolta/hermes-agent/.venv/bin/python3 dashboard/api.py
```

Open:

```text
http://localhost:8765
```

For a fresh install on another machine:

```bash
cd hermes-volta
bash skills/volta/scripts/install_deps.sh
```

## Run The Pipeline Directly

Use the Hermes Volta venv for simulation scripts:

```bash
/mnt/c/Users/ASUS/HermesVolta/hermes-agent/.venv/bin/python3 - <<'PY'
from sim.faraday_pipeline import run

result = run(
    circuit_type="RC_LOWPASS",
    R=1600,
    C=1e-7,
    supply_v=5.0,
    L=None,
    fc=1000,
    description="1kHz audio low-pass filter",
)
print(result)
PY
```

## Useful Commands

E24 resistor sweep:

```bash
/mnt/c/Users/ASUS/HermesVolta/hermes-agent/.venv/bin/python3 sim/sweep_optimizer.py --fc 1000 --C 1e-7
```

Monte Carlo tolerance check:

```bash
/mnt/c/Users/ASUS/HermesVolta/hermes-agent/.venv/bin/python3 sim/monte_carlo.py --R 1600 --C 1e-7 --fc 1000 --n 1000
```

Full smoke test:

```bash
/mnt/c/Users/ASUS/HermesVolta/hermes-agent/.venv/bin/python3 tests/smoke_test.py
```

## Dashboard API

Volta exposes both a browser dashboard and an OpenAI-compatible API:

```text
Dashboard: http://localhost:8765
OpenAI-compatible base URL: http://localhost:8765/v1
Model: volta-1.0
```

The `/design` endpoint streams deterministic Volta pipeline progress directly to the dashboard.

## Kimi Track Note

Hermes Volta is model-agnostic through Hermes Agent. To qualify for the Kimi track, run the demo with Hermes Agent configured to use a Kimi model and show that model selection in the submission video. The circuit pipeline itself remains deterministic and auditable.

## Validation Status

Recent local smoke tests passed `13/13`, covering simulation, batch runs, optimizer, Monte Carlo, compare plot, netlist generation, PCB export, report generation, Telegram delivery, math accuracy, and Firecrawl availability.

## Author

Built by Snehal.

- GitHub: `Snehal707`
- X: `@SnehalRekt`
- Telegram: `@Snehal_7`

## License

MIT
