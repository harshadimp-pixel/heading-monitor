# Hardware Validation Checklist: T4 firmware_bridge (RM3100 / Matek FC)

Owner of the procedure: Firmware Specialist. **To be run by the owner (Harshad) when hardware is available.**
Status: **NOT RUN. Nothing here is verified.** None of the items below may be tagged as hardware-verified until
the raw log is committed under `reports/hardware_logs/` and the Testing & Technical Auditor signs off
(README ground rule 1).

Background and source references: [`docs/firmware/FC_SETUP.md`](../docs/firmware/FC_SETUP.md) (§6 conventions,
§7 summary, LIMITATIONS), bridge usage: [`firmware_bridge/README.md`](../firmware_bridge/README.md).
Non-blocking caveats: [`BLOCKERS.md`](../BLOCKERS.md) B3, B4.

## Safety and setup (applies to every item)
* Bench only. **Remove the propellers**, disconnect the motor battery or keep the FC disarmed, and power it from USB.
* The bridge sends only read-only MSP requests (`MSP_FC_VARIANT`, `MSP_CALIBRATION_DATA`, `MSP_RAW_GPS`, `MSP_ATTITUDE`, `MSP_RAW_IMU`). It never writes
  settings, reboots or flashes. Any FC configuration (FC_SETUP.md §2) is done by the owner in INAV Configurator.
* Expected configuration: INAV on the Matek FC with `mag_hardware = MSP` and `align_mag = CW90`. CAN-L4-3100 TX2
  wired to a spare FC UART RX with MSP enabled. **INAV mag calibration left unset** (`magzero_x/y/z = 0`,
  `maggain_x/y/z = 1024`; check with `get magzero` and `get maggain` in the CLI). Board and module mounted flat,
  arrows forward, away from steel and magnets.
* Close INAV Configurator before running the bridge, because only one program can open the USB port.
* Install: `pip install -r requirements.txt pyserial`. Find the port: Linux `/dev/ttyACM0`, macOS
  `/dev/tty.usbmodem*`, Windows `COMx` (Device Manager).
* Below, `PORT` stands for that port and `DATE` for today's date (e.g. 2026-12-01). Make the log folder first:
  `mkdir -p reports/hardware_logs`.
* Handy one-liner to print accel, mag, |B|, heading and FC attitude from a JSONL file (`F` = file):
  ```
  python -c "import json,math,sys;[print('acc',[round(v,3) for v in s.get('accel_g',[])],'mag',[round(v,1) for v in s['mag_uT']],'|B|',round(math.dist(s['mag_uT'],[0,0,0]),1),'hdg',round(math.degrees(math.atan2(-s['mag_uT'][1],s['mag_uT'][0]))%360,1),'att',s.get('fc_attitude_deg')) for s in map(json.loads,open(sys.argv[1]))]" F
  ```

---

## HV1: MSP link: FC answers MSP_RAW_IMU and MSP_ATTITUDE over USB (MSPv1, v2, v2-over-v1)
**Steps**
1. Connect the FC by USB and power the CAN-L4-3100 (blue LED blinking slowly).
2. Run once for each protocol version:
   ```
   python -m firmware_bridge --port PORT --baud 115200 --msp-version 1  --count 100 --capture reports/hardware_logs/DATE_hv1_v1.capture.jsonl  --out reports/hardware_logs/DATE_hv1_v1.jsonl
   python -m firmware_bridge --port PORT --baud 115200 --msp-version 2  --count 100 --capture reports/hardware_logs/DATE_hv1_v2.capture.jsonl  --out reports/hardware_logs/DATE_hv1_v2.jsonl
   python -m firmware_bridge --port PORT --baud 115200 --msp-version 21 --count 100 --capture reports/hardware_logs/DATE_hv1_v21.capture.jsonl --out reports/hardware_logs/DATE_hv1_v21.jsonl
   ```
3. Check the rate: `python -c "import json,sys;t=[json.loads(l)['t'] for l in open(sys.argv[1])];print(len(t), (len(t)-1)/(t[-1]-t[0]),'Hz')" reports/hardware_logs/DATE_hv1_v1.jsonl`

