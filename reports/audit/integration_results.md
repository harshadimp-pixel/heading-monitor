# Integration results (T6, end-to-end) [SIMULATED] / [REPLAYED]

Run by T6 (Testing & Technical Auditor) on 2026-11-27 at about 00:55 IST.
**Code under test: `git archive 471724e` export** (clean, with no uncommitted work from other owners). The later commits `ed3961c` and `dc3123a` change only docs and screenshots (`git diff --stat 471724e dc3123a`: INSTALL.md, app/README.md, TEAM_TRACKER.md, reports/contributions/*, png), so these results stand for HEAD `dc3123a`.
Harness: `reports/audit/integration_run.py` (T6). Command:
```
cd <clean export> && /workspace/audit/venv_clean/bin/python <repo>/reports/audit/integration_run.py <clean export> <out>
```
Environment: Linux box, Python 3.13.5, numpy 2.5.5, pytest 9.2.0, jsonschema 4.26.0, pyserial; Google Chrome 156 (headless=new, --dump-dom); Node for nothing here.

How every app step works: the harness starts a **fresh** `python -m app --host 127.0.0.1 --port <free ephemeral port>`. It then checks with `ss -ltnpH "sport = :PORT"` that the listening PID is the PID it launched (`pid_ok`). It talks only to that instance, and on close checks that the port is released. It never uses the UI developer's :8080 instance.
Raw machine output: `reports/audit/raw/integration_results.json` (command + summary + app stdout/stderr per step), `raw/integration_run_stdout.log`, DOM dumps `raw/ui_dom_*.html`.

## Summary: 25 / 27 PASS, 2 FAIL (A8, A8b → defect D6, CRITICAL)

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
| A8 | app replay of a hardware-labelled log: badge must not read HARDWARE | **FAIL** |
| A9a | UI render (headless Chrome, sim) | **PASS** |
| A9b | UI render (headless Chrome, 3x field -> warning) | **PASS** |
| A8b | UI render of a replayed hardware-labelled log (headless Chrome) | **FAIL** |

Notes on interpretation:
- A1 RMSE is for the **uncalibrated** app (no calibration loaded), measured after the first second. Scenarios with injected hard/soft iron (calibration_dance, hard_iron, soft_iron) are therefore ~10-14° off. This is expected and is why the calibration wizard exists; A5 shows 0.72° after the wizard calibration. Calibrated accuracy per scenario is in verification_report.md §3 (A1/R2).
- A1 `motor_interference` with the app default `--sim-duration 86400` stretches the motor-current profile over 24 h, so no interference is seen within a few seconds. A1b therefore re-runs it with `--sim-duration 10` (the flag was added in 41bb756): every one of the 76 samples with error > 5° carried a warning.
- A8 / A8b: a JSONL file whose samples say `source:"hardware"` (for example an app JSONL recording of a future live session, R7), replayed with `--source replay:<file>`, is shown with the **HARDWARE** badge and the banner **"Live hardware samples."** The transport line says replay, in small text. Per TEST_PLAN §4 ("wrong source badge" = CRITICAL) this is filed as **D6 (CRITICAL)**. R8 is met literally (badge = sample.source), and the PM decision (ARCHITECTURE.md 2026-11-27, "replayed file keeps its original source") covers the sim case. But for hardware-labelled files, replayed data is presented as live hardware. That conflicts with README rule "UI must show the active data source" and with N4. `firmware_bridge --replay` already relabels to `replay` (A3a), so only the app's own replay path is affected.
- A9b originally failed twice because of T6 harness bugs, not product bugs, and both were fixed before this run: (1) ingest has no clock of its own, so the browser saw stale data, fixed by feeding samples continuously during the render; (2) the DOM parser read only the first `<li>` of the warnings list. Nothing was forced to pass. The fixes are in the harness source.

## Per-step command, raw output and result
### A1 sim:static -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 48249 --source sim:static --rate 50 --seed 3`

Result: pid_ok=True records=162 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.29 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 00:46:22,894 INFO root: Heading monitor UI on http://127.0.0.1:48249  (source sim:static)
```

### A1 sim:yaw_spin -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 45731 --source sim:yaw_spin --rate 50 --seed 3`

Result: pid_ok=True records=155 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.32 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 00:46:26,442 INFO root: Heading monitor UI on http://127.0.0.1:45731  (source sim:yaw_spin)
```

### A1 sim:tilted_spin -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 58641 --source sim:tilted_spin --rate 50 --seed 3`

Result: pid_ok=True records=155 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.42 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 00:46:29,811 INFO root: Heading monitor UI on http://127.0.0.1:58641  (source sim:tilted_spin)
```

### A1 sim:calibration_dance -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 60439 --source sim:calibration_dance --rate 50 --seed 3`

Result: pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=13.91 deg warnings=['FIELD_MAGNITUDE_OUT_OF_RANGE', 'NOT_CALIBRATED', 'TILT_TOO_LARGE'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 00:46:33,207 INFO root: Heading monitor UI on http://127.0.0.1:60439  (source sim:calibration_dance)
```

### A1 sim:hard_iron -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 47227 --source sim:hard_iron --rate 50 --seed 3`

Result: pid_ok=True records=155 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=10.53 deg warnings=['FIELD_MAGNITUDE_OUT_OF_RANGE', 'HIGH_NOISE', 'NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 00:46:36,547 INFO root: Heading monitor UI on http://127.0.0.1:47227  (source sim:hard_iron)
```

### A1 sim:soft_iron -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 41079 --source sim:soft_iron --rate 50 --seed 3`

Result: pid_ok=True records=154 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=10.56 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 00:46:39,916 INFO root: Heading monitor UI on http://127.0.0.1:41079  (source sim:soft_iron)
```

### A1 sim:motor_interference -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 42111 --source sim:motor_interference --rate 50 --seed 3`

Result: pid_ok=True records=152 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.32 deg warnings=['NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 00:46:43,311 INFO root: Heading monitor UI on http://127.0.0.1:42111  (source sim:motor_interference)
```

### A1 sim:high_noise -> heading_core -> app — **PASS**

Command: `-m app --host 127.0.0.1 --port 35117 --source sim:high_noise --rate 50 --seed 3`

Result: pid_ok=True records=153 sources=['sim'] badge=SIMULATED backend=['heading_core'] RMSE_vs_truth(after 1 s, uncalibrated app)=0.35 deg warnings=['HIGH_NOISE', 'NOT_CALIBRATED'] sim_status=sim (T3, real module) port_released=True

Raw process output (last lines):
```
2026-11-27 00:46:46,639 INFO root: Heading monitor UI on http://127.0.0.1:35117  (source sim:high_noise)
```

### A1b sim:motor_interference (--sim-duration 10) -> app: interference must be warned — **PASS**

Command: `-m app --host 127.0.0.1 --port 55341 --source sim:motor_interference --rate 20 --seed 3 --sim-duration 10 --stale 60`

Result: pid_ok=True records=195 warnings_seen=['FIELD_MAGNITUDE_OUT_OF_RANGE', 'HIGH_NOISE'] max|err|=14.7 deg samples err>5deg=76 of which without any warning=0

Raw process output (last lines):
```
2026-11-27 00:46:50,065 INFO root: Heading monitor UI on http://127.0.0.1:55341  (source sim:motor_interference)
```

### A2 replay sim/examples/calibration_dance_10hz_10s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 40089 --source replay:sim/examples/calibration_dance_10hz_10s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=100 records=100 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 00:47:00,079 INFO root: Heading monitor UI on http://127.0.0.1:40089  (source replay:/workspace/audit/clean_471724e/sim/examples/calibration_dance_10hz_10s_seed42.jsonl)
```

### A2 replay sim/examples/hard_iron_10hz_5s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 40753 --source replay:sim/examples/hard_iron_10hz_5s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 00:47:00,863 INFO root: Heading monitor UI on http://127.0.0.1:40753  (source replay:/workspace/audit/clean_471724e/sim/examples/hard_iron_10hz_5s_seed42.jsonl)
```

### A2 replay sim/examples/motor_interference_10hz_5s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 36849 --source replay:sim/examples/motor_interference_10hz_5s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 00:47:01,415 INFO root: Heading monitor UI on http://127.0.0.1:36849  (source replay:/workspace/audit/clean_471724e/sim/examples/motor_interference_10hz_5s_seed42.jsonl)
```

### A2 replay sim/examples/static_10hz_5s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 37229 --source replay:sim/examples/static_10hz_5s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 00:47:01,961 INFO root: Heading monitor UI on http://127.0.0.1:37229  (source replay:/workspace/audit/clean_471724e/sim/examples/static_10hz_5s_seed42.jsonl)
```

### A2 replay sim/examples/yaw_spin_10hz_5s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 52905 --source replay:sim/examples/yaw_spin_10hz_5s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=50 records=50 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 00:47:02,519 INFO root: Heading monitor UI on http://127.0.0.1:52905  (source replay:/workspace/audit/clean_471724e/sim/examples/yaw_spin_10hz_5s_seed42.jsonl)
```

### A2 replay sim/examples/yaw_spin_dronecan_50hz_2s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 38677 --source replay:sim/examples/yaw_spin_dronecan_50hz_2s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=100 records=100 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 00:47:03,030 INFO root: Heading monitor UI on http://127.0.0.1:38677  (source replay:/workspace/audit/clean_471724e/sim/examples/yaw_spin_dronecan_50hz_2s_seed42.jsonl)
```

### A2 replay sim/examples/yaw_spin_msp_50hz_2s_seed42.jsonl — **PASS**

Command: `-m app --host 127.0.0.1 --port 42095 --source replay:sim/examples/yaw_spin_msp_50hz_2s_seed42.jsonl --speed 20`

Result: pid_ok=True file_lines=100 records=100 invalid=0 sample.source=['sim'] badge=['SIMULATED'] state=ended

Raw process output (last lines):
```
2026-11-27 00:47:03,566 INFO root: Heading monitor UI on http://127.0.0.1:42095  (source replay:/workspace/audit/clean_471724e/sim/examples/yaw_spin_msp_50hz_2s_seed42.jsonl)
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

Command: `-m app --host 127.0.0.1 --port 35805 --source replay:<out>/capture_replayed.jsonl --speed 20`

Result: pid_ok=True records=60 sample.source=['replay'] badge=['REPLAY'] heading[0..3]=[0.5, 1.9, 3.4]

Raw process output (last lines):
```
2026-11-27 00:47:04,133 INFO root: Heading monitor UI on http://127.0.0.1:35805  (source replay:<out>/capture_replayed.jsonl)
```

### A4 firmware_bridge --fake-fc | POST -> app (ingest) — **PASS**

Command: `python -m firmware_bridge --fake-fc --count 100 | POST each line to /api/sample ; -m app --host 127.0.0.1 --port 57931 --source ingest --stale 30`

Result: pid_ok=True posted=100 accepted=100 rejected=[] sources=['sim'] badge=['SIMULATED'] heading range=0.2..151.6

Raw process output (last lines):
```
2026-11-27 00:47:04,745 INFO root: Heading monitor UI on http://127.0.0.1:57931  (source ingest)
```

### A5 calibration wizard start/stop/fit/apply/save/clear/load — **PASS**

Command: `-m app --host 127.0.0.1 --port 51935 --source sim:calibration_dance --rate 50 --seed 5`

Result: pid_ok=True collected n=304/300 bins=9/12 octants=5/8 fit ok=True backend=heading_core offset_uT=[11.84591381228662, -8.111246721023761, 4.991328129384055] (sim truth hard-iron [12,-8,5]) | after apply: calibrated=True, RMSE vs truth last 50=0.72 deg | clear -> active=False; load -> active=True

Raw process output (last lines):
```
[["start", {"ok": true}], ["stop", {"ok": true}], ["fit", {"ok": true, "backend": "heading_core", "error": null}], ["apply", {"ok": true}], ["save", {"ok": true, "file": "t6_audit_cal.json"}], ["list", {"files": ["t6_audit_cal.json"]}], ["load", {"ok": true}]]
2026-11-27 00:47:05,146 INFO root: Heading monitor UI on http://127.0.0.1:51935  (source sim:calibration_dance)
```

### A6 frozen + stale data — **PASS**

Command: `-m app --host 127.0.0.1 --port 49501 --source ingest --stale 1.5 ; POST 60 identical samples, then silence`

Result: pid_ok=True 3 s identical samples -> warnings=['SENSOR_STALE', 'NOT_CALIBRATED'] quality=0.025 sensor_status=OK; then 2.2 s silence (stale 1.5 s) -> sensor_status=STALE reason='no sample for 2.2 s (timeout 1.5 s)'

Raw process output (last lines):
```
2026-11-27 00:47:14,225 INFO root: Heading monitor UI on http://127.0.0.1:49501  (source ingest)
```

### A7 serial to missing port (app) — **PASS**

Command: `-m app --host 127.0.0.1 --port 32943 --source serial:/dev/ttyT6_DOES_NOT_EXIST`

Result: pid_ok=True app alive=True source_status={'transport': 'serial', 'state': 'fault', 'backend': 'firmware_bridge (T4)', 'detail': "firmware_bridge exited rc=2 after 0 samples. [firmware_bridge] ERROR: [Errno 2] could not open port /dev/ttyT6_DOES_NOT_EXIST: [Errno 2] No such file or directory: '/dev/ttyT6_DOES_NOT_EXIST'"} sensor_status=FAULT records=0 (no HARDWARE samples fabricated)

Raw process output (last lines):
```
2026-11-27 00:47:16,806 INFO root: Heading monitor UI on http://127.0.0.1:32943  (source serial:/dev/ttyT6_DOES_NOT_EXIST)
```

### A7b firmware_bridge --port missing — **PASS**

Command: `python -m firmware_bridge --port /dev/ttyT6_DOES_NOT_EXIST`

Result: rc=2 stdout_lines=0 stderr="[firmware_bridge] ERROR: [Errno 2] could not open port /dev/ttyT6_DOES_NOT_EXIST: [Errno 2] No such file or directory: '/dev/ttyT6_DOES_NOT_EXIST'"

Raw process output (last lines):
```
[firmware_bridge] ERROR: [Errno 2] could not open port /dev/ttyT6_DOES_NOT_EXIST: [Errno 2] No such file or directory: '/dev/ttyT6_DOES_NOT_EXIST'
```

### A8 app replay of a hardware-labelled log: badge must not read HARDWARE — **FAIL**

Command: `-m app --host 127.0.0.1 --port 51811 --source replay:<out>/hw_labelled.jsonl --speed 20`

Result: pid_ok=True file sample.source=hardware -> app records source=['hardware'] -> badge=['HARDWARE'] (active data source is a REPLAY of a file)

Raw process output (last lines):
```
2026-11-27 00:47:20,183 INFO root: Heading monitor UI on http://127.0.0.1:51811  (source replay:<out>/hw_labelled.jsonl)
```

### A9a UI render (headless Chrome, sim) — **PASS**

Command: `-m app --host 127.0.0.1 --port 52053 --source sim:yaw_spin --stale 60 ; google-chrome --headless=new --dump-dom http://127.0.0.1:<port>/`

Result: Google Chrome 156.0.8078.47; pid_ok=True sourceBadge='SIMULATED' headingValue='30.8° NNE' gpsStatus='Unknown' warnings='NOT_CALIBRATED'

Raw process output (last lines):
```
2026-11-27 00:47:20,563 INFO root: Heading monitor UI on http://127.0.0.1:52053  (source sim:yaw_spin)
```

### A9b UI render (headless Chrome, 3x field -> warning) — **PASS**

Command: `-m app --host 127.0.0.1 --port 40117 --source ingest --stale 600 ; POST |B|~150 uT samples at 20 Hz continuously during render ; dump-dom`

Result: pid_ok=True fed=21 feed_errors=[] sourceBadge='REPLAY' headingValue='6.8° N' (api heading_deg=6.842) warnings='NOT_CALIBRATED | FIELD_MAGNITUDE_OUT_OF_RANGE'

Raw process output (last lines):
```
2026-11-27 00:47:22,699 INFO root: Heading monitor UI on http://127.0.0.1:40117  (source ingest)
```

### A8b UI render of a replayed hardware-labelled log (headless Chrome) — **FAIL**

Command: `-m app --host 127.0.0.1 --port 49721 --source replay:<out>/hw_labelled.jsonl --speed 1 --loop --stale 60 ; dump-dom`

Result: pid_ok=True sourceBadge='HARDWARE' evidenceBanner='Live hardware samples. Accuracy is not hardware-verified until the auditor signs off a committed log.' transportText='transport: replay:<out>/hw_labelled.jsonl · running · app file reader'

Raw process output (last lines):
```
2026-11-27 00:47:24,103 INFO root: Heading monitor UI on http://127.0.0.1:49721  (source replay:<out>/hw_labelled.jsonl)
```

