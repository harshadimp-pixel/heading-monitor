# Architecture (v0.1, PM & CTO)

```mermaid
flowchart LR
  SIM[sim/ simulator] -->|Sample JSONL| CORE
  REPLAY[recorded log replay] -->|Sample JSONL| CORE
  FC[Matek FC + RM3100] -->|MSP/MAVLink| BRIDGE[firmware_bridge/] -->|Sample JSONL| CORE
  CORE[heading_core/ calibration + tilt-comp heading + filter] --> APP[app/ backend + web UI]
```

## Data flow
1. A **source** (sim, replay, or hardware bridge) yields `Sample` objects (see `contracts/sample.schema.json`).
   Transport: newline-delimited JSON over stdout, a file, or TCP `localhost:5760`-style socket.
2. `heading_core` turns samples into `HeadingEstimate` objects (see `contracts/heading_estimate.schema.json`).
3. `app` shows heading (compass rose + numeric), raw/calibrated field, field magnitude, tilt,
   calibration quality, interference warnings, and the source badge.

## Python interfaces (must exist)
```python
# heading_core/__init__.py
class Calibration:            # hard-iron offset (3,), soft-iron matrix (3x3)
    def apply(self, mag_uT) -> list[float]: ...
    @staticmethod
    def fit(samples_uT: list[list[float]]) -> "Calibration": ...   # ellipsoid fit
    def to_dict(self) -> dict; @staticmethod
    def from_dict(d) -> "Calibration": ...

def tilt_compensated_heading(mag_uT, accel_g, declination_deg=0.0) -> float  # deg 0..360, true if decl given
class HeadingEstimator:
    def __init__(self, calibration: Calibration | None = None, declination_deg: float = 0.0): ...
    def update(self, sample: dict) -> dict   # returns HeadingEstimate dict

# sim/ :  python -m sim --rate 50 --duration 60 --scenario <name> [--seed N]  -> JSONL Samples on stdout
# firmware_bridge/ : python -m firmware_bridge --port /dev/ttyACM0 --baud 115200 -> JSONL Samples
#                    (must also support --replay <file> and must emit source="hardware" only from a live port)
# app/ : python -m app --source sim|replay:<file>|serial:<port>   -> serves UI on http://localhost:8080
```

## Frames and units
- Body frame NED-style: x forward, y right, z down. Magnetic field in microtesla (µT). Accel in g. Gyro in deg/s.
- Heading: degrees clockwise from magnetic north (or true north when declination applied), range [0, 360).
- Accelerometer is specific force in g: level and at rest reads (0, 0, -1) in the NED body frame (z down). Firmware bridge must convert FC output to this convention.
- RM3100 raw counts are carried alongside µT when available, with the cycle-count used for conversion.

## Decisions log
- 2026-11-26: Python reference implementation, web UI served locally; JSONL sample contract as the single seam
  between sources and core so sim and hardware are interchangeable.
- 2026-11-27: jsonschema added to requirements. Sim may add extra `truth` keys (true_heading_deg, earth_field_body_uT, field_at_sensor_uT, interference_uT, motor_current_A, declination_deg); `truth.heading_deg` is magnetic heading. Run config carried in the first line's `meta` only. Accel sign convention fixed as above.
- 2026-11-27: Hardware target per T1 is the Matek CAN-L4-3100 module (RM3100 behind AP_Periph); FC receives scaled field (DroneCAN Gauss / MSP mG), not raw counts. `mag_raw` is optional and absent on hardware.
- 2026-11-27 (PM, on T2 review): Warning codes frozen as contract: NOT_CALIBRATED, FIELD_MAGNITUDE_OUT_OF_RANGE, TILT_TOO_LARGE, NO_ACCEL, DIP_ANGLE_ANOMALY, HIGH_NOISE, INVALID_MAG, SENSOR_STALE, MAG_STALE, TIMESTAMP_STALE. New codes need PM sign-off.
- 2026-11-27: Approved optional kwargs `HeadingEstimator(config=CoreConfig)` and `tilt_compensated_heading(..., accel_convention="specific_force")` (defaults preserve the interface above).
- 2026-11-27: Single-calibration rule. The app's ellipsoid calibration is the only calibration. Hardware setup keeps the FC's mag calibration neutral (INAV magzero=0, maggain=1024). The bridge reports `meta.fc_mag_calibrated` (true/false/unknown); the app warns if not false.
- 2026-11-27: Quantised sources. A source whose mag is quantised sets `meta.mag_quant_uT` (MSP: 0.1). When that step is >= 3x the expected noise, MAG_STALE uses bit-identical readings over a longer window (CoreConfig, default 5 s) and does not cut quality below 0.3x. SENSOR_STALE and TIMESTAMP_STALE are unchanged. Thresholds are provisional until a hardware replay log exists.
