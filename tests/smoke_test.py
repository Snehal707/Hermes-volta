from __future__ import annotations

import json
import math
import os
import sys
import traceback
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path("/mnt/c/Users/ASUS/HermesVolta")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
SMOKE_ROOT = PROJECT_ROOT / "outputs" / "smoke_test" / RUN_ID
SMOKE_ROOT.mkdir(parents=True, exist_ok=True)

CIRCUITS = [
    {"circuit_type": "RC_LOWPASS", "R": 1600.0, "C": 1e-7, "L": None, "fc": 1000.0},
    {"circuit_type": "RC_HIGHPASS", "R": 1600.0, "C": 1e-7, "L": None, "fc": 1000.0},
    {"circuit_type": "RLC_BANDPASS", "R": 50.0, "C": 1e-7, "L": 1e-3, "fc": 5000.0},
]

REQUIRED_REPORT_FIELDS = [
    "Circuit type:",
    "Date:",
    "Description:",
    "Component Values",
    "R:",
    "C:",
    "Supply:",
    "Error:",
    "Result:",
    "BOM / JLCPCB Search Strings",
    "Ref | Value | Footprint | Search",
    "Output Files",
    "Hermes Memory Entry",
]


def _output_dir(name: str) -> Path:
    path = SMOKE_ROOT / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _existing_file(path: Any) -> bool:
    return bool(path) and Path(str(path)).is_file()


def _require_files(result: dict[str, Any], keys: list[str]) -> None:
    missing = [key for key in keys if not _existing_file(result.get(key))]
    if missing:
        raise AssertionError(f"missing output files for keys: {missing}")


def _result_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "actual_fc": result.get("actual_fc"),
        "error_pct": result.get("error_pct"),
        "output_dir": result.get("output_dir"),
        "bode_path": result.get("bode_path"),
        "wave_path": result.get("wave_path"),
        "netlist": result.get("netlist"),
        "pcb_png": result.get("pcb_png"),
        "gerbers": result.get("gerbers"),
        "report": result.get("report"),
        "compare_plot": result.get("compare_plot"),
    }


def _assert_finite_fc(value: Any) -> None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0:
        raise AssertionError(f"actual_fc is not a positive finite number: {value!r}")


def _design_test(circuit: dict[str, Any]) -> dict[str, Any]:
    from sim.faraday_pipeline import run

    result = run(
        circuit["circuit_type"],
        R=circuit["R"],
        C=circuit["C"],
        L=circuit["L"],
        fc=circuit["fc"],
        supply_v=5.0,
        description=f"Smoke test {circuit['circuit_type']}",
    )
    _assert_finite_fc(result.get("actual_fc"))
    _require_files(result, ["bode_path", "wave_path", "netlist", "pcb_png", "report"])
    if result.get("compare_plot"):
        _require_files(result, ["compare_plot"])
    return _result_summary(result)


def test_rc_lowpass_design() -> dict[str, Any]:
    return _design_test(CIRCUITS[0])


def test_rc_highpass_design() -> dict[str, Any]:
    return _design_test(CIRCUITS[1])


def test_rlc_bandpass_design() -> dict[str, Any]:
    return _design_test(CIRCUITS[2])


def test_batch_simulation() -> dict[str, Any]:
    from sim import simulate

    results = {}
    for circuit in CIRCUITS:
        output_dir = _output_dir(f"batch_{circuit['circuit_type']}")
        result = simulate.run_simulation(
            topology=circuit["circuit_type"],
            resistance_ohm=circuit["R"],
            capacitance_f=circuit["C"],
            inductance_h=circuit["L"],
            source_amplitude_v=5.0,
            output_dir=output_dir,
        )
        _assert_finite_fc(result.get("actual_fc"))
        _require_files(result, ["bode_path", "wave_path"])
        results[circuit["circuit_type"]] = result
    return {
        name: {
            "actual_fc": value.get("actual_fc"),
            "bode_path": value.get("bode_path"),
            "wave_path": value.get("wave_path"),
        }
        for name, value in results.items()
    }


