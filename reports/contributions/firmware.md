# Contribution: Firmware Specialist (T4, RM3100 compatibility research, D8 bridge side)

**Nothing in this file is hardware-verified.** No flight controller, CAN-L4-3100 node or aircraft was connected,
flashed or configured. Every result comes from reading firmware source/docs [SOURCE-DERIVED], hand-built MSP byte
streams [HAND-BUILT FRAMES] or simulation [SIMULATED]. The hardware checks are listed in
`reports/HARDWARE_VALIDATION_CHECKLIST.md` and none has been run. `config/verified_devices.json` is empty, so no
bridge output can be `provenance: "verified"` today.

Refreshed after D8 (PM request, 2026-11-27). Checked against `origin/main` = HEAD `af640ae` before writing.

## 1. Deliverables and paths

| Deliverable | Path | Evidence label |
|---|---|---|
| RM3100 / Matek AP_Periph compatibility report (formats, heading telemetry, monitoring, firmware comparison) | `docs/firmware/RM3100_COMPATIBILITY.md`; Page: https://cursor.com/canvas/store-1701c379-0283-4dd8-bd49-148fca282093/3d4650fa-b019-48bc-ba8b-22e3f35dade3 | SOURCE-DERIVED + SIMULATED |
| Quantisation simulation behind the report (6 data paths, 4 field cases, heading error) | `docs/firmware/research/rm3100_quantization_sim.py`, `rm3100_quantization_results.json`, `test_rm3100_quantization_sim.py` | SIMULATED |
| FC setup guide: INAV primary (MSP compass, `mag_hardware = MSP`, `align_mag = CW90`, H743 + F405), ArduPilot DroneCAN alternative (H743), ArduPilot MSP-compass path (F405), neutral FC mag calibration, unit scaling, body frame, calibration/quantisation metadata (§6.4), GPS availability (§6.6), device identity and provenance (§6.7), LIMITATIONS L1-L11 | `docs/firmware/FC_SETUP.md` | SOURCE-DERIVED (pinned INAV `maintenance-10.x` @fce6c94, Betaflight and ArduPilot master) |
| MSP telemetry bridge: MSPv1 / MSPv2 / v2-over-v1 framing and incremental parser; read-only allowlist (`MSP_API_VERSION` 1, `MSP_FC_VARIANT` 2, `MSP_FC_VERSION` 3, `MSP_BOARD_INFO` 4, `MSP_CALIBRATION_DATA` 14, `MSP_RAW_IMU` 102, `MSP_RAW_GPS` 106, `MSP_ATTITUDE` 108, `MSP_UID` 160); INAV scaling (mag 0.1 µT/LSB, acc 512 LSB/g, FLU→FRD so level = (0,0,−1) g); `meta.mag_quant_uT`; `meta.fc_mag_calibrated`; optional `gps {fix,num_sat}` (no coordinates); `--replay` (Sample JSONL / capture JSONL / raw bytes → `source='replay'`); `--fake-fc` (`source='sim'`); `--capture`; live `--port` (never run on hardware); optional pyserial | `firmware_bridge/` (`msp.py`, `scaling.py`, `sample.py`, `bridge.py`, `identity.py`, `fake_fc.py`, `cli.py`, `README.md`) | HAND-BUILT FRAMES + SOURCE-DERIVED |
| **D8 (serial is not proof of hardware), bridge side:** self-reported identity in `meta.device_identity` (`self_reported: true`); `meta.provenance` = `simulated` / `unverified` / `verified` (+ `provenance_reason`, `verified_device_label`); fake FC reports `SIML`/`SIMF` → `sim` (SIML/SIMF always wins, even over an allowlisted UID); `verified` only for a live UID in the allowlist; replay never verified; `--verified-devices FILE`. No schema change | `firmware_bridge/identity.py`, `docs/firmware/D8_PROVENANCE.md` (contract for the UI), `config/verified_devices.json` (ships `{"devices": []}`) | SOURCE-DERIVED + HAND-BUILT FRAMES |
| Bridge tests | `firmware_bridge/tests/` (`frames.py`, `test_msp_framing.py`, `test_scaling_sample.py`, `test_bridge_modes.py`, `test_fc_calibration_quant.py`, `test_gps_availability.py`, `test_d8_provenance.py`) | HAND-BUILT FRAMES, SIMULATED |
| Hardware validation checklist HV1-HV8 + optional HV9 (GPS, no position in logs); sign-off now records the UID the bridge reports (`meta.device_identity.uid`) and when it was added to `config/verified_devices.json` (only after Auditor sign-off). Status NOT RUN | `reports/HARDWARE_VALIDATION_CHECKLIST.md` | procedure only |
| Non-blocking blockers B3 (INAV `maggain` normalisation not undone) and B4 (INAV 10 still RC) | `BLOCKERS.md` | SOURCE-DERIVED |
| T4 tracker row, LIMITATIONS F1-F11, changelog lines; defect D4 (replay forwarded schema-invalid samples) fixed in `403976b` | `TEAM_TRACKER.md` | n/a |

