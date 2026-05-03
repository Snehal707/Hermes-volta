"""Headless KiCad PCB export helpers for Hermes Volta."""

import sys
from pathlib import Path

_REPO_BOOT = Path(__file__).resolve().parents[1]
if str(_REPO_BOOT) not in sys.path:
    sys.path.insert(0, str(_REPO_BOOT))

from sim.volta_paths import prepend_sim_import_helpers  # noqa: E402

prepend_sim_import_helpers()

import shutil  # noqa: E402
import subprocess  # noqa: E402
import zipfile  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Any  # noqa: E402
from xml.etree import ElementTree as ET  # noqa: E402


OUTPUT_DIR = Path("outputs")
NETLIST_PATH = OUTPUT_DIR / "circuit.net"
PCB_PATH = OUTPUT_DIR / "circuit.kicad_pcb"
PCB_PNG_PATH = OUTPUT_DIR / "pcb_view.png"
GERBER_DIR = OUTPUT_DIR / "gerbers"
GERBER_ZIP_PATH = OUTPUT_DIR / "gerbers.zip"


@dataclass(frozen=True)
class NetComponent:
    ref: str
    value: str
    footprint: str
    nets: tuple[str, ...]


def _warn(message: str) -> None:
    print(f"Warning: {message}")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def _read_netlist(netlist_path: Path) -> tuple[list[NetComponent], dict[str, list[tuple[str, str]]]]:
    """Read a KiCad legacy XML netlist."""
    tree = ET.parse(netlist_path)
    root = tree.getroot()

    values: dict[str, tuple[str, str]] = {}
    for comp in root.findall("./components/comp"):
        ref = comp.attrib.get("ref", "")
        value = comp.findtext("value", default="")
        footprint = comp.findtext("footprint", default="")
        values[ref] = (value, footprint)

    nets: dict[str, list[tuple[str, str]]] = {}
    by_ref: dict[str, list[str]] = {ref: [] for ref in values}
    for net in root.findall("./nets/net"):
        name = net.attrib.get("name", "")
        nodes: list[tuple[str, str]] = []
        for node in net.findall("node"):
            ref = node.attrib.get("ref", "")
            pin = node.attrib.get("pin", "")
            if not ref:
                continue
            nodes.append((ref, pin))
            by_ref.setdefault(ref, []).append(name)
        nets[name] = nodes

    components = [
        NetComponent(ref=ref, value=value, footprint=footprint, nets=tuple(by_ref.get(ref, ())))
        for ref, (value, footprint) in sorted(values.items())
    ]
    return components, nets


def _infer_circuit_type(components: list[NetComponent], nets: dict[str, list[tuple[str, str]]]) -> str:
    refs = {component.ref for component in components}
    if {"R1", "C1", "L1"}.issubset(refs):
        r_nets = set(next((c.nets for c in components if c.ref == "R1"), ()))
        c_nets = set(next((c.nets for c in components if c.ref == "C1"), ()))
        if "GND" in c_nets and "VOUT" in r_nets:
            return "RLC_NOTCH"
        return "RLC_BANDPASS"
    if {"R1", "C1"}.issubset(refs):
        c_nets = set(next((c.nets for c in components if c.ref == "C1"), ()))
        if "GND" in c_nets:
            return "RC_LOWPASS"
        return "RC_HIGHPASS"
    return "Hermes Volta Circuit"


def _component_position(ref: str, index: int, circuit_type: str) -> tuple[float, float]:
    if circuit_type == "RC_LOWPASS":
        fixed = {
            "J1": (1.0, 2.8),
            "R1": (3.25, 2.8),
            "C1": (4.95, 1.7),
            "J2": (6.8, 2.8),
        }
    elif circuit_type == "RC_HIGHPASS":
        fixed = {
            "J1": (1.0, 2.8),
            "C1": (3.25, 2.8),
            "R1": (4.95, 1.7),
            "J2": (6.8, 2.8),
        }
    else:
        fixed = {
            "J1": (0.9, 2.8),
            "C1": (3.0, 2.8),
            "L1": (5.1, 2.8),
            "R1": (7.0, 2.8),
            "J2": (9.05, 2.8),
        }
    return fixed.get(ref, (2.0 + index * 1.7, 2.0))


def _component_size(ref: str) -> tuple[float, float]:
    if ref.startswith("J"):
        return (0.72, 0.9)
    if ref.startswith("L"):
        return (1.28, 0.78)
    return (1.28, 0.78)


def _pin_positions(x: float, y: float, width: float) -> tuple[tuple[float, float], tuple[float, float]]:
    return (x - width / 2, y), (x + width / 2, y)


