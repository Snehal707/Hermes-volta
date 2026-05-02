# Filter Transfer Functions Reference

Use this reference for first-pass Volta calculations before running PySpice/Ngspice.

## RC Low-Pass

Transfer function:

```text
H(s) = 1 / (1 + sRC)
```

Cutoff:

```text
fc = 1 / (2πRC)
```

At `fc`, the response is -3 dB relative to passband. Above cutoff, an ideal first-order RC low-pass rolls off at -20 dB/decade.

## RC High-Pass

Transfer function:

```text
H(s) = sRC / (1 + sRC)
```

Cutoff:

```text
fc = 1 / (2πRC)
```

At `fc`, the response is -3 dB relative to passband. Below cutoff, an ideal first-order RC high-pass attenuates at 20 dB/decade.

## RLC Band-Pass

Center frequency:

```text
fc = 1 / (2π√LC)
```

Quality factor:

```text
Q = (1/R)√(L/C)
```

Bandwidth:

```text
BW = R / L
```

This convention matches a simple series LC feeding a load resistance. Confirm topology-specific definitions before comparing Q values.

## RLC Notch

Notch frequency:

```text
fc = 1 / (2π√LC)
```

The notch depth depends on source impedance, load impedance, inductor resistance, capacitor ESR, and layout parasitics.

## E24 Standard Values

| Series | Values per decade |
| --- | --- |
| E24 | 10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91 |

Example decade expansions:

| Range | Values |
| --- | --- |
| 100 Ω decade | 100, 110, 120, 130, 150, 160, 180, 200, 220, 240, 270, 300, 330, 360, 390, 430, 470, 510, 560, 620, 680, 750, 820, 910 Ω |
| 1 kΩ decade | 1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1 kΩ |
| 10 kΩ decade | 10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91 kΩ |

## Common Capacitor Values

| Family | Values |
| --- | --- |
| pF | 10 pF, 22 pF, 47 pF, 100 pF, 220 pF, 470 pF |
| nF | 1 nF, 2.2 nF, 4.7 nF, 10 nF, 22 nF, 47 nF, 100 nF, 220 nF, 470 nF |
| µF | 1 µF, 2.2 µF, 4.7 µF, 10 µF, 22 µF |

Notes:

- Use C0G/NP0 for precision small capacitance where available.
- X7R and X5R are common for 0402, but DC bias can reduce effective capacitance.
- Electrolytics and tantalums are not appropriate for precision small-signal cutoff setting without tolerance analysis.

## Frequency Scaling Rules

- RC filters: doubling `R` halves `fc` when `C` is constant.
- RC filters: doubling `C` halves `fc` when `R` is constant.
- RLC filters: quadrupling `L` halves `fc` when `C` is constant.
- RLC filters: quadrupling `C` halves `fc` when `L` is constant.
- First-order filters change slope by 20 dB/decade per pole.
- Always recompute after rounding to E-series values.

## Butterworth vs Chebyshev

| Family | Strength | Tradeoff |
| --- | --- | --- |
| Butterworth | Maximally flat passband | Slower transition than Chebyshev |
| Chebyshev | Sharper transition for a given order | Passband ripple and more phase variation |

For Volta's current passive first-order and simple RLC workflows, use these families as design context rather than direct synthesis targets.
