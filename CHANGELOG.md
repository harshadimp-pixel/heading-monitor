# Changelog

## 2026-11-27
- [pm] Codex CONDITIONAL PASS at f1a0e3e (documentation corrections, D8): status set to 'CONDITIONAL PASS: corrections in progress, pending independent Codex re-verification'. Virtual-only acceptance boundary stated in FINAL_REPORT.md, PROJECT_STATUS.md and README.md (simulated and replayed data only; no physical flight hardware operated; no autonomous navigation; no paid services). D7 remains CLOSED (02c0ec0). R8 / README rule 2 updated for D8: the badge is derived from sample.source plus provenance; a serial connection is not proof of hardware; HARDWARE requires a UID in config/verified_devices.json (ships empty); SIML/SIMF → SIMULATED; unknown serial → UNVERIFIED SOURCE. L-SER is superseded by D8 (in progress). Skipped-test inventory referenced at reports/audit/skipped_tests.md. Install and browser-test prerequisites recorded in docs/INSTALL_PREREQS.md (INSTALL.md remains UI-owned).
- [pm] D7 (R8 wording): REQUIREMENTS.md R8 and README ground rule 2 updated to the accepted badge rules (ARCHITECTURE.md eacf8a2, c831574). The badge is derived from sample.source; HARDWARE only for a live serial transport; replayed hardware → 'REPLAY (recorded hardware)'; hardware via ingest → 'UNVERIFIED SOURCE'.
- [math] sensor-spec TC19/§8.2 fix (Sim Dev report via PM): RM3100 CC200 LSB is 1/75 µT = 0.013333 µT (gain 75 LSB/µT, PNI-UM Table 3-1; datasheet '13 nT' is the rounded value), not 0.013. Code now uses exact 1/75 (RM3100_LSB_CC200_UT); TC19 quantisation sigma 0.0037528 -> 0.0038490 µT (+2.56%); no other expected values changed; test_cases.json regenerated, SPEC.pdf re-rendered; 23/23 pass.
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

- 2026-11-27 (PM): N6 updated. The repository is public by owner decision; no secrets or personal data may be committed.
