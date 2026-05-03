---
name: volta
description: Design analog circuits from plain English. Computes component values, runs PySpice/Ngspice simulation, exports KiCad PCB, generates Bode plots and JLCPCB-ready Gerbers. Learns verified recipes across sessions.
version: 1.0.0
author: Snehal707
repository: https://github.com/Snehal707/hermes-volta
license: MIT
platforms: [linux, macos]
tags: [electronics, EDA, PCB, KiCad, PySpice, filters, simulation, engineering]
requires_toolsets: [terminal]
config:
  volta.output_dir:
    default: ./outputs
  volta.supply_voltage:
    default: 5.0
  volta.footprint:
    default: "0402"
  volta.component_library:
    default: JLCPCB
  volta.fc_tolerance:
    default: 5.0
  volta.sim_path:
    default: ~/hermes-volta/sim
---

# Volta

Volta is a Hermes skill for turning plain-English analog circuit requests into component values, simulation artifacts, KiCad outputs, and reusable verified recipes.

## 1. What Volta Does

1. Parses the user's circuit goal, target frequency, supply voltage, constraints, and preferred component size.
2. Selects a supported topology or explains why the requested topology is outside the current scope.
3. Computes first-pass component values from filter equations.
4. Rounds resistor candidates to E24 values when a manufacturable part is needed.
5. Runs PySpice/Ngspice AC and transient simulations through `sim/simulate.py`.
6. Generates dark-theme Bode and transient waveform plots.
7. Generates a KiCad legacy netlist with JLCPCB-oriented footprints.
8. Exports a PCB preview and Gerber archive when `kicad-cli` is available.
9. Writes a cutoff report with theory, simulation, BOM search strings, and pass/fail status.
10. Saves verified recipes and scaling observations to Hermes memory so future sessions improve.

## 2. Circuit Types Supported

| Circuit type | Purpose | Main equation | Simulator support | PCB export |
| --- | --- | --- | --- | --- |
| `RC_LOWPASS` | Attenuate frequencies above cutoff | `fc = 1/(2pRC)` | AC + transient | Yes |
| `RC_HIGHPASS` | Attenuate frequencies below cutoff | `fc = 1/(2pRC)` | AC + transient | Yes |
| `RLC_BANDPASS` | Pass a resonant band | `fc = 1/(2pvLC)` | AC + transient | Yes |
| `RLC_NOTCH` | Reject a resonant band | `fc = 1/(2pvLC)` | AC + transient | Yes |
| `RL_LOWPASS` | Inductive low-pass/load smoothing | `fc = R/(2pL)` | AC + transient | Simulation only |

## 3. When to Load This Skill

Load Volta when the user asks to:

- Design an analog filter from a target cutoff or center frequency.
- Choose resistor, capacitor, or inductor values.
- Run a circuit simulation and produce plots.
- Export a simple KiCad PCB or Gerber package.
- Produce a JLCPCB-ready BOM search plan.
- Analyze cutoff error, tolerances, or manufacturable E24 alternatives.
- Convert a hand-drawn passive filter sketch into a simulated design.
- Recommend a circuit autonomously from a project description such as a guitar pedal, Arduino audio project, microphone preamp, sensor interface, or power-supply noise cleanup.

Do not treat Volta output as final safety approval. For mains, medical, automotive, aerospace, high-voltage, high-current, RF compliance, or life-safety use, explicitly require qualified engineering review.

## 4. Procedure

### Step 1: Parse

Extract:

- Circuit type or intent.
- Target cutoff/center frequency `fc`.
- Known `R`, `C`, `L`, and supply voltage.
- Load assumptions.
- Output requirements and allowed tolerance.

If the user gives a phrase like "1 kHz low-pass," map it to `RC_LOWPASS` unless the user asks for higher order behavior.

### Step 2: Check Memory + Session Search

Search Hermes memory and session history for verified recipes:

- Same circuit type.
- Similar frequency decade.
- Same footprint and component library.
- Previous pass/fail data and actual simulated cutoff.

Prefer verified local recipes over fresh guesses.

### Step 3: Compute

For RC filters:

