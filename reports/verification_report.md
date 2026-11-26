# T6 Verification Report — PRELIMINARY (Phase 1 complete, Phase 2 partial)

Auditor: Testing & Technical Auditor (T6). Run: 2026-11-27 00:05 IST on repo HEAD `912476c` **plus uncommitted
working-tree changes of other owners** (T2/T4/T5 are still IN-PROGRESS, so results for them are provisional and will be re-run at REVIEW).
Every result below is `[SIMULATED]` (or `[DATASHEET]` where marked). Nothing is `[HARDWARE-VERIFIED]`: `reports/hardware_logs/` does not exist.

Command: `python3 -m pytest tests -v -s` → **71 passed, 2 failed, 1 skipped** (35.8 s). Full log: `/workspace/audit/phase1_final_run.log` (box scratch).
Owner suites re-run by T6: `pytest sim/tests` 80 passed; `pytest heading_core/tests` 54 passed; `pytest docs/math/sensor-spec` 23 passed;
`app/tests`, `firmware_bridge/tests`: empty (no tests yet).

## Status of deliverables
| Task | Owner | Tracker status | T6 verdict now |
|---|---|---|---|
| T1 hardware fact sheet | HW Research | REVIEW | **PASS (provisional)** – gain 20/38/75 LSB/µT @ CC 50/100/200, range ±800 µT, noise 30/20/15 nT re-read by T6 in PNI RM3100 User Manual Table 3-1 and match `key_numbers.json`; LIMITATIONS present (L1-L15); no unsupported claims. Note: `/workspace/hwsrc/RM3100-RM2100-Sensor-Suite-User-Manual.pdf` is a 233-byte captcha HTML page, not a PDF (failed download) – do not cite it. |
| T2 heading_core | Math | IN-PROGRESS | **Not final.** All heading/tilt/declination/calibration criteria pass; E3 fails (D1). |
| T3 simulator | Sim | REVIEW | **PASS** – S1 (8 scenarios schema-valid, monotonic t, 500 samples/10 s), S2 truth vs T6 refmodel ≤0.05 µT, S3 byte-identical per seed, S4 scaling matches datasheet gain, 80 owner tests pass, LIMITATIONS present. |
| T4 firmware_bridge | FW | IN-PROGRESS | **NOT RUN** – no parser tests yet; no FC_SETUP.md yet. |
| T5 app | UI | IN-PROGRESS | **Not final** – U1 smoke passes (`python -m app --source sim` serves :8080); U2-U5 not yet implemented by T6; no LIMITATIONS section yet. |

## Results per criterion
| ID | Result | Evidence |
|---|---|---|
| H1 level sweep 0..359 | PASS | max err ≤ 0.01° vs T6 reference model |
| H2 cardinals / clockwise | PASS | N=0, E=90, S=180, W=270 |
| H3 range [0,360) | PASS | 10 000 random attitudes, 359.999/0.001 edge cases |
| H4 tilt ±30°, noise-free | PASS | ≤ 0.1° over 4 inclinations × 24 yaws × 13×13 tilt grid |
| H5 tilt, noisy | PASS | RMSE 0.628°, max 2.317° (0.15 µT, 0.005 g, seed 42) |
| H6 declination | PASS | d ∈ {-30,-1.5,0,0.5,15,180}; 359+2 → 1.0 |
| H7 degenerate geometry | PASS | no crash / NaN-or-error for vertical field, zero field, accel along x |
| C1 hard iron | PASS | est (35.004, -21.998, 40.003) vs true (35, -22, 40) µT |
| C2 soft iron | PASS | |B| rel std 0.31 %, direction err 0.251° rms |
| C3 calibrated heading | PASS | 0.354° RMSE calibrated vs 82.4° uncalibrated |
| C4 fit robustness | PASS | <10 pts and yaw-only data raise ValueError; NaN rows dropped, fit still good |
| C5 serialization | PASS | round-trip diff ≤ 1e-9 |
| E1 NaN/inf mag/accel | PASS | no NaN output, flagged, filter recovers within 1° |
| E2 field out of range (×0.3, ×2, ×20) | PASS | FIELD_MAGNITUDE warning |
| E3 frozen / stuck sensor (3 s identical) | **FAIL** | warnings [] and quality 1.0 → **D1** |
| E4 time anomalies | PASS | backwards / repeated t and 2 s gap: no crash, back within 1° |
| E5 interference step 25 µT | PASS | flagged at onset sample; heading error during disturbance 13.1° (reported) |
| E6 missing accel / malformed | PASS | NO_ACCEL + level assumption; malformed rejected or schema-valid |
| F1 wrap-around smoothing | PASS | identical behaviour across 0/360 and 180 (diff 1.4e-13); lag 4.5° on 25°/s ramp (tuning, reported) |
| F2 step 90° | PASS | settles within 1° after 42 samples (0.84 s @ 50 Hz) |
| K1 schema + source passthrough | PASS | sim/replay/hardware all passed through unchanged |
| R1 repeatability, identical input ×5 | PASS | spread 0.0° |
| A1/R2 end-to-end, 5 seeds, 20 s | PASS | RMSE mean±std: static 0.371±0.254, yaw_spin 0.527±0.241, tilted_spin 0.549±0.226, hard_iron 0.528±0.243, soft_iron 0.527±0.242 (calibrated from separate calibration_dance), high_noise 0.846±0.229 |
| A1 motor_interference | PASS (flag) | warnings raised; RMSE 16.3° during interference (expected; no target) |
| S1-S4 sim | PASS | see T3 row |
| M1-M3 MSP | NOT RUN | firmware_bridge in progress; T6 frame builders (v1 XOR, v2 CRC8 DVB-S2) ready in tests/msp_frames.py |
| U1 app starts | PASS | HTTP 200 on :8080 within 10 s |
| U2-U5 dashboard | NOT RUN | pending T5 REVIEW |
| Q1 claims audit | PASS so far | see below |
| Q3 LIMITATIONS sections | FAIL (pending) | missing in app/ (T5 in progress) |

