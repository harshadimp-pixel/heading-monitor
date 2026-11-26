# T6 Verification Report — FINAL (v2.0)

Auditor: Testing & Technical Auditor (T6). Updated 2026-11-27 at about 01:15 IST.
**Code under test:** clean `git archive` exports (never the shared working tree) of **`c942d6f`** (D3 fix f31784a; full suites + D3 re-test), **`471724e`** (integration harness, all owner suites) and **HEAD `dc3123a`** (repo-root suite, claims audit; it differs from 471724e only in docs and screenshots).
Clean venv: `pip install -r requirements.txt` (numpy 2.5.5, pytest 9.2.0, jsonschema 4.26.0) + pyserial; Python 3.13.5; Google Chrome 156 headless; Node.
Companion documents (all in `reports/audit/`): `integration_results.md` (A), `traceability.md` (B), `claims_audit.md` (C), `team_rules_compliance.md` (D). Executed counts: `TEST_RESULTS.md`.

Evidence labels: every accuracy and robustness result is **[SIMULATED]** or **[REPLAYED]**; RM3100 constants **[DATASHEET]**; MSP scaling **[SOURCE-CODE]**.
**Nothing is [HARDWARE-VERIFIED]:** `reports/hardware_logs/` does not exist.

## 0. OVERALL VERDICT: **CONDITIONAL PASS** (virtual scope only). Completion NOT yet approved.
Reasons:
1. The software runs end to end on simulated and replayed data. T6 started every instance itself on PID-verified ephemeral ports, and 25/27 integration steps pass.
2. All suites are green: repo root at dc3123a gives **506 passed, 44 skipped, 0 failed** (44 skips are sim spec-check cases outside the simulator's scope; none hides a required check, see §3a). Every owner count was reproduced.
3. D3 is fixed and re-tested (E3b stress 0/20), and frozen-sensor detection did not regress (D1 stays closed).
4. All required reports exist (FACTSHEET, HEADING_MATH, FC_SETUP, sim/firmware_bridge/app READMEs, INSTALL, TEST_PLAN, this report, TEST_RESULTS, six contribution reports, audit A–D).
5. Claims audit: 0 applied hardware tags, 0 hardware-performance claims, 0 positioning/navigation claims. TEAM_RULES: PASS (disclosed incidents).

**Condition (blocks approval):** **D6 (CRITICAL, open)**. The app's own replay of a JSONL file whose samples carry `source:"hardware"` shows the **HARDWARE** badge and the banner "**Live hardware samples.**" This is per TEST_PLAN §4 ("wrong source badge" = CRITICAL), and conflicts with README "UI must show the active data source" and with N4. Approval follows once D6 is fixed (or the PM records an explicit, reasoned waiver in TEAM_TRACKER) **and** T6 re-runs A8/A8b green.
It is latent today, because no hardware log exists yet. It will trigger the first time an app recording of a live FC session (R7) is replayed.
Hardware performance remains entirely unverified (BLOCKERS B1; HARDWARE_VALIDATION_CHECKLIST not run).

## 1. Verdict per deliverable
| Deliverable | Owner | Verdict | Evidence (one line) |
|---|---|---|---|
| T1 hardware fact sheet (`docs/hardware/`) | HW Research | **PASS** | PNI UM Table 3-1 re-read by T6 matches key_numbers.json [DATASHEET]; check_key_numbers.py present; L1–L17; ±800/±1100 µT conflict disclosed. |
| T2 heading_core + `docs/math/` | Math | **PASS** | 76/76 owner + 23/23 sensor-spec; all T6 H/C/E/F/R criteria pass; **D3 CLOSED at f31784a** (E3b 0/20, E3c–E3g pass); residual 14a documented. |
| T3 simulator (`sim/`) | Sim | **PASS** | 152 passed + 44 documented N/A skips; S1–S4; all 8 scenarios run through the app (A1). |
| T4 firmware_bridge + FC_SETUP.md | FW | **PASS** | 95/95 (with pyserial); M1–M4; A3a capture→replay bit-identical mag; A4 fake-FC labelled sim; A7b missing port rc=2, no output; GPS coordinates stripped. |
| T5 app (`app/`) | UI | **FAIL (D6 open)** | 45/45 owner tests; U1–U5, A1–A7, A9a/b pass; A8/A8b fail (replayed hardware-labelled log → HARDWARE badge + "Live" banner). |
| PM docs (README, ARCHITECTURE, contracts, REQUIREMENTS, BLOCKERS, TRACKER, INSTALL) | PM | **PASS with note** | Contracts are consistent with all producers. The ARCHITECTURE decision "replayed file keeps its original source" is the design root of D6 (shared ownership). |
| T6 (TEST_PLAN, tests, reports, audit A–D) | QA | complete | 111 T6 tests; self-reported D5 and the 9b808b5 tracker revert, both repaired. |

## 2. D3 re-test and regression check (PM request, f31784a / c942d6f)
- PM claim "499 passed, 45 skipped, 0 failed at c942d6f": **reproduced**. T6 got 501 passed / 44 skipped at c942d6f, which includes 2 extra T6 tests written during this re-test: 499 + 2. The 45th skip is `firmware_bridge/tests/test_bridge_modes.py` (pty serial), which skips when pyserial is absent (INSTALL.md:80). T6 has pyserial, and that test passes.
- E3b stress 20 × 60 s, stationary, 15 nT, 0.1 µT steps: **0/20** falsely stale (was 4/20). Single sessions 0/600.
- Frozen-sensor regression matrix (`reports/audit/raw/d3_regress.py`, output `raw/d3_regress_c942d6f.log`; also tests E3c–E3g):
  - mag-only frozen, **no gyro and no accel**: SENSOR_STALE after 0.5 s (with and without quant meta, and on-grid via inference) → **D1 not reopened**.
  - all channels frozen → SENSOR_STALE 0.5 s. Frozen off-grid mag + live accel → MAG_STALE 0.5 s.
  - frozen quantised mag + gyro 20°/s → MAG_STALE 0.2 s; + 10° tilt change with no gyro → 1.7 s.
  - **Not detected (limitation, not defect):** frozen quantised mag with live accel and (a) a stationary vehicle, (b) a gyro below the 1°/s deadband, or (c) **no gyro during a level yaw turn**. This is the consequence of PM decision (a), `quant_nogyro_time_rule=False`. It is documented in HEADING_MATH 14a and ARCHITECTURE 1befc7b. Mitigation: the MSP bridge always emits gyro_dps, so case (c) affects only gyro-less sources. T6 records it as **L-D3** (below). D1 stays closed because a frozen sensor with no accel or gyro is still flagged.

### 3a. The 44 skips
All 44 are `sim/tests/test_spec_cases.py` cases where T2's sensor spec has a quantity the simulator does not model. They are marked N/A by T3's spec_check (36 PASS / 44 N/A / 0 MISMATCH):
- TC03 circular statistics (4)
- TC05/06/14 first-order formulas (3)
- TC08 dipole/wire source models (4)
- TC09–TC12, TC17, TC18, TC20 navigation/geodesy/dead reckoning/grid convergence (29)
- TC13 WMM/analytic (3)
- TC19 generic 0.15 µT part (1)

None maps to R1–R8. The navigation ones are out of scope by the heading-only rule. Circular statistics, formulas and declination are tested in heading_core and sensor-spec (23 passed). The interference source model is [ASSUMED] k·I (a limitation, not a hidden check). **No skip hides a required check.**

## 3. Results per criterion (403976b, re-run at c942d6f / 471724e / dc3123a)
| ID | Result | Evidence [SIMULATED] |
|---|---|---|
| H1 level sweep 0..359 | PASS | max err ≤ 0.01° vs the T6 reference model (itself checked against a textbook formula to 1e-6°) |
| H2 cardinals / clockwise | PASS | N=0, E=90, S=180, W=270 |
| H3 output range | PASS | 10 000 random attitudes all in [0,360); edge cases 359.999 and 0.001 handled |
| H4 tilt ±30°, noise-free | PASS | ≤ 0.1° (inclination 20/40/60/70°, 24 yaws, 13×13 tilt grid) |
| H5 tilt, noisy | PASS | RMSE 0.628°, max 2.317° |
| H6 declination | PASS | d ∈ {-30,-1.5,0,0.5,15,180}; 359° + 2° → 1.0° |
| H7 degenerate geometry | PASS | no crash; each case returns either a NaN or error, or a flagged result |
| C1 hard iron | PASS | estimated (35.004, -21.998, 40.003) vs true (35, -22, 40) µT |
| C2 soft iron | PASS | relative std of |B| 0.31 %, direction error 0.251° rms |
| C3 calibrated heading | PASS | 0.354° RMSE calibrated vs 82.4° uncalibrated |
| C4 fit robustness | PASS | <10 points or yaw-only data → ValueError; NaN rows dropped and the fit is still good |
| C5 serialisation | PASS | round-trip diff ≤ 1e-9 |
| E1 NaN/inf input | PASS | flagged; filter recovers within 1° |
| E2 field out of range | PASS | FIELD_MAGNITUDE_OUT_OF_RANGE raised at ×0.3, ×2 and ×20 |
| E3 frozen sensor (identical samples, 3 s) | PASS | SENSOR_STALE, quality 0.05 → **D1 closed** |
| E3b stress (20 × 60 s) | 0aaa066 and 1befc7b: **FAIL** 4/20; **c942d6f (f31784a): PASS 0/20** | Before f31784a: (seed 5, 48 flagged samples), (7, 591), (11, 129), (14, 345); the cause was the no-gyro 5 s time rule (T6 showed 4/20 with `quant_nogyro_time_rule=True`, 0/20 with False at 1befc7b). At c942d6f, 0/20 sessions are flagged. meta.mag_quant_uT = 0.1, noise 15 nT [DATASHEET]. |
| E3c frozen mag during a 20°/s turn (gyro present, quantised) | PASS | MAG_STALE after 0.2 s, quality 0.024 |
| E3d stationary mag-only freeze, quantised, live accel, no gyro | OBSERVATION (documented limitation 14a) | 0/1200 samples flagged over 60 s: undetectable by design |
| E3e mag-only frozen (no accel, no gyro), with/without quant meta | PASS | SENSOR_STALE after 0.5 s, quality 0.035: **D1 not reopened** |
| E3f frozen off-grid mag, live accel, no gyro | PASS | MAG_STALE after 0.5 s |
| E3g frozen quantised mag, +10° pitch over 5 s, no gyro | PASS | MAG_STALE after 1.7 s |
| D3 matrix F10: frozen quantised mag during a level 20°/s yaw turn, **no gyro** | OBSERVATION → limitation L-D3 | not flagged (quality 0.99). Documented in HEADING_MATH 14a. The MSP bridge always supplies gyro_dps (MSP_RAW_IMU), so this affects only gyro-less sources (e.g. DroneCAN-only or hand-made logs). |
| E3b single 30 s session | 403976b: **FAIL**; 0aaa066 and c942d6f: PASS (0/600 flagged, min quality 0.983) | At 403976b: At σ = 15 nT [DATASHEET] with 0.1 µT steps: 55/600 samples flagged MAG_STALE (first at 4.6 s), min quality 0.296. Same result with and without `meta.mag_quant_uT`. At σ = 0.05 µT [ASSUMED]: 0/600. Frozen case with meta still flagged (PASS). → **D3** |
| E4 time anomalies | PASS | no crash; back within 1° |
| E5 interference step 25 µT | PASS | flagged at the onset sample; 13.1° error during the disturbance (reported, not gated) |
| E6 missing accel / malformed | PASS | NO_ACCEL plus level assumption; malformed input rejected |
| F1 wrap-invariant smoothing | PASS | behaviour identical across 0/360 and 180 (diff 1.4e-13); 4.5° lag on a 25°/s ramp (tuning property, reported) |
| F2 step 90° | PASS | within 1° after 42 samples (0.84 s at 50 Hz) |
| K1 schema + source passthrough | PASS | |
| R1 repeatability, identical input ×5 | PASS | spread 0.0° |
| A1/R2 end-to-end, 5 seeds × 20 s | PASS | RMSE mean±std: static 0.371±0.254, yaw_spin 0.527±0.241, tilted_spin 0.549±0.226, hard_iron 0.528±0.243, soft_iron 0.527±0.242 (calibrated from a separate calibration_dance), high_noise 0.846±0.229 |
| A1 motor_interference | PASS (flag) | warnings raised; RMSE 16.3° during interference (no target) |
| S1-S4 simulator | PASS | see T3 row |
| M1 decode exact (v1, v2) | PASS | RAW_IMU and ATTITUDE payloads decoded exactly; bridge encoder byte-identical to the T6 encoder (CRC-8/DVB-S2 check value 0xBC verified) |
| M2 robustness | PASS | byte-by-byte and random chunking OK; bad XOR and bad CRC rejected; every payload single-bit flip rejected; truncated → resync; short length mismatch rejected; error frames reported. Fuzz over 2000 streams: 98.8 % of valid frames recovered. 4 corrupted v2 frames passed the 8-bit CRC (size-byte collisions, inherent 1/256); **0 leaked** into samples or attitude (payload-length check). |
| M2 long-length resync | OBSERVATION | A corrupted length byte claiming 200 bytes holds back the 3 following valid frames until 156 more bytes arrive. Live polling: a few cycles of delay. End of a binary replay: those frames are lost. Not gated. |
| M3 source labelling + schema | PASS | `--fake-fc` → 50/50 samples with source=sim, schema-valid. `--replay` of hardware-labelled JSONL → source=replay with `original_source` kept. Binary replay with garbage → 4/4 valid. Malformed Sample lines: at 997d00f, 2 of 3 emitted lines were schema-invalid (**D4**); at 403976b they are skipped (**D4 closed**). |
| M4 INAV scaling | PASS | 512 LSB/g, mGauss → 0.1 µT, FLU→FRD (x,-y,-z): level → accel (0,0,-1) g [SOURCE-CODE, not hardware-checked] |
| U1 app starts (own instance) | PASS | Ephemeral port; `ss -ltnp` listener PID == PID launched by T6 (e.g. pid 82508, port 60061); 29 sim records in 1.5 s; port released after shutdown. **The earlier Phase-1 U1 PASS is withdrawn:** it may have hit the UI developer's :8080 instance. |
| U2 source badge | PASS | Records cycling through sim/replay/hardware: badge (the UI's own `headingmath.js` in Node) maps exactly in 10/10. Non-contract values ("SIMULATED", "", null, "sensor", "HARDWARE") → no badge (NO DATA); nothing is inferred. |
| U3 displayed value | PASS | App `heading_deg` vs a fresh heading_core fed the same samples: max diff 0.0°. Steady display: 359.96 → "0.0", 359.94 → "359.9", 0.04 → "0.0", 0.06 → "0.1", 180 → "180.0", 89.95 → "90.0"; "360.0" never shown. |
| U4 errors / quality / staleness | PASS | 3× field → FIELD_MAGNITUDE_OUT_OF_RANGE, quality 0.003. 2-element mag → HTTP 422, counted invalid. 2.2 s silence with `--stale 1.5` → sensor_status STALE. |
| U5 CSV export | PASS | export equals history to ≤ 1e-6 |
| Q1a hardware tag | PASS | at dc3123a: 0 applied tags; 30 mentions excluded and each confirmed by hand (audit/claims_audit.md) |
| Q1b positioning / navigation | PASS | at dc3123a: 0 rejected from 89 inventory lines (audit/claims_audit.md) |
| Q3 LIMITATIONS present | PASS | docs/hardware, docs/math, sim, docs/firmware, firmware_bridge, app |

### Accuracy-figure inputs, kept separate (PM request)
**[DATASHEET]:** RM3100 noise 15 nT rms and gain 75 LSB/µT at CC200; range ±800 µT. Source: PNI RM3100 User Manual Table 3-1, re-read by T6 in `/workspace/hwsrc/RM3100-User-Manual.pdf`.
**[SOURCE-CODE]:** MSP mag quantisation 0.1 µT (int16 mGauss) and accel 1/512 g, per `firmware_bridge/scaling.py` and FC_SETUP.md §6 (INAV source).
**[ASSUMED]** (no external source; sim constants or T6 choices):
- accel noise 0.003 g and accel bias σ 0.01 g
- gyro noise 0.05 °/s and gyro bias σ 0.3 °/s
- FC attitude noise 0.3°
- high_noise scenario: env noise 1.0 µT and IMU ×5
- hard-iron (25,-15,10) µT and the soft-iron matrices
- motor k (0.8,-0.4,1.5) µT/A
- Earth field 50 µT, inclination 60°, declination 0
- T6 tests: 0.15 µT / 0.005 g noise in H5 and C1-C3, 0.002 g accel and 0.05 µT environment noise in E3b

The accel bias (0.01 g, about 0.57° of tilt) is the main contributor to the A1 RMSE figures.
| INT integrated end-to-end (audit/integration_results.md) | **25/27 PASS** | A1 8/8 scenarios sim→heading_core→app; A1b motor interference warned (76/76 bad samples flagged); A2 7/7 example logs; A3a/b fake-FC `--capture` → `--replay` → app (REPLAY badge); A4 fake-FC → bridge → app: SIMULATED, never HARDWARE; A5 wizard 0.72°; A6 frozen/stale; A7/A7b missing port → FAULT, no data; A9a/b headless Chrome: badge, heading, warnings, GPS 'Unknown'. **FAIL A8/A8b → D6** |
| A8 badge for replayed hardware-labelled log | **FAIL → D6 (CRITICAL)** | app shows HARDWARE + "Live hardware samples." for `--source replay:<file>` |


## 4. Defects
| ID | Sev | Owner | Status | Summary |
|---|---|---|---|---|
| D1 | MAJOR | T2 | **CLOSED** | Frozen sensor not flagged; fixed 758faeb; still flagged after the D3 change (E3, E3e, A6). |
| D2 | MINOR | PM | **CLOSED** | Blanket commit; verified fixed. |
| D3 | MAJOR | T2 + PM rule | **CLOSED** (f31784a, re-tested at c942d6f) | False MAG_STALE on a stationary quantised sensor; E3b stress 0/20. Residual stationary/no-gyro blind spot → limitation L-D3 (HEADING_MATH 14a). |
| D4 | MAJOR | T4 | **CLOSED** | Bridge replay forwarded schema-invalid lines; fixed 403976b. |
| D5 | MINOR | T6 | **CLOSED** (self-reported) | Accidental HEAD detach; repaired (84fc231). |
| **D6** | **CRITICAL** | T5 (app replay/badge) + PM (ARCHITECTURE decision "replay keeps original source") | **OPEN, blocks approval** | `python -m app --source replay:<file>` with samples `source:"hardware"` → badge **HARDWARE**, banner "**Live hardware samples.**" (integration A8, A8b; DOM `audit/raw/ui_dom_hw_replay.html`). Suggested fix (owner's choice): in the app's replay source, relabel `hardware` → `replay` and keep `original_source` (as `firmware_bridge --replay` already does), or show "REPLAY (recorded hardware)" with a non-live banner. |

## 5. Claims audit → `reports/audit/claims_audit.md`
0 applied hardware tags (30 mentions confirmed by hand); 0 hardware-performance claims; 0 positioning, distance or GPS-independent navigation claims (89 inventory lines adjudicated). The GPS indicator is availability-only, with coordinates stripped. Runtime claim issue: D6.

## 6. TEAM_RULES compliance → `reports/audit/team_rules_compliance.md`
13/13 PASS as far as verifiable. Spend: none found (requirements are OSS; no keys, purchases or paid APIs; all contribution reports state none). Disclosed rule-1 incidents: D5 and 9b808b5 (T6), d211e80 (sim); all repaired.

## 7. Traceability → `reports/audit/traceability.md`
Delivered 11 (R1–R5, R7, N1–N3, N5, N6); Partial 3 (R6 live MSP not runnable without hardware; R8 and N4 because of D6); Not delivered 0.

## LIMITATIONS (T6, unresolved)
1. All results are [SIMULATED] or [REPLAYED] against an idealised uniform-field model. **None transfer to the physical RM3100 or Matek FC.** No hardware log exists, so [HARDWARE-VERIFIED] sign-off is impossible (HARDWARE_VALIDATION_CHECKLIST not run).
2. Exact Matek FC model and firmware are unknown (T1 L1). INAV axis convention, mag scaling and pitch sign are [SOURCE-CODE] only.
3. MSP tests use hand-built frames and the fake FC; real USB timing, rate limits and partial reads are untested. Live `serial:` was only tested against a missing port.
4. **L-D3:** in quantised mode a frozen mag is undetectable on a stationary vehicle, below 1°/s, or during a level yaw turn when no gyro is supplied (PM decision (a)). The opt-in `quant_nogyro_time_rule=True` catches long freezes but brings back about 4/20 false alarms in T6's stress test.
5. App ingest trusts the client-declared `source` (documented).
6. pyserial is not in requirements.txt; a fresh install cannot use `serial:` until it is added (documented in INSTALL.md).
7. UI checks use DOM text from headless Chrome (badge, heading, warnings, GPS, banner); pixels and human readability were not assessed. Demo video and screenshots were not inspected frame by frame.
8. The default `--sim-duration 86400` stretches the motor_interference profile over 24 h, so in a short live demo interference does not appear unless `--sim-duration` is set (A1 vs A1b).
9. F1 lag (4.5° on a 25°/s ramp) and E5 interference error (13°) are reported, not gated. T6 numeric targets have not been reviewed by the owner. Python 3.10 was not tested (3.13.5 only).