def test_sweep_optimizer() -> dict[str, Any]:
    from sim.sweep_optimizer import cutoff_hz, find_best_e24_r

    best_r = find_best_e24_r(1000.0, 1e-7)
    actual_fc = cutoff_hz(best_r, 1e-7)
    if best_r != 1600.0:
        raise AssertionError(f"expected 1600.0 ohm, got {best_r}")
    return {"best_r": best_r, "actual_fc": actual_fc}


def test_monte_carlo() -> dict[str, Any]:
    from sim.monte_carlo import run_monte_carlo

    summary = run_monte_carlo(1600.0, 1e-7, 1000.0, iterations=100)
    if summary.mean_hz <= 0 or summary.max_hz < summary.min_hz:
        raise AssertionError(f"invalid Monte Carlo summary: {summary}")
    return {
        "mean_hz": summary.mean_hz,
        "std_hz": summary.std_hz,
        "min_hz": summary.min_hz,
        "max_hz": summary.max_hz,
        "within_5pct": summary.within_5pct,
    }


def test_compare_plot() -> dict[str, Any]:
    from sim.compare_plot import generate_compare_plot

    results = {}
    for circuit in CIRCUITS[:2]:
        output_dir = _output_dir(f"compare_{circuit['circuit_type']}")
        path = generate_compare_plot(
            output_dir=str(output_dir),
            circuit_type=circuit["circuit_type"],
            R=circuit["R"],
            C=circuit["C"],
            fc=circuit["fc"],
            supply_v=5.0,
        )
        if not path.is_file():
            raise AssertionError(f"compare plot missing: {path}")
        results[circuit["circuit_type"]] = str(path)
    return results


def test_netlist_generation() -> dict[str, Any]:
    from sim.netlist import generate_netlist

    results = {}
    for circuit in CIRCUITS:
        output_dir = _output_dir(f"netlist_{circuit['circuit_type']}")
        path = generate_netlist(
            circuit_type=circuit["circuit_type"],
            R=circuit["R"],
            C=circuit["C"],
            L=circuit["L"],
            supply_v=5.0,
            output_dir=output_dir,
        )
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        for required in ("<export", "components", "nets", "R1", "C1"):
            if required not in text:
                raise AssertionError(f"{required!r} missing from {path}")
        if circuit["circuit_type"].startswith("RLC") and "L1" not in text:
            raise AssertionError(f"'L1' missing from {path}")
        results[circuit["circuit_type"]] = path
    return results


def test_pcb_export() -> dict[str, Any]:
    from sim.netlist import generate_netlist
    from sim.pcb_export import run_pcb_export

    results = {}
    for circuit in CIRCUITS:
        output_dir = _output_dir(f"pcb_{circuit['circuit_type']}")
        netlist_path = generate_netlist(
            circuit["circuit_type"],
            R=circuit["R"],
            C=circuit["C"],
            L=circuit["L"],
            supply_v=5.0,
            output_dir=output_dir,
        )
        result = run_pcb_export(netlist_path, output_dir=output_dir, actual_fc=circuit["fc"])
        if not _existing_file(result.get("pcb_png")):
            raise AssertionError(f"PCB preview missing for {circuit['circuit_type']}: {result}")
        results[circuit["circuit_type"]] = result
    return results


def test_report_generation() -> dict[str, Any]:
    from sim.report import write_report

    output_dir = _output_dir("report_RLC_BANDPASS")
    params = {
        "circuit_type": "RLC_BANDPASS",
        "R": 50.0,
        "C": 1e-7,
        "L": 1e-3,
        "supply_v": 5.0,
        "fc": 5000.0,
        "description": "Smoke report field check",
    }
    sim_results = {
        "actual_fc": 5000.0,
        "bode_path": str(output_dir / "frequency_response.png"),
        "wave_path": str(output_dir / "waveform.png"),
        "netlist": str(output_dir / "circuit.net"),
        "pcb_png": str(output_dir / "pcb_view.png"),
        "gerbers": str(output_dir / "gerbers.zip"),
    }
    path = write_report(params, sim_results, output_dir=output_dir)
    text = Path(path).read_text(encoding="utf-8")
    missing = [field for field in REQUIRED_REPORT_FIELDS if field not in text]
    missing.extend(
        field
        for field in (
            "Hermes Volta Bandpass Report",
            "Bandpass Center Frequency",
            "Target f0:",
            "Theory f0:",
            "Actual f0:",
        )
        if field not in text
    )
    if "L:" not in text:
        missing.append("L:")
    if missing:
        raise AssertionError(f"report missing fields: {missing}")
    return {"report": path, "fields_checked": len(REQUIRED_REPORT_FIELDS) + 1}


