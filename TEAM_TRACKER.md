# Task Tracker  (owner: PM & CTO; each owner updates own rows)

Status: TODO / IN-PROGRESS / BLOCKED / REVIEW / DONE

| ID | Task | Owner | Depends on | Status | Notes |
|---|---|---|---|---|---|
| T1 | Hardware fact sheet: RM3100 (interface, cycle counts, gain, noise, ranges), Matek FC models & compass support in INAV/ArduPilot/Betaflight, wiring, sources -> `docs/hardware/` | Hardware Research Engineer | - | REVIEW | `docs/hardware/FACTSHEET.md` (+ key_numbers.json, SOURCES.md). 75 LSB/uT @CC200; our CAN-L4-3100 delivers DroneCAN float16 Gauss <=25 Hz or MSP int16 mG; INAV needs MSP (no DroneCAN mag); exact FC model UNKNOWN. Limitations L1-L15 below |
| T2 | Heading math + calibration library `heading_core/` (ellipsoid hard/soft-iron fit, tilt comp, declination, smoothing w/ wrap-around, quality metric) + `docs/math/` derivation, unit tests | Mathematics & Sensor Scientist | T1 (soft) | IN-PROGRESS | interface stubs committed (importable); impl in progress. Nominal field 50 uT (CoreConfig) until T1. Proposed warning codes in heading_core/warnings_codes.py (PM to confirm) |
| T3 | Sensor simulator `sim/`: RM3100 + FC IMU, scenarios (static, slow yaw spin, tilted spin, hard/soft iron, motor interference, noise), ground truth, seeded | Simulation Developer | T1 (soft) | TODO | emits Sample JSONL; source="sim" |
| T4 | FC telemetry bridge `firmware_bridge/` (MSP over USB: MSP_RAW_IMU / MSP_ATTITUDE; MAVLink optional) + `docs/firmware/` FC config steps for RM3100 on Matek | Firmware Specialist | T1 | IN-PROGRESS | test against recorded/synthetic MSP frames; source="hardware" only from a live port |
| T5 | Heading-monitor app `app/`: backend + local web UI (compass, numbers, field, tilt, calibration wizard, warnings, source badge), `--source sim|replay|serial` | UI & Software Developer | T2, T3 (contracts first) | IN-PROGRESS | stdlib HTTP+WebSocket backend, vanilla JS UI; local stubs behind ARCHITECTURE.md interfaces until T2/T3/T4 land |
| T6 | Independent test plan, integration tests, accuracy runs vs sim truth, claims audit, `reports/verification_report.md` | Testing & Technical Auditor | T2-T5 | TODO | write test plan now; must not test own code |
| T7 | Integration, review, consolidated report to owner | PM & CTO | T1-T6 | IN-PROGRESS | |
| T8 | Group-chat hub: route questions to the right specialist, consolidate answers, record decisions for the owner | All group bot Work project | - | IN-PROGRESS | owner assigned this role 2026-11-26; no code ownership |

## Change log
- 2026-11-26 PM: repo, contracts, tracker created.
- 2026-11-26 HW: T1 started (IN-PROGRESS).
- 2026-11-26 FW: T4 started (IN-PROGRESS).
- 2026-11-26 UI: T5 started (IN-PROGRESS).
- 2026-11-27 Hub: T8 added (IN-PROGRESS).
- 2026-11-27 HW: T1 -> REVIEW (FACTSHEET.md, key_numbers.json, SOURCES.md).

## Limitations — T1 Hardware (mirrors docs/hardware/FACTSHEET.md §8)
- L1 Exact Matek FC model + FC firmware UNKNOWN (candidate list only; see BLOCKERS B2).
- L2 No hardware verification; all numbers DATASHEET / OFFICIAL-DOC / SOURCE-CODE / DERIVED.
- L3 RM3100 gain/noise published only for cycle counts 50/100/200.
- L4 Range conflict: +/-800 uT (PNI manual) vs +/-1100 uT (PNI product page / sales sheet).
- L5 PNI manual internal inconsistencies (SA0/SA1 mapping, DRDM width, CMM 0x79 example, ~430 Hz vs 147 Hz 3-axis).
- L6 REVID 0x22 known only from INAV source, not PNI docs.
- L7 PNI "noise": RMS vs peak-to-peak not stated.
- L8 CAN-L4-3100 actual MSP / DroneCAN output rates on our unit UNKNOWN (DroneCAN capped at 25 Hz in code).
- L9 MSP output on the pre-installed MatekL431-GPS firmware is version-dependent / unverified.
- L10 Module output frame and Matek's INAV `align_mag = CW90` rationale unverified (needs a physical rotation test).
- L11 Betaflight DroneCAN mag (added 2026-07, in tag 2026.6.2) untested; inclusion in Matek H743 builds UNKNOWN.
- L12 H743-MINI, F405-HDTE/WMN/MINI-TE, H7A3 boards not verified.
- L13 H743-WING/SLIM V3 specs from reseller copies of Matek pages (cross-checked against ArduPilot hwdef).
- L14 Web sources may change; PDFs not committed (sha256 in docs/hardware/SOURCES.md).
- L15 ArduPilot COMPASS_TYPEMASK -> COMPASS_DISBLMSK rename: first release containing it not identified.
