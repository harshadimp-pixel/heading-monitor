# Heading mathematics, calibration and filtering (T2, `heading_core/`)

Owner: Mathematics & Sensor Scientist. Status: REVIEW (D1 fixed; PM review decisions 3–4 implemented 2026-11-27). Implementation: `heading_core/` (numpy only).
Evidence labels follow README ground rule 1. Every performance number in this document is
**[SIMULATED]** (synthetic data from `heading_core/synth.py`) unless tagged [DATASHEET]. Nothing here is
hardware-verified; no physical RM3100 / Matek FC was used.

Contents: 1 Quantities · 2 Frames and conventions · 3 Forward model · 4 Tilt compensation · 5 Ellipsoid
calibration · 6 Error model · 7 Smoothing · 8 Quality metric and warnings · 9 API summary ·
10 Accuracy experiment · 11 Reference test cases · 12 Assumptions · 13 LIMITATIONS

---

## 1. Heading versus movement, distance and where the vehicle is

These are different mathematical objects; this library computes only the first.

> **Scope rule (Auditor condition):** heading_core does not and must never provide a position, displacement or
> distance feature. Cross-track / dead-reckoning numbers are not features: they are error analysis only
> (here and in `docs/math/sensor-spec/`).

| Quantity | Definition | Sensor that observes it | In heading_core? |
|---|---|---|---|
| Heading ψ | Angle of the body x-axis (nose) projected on the horizontal plane, clockwise from north | magnetometer + accelerometer (tilt) | **yes** |
| Course over ground χ | Direction of the horizontal velocity vector v: χ = atan2(v_E, v_N) | needs velocity (GNSS, optical flow, airspeed+wind) | no |
| Distance travelled s | s = ∫ ‖v‖ dt (path length), a scalar | needs speed | no |
| Geographic place (lat/lon) | p(t) = p(0) + ∫ v dt | needs velocity or absolute fixes | no |

* χ ≠ ψ in general: χ − ψ is the crab / sideslip angle (wind, lateral drift, a multirotor can translate in any
  direction regardless of where its nose points). A stationary vehicle has a well-defined heading but no course.
* Heading carries **no** information about speed, so it cannot by itself give distance or where the vehicle is.
  Integrating velocity built from heading plus an assumed speed is not done here and is not claimed: such an
  estimate's error grows without bound (a constant heading error δψ alone gives a cross-track error ≈ s·sin δψ,
  i.e. ~1.7 % of distance per degree), before even counting speed errors.
* Magnetic vs true vs grid north: ψ_true = ψ_mag + D, with D the magnetic declination (east positive). Grid north
  (map projections) differs again by the meridian convergence; not handled here.

## 2. Frames and conventions

* **Body frame** (ARCHITECTURE.md): NED-style, x forward, y right, z down. Units: µT, g, deg/s.
* **Navigation frame**: local NED (x north, y east, z down). True north unless stated; magnetic north is the
  direction of the horizontal Earth field.
* **Euler angles**: aerospace ZYX sequence, yaw ψ, pitch θ, roll φ. C_nb = R_z(ψ) R_y(θ) R_x(φ) maps body to NED
  (v_n = C_nb v_b). Roll > 0 = right side down, pitch > 0 = nose up, ψ clockwise seen from above.
* **Heading output**: degrees in [0, 360) (`wrap360` guards the 360.0 round-off case). Magnetic unless a
  declination is passed, then true.
* **Accelerometer sign** (configurable `CoreConfig.accel_convention`):
  * `"specific_force"` (default; physical accelerometer output, ArduPilot-style, and what `sim/` emits):
    level and at rest reads **(0, 0, −1) g**. Gravity direction in body g_b = −a.
  * `"gravity"`: the reading is the gravity vector itself; level reads (0, 0, +1) g. g_b = a.
  If the wrong convention is configured the computed tilt is ~180° and `TILT_TOO_LARGE` fires, so the mismatch
  is visible rather than silent.

## 3. Forward model (used by tests, the experiment, and for the Simulation Developer)

Earth field in NED with total intensity F, inclination (dip) I (+ down), declination D:

    B_n = F [cos I cos D,  cos I sin D,  sin I]^T              H = F cos I  (horizontal intensity)

True body field and static accelerometer:

    b = C_nb^T B_n
    g_b = C_nb^T [0,0,1]^T = [−sin θ,  sin φ cos θ,  cos φ cos θ]^T,   a = −g_b (specific force)

Sensor model (hard iron o, soft iron / scale / misalignment A, noise n, quantisation q):

    m = q( A b + o + n ),     q(x) = LSB · round(x / LSB)