def _load_dotenv(path: Path) -> dict[str, str]:
    values = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def test_telegram_delivery() -> dict[str, Any]:
    env = {**_load_dotenv(Path.home() / ".hermes" / ".env"), **os.environ}
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_HOME_CHANNEL", "")
    if not token or not chat_id:
        raise AssertionError("TELEGRAM_BOT_TOKEN or TELEGRAM_HOME_CHANNEL missing from ~/.hermes/.env")

    message = "🧪 Hermes Volta smoke test — all systems operational"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
    data = json.loads(body)
    if data.get("ok") is not True:
        raise AssertionError(f"Telegram response was not ok:true: {data}")
    return {"ok": data.get("ok"), "chat_id": chat_id, "message_id": data.get("result", {}).get("message_id")}


def _nearest_index(values: Any, target: float) -> int:
    return min(range(len(values)), key=lambda index: abs(float(values[index]) - target))


def _phase_error_deg(actual: float, expected: float) -> float:
    return abs((actual - expected + 180.0) % 360.0 - 180.0)


def test_mathematical_accuracy() -> dict[str, Any]:
    from sim import simulate

    details = {}
    failures = []
    for circuit in CIRCUITS:
        topology = circuit["circuit_type"]
        spec = simulate.SimulationSpec(
            topology=topology,
            resistance_ohm=circuit["R"],
            capacitance_f=circuit["C"],
            inductance_h=circuit["L"],
            source_amplitude_v=5.0,
        )
        built_circuit, output_node = simulate.build_circuit(spec)
        ac = simulate.normalize_magnitude(topology, simulate.run_ac(built_circuit, output_node))
        actual_fc = simulate.actual_frequency(topology, ac["frequency_hz"], ac["magnitude_db"])

        if topology in {"RC_LOWPASS", "RC_HIGHPASS"}:
            theory_fc = 1.0 / (2.0 * math.pi * circuit["R"] * circuit["C"])
            fc_index = _nearest_index(ac["frequency_hz"], theory_fc)
            reference_index = 0 if topology == "RC_LOWPASS" else len(ac["frequency_hz"]) - 1
            phase_expected = -45.0 if topology == "RC_LOWPASS" else 45.0
            phase_at_fc = float(ac["phase_deg"][fc_index])
            phase_error = _phase_error_deg(phase_at_fc, phase_expected)
            if phase_error >= 5.0:
                failures.append(f"{topology} phase at fc {phase_at_fc:.3f} deg outside 5 deg of {phase_expected:g}")
        else:
            theory_fc = 1.0 / (2.0 * math.pi * math.sqrt(circuit["L"] * circuit["C"]))
            fc_index = _nearest_index(ac["frequency_hz"], theory_fc)
            reference_index = max(range(len(ac["magnitude_db"])), key=lambda index: float(ac["magnitude_db"][index]))
            phase_at_fc = float(ac["phase_deg"][fc_index])
            phase_error = None

        fc_error = abs(actual_fc - theory_fc) / theory_fc
        reference_mag = float(ac["magnitude_db"][reference_index])
        mag_at_fc = float(ac["magnitude_db"][fc_index])

        if fc_error >= 0.05:
            failures.append(f"{topology} actual_fc error {fc_error:.3%} is not within 5%")
        if abs(reference_mag) > 0.5:
            failures.append(f"{topology} reference magnitude {reference_mag:.3f} dB is not within 0.5 dB of 0 dB")
        if abs(mag_at_fc + 3.0103) > 1.0 and topology in {"RC_LOWPASS", "RC_HIGHPASS"}:
            failures.append(f"{topology} magnitude at fc {mag_at_fc:.3f} dB is not within 1 dB of -3 dB")
        if topology == "RLC_BANDPASS" and abs(mag_at_fc) > 1.0:
            failures.append(f"{topology} magnitude at center {mag_at_fc:.3f} dB is not within 1 dB of 0 dB")

        details[topology] = {
            "theory_fc": theory_fc,
            "actual_fc": actual_fc,
            "fc_error_pct": fc_error * 100.0,
            "reference_magnitude_db": reference_mag,
            "magnitude_at_fc_db": mag_at_fc,
            "phase_at_fc_deg": phase_at_fc,
            "phase_error_deg": phase_error,
        }

    if failures:
        raise AssertionError("; ".join(failures))
    return details


