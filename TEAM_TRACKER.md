# Task Tracker  (owner: PM & CTO; each owner updates own rows)

Status: TODO / IN-PROGRESS / BLOCKED / REVIEW / DONE

| ID | Task | Owner | Depends on | Status | Notes |
|---|---|---|---|---|---|
| T1 | Hardware fact sheet: RM3100 (interface, cycle counts, gain, noise, ranges), Matek FC models & compass support in INAV/ArduPilot/Betaflight, wiring, sources -> `docs/hardware/` | Hardware Research Engineer | - | REVIEW | `docs/hardware/FACTSHEET.md` (+ key_numbers.json, SOURCES.md). 75 LSB/uT @CC200; our CAN-L4-3100 delivers DroneCAN float16 Gauss <=25 Hz or MSP int16 mG; INAV needs MSP (no DroneCAN mag); exact FC model UNKNOWN. Limitations L1-L15 below |
| T2 | Heading math + calibration library `heading_core/` (ellipsoid hard/soft-iron fit, tilt comp, declination, smoothing w/ wrap-around, quality metric) + `docs/math/` derivation, unit tests | Mathematics & Sensor Scientist | T1 (soft) | REVIEW | Done: heading_core (Calibration ellipsoid/sphere fit, tilt_compensated_heading, HeadingEstimator w/ complementary+gyro or circular-mean smoothing, quality 0..1, warnings), 54 unit tests pass, docs/math/HEADING_MATH.md, MC results docs/math/accuracy_results.md [SIMULATED] (ellipsoid cal 0.30 deg RMS, raw 29.5 deg RMS), sim cross-check docs/math/sim_check_results.md [SIMULATED]. LIMITATIONS (full list HEADING_MATH.md s13): L1 no hardware validation; L2 accel-only tilt wrong under dynamic accel, no attitude filter; L3 real FC accel sign/axes unverified (bridge must convert to specific force); L4 mag-to-body misalignment not observable by ellipsoid fit; L5 needs full 3-D calibration coverage, plain LS fit not outlier-robust, no auto coverage gate; L6 motor/current interference detected not compensated; L7 risk of double calibration if FC/AP_Periph already applies offsets; L8 declination constant, no WMM/IGRF; L9 heading ill-conditioned at high dip, no gimbal-lock support; L10 quality metric heuristic, thresholds untuned; L11 HIGH_NOISE conflates noise and lag without gyro; L12 MC noise/bias params assumed; L13 warning codes + extra kwargs (config, accel_convention) await PM confirmation; L14 temperature/linearity/cycle-count not modelled; L15 no speed/distance/place output |
| T3 | Sensor simulator `sim/`: RM3100 + FC IMU, scenarios (static, slow yaw spin, tilted spin, hard/soft iron, motor interference, noise), ground truth, seeded | Simulation Developer | T1 (soft) | REVIEW | `python -m sim --rate 50 --duration 60 --scenario <name> --seed N [--out f.jsonl]`; 8 scenarios; examples in sim/examples/; `pytest sim/tests` 80 passed [SIMULATED]; RM3100 table values cross-checked against T1 FACTSHEET.md + key_numbers.json (DRAFT). LIMITATIONS (detail in sim/README.md): (1) RM3100 values are datasheet typicals, not per-unit; gain/noise at CC other than 50/100/200 PROVISIONAL [DERIVED-APPROX]; (2) range ±800 µT (manual) vs ±1100 µT (sales sheet), saturation modelled as hard clip; (3) white Gaussian noise only, no 1/f, temperature, hysteresis, linearity or cross-axis error; (4) uniform static Earth field, no WMM/IGRF, defaults 50 µT / I 60° / D 0° not our site; (5) IMU noise/bias ASSUMED generic MEMS, not the Matek IMU, no vibration or linear accel; (6) idealised hard/soft-iron and single-vector motor-current model, ASSUMED coefficients; (7) ideal timing, no jitter, latency or dropouts, no MSP transport; (8) fc_attitude_deg is a crude stand-in; (9) no GPS; (10) accel convention = specific force (level -> z = -1 g), matching T2's default, but the contract doesn't specify it and T4 must confirm; (11) calibration_dance needs ≥ 30 s; (12) jsonschema not in requirements.txt, so the full-schema tests are skipped without it. QUESTIONS for PM: add jsonschema to requirements.txt? state the accel sign convention in the contract? OK that extra keys are in `truth`, and that sim_config is only in the first line's `meta`? |
| T4 | FC telemetry bridge `firmware_bridge/` (MSP over USB: MSP_RAW_IMU / MSP_ATTITUDE; MAVLink optional) + `docs/firmware/` FC config steps for RM3100 on Matek | Firmware Specialist | T1 | IN-PROGRESS | test against recorded/synthetic MSP frames; source="hardware" only from a live port |
| T5 | Heading-monitor app `app/`: backend + local web UI (compass, numbers, field, tilt, calibration wizard, warnings, source badge), `--source sim|replay|serial` | UI & Software Developer | T2, T3 (contracts first) | IN-PROGRESS | stdlib HTTP+WebSocket backend, vanilla JS UI; local stubs behind ARCHITECTURE.md interfaces until T2/T3/T4 land |
| T6 | Independent test plan, integration tests, accuracy runs vs sim truth, claims audit, `reports/verification_report.md` | Testing & Technical Auditor | T2-T5 | IN-PROGRESS | Phase 1 done: reports/TEST_PLAN.md (criteria H/C/E/F/S/A/R/M/U/K/Q, all [SIMULATED]); tests/test_t6_*.py (74 tests); preliminary reports/verification_report.md: 71 pass, 2 fail (D1, app LIMITATIONS pending), MSP + dashboard NOT RUN. Waiting for T2/T4/T5 REVIEW. LIMITATIONS: see verification_report.md |
| T7 | Integration, review, consolidated report to owner | PM & CTO | T1-T6 | IN-PROGRESS | |
| T8 | Group-chat hub: route questions to the right specialist, consolidate answers, record decisions for the owner | All group bot Work project | - | IN-PROGRESS | owner assigned this role 2026-11-26; no code ownership |
| D1 | Defect (MAJOR): frozen/stuck sensor (identical samples for 3 s) not flagged; quality stays 1.0 (T6 test E3) | Mathematics & Sensor Scientist | T2 | OPEN | add stale/stuck-data warning; re-test tests/test_t6_estimator.py::test_E3_frozen_sensor |
| D2 | Defect (MINOR): commit 7313846 used blanket git add; committed other owners' WIP and tests/__pycache__/*.pyc | PM & CTO | - | OPEN | use path-scoped `git add` |

