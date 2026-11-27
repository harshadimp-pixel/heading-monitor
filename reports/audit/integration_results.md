# Integration results (T6, end-to-end): v5 FINAL rerun (fresh clone 03fc993) [SIMULATED] / [REPLAYED]

Run by T6 on 2026-11-27, 11:55–11:58 IST, in a **fresh `git clone` checked out at 03fc993** (porcelain-clean). That is UI's flake fix 3cf0d1f (on top of 479a72c, the decided label + D9) plus T6's D11 helper fix; there is no product-code difference from 3cf0d1f. The venv is private (/workspace/audit/venv_clean, not /tmp/hm-venv), and TMPDIR/HOME are private dirs under /workspace/audit (0 Chrome temp leftovers after the run).
Command, run as a clean machine would run it (empty temporary HOME; unique work dirs under /workspace/audit):
```
cd <clone> && HOME=$(mktemp -d) TMPDIR=$(mktemp -d) python reports/audit/integration_run.py <clone> <out>
```
Environment: Linux, Python 3.13.5, numpy 2.5.5, pytest 9.2.0, jsonschema 4.26.0, pyserial 3.5; Google Chrome 156.0.8078.47, headless=new, `--dump-dom`, with a **fresh temporary `--user-data-dir` + `--incognito` per launch, removed afterwards** (Codex 25/30 profile finding fixed). Node runs the app's own `headingmath.js`.
Every app step starts a **fresh** `python -m app` on a free ephemeral port, and the listening PID is checked against the started PID with `ss` (`pid_ok`). The UI developer's long-running instance on 8080 is never the instance tested.
Raw: `raw/integration_results.json`, `raw/integration_run_stdout.log`, `raw/ui_dom_*.html`. No-pyserial run: `raw/integration_results_noserial.json`, `raw/integration_noserial_stdout.log`.

## Summary: 37 / 37 PASS with pyserial; 31 / 37 without pyserial (the 6 serial D8 steps count as FAIL 'NOT RUN')

**D8 steps:**
- **A10c:** product fake FC on a pty → SIMULATED, 0 live.
- **A10d and A10e:** unknown and unidentified devices → UNVERIFIED SOURCE.
- **A10f:** F11 limitation demonstration. An emulator with an allowlisted UID gets the badge **'ALLOWLISTED DEVICE (identity not authenticated)'** and the exact decided banner. This is **NOT hardware validation**: an allowlist match is an administrative trust decision, not hardware authentication.
- **A10g:** UID one bit off → UNVERIFIED SOURCE.
- **A10h:** shipped allowlist empty.
- **A10i:** forged ingest claims into a serial app are refused (POST /api/sample only with `--source ingest`); 0 live, 0 verified.
- **A10z:** none of the 10 DOM dumps shows a bare-HARDWARE badge.

History:
- 1ddd6b9: 37/37, no-pyserial 31/37 (same PASS/FAIL for every step; only the measured numbers vary run to run, 11:16 IST).
- 25e308d: 35/37 (A10f/A10z failed before the label landed).
- 8343656: 35/35 with the previous harness.
- f058c9a: 30/30 (v3).
- 471724e: 25/27 (D6).

