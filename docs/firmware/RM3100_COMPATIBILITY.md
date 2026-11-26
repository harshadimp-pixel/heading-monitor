# RM3100 ↔ Matek / AP_Periph Firmware Compatibility Report

Scope: desk research from public docs and source code, plus a synthetic-data simulation. No firmware was flashed or modified and no aircraft or hardware was connected.

Source snapshots (shallow clones, read only):

| Repo | Commit | Commit time (IST, UTC+5:30) |
|---|---|---|
| ArduPilot/ardupilot (master) | 6034266 | 2026-11-26 20:23 |
| iNavFlight/inav (master, version 10.0.0) | fce6c94 | 2026-11-26 08:17 |
| betaflight/betaflight (master) | f511ed9 | 2026-11-26 22:54 |
| PX4/PX4-Autopilot (main) | f364b94 | 2026-11-26 21:08 |
| dronecan/DSDL | b4653c7 | 2026-02-05 07:56 |

Line numbers below refer to these commits.

## 1. Key findings

1. **Use the RM3100 through ArduPilot AP_Periph (CAN), or through the AP_Periph MSP output.** Every Matek RM3100 product is an AP_Periph CAN node (CAN-L4-3100, M10-L4-3100 (EOL), M9N-G4-3100 (EOL), plus the MatekF405-CAN FC target). All of their hwdefs declare the RM3100 on **SPI, 1 MHz, `ROTATION_PITCH_180`**.
2. **AP_Periph does not compute heading from the magnetometer.** It sends only the calibrated field vector (`uavcan.equipment.ahrs.MagneticFieldStrength`, float16 Gauss) at up to 25 Hz by default. The flight controller computes heading in its AHRS/EKF. The only heading an AP_Periph node sends is GNSS moving-baseline yaw (`ardupilot.gnss.Heading` / RelPosHeading).
3. **The default path loses very little precision.** Synthetic simulation: float16 adds ≤0.034° worst-case heading error at |H| = 20 µT, against a 0.025° floor from the raw RM3100 LSB. The int16 mGauss telemetry and log hop (MAVLink xmag, DataFlash MAG) is coarser, at ≤0.29° worst case for |H| = 20 µT and ≤1.15° for |H| = 5 µT.
4. **INAV's native RM3100 driver throws away the low 8 bits.** It keeps `count24 >> 8`, about 34 mG per LSB. In simulation that gives up to 13.5° heading error at |H| = 20 µT, before calibration. This is a known open INAV issue (#10746, consolidated in #10812). INAV also registers the RM3100 on SPI only (issue #9390). For INAV, the better route is the Matek node's **MSP output** (`MSP2_SENSOR_COMPASS`, int16 mGauss).
5. **Betaflight has no RM3100 bus driver.** Current master does include a DroneCAN magnetometer subscriber (`MAG_DRONECAN`, MagneticFieldStrength and MagneticFieldStrength2) behind `ENABLE_DRONECAN`. I could not confirm which release, or which Matek target, ships it.
6. **The `MatekL431-MagHiRes` build is for surveying only.** It sends only `dronecan.sensors.magnetometer.MagneticFieldStrengthHiRes` (float32). The ArduPilot FC only *logs* that message (MAGH), and only when built with `AP_COMPASS_DRONECAN_HIRES_ENABLED` (default 0). It never feeds the EKF. In the MAGH logging call, the `Sensor` and `Bus` arguments are passed in the wrong order (source observation).

## 2. Matek products and hwdefs

All paths are under `libraries/AP_HAL_ChibiOS/hwdef/`.