```text
fc = 1 / (2pRC)
R = 1 / (2pfcC)
C = 1 / (2pfcR)
```

For RLC resonance:

```text
fc = 1 / (2pvLC)
Q = (1/R)v(L/C)
```

For RL low-pass:

```text
fc = R / (2pL)
```

Show the math in the response before running tools.

## Autonomous Design Mode

When the user describes a project instead of specifying a circuit, Volta should autonomously recommend and generate the first useful circuit design.

CRITICAL: Autonomous Design Mode is an execution mode, not a suggestion mode. Do not ask "Want me to..." or request confirmation before simulation. Once the project type is understood, decide the circuit, explain the decision briefly, and immediately run the full Faraday pipeline in the same turn.

CRITICAL: Do not fall back to the project default supply voltage until the supply-voltage search has been attempted. If the search result gives a common project supply, use that value and mention it. Use the project default only when search is unavailable or inconclusive.

Trigger this mode when the user describes a project without specifying `fc`. Typical examples:

- "I'm building a guitar pedal"
- "I'm making an Arduino audio project"
- "I'm designing a microphone preamp"
- "I'm building a sensor interface"
- "I need to clean up my power supply noise"

Trigger keywords include: "building", "making", "designing", "project", "for my", and "I need".

Volta should not ask the user for `fc` or component values. Instead:

1. Run `web_search` for `"{project type} typical signal frequency range"`.
2. Run `web_search` for `"{project type} supply voltage common"`.
3. From the search results, determine:
   - Recommended circuit type
   - Target `fc`
   - Supply voltage
   - Why this design makes sense
4. Tell the user what Volta decided and why before running the pipeline. Example:

```text
For a guitar pedal: audio signal range is about 80 Hz-8 kHz.
I'll design a 10 kHz low-pass anti-alias filter at 9 V to preserve the full audio range while blocking RF noise.
```

5. Run the full Faraday pipeline using those autonomous decisions. Do not stop after explaining the recommendation.
6. In Telegram delivery, include the reasoning:

```python
send_message(platform="telegram", message="Why this design: {explanation}")
```

Autonomous defaults should be conservative:

- Prefer `RC_LOWPASS` for audio anti-aliasing, RF cleanup, and general signal smoothing.
- Prefer `RC_HIGHPASS` for DC blocking or removing low-frequency rumble from audio.
- Prefer `RLC_NOTCH` only when the project clearly needs rejection of a known narrow interference frequency.
- Prefer `RL_LOWPASS` or RC decoupling guidance for power-supply noise cleanup when the current path or load impedance is unclear.
- If search results conflict, choose the safer wider-bandwidth design and explain the uncertainty.

### Step 4: Execute Code Pipeline

Do not run `hermes checkpoint save`; this Hermes install does not provide a `checkpoint` CLI command.
Filesystem checkpoints are handled automatically by Hermes when `checkpoints.enabled` is true.

Use the Faraday pipeline in a single `execute_code` turn:

When running sim scripts via terminal tool, ALWAYS use:

```bash
export VOLTA_PROJECT_ROOT="${VOLTA_PROJECT_ROOT:-$(pwd)}"
PYTHON="${VOLTA_PYTHON:-$VOLTA_PROJECT_ROOT/hermes-agent/.venv/bin/python3}"
$PYTHON -c "from sim.faraday_pipeline import run; ..."
```

Never use `python3`, `/usr/bin/python3`, or any other interpreter.

```python
from sim.faraday_pipeline import run

result = run(
    circuit_type="RC_LOWPASS",
    R=1592,
    C=1e-7,
    supply_v=5.0,
    L=1e-2,
    fc=1000,
    description="1 kHz input anti-noise low-pass"
)
result
```

Immediately after `run(...)` returns, extract:

```python
from pathlib import Path

output_dir = Path(result["output_dir"]).expanduser().resolve()
actual_fc = result["actual_fc"]
error_pct = result["error_pct"]
```

Then perform the mandatory Telegram delivery gate in `## Telegram Delivery`.
Do not write the final answer to the user until all six `send_message(platform="telegram", ...)` calls have completed.

Expected return keys:

```text
actual_fc, error_pct, bode_path, wave_path, pcb_png, gerbers, report
```

