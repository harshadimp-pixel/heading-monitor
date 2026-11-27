# FC setup: Matek CAN-L4-3100 (RM3100) → Matek FC → heading monitor (T4)

Owner: Firmware Specialist. Status: REVIEW. **Nothing here is `[HARDWARE-VERIFIED]`.** No FC was connected,
flashed or configured while writing this. Every step comes from firmware source or vendor docs (pinned below).
Each step is either verified in source (`[SOURCE-CODE]`), taken from vendor docs (`[OFFICIAL-DOC]`), or marked
**UNCERTAIN**.

Related: compatibility report [`RM3100_COMPATIBILITY.md`](RM3100_COMPATIBILITY.md) (quantisation simulation in
[`research/`](research/)), hardware facts in [`../hardware/FACTSHEET.md`](../hardware/FACTSHEET.md), bridge usage in
[`../../firmware_bridge/README.md`](../../firmware_bridge/README.md).

## 0. Source pins

| Repo | Ref | Commit |
|---|---|---|
| iNavFlight/inav | `maintenance-10.x` (10.0 RC line; 10.0.0-rc2 published 2026-09-29) | `fce6c94` |
| iNavFlight/inav | `master` | `940b928` (has **no** DroneCAN code at all) |
| ArduPilot/ardupilot | `master` | `6034266` |
| betaflight/betaflight | `master` | (file listing only, 2026-11-26) |

Line numbers below are for `maintenance-10.x` (INAV) and `master` (ArduPilot) unless stated otherwise.
Note: `RM3100_COMPATIBILITY.md` labels `fce6c94` as "INAV master". On GitHub, `fce6c94` is the head of
`maintenance-10.x`, and `master` is `940b928`. The RM3100 and MSP code I compared is the same on both.

## 1. What we have and which path to use

