# sim/ — virtual RM3100 + flight-controller IMU simulator (T3)

> **THIS IS A SIMULATION, NOT HARDWARE CHARACTERISATION.**
> Every value this package emits is **[SIMULATED]**. RM3100 constants are datasheet *typical* values
> (**[DATASHEET]** at cycle counts 50/100/200, cross-checked against T1's `docs/hardware/FACTSHEET.md`; other cycle
> counts are **[DERIVED-APPROX]** and flagged `provisional`); IMU, interference and environment
> constants are **ASSUMED** round numbers chosen for testing. Nothing here describes the behaviour of our
> physical RM3100 or Matek FC, and no result from it may be tagged `[HARDWARE-VERIFIED]`.

Emits `Sample` objects (`contracts/sample.schema.json`) as JSON Lines with `source: "sim"` and a
ground-truth `truth` block, so `heading_core` and `app` can be developed and tested end to end.

## Install and run
```bash
pip install -r requirements.txt          # numpy, pytest
pip install jsonschema                   # only needed for the schema-validation tests (see Questions)

python -m sim --rate 50 --duration 60 --scenario yaw_spin --seed 1            # JSONL on stdout
python -m sim --rate 50 --duration 60 --scenario calibration_dance --seed 1 --out cal.jsonl
python -m sim --list-scenarios
python -m sim --scenario hard_iron --describe                                   # resolved config, JSON
python -m pytest sim/tests -q
```
Options: `--cycle-count N` (RM3100, default 200), `--field-total uT`, `--inclination deg` (+down),
`--declination deg` (+east), `--hard-iron X Y Z`, `--soft-iron w11..w33` (row-major), `--motor-k X Y Z` (uT/A),
`--env-noise uT`, `--imu-noise-scale k`, `--mag-noise-scale k`, `--no-fc-attitude`, `--realtime`
(wall-clock pacing for a live feed), `--out FILE` (`--tee` to also print to stdout).
Output is byte-for-byte deterministic for a given seed and options. Defaults: seed 0, rate 50 Hz, 60 s.

## Scenarios
| name | attitude | disturbances |
|---|---|---|
| `static` | level, true yaw 30° | sensor + IMU noise only |
| `yaw_spin` | level, 1 rev / 20 s (18 °/s) | none |
| `tilted_spin` | roll 20°, pitch −15°, yaw 1 rev / 20 s | none |
| `calibration_dance` | roll ±150°, pitch ±70°, yaw 1 rev / 8 s (incommensurate periods) | hard iron (12, −8, 5) µT + mild soft iron. ≥ 30 s recommended; 60 s covers ≥ 80 % of a 50-bin sphere (tested) |
| `hard_iron` | as yaw_spin | offset (25, −15, 10) µT |
| `soft_iron` | as yaw_spin | symmetric W = [[1.15,.06,0],[.06,.88,.03],[0,.03,1]] |
| `motor_interference` | as yaw_spin | motor current vs run fraction: 0 A (0–15 %), 8 A, 20 A, 14±8 A pulsing (55–80 %), 0 A; field = k·I, k = (0.8, −0.4, 1.5) µT/A |
| `high_noise` | as yaw_spin | 1.0 µT/axis environmental field noise, 5× IMU noise |

## Output fields
Contract fields: `t`, `source="sim"`, `mag_uT` (= counts / gain, what a driver reports), `mag_raw` (24-bit counts),
`rm3100_cycle_count`, `accel_g`, `gyro_dps`, `fc_attitude_deg`, `truth{heading_deg, roll_deg, pitch_deg}`, `meta`.