### Step 5: Verify

Check:

- `actual_fc` is within `volta.fc_tolerance`.
- Bode plot exists and has plausible magnitude/phase behavior.
- Transient plot exists and matches topology behavior.
- Report includes BOM and memory entry.
- PCB/Gerbers exist if `kicad-cli` is installed.

### Step 6: Parallel Optimization via delegate_task

When the target matters, launch three subagents:

- Subagent A: run `$PYTHON sim/sweep_optimizer.py --fc <target> --C <capacitance>` and report the top E24 resistor candidates.
- Subagent B: inspect the Bode plot/report for pass/fail and physical plausibility.
- Subagent C: run `$PYTHON sim/monte_carlo.py --R <resistance> --C <capacitance> --fc <target> --n 1000` and report tolerance robustness.

Merge the results into a final recommendation.

### Step 7: Save to Memory

After verification, save a concise memory entry:

```text
Hermes Volta verified RC_LOWPASS: target 1 kHz, R=1.6 kO, C=100 nF, actual_fc=994.7 Hz, error=0.53%, footprint=0402, library=JLCPCB.
```

Never call the memory tool with an empty string. If no verified design was completed, skip memory saving.

### Step 8: Patch Skill via skill_manage

When a recipe is repeatedly verified or corrected, update:

- `references/component_recipes.md`
- `references/filter_math.md`
- this skill's Scaling Rules section if a general rule emerges.

Use `skill_manage` or a repo patch so the improvement persists.

### Step 9: Deliver Outputs

Return:

- Circuit type and assumptions.
- Component values.
- Theory and simulated cutoff.
- Error percentage and pass/fail.
- Bode plot path.
- Waveform path.
- KiCad netlist path.
- PCB PNG and Gerber zip path when available.
- Report path.
- Memory entry string.

## Telegram Delivery

After every design, ALWAYS send these 7 messages in order.
This is a mandatory delivery gate, not an optional summary step.
The final user response is not complete until all seven Telegram calls below have been executed.

Use the per-design folder returned by `faraday_pipeline`:

```python
from pathlib import Path

output_dir = Path(result["output_dir"]).expanduser().resolve()
```

The `output_dir` is always returned in the result dict as `"output_dir"`.

CRITICAL: Do not pass literal strings like `"{output_dir}/frequency_response.png"` to `send_message`. Build real file paths with `output_dir / "filename"` or an f-string before sending.

1. Send text summary:
```python
send_message(
    platform="telegram",
    message="Volta Design Complete: {circuit_type} {fc}Hz\nR={R} C={C}\nActual fc={actual_fc}Hz\nError={error}%\nStatus=PASS"
)
```

2. Send Bode plot:
```python
send_message(platform="telegram", file=str(output_dir / "frequency_response.png"), message="Bode Plot")
```

3. Send waveform:
```python
send_message(platform="telegram", file=str(output_dir / "waveform.png"), message="Transient Waveform")
```

4. Send PCB view:
```python
send_message(platform="telegram", file=str(output_dir / "pcb_view.png"), message="PCB Layout")
```

5. Send report:
```python
send_message(platform="telegram", file=str(output_dir / "cutoff_report.txt"), message="Design Report")
```

6. Send Gerbers:
```python
send_message(platform="telegram", file=str(output_dir / "gerbers.zip"), message="Gerbers")
```

7. Send VIN vs VOUT annotated comparison plot:
```python
send_message(platform="telegram",
  file=str(output_dir / "compare_plot.png"),
  message="Filter Effect - VIN vs VOUT | Orange=noisy input | Green=filtered output (real simulation)")
```

MANDATORY: This must be sent after every design. Never skip it.
compare_plot.png is always generated by faraday_pipeline.py.

CRITICAL: Never skip image delivery. Even if text summary was sent, always send all 7 messages.
CRITICAL: If the design was run through terminal instead of `execute_code`, still call `send_message` afterward with the returned `output_dir`.
CRITICAL: Do not stop after sending the text summary. The Bode plot, waveform, PCB view, report, Gerbers, and compare plot messages must be sent as files every time.

## Engineering Advice

