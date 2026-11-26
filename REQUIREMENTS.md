# Requirements (agreed, v1.0 — 2026-11-26)

Source: owner (Harshad Vora) instructions to PM & CTO; refined by PM. Changes require a CHANGELOG entry.

## Functional
- R1. Display a live magnetic heading (0–360°) derived from RM3100 magnetometer data, with numeric value and compass rose.
- R2. Tilt-compensate heading using FC accelerometer/attitude data; show roll and pitch.
- R3. Hard-iron and soft-iron calibration (ellipsoid fit) with an in-app calibration wizard; save/load calibration.
- R4. Optional magnetic declination to report true heading.
- R5. Show field magnitude, 3-axis field, a heading-quality indicator and warnings (interference, excessive tilt, uncalibrated).
- R6. Data sources interchangeable through one Sample contract: simulator, recorded-log replay, live Matek FC over MSP (USB serial).
- R7. Record sessions to JSONL/CSV.
- R8. Persistent DATA SOURCE badge (SIMULATED / REPLAY / HARDWARE) driven only by the sample's `source` field.

## Non-functional
- N1. Runs locally on Linux with Python 3.10+, free/open-source dependencies only.
- N2. All experiments virtual; no hardware purchases or paid services without owner approval.
- N3. Every module executed and tested; independent tests by the Testing & Technical Auditor.
- N4. Evidence labelling: `[SIMULATED]`, `[REPLAYED]`, `[DATASHEET]`, `[HARDWARE-VERIFIED]`. The last needs a committed raw hardware log plus auditor sign-off. No simulated result may be presented as hardware performance.
- N5. All unresolved limitations documented (BLOCKERS.md and per-module LIMITATIONS sections).
- N6. Work kept in this private repository; each bot commits its completed work.

## Acceptance (numeric targets set in reports/TEST_PLAN.md by the auditor, all [SIMULATED])