RM3100 @ cycle count 200: LSB = 1/75 µT (gain 75 LSB/µT), noise 15 nT [DATASHEET] (PNI RM3100 user manual
Table 3-1; also docs/hardware/FACTSHEET.md). Code: `heading_core/synth.py` (`body_field`, `body_accel`,
`distort`, `random_orientations` (uniform random rotations via normalised Gaussian quaternions)).

## 4. Tilt compensation

Roll and pitch from the (static) gravity direction g_b = (g_x, g_y, g_z):

    φ = atan2(g_y, g_z)                     (−180, 180]
    θ = atan2(−g_x, √(g_y² + g_z²))          [−90, 90]

De-rotate the calibrated body field b = (m_x, m_y, m_z) by roll then pitch into the level frame
(i.e. R_y(θ) R_x(φ) b):

    X_h =  m_x cos θ + m_y sin φ sin θ + m_z cos φ sin θ
    Y_h =  m_y cos φ − m_z sin φ
    Z_v = −m_x sin θ + m_y sin φ cos θ + m_z cos φ cos θ

Heading, dip and tilt:

    ψ = wrap360( atan2(−Y_h, X_h) + D )
    I_meas = atan2(Z_v, √(X_h² + Y_h²))
    tilt   = acos(cos φ cos θ)

Derivation: R_y(θ)R_x(φ) b = R_z(ψ)^T B_n = (H cos ψ, −H sin ψ, F sin I) for D = 0, hence
tan ψ = −Y_h / X_h. Level check: nose north → b = (H, 0, Z); nose east → b = (0, −H, Z) (north is on the left).
Undefined when X_h = Y_h = 0 (field vertical in the level frame, e.g. near magnetic poles); the code raises
`ValueError` in `tilt_compensated_heading` and emits `INVALID_MAG` in the estimator.

Roll/pitch priority in `HeadingEstimator`: `accel_g` → `fc_attitude_deg.roll/pitch` → level assumed
(`NO_ACCEL`). Gyro is used only for filter propagation (section 7).

## 5. Ellipsoid (hard + soft iron) calibration

With |b| = F constant during a calibration rotation, m − o = A b lies on the ellipsoid

    (m − o)^T Q (m − o) = 1,   Q = (A A^T)^{-1} / F²   (symmetric positive definite)

**Fit** (`Calibration.fit(samples, method="ellipsoid")`): centre and scale the data (y = (m − μ)/s) for
conditioning, then linear least squares on the 9-parameter quadric

    a y₁² + b y₂² + c y₃² + 2d y₁y₂ + 2e y₁y₃ + 2f y₂y₃ + 2g y₁ + 2h y₂ + 2i y₃ = 1

With M = [[a,d,e],[d,b,f],[e,f,c]], v = (g,h,i): centre c_y = −M⁻¹v, k = 1 + c_yᵀ M c_y, Q_y = M/k.
Back in µT: o = μ + s c_y, Q = Q_y / s². Rejected (ValueError) if the design matrix is rank-deficient
(σ_min/σ_max < 1e-6, e.g. a level yaw-only spin), if k ≤ 0 or Q is not positive definite, or with < 9 samples.
Non-finite rows are dropped.

**Correction matrix**: with Q = V Λ Vᵀ, Q^{1/2} = V Λ^{1/2} Vᵀ, the field radius is normalised to the
geometric-mean radius R = det(Q)^{−1/6} so that

    W = R · Q^{1/2},   det W = 1,   b_cal = W (m − o),   |b_cal| ≈ R

This keeps the calibrated field in µT and comparable with the expected Earth field (R is stored as
`Calibration.field_uT` and used as the magnitude reference). For a symmetric A, W A = det(A)^{1/3} I exactly.
For a general A = P S (polar decomposition, P rotation), W A = det(A)^{1/3} P: **a rotational part of the
distortion (sensor-to-body misalignment) cannot be recovered by any magnetometer-only fit** and remains as a
heading error.

**Sphere fit** (`method="sphere"`, offset only, W = I): linear LS on |y|² = 2 c·y + k; robust when coverage is
poor. Fit diagnostics: `residual_rms` (RMS of |b_cal| − R), `coverage` (fraction of 26 cube direction bins hit
by the calibrated field), `n_samples`.

**Serialisation**: `to_dict()` → `{"version":1, "method", "offset_uT":[3], "soft_iron":[[3x3]], "field_uT",
"residual_rms_uT", "n_samples", "coverage"}`; `from_dict` is its inverse (also accepts `offset`/`soft_iron_matrix`).

