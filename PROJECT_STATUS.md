# Project Status — Virtual Heading Monitor (RM3100 + Matek FC)

**Last updated:** 2026-11-27 12:03 IST by PM & CTO
**Overall:** 🟡 IN PROGRESS — T1–T6 are in IN-PROGRESS/REVIEW. CRITICAL defect D8 is OPEN. T7 is DONE. No result is [HARDWARE-VERIFIED].

## Phase
| Phase | Status |
|---|---|
| 0. Scaffold repo, contracts, rules | DONE |
| 1. Research + core modules (T1–T4) | REVIEW |
| 2. Application (T5) | REVIEW (D8 CRITICAL OPEN) |
| 3. Independent verification (T6) | IN PROGRESS |
| 4. Integration + consolidated report (T7) | DONE |

## Tasks
| ID | Status | Summary |
|---|---|---|
| T1 | REVIEW | `docs/hardware/FACTSHEET.md` (+ key_numbers.json, SOURCES.md). 75 LSB/uT @CC200; our CAN-L4-3100 delivers DroneCAN float16 Gauss <=25 Hz or MSP int16 mG; INAV needs MSP (no DroneCAN mag); exact FC model UNKNOWN. Audit… |
| T2 | REVIEW | Done: heading_core (Calibration ellipsoid/sphere fit, tilt_compensated_heading, HeadingEstimator w/ complementary+gyro or circular-mean smoothing, quality 0..1, warnings), 76 unit tests pass; D3 fixed (quantised… |
| T3 | REVIEW | `python -m sim --rate 50 --duration 60 --scenario <name> --seed N [--out f.jsonl] [--output-mode raw/dronecan/msp]`; 8 scenarios; 7 example logs in sim/examples/ (5 raw + 1 dronecan + 1 msp); `pytest sim/tests` 152… |
| T4 | REVIEW | `python -m firmware_bridge --port P --baud 115200` (source=hardware) / `--replay F` (replay: Sample JSONL, --capture JSONL, raw MSP bytes) / `--fake-fc` (sim); MSPv1/v2/v2-over-v1, read-only requests only; `pytest… |
| T5 | REVIEW | `python -m app --source sim[:scenario]/replay:<file>/serial:<port>/ingest` -> http://localhost:8080. Stdlib HTTP + RFC6455 WebSocket, vanilla JS/SVG/canvas, no new deps. Uses real heading_core (T2) + sim (T3) via… |
| T6 | IN-PROGRESS | v4 (D8 re-verification) in progress: D8 (CRITICAL) filed; A10c rewritten; D8 regression tests and skipped_tests.md added. Previous: FINAL v3.0 (2026-11-27 ~01:30 IST, D6 re-test): OVERALL PASS (virtual scope only);… |
| T7 | DONE | reports/FINAL_REPORT.md; official T6 verdict PASS (virtual scope only), completion APPROVED for that scope; D6 CLOSED; D7 wording updated (REVIEW); hardware validation NOT RUN |
| T8 | IN-PROGRESS | owner assigned this role 2026-11-26; no code ownership |

## Unresolved defects
| ID | Severity | Status | Summary |
|---|---|---|---|
| D8 | CRITICAL | OPEN | Defect (CRITICAL, per TEST_PLAN: wrong source badge; from Codex audit of f1a0e3e, PM decision ARCHITECTURE.md D8 1bef73e): a serial connection is treated as proof of hardware. `app --source serial:<port>` labels every sample HARDWARE + 'Live hardware samples' whenever the… |
| D9 | MINOR | REVIEW | Defect (MINOR, test labelling / N4 wording; from the ChatGPT D8 review at e538cea): app/tests/test_app_d8_serial_provenance.py::test_e2e_bridge_over_pty drives a FakeFC on a virtual pty reporting INAV/MKF4 + an allowlisted UID and asserts device_status 'verified' /… |

## Closed defects
D1 (MAJOR, CLOSED), D2 (MINOR, CLOSED), D3 (MAJOR, CLOSED), D4 (MAJOR, CLOSED), D5 (MINOR, CLOSED), D6 (CRITICAL, CLOSED), D7 (MINOR, CLOSED).

## Open blockers
| ID | Status | Summary |
|---|---|---|
| B1 | OPEN (accepted for virtual phase) | No physical RM3100 + Matek FC is connected to the project environment |
| B2 | OPEN | Exact Matek FC model and firmware (INAV/ArduPilot/Betaflight) on the team's board unknown |
| B3 | OPEN (non-blocking) | firmware_bridge cannot undo INAV's mag calibration normalisation: after INAV mag calibration, MSP_RAW_IMU mag = (m − magzero)·1024/maggain (INAV `sensors/compass.c` L560), i.e. dimensionless, not mGauss |
| B4 | OPEN (non-blocking) | INAV 10 is still a release candidate (10.0.0-rc2, 2026-09-29; stable planned December 2026); DroneCAN code exists only on `maintenance-10.x`, with no DroneCAN magnetometer |

## Evidence status
- Hardware-verified results: **none**. No committed hardware log and auditor sign-off exist, so nothing is labelled [HARDWARE-VERIFIED].
- All performance figures and executed tests are [SIMULATED] unless explicitly labelled otherwise.
- Latest whole-repo / featured run (2026-11-27 01:25 IST, 0c25062 (HEAD)): **513 passed, 44 skipped, 0 failed** [SIMULATED].
- **Integrated end-to-end A1–A10** (incl. D6 A8/A8b, edge cases A10a–c, headless…: **30/30 PASS** → D6 CLOSED [SIMULATED]/[REPLAYED].

See TEAM_TRACKER.md for per-task detail, BLOCKERS.md for open issues, TEST_RESULTS.md for executed tests.