**Expected:** stderr shows `FC variant: INAV`. Each run exits with code 0 and writes 100 lines, all with `"source":"hardware"`,
`meta.msg = "MSP_RAW_IMU"`, and a `fc_attitude_deg` object present. Rate is about 20 Hz (the default `--rate 20`).

**Pass:** all three versions produce 100 samples at ≥ 15 Hz and none are all-zero `mag_uT`.
**Fail:** an error/exit code 2, `FC variant` not INAV, missing attitude, or `mag_uT == [0,0,0]` (means mag not detected; see FC_SETUP.md §2 step 5).

| Version | Samples | Rate (Hz) | FC variant | Result (PASS/FAIL) | Notes |
|---|---|---|---|---|---|
| v1 | | | | | |
| v2 | | | | | |
| v2-over-v1 | | | | | |

---

## HV2: Accelerometer sign and scale (body frame FRD, level = (0, 0, −1) g)
**Steps** (use a protractor, phone inclinometer or a 30° wedge; hold still ≥ 3 s for each pose):
```
python -m firmware_bridge --port PORT --baud 115200 --count 60 --out reports/hardware_logs/DATE_hv2_level.jsonl
python -m firmware_bridge --port PORT --baud 115200 --count 60 --out reports/hardware_logs/DATE_hv2_noseup30.jsonl
python -m firmware_bridge --port PORT --baud 115200 --count 60 --out reports/hardware_logs/DATE_hv2_rightdown30.jsonl
```
Poses: (a) level; (b) nose up 30°; (c) right side down 30° (rolled right). Average `accel_g` with the one-liner.

**Expected (g, ±0.05 per axis):**
| Pose | accel_g x | accel_g y | accel_g z |
|---|---|---|---|
| Level | 0.00 | 0.00 | −1.00 |
| Nose up 30° | +0.50 | 0.00 | −0.87 |
| Right side down 30° | 0.00 | −0.50 | −0.87 |

**Pass:** every average is within ±0.05 g of the table, and `|accel_g|` is 1.00 ± 0.05.
**Fail:** any sign is reversed (this means the forward-left-up → FRD mapping in `firmware_bridge/scaling.py` is wrong; report it to the PM), or the magnitude is off (512 LSB/g assumption is wrong).

| Pose | Measured x | y | z | Result (PASS/FAIL) |
|---|---|---|---|---|
| Level | | | | |
| Nose up 30° | | | | |
| Right down 30° | | | | |

---

## HV3: Gyro sign and mag heading follow FC yaw (clockwise rotation)
**Steps**
1. Start recording: `python -m firmware_bridge --port PORT --baud 115200 --duration 30 --capture reports/hardware_logs/DATE_hv3.capture.jsonl --out reports/hardware_logs/DATE_hv3.jsonl`
2. Keep the craft level. Slowly turn it **clockwise seen from above**, about 90° every 5 s, for at least one full turn.
3. Inspect it with the one-liner. Gyro: `python -c "import json,sys;print(max(json.loads(l)['gyro_dps'][2] for l in open(sys.argv[1])))" reports/hardware_logs/DATE_hv3.jsonl`

**Expected:** during the turn `gyro_dps[2] > 0` (about +10 to +30 °/s). Both `fc_attitude_deg.yaw` and the mag heading
`atan2(−mag_y, mag_x)` **increase** (wrapping 359→0). The mag heading tracks FC yaw within ±15° (uncalibrated, magnetic,
no declination).

**Pass:** gyro z positive while turning clockwise, both headings increase, |mag heading − FC yaw| ≤ 15° at the four 90° stops.
**Fail:** gyro z negative (gyro sign inferred wrong, LIMITATION F2), or mag heading decreasing or offset by about 90°/180° (axis mapping or `align_mag` wrong).

| Check | Measured | Result (PASS/FAIL) |
|---|---|---|
| gyro z sign while turning CW | | |
| FC yaw increases | | |
| Mag heading increases | | |
| Max |mag hdg − FC yaw| at 0/90/180/270 | | |

---