## 6. Error model (first order, level, verified numerically in tests/experiment)

* **Magnetometer white noise** σ_m per axis: σ_ψ ≈ σ_m / H rad. Example: σ_m = 15 nT [DATASHEET], F = 50 µT,
  I = 40° → H = 38.3 µT → σ_ψ ≈ 0.022°. Monte Carlo with error-free accel gave 0.024° RMS [SIMULATED].
* **Residual hard iron** (b_x, b_y) in the level frame: ψ_meas = atan2(H sin ψ − b_y, H cos ψ + b_x),
  δψ ≈ −(b_x sin ψ + b_y cos ψ)/H rad — a one-cycle error over ψ (1° per ~0.67 µT at H = 38 µT).
* **Residual soft iron**: two-cycle (2ψ) error, amplitude ≈ ε rad for a fractional scale/cross-axis error ε.
* **Tilt error** (δφ, δθ = estimated − true roll/pitch, near level):
  δψ ≈ tan I · (δφ cos ψ − δθ sin ψ). Verified numerically: I = 40°, 0.5° roll error at ψ = 0 → 0.4195°.
  Accelerometer bias β (g) gives δφ, δθ ≈ β rad; e.g. 5 mg → 0.29° → up to 0.24° heading at I = 40°.
  Errors grow with dip: tan I = 0.84 (40°), 1.73 (60°), 5.7 (80°).
* **Dynamic acceleration**: the accelerometer measures specific force, so any linear/centripetal acceleration
  a_lin corrupts tilt by ≈ a_lin/g rad (and heading via the formula above). Not modelled; see LIMITATIONS.
* **No tilt compensation** (level assumed while tilted): error up to tens of degrees (−65° for I = 60°,
  ψ = 45°, φ = 30°); this is why tilt compensation is mandatory.

## 7. Smoothing (wrap-safe)

All angle arithmetic uses `angle_diff_deg(a,b) ∈ (−180,180]` and `wrap360`, never raw subtraction.

**Complementary filter** (default, `smoothing="complementary"`):

    ψ̂⁻ₖ = wrap360( ψ̂ₖ₋₁ + ψ̇ Δt )                      (gyro propagation, if gyro_dps present and use_gyro)
    ψ̇  = (q sin φ + r cos φ) / cos θ                 (ZYX Euler yaw rate from body rates p,q,r)
    νₖ = angle_diff(ψ_mag,k, ψ̂⁻ₖ)                     (innovation)
    ψ̂ₖ = wrap360( ψ̂⁻ₖ + α · q_field · νₖ )

q_field (section 8) de-weights samples whose field magnitude is disturbed. Without gyro the filter is a circular
EMA with steady-state lag on a constant rate ω: lag = ω Δt (1 − α)/α (e.g. 30°/s, 50 Hz, α = 0.05 → 11.4°;
the Monte Carlo measured 11.43° [SIMULATED]). Gyro propagation removes this lag; gyro bias b_g gives a steady
offset ≈ b_g Δt (1 − α)/α (0.2°/s → 0.08°).

**Circular mean** (`smoothing="circular_mean"`, window N): ψ̂ = atan2(Σ sin ψᵢ, Σ cos ψᵢ). Lag on a ramp ≈
ω Δt (N − 1)/2 (N = 25 → 7.2° at 30°/s, measured 7.21° [SIMULATED]). Does not use gyro.

Filter resets on dt ≤ 0 or dt > `max_dt_s` (1 s). Invalid magnetometer samples (non-finite, zero field, zero
horizontal field) do not touch the filter state; the previous heading is held with quality 0.

## 8. Quality metric and warnings

Each factor uses the soft penalty f(d, tol) = 1/(1 + (d/tol)²) (1 at 0, 0.5 at the tolerance, 0.2 at 2×):

    quality = f(| |b|/B₀ − 1 |, field_tolerance_frac)        B₀ = Calibration.field_uT if present else expected_field_uT (50 µT)
            × f(tilt, max_tilt_deg)
            × f(|I_meas − I_expected|, dip_tolerance_deg)      only if expected_dip_deg configured
            × f(noise, noise_warn_deg)                         noise = RMS of last N innovations ν (deg)
            × 0.5 if not calibrated  × 0.7 if no tilt source
            × 0.05 SENSOR_STALE / 0.3 MAG_STALE / 0.05 TIMESTAMP_STALE;   0 for invalid magnetometer samples

