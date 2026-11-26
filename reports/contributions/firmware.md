# Contribution: Firmware Specialist (T4 + RM3100 compatibility research)

**Nothing in this file is hardware-verified.** No flight controller, CAN-L4-3100 node or aircraft was connected,
flashed or configured. Every result comes from reading firmware source/docs [SOURCE-DERIVED], hand-built MSP byte
streams [HAND-BUILT FRAMES] or simulation [SIMULATED]. The hardware checks are listed in
`reports/HARDWARE_VALIDATION_CHECKLIST.md` and none has been run.

## 1. Deliverables and paths

| Deliverable | Path | Evidence label |
|---|---|---|
| RM3100 / Matek AP_Periph compatibility report (formats, heading telemetry, monitoring, firmware comparison) | `docs/firmware/RM3100_COMPATIBILITY.md`; Page: https://cursor.com/canvas/store-1701c379-0283-4dd8-bd49-148fca282093/3d4650fa-b019-48bc-ba8b-22e3f35dade3 | SOURCE-DERIVED + SIMULATED |
| Quantisation simulation behind the report (6 data paths, 4 field cases, heading error) | `docs/firmware/research/rm3100_quantization_sim.py`, `rm3100_quantization_results.json`, `test_rm3100_quantization_sim.py` | SIMULATED |
| FC setup guide: INAV primary (MSP compass, `mag_hardware = MSP`, `align_mag = CW90`, H743 + F405), ArduPilot DroneCAN alternative (H743), ArduPilot MSP-compass path (F405), neutral FC mag calibration, unit scaling, body frame, calibration/quantisation metadata, GPS availability, LIMITATIONS L1-L10 | `docs/firmware/FC_SETUP.md` | SOURCE-DERIVED (pinned INAV `maintenance-10.x` @fce6c94, ArduPilot master) |
| MSP telemetry bridge: MSPv1 / MSPv2 / v2-over-v1 framing and incremental parser, read-only allowlist (`MSP_API_VERSION`, `MSP_FC_VARIANT`, `MSP_FC_VERSION`, `MSP_CALIBRATION_DATA`, `MSP_RAW_GPS`, `MSP_ATTITUDE`, `MSP_RAW_IMU`), INAV scaling (mag 0.1 µT/LSB, acc 512 LSB/g, FLU→FRD so level = (0,0,−1) g), `meta.mag_quant_uT`, `meta.fc_mag_calibrated`, optional `gps {fix,num_sat}` (no coordinates), `--replay` (Sample JSONL / capture JSONL / raw bytes → `source='replay'`), `--fake-fc` (`source='sim'`), `--capture`, live `--port` (`source='hardware'`, never run on hardware), optional pyserial | `firmware_bridge/` (`msp.py`, `scaling.py`, `sample.py`, `bridge.py`, `fake_fc.py`, `cli.py`, `README.md`) | HAND-BUILT FRAMES + SOURCE-DERIVED |
| Bridge tests | `firmware_bridge/tests/` (`frames.py`, `test_msp_framing.py`, `test_scaling_sample.py`, `test_bridge_modes.py`, `test_fc_calibration_quant.py`, `test_gps_availability.py`) | HAND-BUILT FRAMES, SIMULATED |
| Hardware validation checklist HV1-HV8 + optional HV9 (GPS, no position in logs), status NOT RUN | `reports/HARDWARE_VALIDATION_CHECKLIST.md` | procedure only |
| Non-blocking blockers B3 (INAV `maggain` normalisation not undone) and B4 (INAV 10 still RC) | `BLOCKERS.md` | SOURCE-DERIVED |
| T4 tracker row, LIMITATIONS F1-F10, changelog lines; defect D4 (replay forwarded schema-invalid samples) fixed | `TEAM_TRACKER.md` | — |