## Math recomputation (T6, independent)
TC12: 1000·sin2° = 34.8995 m, 1000·cos2° = 999.3908 m, 2000·sin1° = 34.9048 m (match). TC18: 1000·sin1° = 17.4524 m; white-noise
approx 10·√100·rad(2°) = 3.4907 m (match). TC08 dipole: 7.407 / 3.704 / 0.926 µT (match). T1 gain table re-read from PDF (match).

## Claims audit (Q1) – statements implying position / distance / navigation / hardware performance
Automated scan (`tests/test_t6_claims.py`) + manual read. **No unsupported claim found so far; nothing rejected yet.**
- `docs/math/sensor-spec/` TC12/TC17/TC18 (“Dead-reckoning cross-track error…”, “dead reckoning in lat/lon”): **accepted as analysis
  only** – it quantifies how heading error would propagate *if* a velocity source existed; SPEC.md §4.6 states position is
  unobservable from heading alone. Condition: this code must never be surfaced in the app as a position/distance feature.
- `docs/hardware/FACTSHEET.md` 329/331/349 “distance”: physical separation guidance for interference, not measurement. OK.
- `app/hub.py:29`: “position and movement are Unknown. Nothing is inferred from heading.” Correct.
- All docs state nothing is `[HARDWARE-VERIFIED]`. OK.

## TEAM_RULES compliance (Q3)
- Rule 3 (shared repo): all work found in repo. Rule 13 (LIMITATIONS): present for T1 (FACTSHEET §8 + tracker), T3 (sim/README + tracker),
  T2 sensor-spec (S1-S9), FW research doc; **missing for app/** (in progress).
- Process note (D2): commit 7313846 `[pm]` used a blanket add and committed T6's uncommitted test files and `tests/__pycache__/*.pyc`.

## Defects
- **D1 (MAJOR, T2)** E3: 3 s of bit-identical samples (frozen/disconnected sensor returning last value) produce no warning and quality 1.0.
  A real RM3100 always shows count-level noise; a stuck value should raise e.g. STALE_DATA and drop quality.
- **D2 (MINOR, PM)** blanket `git add` committed other owners' WIP and .pyc files; use path-scoped adds.

## LIMITATIONS (T6)
1. Preliminary: T2, T4, T5 not in REVIEW; their results will be re-run. 2. All accuracy figures are [SIMULATED] against an
idealised model; none transfer to the physical RM3100/Matek FC. 3. MSP and dashboard (U2-U5) criteria not yet executed.
4. Exact Matek FC model unknown (T1 L1). 5. No hardware logs exist, so no [HARDWARE-VERIFIED] sign-off is possible.
6. Project completion **cannot be approved yet**: T4 deliverable and FC_SETUP.md, app LIMITATIONS, dashboard checks, and final T2 are pending.
