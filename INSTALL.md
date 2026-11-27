# INSTALL — Virtual Heading Monitor (clean machine)

Author: UI & Software Developer (T5). Everything here is free and open source and runs **offline and virtual**:
no hardware, no paid services. The steps below were checked on a fresh clone in a fresh venv. Results are in
the "Verification log" at the end.

## 1. Prerequisites
| Need | Version (as verified) | Required for |
|---|---|---|
| Python | 3.10+ (verified with 3.13.5) | everything |
| git | any | cloning |
| Google Chrome or Chromium | any recent (verified with google-chrome) | *optional*: the 7 headless-UI tests in `app/tests/test_app_ui_headless.py` (skipped when absent) and the demo video |
| Node.js | any recent (verified with 24) | *optional*: 2 app tests that run the front-end JS maths and badge mapping (skipped when absent) |
| ffmpeg (with libx264) | verified with 7.1 | *optional*: only `reports/demo/make_demo.py` |
| pyserial | verified with 3.5 | *optional*. Listed in `requirements.txt`, but nothing else depends on it. It is needed only for `--source serial:<port>` (`firmware_bridge --port`) and for the end-to-end tests over a virtual serial port (pty): 3 in `app/tests`, the bridge's pty tests, and the Auditor's pty/D8 checks. Without it those tests are skipped, not failed |

Playwright is **not** needed. The UI tests drive Chrome over the DevTools protocol with the Python standard library.

## 2. Install
```bash
git clone <repo-url-or-path> heading-monitor      # e.g. git clone /workspace/heading-monitor heading-monitor
cd heading-monitor
python3 -m venv .venv
. .venv/bin/activate                              # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt                   # numpy, pytest, jsonschema, pyserial (pyserial optional)
# minimal install without pyserial: pip install numpy pytest jsonschema  (serial source + pty tests then skip)
```
The app itself (`app/`) uses only the standard library. numpy is needed by `heading_core` and `sim`.

## 3. Run the dashboard
All commands run from the repo root and open **http://localhost:8080** (`--port 0` picks a free port and prints it).

| Source | Command | Notes |
|---|---|---|
| Simulator (default scenario) | `python -m app --source sim` | T3 simulator in real time; badge SIMULATED |
| Simulator scenario | `python -m app --source sim:<scenario>` | scenarios: `static`, `yaw_spin`, `tilted_spin`, `calibration_dance`, `hard_iron`, `soft_iron`, `motor_interference`, `high_noise` (list: `python -m sim --list-scenarios`) |
| Replay a recording | `python -m app --source replay:reports/demo/demo_tilted_spin_recording.jsonl [--speed 2] [--loop]` | any Sample JSONL; the badge follows each sample's own `source` |
| Serial FC (untested on hardware) | `python -m app --source serial:/dev/ttyACM0 --baud 115200 [--verified-devices FILE]` | via `python -m firmware_bridge`; needs pyserial. A serial link is not proof of hardware (D8): the badge shows UNVERIFIED SOURCE unless the device's self-reported UID is on the allowlist (`config/verified_devices.json`, ships empty), and then reads "ALLOWLISTED DEVICE (identity not authenticated)". Without a device it shows FAULT / NO DATA |
| External ingest | `python -m app --source ingest` | POST Samples to `/api/sample` (see `app/README.md`) |

Useful options: `--port`, `--rate 20`, `--seed N`, `--sim-duration S`, `--declination DEG`, `--stale 2`,
`--calibration file.json`, `--verified-devices FILE`. Stop with Ctrl-C.

## 4. Run the tests
Run from the repo root with the venv active. Every suite is independent.

| Suite | Command | Owner |
|---|---|---|
| App (T5) | `python -m pytest app/tests -q` | UI & Software Developer |
| Auditor / independent (T6) | `python -m pytest tests -q` | Testing & Technical Auditor |
| heading_core (T2) | `python -m pytest heading_core/tests -q` | Mathematics & Sensor Scientist |
| Math reference spec (T2) | `python -m pytest docs/math/sensor-spec -q` | Mathematics & Sensor Scientist |
| Simulator (T3) | `python -m pytest sim/tests -q` | Simulation Developer |
| Firmware bridge (T4) | `python -m pytest firmware_bridge/tests -q` | Firmware Specialist |
| FW quantization research (T4) | `python -m pytest docs/firmware/research -q` | Firmware Specialist |