**Frozen / stale data (defect D1).** A frozen or disconnected sensor typically keeps returning its last value.
For each channel (mag, accel) the estimator keeps the first vector of the current run r₀ and its time t₀; a new
reading v continues the run while maxᵢ|vᵢ − r₀ᵢ| ≤ tol (1e-6 µT mag, 1e-7 g accel — "near-identical", far
below RM3100 noise of 15 nT). The channel is frozen when t − t₀ ≥ `stale_window_s` (0.5 s) and the run has ≥
`stale_min_samples` (10). Any change beyond tol restarts the run, so recovery is immediate on the first live
sample. An absent accel channel counts as frozen (it cannot contradict the mag). Timestamps: t ≤ previous t ⇒
`TIMESTAMP_STALE`; a backwards jump larger than `max_dt_s` (1 s) is treated as a new stream (filter reset), not
staleness. All thresholds are in `CoreConfig` (`stale_detection=False` disables the frozen check). Test cases:
3 s identical at 50 Hz flagged from 0.5 s with quality ≤ 0.05 and cleared on the first noisy live sample.

**Quantised sources (PM decision 2026-11-27; thresholds PROVISIONAL).** A source with coarse mag steps sets
`meta.mag_quant_uT` (MSP: 0.1 µT). The value is remembered for the stream (meta may appear on the first line only);
`CoreConfig.mag_quant_uT` overrides it. If neither is present, q is **inferred** from the data
(`infer_mag_quant`, on by default, **approved by the PM 2026-11-27**, PROVISIONAL): the largest candidate step in {1, 0.5, 0.1, 0.05, 0.01} µT on which every mag
component seen so far lies (within 1e-6 µT), after ≥ 5 samples; one off-grid reading rules a step out for the
stream. Continuous data and RM3100 counts/75 are never on such a grid. Priority: config > meta > inferred. If q ≥ `quant_noise_ratio` (3) × `expected_mag_noise_uT` (0.015 µT,
RM3100 @ CC 200 [DATASHEET]) the estimator is in *quantised mode*. Rationale: with 0.1 µT steps ≫ 15 nT noise a
still sensor legitimately repeats readings, often for many seconds (up to 23 s in our 20 Hz sessions); from
mag data alone a still sensor and a frozen one are indistinguishable (defect D3).

*Quantised-mode `MAG_STALE` rule (D3, PM decision 2026-11-27; all thresholds PROVISIONAL).* MAG_STALE needs
**motion evidence while the mag stays bit-identical** (exact equality since the reading last changed):

* **Gyro evidence** (chosen integration): ω̄ = first-order low-pass of the body-rate vector
  (τ = `quant_gyro_lp_tau_s` = 0.5 s), θ_g = ∫ max(0, ‖ω̄‖ − ω_db) dt with deadband ω_db =
  `quant_gyro_deadband_dps` = 1°/s, **reset to 0 whenever the mag changes**. Why: plain integration turns a
  0.2°/s/axis residual bias into ~21° over 60 s (‖b‖ = 0.35°/s); resetting on mag change bounds the window, and the
  deadband (above any plausible post-boot residual bias, and above INAV's 1°/s integer gyro quantisation dithered
  by bias) makes the bias contribution exactly zero. Online bias estimation was rejected: with no trusted
  "stationary" signal it would absorb a slow constant spin. The low-pass removes white gyro noise.
* **Accel evidence**: change of low-passed (τ = `quant_accel_lp_tau_s` = 0.2 s) accel roll/pitch since the mag last
  changed, max(|Δφ|, |Δθ|). Used only while | ‖a‖ − 1 g | ≤ `quant_accel_1g_tol_g` (0.05 g), so linear
  acceleration does not fake a tilt change. Accel bias cancels (difference).
* Flag when θ_g > `quant_motion_threshold_deg` (3°) **or** accel evidence > 3°: `MAG_STALE`, quality ×
  max(0.3, `mag_stale_quality_factor`) = 0.3 (never below 0.3×).
* **No gyro** in the sample: **only** the accel-tilt evidence rule above (quality ×0.3) — default since the PM's
  D3 decision (a), 2026-11-27. The time rule `quant_nogyro_time_rule` is **opt-in (default False)**: if enabled,
  bit-identical for ≥ `stale_quant_window_s` (5 s) → `MAG_STALE` as a **warning only, quality not cut**. With gyro
  present the time rule is never used.

`SENSOR_STALE` (mag near-identical **and** accel frozen or absent, 0.5 s, ×0.05) and `TIMESTAMP_STALE` are
unchanged in both modes; non-quantised mode is unchanged (0.5 s near-identical rule, ×0.3).

