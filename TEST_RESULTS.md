# Test Results

Only tests that were actually executed appear here, with command, date, environment and raw outcome.
Every result carries an evidence label. Maintained by the Testing & Technical Auditor (summary). Detail is in reports/verification_report.md.

Environment: Linux box, Python 3.13.5. Clean venv built from `requirements.txt` (numpy 2.5.5, pytest 9.2.0, jsonschema 4.26.0), plus pyserial for the bridge's pty test.
Code: `git archive 403976b` export, plus T6 `tests/` (committed with this file). Run by T6 on 2026-11-27 at about 00:30 IST.

| Date (IST) | Test / suite | Command | Commit | Result | Evidence | Run by |
|---|---|---|---|---|---|---|
| 2026-11-27 | T6 independent suite (all) | `python -m pytest tests -q -s` | 403976b | **102 passed, 2 failed** (both are E3b → D3) | [SIMULATED] | T6 |
| 2026-11-27 | heading_core owner suite | `python -m pytest heading_core/tests` | 403976b | 59 passed | [SIMULATED] | T6 |
| 2026-11-27 | math sensor-spec | `python -m pytest docs/math/sensor-spec` | 403976b | 23 passed | [SIMULATED] | T6 |
| 2026-11-27 | sim owner suite | `python -m pytest sim/tests` | 403976b | 80 passed | [SIMULATED] | T6 |
| 2026-11-27 | firmware_bridge owner suite | `python -m pytest firmware_bridge/tests` | 403976b | 64 passed, 1 skipped (no pyserial); 65 passed with pyserial | [SIMULATED] hand-built frames | T6 |
| 2026-11-27 | app owner suite | `python -m pytest app/tests` | 403976b | 40 passed | [SIMULATED] | T6 |
| 2026-11-27 | firmware_bridge owner suite | same | 997d00f | 41 passed, 1 skipped | [SIMULATED] | T6 |
| 2026-11-27 | T6 MSP replay of malformed Sample JSONL | `tests/test_t6_msp.py::test_M3_replay_malformed_sample_lines` | 997d00f → 403976b | FAIL (2/3 invalid emitted) → PASS | [SIMULATED] | T6 |

Key numbers [SIMULATED]:
- **Heading:** level error ≤ 0.01°; tilt ±30° noise-free ≤ 0.1°; noisy tilt RMSE 0.628° (max 2.317°).
- **Calibration:** hard iron recovered to ≤ 0.004 µT; calibrated heading 0.354° vs 82.4° uncalibrated.
- **End-to-end RMSE** (5 seeds, mean±std): static 0.371±0.254°, yaw_spin 0.527±0.241°, tilted_spin 0.549±0.226°, hard_iron 0.528±0.243°, soft_iron 0.527±0.242°, high_noise 0.846±0.229°. motor_interference 16.3° (flagged).
- **Repeatability:** spread 0.0° on identical input; sim output byte-identical per seed.
- **MSP fuzz** (2000 streams): 98.8 % of valid frames recovered; 0 corrupted frames leaked into samples.
- **Dashboard:** display vs core diff 0.0°; badge matched sample.source 10/10; 359.96 → "0.0".
- **E3b (D3):** at 15 nT [DATASHEET] noise with 0.1 µT quantisation, 55/600 samples falsely MAG_STALE.

Inputs: [DATASHEET] RM3100 noise 15 nT and gain 75 LSB/µT (PNI UM Table 3-1). All IMU, interference and field parameters are [ASSUMED]; see verification_report.md §3.