| Board / product | Firmware type | RM3100 declaration | Mag defines |
|---|---|---|---|
| CAN-L4-3100 / M10-L4-3100 → `MatekL431-GPS/hwdef.dat` | AP_Periph | L20-21 `SPIDEV rm3100 SPI1 DEVID1 MAG_CS MODE0 1*MHZ 1*MHZ`; `COMPASS RM3100 SPI:rm3100 false ROTATION_PITCH_180`; L24 also probes QMC5883L on I2C 0x0D | L15 `AP_PERIPH_MAG_ENABLED 1`, L16 `AP_COMPASS_PROBING_ENABLED 1`, L18 `HAL_COMPASS_MAX_SENSORS 1`, MSP enabled (L51) |
| same boards → `MatekL431-Periph/hwdef.dat` | AP_Periph | L34-35 (SPI1, PITCH_180), L40 QMC5883L | L32 `AP_PERIPH_MAG_ENABLED 1`, MSP L57-59 |
| `MatekL431-MagHiRes/hwdef.dat` | AP_Periph (survey) | L6-7 (SPI1, PITCH_180) | L4 `AP_PERIPH_MAG_ENABLED 1`, L12 `AP_PERIPH_MAG_HIRES 1`, L13 `AP_PERIPH_MAG_MAX_RATE 0` |
| `MatekL431/hwdef.inc` (common) | AP_Periph | L51-55: SPI1 PA5/PB4/PA7, `PA4 MAG_CS` | `env AP_PERIPH 1` (L24) |
| M9N-G4-3100 → `MatekG474-GPS/hwdef.dat` | AP_Periph | L23-24 `SPIDEV rm3100 SPI2 …`, PITCH_180 | L21, L26, L28 probing, MSP L32-34 |
| `MatekG474-Periph/hwdef.dat` | AP_Periph | L17-18 (SPI2) | L15, L20, L22 |
| `MatekG474/hwdef.inc` | AP_Periph | L51-55 `PB12 MAG_CS` | |
| `f405-MatekGPS/hwdef.dat` (legacy F405 CAN GPS) | AP_Periph | L146-147 (SPI2), L152 QMC5883L fallback | L144, L149 |
| `MatekF405-CAN/hwdef.dat` | **FC** (ArduPilot) | L124-125 `SPIDEV rm3100 SPI2 …`, PITCH_180 | L128 `AP_COMPASS_PROBING_ENABLED 1` |
| `MatekH743-periph/hwdef.dat` | AP_Periph built on the H743 FC | no RM3100 line; uses probing | L20 `AP_PERIPH_MAG_ENABLED 1`, L32 max 1 |
| `f303-MatekGPS/hwdef.dat` (M8Q-CAN) | AP_Periph | **QMC5883L only** (L114), no RM3100 | |
| MatekH743, MatekF405, -Wing, -TE, MatekF765-Wing | FC | no onboard mag | `AP_COMPASS_PROBING_ENABLED 1`, `HAL_COMPASS_AUTO_ROT_DEFAULT 2` (e.g. MatekH743 L197-199) |
| MatekF765-SE, MatekH7A3, MatekH7A3-Wing | FC | no compass lines in hwdef.dat | defaults only |

Driver enable: `AP_COMPASS_RM3100_ENABLED` defaults to `AP_COMPASS_I2C_BACKEND_DEFAULT_ENABLED` (`libraries/AP_Compass/AP_Compass_config.h` L150-151). On FCs with probing enabled, an external I2C RM3100 is probed at 0x20-0x23 (`AP_Compass.cpp` L1275-1301, addresses in `AP_Compass_RM3100.h` L29-33).

Matek product pages: <https://www.mateksys.com/?portfolio=can-l4-3100>, <https://www.mateksys.com/?portfolio=m10-l4-3100> (EOL Dec 2024), <https://www.mateksys.com/?portfolio=m9n-g4-3100> (EOL). They recommend `COMPASS_TYPEMASK`. On current master that bitmask is named `COMPASS_DISBLMSK` (`AP_Compass.cpp` L532-537); RM3100 is bit 16 and DroneCAN is bit 11.

INAV targets with an RM3100: `MATEKF405CAN` (SPI2, CS PB12) and `MATEKH743` (external RM3100 on the spare SPI3 pads, CS PE2 "CS2"), in `src/main/target/*/target.h`.

## 3. RM3100 driver details

ArduPilot driver: `libraries/AP_Compass/AP_Compass_RM3100.cpp`.

