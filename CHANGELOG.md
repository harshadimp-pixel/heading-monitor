# Changelog

## 2026-11-27
- [sim] Delivered output modes (--output-mode dronecan|msp: Matek CAN-L4-3100/AP_Periph model from source code), spec check vs T2 sensor spec (35 PASS / 44 N/A / 1 MISMATCH TC19 spec-side), optional misalignment + Gauss-Markov bias, 2 example logs; 151 sim tests pass [SIMULATED].
- [hw] T1 audit follow-up: PNI manual + sales sheet re-downloaded and verified (66/66 automated checks, docs/hardware/VERIFICATION.md, verify_datasheet.py); SOURCES.md corrected; captcha/redirect downloads renamed INVALID (never cited); limitations L16-L17 added.
- [math] T2 sensor-spec: docs/math/sensor-spec/ (SPEC.md/.pdf, reference_model.py, test_reference.py 23 passed, test_cases.json 20 vectors) for T3 Sim developer [SIMULATED].
- [sim] T3 -> REVIEW: sim/ simulator (RM3100 counts/uT model, IMU, hard/soft iron, motor interference, 8 scenarios), example logs, 80 pytest passing [SIMULATED], README with LIMITATIONS.
- [hw] T1 hardware fact sheet complete -> REVIEW: docs/hardware/FACTSHEET.md, key_numbers.json, SOURCES.md; T1 limitations added to TEAM_TRACKER.md.
- [hub] Added T8 (group-chat hub) row to TEAM_TRACKER.md.
- [pm] Added PROJECT_STATUS.md, REQUIREMENTS.md, TEST_RESULTS.md, BLOCKERS.md, CHANGELOG.md; renamed TRACKER.md to TEAM_TRACKER.md. Repository moving to private GitHub.

## 2026-11-26
- [pm] Project scaffold: README, ARCHITECTURE, contracts (Sample, HeadingEstimate), tracker.
- [pm] Owner's team working rules added (TEAM_RULES.md). Six specialists briefed (T1–T6).
- [pm] .gitignore for caches; jsonschema added; accel sign convention + sim truth keys fixed in ARCHITECTURE.md.
- [pm] T2 review decisions: warning codes frozen, optional kwargs approved, single-calibration rule, quantisation-aware MAG_STALE.
- [pm] T5 review decisions: optional gps availability field, replay badge rule, ephemeral ports in tests.
- [pm] Approved provisional quantisation-step inference in heading_core (infer_mag_quant, default on).