| Step | Result | Summary |
|---|---|---|
| A1 sim:static -> heading_core -> app | **PASS** | pid_ok=True records=155 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.29 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:yaw_spin -> heading_core -> app | **PASS** | pid_ok=True records=153 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.32 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:tilted_spin -> heading_core -> app | **PASS** | pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.41 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:calibration_dance -> heading_core -> app | **PASS** | pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=13.91 deg warnings=['FIELD_MAGNITUDE_OUT_OF_RANGE', 'NOT_CALIBRATED', 'TILT_TOO_LARGE'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:hard_iron -> heading_core -> app | **PASS** | pid_ok=True records=153 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=10.62 deg warnings=['FIELD_MAGNITUDE_OUT_OF_RANGE', 'HIGH_NOISE', 'NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:soft_iron -> heading_core -> app | **PASS** | pid_ok=True records=150 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=10.58 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:motor_interference -> heading_core -> app | **PASS** | pid_ok=True records=153 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.32 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:high_noise -> heading_core -> app | **PASS** | pid_ok=True records=153 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.35 deg warnings=['HIGH_NOISE', 'NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1b sim:motor_interference (--sim-duration 10) -> app: interference must be warned | **PASS** | pid_ok=True records=199 warnings_seen=['FIELD_MAGNITUDE_OUT_OF_RANGE', 'HIGH_NOISE'] max/err/=14.7 deg samples err>5deg=76 of which without any warning=0 |
| A2 replay sim/examples/calibration_dance_10hz_10s_seed42.jsonl | **PASS** | pid_ok=True file_lines=100 records=100 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A2 replay sim/examples/hard_iron_10hz_5s_seed42.jsonl | **PASS** | pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A2 replay sim/examples/motor_interference_10hz_5s_seed42.jsonl | **PASS** | pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A2 replay sim/examples/static_10hz_5s_seed42.jsonl | **PASS** | pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A2 replay sim/examples/yaw_spin_10hz_5s_seed42.jsonl | **PASS** | pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A2 replay sim/examples/yaw_spin_dronecan_50hz_2s_seed42.jsonl | **PASS** | pid_ok=True file_lines=100 records=100 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A2 replay sim/examples/yaw_spin_msp_50hz_2s_seed42.jsonl | **PASS** | pid_ok=True file_lines=100 records=100 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A3a fake-FC --capture -> firmware_bridge --replay | **PASS** | rc=0/0 capture_header_source=sim live=60 (source ['sim']) replayed=60 (source ['replay']) mag bit-identical=True |
| A3b capture replay -> app | **PASS** | pid_ok=True records=60 sample.source=['replay'] badge=['REPLAY'] heading[0..3]=[0.7, 2.1, 3.7] |
| A4 firmware_bridge --fake-fc | POST -> app (ingest) | **PASS** | pid_ok=True posted=100 accepted=100 rejected=[] sources=['sim'] badge=['SIMULATED'] heading range=0.2..151.7 |
| A5 calibration wizard start/stop/fit/apply/save/clear/load | **PASS** | pid_ok=True collected n=303/300 bins=9/12 octants=5/8 fit ok=True backend=heading_core offset_uT=[11.876943017379679, -8.040083296555874, 5.001786724385932] (sim truth hard-iron [12,-8,5]) / after apply: calibrated=True, RMSE vs truth last 50=0.72 deg / clear -> active=False; load -> active=True |
| A6 frozen + stale data | **PASS** | pid_ok=True 3 s identical samples -> warnings=['SENSOR_STALE', 'NOT_CALIBRATED'] quality=0.025 sensor_status=OK; then 2.2 s silence (stale 1.5 s) -> sensor_status=STALE reason='no sample for 2.2 s (timeout 1.5 s)' |
| A7 serial to missing port (app) | **PASS** | pid_ok=True app alive=True source_status={'transport': 'serial', 'state': 'fault', 'backend': 'firmware_bridge (T4)', 'detail': "firmware_bridge exited rc=2 after 0 samples. [firmware_bridge] ERROR: [Errno 2] could not open port /dev/ttyT6_DOES_NOT_EXIST: [Errno 2] No such file or directory: '/dev/ttyT6_DOES_NOT_EXIST'", 'command': '/workspace/audit/venv_clean/bin/python -m firmware_bridge --port /dev/ttyT6_DOES_NOT_EXIST --baud 115200 --verified-devices /workspace/audit/clone_03fc993/config/verified_devices.json'} sensor_status=FAULT records=0 (no live or allowlisted samples fabricated) |
| A7b firmware_bridge --port missing | **PASS** | rc=2 stdout_lines=0 stderr="[firmware_bridge] ERROR: [Errno 2] could not open port /dev/ttyT6_DOES_NOT_EXIST: [Errno 2] No such file or directory: '/dev/ttyT6_DOES_NOT_EXIST'" |
| A8 app replay of a hardware-labelled log: badge must be REPLAY (recorded hardware), never live/allowlisted | **PASS** | pid_ok=True file sample.source=hardware -> app records=20 source=['replay'] original_source=['hardware'] transport=['replay'] live_hardware_true=0 -> badgeInfo (app's headingmath.js in Node)=['REPLAY (recorded hardware)'] |
| A9a UI render (headless Chrome, sim) | **PASS** | Google Chrome 156.0.8078.47; pid_ok=True sourceBadge='SIMULATED' headingValue='54.6° NE' gpsStatus='Unknown' warnings='NOT_CALIBRATED' |
| A9b UI render (headless Chrome, 3x field -> warning) | **PASS** | pid_ok=True fed=13 feed_errors=[] sourceBadge='REPLAY' headingValue='6.8° N' (api heading_deg=6.842) warnings='NOT_CALIBRATED / FIELD_MAGNITUDE_OUT_OF_RANGE' |
| A8b UI render of a replayed hardware-labelled log (headless Chrome) | **PASS** | pid_ok=True sourceBadge='REPLAY (recorded hardware)' evidenceBanner='[REPLAYED] Recorded hardware log played back from a file. This is recorded data, not a live sensor stream. Nothing here is hardware-verified.' transportText='transport: replay:/workspace/audit/final2_03fc993/integ/hw_labelled.jsonl · running · app file reader' |
| A10a replayed file cannot defeat the D6 relabel (case variants, original_source/transport/live tricks) | **PASS** | pid_ok=True lines=9 accepted=7 invalid=2 last_error="invalid sample: source must be one of ('sim', 'replay', 'hardware')"; records (t, source, original_source, transport, live_hardware, badge)=[(0.1, 'replay', 'hardware', 'replay', False, 'REPLAY (recorded hardware)'), (0.15000000000000002, 'replay', 'hardware', 'replay', False, 'REPLAY (recorded hardware)'), (0.2, 'replay', 'hardware', 'replay', False, 'REPLAY (recorded hardware)'), (0.25, 'replay', 'HARDWARE', 'replay', False, 'REPLAY'), (0.30000000000000004, 'replay', None, 'replay', False, 'REPLAY'), (0.35000000000000003, 'sim', 'hardware', 'replay', False, 'SIMULATED'), (0.4, 'replay', 'hardware', 'replay', False, 'REPLAY (recorded hardware)')]; violations=[] |
| A10b ingest of source=hardware (+ injected transport=serial) -> UNVERIFIED SOURCE, never live | **PASS** | pid_ok=True records=29 sample.source=['hardware'] transport=['ingest'] live_hardware_true=0 badgeInfo(Node)=['UNVERIFIED SOURCE'] DOM sourceBadge='UNVERIFIED SOURCE' evidenceBanner='[UNVERIFIED] Samples are labelled "hardware" but arrived via ingest, not a live serial source. They are not treated as live sensor data.' |
| A10h D8: shipped config/verified_devices.json exists and is empty | **PASS** | exists=True entries=[] |
| A10c D8: product fake FC on a virtual pty via serial: must be SIMULATED, never live/allowlisted/HARDWARE | **PASS** | pid_ok=True port=<virtual pty> device=firmware_bridge.fake_fc.FakeFC() (NO hardware) records=25 sample.source=['sim'] live_hardware_true=0/25 DOM sourceBadge='SIMULATED' (required 'SIMULATED') evidenceBanner='[SIMULATED] Values come from the simulator. They are not hardware measurements.' |
| A10d D8: unknown device (INAV/MKH7, UID not listed) via serial: UNVERIFIED SOURCE | **PASS** | pid_ok=True port=<virtual pty> device=T6 MSPDevice records=25 sample.source=['hardware'] live_hardware_true=0/25 DOM sourceBadge='UNVERIFIED SOURCE' (required 'UNVERIFIED SOURCE') evidenceBanner='[UNVERIFIED] Samples arrived over a serial link, but the device is not in config/verified_devices.json (UID not in the verified list). A serial connection is not proof of hardware. Board and variant are reported by device, not verified.' |
| A10e D8: unidentified device (identity queries fail) via serial: UNVERIFIED SOURCE | **PASS** | pid_ok=True port=<virtual pty> device=T6 MSPDevice identity=False records=24 sample.source=['hardware'] live_hardware_true=0/24 DOM sourceBadge='UNVERIFIED SOURCE' (required 'UNVERIFIED SOURCE') evidenceBanner='[UNVERIFIED] Samples arrived over a serial link, but the device is not in config/verified_devices.json (no device UID reported). A serial connection is not proof of hardware. Board and variant are reported by device, not verified.' |
| A10f D8/F11: virtual pty emulator INAV/MKF4 reporting an allowlisted UID (temporary allowlist copy): passes the allowlist -> badge must read exactly 'ALLOWLISTED DEVICE (identity not authenticated)' (never bare HARDWARE) with the decided banner. LIMITATION DEMONSTRATION (UID match = administrative trust, not hardware authentication); NOT hardware validation | **PASS** | pid_ok=True port=<virtual pty> uid=3654002b1147333039383101 listed; NO hardware records=25 sample.source=['hardware'] live_hardware_true=25/25 DOM sourceBadge='ALLOWLISTED DEVICE (identity not authenticated)' (required 'ALLOWLISTED DEVICE (identity not authenticated)') evidenceBanner='Live serial device whose self-reported UID is on the local allowlist. The UID is not cryptographic proof; this is not hardware verification.' |
| A10g D8: non-allowlisted UID with a non-empty allowlist via serial: UNVERIFIED SOURCE | **PASS** | pid_ok=True port=<virtual pty> uid one bit off records=24 sample.source=['hardware'] live_hardware_true=0/24 DOM sourceBadge='UNVERIFIED SOURCE' (required 'UNVERIFIED SOURCE') evidenceBanner='[UNVERIFIED] Samples arrived over a serial link, but the device is not in config/verified_devices.json (UID not in the verified list). A serial connection is not proof of hardware. Board and variant are reported by device, not verified.' |
| A10i D8: forged ingest claims (allowlisted UID + provenance verified + live_hardware) POSTed into a serial app with a non-empty allowlist: never live, never allowlisted | **PASS** | pid_ok=True posted=30 refused=30 accepted=0 refusal=['POST /api/sample is only accepted when the app runs with --source ingest'] records=50 forged_records_seen=0 device_status(forged)=[] live_hardware_true=0 device_verified_true=0 DOM sourceBadge='UNVERIFIED SOURCE' |
| A10z D8 label: no rendered sourceBadge in this run is the bare word 'HARDWARE' | **PASS** | dom_dumps_scanned=10 bare_HARDWARE=[] |

## No-pyserial run (same harness, `import serial` stubbed to fail)

| Step | Result | Summary |
|---|---|---|
| A1 sim:static -> heading_core -> app | **PASS** | pid_ok=True records=156 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.29 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:yaw_spin -> heading_core -> app | **PASS** | pid_ok=True records=150 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.31 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:tilted_spin -> heading_core -> app | **PASS** | pid_ok=True records=155 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.42 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:calibration_dance -> heading_core -> app | **PASS** | pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=13.91 deg warnings=['FIELD_MAGNITUDE_OUT_OF_RANGE', 'NOT_CALIBRATED', 'TILT_TOO_LARGE'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:hard_iron -> heading_core -> app | **PASS** | pid_ok=True records=150 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=10.75 deg warnings=['FIELD_MAGNITUDE_OUT_OF_RANGE', 'HIGH_NOISE', 'NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:soft_iron -> heading_core -> app | **PASS** | pid_ok=True records=153 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=10.56 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:motor_interference -> heading_core -> app | **PASS** | pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.32 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1 sim:high_noise -> heading_core -> app | **PASS** | pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.35 deg warnings=['HIGH_NOISE', 'NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True |
| A1b sim:motor_interference (--sim-duration 10) -> app: interference must be warned | **PASS** | pid_ok=True records=199 warnings_seen=['FIELD_MAGNITUDE_OUT_OF_RANGE', 'HIGH_NOISE'] max/err/=14.7 deg samples err>5deg=76 of which without any warning=0 |
| A2 replay sim/examples/calibration_dance_10hz_10s_seed42.jsonl | **PASS** | pid_ok=True file_lines=100 records=100 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A2 replay sim/examples/hard_iron_10hz_5s_seed42.jsonl | **PASS** | pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A2 replay sim/examples/motor_interference_10hz_5s_seed42.jsonl | **PASS** | pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A2 replay sim/examples/static_10hz_5s_seed42.jsonl | **PASS** | pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A2 replay sim/examples/yaw_spin_10hz_5s_seed42.jsonl | **PASS** | pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A2 replay sim/examples/yaw_spin_dronecan_50hz_2s_seed42.jsonl | **PASS** | pid_ok=True file_lines=100 records=100 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A2 replay sim/examples/yaw_spin_msp_50hz_2s_seed42.jsonl | **PASS** | pid_ok=True file_lines=100 records=100 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended |
| A3a fake-FC --capture -> firmware_bridge --replay | **PASS** | rc=0/0 capture_header_source=sim live=60 (source ['sim']) replayed=60 (source ['replay']) mag bit-identical=True |
| A3b capture replay -> app | **PASS** | pid_ok=True records=60 sample.source=['replay'] badge=['REPLAY'] heading[0..3]=[0.7, 2.1, 3.7] |
| A4 firmware_bridge --fake-fc | POST -> app (ingest) | **PASS** | pid_ok=True posted=100 accepted=100 rejected=[] sources=['sim'] badge=['SIMULATED'] heading range=0.2..151.7 |
| A5 calibration wizard start/stop/fit/apply/save/clear/load | **PASS** | pid_ok=True collected n=304/300 bins=9/12 octants=5/8 fit ok=True backend=heading_core offset_uT=[11.84591381228662, -8.111246721023761, 4.991328129384055] (sim truth hard-iron [12,-8,5]) / after apply: calibrated=True, RMSE vs truth last 50=0.72 deg / clear -> active=False; load -> active=True |
| A6 frozen + stale data | **PASS** | pid_ok=True 3 s identical samples -> warnings=['SENSOR_STALE', 'NOT_CALIBRATED'] quality=0.025 sensor_status=OK; then 2.2 s silence (stale 1.5 s) -> sensor_status=STALE reason='no sample for 2.2 s (timeout 1.5 s)' |
| A7 serial to missing port (app) | **PASS** | pid_ok=True app alive=True source_status={'transport': 'serial', 'state': 'fault', 'backend': 'firmware_bridge (T4)', 'detail': 'firmware_bridge exited rc=2 after 0 samples. [firmware_bridge] ERROR: pyserial is not installed; live --port mode needs it: pip install pyserial  (replay and --fake-fc work without it)', 'command': '/workspace/audit/venv_clean/bin/python -m firmware_bridge --port /dev/ttyT6_DOES_NOT_EXIST --baud 115200 --verified-devices /workspace/audit/clone_03fc993/config/verified_devices.json'} sensor_status=FAULT records=0 (no live or allowlisted samples fabricated) |
| A7b firmware_bridge --port missing | **PASS** | rc=2 stdout_lines=0 stderr='[firmware_bridge] ERROR: pyserial is not installed; live --port mode needs it: pip install pyserial  (replay and --fake-fc work without it)' |
| A8 app replay of a hardware-labelled log: badge must be REPLAY (recorded hardware), never live/allowlisted | **PASS** | pid_ok=True file sample.source=hardware -> app records=20 source=['replay'] original_source=['hardware'] transport=['replay'] live_hardware_true=0 -> badgeInfo (app's headingmath.js in Node)=['REPLAY (recorded hardware)'] |
| A9a UI render (headless Chrome, sim) | **PASS** | Google Chrome 156.0.8078.47; pid_ok=True sourceBadge='SIMULATED' headingValue='44.9° NE' gpsStatus='Unknown' warnings='NOT_CALIBRATED' |
| A9b UI render (headless Chrome, 3x field -> warning) | **PASS** | pid_ok=True fed=19 feed_errors=[] sourceBadge='REPLAY' headingValue='6.8° N' (api heading_deg=6.842) warnings='NOT_CALIBRATED / FIELD_MAGNITUDE_OUT_OF_RANGE' |
| A8b UI render of a replayed hardware-labelled log (headless Chrome) | **PASS** | pid_ok=True sourceBadge='REPLAY (recorded hardware)' evidenceBanner='[REPLAYED] Recorded hardware log played back from a file. This is recorded data, not a live sensor stream. Nothing here is hardware-verified.' transportText='transport: replay:/workspace/audit/final2_03fc993/integ_noserial/hw_labelled.jsonl · running · app file reader' |
| A10a replayed file cannot defeat the D6 relabel (case variants, original_source/transport/live tricks) | **PASS** | pid_ok=True lines=9 accepted=7 invalid=2 last_error="invalid sample: source must be one of ('sim', 'replay', 'hardware')"; records (t, source, original_source, transport, live_hardware, badge)=[(0.1, 'replay', 'hardware', 'replay', False, 'REPLAY (recorded hardware)'), (0.15000000000000002, 'replay', 'hardware', 'replay', False, 'REPLAY (recorded hardware)'), (0.2, 'replay', 'hardware', 'replay', False, 'REPLAY (recorded hardware)'), (0.25, 'replay', 'HARDWARE', 'replay', False, 'REPLAY'), (0.30000000000000004, 'replay', None, 'replay', False, 'REPLAY'), (0.35000000000000003, 'sim', 'hardware', 'replay', False, 'SIMULATED'), (0.4, 'replay', 'hardware', 'replay', False, 'REPLAY (recorded hardware)')]; violations=[] |
| A10b ingest of source=hardware (+ injected transport=serial) -> UNVERIFIED SOURCE, never live | **PASS** | pid_ok=True records=28 sample.source=['hardware'] transport=['ingest'] live_hardware_true=0 badgeInfo(Node)=['UNVERIFIED SOURCE'] DOM sourceBadge='UNVERIFIED SOURCE' evidenceBanner='[UNVERIFIED] Samples are labelled "hardware" but arrived via ingest, not a live serial source. They are not treated as live sensor data.' |
| A10h D8: shipped config/verified_devices.json exists and is empty | **PASS** | exists=True entries=[] |
| A10c D8: product fake FC on a virtual pty via serial: SIMULATED | **FAIL** | NOT RUN (counts as FAIL): pyserial or os.openpty unavailable; install pyserial (requirements.txt optional entry) |
| A10d D8: unknown device via serial: UNVERIFIED SOURCE | **FAIL** | NOT RUN (counts as FAIL): pyserial or os.openpty unavailable; install pyserial (requirements.txt optional entry) |
| A10e D8: unidentified device via serial: UNVERIFIED SOURCE | **FAIL** | NOT RUN (counts as FAIL): pyserial or os.openpty unavailable; install pyserial (requirements.txt optional entry) |
| A10f D8/F11: emulator reporting an allowlisted UID: allowlisted label (limitation demonstration) | **FAIL** | NOT RUN (counts as FAIL): pyserial or os.openpty unavailable; install pyserial (requirements.txt optional entry) |
| A10g D8: non-allowlisted UID: UNVERIFIED SOURCE | **FAIL** | NOT RUN (counts as FAIL): pyserial or os.openpty unavailable; install pyserial (requirements.txt optional entry) |
| A10i D8: forged ingest claims into a serial app with a non-empty allowlist: never live | **FAIL** | NOT RUN (counts as FAIL): pyserial or os.openpty unavailable; install pyserial (requirements.txt optional entry) |
| A10z D8 label: no rendered sourceBadge in this run is the bare word 'HARDWARE' | **PASS** | dom_dumps_scanned=4 bare_HARDWARE=[] |

## Per-step command and raw output (tail)

### A1 sim:static -> heading_core -> app: PASS

Command: `-m app --host 127.0.0.1 --port 54165 --source sim:static --rate 50 --seed 3`

```
2026-11-27 11:55:25,352 INFO root: Heading monitor UI on http://127.0.0.1:54165  (source sim:static)

```

### A1 sim:yaw_spin -> heading_core -> app: PASS

Command: `-m app --host 127.0.0.1 --port 43989 --source sim:yaw_spin --rate 50 --seed 3`

```
2026-11-27 11:55:28,721 INFO root: Heading monitor UI on http://127.0.0.1:43989  (source sim:yaw_spin)

```

### A1 sim:tilted_spin -> heading_core -> app: PASS

Command: `-m app --host 127.0.0.1 --port 55539 --source sim:tilted_spin --rate 50 --seed 3`

```
2026-11-27 11:55:32,036 INFO root: Heading monitor UI on http://127.0.0.1:55539  (source sim:tilted_spin)

```

### A1 sim:calibration_dance -> heading_core -> app: PASS

Command: `-m app --host 127.0.0.1 --port 47625 --source sim:calibration_dance --rate 50 --seed 3`

```
2026-11-27 11:55:35,353 INFO root: Heading monitor UI on http://127.0.0.1:47625  (source sim:calibration_dance)

```

### A1 sim:hard_iron -> heading_core -> app: PASS

Command: `-m app --host 127.0.0.1 --port 48753 --source sim:hard_iron --rate 50 --seed 3`

```
2026-11-27 11:55:38,723 INFO root: Heading monitor UI on http://127.0.0.1:48753  (source sim:hard_iron)

```

### A1 sim:soft_iron -> heading_core -> app: PASS

Command: `-m app --host 127.0.0.1 --port 41451 --source sim:soft_iron --rate 50 --seed 3`

```
2026-11-27 11:55:42,037 INFO root: Heading monitor UI on http://127.0.0.1:41451  (source sim:soft_iron)

```

### A1 sim:motor_interference -> heading_core -> app: PASS

Command: `-m app --host 127.0.0.1 --port 41639 --source sim:motor_interference --rate 50 --seed 3`

```
2026-11-27 11:55:45,367 INFO root: Heading monitor UI on http://127.0.0.1:41639  (source sim:motor_interference)

```

### A1 sim:high_noise -> heading_core -> app: PASS

Command: `-m app --host 127.0.0.1 --port 40321 --source sim:high_noise --rate 50 --seed 3`

```
2026-11-27 11:55:48,678 INFO root: Heading monitor UI on http://127.0.0.1:40321  (source sim:high_noise)

```

### A1b sim:motor_interference (--sim-duration 10) -> app: interference must be warned: PASS

Command: `-m app --host 127.0.0.1 --port 54617 --source sim:motor_interference --rate 20 --seed 3 --sim-duration 10 --stale 60`

```
2026-11-27 11:55:52,213 INFO root: Heading monitor UI on http://127.0.0.1:54617  (source sim:motor_interference)

```

### A2 replay sim/examples/calibration_dance_10hz_10s_seed42.jsonl: PASS

Command: `-m app --host 127.0.0.1 --port 39803 --source replay:sim/examples/calibration_dance_10hz_10s_seed42.jsonl --speed 20`

```
2026-11-27 11:56:02,403 INFO root: Heading monitor UI on http://127.0.0.1:39803  (source replay:/workspace/audit/clone_03fc993/sim/examples/calibration_dance_10hz_10s_seed42.jsonl)

```

### A2 replay sim/examples/hard_iron_10hz_5s_seed42.jsonl: PASS

Command: `-m app --host 127.0.0.1 --port 51451 --source replay:sim/examples/hard_iron_10hz_5s_seed42.jsonl --speed 20`

```
2026-11-27 11:56:03,154 INFO root: Heading monitor UI on http://127.0.0.1:51451  (source replay:/workspace/audit/clone_03fc993/sim/examples/hard_iron_10hz_5s_seed42.jsonl)

```

### A2 replay sim/examples/motor_interference_10hz_5s_seed42.jsonl: PASS

Command: `-m app --host 127.0.0.1 --port 33619 --source replay:sim/examples/motor_interference_10hz_5s_seed42.jsonl --speed 20`

```
2026-11-27 11:56:03,681 INFO root: Heading monitor UI on http://127.0.0.1:33619  (source replay:/workspace/audit/clone_03fc993/sim/examples/motor_interference_10hz_5s_seed42.jsonl)

```

### A2 replay sim/examples/static_10hz_5s_seed42.jsonl: PASS

Command: `-m app --host 127.0.0.1 --port 46949 --source replay:sim/examples/static_10hz_5s_seed42.jsonl --speed 20`

```
2026-11-27 11:56:04,179 INFO root: Heading monitor UI on http://127.0.0.1:46949  (source replay:/workspace/audit/clone_03fc993/sim/examples/static_10hz_5s_seed42.jsonl)

```

### A2 replay sim/examples/yaw_spin_10hz_5s_seed42.jsonl: PASS

Command: `-m app --host 127.0.0.1 --port 58669 --source replay:sim/examples/yaw_spin_10hz_5s_seed42.jsonl --speed 20`

```
2026-11-27 11:56:04,687 INFO root: Heading monitor UI on http://127.0.0.1:58669  (source replay:/workspace/audit/clone_03fc993/sim/examples/yaw_spin_10hz_5s_seed42.jsonl)

```

### A2 replay sim/examples/yaw_spin_dronecan_50hz_2s_seed42.jsonl: PASS

Command: `-m app --host 127.0.0.1 --port 46781 --source replay:sim/examples/yaw_spin_dronecan_50hz_2s_seed42.jsonl --speed 20`

```
2026-11-27 11:56:05,193 INFO root: Heading monitor UI on http://127.0.0.1:46781  (source replay:/workspace/audit/clone_03fc993/sim/examples/yaw_spin_dronecan_50hz_2s_seed42.jsonl)

```

### A2 replay sim/examples/yaw_spin_msp_50hz_2s_seed42.jsonl: PASS

Command: `-m app --host 127.0.0.1 --port 46945 --source replay:sim/examples/yaw_spin_msp_50hz_2s_seed42.jsonl --speed 20`

```
2026-11-27 11:56:05,711 INFO root: Heading monitor UI on http://127.0.0.1:46945  (source replay:/workspace/audit/clone_03fc993/sim/examples/yaw_spin_msp_50hz_2s_seed42.jsonl)

```

### A3a fake-FC --capture -> firmware_bridge --replay: PASS

Command: `python -m firmware_bridge --fake-fc --count 60 --capture fake_capture.jsonl --out fake_samples.jsonl ; python -m firmware_bridge --replay fake_capture.jsonl --out capture_replayed.jsonl`

```
[firmware_bridge] device identity (self-reported): variant='SIML' board='SIMF' uid='a0a1a2a3a4a5a6a7a8a9aaab' -> source=sim provenance=simulated (simulated transport (fake FC))
[firmware_bridge] FC mag calibration: fc_mag_calibrated=False

```

### A3b capture replay -> app: PASS

Command: `-m app --host 127.0.0.1 --port 49021 --source replay:<out>/capture_replayed.jsonl --speed 20`

```
2026-11-27 11:56:06,315 INFO root: Heading monitor UI on http://127.0.0.1:49021  (source replay:/workspace/audit/final2_03fc993/integ/capture_replayed.jsonl)

```

### A4 firmware_bridge --fake-fc | POST -> app (ingest): PASS

Command: `python -m firmware_bridge --fake-fc --count 100 | POST each line to /api/sample ; -m app --host 127.0.0.1 --port 51963 --source ingest --stale 30`

```
2026-11-27 11:56:06,838 INFO root: Heading monitor UI on http://127.0.0.1:51963  (source ingest)

```

### A5 calibration wizard start/stop/fit/apply/save/clear/load: PASS

Command: `-m app --host 127.0.0.1 --port 34631 --source sim:calibration_dance --rate 50 --seed 5`

```
[["start", {"ok": true}], ["stop", {"ok": true}], ["fit", {"ok": true, "backend": "heading_core", "error": null}], ["apply", {"ok": true}], ["save", {"ok": true, "file": "t6_audit_cal.json"}], ["list", {"files": ["t6_audit_cal.json"]}], ["load", {"ok": true}]]
2026-11-27 11:56:07,223 INFO root: Heading monitor UI on http://127.0.0.1:34631  (source sim:calibration_dance)

```

### A6 frozen + stale data: PASS

Command: `-m app --host 127.0.0.1 --port 60883 --source ingest --stale 1.5 ; POST 60 identical samples, then silence`

```
2026-11-27 11:56:16,274 INFO root: Heading monitor UI on http://127.0.0.1:60883  (source ingest)

```

### A7 serial to missing port (app): PASS

Command: `-m app --host 127.0.0.1 --port 56927 --source serial:/dev/ttyT6_DOES_NOT_EXIST`

```
2026-11-27 11:56:18,856 INFO root: Heading monitor UI on http://127.0.0.1:56927  (source serial:/dev/ttyT6_DOES_NOT_EXIST)

```

### A7b firmware_bridge --port missing: PASS

Command: `python -m firmware_bridge --port /dev/ttyT6_DOES_NOT_EXIST`

```
[firmware_bridge] ERROR: [Errno 2] could not open port /dev/ttyT6_DOES_NOT_EXIST: [Errno 2] No such file or directory: '/dev/ttyT6_DOES_NOT_EXIST'

```

### A8 app replay of a hardware-labelled log: badge must be REPLAY (recorded hardware), never live/allowlisted: PASS

Command: `-m app --host 127.0.0.1 --port 38387 --source replay:<out>/hw_labelled.jsonl --speed 20`

```
2026-11-27 11:56:22,158 INFO root: Heading monitor UI on http://127.0.0.1:38387  (source replay:/workspace/audit/final2_03fc993/integ/hw_labelled.jsonl)

```

### A9a UI render (headless Chrome, sim): PASS

Command: `-m app --host 127.0.0.1 --port 45245 --source sim:yaw_spin --stale 60 ; google-chrome --headless=new --dump-dom http://127.0.0.1:<port>/`

```
2026-11-27 11:56:22,487 INFO root: Heading monitor UI on http://127.0.0.1:45245  (source sim:yaw_spin)

```

### A9b UI render (headless Chrome, 3x field -> warning): PASS

Command: `-m app --host 127.0.0.1 --port 57977 --source ingest --stale 600 ; POST |B|~150 uT samples at 20 Hz continuously during render ; dump-dom`

```
2026-11-27 11:56:25,951 INFO root: Heading monitor UI on http://127.0.0.1:57977  (source ingest)

```

### A8b UI render of a replayed hardware-labelled log (headless Chrome): PASS

Command: `-m app --host 127.0.0.1 --port 43701 --source replay:<out>/hw_labelled.jsonl --speed 1 --loop --stale 60 ; dump-dom`

```
2026-11-27 11:56:26,883 INFO root: Heading monitor UI on http://127.0.0.1:43701  (source replay:/workspace/audit/final2_03fc993/integ/hw_labelled.jsonl)

```

### A10a replayed file cannot defeat the D6 relabel (case variants, original_source/transport/live tricks): PASS

Command: `-m app --host 127.0.0.1 --port 44337 --source replay:<out>/replay_tricks.jsonl --speed 20`

```
variants: ["upper-case HARDWARE", "title-case Hardware", "hardware + meta.original_source=sim", "replay + original_source=hardware + top-level transport=serial, live_hardware=true", "hardware + top-level transport=serial, live_hardware=true", "replay + meta.original_source=HARDWARE", "replay + meta.original_source=object", "sim + meta.original_source=hardware", "hardware + meta.replayed_from spoof"]
2026-11-27 11:56:28,147 INFO root: Heading monitor UI on http://127.0.0.1:44337  (source replay:/workspace/audit/final2_03fc993/integ/replay_tricks.jsonl)

```

### A10b ingest of source=hardware (+ injected transport=serial) -> UNVERIFIED SOURCE, never live: PASS

Command: `-m app --host 127.0.0.1 --port 57671 --source ingest --stale 600 ; POST hardware samples ; dump-dom`

```
2026-11-27 11:56:28,382 INFO root: Heading monitor UI on http://127.0.0.1:57671  (source ingest)

```

### A10h D8: shipped config/verified_devices.json exists and is empty: PASS

Command: `cat config/verified_devices.json`

```
{"_comment": "D8 (ARCHITECTURE.md 2026-11-27): the ONLY path to provenance 'verified' / the HARDWARE badge. Ships EMPTY. Add an entry only after reports/HARDWARE_VALIDATION_CHECKLIST.md passes with the Auditor's sign-off and a committed hardware log. uid = 24 hex chars = the 12 MSP_UID (160) payload bytes in wire order. A device reporting fc_variant SIML or board SIMF is never verified, even if listed. A UID is self-reported and not cryptographic proof.", "devices": []}
```

### A10c D8: product fake FC on a virtual pty via serial: must be SIMULATED, never live/allowlisted/HARDWARE: PASS

Command: `-m app --host 127.0.0.1 --port 41533 --source serial:<pty> --stale 60`

```
2026-11-27 11:56:30,203 INFO root: Heading monitor UI on http://127.0.0.1:41533  (source serial:/dev/pts/0)

```

### A10d D8: unknown device (INAV/MKH7, UID not listed) via serial: UNVERIFIED SOURCE: PASS

Command: `-m app --host 127.0.0.1 --port 55851 --source serial:<pty> --stale 60`

```
2026-11-27 11:56:31,602 INFO root: Heading monitor UI on http://127.0.0.1:55851  (source serial:/dev/pts/2)

```

### A10e D8: unidentified device (identity queries fail) via serial: UNVERIFIED SOURCE: PASS

Command: `-m app --host 127.0.0.1 --port 42695 --source serial:<pty> --stale 60`

```
2026-11-27 11:56:33,006 INFO root: Heading monitor UI on http://127.0.0.1:42695  (source serial:/dev/pts/1)

```

### A10f D8/F11: virtual pty emulator INAV/MKF4 reporting an allowlisted UID (temporary allowlist copy): passes the allowlist -> badge must read exactly 'ALLOWLISTED DEVICE (identity not authenticated)' (never bare HARDWARE) with the decided banner. LIMITATION DEMONSTRATION (UID match = administrative trust, not hardware authentication); NOT hardware validation: PASS

Command: `-m app --host 127.0.0.1 --port 38879 --source serial:<pty> --stale 60`

```
2026-11-27 11:56:34,697 INFO root: Heading monitor UI on http://127.0.0.1:38879  (source serial:/dev/pts/1)

```

### A10g D8: non-allowlisted UID with a non-empty allowlist via serial: UNVERIFIED SOURCE: PASS

Command: `-m app --host 127.0.0.1 --port 37125 --source serial:<pty> --stale 60`

```
2026-11-27 11:56:36,124 INFO root: Heading monitor UI on http://127.0.0.1:37125  (source serial:/dev/pts/1)

```

### A10i D8: forged ingest claims (allowlisted UID + provenance verified + live_hardware) POSTed into a serial app with a non-empty allowlist: never live, never allowlisted: PASS

Command: `-m app --host 127.0.0.1 --port 60317 --source serial:<pty> --stale 60 ; POST forged samples`

```
2026-11-27 11:56:37,499 INFO root: Heading monitor UI on http://127.0.0.1:60317  (source serial:/dev/pts/2)

```

### A10z D8 label: no rendered sourceBadge in this run is the bare word 'HARDWARE': PASS

Command: `scan ui_dom_*.html`

```

```
