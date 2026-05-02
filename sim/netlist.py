"""KiCad netlist generation for Hermes Volta.

The generator tries SKiDL first. If SKiDL is unavailable or cannot generate
the requested circuit, it writes a manual KiCad legacy XML netlist.
"""

import sys
import os

# Add venv site-packages to path so execute_code can find packages
VENV_SITE_PACKAGES = "/mnt/c/Users/ASUS/HermesVolta/hermes-agent/.venv/lib/python3.11/site-packages"
if VENV_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, VENV_SITE_PACKAGES)

# Also add project root
PROJECT_ROOT = "/mnt/c/Users/ASUS/HermesVolta"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.etree.ElementTree import Element, SubElement, tostring


CircuitType = Literal["RC_LOWPASS", "RC_HIGHPASS", "RLC_BANDPASS", "RLC_NOTCH"]

OUTPUT_DIR = Path("outputs")
NETLIST_PATH = OUTPUT_DIR / "circuit.net"
RESISTOR_FOOTPRINT = "Resistor_SMD:R_0402"
CAPACITOR_FOOTPRINT = "Capacitor_SMD:C_0402"
INDUCTOR_FOOTPRINT = "Inductor_SMD:L_0402"
CONNECTOR_FOOTPRINT = "Connector:TestPoint"


@dataclass(frozen=True)
class NetComponent:
    ref: str
    value: str
    footprint: str
    pins: tuple[str, str]


def _normalize_circuit_type(circuit_type: str) -> CircuitType:
    normalized = circuit_type.strip().upper().replace("-", "_")
    supported = {"RC_LOWPASS", "RC_HIGHPASS", "RLC_BANDPASS", "RLC_NOTCH"}
    if normalized not in supported:
        raise ValueError(f"unsupported netlist circuit type {circuit_type!r}")
    return normalized  # type: ignore[return-value]


def _eng(value: float, unit: str) -> str:
    prefixes = [
        (1e9, "G"),
        (1e6, "M"),
        (1e3, "k"),
        (1.0, ""),
        (1e-3, "m"),
        (1e-6, "u"),
        (1e-9, "n"),
        (1e-12, "p"),
    ]
    magnitude = abs(value)
    for scale, prefix in prefixes:
        if magnitude >= scale or scale == 1e-12:
            return f"{value / scale:.6g}{prefix}{unit}"
    return f"{value:.6g}{unit}"


def _components(circuit_type: CircuitType, r_ohm: float, c_f: float, l_h: float | None) -> list[NetComponent]:
    r_value = _eng(r_ohm, "R")
    c_value = _eng(c_f, "F")
    source = NetComponent("J1", "VIN", CONNECTOR_FOOTPRINT, ("VIN", "GND"))

    if circuit_type == "RC_LOWPASS":
        return [
            source,
            NetComponent("R1", r_value, RESISTOR_FOOTPRINT, ("VIN", "VOUT")),
            NetComponent("C1", c_value, CAPACITOR_FOOTPRINT, ("VOUT", "GND")),
            NetComponent("J2", "VOUT", CONNECTOR_FOOTPRINT, ("VOUT", "GND")),
        ]
    if circuit_type == "RC_HIGHPASS":
        return [
            source,
            NetComponent("C1", c_value, CAPACITOR_FOOTPRINT, ("VIN", "VOUT")),
            NetComponent("R1", r_value, RESISTOR_FOOTPRINT, ("VOUT", "GND")),
            NetComponent("J2", "VOUT", CONNECTOR_FOOTPRINT, ("VOUT", "GND")),
        ]
    if circuit_type == "RLC_BANDPASS":
        if l_h is None:
            raise ValueError(f"L is required for {circuit_type}")
        l_value = _eng(l_h, "H")
        return [
            source,
            NetComponent("L1", l_value, INDUCTOR_FOOTPRINT, ("VIN", "N_LC")),
            NetComponent("C1", c_value, CAPACITOR_FOOTPRINT, ("N_LC", "VOUT")),
            NetComponent("R1", r_value, RESISTOR_FOOTPRINT, ("VOUT", "GND")),
            NetComponent("J2", "VOUT", CONNECTOR_FOOTPRINT, ("VOUT", "GND")),
        ]
    if l_h is None:
        raise ValueError(f"L is required for {circuit_type}")
    l_value = _eng(l_h, "H")
    return [
        source,
        NetComponent("R1", r_value, RESISTOR_FOOTPRINT, ("VIN", "VOUT")),
        NetComponent("L1", l_value, INDUCTOR_FOOTPRINT, ("VOUT", "N_LC")),
        NetComponent("C1", c_value, CAPACITOR_FOOTPRINT, ("N_LC", "GND")),
        NetComponent("J2", "VOUT", CONNECTOR_FOOTPRINT, ("VOUT", "GND")),
    ]


