# Integration results (T6, end-to-end) [SIMULATED] / [REPLAYED]

Run by T6 (Testing & Technical Auditor) on 2026-11-27 at about 01:17 IST: the **D6 re-test, a full re-run of every A step**.
**Code under test: `git archive f058c9a` export.** It is clean and contains the D6 fix 0ca6b0f, the PM decisions eacf8a2 and c831574, and 1e37a34. The only later commit, `0c25062` (HEAD, "[pm] status sync"), changes PROJECT_STATUS.md only (`git diff --stat f058c9a 0c25062`). The full test suite was run on `0c25062` itself (TEST_RESULTS.md).
Harness: `reports/audit/integration_run.py` (T6). Command:
```
cd <clean export> && /workspace/audit/venv_clean/bin/python <repo>/reports/audit/integration_run.py <clean export> <out>
```
Environment: Linux box, Python 3.13.5, numpy 2.5.5, pytest 9.2.0, jsonschema 4.26.0, pyserial; Google Chrome 156 (headless=new, --dump-dom); Node (runs the app's own `headingmath.js` `badgeInfo`).

How every app step works: the harness starts a **fresh** `python -m app --host 127.0.0.1 --port <free ephemeral port>`. It then checks with `ss -ltnpH "sport = :PORT"` that the listening PID is the PID it launched (`pid_ok`). It talks only to that instance, and on close checks that the port is released. It never uses the UI developer's :8080 instance.
Raw machine output: `reports/audit/raw/integration_results.json` (command + summary + app output per step), `raw/integration_run_stdout.log`, DOM dumps `raw/ui_dom_*.html`.

## Summary: 30 / 30 PASS

History: at 471724e the result was 25/27 (A8 and A8b FAIL → D6 CRITICAL). After fix 0ca6b0f, A8 and A8b pass. The A8 and A8b criteria were also **tightened**. A8 now requires source=replay, meta.original_source=hardware, no live flag, and the app's own badgeInfo = "REPLAY (recorded hardware)". A8b requires that exact DOM badge and a "not a live" banner. Three D6 edge-case steps (A10a–c) were added.

| Step | What | Result |
|---|---|---|
| A1 | sim:static -> heading_core -> app | **PASS** |
| A1 | sim:yaw_spin -> heading_core -> app | **PASS** |
| A1 | sim:tilted_spin -> heading_core -> app | **PASS** |
| A1 | sim:calibration_dance -> heading_core -> app | **PASS** |
| A1 | sim:hard_iron -> heading_core -> app | **PASS** |
| A1 | sim:soft_iron -> heading_core -> app | **PASS** |
| A1 | sim:motor_interference -> heading_core -> app | **PASS** |
| A1 | sim:high_noise -> heading_core -> app | **PASS** |
| A1b | sim:motor_interference (--sim-duration 10) -> app: interference must be warned | **PASS** |
| A2 | replay sim/examples/calibration_dance_10hz_10s_seed42.jsonl | **PASS** |
| A2 | replay sim/examples/hard_iron_10hz_5s_seed42.jsonl | **PASS** |
| A2 | replay sim/examples/motor_interference_10hz_5s_seed42.jsonl | **PASS** |
| A2 | replay sim/examples/static_10hz_5s_seed42.jsonl | **PASS** |
| A2 | replay sim/examples/yaw_spin_10hz_5s_seed42.jsonl | **PASS** |
| A2 | replay sim/examples/yaw_spin_dronecan_50hz_2s_seed42.jsonl | **PASS** |
| A2 | replay sim/examples/yaw_spin_msp_50hz_2s_seed42.jsonl | **PASS** |
| A3a | fake-FC --capture -> firmware_bridge --replay | **PASS** |
| A3b | capture replay -> app | **PASS** |
| A4 | firmware_bridge --fake-fc | POST -> app (ingest) | **PASS** |
| A5 | calibration wizard start/stop/fit/apply/save/clear/load | **PASS** |
| A6 | frozen + stale data | **PASS** |
| A7 | serial to missing port (app) | **PASS** |
| A7b | firmware_bridge --port missing | **PASS** |
| A8 | app replay of a hardware-labelled log: badge must not read HARDWARE | **PASS** |
| A9a | UI render (headless Chrome, sim) | **PASS** |
| A9b | UI render (headless Chrome, 3x field -> warning) | **PASS** |
| A8b | UI render of a replayed hardware-labelled log (headless Chrome) | **PASS** |
| A10a | replayed file cannot defeat the D6 relabel (case variants, original_source/transport/live tricks) | **PASS** |
| A10b | ingest of source=hardware (+ injected transport=serial) -> UNVERIFIED SOURCE, never live | **PASS** |
| A10c | serial transport over a virtual pty (fake FC): HARDWARE only via serial (observation L-SER) | **PASS** |

Notes on interpretation:
- A1 RMSE is for the **uncalibrated** app. The hard-iron, soft-iron and calibration_dance scenarios are therefore ~10-14° off; A5 gives 0.72° after the wizard calibration.
- A1b re-runs motor_interference with `--sim-duration 10` so the current profile actually plays: every sample with >5° error carried a warning.
- **A10a (relabel cannot be defeated):** nine crafted lines were replayed.
  - "HARDWARE" and "Hardware" are rejected by the schema enum (invalid = 2).
  - `hardware` with `meta.original_source` = sim or replay is relabelled with original_source forced to `hardware`.
  - A top-level `transport: "serial"` and `live_hardware: true` in a file are ignored; the app derives `transport` from its own `--source`.
  - `replay` + `original_source: "HARDWARE"` or an object gives plain REPLAY.
  - No record reached source=hardware, the live flag, HARDWARE or UNVERIFIED SOURCE.
  - Accepted limitation (PM c831574): a file may claim `source:"replay", meta.original_source:"hardware"` and is then shown as "REPLAY (recorded hardware)". This is still a non-live label.
- **A10b (ingest):** POSTed `hardware` samples, even with injected `transport:"serial"` and `live_hardware:true`, keep `sample.source="hardware"`. Transport is `ingest`, the live flag is 0, the DOM badge reads **UNVERIFIED SOURCE**, and the banner starts "[UNVERIFIED] … not a live serial source".
- **A10c (observation → limitation L-SER):** a *virtual* pty driven by `firmware_bridge`'s FakeFC (no device at all) and opened via `--source serial:<pty>` is shown as **HARDWARE** with the banner "Live hardware samples (serial)". The serial transport cannot tell a virtual port from a real flight controller. This matches the contract ("hardware only from a live port") and needs a deliberate set-up, so T6 records it as a limitation, not a defect. The step "passes" only in the sense that HARDWARE is reachable **only** through the serial transport. Nothing from it is a hardware result.
- A9b fixes in the T6 harness (continuous feeding during render; full warnings-list parsing) date from the previous run; nothing was forced to pass.

## Per-step command, raw output and result
### A1 sim:static -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 60017 --source sim:static --rate 50 --seed 3`

Result: pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.29 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 01:15:54,184 INFO root: Heading monitor UI on http://127.0.0.1:60017  (source sim:static)
```

### A1 sim:yaw_spin -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 55179 --source sim:yaw_spin --rate 50 --seed 3`

Result: pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.32 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 01:15:57,488 INFO root: Heading monitor UI on http://127.0.0.1:55179  (source sim:yaw_spin)
```

### A1 sim:tilted_spin -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 45259 --source sim:tilted_spin --rate 50 --seed 3`

Result: pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.41 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 01:16:00,808 INFO root: Heading monitor UI on http://127.0.0.1:45259  (source sim:tilted_spin)
```

### A1 sim:calibration_dance -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 40685 --source sim:calibration_dance --rate 50 --seed 3`

Result: pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=13.91 deg warnings=['FIELD_MAGNITUDE_OUT_OF_RANGE', 'NOT_CALIBRATED', 'TILT_TOO_LARGE'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 01:16:04,121 INFO root: Heading monitor UI on http://127.0.0.1:40685  (source sim:calibration_dance)
```

### A1 sim:hard_iron -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 49893 --source sim:hard_iron --rate 50 --seed 3`

Result: pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=10.57 deg warnings=['FIELD_MAGNITUDE_OUT_OF_RANGE', 'HIGH_NOISE', 'NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 01:16:07,421 INFO root: Heading monitor UI on http://127.0.0.1:49893  (source sim:hard_iron)
```

### A1 sim:soft_iron -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 40711 --source sim:soft_iron --rate 50 --seed 3`

Result: pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=10.56 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 01:16:10,749 INFO root: Heading monitor UI on http://127.0.0.1:40711  (source sim:soft_iron)
```

### A1 sim:motor_interference -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 60359 --source sim:motor_interference --rate 50 --seed 3`

Result: pid_ok=True records=155 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.32 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 01:16:14,076 INFO root: Heading monitor UI on http://127.0.0.1:60359  (source sim:motor_interference)
```

### A1 sim:high_noise -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 42453 --source sim:high_noise --rate 50 --seed 3`

Result: pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.35 deg warnings=['HIGH_NOISE', 'NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 01:16:17,386 INFO root: Heading monitor UI on http://127.0.0.1:42453  (source sim:high_noise)
```

### A1b sim:motor_interference (--sim-duration 10) -> app: interference must be warned — **PASS**

Command: `-m app --host 127.0.0.1 --port 56921 --source sim:motor_interference --rate 20 --seed 3 --sim-duration 10 --stale 60`

Result: pid_ok=True records=199 warnings_seen=['FIELD_MAGNITUDE_OUT_OF_RANGE', 'HIGH_NOISE'] max|err|=14.7 deg samples err>5deg=76 of which without any warning=0

Raw process output (last lines):
```
2026-11-27 01:16:20,818 INFO root: Heading monitor UI on http://127.0.0.1:56921  (source sim:motor_interference)
```

### A2 replay sim/examples/calibration_dance_10hz_10s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 37697 --source replay:sim/examples/calibration_dance_10hz_10s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=100 records=100 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 01:16:30,963 INFO root: Heading monitor UI on http://127.0.0.1:37697  (source replay:<export>/sim/examples/calibration_dance_10hz_10s_seed42.jsonl)
```

### A2 replay sim/examples/hard_iron_10hz_5s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 46849 --source replay:sim/examples/hard_iron_10hz_5s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 01:16:31,744 INFO root: Heading monitor UI on http://127.0.0.1:46849  (source replay:<export>/sim/examples/hard_iron_10hz_5s_seed42.jsonl)
```

### A2 replay sim/examples/motor_interference_10hz_5s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 33909 --source replay:sim/examples/motor_interference_10hz_5s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 01:16:32,255 INFO root: Heading monitor UI on http://127.0.0.1:33909  (source replay:<export>/sim/examples/motor_interference_10hz_5s_seed42.jsonl)
```

### A2 replay sim/examples/static_10hz_5s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 42591 --source replay:sim/examples/static_10hz_5s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 01:16:32,781 INFO root: Heading monitor UI on http://127.0.0.1:42591  (source replay:<export>/sim/examples/static_10hz_5s_seed42.jsonl)
```

### A2 replay sim/examples/yaw_spin_10hz_5s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 46747 --source replay:sim/examples/yaw_spin_10hz_5s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 01:16:33,283 INFO root: Heading monitor UI on http://127.0.0.1:46747  (source replay:<export>/sim/examples/yaw_spin_10hz_5s_seed42.jsonl)
```

### A2 replay sim/examples/yaw_spin_dronecan_50hz_2s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 54013 --source replay:sim/examples/yaw_spin_dronecan_50hz_2s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=100 records=100 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 01:16:33,802 INFO root: Heading monitor UI on http://127.0.0.1:54013  (source replay:<export>/sim/examples/yaw_spin_dronecan_50hz_2s_seed42.jsonl)
```

### A2 replay sim/examples/yaw_spin_msp_50hz_2s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 49245 --source replay:sim/examples/yaw_spin_msp_50hz_2s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=100 records=100 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 01:16:34,078 INFO root: Heading monitor UI on http://127.0.0.1:49245  (source replay:<export>/sim/examples/yaw_spin_msp_50hz_2s_seed42.jsonl)
```

### A3a fake-FC --capture -> firmware_bridge --replay — **PASS**

Command: `python -m firmware_bridge --fake-fc --count 60 --capture fake_capture.jsonl --out fake_samples.jsonl ; python -m firmware_bridge --replay fake_capture.jsonl --out capture_replayed.jsonl`

Result: rc=0/0 capture_header_source=sim live=60 (source ['sim']) replayed=60 (source ['replay']) mag bit-identical=True

Raw process output (last lines):
```
[firmware_bridge] FC variant: INAV
[firmware_bridge] FC mag calibration: fc_mag_calibrated=False
```

### A3b capture replay -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 39157 --source replay:<out>/capture_replayed.jsonl --speed 20`

Result: pid_ok=True records=60 sample.source=['replay'] badge=['REPLAY'] heading[0..3]=[0.5, 1.9, 3.4]

Raw process output (last lines):
```
2026-11-27 01:16:34,420 INFO root: Heading monitor UI on http://127.0.0.1:39157  (source replay:<out>/capture_replayed.jsonl)
```

### A4 firmware_bridge --fake-fc | POST -> app (ingest) — **PASS**

Command: `python -m firmware_bridge --fake-fc --count 100 | POST each line to /api/sample ; -m app --host 127.0.0.1 --port 37309 --source ingest --stale 30`

Result: pid_ok=True posted=100 accepted=100 rejected=[] sources=['sim'] badge=['SIMULATED'] heading range=0.2..151.6

Raw process output (last lines):
```
2026-11-27 01:16:34,948 INFO root: Heading monitor UI on http://127.0.0.1:37309  (source ingest)
```

### A5 calibration wizard start/stop/fit/apply/save/clear/load — **PASS**

Command: `-m app --host 127.0.0.1 --port 60147 --source sim:calibration_dance --rate 50 --seed 5`

Result: pid_ok=True collected n=304/300 bins=9/12 octants=5/8 fit ok=True backend=heading_core offset_uT=[11.84591381228662, -8.111246721023761, 4.991328129384055] (sim truth hard-iron [12,-8,5]) | after apply: calibrated=True, RMSE vs truth last 50=0.72 deg | clear -> active=False; load -> active=True

Raw process output (last lines):
```
[["start", {"ok": true}], ["stop", {"ok": true}], ["fit", {"ok": true, "backend": "heading_core", "error": null}], ["apply", {"ok": true}], ["save", {"ok": true, "file": "t6_audit_cal.json"}], ["list", {"files": ["t6_audit_cal.json"]}], ["load", {"ok": true}]]
2026-11-27 01:16:35,354 INFO root: Heading monitor UI on http://127.0.0.1:60147  (source sim:calibration_dance)
```

### A6 frozen + stale data — **PASS**

Command: `-m app --host 127.0.0.1 --port 33673 --source ingest --stale 1.5 ; POST 60 identical samples, then silence`

Result: pid_ok=True 3 s identical samples -> warnings=['SENSOR_STALE', 'NOT_CALIBRATED'] quality=0.025 sensor_status=OK; then 2.2 s silence (stale 1.5 s) -> sensor_status=STALE reason='no sample for 2.2 s (timeout 1.5 s)'

Raw process output (last lines):
```
2026-11-27 01:16:44,420 INFO root: Heading monitor UI on http://127.0.0.1:33673  (source ingest)
```

### A7 serial to missing port (app) — **PASS**

Command: `-m app --host 127.0.0.1 --port 35497 --source serial:/dev/ttyT6_DOES_NOT_EXIST`

Result: pid_ok=True app alive=True source_status={'transport': 'serial', 'state': 'fault', 'backend': 'firmware_bridge (T4)', 'detail': "firmware_bridge exited rc=2 after 0 samples. [firmware_bridge] ERROR: [Errno 2] could not open port /dev/ttyT6_DOES_NOT_EXIST: [Errno 2] No such file or directory: '/dev/ttyT6_DOES_NOT_EXIST'"} sensor_status=FAULT records=0 (no HARDWARE samples fabricated)

Raw process output (last lines):
```
2026-11-27 01:16:46,945 INFO root: Heading monitor UI on http://127.0.0.1:35497  (source serial:/dev/ttyT6_DOES_NOT_EXIST)
```

### A7b firmware_bridge --port missing — **PASS**

Command: `python -m firmware_bridge --port /dev/ttyT6_DOES_NOT_EXIST`

Result: rc=2 stdout_lines=0 stderr="[firmware_bridge] ERROR: [Errno 2] could not open port /dev/ttyT6_DOES_NOT_EXIST: [Errno 2] No such file or directory: '/dev/ttyT6_DOES_NOT_EXIST'"

Raw process output (last lines):
```
[firmware_bridge] ERROR: [Errno 2] could not open port /dev/ttyT6_DOES_NOT_EXIST: [Errno 2] No such file or directory: '/dev/ttyT6_DOES_NOT_EXIST'
```

### A8 app replay of a hardware-labelled log: badge must not read HARDWARE — **PASS**

Command: `-m app --host 127.0.0.1 --port 57307 --source replay:<out>/hw_labelled.jsonl --speed 20`

Result: pid_ok=True file sample.source=hardware -> app records=20 source=['replay'] original_source=['hardware'] transport=['replay'] live_hardware_true=0 -> badgeInfo (app's headingmath.js in Node)=['REPLAY (recorded hardware)']

Raw process output (last lines):
```
2026-11-27 01:16:50,268 INFO root: Heading monitor UI on http://127.0.0.1:57307  (source replay:<out>/hw_labelled.jsonl)
```

### A9a UI render (headless Chrome, sim) — **PASS**

Command: `-m app --host 127.0.0.1 --port 37219 --source sim:yaw_spin --stale 60 ; google-chrome --headless=new --dump-dom http://127.0.0.1:<port>/`

Result: Google Chrome 156.0.8078.47; pid_ok=True sourceBadge='SIMULATED' headingValue='29.0° NNE' gpsStatus='Unknown' warnings='NOT_CALIBRATED'

Raw process output (last lines):
```
2026-11-27 01:16:50,608 INFO root: Heading monitor UI on http://127.0.0.1:37219  (source sim:yaw_spin)
```

### A9b UI render (headless Chrome, 3x field -> warning) — **PASS**

Command: `-m app --host 127.0.0.1 --port 34013 --source ingest --stale 600 ; POST |B|~150 uT samples at 20 Hz continuously during render ; dump-dom`

Result: pid_ok=True fed=14 feed_errors=[] sourceBadge='REPLAY' headingValue='6.8° N' (api heading_deg=6.842) warnings='NOT_CALIBRATED | FIELD_MAGNITUDE_OUT_OF_RANGE'

Raw process output (last lines):
```
2026-11-27 01:16:52,657 INFO root: Heading monitor UI on http://127.0.0.1:34013  (source ingest)
```

### A8b UI render of a replayed hardware-labelled log (headless Chrome) — **PASS**

Command: `-m app --host 127.0.0.1 --port 40527 --source replay:<out>/hw_labelled.jsonl --speed 1 --loop --stale 60 ; dump-dom`

Result: pid_ok=True sourceBadge='REPLAY (recorded hardware)' evidenceBanner='[REPLAYED] Recorded hardware log played back from a file. This is recorded data, not a live sensor stream. Nothing here is hardware-verified.' transportText='transport: replay:<out>/hw_labelled.jsonl · running · app file reader'

Raw process output (last lines):
```
2026-11-27 01:16:53,626 INFO root: Heading monitor UI on http://127.0.0.1:40527  (source replay:<out>/hw_labelled.jsonl)
```

### A10a replayed file cannot defeat the D6 relabel (case variants, original_source/transport/live tricks) — **PASS**

Command: `-m app --host 127.0.0.1 --port 36365 --source replay:<out>/replay_tricks.jsonl --speed 20`

Result: pid_ok=True lines=9 accepted=7 invalid=2 last_error="invalid sample: source must be one of ('sim', 'replay', 'hardware')"; records (t, source, original_source, transport, live_hardware, badge)=[(0.1, 'replay', 'hardware', 'replay', False, 'REPLAY (recorded hardware)'), (0.15000000000000002, 'replay', 'hardware', 'replay', False, 'REPLAY (recorded hardware)'), (0.2, 'replay', 'hardware', 'replay', False, 'REPLAY (recorded hardware)'), (0.25, 'replay', 'HARDWARE', 'replay', False, 'REPLAY'), (0.30000000000000004, 'replay', None, 'replay', False, 'REPLAY'), (0.35000000000000003, 'sim', 'hardware', 'replay', False, 'SIMULATED'), (0.4, 'replay', 'hardware', 'replay', False, 'REPLAY (recorded hardware)')]; violations=[]

Raw process output (last lines):
```
variants: ["upper-case HARDWARE", "title-case Hardware", "hardware + meta.original_source=sim", "replay + original_source=hardware + top-level transport=serial, live_hardware=true", "hardware + top-level transport=serial, live_hardware=true", "replay + meta.original_source=HARDWARE", "replay + meta.original_source=object", "sim + meta.original_source=hardware", "hardware + meta.replayed_from spoof"]
2026-11-27 01:16:54,850 INFO root: Heading monitor UI on http://127.0.0.1:36365  (source replay:<out>/replay_tricks.jsonl)
```

### A10b ingest of source=hardware (+ injected transport=serial) -> UNVERIFIED SOURCE, never live — **PASS**

Command: `-m app --host 127.0.0.1 --port 52913 --source ingest --stale 600 ; POST hardware samples ; dump-dom`

Result: pid_ok=True records=28 sample.source=['hardware'] transport=['ingest'] live_hardware_true=0 badgeInfo(Node)=['UNVERIFIED SOURCE'] DOM sourceBadge='UNVERIFIED SOURCE' evidenceBanner='[UNVERIFIED] Samples are labelled "hardware" but arrived via ingest, not a live serial source. They are not treated as live sensor data.'

Raw process output (last lines):
```
2026-11-27 01:16:55,145 INFO root: Heading monitor UI on http://127.0.0.1:52913  (source ingest)
```

### A10c serial transport over a virtual pty (fake FC): HARDWARE only via serial (observation L-SER) — **PASS**

Command: `-m app --host 127.0.0.1 --port 46671 --source serial:<pty> --stale 60`

Result: pid_ok=True port=/dev/pts/0 (virtual pty + firmware_bridge FakeFC, NO device) records=26 source=['hardware'] live_hardware_true=26/26 source_status=running DOM sourceBadge='HARDWARE' evidenceBanner='Live hardware samples (serial). Accuracy is not hardware-verified until the auditor signs off a committed log.' => OBSERVATION: a virtual serial port is shown as live HARDWARE (limitation L-SER, not a pass of hardware accuracy)

Raw process output (last lines):
```
2026-11-27 01:16:56,916 INFO root: Heading monitor UI on http://127.0.0.1:46671  (source serial:/dev/pts/0)
```

