# Hermes Agent Creative Hackathon Demo Plan

## One-Line Pitch

Hermes Volta turns natural language into verified analog circuit artifacts: simulation plots, KiCad-compatible EDA files, Gerbers, reports, Telegram delivery, and a live dashboard.

## 90-Second Video Structure

1. Show Hermes Agent / Kimi model selection if entering the Kimi track.
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

## Claims To Avoid

- Do not claim production-ready PCB layout.
- Do not claim automatic component sourcing/pricing is final without manual verification.
- Do not claim Kimi track eligibility unless the video proves a Kimi model was used.

## Suggested Tweet Copy

```text
I built Hermes Volta for the Hermes Agent Creative Hackathon.

Plain English -> analog circuit design -> PySpice/Ngspice simulation -> Bode/transient plots -> KiCad-compatible netlist/starter PCB -> Gerbers -> report -> Telegram + dashboard delivery.

Demo: [video link]

@NousResearch
```
