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
pip install -r requirements.txt          # numpy, pytest, jsonschema

python -m sim --rate 50 --duration 60 --scenario yaw_spin --seed 1            # JSONL on stdout
python -m sim --rate 50 --duration 60 --scenario calibration_dance --seed 1 --out cal.jsonl
python -m sim --list-scenarios
python -m sim --scenario hard_iron --describe                                   # resolved config, JSON
python -m sim --scenario yaw_spin --output-mode dronecan --rate 50 --duration 60   # what the FC receives
python -m sim.spec_check                                                       # sim vs T2 sensor spec, 20 cases
python -m pytest sim/tests -q
```
Options: `--cycle-count N` (RM3100, default 200), `--field-total uT`, `--inclination deg` (+down),
`--declination deg` (+east), `--hard-iron X Y Z`, `--soft-iron w11..w33` (row-major), `--motor-k X Y Z` (uT/A),
`--env-noise uT`, `--imu-noise-scale k`, `--mag-noise-scale k`, `--no-fc-attitude`, `--realtime`
(wall-clock pacing for a live feed), `--out FILE` (`--tee` to also print to stdout),
`--output-mode raw|dronecan|msp` (default `raw`; see "Delivered output modes"), `--delivered-rate Hz` (25),
`--periph-poll Hz` (80), `--attitude ROLL PITCH YAW` (hold a fixed attitude instead of the scenario's),
`--misalignment RX RY RZ` (deg, spec term M), `--mag-bias-gm SIGMA_UT TAU_S` (Gauss-Markov bias, spec term b_rw),
`--imu-bias-scale k` (0 = no accel/gyro bias).
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

Example logs are in `examples/`: five raw-mode logs (10 Hz, seed 42, ≤ 64 KB each) and one each for `dronecan` and `msp` (`yaw_spin`, 50 Hz, 2 s, so they show sample-and-hold). A test regenerates every one and checks it matches byte for byte.

## Delivered output modes (`--output-mode dronecan|msp`)
Per T1 (`docs/hardware/FACTSHEET.md` §2) our module is a **Matek CAN-L4-3100**: the RM3100 sits behind an STM32 running
ArduPilot **AP_Periph**, so the FC never sees RM3100 counts. These modes model what the FC receives. `raw` (the default)
is unchanged, byte for byte.

What I checked in the source code myself ([SOURCE-CODE], ArduPilot commit `6034266b5abffd36fb4b89f0bf61fb6db8aed85d`, the same pin T1 used):
- `libraries/AP_Compass/AP_Compass_RM3100.cpp`: forces cycle count 200 (`CCP0 0xC8`), `_scaler = 1/75 µT/LSB → mG`,
  `TMRC 0x94`, and a timer at **80 Hz** (`register_periodic_callback(1000000U/80U)`) that reads only when DRDY is set.
  So the delivered modes require `--cycle-count 200`.
- `libraries/AP_Compass/AP_Compass_Backend.cpp`: `accumulate_sample()` sums the readings and `drain_accumulated_samples()`
  publishes their **mean**, so each delivered value averages the RM3100 readings since the last read (3 or 4 at 80→25 Hz).
- `Tools/AP_Periph/compass.cpp`: `AP_PERIPH_MAG_MAX_RATE 25U`. It returns if less than 40 ms has passed, sends only
  new data from a healthy compass, and sends `uavcan.equipment.ahrs.MagneticFieldStrength` with
  `magnetic_field_ga = get_field() * 0.001` (mG → Gauss) as **float16** (the HiRes message only with `AP_PERIPH_MAG_HIRES`).
- DSDL `uavcan/equipment/ahrs/1001.MagneticFieldStrength.uavcan` (dronecan/DSDL `b4653c7`): `float16[3] magnetic_field_ga`,
  "in Gauss … SI units are avoided because of float16 range limitations". The message is marked deprecated in favour of 1002.
- float16 conversion: libcanard `canardConvertNativeFloatToFloat16`, at the exact submodule pin of that ArduPilot commit
  (DroneCAN/libcanard `601ed35`). `sim/delivery.py` ports it bit for bit. A test shows it equals IEEE round-to-nearest except at
  exact ties, which it rounds away from zero. Step size: 2⁻¹² G = **0.0244 µT** for components of 25–50 µT,
  0.0122 µT for 12.5–25 µT, and 0.0488 µT for 50–100 µT.
- `Tools/AP_Periph/msp.cpp` + `libraries/AP_MSP/msp_sensors.h`: `MSP2_SENSOR_COMPASS`, `int16 magX/Y/Z` in **mGauss**
  (0.1 µT), assigned straight from the float field, so it **truncates toward zero** (bias up to −0.1 µT per axis toward zero).
  It is sent only when `compass.last_update_ms()` changes.

What I **inferred** rather than verified: MSP updates are also limited to 25 Hz, because in AP_Periph `compass.read()`
is called only from `can_mag_update()`. T1 lists the MSP rate as UNKNOWN; please confirm with a hardware log.

The model: RM3100 polls on an exact 80 Hz grid, publishes on an exact 25 Hz grid, and each publish is the float32 mean of
the polls in (previous, current], encoded as float16 Gauss or int16 mG and decoded back to µT for `mag_uT`. The JSONL `--rate` is
what the FC/app samples; each line carries the **latest** message (**sample-and-hold**). Above 25 Hz, values repeat
(stderr notes this); below it, messages are skipped. `mag_raw` and `rm3100_cycle_count` are left out (they're optional in the
schema, and ARCHITECTURE.md 2026-11-27 says `mag_raw` is absent on hardware), so no contract change was needed. Extra `meta` keys:
`output_mode`, `mag_seq` (message number), `mag_fresh` (new message since the previous line), `mag_age_s`,
`mag_n_avg`, `mag_sample_mid_s` (mean time of the averaged polls, for latency analysis), `mag_quant_uT`
(0.1 for MSP; the float16 step of the largest component for DroneCAN; key per PM decision 2026-11-27), and `msp_mag_mG` or
`dronecan_float16_bits` (the exact wire values). In these modes `truth.field_at_sensor_uT` is the field at the line's time
without environmental noise or GM bias.

## Model and assumptions
Frames: NED, body x forward, y right, z down; ZYX Euler (yaw, pitch, roll), yaw from true north.

1. **Earth field**: uniform and constant, `B_ned = F·[cos I cos D, cos I sin D, sin I]`. Defaults F = 50 µT,
   I = 60°, D = 0° are generic placeholders, not our site.
2. **Field at the sensor**: `B = W·M·(Rᵀ B_ned) + h + k·I(t) + b_GM(t) + n_env`, where W is the soft-iron matrix,
   M an optional axis misalignment rotation (default I), h the hard-iron offset, k the motor coefficient (µT/A), I(t) the
   motor current, b_GM an optional first-order Gauss-Markov bias and n_env white noise. This matches T2's spec
   (`docs/math/sensor-spec/SPEC.md` §5.1) except that the spec routes interference through S·M. For a body-fixed source
   that is the same as using k_sim = S·M·k_spec, so it doesn't change any heading result. Temperature terms aren't modelled.
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
10. **Accel convention** is now fixed in ARCHITECTURE.md (specific force, level (0, 0, −1) g) and the sim follows it.
    The Firmware Specialist still has to confirm the Matek FC's native sign; any conversion belongs in the bridge, not here.
11. `calibration_dance` needs at least 30 s for good sphere coverage; the 10 s example is only a format sample.
12. **The delivered modes come from reading source code, not from hardware.** They use exact 80 Hz and 25 Hz grids with no loop
    jitter. The AP_Periph-side calibration (COMPASS_OFS/DIA/ODI, default 0/identity), board rotation and AP_RM3100_REVERSAL_MASK
    are assumed to be identity. The FC-side processing after reception (ArduPilot `AP_Compass_DroneCAN` or INAV `compass_msp`,
    including their own averaging, rotation and calibration) isn't modelled. The MSP ≤ 25 Hz rate is INFERRED. The firmware on our
    unit (MatekL431-GPS vs -Periph) and its MSP availability are UNKNOWN (T1 L8). C overflow of int16 mG beyond ±3276.7 µT
    is undefined behaviour; the sim clips and flags it.
13. **Spec check (`sim/spec_check.py`)**: 35 applicable keys PASS. 44 keys are N/A (formulas, circular statistics, dipole/wire
    sources, WMM, navigation and geodesy, which the sim doesn't model). One MISMATCH is logged: TC19 quantisation σ, where
    the spec's LSB of 0.013 µT differs from the sim's 1/75 µT. The spec's temperature terms (k_T, k_off) and random-walk bias
    are not modelled; misalignment and Gauss-Markov bias are, but are off by default.

## Tests
`python -m pytest sim/tests -q` covers schema validation (every scenario, CLI output and example logs), determinism
(same seed gives identical bytes, `--out` matches stdout), the gain table and scaling, counts↔µT consistency, noise vs
model, saturation and 24-bit clipping, field magnitude and dip, truth heading against an independent tilt-compensation
formula (three declinations), measured heading from accel+mag, gyro/accel consistency, calibration-dance sphere
coverage, and hard-iron, soft-iron, motor-interference and high-noise behaviour. `test_delivery.py` covers the
DroneCAN and MSP modes: the bit-exact float16 port, step sizes, truncation, the ≤ 25 Hz limit, sample-and-hold,
80→25 Hz averaging, latency, schema, `mag_quant_uT`, and no false stale warnings in `heading_core`.
`test_spec_cases.py` runs all 20 of T2's spec cases through the sim (see LIMITATIONS 13), plus misalignment and
Gauss-Markov checks.
