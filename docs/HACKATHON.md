# Hermes Agent Creative Hackathon Demo Plan

## Hackathon Context

Hermes Volta is a submission for **The Hermes Agent Creative Hackathon by Nous Research**. The project demonstrates Hermes Agent in a creative engineering domain: turning plain-English analog circuit intent into simulated waveforms, Bode plots, KiCad-compatible artifacts, Gerbers, reports, Telegram delivery, and a live dashboard.

## One-Line Pitch

Hermes Volta turns natural language into verified analog circuit artifacts: simulation plots, KiCad-compatible EDA files, Gerbers, reports, Telegram delivery, and a live dashboard, powered by Hermes Agent skills, memory, tools, and Kimi K2.6.

## Kimi Track

The demo was run with **Kimi K2.6** through Hermes Agent. The model drives intent understanding and autonomous workflow choices, while the circuit math, simulation, plots, reports, and EDA artifacts remain deterministic and inspectable.

## Hermes Skills Shown

| Skill / capability | Demo role |
| --- | --- |
| Volta skill | Loads `skills/volta/SKILL.md` as the circuit design workflow: compute first, simulate, verify, export, remember. |
| Skill references | Uses filter math, KiCad footprint guidance, component recipes, and extended process docs from `skills/volta/references/`. |
| Learning loop | Durable discoveries can be folded back into the Volta skill/references for future designs. |
| Memory | Verified recipes are saved and reused for later prompts. |
| Session search | Prior designs can be found and scaled, such as retargeting an accurate design to 8 kHz. |
| Context references | Prompts can directly reference project files such as `@MEMORY.md`. |

## Hermes Tools Shown

| Tool / surface | Demo role |
| --- | --- |
| `execute_code` / terminal | Runs PySpice, Ngspice, KiCad CLI, sweeps, Monte Carlo checks, and report generation. |
| Telegram `send_message` | Delivers design summaries, plots, reports, Gerbers, and status updates. |
| Voice mode | Telegram voice prompts become design requests. |
| Vision analysis | Hand-drawn schematic photos can be interpreted into supported circuit simulations. |
| Web search / Firecrawl | Autonomous design mode can research domain requirements before choosing a filter. |
| Cron scheduling | Recurring BOM checks can be scheduled. |
| Background sessions | Long-running designs can continue in the background. |
| Rollback / history | Previous designs can be restored for review or recovery. |
| RL trajectory logging | Learned design paths are recorded under `outputs/trajectories/`. |
| Dashboard/API | FastAPI dashboard streams Hermes progress and serves generated artifacts. |

## 90-Second Video Structure

1. Show Hermes Agent using Kimi K2.6.
2. Open the Hermes Volta dashboard.
3. Prompt:

   ```text
   design a 2kHz high-pass filter for a microphone at 5V
   ```

4. Show streamed progress in the Hermes Stream panel.
5. Show the generated artifacts:

   - Bode plot
   - PCB visual
   - transient validation
   - VIN vs VOUT filter effect plot
   - cutoff report
   - Telegram delivery

6. Open the output folder and show the EDA artifacts:

   - `circuit.net`
   - `circuit.kicad_pcb`
   - `gerbers.zip`

7. Close with:

   ```text
   Hermes Volta is a circuit-design copilot that computes, simulates, verifies, exports, and delivers analog designs from plain English.
   ```

## Honest Claims To Make

- Real PySpice/Ngspice simulation is used for frequency and transient validation.
- E24 resistor selection is used for practical RC designs.
- KiCad-compatible starter artifacts are generated.
- Gerbers are exported with `kicad-cli` when available.
- PCB visual preview is generated from the netlist for demo readability.
- The demo covers Hermes skills, memory, session search, web search, Telegram, voice, vision, cron scheduling, background work, rollback, and dashboard streaming.

## Claims To Avoid

- Do not claim production-ready PCB layout.
- Do not claim automatic component sourcing/pricing is final without manual verification.
- Do not claim the generated KiCad board is a finalized manufacturable PCB without manual layout review.

## Demo Coverage

### CLI Prompts

1. `design an anti-aliasing filter for a 44.1kHz audio ADC at 5V`
2. `design RC lowpass filters at 200Hz, 2kHz and 20kHz`
3. `@MEMORY.md scale my most accurate design to 8kHz`
4. `I'm building an ECG heart monitor and need to filter muscle noise`
5. `@MEMORY.md which design should I use for a guitar pedal?`
6. `show me all the circuit designs you have learned from so far`
7. `what new rules have you added to your skill file from our designs?`

### Telegram Prompts

1. Voice message: `design a 500Hz high-pass filter at 3.3 volts`
2. Hand-drawn schematic photo: `simulate this circuit`
3. `I'm building a drone vibration sensor`
4. `check my BOM prices every Monday morning`
5. `design a 3kHz bandpass filter in background`
6. `generate a render for my last design`
7. `roll back to previous design`

### Dashboard Prompt

```text
design a 7kHz low-pass filter at 3.3V
```

Show all four artifact panels updating, the design history dropdown, and the Hermes Stream filling with progress.

## Suggested Tweet Copy

```text
I built Hermes Volta for the Hermes Agent Creative Hackathon using Hermes Agent + Kimi K2.6.

Plain English -> analog circuit design -> PySpice/Ngspice simulation -> Bode/transient plots -> KiCad-compatible netlist/starter PCB -> Gerbers -> report -> Telegram + dashboard delivery.

The demo shows skills, memory, session search, web search, voice, vision, cron jobs, background sessions, rollback, RL trajectories, and live dashboard streaming.

Demo: https://youtu.be/Qx1U6dPjKfs
Repo: https://github.com/Snehal707/hermes-volta

@NousResearch
```
