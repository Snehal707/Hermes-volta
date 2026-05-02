import sys
sys.path.insert(0, "/mnt/c/Users/ASUS/HermesVolta")
from sim.faraday_pipeline import run

result = run(
    circuit_type="RC_LOWPASS",
    R=1600,
    C=100e-9,
    supply_v=5.0,
    L=1e-12,
    fc=1000.0,
    description="1kHz low-pass filter at 5V, 1.6kR+100nF, 0402 SMD"
)

print("=== RESULT ===")
for k, v in result.items():
    print(f"{k}: {v}")