After every verified design, always add a brief engineering note relevant to the circuit type:

RC_LOWPASS:
- "If used as anti-alias filter before ADC: sampling rate must be >> 2 × fc (Nyquist). ADC input impedance must be >> R to avoid filter loading."
- "For audio: fc sets the -3dB point. Perceived rolloff starts ~1 octave before fc."

RC_HIGHPASS:
- "If used as DC-blocking filter: fc sets low-frequency cutoff. Verify source impedance << R."
- "For AC coupling: use X7R ceramic cap to avoid capacitance variation with DC bias."

RLC_BANDPASS:
- "Q factor determines bandwidth. Q = fc/BW. Higher Q = narrower band."
- "Inductor DCR adds series resistance — verify DCR << R for accurate Q."

RLC_NOTCH:
- "Notch depth depends on component matching. 1% tolerance components give ~40dB notch depth."

Send this advice as a final Telegram message after the 6 standard messages:

```python
send_message(platform="telegram", 
  message="Engineering Note: {relevant_advice}")
```

## Event Hooks

After every verified design, fire a webhook to log the design to an external system using terminal:

```python
terminal(command="""
curl -s -X POST https://hooks.zapier.com/hooks/catch/volta-designs \
  -H "Content-Type: application/json" \
  -d '{
    "circuit_type": "{circuit_type}",
    "fc": "{fc}",
    "actual_fc": "{actual_fc}",
    "error": "{error}",
    "R": "{R}",
    "C": "{C}",
    "status": "PASS",
    "timestamp": "{timestamp}",
    "output_dir": "{output_dir}"
  }' 2>/dev/null || echo "webhook skipped"
""")
```

## API Server

Hermes Volta exposes an OpenAI-compatible API server via the existing FastAPI dashboard at port `8765`.

Other developers can point any OpenAI-compatible client to:
`http://localhost:8765/v1`
and use Volta as their circuit design assistant.

Available endpoints:

- `POST /v1/chat/completions`: OpenAI-compatible endpoint. Accepts `{"messages": [{"role": "user", "content": "design a 1kHz filter"}]}`. Detects circuit design intent, runs `faraday_pipeline` when design intent is detected, and returns an OpenAI-format response with design results.
- `GET /v1/models`: Returns available models: `{"data": [{"id": "volta-1.0", "object": "model"}]}`.
- `GET /designs`: Lists all design folders in `outputs/`.
- `GET /designs/{folder_name}`: Returns full design data including `circuit_type`, `R`, `C`, `fc`, `actual_fc`, `error`, and all file paths.

Compatible clients include Open WebUI, LobeChat, LibreChat, and any OpenAI client that allows a custom base URL.

## Plugins

Volta includes a custom audit plugin that logs every tool call for transparency and debugging. View at `/audit` on the dashboard.

The audit plugin records:

- Timestamp
- Tool name
- Tool input summary
- Session ID
- Circuit type and frequency when detectable
- End-of-session summary such as: `Session X: designed RC_LOWPASS 1kHz, 8 tool calls, 2m 43s`

The plugin lives at `plugins/volta_audit.py` in this project and is installed into Hermes as `~/.hermes/plugins/volta_audit/`.

## RL Training

Every Volta design session generates ShareGPT trajectory data. This data trains the next generation of Hermes models to be better circuit design agents. Your designs make the agent smarter for everyone.

Trajectories are saved to `outputs/trajectories/{session_id}.json` with:

- User request
- Volta reasoning summary
- Tool/simulation result
- Verification response
- Metadata including circuit type, target fc, actual fc, error percentage, tools used, skill, and timestamp

Run: `$PYTHON tools/submit_trajectory.py` to submit trajectories.

## IDE Integration (ACP)

Hermes Volta works inside ACP-compatible editors: VS Code, Cursor, Zed, JetBrains.

Use Volta directly inside your IDE without leaving your editor.

Setup for Cursor/VS Code:

1. Install the Hermes ACP extension
2. Connect to: `http://localhost:8765` (Volta API server)
3. Or run: `hermes --acp` in terminal

What you get in your IDE:

- Design circuits from the chat panel
- Output files appear directly in your file explorer
- `frequency_response.png` opens in the image preview
- `circuit.net` opens in the KiCad integration
- Gerbers folder appears ready to zip and upload

Workflow:

1. Open project in Cursor
2. Open Hermes chat panel
3. Type: `/volta design a 1kHz low-pass filter`
4. Bode plot appears in IDE image viewer
5. `circuit.net` appears in file tree
6. Gerbers folder ready to upload to JLCPCB

This turns your IDE into a full EDA workstation.

## Context References

Hermes supports `@` references to inject files into conversation. Volta should use these references as direct design context.

When user says:
- "optimize @outputs/circuit.net"
- "analyze @MEMORY.md"
- "improve @outputs/cutoff_report.txt"
- "@outputs/RC_LOWPASS_1000Hz_20260501_043223/cutoff_report.txt compare with latest"

Volta should:
1. Recognize the `@` reference as a file injection.
2. Read the referenced file content.
3. Use it as context for the requested operation.

Common `@` reference patterns:

- `@MEMORY.md` — injects all verified recipes for comparison.
- `@outputs/{folder}/cutoff_report.txt` — injects a specific design report.
- `@outputs/{folder}/circuit.net` — injects the KiCad netlist.
- `@skills/volta/references/component_recipes.md` — injects community recipes.

Example use cases:

- "`@MEMORY.md` which of my designs has the lowest error?"
- "`@outputs/RC_LOWPASS_1000Hz/cutoff_report.txt` scale this to 5kHz"
- "compare `@outputs/RC_LOWPASS_1000Hz/cutoff_report.txt` with `@outputs/RC_LOWPASS_2000Hz/cutoff_report.txt`"

## Honcho Memory Provider

Hermes supports external memory providers including Honcho for deep cross-session user modeling.

Volta supports the Honcho memory provider for enhanced cross-session personalization. To enable:

1. Install:

```bash
pip install honcho-ai
```

2. Add to `~/.hermes/.env`:

```env
HONCHO_API_KEY=your_key
HONCHO_APP_ID=hermes-volta
```

3. Add to `~/.hermes/config.yaml`:

```yaml
memory:
  provider: honcho
  honcho_app_id: hermes-volta
```

With Honcho enabled, Volta builds a deep model of your design preferences across sessions:

- Preferred supply voltages
- Favorite frequency ranges
- Component preferences
- Design patterns you repeat
- Projects you're working on

This makes Volta smarter about predicting what you need before you ask.

## Checkpoints and Rollback

Before every design that overwrites output files, Hermes should:
1. Confirm `checkpoints.enabled` is true in Hermes config.
2. Proceed with simulation. Hermes automatic filesystem checkpoints protect the previous outputs.
3. If user says "that was wrong" or "roll back" or "restore previous":
   - Call `/rollback` to restore the previous outputs.
   - Confirm: "Restored previous design outputs."

Trigger phrases:
- "roll back" -> `/rollback`
- "restore previous design" -> `/rollback`
- "undo last design" -> `/rollback`
- "the previous design was better" -> `/rollback`

Do not call `hermes checkpoint save`; this is not a valid command in this Hermes install. Use `/rollback` only when the user asks to restore.

## Batch Processing

When user asks to design multiple filters at once, run them in parallel using `delegate_task`.

Trigger phrases:
- "design filters at 100Hz, 500Hz, 1kHz, 5kHz"
- "design a filter bank"
- "batch design"
- "design multiple filters"

When triggered:
1. Parse all requested frequencies and circuit types from the message.
2. Spawn one subagent per filter using `delegate_task` (max 3 at a time).
3. Each subagent runs the full `faraday_pipeline` for its frequency.
4. Collect all results.
5. Each filter gets its own output folder under `outputs/{circuit_type}_{fc}Hz_{timestamp}/`.
6. Send a batch summary to Telegram:
   "? Batch Design Complete — X filters designed"
   Then send each filter's plots and reports individually from its own output folder.
7. Save all verified recipes to `MEMORY.md`.

Example: "design RC lowpass filters at 100Hz, 1kHz, 10kHz" -> 3 parallel subagents -> 3 complete design packages -> Telegram.

