# Contribution report — Mathematics & Sensor Scientist (T2, `heading_core/` + `docs/math/`)

**Status:** T2 at REVIEW (PM accepted pending the Auditor's re-test). D1 is CLOSED. D3 is REVIEW (fixed per PM decision (a); awaiting Auditor re-test).
**Evidence level:** every performance number is **[SIMULATED]** unless tagged **[DATASHEET]** or **[ASSUMED]**. Device constants such as RM3100 noise (15 nT) and the cycle-count 200 LSB (1/75 µT) are **[DATASHEET]**. Experiment priors that are not datasheet values are **[ASSUMED]**. **Nothing is hardware-verified.** No RM3100, Matek CAN-L4-3100 or Matek flight controller was connected, and no hardware replay log exists.

## 1. Deliverables and paths

| Path | Content |
|---|---|
| `docs/math/sensor-spec/SPEC.md`, `SPEC.pdf` | Magnetic heading math spec: frames and norths, tilt compensation, heading vs track / distance / position (error analysis only), sensor error model, interference, ellipsoid calibration, virtual-experiment design, assumptions, LIMITATIONS S1–S11, reference cases TC01–TC20 |
| `docs/math/sensor-spec/reference_model.py` | Numpy reference implementation of the spec formulas |
| `docs/math/sensor-spec/test_reference.py`, `test_cases.json` | 23 pytest checks against 20 generated test vectors |
| `docs/math/sensor-spec/render_pdf.sh` | SPEC.md → SPEC.pdf via pandoc, MathJax SVG and headless Chrome (free tools only) |
| `heading_core/` | T2 package (numpy): `Calibration` (ellipsoid / sphere fit, `apply`, `to_dict` / `from_dict`), `tilt_compensated_heading` (NED body: x forward, y right, z down; specific force, level = (0, 0, −1) g), `HeadingEstimator.update(sample)` → `HeadingEstimate` (wrap-safe complementary or circular-mean smoothing, optional gyro, quality 0..1, frozen warning codes) |
| `heading_core/calibration.py`, `heading.py`, `estimator.py`, `config.py`, `warnings_codes.py`, `synth.py` | Implementation modules |
| `heading_core/tests/test_heading_core.py` | Unit tests on synthetic vectors (76 tests after D3 decision (a)) |
| `heading_core/experiments/accuracy_mc.py`, `sim_check.py` | Monte Carlo accuracy experiment and T3 simulator cross-check |
| `docs/math/HEADING_MATH.md` | Derivation, API, assumptions, and LIMITATIONS 1–17 (including 14a) |
| `docs/math/accuracy_results.md`, `accuracy_results.json` | Monte Carlo results **[SIMULATED]** |
| `docs/math/sim_check_results.md` | heading_core vs T3 simulator cross-check **[SIMULATED]** |

`[math]` commits (author Mathematics & Sensor Scientist; Asia/Calcutta times from `git log`):

| Commit | Time (Asia/Calcutta) | Content |
|---|---|---|
| `b7f4d6a` | 2026-11-26 23:54:35 | T2 interface stubs (`Calibration`, `tilt_compensated_heading`, `HeadingEstimator`); T2 IN-PROGRESS |
| `ace283c` | 2026-11-26 23:55:46 | Untrack pycache; add `heading_core/.gitignore` |
| `a4878c7` | 2026-11-26 23:58:55 | Implement calibration, tilt-compensated heading, estimator, synth model; 47 unit tests |
| `912476c` | 2026-11-27 00:04:18 | Sensor spec (`SPEC.md`/`.pdf`, reference model, 23 pytest checks, 20 vectors); LIMITATIONS S1–S9 as first filed |
| `758faeb` | 2026-11-27 00:11:54 | T2 → REVIEW; D1 frozen-data detection (`SENSOR_STALE` / `MAG_STALE` / `TIMESTAMP_STALE`); `HEADING_MATH.md` with LIMITATIONS and the dead-reckoning scope rule; MC + sim cross-check **[SIMULATED]**; 59 tests |
| `b7e28d0` | 2026-11-27 00:20:57 | PM decisions (3) and (4): quantised-source `MAG_STALE` (`meta.mag_quant_uT` or inferred decimal grid; bit-identical ≥ 5 s, quality ≥ 0.3×) and `fc_mag_calibrated` handling; thresholds marked PROVISIONAL; 67 tests |
| `171e1e5` | 2026-11-27 00:21:14 | `TEAM_TRACKER.md`: T2 stays REVIEW; PM decisions implemented; PROVISIONAL thresholds noted |
| `64579d9` | 2026-11-27 00:26:22 | Sensor-spec TC19 / §8.2 fix: RM3100 CC200 LSB = exact 1/75 µT (was the rounded 0.013 µT); reference model, tests, vectors and PDF updated |
| `d177c37` | 2026-11-27 00:33:06 | D3: quantised-mode `MAG_STALE` needs gyro/accel motion evidence (> 3°, 1°/s deadband, reset on mag change); no-gyro 5 s fallback warning-only; 75 tests |
| `17a48ee` | 2026-11-27 00:33:06 | `TEAM_TRACKER.md`: D3 → REVIEW (fixed); residual limitation noted |
| `f31784a` | 2026-11-27 00:36:49 | PM D3 decision (a): `quant_nogyro_time_rule=False` by default (opt-in kept); no gyro → accel-tilt evidence only; LIMITATIONS 14a updated; 76 tests |
| `c942d6f` | 2026-11-27 00:36:49 | `TEAM_TRACKER.md`: T2/D3 notes for decision (a) |

The PM recorded decision (a) in `ARCHITECTURE.md` in `1befc7b` (`[pm]`, 2026-11-27 00:34:11 Asia/Calcutta), immediately before `f31784a`.

**TC19 / `64579d9`.** The Simulation Developer reported that SPEC §8.2 and TC19 used a 0.013 µT step, while the 200-cycle LSB is 1/75 = 0.01333… µT (PNI User Manual Table 3-1 gain 75 LSB/µT; the datasheet “13 nT” is the rounded value). The spec, reference model, `test_cases.json` and SPEC.pdf were corrected to the exact 1/75 µT. The only expected value that moved was TC19 quantisation sigma, 0.0037528 → 0.0038490 µT; heading noise stayed 0.034377°.

Dead-reckoning figures in the spec and in `HEADING_MATH.md` remain error analysis only. `heading_core` has no position or distance feature (Auditor condition; LIMITATIONS 17).

## 2. Tests actually executed

Re-run on 2026-11-27 at HEAD `c942d6f` (after `f31784a`, which set `quant_nogyro_time_rule=False` by default), in `/workspace/venvs/hm` (Python 3.13.5, numpy 2.5.5, pytest 9.2.0, jsonschema 4.26.0), from the shared box. Results below are copied from the console of this re-run, not from earlier reports. All **[SIMULATED]**.

| When (Asia/Calcutta) | Command | Result |
|---|---|---|
| 2026-11-27 00:37:57 → 00:39:43 | `/workspace/venvs/hm/bin/python -m pytest heading_core/tests tests` (repo root `/workspace/heading-monitor`) | collected 181 items; **181 passed in 105.29s (0:01:45)** |
| 2026-11-27 00:37:59 | `/workspace/venvs/hm/bin/python -m pytest -q test_reference.py` (cwd `docs/math/sensor-spec/`) | **23 passed in 0.27s** |

Exact summary lines:

```
======================= 181 passed in 105.29s (0:01:45) ========================
```

```
23 passed in 0.27s
```

Breakdown of the 181: `heading_core/tests/test_heading_core.py` 76 passed; `tests/` (Auditor T6) 105 passed, including `tests/test_t6_stale_quant.py` (6 passed). That file includes `test_E3b_stress_20_sessions_60s`. At an earlier check, E3b failed by design under the then-default no-gyro 5 s time rule (4/20 sessions warned, quality at least 0.944). After PM D3 decision (a) and `f31784a`, this re-run observed E3b **pass** (0 failed in the 181). No tests failed.

The accuracy table below is **not** from a re-run of the Monte Carlo in this session. The numbers are copied exactly from `docs/math/accuracy_results.md`, which was generated by `python -m heading_core.experiments.accuracy_mc --trials 200 --seed 2026` (python 3.13.5, numpy 2.5.5). Synthetic data only.

### A. Per-sample heading error, random heading, roll/pitch uniform +-30 deg [SIMULATED]

Copied from `docs/math/accuracy_results.md`:

| Case | RMS (deg) | P95 (deg) | Max (deg) | N |
|---|---|---|---|---|
| Ellipsoid fit, NO tilt compensation (level assumed) | 16.129 | 30.407 | 57.073 | 100000 |
| Raw (no calibration), tilt-compensated | 29.505 | 55.361 | 179.760 | 100000 |
| Hard-iron only (sphere fit) | 2.994 | 5.829 | 11.121 | 100000 |
| Ellipsoid fit (hard + soft iron) | 0.301 | 0.605 | 1.751 | 100000 |
| Ellipsoid fit, error-free accel (isolates mag + fit error) | 0.024 | 0.046 | 0.104 | 100000 |
| Ellipsoid fit, + 0.3 uT platform noise | 0.564 | 1.111 | 2.763 | 100000 |
| Ellipsoid fit, true soft iron has skew part (+-0.02) | 0.691 | 1.330 | 2.962 | 100000 |

### B. Smoothing (with 0.3 uT platform noise, ellipsoid calibration), 2 s warm-up excluded [SIMULATED]

Copied from `docs/math/accuracy_results.md`:

| Case | RMS (deg) | P95 (deg) | Max (deg) | N |
|---|---|---|---|---|
| Static hold, per-sample (no smoothing) | 0.556 | 1.094 | 2.466 | 80000 |
| Static hold, complementary filter (alpha 0.05, gyro) | 0.273 | 0.529 | 1.055 | 80000 |
| Static hold, circular mean (25 samples) | 0.271 | 0.531 | 1.155 | 80000 |
| 30 deg/s yaw spin, per-sample (no smoothing) | 0.557 | 1.093 | 2.964 | 80000 |
| 30 deg/s yaw spin, complementary + gyro | 0.268 | 0.527 | 1.024 | 80000 |
| 30 deg/s yaw spin, complementary, no gyro | 11.425 | 11.830 | 12.385 | 80000 |
| 30 deg/s yaw spin, circular mean (25 samples) | 7.208 | 7.630 | 8.198 | 80000 |

Calibration fit (same document): mean |offset error| 0.0026 uT (max 0.0058), mean residual RMS 0.0153 uT [SIMULATED].

Simulator cross-check numbers, copied exactly from `docs/math/sim_check_results.md` (generated by `python -m heading_core.experiments.sim_check`; not re-run in this session), errors in degrees vs `truth.heading_deg` [SIMULATED]:

| Scenario | Calibration | per-sample RMS | per-sample max | filtered RMS | filtered max |
|---|---|---|---|---|---|
| static | raw | 0.957 | 1.935 | 1.567 | 1.661 |
| static | calibrated | 0.778 | 1.768 | 0.686 | 0.891 |
| yaw_spin | raw | 34.171 | 57.256 | 26.076 | 42.712 |
| yaw_spin | calibrated | 0.829 | 1.785 | 0.772 | 1.235 |
| tilted_spin | raw | 42.149 | 82.569 | 32.182 | 65.182 |
| tilted_spin | calibrated | 0.709 | 1.658 | 0.638 | 1.053 |

## 3. Open limitations

Full text is in `docs/math/HEADING_MATH.md` §13 (L1–L17, including 14a) and `docs/math/sensor-spec/SPEC.md` §10 (S1–S11), mirrored in the T2 row and the “Limitations — T2 Math sensor spec” section of `TEAM_TRACKER.md`. None of these has been checked on hardware.

Summary of `HEADING_MATH.md` §13:

1. **No hardware validation.** All numbers are [SIMULATED] or [DATASHEET] (BLOCKERS B1).
2. Accelerometer-only tilt is wrong under dynamic acceleration; no attitude filter is implemented.
3. Real FC accelerometer sign and axes are unverified; the firmware bridge must convert to specific force. `accel_convention="gravity"` is an escape hatch.
4. Magnetometer/body misalignment is not observable by the ellipsoid fit (±0.02 skew already doubles RMS, 0.30° → 0.69° [SIMULATED]).
5. Calibration needs full 3-D coverage; the fit is plain algebraic least squares, not outlier-robust, with no automatic accept/reject threshold.
6. Time-varying interference (motor/ESC currents) is detected, not compensated.
7. Risk of double calibration if the FC / AP_Periph already applies offsets (single-calibration rule: our ellipsoid fit is the only intended calibration; `meta.fc_mag_calibrated=true` still applies our fit and multiplies quality by 0.7, with no new warning code).
8. Declination is a user-supplied constant; no WMM/IGRF, no grid north.
9. Heading is ill-conditioned at high dip; tilt near ±90° pitch is not supported.
10. Quality is a heuristic, not a calibrated error bound; thresholds are untuned on data.
11. `HIGH_NOISE` conflates noise and lag without gyro.
12. Monte Carlo noise/bias parameters are [ASSUMED], not board measurements.
13. Warning codes are frozen by the PM, so FC-calibration-active has no own code (quality only; the app warns).
14. **Frozen-data and quantised-mode thresholds are PROVISIONAL** until a hardware replay log exists. Listed values: 0.5 s / 10 samples / 1e-6 µT / 1e-7 g; quantised mode: ratio 3, motion threshold 3°, gyro deadband 1°/s, LP 0.5 s / 0.2 s, 1 g tolerance 0.05 g, no-gyro window 5 s, quality factor ≥ 0.3×; `expected_mag_noise_uT` 0.015 µT; grid inference; `fc_mag_calibrated_quality_factor` 0.7. A sensor stuck at a noisy value or slowly drifting is not detected. A non-decimal quantisation step without meta is not inferred and uses the 0.5 s rule.
14a. **Residual (D3): a mag-only freeze on a stationary vehicle cannot be detected on quantised hardware.** With 0.1 µT steps and 15 nT noise, a healthy still sensor repeats bit-identical readings, so there is no evidence to separate “frozen” from “still” without motion. Detection needs rotation > 3° (beyond the 1°/s deadband) or a > 3° tilt change. Slow turns < 1°/s, or rotation about the field direction, with a frozen mag go unflagged; a gyro bias > ~1°/s (magnitude) could cause false alarms. **Default `quant_nogyro_time_rule=False`** (PM D3 decision (a), `f31784a`): without gyro, only a > 3° accel tilt change is evidence, so a frozen mag on a vehicle that only yaws (level turn) with no gyro is not detected. The opt-in 5 s rule (`True`) catches long freezes without gyro but also warns on healthy still sensors (4/20 Auditor E3b sessions in the earlier configuration; warning only, quality kept). Quantised stationary data with no accel channel still raises `SENSOR_STALE` after 0.5 s.
15. Temperature drift, RM3100 linearity (0.5 % [DATASHEET]) and cycle-count changes are not modelled.
16. Heading is not course over ground; no speed, distance or place estimate is provided.
17. **Scope rule (binding):** dead-reckoning figures are error analysis only; `heading_core` does not and will not provide a position, displacement or distance feature.

Sensor-spec LIMITATIONS (SPEC.md §10 / tracker S1–S11, in brief): no WMM/IGRF evaluation in code (S1); §8.2 priors are [ASSUMED] except RM3100 noise/resolution [DATASHEET] (S2); Matek CAN path frame/units at the FC/MSP boundary must be confirmed before applying formulas to logs (S3); Euler heading undefined near |pitch| = 90° (S5); algebraic ellipsoid fit cannot recover misalignment rotation (S6); spherical haversine/rhumb error up to ~0.5% (S7); dipole/wire models are far-field idealisations (S8); temperature linear only (S9); error-budget terms assumed independent (S10); TC07/TC18 Monte Carlo tolerances are statistical (3–4%) (S11). S4 (accel sign) is now the agreed contract (specific force, level z = −1 g); native FC sign remains unverified on hardware.

Tracker items: T2 REVIEW; D1 CLOSED (T6 re-test PASS at `403976b`); D3 REVIEW, awaiting Auditor re-test after decision (a).

## 4. Money spent and paid tools or services

**None.** No purchases, subscriptions, paid APIs or paid services. Only free tools and libraries were used:

- Python 3.13.5, numpy 2.5.5, pytest 9.2.0, jsonschema 4.26.0 — installed from PyPI into `/workspace/venvs/hm` (confirmed with `pip list` in that venv).
- pandoc 3.9 via `pypandoc_binary` 1.17 in `/workspace/.venv-pdf` (binary at `/workspace/.venv-pdf/lib/python3.13/site-packages/pypandoc/files/pandoc`; not on the system `PATH`). Confirmed with `/workspace/.venv-pdf/bin/pip list` and `pandoc --version` from that path.
- Google Chrome 156.0.8078.47, invoked headless by `docs/math/sensor-spec/render_pdf.sh`.
- MathJax 3 loaded from the public CDN `https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg-full.js` (same script), used only to render SPEC.pdf.

No paid tools or services.
