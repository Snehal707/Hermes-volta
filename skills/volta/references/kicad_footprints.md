# KiCad Footprint Reference — Hermes Volta

Preferred footprints target low-cost JLCPCB assembly and compact two-layer prototype boards. Verify availability in the current JLCPCB parts catalog before ordering.

## Preferred JLCPCB Footprints

| Component type | Preferred footprint | Notes |
| --- | --- | --- |
| Resistor, 0402 | `Resistor_SMD:R_0402` | Default for RC filters and dividers |
| Capacitor, 0402 | `Capacitor_SMD:C_0402` | Use C0G/NP0 where precision matters; check DC bias for X5R/X7R |
| Inductor, 0402 | `Inductor_SMD:L_0402` | Check saturation current, DCR, and self-resonant frequency |
| Test point, SMD | `TestPoint:TestPoint_Pad_D1.0mm` | Useful for `VIN`, `VOUT`, and `GND` |
| 2-pin through-hole connector | `Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical` | Good for bench power or signal input |
| 3-pin through-hole connector | `Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical` | Useful for `VIN`, `VOUT`, `GND` |
| SMA edge connector | `Connector_Coaxial:SMA_Amphenol_132134_EdgeMount` | Use for RF-ish bench signals only after impedance-aware layout |
| Generic IC SOIC-8 | `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm` | For future op-amp active filters |
| Generic IC SOT-23-5 | `Package_TO_SOT_SMD:SOT-23-5` | For tiny op-amps, regulators, references |

## JLCPCB 2-Layer Design Rules

Use conservative defaults unless the board has a reason to push limits.

| Rule | Recommended value | Notes |
| --- | --- | --- |
| Layers | 2 | Top and bottom copper |
| Finished copper | 1 oz | Default prototype choice |
| Minimum trace width | 0.15 mm | Use wider traces for power |
| Preferred signal trace width | 0.20 mm | Easier to fabricate and inspect |
| Power trace width | 0.50 mm or wider | Calculate for current and temperature rise |
| Minimum clearance | 0.15 mm | Increase for voltage, noise, or hand assembly margin |
| Preferred clearance | 0.20 mm | Good default for simple filters |
| Minimum via drill | 0.30 mm | Conservative standard via |
| Preferred via drill | 0.40 mm | More robust for prototypes |
| Minimum via diameter | 0.60 mm | Pair with 0.30 mm drill |
| Preferred via diameter | 0.80 mm | Pair with 0.40 mm drill |
| Edge clearance | 0.30 mm minimum | Keep copper away from board outline |
| Solder mask expansion | KiCad default | Review for fine-pitch footprints |

## Layout Notes

- Keep the filter input, output, and ground return short.
- Put shunt capacitors close to the output node and ground.
- Avoid routing noisy digital signals near high-impedance analog nodes.
- Use a continuous ground reference where possible.
- Add test pads for `VIN`, `VOUT`, and `GND`.
- For RLC filters, check inductor orientation, DCR, and magnetic coupling.
- Generated PCB files are starting points, not finished production layouts.