All suites can also run together with `python -m pytest -q` from the repo root. The totals equal the sum of the
per-suite runs (see the verification log). There is no module-name clash.
The app tests start their own app instances on OS-assigned ports. They never touch port 8080, so they can run
while the dashboard is open.

## 5. Demo video (optional)
`python reports/demo/make_demo.py` produces the files in `reports/demo/`. It needs Chrome and ffmpeg.
See `reports/demo/README.md`.

## Verification log
### Current counts (2026-11-27, 10:45–11:03 IST, real runs)
These runs used the shared working tree at HEAD d5374a1, plus the T5 label/D9 change committed right after (see
TEAM_TRACKER changelog). The Auditor's in-progress `tests/` edits were present in the tree. Two environments, both
Python 3.13.5, numpy 2.5.5, pytest 9.2.0, jsonschema 4.26.0, google-chrome and Node v24.22.1:
- **A:** system python without pyserial.
- **B:** the venv `/tmp/hm-venv`, made with `pip install -r requirements.txt`, so it has pyserial 3.5.

| Suite | A: without pyserial | B: with pyserial |
|---|---|---|
| `app/tests` | 82 passed, 3 skipped (the 3 pty end-to-end tests), ×3 | 85 passed in 2 of 3 runs; the other run: 2 failed, 83 passed (see below); 5 reruns: 85 passed each |
| `tests` (Auditor) | 111 passed, 2 skipped | 173 passed |
| `heading_core/tests` | 76 passed | 76 passed |
| `docs/math/sensor-spec` | 23 passed | 23 passed |
| `sim/tests` | 152 passed, 44 skipped (deliberate; see sim's skip reasons) | 152 passed, 44 skipped |
| `firmware_bridge/tests` | 136 passed, 2 skipped (pyserial) | 138 passed |
| `docs/firmware/research` | 4 passed | 4 passed |
| bare `python -m pytest -q` | 584 passed, 51 skipped (2 min 23 s) | 651 passed, 44 skipped (3 min 27 s) |

In B, one of the first three `app/tests` runs reported 2 failed / 83 passed after 101 s. Its failure details were not
captured, and it did not recur: 5 further runs in B each gave 85 passed, and so did the other 2 runs. The other 44
skips in B are sim's deliberate skips.

`reports/audit/integration_run.py <repo> /tmp/...` gave 37/37 in B and 31/37 in A. In A, the 6 checks A10c–A10g and
A10i report NOT RUN, which counts as FAIL, because pyserial is missing.

### First verification (2026-11-26, fresh clone)
Real run on 2026-11-26 (IST), following this file on a fresh clone in a fresh venv:
`git clone /workspace/heading-monitor /tmp/hm-clone` (HEAD 41bb756), then `python3 -m venv /tmp/hm-venv` and
`pip install -r requirements.txt` (no pyserial in requirements at that time). The counts below are historical; the
current counts are in the table above.

| Suite | Result (2026-11-26) |
|---|---|
| `app/tests` | 45 passed |
| `tests` | 105 passed |
| `heading_core/tests` | 76 passed |
| `docs/math/sensor-spec` | 23 passed |
| `sim/tests` | 152 passed, 44 skipped |
| `firmware_bridge/tests` | 94 passed, 1 skipped (pyserial absent) |
| `docs/firmware/research` | 4 passed |
| all seven paths in one run | 499 passed, 45 skipped |

Each source was started with `python -m app --source ... --port 0` and `/api/status` was read after about 5 s
(2026-11-26):

| Source | Result |
|---|---|
| `sim:tilted_spin` | sensor OK, latest_sample_source=sim, estimator_backend=heading_core, 96/96 samples accepted |
| `replay:reports/demo/demo_tilted_spin_recording.jsonl` | OK, source=sim (a replayed sim log keeps SIMULATED), 99/99 accepted |
| `ingest` | NO DATA, "no valid sample received yet" (expected until something POSTs to `/api/sample`) |
| `serial:/dev/ttyNONE` without pyserial | FAULT: "firmware_bridge exited rc=2 … pyserial …" |
| `serial:/dev/ttyNONE` with pyserial | FAULT: "could not open port /dev/ttyNONE" |

Not verified: `serial:` against a real flight controller (none available; see app/README LIMITATIONS 3 and 11).
