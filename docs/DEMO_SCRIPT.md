# Hermes Volta Demo Script

This script matches the public hackathon demo flow. It is written for **The Hermes Agent Creative Hackathon by Nous Research** and highlights Hermes Agent skills, tools, multimodal control, and Volta's deterministic engineering pipeline.

## Core Story

Hermes Volta is a circuit-design copilot built on Hermes Agent. It turns plain English into:

- Filter topology selection
- Component values
- PySpice/Ngspice simulation
- Bode and transient validation plots
- KiCad-compatible netlists and starter boards
- Gerber archives
- Cutoff reports
- Telegram delivery
- Dashboard streaming
- Reusable learned recipes

The important demo claim is not just "AI explains circuits." The claim is:

```text
Hermes Agent can operate a real engineering workflow: compute, simulate, verify, export, deliver, and remember.
```

## Demo Video

[![Hermes Volta demo video](https://img.youtube.com/vi/Qx1U6dPjKfs/maxresdefault.jpg)](https://youtu.be/Qx1U6dPjKfs)

## CLI Segment

Show Hermes Agent running with Kimi K2.6, then run these prompts:

1. `design an anti-aliasing filter for a 44.1kHz audio ADC at 5V`
2. `design RC lowpass filters at 200Hz, 2kHz and 20kHz`
3. `@MEMORY.md scale my most accurate design to 8kHz`
4. `I'm building an ECG heart monitor and need to filter muscle noise`
5. `@MEMORY.md which design should I use for a guitar pedal?`
6. `show me all the circuit designs you have learned from so far`
7. `what new rules have you added to your skill file from our designs?`

What this proves:

- Skills and references are active.
- The learning loop can improve `skills/volta/SKILL.md`.
- Session search and memory can reuse previous designs.
- Autonomous mode can research project context before choosing a topology.
- Batch/delegated work can run sweeps and tolerance checks.
- RL trajectories are saved for learned design paths.

## Telegram Segment

Run these Telegram interactions:

1. Voice message: `design a 500Hz high-pass filter at 3.3 volts`
2. Hand-drawn schematic photo: `simulate this circuit`
3. `I'm building a drone vibration sensor`
4. `check my BOM prices every Monday morning`
5. `design a 3kHz bandpass filter in background`
6. `generate a render for my last design`
7. `roll back to previous design`

What this proves:

- Hermes Agent can handle voice, text, and vision inputs.
- Telegram is a real operating surface, not only a notification target.
- Cron, background sessions, rendering, and rollback are part of the workflow.

## Dashboard Segment

Prompt:

```text
design a 7kHz low-pass filter at 3.3V
```

Show:

- Hermes Stream filling with progress
- Bode plot
- PCB visual
- Full-width transient validation plot
- VIN vs VOUT filter effect plot
- Cutoff report
- Design history dropdown

What this proves:

- Hermes Volta has a live visual interface.
- Generated artifacts update directly from the engineering pipeline.
- The dashboard is demo-ready for judges who want to inspect results quickly.

## Closing Line

```text
Hermes Volta turns Hermes Agent into an analog circuit engineer: it computes, simulates, verifies, exports, delivers, and learns from each design.
```