## HV4: Neutral FC calibration, field magnitude and vertical sign (units µT)
**Steps**
1. INAV CLI (owner, FC_SETUP.md §2 step 6): `get magzero` → all 0 and `get maggain` → all 1024. If not, either set
   them neutral as in FC_SETUP.md §2 step 6 (then `save`) or record the values and STOP (see BLOCKERS B3).
   Do **not** run the FC compass calibration. If the AP_Periph node is reachable (DroneCAN GUI Tool), note its
   `COMPASS_OFS_X/Y/Z`, `COMPASS_DIA_X/Y/Z`, `COMPASS_ODI_X/Y/Z`, `COMPASS_SCALE` (neutral = 0 / 1 / 0 / 0).
2. Close the CLI/Configurator, then check what the bridge reads back (read-only `MSP_CALIBRATION_DATA`):
   ```
   python -m firmware_bridge --port PORT --baud 115200 --count 5 --capture reports/hardware_logs/DATE_hv4_cal.capture.jsonl --out reports/hardware_logs/DATE_hv4_cal.jsonl
   python -c "import json,sys;m=json.loads(open(sys.argv[1]).readline())['meta'];print(m['fc_mag_calibrated'],m.get('fc_mag_cal'),m['mag_quant_uT'])" reports/hardware_logs/DATE_hv4_cal.jsonl
   ```