False-alarm results [SIMULATED] (`heading_core/tests/test_heading_core.py::test_d3_*`; 20 seeded 60 s stationary
sessions each, 0.1 µT grid, RM3100 15 nT, accel 2 mg + 1/512 g steps, gyro 0.1°/s noise): 0/20 false MAG_STALE /
SENSOR_STALE for gyro bias U(±0.2)°/s/axis @ 50 Hz, U(±0.5) @ 50 Hz, U(±0.3) with integer-°/s gyro @ 50 Hz, and
U(±0.2) @ 20 Hz. Peak evidence: gyro 0.000°, accel 0.18–0.24° (threshold 3°). Longest legitimately bit-identical
run: 9.3 s @ 50 Hz, 23.3 s @ 20 Hz. Detection: frozen mag during a 30°/s and a 5°/s turn is flagged; a 10° pitch
change without gyro is flagged by accel.

**Single-calibration rule (ARCHITECTURE.md 2026-11-27).** The ellipsoid fit in heading_core is the only intended
magnetometer calibration; the FC's own mag calibration is kept neutral (INAV magzero = 0, maggain = 1024). The
bridge reports `meta.fc_mag_calibrated` (true / false / "unknown"), remembered per stream. heading_core handles it
within the frozen codes:
* `false`, `"unknown"` or absent: no effect.
* `true`: our calibration is still applied unchanged and no warning code is added (none of the frozen codes means
  "FC calibration active"; `NOT_CALIBRATED` would be false). Quality is multiplied by
  `fc_mag_calibrated_quality_factor` (0.7, PROVISIONAL). Reason: a *fixed* FC affine correction composed with our
  fit is still an affine map and is absorbed by the fit, but it may change after our fit (FC re-calibration),
  which silently invalidates it. The app shows the user-facing warning (ARCHITECTURE.md: "the app warns if not
  false"). `last_debug["fc_mag_calibrated"]` exposes the flag. This quality-only handling was **approved by the
  PM 2026-11-27**.

Warning codes (frozen as contract in ARCHITECTURE.md 2026-11-27; `heading_core/warnings_codes.py`; the schema only says "array of strings"):

| Code | Trigger (defaults) |
|---|---|
| `NOT_CALIBRATED` | estimator has no `Calibration` |
| `FIELD_MAGNITUDE_OUT_OF_RANGE` | \| \|b\|/B₀ − 1 \| > 0.15 (interference / bad calibration) |
| `TILT_TOO_LARGE` | tilt > 45° |
| `DIP_ANGLE_ANOMALY` | \|I_meas − expected_dip_deg\| > 5° (only if configured) |
| `NO_ACCEL` | no usable accel and no fc_attitude roll/pitch (level assumed) |
| `HIGH_NOISE` | innovation RMS > 3° (also fires during fast turns without gyro — it measures lag too) |
| `INVALID_MAG` | non-finite mag, zero field or zero horizontal field; sample ignored |
| `SENSOR_STALE` | mag **and** accel (if present) frozen for ≥ `stale_window_s` (0.5 s) and ≥ 10 samples (D1); quality × 0.05 |
| `MAG_STALE` | mag frozen as above while accel still changes; quality × 0.3. Quantised mode: bit-identical mag **plus** gyro/accel motion evidence > 3° (×0.3); no gyro: also bit-identical ≥ 5 s, warning only (PROVISIONAL) |
| `TIMESTAMP_STALE` | `t` ≤ previous `t` (repeated or out-of-order); sample not fed to the filter, held heading output; quality × 0.05 |

## 9. API summary

```python
from heading_core import Calibration, tilt_compensated_heading, HeadingEstimator, CoreConfig
cal = Calibration.fit(list_of_mag_uT)                    # or method="sphere"
b = cal.apply(m)                                         # list[float]
psi = tilt_compensated_heading(b, accel_g, declination_deg=0.0)   # [0,360)
est = HeadingEstimator(cal, declination_deg=0.0, config=CoreConfig())
out = est.update(sample_dict)   # -> HeadingEstimate dict (contracts/heading_estimate.schema.json)
est.last_debug                  # extra per-sample values (calibrated vector, dip, tilt, noise) not in the contract
```
`HeadingEstimator.__init__` has an extra optional `config` keyword (ARCHITECTURE signature otherwise unchanged).
`tilt_compensated_heading` has an extra optional `accel_convention` keyword.

## 10. Accuracy experiment [SIMULATED]

`python -m heading_core.experiments.accuracy_mc --trials 200 --seed 2026` → `docs/math/accuracy_results.md`
and `.json` (full parameter list there). 200 trials; each draws hard iron U(±30 µT), symmetric soft iron
I + U(±0.10), a 300-sample full-sphere calibration set, then 500 test attitudes (ψ uniform, roll/pitch U(±30°)).
Noise: RM3100 15 nT + 1/75 µT quantisation [DATASHEET]; accel 3 mg white + 5 mg per-trial bias, platform
noise 0.3 µT, gyro 0.05°/s noise + 0.2°/s bias — these are **assumptions**, not measured values.
F = 50 µT, I = 40°.

| Case [SIMULATED] | RMS ° | P95 ° | Max ° |
|---|---|---|---|
| Raw (no calibration), tilt-compensated | 29.505 | 55.361 | 179.760 |
| Hard-iron only (sphere fit) | 2.994 | 5.829 | 11.121 |
| Ellipsoid fit (hard + soft iron) | 0.301 | 0.605 | 1.751 |
| Ellipsoid fit, error-free accel (mag + fit error only) | 0.024 | 0.046 | 0.104 |
| Ellipsoid fit, NO tilt compensation | 16.129 | 30.407 | 57.073 |
| Ellipsoid fit + 0.3 µT platform noise | 0.564 | 1.111 | 2.763 |
| Ellipsoid fit, true soft iron has ±0.02 skew (misalignment) | 0.691 | 1.330 | 2.962 |
| Static hold, per-sample (0.3 µT platform noise) | 0.556 | 1.094 | 2.466 |
| Static hold, complementary α = 0.05 + gyro | 0.273 | 0.529 | 1.055 |
| Static hold, circular mean N = 25 | 0.271 | 0.531 | 1.155 |
| 30°/s spin, per-sample | 0.557 | 1.093 | 2.964 |
| 30°/s spin, complementary + gyro | 0.268 | 0.527 | 1.024 |
| 30°/s spin, complementary, no gyro | 11.425 | 11.830 | 12.385 |
| 30°/s spin, circular mean N = 25 | 7.208 | 7.630 | 8.198 |

Reading: after calibration the error budget is dominated by accelerometer bias (tilt error × tan I), which
smoothing cannot remove (smoothed floor ≈ 0.27°). Sensor noise of the RM3100 itself is negligible (0.024°).
Filtering without gyro trades noise for lag during turns; the lag values match the analytic formulas in §7.

### 10b. Cross-check against the T3 simulator [SIMULATED]

`python -m heading_core.experiments.sim_check` (results in `docs/math/sim_check_results.md`): calibrating on the
sim's 60 s `calibration_dance` recovers the injected hard iron (18, −12, 25) µT; with calibration, per-sample
heading RMS vs `truth.heading_deg` is 0.71–0.83° on static / yaw_spin / tilted_spin and 0.64–0.77° filtered,
against 34–42° RMS uncalibrated on the spin scenarios. This uses the simulator's own noise/bias models, so it checks that the interfaces and
conventions agree, not real-world accuracy.

## 11. Reference test cases (all in `heading_core/tests/test_heading_core.py`, 76 tests)

| Case | Input | Expected |
|---|---|---|
| Level cardinals | b = (30,0,40), (0,−30,40), (−30,0,40), (0,30,40); a = (0,0,−1) | 0°, 90°, 180°, 270° |
| Tilted | ψ,θ,φ ∈ {(30,20,0),(120,0,−25),(250,−35,40),(359,10,10),(0,60,0),(200,−5,70)}, I = 60° | ψ, φ, θ, I recovered to 1e−9° |
| No tilt comp | ψ = 45°, φ = 30°, I = 60°, accel ignored | error > 20° (≈ −65°) |
| Declination | true 100°, D = +5° | 95° magnetic, 100° with D |
| Gravity convention | a = +g_b | same heading/attitude |
| Ellipsoid recovery | 600 random orientations, o = (12,−25,8) µT, sym. soft iron ±0.2, 15 nT noise | offset ±0.05 µT, W A ∝ I (2e−3), det W = 1, residual < 0.05 µT |
| Calibrated heading | 200 random attitudes ±30° | max error < 0.2° (raw > 10°) |
| Degenerate data | 5 samples; level yaw-only circle; NaN row | ValueError; ValueError; row dropped |
| Wrap smoothing | alternating 358°/2° (both modes) | stays within 2.5° of 0°, never near 180° |
| Wrap invariance | 0.5°/sample ramp from 350° vs 170° | identical errors (1e−6) |
| Warnings | no cal; \|B\| = 70 µT; pitch 50°; dip 55° vs 40°; no accel; σ = 8 µT noise; NaN/inf/zero mag | each code fires; invalid sample leaves filter at 45° |
| D1 frozen sensor | 150 identical samples (3 s @ 50 Hz), then live noisy data | `SENSOR_STALE` from 0.5 s, quality ≤ 0.05; clears on first live sample, quality > 0.9 |
| Frozen variants | mag frozen + live accel; no accel; 1e-9 µT jitter; repeated/backward `t`; >1 s backwards jump | `MAG_STALE`; `SENSOR_STALE`; still frozen; `TIMESTAMP_STALE` + held heading; reset, no warning |
| Quantised varying | 0.1 µT steps with 0.06 µT noise (12 s); slow 2°/s turn | never MAG_STALE / SENSOR_STALE |
| Quantised edge cases | q = 0.02 µT (< 3×noise); CoreConfig override; mag+accel frozen | normal 0.5 s rule; quantised mode; SENSOR_STALE ×0.05 unchanged |
| Quantised, no meta | 0.1 µT grid, 4 s bit-identical; continuous noisy data | grid 0.1 inferred, no MAG_STALE; nothing inferred |
| D3 stationary quantised | 4 × 20 seeded 60 s sessions (bias 0.2 / 0.5 / 0.3 + integer gyro / 20 Hz) | 0 false MAG_STALE or SENSOR_STALE |
| D3 frozen mag while turning | 30°/s and 5°/s yaw, mag stuck from 2 s | MAG_STALE, quality = 0.3 × unflagged |
| D3 tilt, no gyro | pitch 0→10°, mag stuck, live accel | MAG_STALE by accel evidence, quality cut |
| D3 bias | 0.2°/s/axis constant for 60 s, mag bit-identical | gyro evidence stays 0, no MAG_STALE |
| D3 no-gyro default | 0.1 µT stationary 12 s, no gyro | no MAG_STALE / SENSOR_STALE, quality = unflagged |
| D3 no-gyro opt-in time rule | same, `quant_nogyro_time_rule=True` | MAG_STALE from 5.0 s, quality equal to unflagged |
| fc_mag_calibrated | true / false / "unknown" / absent | same heading and warnings; quality ×0.7 only for true |
| Accel convention | (0,0,−1) level; nose-up 10° → x = +sin 10°; (0,0,+1) fed in | 0/0; pitch 10°; `TILT_TOO_LARGE` |
| Schema | every estimator output (incl. 300 random-garbage samples) | validates against contracts/heading_estimate.schema.json |

## 12. Assumptions

1. Earth field magnitude 50 µT nominal (configurable, `CoreConfig.expected_field_uT`); after calibration the
   fitted radius is the reference. Dip 40° in the experiment (placeholder — site value from WMM/IGRF needed).
2. Field is uniform and constant during calibration and use (no local gradients, no time variation).
3. Hard/soft iron are constant (rigidly attached ferrous material, no current-dependent fields).
4. Accelerometer measures only gravity (vehicle not accelerating) when used for tilt.
5. Magnetometer axes are aligned with the body frame (any rotation is treated as soft iron and is not observable).
6. Noise is white, Gaussian, isotropic; RM3100 "noise 15 nT" [DATASHEET] interpreted as per-axis 1σ.
7. Sample timestamps are monotonic seconds; gyro in deg/s in the same body frame.

## 13. LIMITATIONS

Unresolved at REVIEW (mirrored in TEAM_TRACKER.md, T2 row):

1. **No hardware validation.** All numbers are [SIMULATED] or [DATASHEET]; nothing is verified on the RM3100 /
   Matek FC (BLOCKERS B1).
2. **Accelerometer-only tilt** is wrong under dynamic acceleration (turns, take-off, vibration); no
   attitude filter (Mahony/EKF) is implemented. `fc_attitude_deg` can be used instead when no accel is supplied,
   but the FC's own attitude quality is unknown.
3. **Accelerometer sign of real FC data is unverified.** ARCHITECTURE.md (2026-11-27) fixes the contract to
   specific force (level = (0,0,−1) g), which the core and `sim/` use. Whether MSP_RAW_IMU from INAV/Betaflight
   reports +1 g on z, and whether its axes are NED, has not been checked on hardware; the firmware bridge (T4)
   must convert. `accel_convention="gravity"` exists as an escape hatch.
4. **Magnetometer/body misalignment** (rotational part of the distortion) is not observable by the ellipsoid
   fit; ±0.02 skew already doubles RMS error (0.30° → 0.69° [SIMULATED]). Needs a separate alignment step
   (e.g. known-heading references) — not implemented.
5. **Calibration needs full 3-D orientation coverage.** Yaw-only data is rejected (ValueError) and the user must
   fall back to `method="sphere"`; partial coverage is only flagged by the `coverage` diagnostic, not by an
   automatic accept/reject threshold. Fit is plain algebraic least squares (not outlier-robust; not the
   geometrically optimal fit), so interference spikes in calibration data bias it.
6. **Time-varying interference** (motor/ESC currents) is only detected via field magnitude / dip / noise checks;
   it is not compensated (no current-based compensation like ArduPilot's compass-motor calibration).
7. **Matek RM3100 CAN module path**: if the FC (ArduPilot/AP_Periph) already applies its own compass offsets,
   applying a heading_core calibration on top would double-correct. Which data (raw vs FC-calibrated) the bridge
   delivers is undetermined (depends on T1/T4).
8. **Declination is a user-supplied constant**; no WMM/IGRF model, no location input, no secular variation.
   Grid north / meridian convergence not handled.
9. **Heading undefined near vertical field** (high dip, |X_h|,|Y_h| → 0); sensitivity to tilt error grows as tan I.
   Behaviour above ~80° dip is not characterised. Tilt near ±90° pitch (gimbal lock) is not supported.
10. **Quality metric is heuristic** (product of soft penalties with hand-picked tolerances); it is not a calibrated
    probability or a heading-error bound. Thresholds (15 % field, 45° tilt, 5° dip, 3° noise) are not tuned on data.
11. **HIGH_NOISE conflates noise and lag**: without gyro, fast turns raise innovation RMS and can trigger it.
12. **Noise/bias parameters of the experiment** (accel 3 mg / 5 mg, 0.3 µT platform noise, gyro values, hard/soft
    iron ranges) are assumptions, not measurements of our board.
13. Warning codes and the `config` / `accel_convention` keywords were approved by the PM (ARCHITECTURE.md
    2026-11-27); new codes need PM sign-off, so some conditions (e.g. FC calibration active) have no own code.
14. **Frozen-data and quantised-mode thresholds are PROVISIONAL** until a hardware replay log exists (0.5 s /
    10 samples / 1e-6 µT / 1e-7 g; quantised mode: ratio 3, motion threshold 3°, gyro deadband 1°/s, LP 0.5 s /
    0.2 s, 1 g tolerance 0.05 g, no-gyro window 5 s, factor ≥ 0.3×; `expected_mag_noise_uT` 0.015 µT;
    grid inference; `fc_mag_calibrated_quality_factor` 0.7). A sensor stuck at a *noisy* value or slowly drifting
    is not detected. A source quantised on a non-decimal step without meta is not inferred and uses the 0.5 s rule.
    `fc_mag_calibrated = true` cannot be expressed by a frozen warning code; only quality reflects it in the core.
14a. **Residual (D3): a mag-only freeze on a stationary vehicle cannot be detected on quantised hardware.** With
    0.1 µT steps and 15 nT noise a healthy still sensor repeats bit-identical readings, so without motion there is
    no evidence to separate "frozen" from "still". Detection needs rotation > 3° (beyond the 1°/s deadband) or a
    > 3° tilt change. Consequences: slow turns < 1°/s, or rotation about the field direction, with a frozen mag go
    unflagged; a gyro bias > ~1°/s (magnitude) could cause false alarms. **Default `quant_nogyro_time_rule=False`**
    (PM D3 decision (a)): without gyro only a > 3° accel tilt change is evidence, so a frozen mag on a vehicle that
    only yaws (level turn) with no gyro is not detected. The opt-in 5 s rule (True) catches long freezes without
    gyro but also warns on healthy still sensors (4/20 Auditor E3b sessions; warning only, quality kept). Quantised stationary data with **no** accel channel still raises
    `SENSOR_STALE` after 0.5 s (unchanged rule).
15. Temperature drift, RM3100 linearity (0.5 % [DATASHEET]) and cycle-count changes are not modelled.
16. Heading is not course over ground; no speed, distance or place estimate is provided or implied (section 1).
17. **Scope rule (Auditor condition, binding):** heading_core does not and will not provide a position,
    displacement or distance feature; dead-reckoning figures are not a feature, only error analysis (this
    document and `docs/math/sensor-spec/`). Adding such a feature is out of scope for T2.