| Item | ArduPilot | INAV | PX4 |
|---|---|---|---|
| Bus | SPI (read flag 0x80) or I2C 0x20-0x23 | SPI only (`common_hardware.c` L290-294) | I2C (default 0x20) or SPI |
| Detection | Reads CCX/CCY/CCZ and expects the default 0x00C8 (L103-122) | REVID 0x22 | REVID / BIST |
| Cycle count | 200 (CCP0 0xC8) | 200 | 200 (0xC8) |
| TMRC | 0x94 ("150 Hz" comment) | 0x94 | 0x95 (~75 Hz) |
| CMM | 0x71 | 0x71 | – |
| Poll rate | 80 Hz timer (L157) | sensor task | 13 ms (~75 Hz) |
| Scaling | `(1/75) × UTESLA_TO_MGAUSS` = 0.1333 mG/LSB, full 24 bits (L135, L196-205) | **int16 of the top 16 bits** (L131-139) | 1/(75 × 0.01) |
| Axis polarity fix | `AP_RM3100_REVERSAL_MASK` hwdef option (L207-220) | – | – |
| Rotation | hwdef `ROTATION_PITCH_180` on all Matek nodes, plus FC `COMPASS_ORIENTx` | `align_mag` (Matek says CW90 for MSP) | `-R` |
| Filtering | Samples averaged between reads (`accumulate_sample`/`drain_accumulated_samples`); optional `COMPASS_FLTR_RNG` gate (default 0, off) | INAV compass LPF/calibration | uORB |