Our module is the **Matek CAN-L4-3100**: an RM3100 on SPI behind an STM32L431 running ArduPilot **AP_Periph**
([Matek page](https://www.mateksys.com/?portfolio=can-l4-3100), [FACTSHEET](../hardware/FACTSHEET.md)).
The FC never sees RM3100 registers or raw counts. It gets a field vector from AP_Periph in one of two ways:

* **DroneCAN** `uavcan.equipment.ahrs.MagneticFieldStrength` (Gauss). Only ArduPilot (and PX4) consume it.
* **MSP over UART2**: `MSP2_SENSOR_COMPASS` (0x1F04), `int16` **mGauss** front/right/down, pushed as MSPv2
  frames (`Tools/AP_Periph/msp.cpp` L158-177, `send_msp_packet` L37 `MSP_V2_NATIVE`; struct
  `libraries/AP_MSP/msp_sensors.h` and INAV `msp/msp_protocol_v2_sensor_msg.h` L78-84). Both Matek AP_Periph
  builds enable MSP on serial1 = USART2 (`hwdef/MatekL431-GPS/hwdef.dat` L50-53,
  `MatekL431-Periph/hwdef.dat` L56-59, `MatekL431/hwdef.inc` L78-80 `SERIAL_ORDER USART1 USART2 USART3`).

| FC firmware | FC board | RM3100 path | Telemetry the bridge reads | Bridge support |
|---|---|---|---|---|
| **INAV** (primary) | MATEKH743 (has CAN) **or** any Matek F405 | **MSP**: node TX2 → FC UART RX, `mag_hardware = MSP` | MSP over USB: `MSP_RAW_IMU` + `MSP_ATTITUDE` | **Yes** (`--profile inav-msp-mag`, default) |
| INAV | any | INAV DroneCAN | — | **Not possible**: INAV 10 DroneCAN handles GNSS, battery, NodeInfo only (`drivers/dronecan/dronecan.c` L434-596, no MagneticFieldStrength handler; `docs/DroneCAN.md` "Supported Features" table) |
| INAV | MATEKH743 / MATEKF405CAN | bare RM3100 on SPI (not our module) | MSP | Supported with a caveat: 3.41 µT/LSB, see §6 (`--profile inav-rm3100-spi`) |
| **ArduPilot** (alternative) | MatekH743 (CAN1) | **DroneCAN** | MAVLink over USB | **Not implemented** (bridge is MSP-only, see LIMITATIONS) |
| ArduPilot | Matek F405 without CAN | MSP sensor on a UART (`SERIALx_PROTOCOL = 32`) | MAVLink over USB | Not implemented (MAVLink) |
| Betaflight | any | — | — | Not supported: no RM3100 driver in `src/main/drivers/compass/` (master). The research report found a DroneCAN mag subscriber behind `ENABLE_DRONECAN`; I did not verify which release ships it |

The PM/T1 context ("INAV 10 has no CAN compass → INAV via MSP, `mag_hardware=MSP`, `align_mag=CW90`; ArduPilot via
DroneCAN `CAN_P1_DRIVER=1`, `CAN_D1_PROTOCOL=1`") **matches the source**. Notes: (a) `align_mag=CW90` is Matek's
recommendation for an arrow-forward mount. INAV 10's default (`DEFAULT`) maps to `CW270_DEG_FLIP`
(`sensors/compass.c` L349-353), so set it explicitly. (b) Matek's page uses `COMPASS_TYPEMASK`, but current
ArduPilot names the parameter **`COMPASS_DISBLMSK`** (`AP_Compass.cpp` L532-537). It is the same index (33) and
was already renamed in Copter-4.5. Bit 11 = DroneCAN, 16 = RM3100, 17 = MSP.

## 2. Path A — INAV (primary), MSP compass. Works on MATEKH743 and Matek F405 boards

Hardware (from the [Matek page](https://www.mateksys.com/?portfolio=can-l4-3100), `[OFFICIAL-DOC]`):
CAN-L4-3100 `5V` → FC 4.0–5.3 V, `G` → GND, `TX2` → a **spare FC UART RX**. Mount ≥10 cm from power wiring, ESCs and motors.

1. **Firmware target.** Flash INAV (9.x stable, or 10.x RC; see LIMITATIONS) for the exact board:
   `MATEKH743`, `MATEKF405` / `MATEKF405SE` / `MATEKF405TE` / `MATEKF405CAN` … (targets in `src/main/target/MATEK*`).
   All Matek targets define `USE_MAG` and `USE_MAG_ALL` (INAV `master`: e.g. `MATEKH743/target.h` L116-118,
   `MATEKF405/target.h` L153-155). The MSP mag driver needs no target-specific bus.
   *Flashing is the owner's job. The team does not touch live firmware.*
2. **Node firmware.** The node ships with `MatekL431-GPS` firmware (Matek page). Its hwdef and `MatekL431-Periph`
   both enable MSP on USART2 at `AP_PERIPH_MSP_PORT_DEFAULT 1`. **UNCERTAIN:** the node's serial1 baud
   default. Matek says use 115200 on the FC side.
3. **Ports tab / CLI.** Enable **MSP only** on the UART wired to TX2, at 115200 (Matek page). CLI form:
   `serial <uart_index> 1 115200 115200 0 115200`. Function mask bit 0 = MSP. **UNCERTAIN:** check the index and
   field order with `serial` on the board before saving.
4. **Select the MSP compass and alignment** (`fc/settings.yaml`: `mag_hardware` table includes `MSP`; `align_mag`):
   ```
   set mag_hardware = MSP
   set align_mag = CW90          # Matek: module flat, arrow forward, FC arrow forward
   save
   ```
   Why CW90: INAV rotates the FRD `MSP2_SENSOR_COMPASS` vector by `CW90_DEG_FLIP` (`drivers/compass/compass_msp.c`
   L73). Then `align_mag` CW90 (`sensors/boardalignment.c` L126-150) gives forward-left-up, which is INAV's body
   frame (§6.3). For other mountings use `align_mag_roll/pitch/yaw` (decidegrees; non-zero overrides `align_mag`,
   `settings.yaml`). INAV 10 also has an auto-orientation step after calibration (`compass.c` L540-552).
5. **Check it is detected.** In the CLI run `status`. The mag should be listed. In the Configurator Sensors tab the mag
   should update at ≥4 Hz; INAV drops the MSP mag after 250 ms without data (`compass_msp.c` L46, L82).
6. **Keep the FC mag calibration neutral (single-calibration rule, ARCHITECTURE.md 2026-11-27).** The app's
   ellipsoid fit (`heading_core`) must be the only calibration. INAV mag calibration (Configurator "Calibrate
   Magnetometer", stick command or `MSP_MAG_CALIBRATION`; 30 s default `mag_calibration_time`) rewrites
   `magzero_*` and `maggain_*`. After that, `MSP_RAW_IMU` mag is `(raw − zero)·1024/gain`, which is
   dimensionless and normalised to about 1024 per axis peak (`compass.c` L560). So:
   ```
   set magzero_x = 0
   set magzero_y = 0
   set magzero_z = 0
   set maggain_x = 1024
   set maggain_y = 1024
   set maggain_z = 1024
   save
   ```
   These are the defaults (`fc/settings.yaml`: `magzero_*` default 0, `maggain_*` default 1024; INAV itself treats
   exactly this combination as "not calibrated", `compass.c` L389-390 at `master`). **Do not run the FC compass
   calibration** afterwards. Check with `get magzero` / `get maggain`. INAV will report the compass as
   uncalibrated (`COMPASS_CALIBRATED` state off), which is expected for this bench/monitoring setup; a craft that must
   *navigate* with INAV needs INAV's own calibration and is outside the single-calibration rule (BLOCKERS B3).
   The AP_Periph node also has calibration parameters (see Path B, step 2a); keep those neutral too, because
   `MSP2_SENSOR_COMPASS` carries the node's corrected field.
   **How the bridge reports it:** at start-up (after `MSP_FC_VARIANT` = `INAV`) and then every 10 s it sends the
   read-only `MSP_CALIBRATION_DATA` (14). INAV answers it from `mspFcProcessOutCommand` (`fc_msp.c` L1574-1603 at
   `fce6c94`; same layout at tag `9.1.0` and `master`): `u8 accCalibAxisFlags, accZero[3], accGain[3], magZero[3],
   u16 opflow_scale·256, magGain[3]` (27 bytes, int16 LE). `meta.fc_mag_calibrated` is then:
   `false` if magZero = (0,0,0) **and** magGain = (1024,1024,1024); `true` if they differ; `"unknown"` if there is no
   reply, an error frame, a short payload, a non-INAV FC (layout not verified for Betaflight; ArduPilot's AP_MSP does
   not implement message 14), or all-zero zero+gain (INAV build without `USE_MAG`). The read values are in
   `meta.fc_mag_cal`. The bridge never sends `MSP_SET_CALIBRATION_DATA` (15), `MSP_MAG_CALIBRATION` (206),
   `MSP_EEPROM_WRITE` (250) or `MSP2_COMMON_SET_SETTING` (0x1004); see `bridge.ALLOWED_REQUESTS`.
   It cannot see the AP_Periph node's own calibration, so `false` means "FC neutral" only.
7. **MSP over USB.** Nothing to do. INAV sets serial port config index 0 to `FUNCTION_MSP` by default
   (`io/serial.c` L123), and on Matek USB targets that is the USB VCP. Baud is ignored on VCP. Then run:
   `python -m firmware_bridge --port /dev/ttyACM0 --baud 115200` (Windows: `--port COM5`).

## 3. Path B — ArduPilot (alternative), DroneCAN compass on MatekH743

1. **Firmware target:** `MatekH743` (ArduPilot `libraries/AP_HAL_ChibiOS/hwdef/MatekH743/hwdef.dat`: CAN1 on
   PD0/PD1 L139-142; no onboard compass, `AP_COMPASS_PROBING_ENABLED` L195-199). Node: CAN-L4-3100 CAN port → FC CAN1.
2. **Params** (`AP_CANIfaceParams.cpp` L23-26, `AP_CANManager_CANDriver_Params.cpp` L27-31, Matek page):
   ```
   CAN_P1_DRIVER   = 1      # first driver on physical CAN1
   CAN_D1_PROTOCOL = 1      # DroneCAN
   COMPASS_ENABLE  = 1
   COMPASS_DISBLMSK: make sure bit 11 (DroneCAN) is NOT set   # Matek's "COMPASS_TYPEMASK"
   COMPASS_AUTODEC = 1      # Matek page
   ```
   Reboot. The node's own orientation is fixed in its hwdef (`ROTATION_PITCH_180`). Set the FC-side
   `COMPASS_ORIENT` (`AP_Compass.cpp` L182-187) for the mounting by hand (do not use the onboard calibration's
   auto-rotation, because that calibration would also write offsets; see 2a).
   **2a. Keep compass calibration neutral (single-calibration rule).** ArduPilot equivalents of INAV's
   magzero/maggain, with their defaults (`AP_Compass.cpp` at `6034266`): `COMPASS_OFS_X/Y/Z = 0` (L106),
   `COMPASS_DIA_X/Y/Z = 1` (L403), `COMPASS_ODI_X/Y/Z = 0` (L422), `COMPASS_SCALE = 0` ("If this is 0 then no
   scaling is done", L589-594), `COMPASS_MOTCT = 0` and `COMPASS_MOT_X/Y/Z = 0` (L150, L178), plus
   `COMPASS_LEARN = 0` (L119-124) so EKF/in-flight learning does not write offsets. Repeat for `COMPASS_OFS2_*`
   etc. if a second compass is enabled. Do not run the onboard or large-vehicle compass calibration.
   **The AP_Periph node** has the same `COMPASS_` parameter group (`Tools/AP_Periph/Parameters.cpp` L268-272), and
   its published field already includes those corrections. Set the same neutral values on the node (DroneCAN GUI
   Tool or Mission Planner's DroneCAN parameter page) and do not calibrate it. **UNCERTAIN:** ArduPilot's
   pre-arm check will report the compass as not calibrated; that is acceptable on the bench (no arming), not for
   flight. The bridge cannot read any of these yet (MAVLink not implemented), so it would report `"unknown"`.
3. **Telemetry over USB:** SERIAL0 (USB, `SERIAL_ORDER OTG1 …` L102) defaults to MAVLink2
   (`AP_SerialManager.cpp` L37-38 `DEFAULT_SERIAL0_PROTOCOL SerialProtocol_MAVLink2`). Mag is in MAVLink
   `RAW_IMU`/`SCALED_IMU` `xmag..zmag`. ArduPilot sends `compass.get_field()` in **milligauss**
   (`GCS_Common.cpp` `send_raw_imu`, L2270-2289). Heading is in `ATTITUDE.yaw` / `VFR_HUD.heading`.
   **The bridge does not speak MAVLink yet.**
4. **ArduPilot and MSP:** ArduPilot speaks MSP **only on serial ports set to `SERIALx_PROTOCOL = 32`** (generic
   MSP/sensors), 33 (DJI FPV) or 42 (DisplayPort) (`AP_SerialManager.h` L136-146;
   [ArduPilot MSP docs](https://ardupilot.org/copter/docs/common-msp-overview-4.2.html): "MSP requires a free serial
   port"). Even then it answers `MSP_ATTITUDE` but **not `MSP_RAW_IMU`**. `AP_MSP_Telem_Backend.cpp` L490-540 has
   no case for it, so you get no mag over MSP from ArduPilot. The bridge reports this (`FC variant: ARDU` warning)
   and stops after 5 error replies.

## 4. Path C — ArduPilot on a Matek F405 without CAN (MSP compass)

From the Matek page (ArduPilot ≥ 4.1) and `AP_Compass_config.h` L53-55 (`AP_COMPASS_MSP_ENABLED` follows
`HAL_MSP_SENSORS_ENABLED`, default on): wire node TX2 → FC UART RX, set `SERIALx_PROTOCOL = 32`,
`SERIALx_BAUD = 115`, clear `COMPASS_DISBLMSK` bit 17 (MSP), and reboot. **UNCERTAIN:** whether a given
1 MB F405 ArduPilot build keeps MSP sensors enabled. Check `COMPASS_DEV_ID` after boot. Telemetry is again MAVLink
over USB, which the bridge does not support yet.

## 5. F405 vs H743 summary

| Board | INAV | ArduPilot |
|---|---|---|
| MATEKH743 (CAN1) | MSP compass on a UART (INAV DroneCAN has no mag). USB MSP → bridge ✔ | DroneCAN compass (best fidelity). USB MAVLink → bridge ✘ (todo) |
| Matek F405 (no CAN: F405/SE/TE…) | MSP compass on a UART. USB MSP → bridge ✔ | MSP compass `SERIALx_PROTOCOL=32`. USB MAVLink → bridge ✘ |
| MatekF405-CAN | as above (MSP). Its target also wires a bare SPI RM3100 (not our module) | DroneCAN, or its own SPI RM3100 |

## 6. Unit scaling and conventions (what the bridge assumes)

### 6.1 MSP_RAW_IMU (102), 9×int16 LE: acc[3], gyro[3], mag[3]
| Field | INAV (`fc/fc_msp.c` L606-620) | Betaflight (`msp/msp.c` L1250-1268) | ArduPilot |
|---|---|---|---|
| acc | `lrintf(accADCf·512)`, accADCf = counts/acc_1G (`sensors/acceleration.c` L595) → **512 LSB/g** | raw counts (`acc.accADC`), sensor-dependent acc_1G: **UNCERTAIN** | not implemented |
| gyro | `gyroRateDps()` → **deg/s** | deg/s | — |
| mag (MSP compass) | `lrintf(magADC)`, magADCRaw = mGauss from MSP (`compass_msp.c` L69-88) → **0.1 µT/LSB** while uncalibrated | no RM3100 | — |
| mag (native SPI RM3100) | CC = 200 (`compass_rm3100.c` L72), `(int16)(xraw>>16)` of a 24-bit value left-aligned by 8 (L132-137) = **raw24>>8** → 256/75 = **3.413 µT/LSB** (34 mG) | — | — |
| mag after INAV calibration | `(m − magzero)·1024/maggain` (`compass.c` L560): **dimensionless** | — | — |

The INAV SPI driver drops the low 8 bits. INAV issue [#10746](https://github.com/iNavFlight/inav/issues/10746)
(closed) and [#10812](https://github.com/iNavFlight/inav/issues/10812) (open consolidation) report this. The code at
both pins still truncates. INAV registers RM3100 **only on SPI** (`target/common_hardware.c` L290-294,
`RM3100_SPI_BUS` only; [#9390](https://github.com/iNavFlight/inav/issues/9390), closed). The only Matek targets
that define it are `MATEKH743` (SPI3, CS2 pad PE2) and `MATEKF405CAN` (SPI2, PB12). The research simulation
(`research/rm3100_quantization_results.json`) puts the resulting heading error at up to about 13.5° at 20 µT.
That is one more reason to use the MSP path.

### 6.2 MSP_ATTITUDE (108), 3×int16 LE
roll and pitch are **decidegrees**, yaw is **degrees** 0..359. Sources: INAV `fc_msp.c` L738-741, Betaflight `msp.c` L1428-1431,
ArduPilot `AP_MSP_Telem_Backend.cpp` L981-1003 (`deg*10`, `wrap_360`).
**Sign:** INAV pitch > 0 = **nose down** (OSD `SYM_PITCH_DOWN` for pitch > 0, `io/osd.c` L3085; INAV's MAVLink sends
`-pitch`, `mavlink/mavlink_streams.c` L725). ArduPilot MSP sends aerospace pitch (+ nose up). The bridge emits
`fc_attitude_deg` in the **aerospace convention** (roll + right side down, pitch + nose up, yaw clockwise from north),
negating pitch for INAV/BTFL. The raw values are kept in `meta.msp_attitude`.

### 6.3 Body frame and accelerometer sign (ARCHITECTURE.md: FRD, level at rest = (0,0,−1) g)
Derived from INAV source, **not hardware-verified**. INAV's sensor vectors are in a **forward-left-up** frame:
* level → acc z = **+1 g** (`flight/imu.c` L367 `wCoGAcc = (accBFNorm.z − 1)…` "z direction is verified via SITL").
* `imuResetOrientationQuaternion` (L287-293) `q = (az+|a|, ay, −ax, 0)` together with roll/pitch extraction
  (L626-627) gives: right side down (+roll) ⇔ **+ay**, so y points **left**; nose up (INAV −pitch) ⇔ **+ax**, so x points **forward**.
* Consistency check: FRD MSP compass → `CW90_DEG_FLIP` → `CW90` (Matek's align) = (f, −r, −d) = forward-left-up.

So the bridge maps INAV `MSP_RAW_IMU` acc, gyro and mag with **(x, −y, −z)** into FRD. INAV level
`acc = (0, 0, 512)` becomes `accel_g = (0, 0, −1)` (specific force, z down). Tests: `test_level_at_rest_is_minus_one_g_z`,
`test_roll_right_and_nose_up_signs`, `test_heading_from_converted_mag_level`. Use `--body-frame frd` to disable
the mapping. `MSP2_SENSOR_COMPASS` is FRD by definition and is not remapped.

### 6.4 Calibration and quantisation metadata
Every emitted sample carries `meta.mag_quant_uT` (ARCHITECTURE.md 2026-11-27 "Quantised sources"): the step of the
mag value as delivered, i.e. the profile scale: **0.1 µT** for the MSP compass path (`inav-msp-mag`, and
`MSP2_SENSOR_COMPASS`), 256/75 ≈ 3.413 µT for `inav-rm3100-spi`, or `--mag-ut-per-lsb` for custom/Betaflight.
`meta.fc_mag_calibrated` is `false` / `true` / `"unknown"` as described in §2 step 6. Sim (`--fake-fc`) and replay
of `--capture` logs or raw MSP bytes derive both the same way (from recorded `MSP_FC_VARIANT` and
`MSP_CALIBRATION_DATA` replies; `"unknown"` if they were not recorded). Replay of Sample JSONL keeps whatever
`meta` the file had and never adds these keys.

### 6.5 Things the bridge does NOT emit
`mag_raw` and `rm3100_cycle_count` are never set. MSP values are not RM3100 counts: they are mGauss, or for the
SPI driver raw24>>8 after alignment. The integers are kept in `meta.msp_raw_imu` for audit.

## 7. Hardware validation checklist (to run when the owner connects hardware; bench only, props off)
Full runnable procedure with commands, expected values, pass/fail criteria and result fields:
[`reports/HARDWARE_VALIDATION_CHECKLIST.md`](../../reports/HARDWARE_VALIDATION_CHECKLIST.md) (items HV1–HV8). Summary:
1. `MSP_FC_VARIANT` = `INAV`; `MSP_RAW_IMU` replies at the poll rate (default 20 Hz); MSPv1, v2 and v2-over-v1 all answer.
2. Level and still: `accel_g ≈ (0, 0, −1)`. Nose up 30°: `accel_g.x ≈ +0.5`. Right side down 30°: `accel_g.y ≈ −0.5`.
3. Turn the craft clockwise (seen from above): `gyro_dps.z > 0`, and both the FC yaw and the bridge mag heading increase.
4. Field magnitude 25–65 µT (location-dependent) with `magzero=0` / `maggain=1024`; northern hemisphere `mag_uT.z > 0`.
5. Pitch sign: nose up gives `fc_attitude_deg.pitch > 0`.
6. Record with `--capture reports/hardware_logs/<date>_inav_msp.jsonl` and check that `--replay` reproduces the same samples.

### 6.6 GPS availability (`gps`, optional)
ARCHITECTURE.md 2026-11-27 added an optional `gps {fix, num_sat, hdop}` object for an availability indicator only.
The bridge fills it from **`MSP_RAW_GPS` (106)**, a read-only "out" message. INAV layout
([fc_msp.c L1044-1053 @ fce6c94](https://github.com/iNavFlight/inav/blob/fce6c94/src/main/fc/fc_msp.c#L1044-L1053),
identical at 9.1.0 and master, inside `#ifdef USE_GPS`): `u8 fixType, u8 numSat, u32 lat, u32 lon, u16 alt(m),
u16 groundSpeed, u16 groundCourse, u16 hdop` (18 bytes). `fixType` is `gpsFixType_e` {0 none, 1 2D, 2 3D}
([io/gps.h L90-92](https://github.com/iNavFlight/inav/blob/maintenance-10.x/src/main/io/gps.h#L90-L92)).

| Sample field | Source | Rule |
|---|---|---|
| `gps.fix` | byte 0 `fixType` | 0→`"none"`, 1→`"2d"`, 2→`"3d"`, anything else→`"unknown"` |
| `gps.num_sat` | byte 1 `numSat` | integer as reported |
| `gps.hdop` | (bytes 16-17 carry `gpsSol.hdop`) | **not emitted**: the schema does not require it, so no extra decoding |
| lat/lon/alt/speed/course | bytes 2-15 | **never decoded or emitted**; zeroed in `--capture` logs |

No other GPS request is needed (`MSP_GPSSTATISTICS` is not used). `gps` is omitted (= "Unknown") for non-INAV/unknown
FC variants (Betaflight's byte 0 is a boolean `STATE(GPS_FIX)`, ArduPilot's layout differs), error frames, payloads
< 18 bytes, no reply (stops asking after 3 silent tries), or a last reply older than 5 s. Nothing needs configuring
on the FC; a GPS receiver is optional and INAV's `feature GPS` only affects whether a fix can appear.

### 6.7 Device identity and provenance (D8)
At connect the bridge reads the device's self-reported identity with read-only `MSP_API_VERSION` (1),
`MSP_FC_VARIANT` (2), `MSP_FC_VERSION` (3), `MSP_BOARD_INFO` (4) and `MSP_UID` (160). Layouts at the INAV pin
([fc_msp.c L478-530, L1191-1195 @ fce6c94](https://github.com/iNavFlight/inav/blob/fce6c94/src/main/fc/fc_msp.c#L478-L530)):
API = u8 protocol, u8 major, u8 minor; variant = 4 ASCII; FC version = u8 major/minor/patch; board info = 4 ASCII board
id, u16 hw revision, u8 OSD flag, u8 capabilities, u8 length + target name; UID = 3 × u32 (STM32 96-bit unique ID),
kept as 24 hex chars in wire order (exactly 12 bytes required; no truncation). **Betaflight differences** (msp.c L715-868): FC version bytes are year−2000 /
month / patch followed by a length-prefixed version string; board info appends board-name and manufacturer strings
and a 32-byte signature (ignored). ArduPilot (AP_MSP) answers variant and board id `ARDU`, a firmware string where the
target name would be, and a 12-byte system ID. Rules, fields and the badge mapping:
[D8_PROVENANCE.md](D8_PROVENANCE.md). **What `verified` means:** `provenance: "verified"` means only that the device's self-reported UID matches an administratively trusted list (`config/verified_devices.json`). It is NOT hardware authentication or proof of device identity, and NOT validation of current measurements or sensor correctness. The production allowlist stays empty. **Display label (decided, d5374a1):** the app shows this case as **"ALLOWLISTED DEVICE (identity not authenticated)"**, not HARDWARE. Internal values are unchanged: `source: "hardware"`, `provenance: "verified"`. To make a board show ALLOWLISTED DEVICE (identity not authenticated), its `meta.device_identity.uid` must be added to
`config/verified_devices.json` after the HV checklist passes with the Auditor's sign-off; nothing on the FC changes.

## LIMITATIONS
* **L1** No hardware: framing, scaling, axis and sign conventions are verified against source and hand-built bytes
  only. Every item in §7 / [HARDWARE_VALIDATION_CHECKLIST.md](../../reports/HARDWARE_VALIDATION_CHECKLIST.md) is open.
* **L2** Body frame (§6.3) is a source derivation. The gyro sign is the weakest link (inferred, not traced to a
  driver). Betaflight frame is assumed identical (not checked).
* **L3** INAV mag units are physical only while `magzero=0` and `maggain=1024` (the bridge now *detects* this via
  `MSP_CALIBRATION_DATA` and reports `meta.fc_mag_calibrated`, but does not correct for it). After INAV calibration, values are
  dimensionless and the bridge does not yet undo `maggain` (it would also need the alignment order, §6.1).
  Tracked as non-blocking [BLOCKERS.md](../../BLOCKERS.md) **B3**.
* **L4** ArduPilot paths (B, C) need MAVLink. The bridge is MSP-only, and ArduPilot answers no `MSP_RAW_IMU`. MAVLink
  (e.g. `SCALED_IMU` mG) is a follow-up. pymavlink would be a new free dependency and needs PM approval.
* **L5** INAV 10 is a release candidate (stable planned for December 2026). The 9.x vs 10.x differences around the
  MSP compass were not diffed line by line. `master` does not contain the 10.x DroneCAN code.
  Tracked as non-blocking [BLOCKERS.md](../../BLOCKERS.md) **B4**.
* **L6** Node UART baud, the CLI `serial` index and field order, and VCP = port 0 on every Matek target are taken
  from docs and are **UNCERTAIN** (§2).
* **L7** INAV MSP compass is `int16` mGauss (0.1 µT steps, ±3.27 G range). That is fine for heading. The research
  report estimates ≤0.29° worst case at |H| = 20 µT.
* **L8** Betaflight: no RM3100 support verified; its scaling is unknown (profile requires explicit factors).
* **L9** `meta.fc_mag_calibrated` covers the **FC** only (INAV, read via `MSP_CALIBRATION_DATA`). The AP_Periph
  node's own `COMPASS_OFS/DIA/ODI/SCALE` are not visible over the FC's MSP, and for ArduPilot nothing is readable
  without MAVLink, so those stay `"unknown"` / unchecked. The value is refreshed every 10 s, so a change on the FC
  shows up within about 10 s. Message 14's layout is verified only for INAV (9.1.0, master, 10.x).
* **L10** `gps` is from source only (INAV `MSP_RAW_GPS`, not checked on hardware). With GPS disabled in INAV (or no
  receiver) 106 still answers `fixType=0, numSat=0`, so "GPS off" and "no fix yet" both read as `fix: "none"`;
  telling them apart would need `MSP_STATUS`/`MSP_SENSOR_STATUS`, which we chose not to add. Builds without
  `USE_GPS` answer an error frame (→ `gps` omitted), inferred from the default case of `mspFcProcessOutCommand`.
  Betaflight/ArduPilot 106 payloads are not interpreted. `--capture` rx is re-encoded per frame (for GPS redaction)
  and is no longer byte-exact.
* **L11** D8 identity is **self-reported** over the same wire and can be spoofed: any device or script can claim any
  variant, board or UID. A UID is not cryptographic proof; the allowlist only records "this UID passed the HV
  checklist". Identity is read once at connect (a device swapped mid-session is not detected). `--passive` sends no
  queries, so it is always unverified. Betaflight/ArduPilot identity layouts are source-read only.
  *Fixed (F12):* an `MSP_UID` reply that is not exactly 12 bytes used to be truncated, so an allowlisted UID plus
  extra bytes verified; now any other length is a failed UID query (`short` / `bad_length`) → unverified, and the
  allowlist match is exact equality.
  **What `verified` means:** `provenance: "verified"` means only that the device's self-reported UID matches an administratively trusted list (`config/verified_devices.json`). It is NOT hardware authentication or proof of device identity, and NOT validation of current measurements or sensor correctness. The production allowlist stays empty. **Display label (decided, d5374a1):** the app shows this case as **"ALLOWLISTED DEVICE (identity not authenticated)"**, not HARDWARE. Internal values are unchanged: `source: "hardware"`, `provenance: "verified"`.
