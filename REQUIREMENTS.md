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
- R8. Persistent DATA SOURCE badge derived from the sample's `source` field plus provenance (transport, self-reported device identity, allowlist match, and `meta.original_source` where present). A serial connection is not proof of hardware. HARDWARE is shown only when a live serial sample is labelled `source: "hardware"` and the device UID matches an entry in `config/verified_devices.json` (that file ships empty; an entry may be added only after the hardware-validation checklist passes with the Auditor's sign-off and a committed hardware log). A device that reports FC variant `SIML` or board id `SIMF` is shown as SIMULATED. Any other live serial origin, including an unknown, unidentified or failed identity query, is shown as UNVERIFIED SOURCE, with the reported board and variant labelled as reported by the device. Replayed hardware → 'REPLAY (recorded hardware)' (not live). Hardware via ingest → 'UNVERIFIED SOURCE'. Replayed sim stays SIMULATED. Otherwise SIMULATED, REPLAY, or NO DATA when nothing current exists.

## Non-functional
- N1. Runs locally on Linux with Python 3.10+, free/open-source dependencies only.
- N2. All experiments virtual; no hardware purchases or paid services without owner approval.
- N3. Every module executed and tested; independent tests by the Testing & Technical Auditor.
- N4. Evidence labelling: `[SIMULATED]`, `[REPLAYED]`, `[DATASHEET]`, `[HARDWARE-VERIFIED]`. The last needs a committed raw hardware log plus auditor sign-off. No simulated result may be presented as hardware performance.
- N5. All unresolved limitations documented (BLOCKERS.md and per-module LIMITATIONS sections).
- N6. Work kept in this private repository; each bot commits its completed work.

## Acceptance (numeric targets set in reports/TEST_PLAN.md by the auditor, all [SIMULATED])
