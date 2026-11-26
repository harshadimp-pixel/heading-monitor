# Test Results

Only tests that were actually executed appear here, with command, date, environment and raw outcome.
Every result carries an evidence label. Maintained by the Testing & Technical Auditor (summary). Detail is in reports/verification_report.md and reports/audit/.

Environment: Linux box, Python 3.13.5. Clean venv built from `requirements.txt` (numpy 2.5.5, pytest 9.2.0, jsonschema 4.26.0), plus pyserial; Google Chrome 156 headless; Node.
Code: clean `git archive <sha>` exports (never the shared working tree), plus T6 `tests/` as committed with this file. Latest run by T6 on 2026-11-27, 00:40–01:10 IST.

## Latest run (final verification v2.0)
| Date (IST) | Test / suite | Command | Commit | Result | Evidence |
|---|---|---|---|---|---|
| 2026-11-27 01:05 | **Whole repo** (all owner suites + T6) | `python -m pytest -q -rs` (repo root) | dc3123a | **506 passed, 44 skipped, 0 failed** | [SIMULATED] |
| 2026-11-27 00:50 | Whole repo (check of PM claim 499/45) | `python -m pytest -q` | c942d6f | 501 passed, 44 skipped (= PM's 499 + 2 new T6 tests; PM's 45th skip = pty serial test without pyserial) | [SIMULATED] |
| 2026-11-27 00:55 | heading_core owner suite | `python -m pytest heading_core/tests -q` | 471724e | 76 passed | [SIMULATED] |
| 2026-11-27 00:55 | sensor-spec | `python -m pytest docs/math/sensor-spec -q` | 471724e | 23 passed | [SIMULATED] |
| 2026-11-27 00:55 | sim owner suite | `python -m pytest sim/tests -q` | 471724e | 152 passed, 44 skipped (spec-check N/A) | [SIMULATED] |
| 2026-11-27 00:55 | firmware_bridge owner suite | `python -m pytest firmware_bridge/tests -q` | 471724e | 95 passed | [SIMULATED] |
| 2026-11-27 00:55 | app owner suite | `python -m pytest app/tests -q` | 471724e | 45 passed | [SIMULATED] |
| 2026-11-27 01:05 | T6 independent suite | `python -m pytest tests -q -s` | dc3123a | 111 passed | [SIMULATED] |
| 2026-11-27 00:50 | D3 re-test: E3b stress 20×60 s | `pytest tests/test_t6_stale_quant.py -s` | c942d6f | 0/20 falsely stale (was 4/20 at 1befc7b) → D3 closed | [SIMULATED] |
| 2026-11-27 00:50 | Frozen-sensor regression matrix F1–F10 | `python reports/audit/raw/d3_regress.py` | c942d6f | F1–F5, F7, F8 flagged (0.2–1.7 s); F6, F9, F10 not flagged (documented limitation 14a) | [SIMULATED] |
| 2026-11-27 00:55 | **Integrated end-to-end** A1–A9 | `python reports/audit/integration_run.py <export> <out>` | 471724e | **25/27 PASS; FAIL A8, A8b → D6 (CRITICAL)** | [SIMULATED]/[REPLAYED] |
| 2026-11-27 01:05 | Claims audit | `pytest tests/test_t6_claims.py -s` | dc3123a | 4 passed; 0 applied hardware tags, 30 mentions, 0 nav claims | n/a |

## Earlier runs (history)
| Date (IST) | Test / suite | Command | Commit | Result | Evidence | Run by |
|---|---|---|---|---|---|---|
| 2026-11-27 | T6 independent suite (all) | `python -m pytest tests -q -s` | 403976b | **102 passed, 2 failed** (both are E3b → D3) | [SIMULATED] | T6 |
| 2026-11-27 | heading_core owner suite | `python -m pytest heading_core/tests` | 403976b | 59 passed | [SIMULATED] | T6 |
| 2026-11-27 | math sensor-spec | `python -m pytest docs/math/sensor-spec` | 403976b | 23 passed | [SIMULATED] | T6 |
| 2026-11-27 | sim owner suite | `python -m pytest sim/tests` | 403976b | 80 passed | [SIMULATED] | T6 |
| 2026-11-27 | firmware_bridge owner suite | `python -m pytest firmware_bridge/tests` | 403976b | 64 passed, 1 skipped (no pyserial); 65 passed with pyserial | [SIMULATED] hand-built frames | T6 |
| 2026-11-27 | app owner suite | `python -m pytest app/tests` | 403976b | 40 passed | [SIMULATED] | T6 |
| 2026-11-27 | T6 independent suite (all, incl. E3b stress) | `python -m pytest tests -q -s` | 0aaa066 | **104 passed, 1 failed** (E3b stress, D3) | [SIMULATED] | T6 |
| 2026-11-27 | heading_core / sensor-spec / sim / firmware_bridge / app owner suites | `python -m pytest <suite>` | 0aaa066 | 67 / 23 / 80 / 65 / 40 passed | [SIMULATED] | T6 |
| 2026-11-27 | firmware_bridge owner suite | same | 997d00f | 41 passed, 1 skipped | [SIMULATED] | T6 |
| 2026-11-27 | T6 MSP replay of malformed Sample JSONL | `tests/test_t6_msp.py::test_M3_replay_malformed_sample_lines` | 997d00f → 403976b | FAIL (2/3 invalid emitted) → PASS | [SIMULATED] | T6 |

Key numbers [SIMULATED]:
- **Heading:** level error ≤ 0.01°; tilt ±30° noise-free ≤ 0.1°; noisy tilt RMSE 0.628° (max 2.317°).
- **Calibration:** hard iron recovered to ≤ 0.004 µT; calibrated heading 0.354° vs 82.4° uncalibrated.
- **End-to-end RMSE** (5 seeds, mean±std): static 0.371±0.254°, yaw_spin 0.527±0.241°, tilted_spin 0.549±0.226°, hard_iron 0.528±0.243°, soft_iron 0.527±0.242°, high_noise 0.846±0.229°. motor_interference 16.3° (flagged).
- **Repeatability:** spread 0.0° on identical input; sim output byte-identical per seed.
- **MSP fuzz** (2000 streams): 98.8 % of valid frames recovered; 0 corrupted frames leaked into samples.
- **Dashboard:** display vs core diff 0.0°; badge matched sample.source 10/10; 359.96 → "0.0".
- **E3b (D3):** at 15 nT [DATASHEET] noise with 0.1 µT quantisation. At 403976b: 55/600 samples falsely MAG_STALE. At 0aaa066: the single session is clean, but 4/20 sixty-second sessions are falsely stale.

Inputs: [DATASHEET] RM3100 noise 15 nT and gain 75 LSB/µT (PNI UM Table 3-1). All IMU, interference and field parameters are [ASSUMED]; see verification_report.md §3.
