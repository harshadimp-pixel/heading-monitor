# T6 Verification Report — FINAL (v1.0)

Auditor: Testing & Technical Auditor (T6). Run 2026-11-27 ~00:30 IST.
**Code under test: commit `403976b`** (clean `git archive` export, so no uncommitted work-in-progress from other owners was included) plus T6's tests in `tests/`.
Clean venv: `pip install -r requirements.txt`, giving numpy 2.5.5, pytest 9.2.0 and jsonschema 4.26.0. pyserial was added only for the firmware bridge's pty test.
Raw logs (box scratch): `/workspace/audit/full_t6_403976b.log`, `full_summary_403976b.log`, `e3b*.log`, `claims_hwtag.log`.
Executed commands and counts: see `TEST_RESULTS.md` (repo root).

Evidence labels: every accuracy or robustness result here is **[SIMULATED]**. RM3100 constants are **[DATASHEET]**. MSP scaling is **[SOURCE-CODE]**.
**Nothing is [HARDWARE-VERIFIED]:** `reports/hardware_logs/` does not exist.

## 1. Verdict per deliverable
| Deliverable | Owner | Verdict | Evidence (one line) |
|---|---|---|---|
| T1 hardware fact sheet (`docs/hardware/`) | HW Research | **PASS** | T6 re-read PNI RM3100 UM Table 3-1: gain 20/38/75 LSB/µT @ CC50/100/200, ±800 µT, noise 30/20/15 nT; these match `key_numbers.json` [DATASHEET]. LIMITATIONS L1-L17 are present. No unsupported claims. |
| T2 heading_core + `docs/math/` | Math | **FAIL (one open MAJOR defect, D3)** | All 59 owner tests and 23 sensor-spec tests pass. All T6 heading, tilt, declination, calibration, filter and repeatability criteria pass, and D1 is fixed. However, E3b fails: a stationary RM3100 read through MSP (0.1 µT quantisation) is falsely flagged MAG_STALE (D3). |
| T3 simulator (`sim/`) | Sim | **PASS** | 80/80 owner tests pass. S1-S4 pass: 8 scenarios are schema-valid, sim truth agrees with the T6 reference model to ≤0.05 µT, output is byte-identical per seed, and gain matches the datasheet. |
| T4 firmware_bridge + `docs/firmware/FC_SETUP.md` | FW | **PASS** | 64 pass + 1 skip, and the pty test passes with pyserial (65/65). T6 MSP tests: 16/16 pass, 0 corrupted frames leaked into samples over 2000 fuzz streams, and source labelling is correct. D4 (found at 997d00f) is fixed in 403976b. |
| T5 app (`app/`) | UI | **PASS** | 40/40 owner tests pass. T6 ran the dashboard on its own PID-verified instance on an ephemeral port: 10/10 checks pass. Displayed heading equals the heading_core value (diff 0.0), 0/360 rounding is correct, the badge equals sample.source in 100% of records, and errors and STALE states are surfaced. LIMITATIONS U0-U10 are present. |
| PM docs (README, ARCHITECTURE, contracts, TEAM_TRACKER, REQUIREMENTS, BLOCKERS, PROJECT_STATUS) | PM | **PASS** | Contracts are consistent with all producers (schema validation passed everywhere). D2 is fixed and verified. No unsupported claims. |
| T6 (this report, TEST_PLAN, tests, TEST_RESULTS) | QA | complete | Self-reported process incident D5 (see §6). |

## 2. Overall completion verdict
**NOT APPROVED (yet).** The software runs end to end on simulated data: `python -m app --source sim` starts and serves, `python -m sim` emits samples, and `python -m firmware_bridge --fake-fc/--replay` emits valid samples. Every required report exists: FACTSHEET.md, HEADING_MATH.md, FC_SETUP.md, sim/README.md, app/README.md, firmware_bridge/README.md, TEST_PLAN.md, this report, and TEST_RESULTS.md.
Approval is blocked by **one open MAJOR defect, D3 (T2)**. On the real hardware path (MSP, 0.1 µT steps), a healthy stationary sensor would be shown as stale or degraded.
Once D3 is fixed and `tests/test_t6_stale_quant.py` passes, completion can be approved **for the virtual (simulated/replay) scope only**. Hardware performance remains unverified (see LIMITATIONS).

## 3. Results per criterion (commit 403976b)
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
| E3b quantised stationary must NOT be stale | **FAIL** | At σ = 15 nT [DATASHEET] with 0.1 µT steps: 55/600 samples flagged MAG_STALE (first at 4.6 s), min quality 0.296. Same result with and without `meta.mag_quant_uT`. At σ = 0.05 µT [ASSUMED]: 0/600. Frozen case with meta still flagged (PASS). → **D3** |
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
| Q1a hardware tag | PASS | 0 applied tags; 19 mentions excluded and each confirmed by hand (§5) |
| Q1b positioning / navigation | PASS | 0 rejected (§5) |
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