Commits (author "Firmware Specialist"). I never pushed; pushing is the PM's call (PM reports D8 pushed; `e37430b` is
on `origin/main`).

| Commit | Time (IST) | Content |
|---|---|---|
| `16911f0` | 2026-11-26 23:54 | T4 in progress |
| `997d00f` | 2026-11-27 00:10 | T4 → REVIEW: bridge, FC_SETUP.md, tracker row, F1-F8 |
| `72fd54a` | 2026-11-27 00:13 | Hardware checklist HV1-HV8, BLOCKERS B3/B4 |
| `403976b` | 2026-11-27 00:17 | `meta.mag_quant_uT`, `meta.fc_mag_calibrated`, neutral-calibration step, HV4 extended, D4 fix |
| `9c429b9` | 2026-11-27 00:23 | Optional `gps {fix,num_sat}` from `MSP_RAW_GPS`, coordinates dropped/zeroed, HV9, F10 |
| `642bc09` | 2026-11-27 00:28 | First version of this contribution file |
| `e37430b` | 2026-11-27 10:08 | D8: identity queries, `meta.device_identity` / `meta.provenance`, fake FC SIML/SIMF, `config/verified_devices.json`, `D8_PROVENANCE.md`, `test_d8_provenance.py`, FC_SETUP §6.7 / L11, checklist UID sign-off, F11 |
| (this commit) | 2026-11-27 | Post-D8 refresh of this file |
| `7313846` | (PM commit) | Added my `docs/firmware/RM3100_COMPATIBILITY.md` and `docs/firmware/research/*` to the repo |

## 2. Tests actually executed (re-run for this refresh at HEAD `af640ae`)

Shared box, Python 3.13.5, pytest 9.2.0; `-p no:cacheprovider`. Every number below was obtained in this re-run,
not copied from earlier reports. The working tree contained other agents' **uncommitted** work (UI: `app/*`,
`app/provenance.py`, `app/tests/test_app_d8_serial_provenance.py`; Auditor: `tests/test_t6_d8_bridge.py`,
`tests/t6_msp_device.py`, `reports/audit/*`), which the repo-wide runs include.