## Background Sessions

When user says:
- "design in background"
- "run this in background"
- "don't wait, just design it"
- "/background design a..."

Use the `/background` command to run the design as a background task.
This lets the user keep chatting while the design runs.
Use `/background` only in live Hermes CLI sessions or messaging gateway sessions where the Hermes process stays alive.
Do not use `/background` through one-shot `hermes chat -q` commands; one-shot mode may treat it as normal prompt text and exit before a background task can be managed.

Example usage:
User: "design a 5kHz bandpass filter in background"
Volta: Uses `/background` so it responds immediately and delivers results to Telegram when done, without blocking the conversation.

For long-running batch designs (3+ filters), always suggest running in background:
"This will take ~3 minutes. Want me to run it in background and notify you on Telegram when done?"

## PCB Product Render

When user says any of these:
- "generate a render"
- "show me what it looks like"
- "product render"
- "photorealistic PCB"
- "make it look real"

Call `image_gen` tool with this prompt:

```python
image_gen(
    prompt="A photorealistic macro photograph of a tiny green PCB 
    circuit board on a dark electronics workbench. The board has 
    two SMD 0402 components: a resistor labeled {R} ohms (R1) and 
    a ceramic capacitor labeled {C} farads (C1). Green soldermask, 
    gold ENIG surface finish, white silkscreen labels. 
    Professional product photography, shallow depth of field, 
    soft studio lighting, dark background. 
    Board silkscreen reads: Hermes Volta {circuit_type} {fc}Hz",
    width=1024,
    height=768
)
```

After generating:
1. Save the image to `output_dir / "product_render.png"`
2. Send to Telegram:
```python
send_message(platform="telegram",
  file=str(output_dir / "product_render.png"),
  message="PCB Product Render - {circuit_type} {fc}Hz")
```

Also add `image_gen` to the standard design flow as optional:
After the 7 standard messages, if user has previously requested renders or says "always render", automatically generate one.

## Cron Automation

After every successful design, offer the user to set up automated monitoring:

"Would you like me to check component prices weekly?"

If user says yes, create a cron job:

cronjob(
    action="create",
    name="Volta Weekly BOM Check",
    schedule="0 9 * * 1",
    prompt="Check LCSC and JLCPCB prices for all circuits saved in 
    MEMORY.md. For each saved design, search for the resistor and 
    capacitor values in 0402 SMD format. Report any price changes 
    greater than 10% since last check. Send results to Telegram.",
    delivery="telegram"
)

Also add instructions for on-demand cron:
User can say "check my BOM prices every Monday" and Volta creates the job.
User can say "stop BOM checks" and Volta removes the job with:
cronjob(action="delete", name="Volta Weekly BOM Check")

## Vision — Hand-Drawn Schematic Input

When the user sends an image (photo of hand-drawn schematic, whiteboard circuit, or datasheet):

1. Call vision_analyze on the image:

vision_analyze(
    image=<uploaded_image>,
    prompt="Extract from this hand-drawn circuit schematic:
    1. Circuit topology (RC lowpass, highpass, bandpass, notch, etc.)
    2. All component values shown (R in ohms, C in farads, L in henries)
    3. Supply voltage if shown
    4. Target cutoff frequency if labeled
    
    Return ONLY this JSON, nothing else:
    {
      'circuit_type': 'RC_LOWPASS',
      'R': 1000,
      'C': 1e-7,
      'L': null,
      'supply_v': 5.0,
      'fc_target': 1000,
      'confidence': 'high',
      'notes': 'any ambiguities'
    }"
)

2. If confidence is high: run full pipeline immediately
3. If confidence is medium: show extracted values, ask user to confirm before simulating
4. If confidence is low: ask user to label component values clearly and resend

5. After simulation: deliver all outputs to Telegram as usual

Also add this trigger instruction:
"Load this skill when user sends any image and says anything like:
simulate this, design this circuit, what is this circuit, analyze this schematic"

## Voice Mode

- User sends voice message on Telegram.
- Hermes auto-transcribes it.
- Treat transcribed text as typed message.
- If circuit design intent detected, run full `/volta` pipeline.
- Deliver all outputs to Telegram as usual.
- User can enable spoken replies with `/voice on` in Telegram.