def _circuit_style(circuit_type: str) -> dict[str, Any]:
    styles: dict[str, dict[str, Any]] = {
        "RC_LOWPASS": {
            "board": "#0d2614",
            "component_colors": {"R1": "#8844aa", "C1": "#4488cc"},
            "component_edges": {"R1": "#e9d5ff", "C1": "#bfdbfe"},
            "bottom_label": "LOW-PASS — passes low frequencies",
        },
        "RC_HIGHPASS": {
            "board": "#0d2614",
            "component_colors": {"C1": "#cc6600", "R1": "#44aacc"},
            "component_edges": {"C1": "#fed7aa", "R1": "#cffafe"},
            "bottom_label": "HIGH-PASS — passes high frequencies",
        },
        "RLC_BANDPASS": {
            "board": "#0d2614",
            "component_colors": {"R1": "#8844aa", "C1": "#4488cc", "L1": "#ccaa00"},
            "component_edges": {"R1": "#e9d5ff", "C1": "#bfdbfe", "L1": "#fef08a"},
            "bottom_label": "BAND-PASS — passes center frequency",
        },
        "RLC_NOTCH": {
            "board": "#0d2614",
            "component_colors": {"R1": "#8844aa", "C1": "#4488cc", "L1": "#ccaa00"},
            "component_edges": {"R1": "#e9d5ff", "C1": "#bfdbfe", "L1": "#fef08a"},
            "bottom_label": "NOTCH — rejects center frequency",
        },
    }
    return styles.get(
        circuit_type,
        {
            "board": "#0d2614",
            "component_colors": {},
            "component_edges": {},
            "bottom_label": "Hermes Volta generated PCB preview",
        },
    )


def _component_label(component: NetComponent) -> str:
    value = component.value.strip()
    if component.ref.startswith("R"):
        value = value.replace("ohm", "Ω").replace("Ohm", "Ω").replace(" ", "")
        if "Ω" not in value:
            value = f"{value}Ω"
    return f"{component.ref}\n{value}"


def _draw_pcb_preview(netlist_path: Path, output_path: Path, actual_fc: float | None = None) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

    components, nets = _read_netlist(netlist_path)
    circuit_type = _infer_circuit_type(components, nets)
    style = _circuit_style(circuit_type)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6.2), dpi=150)
    fig.patch.set_facecolor("#050b06")
    ax.set_facecolor(style["board"])
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.5)
    ax.set_aspect("equal")
    ax.axis("off")

    board = FancyBboxPatch(
        (0.35, 0.55),
        9.3,
        4.45,
        boxstyle="round,pad=0.02,rounding_size=0.16",
        linewidth=2.0,
        edgecolor="#7be495",
        facecolor=style["board"],
    )
    ax.add_patch(board)
    ax.text(
        5,
        5.25,
        f"Hermes Volta PCB — {circuit_type}",
        ha="center",
        va="center",
        color="#b7ffd0",
        fontsize=16,
        fontweight="bold",
        family="monospace",
    )
    if actual_fc is not None:
        ax.text(
            5,
            4.58,
            f"fc = {actual_fc:.0f} Hz",
            ha="center",
            va="center",
            color="#f7ff9a",
            fontsize=20,
            fontweight="bold",
            family="monospace",
            zorder=8,
        )

    placed: dict[str, dict[str, Any]] = {}
    for index, component in enumerate(components):
        x, y = _component_position(component.ref, index, circuit_type)
        width, height = _component_size(component.ref)
        placed[component.ref] = {"component": component, "x": x, "y": y, "width": width, "height": height}

    copper = "#c8a020"
    via = "#f4d35e"
    pin_lookup: dict[tuple[str, str], tuple[float, float]] = {}
    for ref, item in placed.items():
        left, right = _pin_positions(item["x"], item["y"], item["width"])
        pin_lookup[(ref, "1")] = left
        pin_lookup[(ref, "2")] = right

    for net_name, nodes in nets.items():
        points = [pin_lookup[(ref, pin)] for ref, pin in nodes if (ref, pin) in pin_lookup]
        if len(points) < 2:
            continue
        if net_name == "GND":
            y_bus = 1.2
        elif net_name == "VIN":
            y_bus = 3.7
        elif net_name == "VOUT":
            y_bus = 3.2
        else:
            y_bus = 2.15
        x_values = [point[0] for point in points]
        ax.plot([min(x_values), max(x_values)], [y_bus, y_bus], color=copper, linewidth=3.0, solid_capstyle="round")
        label_x = max(x_values) + 0.12
        label_y = y_bus
        label_ha = "left"
        if net_name == "VIN":
            label_x = min(max(min(x_values) + 1.9, 0.9), 3.25)
            label_y = y_bus + 0.16
        elif net_name == "VOUT":
            label_x = min(max(sum(x_values) / len(x_values), 5.2), 6.1)
            label_y = y_bus + 0.16
            label_ha = "center"
        elif net_name == "GND":
            label_x = min(max(x_values) + 0.12, 8.75)
        ax.text(label_x, label_y, net_name, color="#f7e08a", fontsize=8, family="monospace", va="center", ha=label_ha, zorder=12)
        for x, y in points:
            ax.plot([x, x], [y, y_bus], color=copper, linewidth=2.2, solid_capstyle="round")
            ax.add_patch(Circle((x, y), 0.07, color=via, ec="#5e4a00", linewidth=0.8, zorder=5))

    for ref, item in placed.items():
        component = item["component"]
        x = item["x"]
        y = item["y"]
        width = item["width"]
        height = item["height"]
        color = style["component_colors"].get(ref)
        edge = style["component_edges"].get(ref)
        if color is None:
            if ref.startswith("R"):
                color = "#8844aa"
                edge = "#e9d5ff"
            elif ref.startswith("C"):
                color = "#4488cc"
                edge = "#bfdbfe"
            elif ref.startswith("L"):
                color = "#ccaa00"
                edge = "#fef08a"
            else:
                color = "#222f24"
                edge = "#86efac"
        ax.add_patch(
            Rectangle(
                (x - width / 2, y - height / 2),
                width,
                height,
                facecolor=color,
                edgecolor=edge,
                linewidth=1.6,
                zorder=10,
            )
        )
        ax.text(
            x,
            y,
            _component_label(component),
            ha="center",
            va="center",
            color="#ffffff",
            fontsize=10,
            fontweight="bold",
            family="monospace",
            linespacing=1.35,
            zorder=11,
        )

    ax.text(
        5,
        0.78,
        style["bottom_label"],
        color="#b7ffd0",
        fontsize=11,
        fontweight="bold",
        family="monospace",
        ha="center",
    )
    ax.text(0.7, 0.59, "JLCPCB 0402 visual placement", color="#66ff99", fontsize=8, family="monospace")
    ax.text(9.3, 0.59, "not to scale", color="#66ff99", fontsize=8, family="monospace", ha="right")
    fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    return output_path