## Change log
- 2026-11-26 PM: repo, contracts, tracker created.
- 2026-11-26 HW: T1 started (IN-PROGRESS).
- 2026-11-26 FW: T4 started (IN-PROGRESS).
- 2026-11-26 UI: T5 started (IN-PROGRESS).
- 2026-11-27 Hub: T8 added (IN-PROGRESS).
- 2026-11-27 QA: T6 Phase 1 (test plan + tests + preliminary verification report); D1, D2 filed.
- 2026-11-27 HW: T1 -> REVIEW (FACTSHEET.md, key_numbers.json, SOURCES.md).

## Limitations — T6 Testing
- All T6 targets and results are [SIMULATED]; no hardware logs, so no [HARDWARE-VERIFIED] sign-off possible.
- MSP (M1-M3) and dashboard (U2-U5) criteria not yet executed (T4/T5 in progress).
- Results for T2/T5 are preliminary (run against uncommitted WIP); will re-run at REVIEW.

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

## Limitations — T2 Math sensor spec (mirrors docs/math/sensor-spec/SPEC.md §10)
- S1 No WMM/IGRF evaluation in code; D, I, F are scenario inputs (WMM2025 sigma_D formula implemented as planning aid only).
- S2 Sensor priors in SPEC §8.2 are [ASSUMED] typical ranges except RM3100 noise/resolution ([DATASHEET] via T1). No hardware validation; all results [SIMULATED].
- S3 Matek CAN RM3100 (AP_Periph/DroneCAN) frame/units at FC/MSP boundary must be confirmed by T4 before applying formulas to logs.
- S4 Accel sign convention: spec + heading_core default = specific force (level z = -1 g); T3/T4 emitted convention not in contract.
- S5 Euler heading undefined near |pitch| = 90 deg; no quaternion heading specified.
- S6 Ellipsoid fit is algebraic (biased at low SNR / partial coverage); cannot recover misalignment rotation; output scale = geometric-mean radius, not F.
- S7 Spherical haversine/rhumb (up to ~0.5% vs ellipsoidal geodesic); TM convergence spherical first-order only.
- S8 Dipole/wire interference = far-field idealisations; no eddy currents, PWM spectra, hysteresis or re-magnetisation; temperature linear only.
- S9 Error-budget formula assumes independent terms; MC tolerances in TC07/TC18 are statistical (3-4%).
- 2026-11-27 Math: T2 -> REVIEW (heading_core, HEADING_MATH.md with LIMITATIONS, 54 tests, [SIMULATED] accuracy results).