PNI datasheet values at CC=200 (RM3100 User Manual Table 3-1, <https://www.pnisensor.com/wp-content/uploads/RM3100-RM2100-Sensor-Suite-User-Manual-V11.0.pdf>):
- gain: 75 LSB/µT
- sensitivity: 13 nT
- noise: 15 nT
- maximum single-axis rate: 440 Hz, divided by 3 for 3-axis

The manual gives the range as ±800 µT. The sales sheet gives ±1100 µT and a 147 Hz maximum 3-axis rate (<https://www.pnisensor.com/wp-content/uploads/PNI-Sensor-RM3100-Sales-Sheet.pdf>). The two documents disagree on range.

Known history: ArduPilot PR #13895 (2020) changed the scale factor and was later reverted. `DEVTYPE_RM3100_2` (0x12) remains as a "past mistake" ID (`AP_Compass_Backend.h` L73-74). See <https://github.com/ArduPilot/ardupilot/pull/13895>. INAV issues: <https://github.com/iNavFlight/inav/issues/10746>, <https://github.com/iNavFlight/inav/issues/10812>, <https://github.com/iNavFlight/inav/issues/9390>.

## 4. Data formats end to end

| Stage | Field(s) | Unit | Type | Resolution / note | Source |
|---|---|---|---|---|---|
| RM3100 MX/MY/MZ regs 0x24-0x2C | 3 × 24-bit | count | int24 two's complement | 1/75 µT = 0.1333 mG (CC200) | PNI manual; driver L196-205 |
| AP_Compass backend | field | mGauss | float32 | after rotation, offsets, diag/offdiag, scale and motor comp | `AP_Compass_Backend.cpp` |
| DroneCAN 1001 `uavcan.equipment.ahrs.MagneticFieldStrength` (what AP_Periph sends) | `magnetic_field_ga[3]`, `magnetic_field_covariance[<=9]` | Gauss | float16 | 10-bit mantissa: 0.122 mG step at 0.125-0.25 G, 0.244 mG at 0.25-0.5 G | DSDL; `Tools/AP_Periph/compass.cpp` L63-80 |
| DroneCAN 1002 `MagneticFieldStrength2` | `sensor_id` uint8 + same | Gauss | float16 | Accepted by the FC (`AP_Compass_DroneCAN.cpp` L173-186). AP_Periph does **not** send it | DSDL |
| DroneCAN 1043 `dronecan.sensors.magnetometer.MagneticFieldStrengthHiRes` | `sensor_id`, `magnetic_field_ga[3]` | Gauss | float32 | MagHiRes build only; FC logs it as MAGH | DSDL; compass.cpp L82-96 |
| FC DroneCAN backend | ×1000 → mGauss | mGauss | float | rate limit 25 Hz (`AP_PERIPH_MAG_MAX_RATE`) | `AP_Compass_DroneCAN.cpp` L152-157 |
| MSP2_SENSOR_COMPASS (0x1F04), node→FC | instance u8, time_ms u32, magX/Y/Z | mGauss (front/right/down) | int16 | 1 mG | `AP_MSP/msp_sensors.h` L52-58; INAV `msp_protocol_v2_sensor_msg.h` L81-84 |
| MAVLink RAW_IMU / SCALED_IMU(2,3) xmag/ymag/zmag | compass 0 (or n) field | mGauss as sent by ArduPilot | int16 | 1 mG (implicit float→int16 truncation) | `GCS_Common.cpp` L2270-2300, L2365-2410 |
| MAVLink HIGHRES_IMU xmag | field × 0.001 | Gauss | float | – | `GCS_Common.cpp` L2340-2347 |
| MAVLink MAG_CAL_REPORT | compass_id, cal_mask, status, autosaved, fitness, ofs_xyz, diag_xyz, offdiag_xyz, orientation_confidence, old/new orientation, scale_factor | fitness in mGauss RMS; offsets in mGauss | float / uint8 | – | `AP_Compass_Calibration.cpp` L343-359 |
| DataFlash MAG | TimeUS, I, MagX/Y/Z, OfsX/Y/Z, MOX/Y/Z, Health, S | mGauss (unit G, mult 1e-3) | int16 (cast) | 1 mG | `AP_Compass/LogStructure.h` L8-45; `AP_Compass_Logging.cpp` L19-25 |
| DataFlash MAGH | TimeUS, Node, Sensor, Bus, Mx/My/Mz | mGauss | float | Sensor/Bus arguments swapped in the call | `AP_Compass_DroneCAN.cpp` L195-215 |
| INAV MSP_RAW_IMU (102) mag | magADC | INAV internal units (offset-removed, scaled to magGain 1024) | int16 | not mGauss | INAV `fc_msp.c` L606-620; `sensors/compass.c` L560 |
| Betaflight MSP_RAW_IMU mag | magADC | driver/raw units after alignment and zero | int16 | – | BF `msp.c` L1250-1266 |

## 5. Heading telemetry

- **AP_Periph:** no magnetometer heading. `compass.cpp` only publishes the field vector. `gps.cpp` L223-233 publishes `ardupilot.gnss.Heading` only for GPS yaw (moving baseline). `msp.cpp` L104-109 puts GPS `true_yaw` into MSP GPS (65535 means unknown).
- **ArduPilot FC heading:**
  - ATTITUDE `yaw` (rad, `ahrs.get_yaw_rad()`, `GCS_Common.cpp` ~L6148)
  - VFR_HUD `heading` (int16 deg, `ahrs.get_yaw_deg()`, L3534)
  - GLOBAL_POSITION_INT `hdg` (cdeg, `ahrs.yaw_sensor`, ~L6216)

  The yaw source is chosen with `EK3_SRC1_YAW`: 0 None, 1 Compass, 2 GPS, 3 GPS with Compass Fallback, 6 ExternalNav, 8 GSF (`AP_NavEKF_Source.cpp` L58). Declination comes from `COMPASS_DEC` / `COMPASS_AUTODEC`.
- **INAV / Betaflight:** MSP_ATTITUDE (108) yaw in degrees (INAV); MSP_RAW_IMU carries the mag vector.
- **PX4:** `vehicle_attitude` / MAVLink ATTITUDE (not studied in depth).

## 6. Monitoring capabilities (ArduPilot)

- **Health:** a compass is healthy if it updated within 500 ms (`AP_Compass.cpp` L1874). It maps to the SYS_STATUS `MAV_SYS_STATUS_SENSOR_3D_MAG` present/enabled/health bits (`GCS.cpp` L495-503). The AP_Periph node simply stops sending when its compass is unhealthy (compass.cpp L58-60), so on the FC a node failure shows up as this timeout.
- **Pre-arm checks** (`AP_Arming.cpp`):
  - field length must be 185-875 mG (L75-77, L665)
  - offsets ≤ `COMPASS_OFFS_MAX`
  - "Compasses inconsistent" when the XYZ angle differs by >90°, the XY angle by >60°, or the XY length by >200 mG (`AP_Compass.h` L36-38)
  - field must match the World Magnetic Model within `ARMING_MAGTHRESH` (default 100 mG)
- **Parameters:**
  - `COMPASS_USE/USE2/USE3`, `COMPASS_PRIOn_ID`, `COMPASS_DEV_IDn`, `COMPASS_ORIENTn`, `COMPASS_EXTERNn`
  - `COMPASS_OFS*`, `DIA*`, `ODI*`, `SCALE*`, `COMPASS_MOTCT` / `MOT*` (motor interference), `COMPASS_LEARN`
  - `COMPASS_FLTR_RNG`, `COMPASS_DISBLMSK`, `COMPASS_AUTO_ROT`, `COMPASS_CAL_FIT`, `COMPASS_ENABLE`, `COMPASS_OPTIONS`
  - AP_Periph exposes the same `COMPASS_*` group on the node (`Tools/AP_Periph/Parameters.cpp` L268-271)
  - FC CAN setup: `CAN_P1_DRIVER`, `CAN_D1_PROTOCOL = 1` (DroneCAN)
  - I did not find a `MAG_BAUDRATE`-style parameter in AP_Periph
- **Calibration:** onboard calibration reports progress and results with MAG_CAL_PROGRESS / MAG_CAL_REPORT.
- **EKF innovations:**
  - XKF3 `IMX/IMY/IMZ` (mag innovations)
  - XKF4 `SM` (squared mag test ratio, <1 means accepted), `TS` bit 3 (mag timeout), `FS`, `SS`
  - `EK3_MAG_I_GATE`
- **Tools:** the ArduPilot WebTools MAGFit log tool (<https://firmware.ardupilot.org/Tools/WebTools/MAGFit/>) and MAVProxy magfit (not run here).
- **DroneCAN:** the node sends `uavcan.protocol.NodeStatus` (health/mode); the DroneCAN GUI Tool or the Mission Planner DroneCAN tab can read node parameters.

## 7. Firmware support comparison

| Firmware | RM3100 native bus driver | RM3100 via Matek CAN node | via Matek node MSP | Notes |
|---|---|---|---|---|
| ArduPilot FC | Yes: SPI (hwdef) and I2C 0x20-0x23 probing; full 24-bit | Yes: DroneCAN 1001/1002 (float16), MAGH log for 1043 if built with HIRES | Yes: `SERIALx_PROTOCOL=32`, MSP compass (Matek docs) | Most complete monitoring |
| AP_Periph on Matek nodes | Yes: SPI, PITCH_180, 25 Hz cap | It *is* the node | MSP output in -Periph / later -GPS builds | No heading computation |
| INAV (10.0.0 master) | SPI only; truncated to 16 bits (open issue) | No (DroneCAN in INAV covers GPS/battery, not mag; no MagneticField handlers found) | Yes: `mag_hardware = MSP`, int16 mGauss (Matek: since INAV 2.6) | Prefer MSP |
| Betaflight (master) | No | Master has `MAG_DRONECAN` (1001/1002 → int16 mGauss) when built with `USE_DRONECAN`; release status unverified | No MSP compass input found | – |
| PX4 (main) | Yes: I2C/SPI, 75 LSB/µT, ~75 Hz | Via its own UAVCAN sensor bridge (not studied) | – | brief |

## 8. Simulation (synthetic data)

Files:
- Script: `docs/firmware/research/rm3100_quantization_sim.py`
- Output: `docs/firmware/research/rm3100_quantization_results.json`
- Tests: `test_rm3100_quantization_sim.py` (4 pass)

The script sweeps heading 0-360° in 0.05° steps for a level sensor. For each data path it reports the heading error that the number format alone adds. It does not model calibration, tilt or declination. The field values are illustrative, not taken from a location model.

| Path | H=20 µT, Z=40 µT: max / RMS (°) | H=5 µT, Z=55 µT: max / RMS (°) |
|---|---|---|
| A raw 24-bit counts | 0.025 / 0.011 | 0.105 / 0.044 |
| B ArduPilot float mGauss | 0.025 / 0.011 | 0.105 / 0.044 |
| C DroneCAN float16 Gauss | 0.033 / 0.012 | 0.115 / 0.045 |
| D DroneCAN HiRes float32 | 0.025 / 0.011 | 0.105 / 0.044 |
| E int16 mGauss (MAVLink/MAG log after C) | 0.291 / 0.120 | 1.146 / 0.469 |
| F INAV native int16 (count >> 8) | 13.5 / 5.83 | 44.9 / 22.6 |

With datasheet noise added (σ = 15 nT, seed 1), paths A-D give 0.162 / 0.044 (20 µT) and 0.689 / 0.177 (5 µT). Path E gives 0.408 / 0.127 and 1.577 / 0.494. Path F is unchanged.

Representation step sizes:

| Representation | Step |
|---|---|
| RM3100 raw LSB | 0.133 mG |
| float16 at 150 mG | 0.122 mG |
| float16 at 250-450 mG | 0.244 mG |
| float16 at 600 mG | 0.488 mG |
| int16 mGauss | 1 mG |
| INAV native | 34.13 mG |

## 9. Recommendations for the heading-monitor app

1. **Preferred virtual input:** ArduPilot-style MAVLink (`RAW_IMU`/`SCALED_IMU` xmag in mGauss, plus ATTITUDE yaw) or DataFlash MAG logs. If the app needs better than about 1 mG resolution, use HIGHRES_IMU (float Gauss).
2. **INAV:** document `mag_hardware = MSP` with the Matek node, not the native RM3100 driver. Treat INAV MSP_RAW_IMU mag as **unitless** (calibrated magADC), not mGauss.
3. **Monitoring:** reproduce the ArduPilot checks in software:
   - 500 ms staleness
   - 185-875 mG field-length band
   - inter-compass angle limits (90°/60°/200 mG)
   - EKF SM ratio > 1
4. **Rotation:** apply node rotation (PITCH_180 is already applied on the node) and FC `COMPASS_ORIENT` exactly once. Do not apply them twice.
5. **MagHiRes:** do not use the MagHiRes build on a flying vehicle unless a standard mag is also present.

## LIMITATIONS

- Nothing was validated on hardware. All conclusions come from source reading at the commits listed above, plus synthetic simulation.
- I could not retrieve the PNI manual's TMRC rate table (Table 5-4); the PDF download returned non-PDF content. The 0x94 ≈ 150 Hz figure comes from the ArduPilot code comment only. The effective rate with CC200 is bounded by the cycle count (sales sheet: 147 Hz for 3 axes).
- The PNI documents conflict on field range (manual ±800 µT vs sales sheet ±1100 µT) and on the 3-axis maximum rate (manual note says ~430 Hz; table ÷3 and sales sheet give ~147 Hz).
- I did not check which Betaflight release (if any) ships `MAG_DRONECAN`, or whether any Matek BF target defines `USE_DRONECAN`. The shallow clone has no tag history.
- I did not search INAV DroneCAN code exhaustively for magnetometer support (no MagneticField handlers found by grep).
- I did not verify the magnetometer on the Matek M10Q-5883 / M9N-5883 (non-CAN, I2C) modules. They are not RM3100 products and are out of scope.
- I did not check the MAVLink common.xml unit annotations for RAW_IMU vs SCALED_IMU xmag; ArduPilot sends mGauss in both.
- I did not trace the PX4 UAVCAN magnetometer bridge or the PX4 Matek targets.
- I did not run SITL. MAGFit and log-based monitoring were reviewed from documentation and source only; no sample DataFlash log was parsed.
- The MAGH Sensor/Bus argument swap is a source-reading observation. It has not been reported upstream or confirmed in a log.
- The simulation leaves out calibration, tilt compensation, declination, timing/latency, CAN bus load and float16 subnormals. INAV's magGain normalization is not modelled; it rescales the values but cannot recover the dropped bits.
