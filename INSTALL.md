# INSTALL — Virtual Heading Monitor (clean machine)

Author: UI & Software Developer (T5). Everything here is free and open source and runs **offline and virtual**:
no hardware, no paid services. The steps below were checked on a fresh clone in a fresh venv. Results are in
the "Verification log" at the end.

## 1. Prerequisites
| Need | Version (as verified) | Required for |
|---|---|---|
| Python | 3.10+ (verified with 3.13.5) | everything |
| git | any | cloning |
| Google Chrome or Chromium | any recent (verified with google-chrome) | *optional*: the 3 headless-UI tests in `app/tests/test_app_ui_headless.py` (skipped when absent) and the demo video |
| Node.js | any recent (verified with 24) | *optional*: 2 app tests that run the front-end JS maths and badge mapping (skipped when absent) |
| ffmpeg (with libx264) | verified with 7.1 | *optional*: only `reports/demo/make_demo.py` |
| pyserial | — | *optional*: only `--source serial:<port>` against a real FC (`pip install pyserial`) |

Playwright is **not** needed. The UI tests drive Chrome over the DevTools protocol with the Python standard library.

## 2. Install
```bash
git clone <repo-url-or-path> heading-monitor      # e.g. git clone /workspace/heading-monitor heading-monitor
cd heading-monitor
python3 -m venv .venv
. .venv/bin/activate                              # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt                   # numpy, pytest, jsonschema
# optional, live hardware only:  pip install pyserial
```
The app itself (`app/`) uses only the standard library. numpy is needed by `heading_core` and `sim`.

## 3. Run the dashboard
All commands run from the repo root and open **http://localhost:8080** (`--port 0` picks a free port and prints it).

| Source | Command | Notes |
|---|---|---|
| Simulator (default scenario) | `python -m app --source sim` | T3 simulator in real time; badge SIMULATED |
| Simulator scenario | `python -m app --source sim:<scenario>` | scenarios: `static`, `yaw_spin`, `tilted_spin`, `calibration_dance`, `hard_iron`, `soft_iron`, `motor_interference`, `high_noise` (list: `python -m sim --list-scenarios`) |
| Replay a recording | `python -m app --source replay:reports/demo/demo_tilted_spin_recording.jsonl [--speed 2] [--loop]` | any Sample JSONL; the badge follows each sample's own `source` |
| Live FC (untested on hardware) | `python -m app --source serial:/dev/ttyACM0 --baud 115200` | via `python -m firmware_bridge`; needs pyserial and a real FC. Without one it shows FAULT / NO DATA |
| External ingest | `python -m app --source ingest` | POST Samples to `/api/sample` (see `app/README.md`) |

Useful options: `--port`, `--rate 20`, `--seed N`, `--sim-duration S`, `--declination DEG`, `--stale 2`,
`--calibration file.json`. Stop with Ctrl-C.

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

All suites can also run together. `python -m pytest -q` from the repo root (or listing all seven paths) gave the
same totals as the per-suite runs on 2026-11-26: 499 passed, 45 skipped. There was no module-name clash.
The app tests start their own app instances on OS-assigned ports. They never touch port 8080, so they can run
while the dashboard is open.

## 5. Demo video (optional)
`python reports/demo/make_demo.py` produces the files in `reports/demo/`. It needs Chrome and ffmpeg.
See `reports/demo/README.md`.

## Verification log
Real run on 2026-11-26 (IST), following this file on a fresh clone in a fresh venv:
`git clone /workspace/heading-monitor /tmp/hm-clone` (HEAD 41bb756), then `python3 -m venv /tmp/hm-venv` and
`pip install -r requirements.txt`. Environment: Python 3.13.5, numpy 2.5.5, pytest 9.2.0, jsonschema 4.26.0,
google-chrome present, Node v24.22.1, pyserial NOT installed.

| Suite | Result |
|---|---|
| `app/tests` | 45 passed (20.6 s) |
| `tests` | 105 passed (54.9 s) |
| `heading_core/tests` | 76 passed (52.2 s) |
| `docs/math/sensor-spec` | 23 passed |
| `sim/tests` | 152 passed, 44 skipped. The skips are deliberate (in sim's own skip reasons: spec cases that are analysis maths or source models the sim does not implement) |
| `firmware_bridge/tests` | 94 passed, 1 skipped (pyserial absent). With `pip install pyserial`: 95 passed |
| `docs/firmware/research` | 4 passed |
| all seven paths in one run, and bare `python -m pytest -q` | 499 passed, 45 skipped |

Each source was started with `python -m app --source ... --port 0` and `/api/status` was read after about 5 s:

| Source | Result |
|---|---|
| `sim:tilted_spin` | sensor OK, latest_sample_source=sim, estimator_backend=heading_core, 96/96 samples accepted |
| `replay:reports/demo/demo_tilted_spin_recording.jsonl` | OK, source=sim (a replayed sim log keeps SIMULATED), 99/99 accepted |
| `ingest` | NO DATA, "no valid sample received yet" (expected until something POSTs to `/api/sample`) |
| `serial:/dev/ttyNONE` without pyserial | FAULT: "firmware_bridge exited rc=2 … pyserial …" |
| `serial:/dev/ttyNONE` with pyserial | FAULT: "could not open port /dev/ttyNONE" |

There were no failures. Fixed in the doc after this run: the old advice to avoid one combined pytest run was wrong,
because the combined run works. Not verified: `serial:` against a real flight controller (none available; see
app/README LIMITATIONS 3).