3. Use the HV3 log (or record 30 s while turning slowly through all orientations).
4. Compute |B| with the one-liner. Look up the local total field and inclination (NOAA WMM calculator, https://www.ngdc.noaa.gov/geomag/calculators/magcalc.shtml).

**Expected:** step 2 prints `False {'source': 'MSP_CALIBRATION_DATA', 'mag_zero': [0, 0, 0], 'mag_gain': [1024, 1024, 1024]} 0.1`
(stderr also shows `fc_mag_calibrated=False`). |B| is between 25 and 65 µT and within about ±20% of the local WMM
total field (uncalibrated, hard-iron included). In the northern hemisphere, level, `mag_uT[2] > 0` (field points down).

**Pass:** step 2 shows `False` with the values matching the CLI read-back, |B| within the range above in ≥ 90% of
samples, and the z sign as expected.
**Fail:** `True` while the CLI shows neutral values (decoder/layout wrong, report to PM), `"unknown"` on INAV (message
14 not answered), |B| about 1000 (INAV calibration active, B3), about 10× too small or large (units not mGauss), or
z sign reversed.

| Item | Value |
|---|---|
| CLI magzero / maggain read back | |
| Bridge `fc_mag_calibrated` / `fc_mag_cal` / `mag_quant_uT` | |
| AP_Periph node COMPASS_OFS / DIA / ODI / SCALE (if checked) | |
| Local WMM total field (µT) / inclination | |
| Measured median |B| (µT) | |
| z sign (level) | |
| Result (PASS/FAIL) | |

---

## HV5: Attitude pitch and roll signs (aerospace convention)
**Steps:** record each pose as in HV2, with `--count 40`, to `DATE_hv5_noseup.jsonl` and `DATE_hv5_rightdown.jsonl`. Check `fc_attitude_deg`.

**Expected:** nose up 30° gives `pitch ≈ +30`. Right side down 30° gives `roll ≈ +30` (±5°). Compare `meta.msp_attitude` (raw INAV): its pitch should be about −300 decidegrees → shown as −30.0, and the bridge negates it.

**Pass:** signs and values as expected (±5°).  **Fail:** pitch sign reversed (INAV pitch convention assumption wrong) or roll sign reversed.

| Pose | fc pitch | fc roll | raw meta pitch | Result (PASS/FAIL) |
|---|---|---|---|---|
| Nose up 30° | | | | |
| Right down 30° | | | | |

---

## HV6: Node UART baud and INAV serial port settings
**Steps**
1. In INAV CLI run `serial` and note the line for the UART wired to the CAN-L4-3100 TX2, then `status` (the mag must be listed) and `get mag_hardware`.
2. Optional, needs a USB-UART adapter: connect adapter RX to the node TX2 (and GND), then
   `python -m firmware_bridge --port ADAPTER_PORT --baud 115200 --passive --duration 10 --capture reports/hardware_logs/DATE_hv6_node.capture.jsonl --out reports/hardware_logs/DATE_hv6_node.jsonl`
   If you get 0 samples, retry with `--baud 57600`, `230400` and `460800`.

**Expected:** the `serial` line shows function mask `1` (MSP) at 115200 on that UART and no other function. `mag_hardware = MSP`.
In step 2, samples arrive with `meta.msg = "MSP2_SENSOR_COMPASS"`, and at the working baud |B| matches HV4 to within 1 µT.

**Pass:** the INAV config matches and the mag is detected. In step 2 (if done), the working baud is recorded.  **Fail:** mag not detected, or the node gives no MSP at any baud.

| Item | Value |
|---|---|
| `serial` line for node UART | |
| `get mag_hardware` | |
| Node TX2 working baud (step 2) | |
| Result (PASS/FAIL) | |

---

## HV7: `align_mag = CW90` is correct for our mounting
**Steps:** with the board and module both arrows-forward and flat, record level and point the nose at **magnetic north**
(use a phone compass held away from the craft), then east (90°):
`python -m firmware_bridge --port PORT --baud 115200 --count 40 --out reports/hardware_logs/DATE_hv7_N.jsonl` (and `_E`).

**Expected:** facing north, `mag_uT[0] > 0` and `|mag_uT[1]|` is small. Facing east, `mag_uT[1] < 0` and `|mag_uT[0]|` is small (heading ≈ 90°).
In INAV Configurator, the heading shown matches the phone compass within ±15°.

**Pass:** both poses as expected.  **Fail:** heading off by about 90°/180° or mirrored. Then try the INAV 10 alignment wizard or `align_mag_roll/pitch/yaw`, record the setting that works, and report it to the PM.

| Pose | mag x | mag y | heading | Result (PASS/FAIL) |
|---|---|---|---|---|
| North | | | | |
| East | | | | |
| align_mag setting used | | | | |

---

## HV8: Capture → replay reproduces the same samples
**Steps**
```
python -m firmware_bridge --replay reports/hardware_logs/DATE_hv1_v1.capture.jsonl --out /tmp/hv8_replay.jsonl
python -c "import json;a=[json.loads(l) for l in open('reports/hardware_logs/DATE_hv1_v1.jsonl')];b=[json.loads(l) for l in open('/tmp/hv8_replay.jsonl')];print(len(a),len(b),sum(x['mag_uT']==y['mag_uT'] and x.get('accel_g')==y.get('accel_g') for x,y in zip(a,b)),{y['source'] for y in b})"
```
**Expected:** the counts are equal (or the replay has ≥ the live count), all paired samples have identical `mag_uT`/`accel_g`, and the
sources printed are `{'replay'}`.

**Pass:** 100% identical vectors and source `replay`.  **Fail:** any mismatch or any `hardware` label in the replay output.

| Live samples | Replay samples | Identical pairs | Sources | Result (PASS/FAIL) |
|---|---|---|---|---|
| | | | | |

---

## HV9 (optional): GPS availability indicator, and no position anywhere
Only if a GPS receiver is connected to the FC. Indoors is fine (no fix expected).
**Steps**
```
python -m firmware_bridge --port PORT --baud 115200 --count 200 --out reports/hardware_logs/DATE_hv9.jsonl --capture reports/hardware_logs/DATE_hv9.capture.jsonl
python -c "import json,collections;c=collections.Counter(json.dumps(json.loads(l).get('gps'),sort_keys=True) for l in open('reports/hardware_logs/DATE_hv9.jsonl'));print(c)"
```
Compare with INAV Configurator's GPS tab (fix type, satellites) just before/after.
**Expected:** `gps` = `{"fix": ..., "num_sat": ...}` matching Configurator; only the keys `fix`/`num_sat`. With no GPS
receiver: `{"fix":"none","num_sat":0}`. Before committing, search both files for your home latitude/longitude
digits (e.g. first 4 digits) and confirm they are absent; in the capture, every 106 frame payload is
`<fix><nsat>` followed by 16 zero bytes.

**Pass:** fix/num_sat agree with Configurator and no position data in either file.  **Fail:** any mismatch or any
position data found (then do not commit the logs).

| Configurator fix / sats | Bridge `gps` | Position absent (Y/N) | Result |
|---|---|---|---|
| | | | |

---

## Sign-off
| Field | Value |
|---|---|
| Run by / date (IST) | |
| FC board + INAV version (`version` in CLI) | |
| CAN-L4-3100 firmware (MatekL431-GPS / -Periph, version) | |
| Logs committed (paths) | |
| Auditor sign-off | |
