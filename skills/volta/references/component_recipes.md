# Verified Component Recipes — Hermes Volta

Community-maintained. Submit PRs: `github.com/Snehal707/hermes-volta`

These tables are intentionally empty until recipes are verified with reproducible simulation artifacts and, ideally, bench measurements. Add only entries that include target frequency, selected components, simulated actual frequency, error percentage, verifier, and date.

## RC_LOWPASS

| fc | R | C | actual_fc | error% | verified_by | date |
| --- | --- | --- | --- | --- | --- | --- |

## RC_HIGHPASS

| fc | R | C | actual_fc | error% | verified_by | date |
| --- | --- | --- | --- | --- | --- | --- |

## RLC_BANDPASS

| fc | R | C | L | actual_fc | error% | verified_by | date |
| --- | --- | --- | --- | --- | --- | --- | --- |

## RLC_NOTCH

| fc | R | C | L | actual_fc | error% | verified_by | date |
| --- | --- | --- | --- | --- | --- | --- | --- |

## How To Contribute

1. Run the Volta pipeline for the recipe.
2. Confirm the generated report includes target `fc`, theory `fc`, actual `fc`, and error percentage.
3. Prefer E24/E96 and JLCPCB-orderable values.
4. Note capacitor dielectric and voltage rating if they materially affect the result.
5. Open a pull request with the report and plot artifacts referenced.

Community:

- Discord: `https://discord.gg/nousresearch`
- Repo: `https://github.com/Snehal707/hermes-volta`