## 4. Defects
| ID | Sev | Owner | Status | Summary |
|---|---|---|---|---|
| D1 | MAJOR | T2 | **CLOSED** | Frozen sensor not flagged. Fixed in 758faeb; E3 passes in T6's own run at 403976b. |
| D2 | MINOR | PM | **CLOSED** | Blanket commit. Verified: `.gitignore` covers caches; 0 tracked .pyc files; PM commits 0c66c38, fc91815 and 9d0552f touch only PM paths, plus the .pyc removal. |
| D3 | MAJOR | T2 | **OPEN** | MAG_STALE false alarm on a stationary, MSP-quantised (0.1 µT) sensor at datasheet noise (55/600 samples, quality down to 0.30). `meta.mag_quant_uT` (now emitted by T4) is not consumed by heading_core. Design note: in T6's simulation of 60 s stationary runs (20 seeds), the longest bit-identical run had median 0.68 s and max 20.65 s, and 4 of 20 runs exceeded 5 s. The planned "5 s window" rule would therefore still false-alarm. Suggestion: when the source is quantised, flag MAG_STALE only if accel is also frozen, or reduce quality without raising a stale warning. |
| D4 | MAJOR | T4 | **CLOSED** | `--replay` forwarded schema-invalid Sample lines (found at 997d00f); fixed in 403976b. |
| D5 | MINOR | T6 | **CLOSED** (self-reported) | While re-running the T4 suite, T6 mistakenly ran `git checkout 997d00f --` in the shared repo, which detached HEAD for about 2 minutes. The UI developer's commit landed on the detached HEAD as 0525a82. T6 restored `main` and cherry-picked it as **84fc231** (author kept, tree identical, no content lost). Uncommitted work of other owners carried over intact. T6 now tests from `git archive` exports only. |

## 5. Claims audit
**Rule for the hardware tag** (implemented in `tests/test_t6_claims.py`, with a self-test): a line containing "[HARDWARE-VERIFIED]" / "hardware-verified" / "hardware verified" counts as a *mention* only if the same line contains a rule or negation cue (no, not, nothing, none, never, nobody, cannot, require(s/d), until, before any, must not, may not, only if/when/after, without a, is/are not, carries). Every other occurrence counts as *applied* and fails while `reports/hardware_logs/` is empty. The self-test confirms that "RMSE 0.4° [HARDWARE-VERIFIED]" and a table cell "HARDWARE-VERIFIED" are still caught.

T6 confirmed all 19 excluded mentions by hand; each states that nothing is hardware-verified or explains the rule:
- README.md:24
- BLOCKERS.md:5
- PROJECT_STATUS.md:16
- TEAM_TRACKER.md:11 and :40
- REQUIREMENTS.md:19
- HARDWARE_VALIDATION_CHECKLIST.md:4
- FC_SETUP.md:3 and :199
- HEADING_MATH.md:6
- FACTSHEET.md:6 and :357
- key_numbers.json:2
- app/README.md:151 ("Nothing here is hardware-verified.")
- app.js:207
- index.html:26
- firmware_bridge/README.md:5
- scaling.py:5
- sim/README.md:8

**Positioning / distance / GPS-independent navigation: no claim rejected.** Reviewed:
- docs/math/sensor-spec TC12/TC17/TC18 and HEADING_MATH.md: dead-reckoning figures are error analysis only, with a binding scope rule (§1 and L17). T6 recomputed 34.8995 m, 999.3908 m, 34.9048 m and 17.4524 m.
- app/README §U0, index.html, app.js: "Heading is orientation, not movement or position"; position, coordinates, speed, course and distance removed.
- ARCHITECTURE.md:54 and contracts: optional `gps` object is availability-only, with no coordinates.
- FC_SETUP.md: no accuracy or position claims. "Fine for heading" for 0.1 µT steps is supported by the [SIMULATED] quantisation study in docs/firmware.

**Hardware-performance statements without a hardware log:** none found. Every hardware-related number is tagged [DATASHEET], [SOURCE-CODE] or [DERIVED], and explicitly unverified.

## 6. TEAM_RULES compliance
| Rule | Finding |
|---|---|
| 1 independent roles | Respected. One violation, by T6: D5 (accidental HEAD detach), now repaired. |
| 3 shared repo | All deliverables are in the repo. |
| 4 research before assuming | T1, T4 and T2 cite pinned sources; the datasheet was verified by T1 (66/66) and independently by T6. |
| 5 execute & verify | Every owner suite re-run by T6 passes. Owner-reported counts match T6's runs: T2 59, T3 80, T4 64+1 (65 with pyserial), T5 40, sensor-spec 23. |
| 7 no fabrication | No owner figure contradicted. T6 recomputed the math-spec numbers and the datasheet table. |
| 8/9 free tools, no spend | Dependencies: numpy, pytest, jsonschema, optional pyserial (all free). |
| 10 virtual only | Yes; no hardware was touched. |
| 13 LIMITATIONS | Present in every area and in TEAM_TRACKER.md. |

## LIMITATIONS (T6, unresolved)
1. All results are [SIMULATED] against an idealised uniform-field model. **None transfer to the physical RM3100 or Matek FC.** No hardware log exists, so [HARDWARE-VERIFIED] sign-off is impossible. See reports/HARDWARE_VALIDATION_CHECKLIST.md (not run).
2. Exact Matek FC model and firmware are unknown (T1 L1). INAV axis convention, mag scaling and pitch sign are [SOURCE-CODE] derivations only.
3. MSP tests use hand-built frames; real FC timing, rate limits and partial reads over USB are untested. The long-length resync delay (§3 M2) is unquantified on a live link.
4. Dashboard checks used the app's ingest mode, the UI's own `headingmath.js` run in Node, and the UI developer's headless-Chrome test. T6 did not visually inspect the rendered pixels, and did not assess human readability.
5. App ingest mode accepts the client-declared `source`, so a client POSTing source="hardware" gets a HARDWARE badge. This is contract-compliant, but the ingest endpoint should only be fed by the bridge.
6. F1 lag (4.5° on a 25°/s ramp) and E5 error during interference (13°) are reported, not gated.
7. T6 numeric targets are T6 proposals and have not been reviewed by the owner.
