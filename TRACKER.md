# Task Tracker  (owner: PM & CTO; each owner updates own rows)

Status: TODO / IN-PROGRESS / BLOCKED / REVIEW / DONE

| ID | Task | Owner | Depends on | Status | Notes |
|---|---|---|---|---|---|
| T1 | Hardware fact sheet: RM3100 (interface, cycle counts, gain, noise, ranges), Matek FC models & compass support in INAV/ArduPilot/Betaflight, wiring, sources -> `docs/hardware/` | Hardware Research Engineer | - | TODO | label every number [DATASHEET] with source URL |
| T2 | Heading math + calibration library `heading_core/` (ellipsoid hard/soft-iron fit, tilt comp, declination, smoothing w/ wrap-around, quality metric) + `docs/math/` derivation, unit tests | Mathematics & Sensor Scientist | T1 (soft) | TODO | follow ARCHITECTURE.md interfaces |
| T3 | Sensor simulator `sim/`: RM3100 + FC IMU, scenarios (static, slow yaw spin, tilted spin, hard/soft iron, motor interference, noise), ground truth, seeded | Simulation Developer | T1 (soft) | TODO | emits Sample JSONL; source="sim" |
| T4 | FC telemetry bridge `firmware_bridge/` (MSP over USB: MSP_RAW_IMU / MSP_ATTITUDE; MAVLink optional) + `docs/firmware/` FC config steps for RM3100 on Matek | Firmware Specialist | T1 | TODO | test against recorded/synthetic MSP frames; source="hardware" only from a live port |
| T5 | Heading-monitor app `app/`: backend + local web UI (compass, numbers, field, tilt, calibration wizard, warnings, source badge), `--source sim|replay|serial` | UI & Software Developer | T2, T3 (contracts first) | TODO | start with contracts + stub data |
| T6 | Independent test plan, integration tests, accuracy runs vs sim truth, claims audit, `reports/verification_report.md` | Testing & Technical Auditor | T2-T5 | TODO | write test plan now; must not test own code |
| T7 | Integration, review, consolidated report to owner | PM & CTO | T1-T6 | IN-PROGRESS | |

## Change log
- 2026-11-26 PM: repo, contracts, tracker created.