def _try_skidl(components: list[NetComponent], output_path: Path) -> bool:
    if os.environ.get("VOLTA_ENABLE_SKIDL", "").strip().lower() not in {"1", "true", "yes"}:
        return False

    try:
        from skidl import Circuit as SkidlCircuit
        from skidl import Net, Part, generate_netlist
    except Exception:
        return False

    try:
        skidl_circuit = SkidlCircuit()
        nets = {name: Net(name) for item in components for name in item.pins}
        with skidl_circuit:
            for item in components:
                if item.ref.startswith("R"):
                    part = Part("Device", "R", ref=item.ref, value=item.value, footprint=item.footprint)
                elif item.ref.startswith("C"):
                    part = Part("Device", "C", ref=item.ref, value=item.value, footprint=item.footprint)
                elif item.ref.startswith("L"):
                    part = Part("Device", "L", ref=item.ref, value=item.value, footprint=item.footprint)
                else:
                    part = Part("Connector", "Conn_01x02_Pin", ref=item.ref, value=item.value, footprint=item.footprint)
                part[1] += nets[item.pins[0]]
                part[2] += nets[item.pins[1]]
        generated = generate_netlist(file_=str(output_path))
        return output_path.exists() or bool(generated)
    except Exception as exc:
        print(f"Warning: SKiDL netlist generation failed, using manual KiCad netlist: {exc}")
        return False


def _write_manual_kicad_netlist(components: list[NetComponent], output_path: Path) -> None:
    export = Element("export", {"version": "D"})
    design = SubElement(export, "design")
    SubElement(design, "source").text = "Hermes Volta"
    SubElement(design, "date").text = ""
    SubElement(design, "tool").text = "Hermes Volta manual KiCad legacy netlist generator"

    comps = SubElement(export, "components")
    for item in components:
        comp = SubElement(comps, "comp", {"ref": item.ref})
        SubElement(comp, "value").text = item.value
        SubElement(comp, "footprint").text = item.footprint
        fields = SubElement(comp, "fields")
        SubElement(fields, "field", {"name": "JLCPCB"}).text = f"{item.value} {item.footprint}"

    nets = SubElement(export, "nets")
    net_names = sorted({net for item in components for net in item.pins})
    for code, net_name in enumerate(net_names, start=1):
        net = SubElement(nets, "net", {"code": str(code), "name": net_name})
        for item in components:
            for pin_index, pin_net in enumerate(item.pins, start=1):
                if pin_net == net_name:
                    SubElement(net, "node", {"ref": item.ref, "pin": str(pin_index)})

    output_path.write_bytes(tostring(export, encoding="utf-8", xml_declaration=True))


def generate_netlist(
    circuit_type: str,
    R: float,
    C: float,
    L: float | None = 10e-3,
    supply_v: float = 1.0,
    output_dir: str | Path = OUTPUT_DIR,
) -> str:
    """Generate ``outputs/circuit.net`` and return its path."""
    del supply_v
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    output_path = out / "circuit.net"
    normalized = _normalize_circuit_type(circuit_type)
    components = _components(normalized, float(R), float(C), float(L) if L is not None else None)

    if not _try_skidl(components, output_path):
        _write_manual_kicad_netlist(components, output_path)

    return str(output_path)


if __name__ == "__main__":
    print(generate_netlist("RC_LOWPASS", R=1_000.0, C=100e-9))
