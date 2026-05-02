# Hermes Volta Architecture

Hermes Volta is not a standalone chatbot. It is a Hermes Agent project that uses a Volta skill, Python simulation tools, KiCad-compatible export helpers, Telegram delivery, and a browser dashboard to turn natural-language circuit requests into inspectable engineering artifacts.

## System Diagram

```mermaid
flowchart TD
    subgraph Inputs
        CLI[CLI prompts]
        TEL[Telegram\ntext, voice, schematic photo]
        DASH[Dashboard prompt]
    end

    subgraph Hermes["Hermes Agent Runtime"]
        MODEL[Kimi K2.6]
        SKILL[Volta skill\nskills/volta/SKILL.md]
        REFS[Skill references\nfilter math, KiCad footprints,\ncomponent recipes]
        MEMORY[Memory + session search]
        TOOLS[Hermes tools\nexecute_code, send_message,\nweb search, cron,\nbackground, rollback]
    end

    subgraph Volta["Hermes Volta Repo"]
        PIPE[sim/faraday_pipeline.py]
        SWEEP[sim/sweep_optimizer.py]
        MC[sim/monte_carlo.py]
        COMPARE[sim/compare_plot.py]
        API[dashboard/api.py]
    end

    subgraph Simulation["Engineering Pipeline"]
        SIM[PySpice + Ngspice\nAC and transient simulation]
        NET[SKiDL/manual KiCad netlist]
        PCB[KiCad CLI starter board,\npreview, Gerbers]
        REPORT[cutoff_report.txt]
    end

    subgraph Artifacts
        BODE[frequency_response.png]
        WAVE[waveform.png]
        EFFECT[compare_plot.png]
        BOARD[pcb_view.png]
        GERBERS[gerbers.zip]
        TXT[cutoff_report.txt]
    end

    CLI --> Hermes
    TEL --> Hermes
    DASH --> API
    API --> PIPE

    MODEL --> SKILL
    SKILL --> REFS
    SKILL --> PIPE
    MEMORY --> PIPE
    TOOLS --> PIPE

    PIPE --> SIM
    PIPE --> NET
    PIPE --> PCB
    PIPE --> REPORT
    PIPE --> SWEEP
    PIPE --> MC
    PIPE --> COMPARE

    SIM --> BODE
    SIM --> WAVE
    COMPARE --> EFFECT
    PCB --> BOARD
    PCB --> GERBERS
    REPORT --> TXT

    BODE --> DASH
    WAVE --> DASH
    EFFECT --> DASH
    BOARD --> DASH
    TXT --> TEL
    GERBERS --> TEL
```

## Where Hermes Agent Lives

The local development machine has a `hermes-agent/` directory at the repo root:

```text
/mnt/c/Users/ASUS/HermesVolta/hermes-agent/
```

That directory is intentionally not committed. It is ignored by `.gitignore` because it is the external Hermes Agent runtime checkout and virtual environment, not source code owned by Hermes Volta.

The public repo shows the Hermes Agent integration points instead:

| Repo path | Role |
| --- | --- |
| `skills/volta/SKILL.md` | The Hermes skill that teaches the agent how to design, simulate, verify, export, deliver, and remember Volta circuits. |
| `skills/volta/references/` | Durable circuit math, footprint rules, component recipes, and extended workflow docs loaded by the Volta skill. |
| `sim/faraday_pipeline.py` | Main Hermes `execute_code` target for a full design run. |
| `sim/simulate.py` | PySpice/Ngspice simulation engine for AC response and transient validation. |
| `sim/netlist.py` | SKiDL-first KiCad netlist generation with manual fallback. |
| `sim/pcb_export.py` | KiCad CLI PCB preview and Gerber export wrapper. |
| `sim/report.py` | Cutoff report and memory-style design summary writer. |
| `dashboard/api.py` | FastAPI layer that streams design progress and serves generated artifacts. |
| `tools/rl_trajectory.py` | Trajectory logging for learned design paths. |
| `tests/smoke_test.py` | End-to-end smoke test for simulation, plots, Telegram, web search, reports, and exports. |

## Runtime Flow

1. A user sends a prompt from CLI, Telegram, or the dashboard.
2. Hermes Agent loads the Volta skill and relevant references.
3. Kimi K2.6 interprets the intent and selects the design workflow.
4. Hermes tools run the deterministic Python pipeline.
5. The pipeline computes component values, simulates the circuit, exports EDA artifacts, writes reports, and records reusable design knowledge.
6. Results are shown in the dashboard, sent through Telegram, and saved under `outputs/`.

## Boundary

Hermes Agent is the orchestration/runtime layer. Hermes Volta is the domain project that supplies the analog-circuit skill, deterministic engineering tools, dashboard, tests, and generated artifacts.
