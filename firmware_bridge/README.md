# firmware_bridge (T4)

This package reads MSP telemetry from a Matek FC (INAV is the primary target) and writes **Sample JSONL** in the
format of [`contracts/sample.schema.json`](../contracts/sample.schema.json). FC setup, unit scaling and sources are
in [`docs/firmware/FC_SETUP.md`](../docs/firmware/FC_SETUP.md). Nothing in this package is hardware-verified yet.

```
python -m firmware_bridge --port /dev/ttyACM0 --baud 115200            # live FC      -> source="hardware"
python -m firmware_bridge --replay FILE                                # recorded     -> source="replay"
python -m firmware_bridge --fake-fc --count 100                        # loopback sim -> source="sim"
```

Useful options:
* `--msp-version 1|2|21`: MSPv1 (`$M`, XOR), MSPv2 (`$X`, CRC-8/DVB-S2), or v2 tunnelled in v1.
* `--rate HZ`: how often to poll in live and fake modes.
* `--profile inav-msp-mag|inav-rm3100-spi|betaflight|custom`, `--auto-profile`, `--mag-ut-per-lsb`,
  `--accel-lsb-per-g`, `--body-frame flu|frd`.
* `--passive`: listen without polling, e.g. on a USB-UART adapter attached to the CAN-L4-3100 TX2, which pushes
  `MSP2_SENSOR_COMPASS`.
* `--capture FILE`: log the raw tx/rx bytes with timestamps, so you can replay them later. Use this for any
  future `reports/hardware_logs/` recording.
* `--count N`, `--duration S`, `--out FILE`, `--realtime` (pace replay output).

**pyserial** is optional. It is only needed for `--port` (`pip install pyserial`). Without it the bridge exits
with code 2 and a clear message. Replay, fake-FC and the tests run on the standard library alone; `jsonschema` is
used by the tests if it is installed.

## Source labelling (hard rule)
The `source` value comes from the transport **class**, never from a flag or from data in a file.
`SerialTransport.kind == "hardware"`, `FakeFCTransport.kind == "sim"`, and replay always writes `"replay"`. A
replayed Sample JSONL keeps the label it was recorded with in `meta.original_source`.

## Safety
Live mode only sends read-only requests: `MSP_FC_VARIANT`, `MSP_CALIBRATION_DATA` (INAV only, at start and every 10 s), `MSP_ATTITUDE` and `MSP_RAW_IMU`. Any other command
raises an error before anything is written (`bridge.ALLOWED_REQUESTS`). There is no `MSP_SET_*`, no reboot and
no flashing.

## Output
* `mag_uT`, `accel_g` and `gyro_dps` are in the ARCHITECTURE body frame (x forward, y right, z down). Level and
  at rest, `accel_g` is (0, 0, −1).
* `fc_attitude_deg` uses the aerospace convention: + roll is right side down, + pitch is nose up, yaw is clockwise
  from north.
* `meta` holds `msp_raw_imu` and `msp_attitude` (the untouched integers), `mag_profile`, `mag_ut_per_lsb`,
  `body_frame_in`, `scaling_uncertain`, `msp_version` and `fc_variant`.
* `meta.mag_quant_uT`: the mag step in µT (0.1 on the MSP path). `meta.fc_mag_calibrated`: `false` only when INAV's
  `magzero`=0 and `maggain`=1024 were read back via `MSP_CALIBRATION_DATA`, `true` if they differ, else `"unknown"`
  (read values in `meta.fc_mag_cal`). See FC_SETUP.md §2 step 6 and §6.4.
* `mag_raw` and `rm3100_cycle_count` are never set, because MSP does not carry RM3100 counts.

## Replay input formats (auto-detected)
1. **Sample JSONL**, such as earlier bridge or sim output. Each line is re-emitted with `source="replay"`.
2. **Capture JSONL** from `--capture`. The first line is a header
   `{"capture":"firmware_bridge/msp","format_version":1,...}`, followed by lines `{"t":..,"rx":"<hex>"}` and
   `{"t":..,"tx":"<hex>"}`. The rx bytes are parsed again and the original `t` is kept.
3. **Raw binary MSP byte stream** (anything that doesn't start with `{`). `t` is synthesised as
   `index / --replay-rate`.

## Modules
`msp.py` (framing, checksums, incremental parser), `scaling.py` (decoders, unit profiles, body frame),
`sample.py` (Sample builder and a dependency-free validator), `bridge.py` (poller, capture, replay),
`fake_fc.py` (simulated INAV-style FC), `cli.py`.

## Tests
`python -m pytest firmware_bridge/tests`. The tests build MSP frames by hand, byte by byte, separately from the
encoder. They cover v1/v2/tunnel framing, the checksums (including the CRC-8/DVB-S2 check value 0xBC),
partial/garbage/bad-checksum/error/jumbo/oversize frames, a 2000-case bit-flip fuzz, scaling, the accel sign and
body frame, schema validation (jsonschema), all replay formats, a capture→replay round trip, sim labelling, the
CLI, and pyserial over a *virtual* pty. The pty test is skipped if pyserial is missing. Its `hardware` label only
proves that the label follows the transport; it is not a hardware result.

## LIMITATIONS
See [FC_SETUP.md § LIMITATIONS](../docs/firmware/FC_SETUP.md#limitations). In short:
* No real FC has been tested, and the axis/sign mapping is derived from source.
* INAV mag is in µT only while INAV's mag calibration is unset.
* There is no MAVLink, so no ArduPilot mag.
* Betaflight scaling is unknown.
* The fake FC is a protocol loopback, not a sensor model (that's `sim/`, T3).