def _http_json(url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=data, headers=request_headers, method="GET" if data is None else "POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw": body}


def _firecrawl_search(api_url: str, api_key: str, query: str) -> dict[str, Any]:
    base = api_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    errors = []
    payloads = [
        {"query": query, "limit": 3},
        {"query": query, "limit": 3, "pageOptions": {"fetchPageContent": False}},
    ]
    for endpoint in ("/v1/search", "/search"):
        for payload in payloads:
            try:
                result = _http_json(f"{base}{endpoint}", payload=payload, headers=headers)
                if result.get("success") is True or result.get("data") or result.get("results"):
                    return {"endpoint": endpoint, "response": result}
                errors.append(f"{endpoint}: empty response {result}")
            except Exception as exc:
                errors.append(f"{endpoint}: {type(exc).__name__}: {exc}")
    raise AssertionError("; ".join(errors))


def _firecrawl_health(api_url: str) -> dict[str, Any]:
    base = api_url.rstrip("/")
    errors = []
    for endpoint in ("/health", "/v1/health", "/"):
        try:
            result = _http_json(f"{base}{endpoint}")
            return {"endpoint": endpoint, "response": result}
        except Exception as exc:
            errors.append(f"{endpoint}: {type(exc).__name__}: {exc}")
    raise AssertionError("; ".join(errors))


def test_web_search_availability() -> dict[str, Any]:
    env = {**_load_dotenv(Path.home() / ".hermes" / ".env"), **os.environ}
    api_url = env.get("FIRECRAWL_API_URL", "")
    api_key = env.get("FIRECRAWL_API_KEY", "")
    if not api_url:
        raise AssertionError("FIRECRAWL_API_URL missing from ~/.hermes/.env")

    health = _firecrawl_health(api_url)
    search = _firecrawl_search(api_url, api_key, "Hermes Volta circuit smoke test")
    response = search["response"]
    result_count = len(response.get("data") or response.get("results") or [])
    if result_count <= 0:
        raise AssertionError(f"Firecrawl search returned no results: {response}")
    return {"api_url": api_url, "health": health, "endpoint": search["endpoint"], "result_count": result_count}


TESTS: list[tuple[str, Callable[[], Any]]] = [
    ("1. RC_LOWPASS design", test_rc_lowpass_design),
    ("2. RC_HIGHPASS design", test_rc_highpass_design),
    ("3. RLC_BANDPASS design", test_rlc_bandpass_design),
    ("4. Batch simulation", test_batch_simulation),
    ("5. sweep_optimizer", test_sweep_optimizer),
    ("6. monte_carlo", test_monte_carlo),
    ("7. compare_plot", test_compare_plot),
    ("8. netlist generation", test_netlist_generation),
    ("9. pcb_export", test_pcb_export),
    ("10. report generation", test_report_generation),
    ("11. Telegram delivery test", test_telegram_delivery),
    ("12. Mathematical accuracy test", test_mathematical_accuracy),
    ("13. Web search availability test", test_web_search_availability),
]


def main() -> int:
    print(f"Hermes Volta smoke test output: {SMOKE_ROOT}")
    passed = 0
    for name, test_func in TESTS:
        print(f"\n{name}")
        try:
            result = test_func()
            passed += 1
            print("PASS")
            print(f"Result: {result}")
        except Exception as exc:
            print("FAIL")
            print(f"Result: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    total = len(TESTS)
    print(f"\n{passed}/{total} tests passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