## 6. Hand-Drawn Schematic Input via vision_analyze

If the user uploads a hand-drawn schematic:

1. Use `vision_analyze` to identify topology, component labels, node names, and ambiguous markings.
2. Restate the inferred circuit and ask only for missing values that block simulation.
3. Map the sketch to one of the supported circuit types.
4. Run the same compute, simulation, export, and report pipeline.
5. Mention any ambiguity from the drawing in the final answer.

## 7. Cron Automation Example

Weekly BOM check with Telegram notification:

```yaml
cron:
  name: volta-weekly-bom-check
  schedule: "0 9 * * MON"
  task: |
    cd ~/hermes-volta
    export VOLTA_PROJECT_ROOT="${VOLTA_PROJECT_ROOT:-$(pwd)}"
    PYTHON="${VOLTA_PYTHON:-$VOLTA_PROJECT_ROOT/hermes-agent/.venv/bin/python3}"
    $PYTHON tools/check_bom_prices.py
    hermes telegram send "Volta weekly BOM check complete. Review outputs/bom_status.txt"
```

Use this pattern only after the user has configured Telegram and any supplier lookup credentials.

## 8. Pitfalls

- Ngspice install: PySpice needs the Ngspice shared library, not only the CLI binary.
- E24 values: ideal math often lands between real resistor values; run the E24 sweep before recommending a production value.
- Ceramic capacitor derating: X5R/X7R 0402 capacitors can lose significant capacitance under DC bias. Prefer C0G/NP0 for precision where capacitance is practical.
- Memory limits: store compact verified recipes, not full logs or plot dumps.
- KiCad CLI: `kicad-cli` exports only when KiCad is installed and available on `PATH`.
- PCB output: generated boards are starting artifacts, not layout-verified production designs.

## 9. Verified Recipes

Community-maintained recipe tables live in `references/component_recipes.md`.

### RC_LOWPASS

| fc | R | C | actual_fc | error% | verified_by | date |
| --- | --- | --- | --- | --- | --- | --- |

### RC_HIGHPASS

| fc | R | C | actual_fc | error% | verified_by | date |
| --- | --- | --- | --- | --- | --- | --- |

### RLC_BANDPASS

| fc | R | C | L | actual_fc | error% | verified_by | date |
| --- | --- | --- | --- | --- | --- | --- | --- |

### RLC_NOTCH

| fc | R | C | L | actual_fc | error% | verified_by | date |
| --- | --- | --- | --- | --- | --- | --- | --- |

## 10. Scaling Rules

Populated automatically as Volta learns.

Initial rules:

- For RC filters, holding `C` constant makes `fc` inversely proportional to `R`.
- For RC filters, holding `R` constant makes `fc` inversely proportional to `C`.
- For RLC resonance, increasing either `L` or `C` lowers `fc` by the square-root relationship.

## 11. Environment Setup

One-command install from the project root:

```bash
bash skills/volta/scripts/install_deps.sh
```

Then run a smoke test:

```bash
export VOLTA_PROJECT_ROOT="${VOLTA_PROJECT_ROOT:-$(pwd)}"
PYTHON="${VOLTA_PYTHON:-$VOLTA_PROJECT_ROOT/hermes-agent/.venv/bin/python3}"
$PYTHON - <<'PY'
from sim.faraday_pipeline import run
print(run("RC_LOWPASS", R=1600, C=1e-7, supply_v=5.0, L=None, fc=1000, description="smoke test"))
PY
```

## 12. Contributing

Pull requests are welcome at `https://github.com/Snehal707/hermes-volta`.

PR checklist:

- Include the target circuit type and component values.
- Include theory `fc`, simulated `actual_fc`, and error percentage.
- Include simulator/environment versions when possible.
- Use JLCPCB-friendly footprints unless the PR explains otherwise.
- Add verified recipes only when the simulation and report artifacts exist.
- Keep safety notes explicit for any power, high-voltage, or connector-facing circuit.

## 13. About

Built by Snehal (`@SnehalRekt`) on Hermes Agent by Nous Research.

