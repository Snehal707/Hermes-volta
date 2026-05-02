import sys
sys.path.insert(0, "/mnt/c/Users/ASUS/HermesVolta")
from sim.faraday_pipeline import run

result = run(
    circuit_type="RC_HIGHPASS",
    R=20000,
    C=100e-9,
    supply_v=5.0,
    L=1e-12,
    fc=80.0,
    description="Microphone preamp rumble filter: 80Hz RC high-pass, 20kR+100nF, 0402 SMD"
)

print("=== RESULT ===")
for k, v in result.items():
    print(f"{k}: {v}")