def _write_minimal_board(netlist_path: Path, pcb_path: Path) -> None:
    """Create a tiny KiCad PCB file so kicad-cli has a board artifact to export."""
    net_hint = netlist_path.name if netlist_path.exists() else "circuit.net"
    pcb_path.write_text(
        f"""(kicad_pcb (version 20221018) (generator hermes-volta)
  (general)
  (paper "A4")
  (title_block
    (title "Hermes Volta generated board")
    (comment 1 "Source netlist: {net_hint}")
  )
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user)
    (33 "F.Adhes" user)
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user)
    (37 "F.SilkS" user)
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (44 "Edge.Cuts" user)
  )
  (gr_rect (start 0 0) (end 30 18)
    (stroke (width 0.1) (type solid)) (fill none) (layer "Edge.Cuts"))
)
""",
        encoding="utf-8",
    )


def _zip_gerbers(gerber_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(gerber_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(gerber_dir))


def run_pcb_export(
    netlist_path: str | Path = NETLIST_PATH,
    output_dir: str | Path | float = OUTPUT_DIR,
    capacitance_f: float | None = None,
    actual_fc: float | None = None,
) -> dict[str, str]:
    """Create a visual PCB preview and Gerber zip.

    The PNG preview is generated with matplotlib from the netlist so components
    are visible even before a real KiCad placement/layout step exists.
    """
    direct_topology = str(netlist_path).strip().upper()
    if isinstance(output_dir, (int, float)) and capacitance_f is not None:
        out = OUTPUT_DIR
        out.mkdir(parents=True, exist_ok=True)
        try:
            from sim import netlist as netlist_generator
        except ImportError:  # pragma: no cover - direct execution from sim/
            import netlist as netlist_generator

        generated_netlist = netlist_generator.generate_netlist(
            circuit_type=direct_topology,
            R=float(output_dir),
            C=float(capacitance_f),
            L=None,
            output_dir=out,
        )
        net = Path(generated_netlist)
    else:
        out = Path(output_dir)
        net = Path(netlist_path)
    out.mkdir(parents=True, exist_ok=True)
    pcb = out / "circuit.kicad_pcb"
    png = out / "pcb_view.png"
    gerbers = out / "gerbers"
    gerbers.mkdir(parents=True, exist_ok=True)
    gerber_zip = out / "gerbers.zip"

    _draw_pcb_preview(net, png, actual_fc=actual_fc)

    if shutil.which("kicad-cli") is None:
        _warn("kicad-cli not available; generated PCB preview only; skipping Gerber export.")
        return {"pcb": str(pcb), "pcb_png": str(png), "gerbers": ""}

    try:
        _write_minimal_board(net, pcb)
        _run([
            "kicad-cli", "pcb", "export", "gerbers",
            "--output", str(gerbers),
            "--layers", "F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts",
            str(pcb),
        ])
        _zip_gerbers(gerbers, gerber_zip)
    except (subprocess.CalledProcessError, OSError) as exc:
        stderr = getattr(exc, "stderr", "") or str(exc)
        _warn(f"kicad-cli Gerber export failed; keeping matplotlib PCB preview. {stderr}")
        return {"pcb": str(pcb), "pcb_png": str(png), "gerbers": ""}

    return {
        "pcb": str(pcb),
        "pcb_png": str(png),
        "gerbers": str(gerber_zip),
    }


def main() -> int:
    result: dict[str, Any] | None = run_pcb_export()
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