Commits (author "Firmware Specialist", none pushed by me; pushing is the PM's call):

| Commit | Time (IST) | Content |
|---|---|---|
| `16911f0` | 2026-11-26 23:54 | T4 in progress |
| `997d00f` | 2026-11-27 00:10 | T4 → REVIEW: bridge, FC_SETUP.md, tracker row, F1-F8 |
| `72fd54a` | 2026-11-27 00:13 | Hardware checklist HV1-HV8, BLOCKERS B3/B4 |
| `403976b` | 2026-11-27 00:17 | `meta.mag_quant_uT`, `meta.fc_mag_calibrated`, neutral-calibration step, HV4 extended, D4 fix |
| `9c429b9` | 2026-11-27 00:23 | Optional `gps {fix,num_sat}` from `MSP_RAW_GPS`, coordinates dropped/zeroed, HV9, F10 |
| `7313846` | (PM commit) | Added my untracked `docs/firmware/RM3100_COMPATIBILITY.md` and `docs/firmware/research/*` to the repo |

## 2. Tests actually executed (re-run for this report at HEAD `d0562e5`)

All runs on the shared box, Python 3.13.5, pytest 9.2.0. Every number below was obtained in this re-run, not
copied from earlier reports.

| When (IST) | Command | Result | How obtained / label |
|---|---|---|---|
| 2026-11-27 00:26:03 | `python3 -m pytest -q firmware_bridge/tests` | **94 passed, 1 skipped** (skip: virtual-pty test, `No module named 'serial'`) | executed; HAND-BUILT FRAMES + SIMULATED fake FC |
| 2026-11-27 00:26:04 | `/tmp/fwvenv/bin/python -m pytest -q firmware_bridge/tests` (venv with pyserial 3.5) | **95 passed** | executed; the pty test uses a *virtual* serial port, its `hardware` label only proves label-follows-transport, not a hardware result |
| 2026-11-27 00:26:04 | `python3 -m pytest -q docs/firmware/research` | **4 passed** | executed; SIMULATED |
| 2026-11-27 00:26:13 | `python3 docs/firmware/research/rm3100_quantization_sim.py` | Max heading error, case H=20 µT/Z=40 µT no noise: raw counts 0.025°, DroneCAN f16 0.033°, int16 mGauss (MSP path) 0.291°, **INAV native SPI driver 13.5°**; high-latitude H=5 µT/Z=55 µT: MSP path 1.146°, INAV native 44.9° | executed; SIMULATED |
| 2026-11-27 00:26:13 | `python3 -m firmware_bridge --fake-fc --count 3` | 3 samples, `source='sim'`, `accel_g = [0,0,-1]`, `gps = {fix:'3d', num_sat:12}` | executed; SIMULATED smoke run |
| 2026-11-27 00:26:04 → 00:27:49 | `python3 -m pytest -q` (full repo, optional) | **1 failed, 486 passed, 45 skipped, 1 xfailed** | executed. The working tree included other agents' uncommitted edits (`app/`, `heading_core/`). The one failure is `tests/test_t6_stale_quant.py::test_E3b_stress_20_sessions_60s` (4/20 sessions falsely MAG_STALE), the Auditor's open `heading_core` defect, not firmware_bridge code |

Coverage of the bridge suite: v1/v2/tunnel framing, XOR and CRC-8/DVB-S2 checksums (check value 0xBC), partial /
garbage / bad-checksum / error / oversize frames, bit-flip fuzz, scaling per profile, accel level = (0,0,−1) g and
roll/pitch signs, schema validation, replay of all three formats, capture→replay round trip, sim labelling,
read-only allowlist, calibration/quantisation metadata, GPS availability (v1/v2/v2-over-v1 hand-built 106 frames,
error/short/no-reply/stale/non-INAV cases, and an assertion that no coordinate keys or values appear anywhere).

## 3. Open limitations
**None of these has been checked on hardware.**
- **F1 / L1** No hardware: framing, scaling, axes and signs checked only against source and hand-built bytes; HV1-HV9 not run.
- **F2 / L2** INAV body frame (forward-left-up) and FLU→FRD mapping are source derivations; gyro sign is the weakest link; Betaflight frame assumed the same.
- **F3 / L3 / B3** INAV mag is µT only while `magzero=0`, `maggain=1024`; the bridge detects but does not undo INAV calibration (non-blocking).
- **F4 / L4** MAVLink deferred: no ArduPilot mag via the bridge (ArduPilot's AP_MSP has no `MSP_RAW_IMU`). pymavlink is approved as an optional extra but not implemented; waits for any Auditor defects against T4 to be fixed first.
- **F5 / L5 / B4** INAV 10 is a release candidate; INAV 9.x vs 10.x MSP-compass path not diffed line by line (non-blocking).
- **F6 / L6** UNCERTAIN from docs: CAN-L4-3100 UART baud, INAV `serial` CLI index/field order, USB VCP = port 0 on every Matek target.
- **F7** INAV native SPI RM3100 driver keeps raw24>>8 (≈3.41 µT/LSB, 13.5° simulated worst case); documented, not our path.
- **F8 / L8** Betaflight: no RM3100 driver verified; scaling unknown.
- **F9 / L9** `meta.fc_mag_calibrated` covers the INAV FC only; AP_Periph node and ArduPilot calibration read as "unknown"; message-14 layout verified for INAV only.
- **F10 / L10** `gps` is INAV-only and source-derived; GPS disabled and "no fix" both read `fix: "none"`; `--capture` rx is frame-exact, not byte-exact (garbage bytes dropped for GPS redaction).
- **L7** MSP compass is int16 mGauss (0.1 µT steps); simulated ≤0.29° at H = 20 µT, ≈1.1° at H = 5 µT.
- The fake FC is a protocol loopback, not a sensor model (that is `sim/`, T3).

## 4. Money spent and paid tools or services
- Money spent: **none**.
- Paid tools or services: **none**. Only free, open-source tools: Python, pytest, pyserial (optional), public INAV/ArduPilot/Betaflight/DroneCAN source and docs on GitHub. pymavlink (free) is approved but not yet used.