Extra keys inside `truth` (allowed by the schema, which doesn't forbid extra properties): `true_heading_deg`,
`declination_deg`, `earth_field_body_uT` (undisturbed field), `field_at_sensor_uT` (after interference and
environmental noise, before sensor noise and quantisation), `interference_uT` (= field_at_sensor − earth_field_body),
`motor_current_A`.
`meta`: `scenario`, `seed`, `i` (sample index); `rm3100_saturated: true` when clipped; the first line also carries
`disclaimer` and `sim_config` (full resolved config incl. hard/soft-iron truth, Earth field vector, IMU bias truth,
RM3100 gain/noise, evidence label, `provisional` flag and source), so a replayed file describes itself.

`truth.heading_deg` is the **magnetic** heading (yaw − declination), in [0, 360), so it matches
`heading_core` output with `declination_deg=0`; `true_heading_deg` is the true heading.

Example logs (10 Hz, seed 42, ≤ 64 KB each) are in `examples/`; a test regenerates them and checks they match byte for byte.

## Model and assumptions
Frames: NED, body x forward, y right, z down; ZYX Euler (yaw, pitch, roll), yaw from true north.

1. **Earth field**: uniform and constant, `B_ned = F·[cos I cos D, cos I sin D, sin I]`. Defaults F = 50 µT,
   I = 60°, D = 0° are generic placeholders, not our site.
2. **Field at the sensor**: `B = W·(Rᵀ B_ned) + h + k·I(t) + n_env`, where W is the soft-iron matrix (it acts on the
   Earth field only), h the hard-iron offset, k the motor coefficient (µT/A), I(t) the motor current and n_env white noise.
3. **RM3100** ([DATASHEET] typicals, PNI RM3100/RM2100 User Manual V16.0 Table 3-1 and Section 5.1,
   <https://www.pnisensor.com/wp-content/uploads/RM3100-RM2100-Sensor-Suite-User-Manual-V11.0.pdf>; PNI RM3100
   sales sheet 2020, <https://www.pnisensor.com/wp-content/uploads/PNI-Sensor-RM3100-Sales-Sheet.pdf>):
   | cycle count | 50 | 100 | 200 |
   |---|---|---|---|
   | gain, LSB/µT | 20 | 38 | 75 |
   | noise, nT | 30 | 20 | 15 |
   | max single-axis rate, Hz (÷3 for 3-axis) | 1600 | 850 | 440 |

   These match T1's `docs/hardware/FACTSHEET.md` (DRAFT, commit bccda22), and a test checks it.
   Default cycle count 200 (register default 0x00C8). At any other cycle count the values are **[DERIVED-APPROX]**
   and `sim_config.rm3100.provisional` is `true`: piecewise-linear between table points, and outside 50–200
   gain ∝ cycle count (≈ 0.3755 LSB/µT per cycle) and noise ∝ 1/√cycle count.
   The datasheet noise figure is used as per-axis 1σ white Gaussian noise. The reading is quantised to integer counts,
   clipped at ±800 µT·gain (manual's monotonic range) and at the 24-bit signed limits, and flagged as saturated.
   A rate above the datasheet's 3-axis maximum prints a warning on stderr but is still simulated.
4. **Accelerometer**: specific force `f = Rᵀ·[0, 0, −1] g` (level and still → [0, 0, −1] g), plus a constant per-seed
   bias (σ 0.01 g) and white noise (σ 0.003 g). Pure rotation: no linear acceleration, vibration or lever arm.
5. **Gyro**: exact body rates from the analytic Euler-angle derivatives (central difference, h = 1e-4 s),
   plus bias (σ 0.3 °/s) and white noise (σ 0.05 °/s). No scale-factor error, misalignment or g-sensitivity.
6. **fc_attitude_deg**: a stand-in for the FC's own estimate. Roll and pitch are truth + 0.3° noise; yaw is
   truth + z-gyro bias × t (drifting, no compass fusion) + noise. It is not a model of INAV, ArduPilot or Betaflight.
7. **Determinism**: `numpy.random.SeedSequence(seed)` spawns independent streams for the bias, mag, environment,
   accel, gyro and FC models.

## LIMITATIONS (unresolved)
1. **The RM3100 figures are datasheet typicals, not per-unit values.** They match T1's FACTSHEET, but that sheet is
   still DRAFT; if T1 revises it, `test_matches_t1_factsheet` will fail. Gain and noise at cycle counts other than
   50, 100 and 200 are **PROVISIONAL / [DERIVED-APPROX]**, because PNI publishes no formula. The typicals were
   specified at 3.0 V with Rb 121 Ω and R_EXT 33 kΩ, and the Matek or breakout board circuit
   may differ.
2. **The two PNI documents disagree on the field range** (manual ±800 µT, 2020 sales sheet ±1100 µT). The sim uses ±800 µT
   and models saturation as hard clipping, whereas the real sensor goes non-monotonic beyond its range.
3. **Gain and noise beyond the 50/100/200 table points are extrapolated (ASSUMED).** The noise model is white Gaussian
   only: no 1/f noise, temperature drift, hysteresis (15 nT), repeatability or ±0.5 % linearity error, and no
   cross-axis or misalignment errors.
4. **The Earth field model is simplified**: uniform and static, with no WMM/IGRF location model, no secular or diurnal
   variation and no local anomalies. The defaults are not our location.
5. **The IMU noise and bias figures are generic MEMS guesses (ASSUMED)**, not the Matek FC's IMU, and the model leaves out
   vibration, linear and centripetal acceleration, temperature effects and scale-factor errors.
6. **The interference models are idealised.** Hard iron is constant. Soft iron is a fixed linear matrix applied to the
   Earth field only. The motor field is a fixed vector proportional to one scalar current, with no per-motor geometry,
   PWM ripple, dynamics or saturation of nearby ferromagnetics. The coefficients are ASSUMED, not measured.
7. **Timing is ideal.** Samples are perfectly periodic, with no I²C/SPI latency, jitter, dropped samples or
   mag/IMU time skew, and no MSP/MAVLink transport effects. Real FC telemetry rates and fields aren't modelled
   (see T4).
8. **fc_attitude_deg is a crude stand-in** and must not be used as a reference for heading accuracy.
9. **GPS and true-north fusion are out of scope for T3** (they aren't in the Sample contract).
10. **Accel sign convention** (specific force, z = −1 g when level) is my choice, because the contract doesn't specify one.
    Some FC firmwares report z ≈ +1 g when level (unverified by T3; T4 to confirm for MSP_RAW_IMU). T2 and T4 must agree; this is raised with the PM.
11. `calibration_dance` needs at least 30 s for good sphere coverage; the 10 s example is only a format sample.
12. `jsonschema` isn't in the repo's `requirements.txt`. Without it the schema tests fall back to a structural check and the
    full-schema parts are skipped.

## Tests
`python -m pytest sim/tests -q` covers schema validation (every scenario, CLI output and example logs), determinism
(same seed gives identical bytes, `--out` matches stdout), the gain table and scaling, counts↔µT consistency, noise vs
model, saturation and 24-bit clipping, field magnitude and dip, truth heading against an independent tilt-compensation
formula (three declinations), measured heading from accel+mag, gyro/accel consistency, calibration-dance sphere
coverage, and hard-iron, soft-iron, motor-interference and high-noise behaviour.
