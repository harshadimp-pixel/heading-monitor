# Project Status — Virtual Heading Monitor (RM3100 + Matek FC)

**Last updated:** 2026-11-27 01:16 IST by PM & CTO
**Overall:** 🟡 IN PROGRESS — T1–T6 are in REVIEW. CRITICAL defect D6 is REVIEW (fixed by UI per ARCHITECTURE D6 decision; awaiting T6 re-run of A8/A8b, Auditor closes). T6 final verification is a CONDITIONAL PASS; completion is not approved until D6 is fixed and A8/A8b are re-run green. T7 is IN-PROGRESS. No result is [HARDWARE-VERIFIED].

## Phase
| Phase | Status |
|---|---|
| 0. Scaffold repo, contracts, rules | DONE |
| 1. Research + core modules (T1–T4) | REVIEW |
| 2. Application (T5) | REVIEW (D6 CRITICAL REVIEW (fixed by UI per ARCHITECTURE D6 decision; awaiting T6 re-run of A8/A8b, Auditor closes)) |
| 3. Independent verification (T6) | REVIEW — CONDITIONAL PASS; completion not approved until D6 is fixed |
| 4. Integration + consolidated report (T7) | IN PROGRESS |

## Tasks
| ID | Status | Summary |
|---|---|---|
| T1 | REVIEW | `docs/hardware/FACTSHEET.md` (+ key_numbers.json, SOURCES.md). 75 LSB/uT @CC200; our CAN-L4-3100 delivers DroneCAN float16 Gauss <=25 Hz or MSP int16 mG; INAV needs MSP (no DroneCAN mag); exact FC model UNKNOWN. Audit… |
| T2 | REVIEW | Done: heading_core (Calibration ellipsoid/sphere fit, tilt_compensated_heading, HeadingEstimator w/ complementary+gyro or circular-mean smoothing, quality 0..1, warnings), 76 unit tests pass; D3 fixed (quantised… |
| T3 | REVIEW | `python -m sim --rate 50 --duration 60 --scenario <name> --seed N [--out f.jsonl] [--output-mode raw/dronecan/msp]`; 8 scenarios; 7 example logs in sim/examples/ (5 raw + 1 dronecan + 1 msp); `pytest sim/tests` 152… |
| T4 | REVIEW | `python -m firmware_bridge --port P --baud 115200` (source=hardware) / `--replay F` (replay: Sample JSONL, --capture JSONL, raw MSP bytes) / `--fake-fc` (sim); MSPv1/v2/v2-over-v1, read-only requests only; `pytest… |
| T5 | REVIEW | `python -m app --source sim[:scenario]/replay:<file>/serial:<port>/ingest` -> http://localhost:8080. Stdlib HTTP + RFC6455 WebSocket, vanilla JS/SVG/canvas, no new deps. Uses real heading_core (T2) + sim (T3) via… |
| T6 | REVIEW | FINAL v2.0 (2026-11-27 ~01:15 IST): OVERALL CONDITIONAL PASS (virtual scope), completion NOT APPROVED until D6 fixed + A8/A8b re-run green. Verdicts: T1 PASS, T2 PASS (D3 closed), T3 PASS, T4 PASS, T5 FAIL (D6), PM… |
| T7 | IN-PROGRESS | Integration, review, consolidated report to owner |
| T8 | IN-PROGRESS | owner assigned this role 2026-11-26; no code ownership |

## Unresolved defects
| ID | Severity | Status | Summary |
|---|---|---|---|
| D6 | CRITICAL | REVIEW (fixed by UI per ARCHITECTURE D6 decision; awaiting T6 re-run of A8/A8b, Auditor closes) | Defect (CRITICAL, per TEST_PLAN: wrong source badge): `python -m app --source replay:<file>` with samples `source:"hardware"` shows badge HARDWARE and banner "Live hardware samples." (T6 integration A8/A8b, reports/audit/integration_results.md; DOM… |

## Closed defects
D1 (MAJOR, CLOSED), D2 (MINOR, CLOSED), D3 (MAJOR, CLOSED), D4 (MAJOR, CLOSED), D5 (MINOR, CLOSED).

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
- Latest whole-repo / featured run (2026-11-27 01:05 IST, dc3123a): **506 passed, 44 skipped, 0 failed** [SIMULATED].
- **Integrated end-to-end** A1–A9: **25/27 PASS; FAIL A8, A8b → D6 (CRITICAL)** [SIMULATED]/[REPLAYED].

See TEAM_TRACKER.md for per-task detail, BLOCKERS.md for open issues, TEST_RESULTS.md for executed tests.