| When (IST) | Command | Result | How obtained / label |
|---|---|---|---|
| 2026-11-27 10:09:51 | `python3 -m pytest -q -p no:cacheprovider firmware_bridge/tests` | **125 passed, 2 skipped** (both skips: virtual-pty tests, pyserial not installed) | executed; HAND-BUILT FRAMES + SIMULATED fake FC |
| 2026-11-27 10:09:52 | `/tmp/fwvenv/bin/python -m pytest -q -p no:cacheprovider firmware_bridge/tests` (venv with pyserial 3.5) | **127 passed** | executed; the pty tests use a *virtual* serial port driven by the fake FC: default fake FC → `sim`/`simulated`, fake FC posing as INAV → `hardware`/`unverified`. Not a hardware result |
| 2026-11-27 10:09:53 | `python3 -m pytest -q -p no:cacheprovider tests/test_t6_msp.py` (Auditor's committed bridge tests) | **16 passed** | executed; HAND-BUILT FRAMES |
| 2026-11-27 10:12:27 | `python3 -m pytest -q -p no:cacheprovider docs/firmware/research` | **4 passed** | executed; SIMULATED |
| 2026-11-27 10:12:27 | `python3 docs/firmware/research/rm3100_quantization_sim.py` | Max heading error, H=20 µT/Z=40 µT: MSP int16-mGauss path 0.291° (0.408° with 15 nT noise), INAV native SPI driver 13.5° (13.55°); H=5 µT/Z=55 µT: MSP path 1.146° (1.577°), INAV native 44.9° (45.0°) | executed; SIMULATED |
| 2026-11-27 10:12:27 | `python3 -m firmware_bridge --fake-fc --count 2` | 2 samples: `source='sim'`, `provenance='simulated'`, reported `SIML`/`SIMF`, `accel_g=[0,0,-1]`, `gps={fix:'3d',num_sat:12}` | executed; SIMULATED smoke run |
| 2026-11-27 10:09:54 → 10:12:22 | `python3 -m pytest -q -p no:cacheprovider -rfE` (full repo, no pyserial) | **558 passed, 50 skipped, 0 failed** | executed; includes the uncommitted work listed above |
| 2026-11-27 10:14:56 | `/tmp/fwvenv/bin/python -m pytest -q -p no:cacheprovider tests/test_t6_d8_bridge.py` (Auditor's **uncommitted** D8 tests; without pyserial the whole file skips: "NOT RUN: pyserial missing") | **30 passed, 1 failed**: `test_non_allowlisted_uid_unverified[extended]` | executed; HAND-BUILT FRAMES over a virtual pty. **Firmware area (my defect), see §3 F12** |

## 3. Open limitations
**None of these has been checked on hardware.**
- **F1 / L1** No hardware: framing, scaling, axes and signs checked only against source and hand-built bytes; HV1-HV9 not run.
- **F2 / L2** INAV body frame (forward-left-up) and FLU→FRD mapping are source derivations; gyro sign is the weakest link; Betaflight frame assumed the same.
- **F3 / L3 / B3** INAV mag is µT only while `magzero=0`, `maggain=1024`; the bridge detects but does not undo INAV calibration (non-blocking).
- **F4 / L4** MAVLink deferred: no ArduPilot mag via the bridge (ArduPilot's AP_MSP has no `MSP_RAW_IMU`). pymavlink is approved as an optional extra but not implemented; waits for Auditor defects against T4 to be fixed first.
- **F5 / L5 / B4** INAV 10 is a release candidate; INAV 9.x vs 10.x MSP-compass path not diffed line by line (non-blocking).
- **F6 / L6** UNCERTAIN from docs: CAN-L4-3100 UART baud, INAV `serial` CLI index/field order, USB VCP = port 0 on every Matek target.
- **F7** INAV native SPI RM3100 driver keeps raw24>>8 (≈3.41 µT/LSB, 13.5° simulated worst case); documented, not our path.
- **F8 / L8** Betaflight: no RM3100 driver verified; scaling unknown.
- **F9 / L9** `meta.fc_mag_calibrated` covers the INAV FC only; AP_Periph node and ArduPilot calibration read as "unknown"; message-14 layout verified for INAV only.
- **F10 / L10** `gps` is INAV-only and source-derived; GPS disabled and "no fix" both read `fix: "none"`; `--capture` rx is frame-exact, not byte-exact.
- **F11 / L11** D8 device identity is **self-reported** over the same wire and can be spoofed (any device or script can claim any variant, board or UID). A UID is not cryptographic proof; the allowlist only records "this UID passed the HV checklist". Identity is read once at connect (a device swapped mid-session is not detected); `--passive` sends no queries and is always unverified; `verified` is never produced on replay; Betaflight/ArduPilot identity layouts are source-read only.
- **F12 (new, found in this re-run, not yet fixed)** An `MSP_UID` reply **longer** than 12 bytes is truncated to its first 12 bytes, so an allowlisted UID followed by extra bytes is classified `verified` (Auditor's uncommitted `test_non_allowlisted_uid_unverified[extended]`). INAV, Betaflight and ArduPilot all send exactly 12 bytes, so the fix is to require exactly 12 and treat any other length as a failed UID query (unverified). Not changed here because this commit is limited to this file. It only matters if the allowlist is non-empty, and it ships empty.
- **L7** MSP compass is int16 mGauss (0.1 µT steps); simulated ≤0.29° at H = 20 µT, ≈1.1° at H = 5 µT.
- **UI dependency (not firmware code):** at HEAD the committed UI still shows HARDWARE for any `hardware` sample over serial; the UI developer's uncommitted D8 work reads `meta.provenance` / `meta.device_identity` and fixes this. The app's serial source does not pass `--verified-devices` to the bridge, so both must use the same allowlist file (fails safe to UNVERIFIED).
- The fake FC is a protocol loopback, not a sensor model (that is `sim/`, T3). It reports `SIML`/`SIMF` and imitates INAV's MSP layouts.

## 4. Money spent and paid tools or services
- Money spent: **none**.
- Paid tools or services: **none**. Only free, open-source tools: Python, pytest, pyserial (optional), public INAV/ArduPilot/Betaflight/DroneCAN source and docs on GitHub. pymavlink (free) is approved but not yet used.
