# Contribution report — UI & Software Developer (T5, `app/`)

**Status:** T5 at REVIEW (PM accepted pending the Auditor's sign-off).
**Evidence level:** every heading, field and accuracy number shown in the app, the screenshots and the demo video is `[SIMULATED]` (T3 sim) or a replay of a simulated log. Nothing here is hardware-verified: no RM3100, Matek CAN-L4-3100 or flight controller was ever connected to the app.
**Scope:** compass heading only. The app has no position, coordinate, map, speed, course or distance features and makes no navigation claims; GPS appears only as a read-only availability indicator.

Filename: `ui.md`, following the area-named siblings (`maths.md`, `sim.md`, `firmware.md`, `hardware.md`, `hub.md`).

## 1. Deliverables
| Path | Content |
|---|---|
| `app/__main__.py` | CLI: `python -m app --source sim[:scenario]\|replay:<file>\|serial:<port>\|ingest` → http://localhost:8080. Options `--host`, `--port` (0 = OS-assigned ephemeral port, real port logged), `--rate`, `--seed`, `--sim-duration`, `--baud`, `--speed`, `--loop`, `--declination`, `--stale`, `--calibration`, `-v` |
| `app/sources.py` | Sample sources: real sim subprocess (`python -m sim --realtime`), replay (paced by `t`), serial (via `python -m firmware_bridge`, never stubbed), ingest (`POST /api/sample`); contract validation (`mag_raw` optional, `gps` optional, no coordinates) |
| `app/core_adapter.py`, `app/_stubs.py` | heading_core `Calibration`/`HeadingEstimator` through the ARCHITECTURE.md interface; labelled local stubs used only on `NotImplementedError` (currently inactive) |
| `app/hub.py`, `app/server.py` | State, history (6000 samples), sensor status OK/DEGRADED/FAULT/STALE/NO DATA, calibration wizard, CSV/JSONL recorder; stdlib HTTP + RFC 6455 WebSocket push (10 Hz) and the REST API listed in `app/README.md` |
| `app/static/` | Vanilla JS/SVG/canvas UI, no CDN or build step: DATA SOURCE badge taken only from `sample.source`, compass with separate measured/reference indicators, filtered and unfiltered heading, roll/pitch, field plot, quality bar and warnings, GPS availability indicator, history chart/table, CSV export, calibration wizard; unavailable values shown as Unknown |
| `app/tests/` | 45 tests: core adapter, heading maths (Python + Node), HTTP/WebSocket smoke tests, 3 headless-Chrome DOM tests driven over the DevTools protocol; all on ephemeral ports |
| `app/README.md` | Run, architecture, UI table, heading-only section, Unknown/stale rules, data interfaces, tests, LIMITATIONS 0–10 |
| `INSTALL.md` | Clean install, running each source, running every test suite, real verification log from a fresh clone + fresh venv |
| `reports/demo/demo.mp4` | 71.48 s, 1440×900, H.264 25 fps, 2,463,884 bytes; real app on ephemeral ports; SIMULATED badge and the caption "Simulated data — not hardware-verified. Compass heading only; no position or navigation." on every frame |
| `reports/demo/*.png`, `README.md`, `make_demo.py`, `demo_metrics.json`, `demo_tilted_spin_recording.jsonl` | Stills `01`–`06`, exact commands, the reproducible script, measured scene metrics `[SIMULATED]`, and the JSONL replayed in scene 6 |
| `reports/screenshots/t5_*.png` | 4 screenshots of the real running app: dashboard (`sim:tilted_spin`), calibration applied (`sim:calibration_dance`), GPS indicator (ingest), no current data → Unknown. Refreshed in this commit to the current labels |
| `TEAM_TRACKER.md` (T5 row + UI changelog lines) | Status, test counts, limitations mirror |

Commits: `84fc231` (T5 → REVIEW: app, 40 tests, LIMITATIONS, screenshots), `516f80c` (GPS indicator wired to `sample.gps`, all tests on `--port 0`, deterministic headless UI tests), `41bb756` (demo video, INSTALL.md, `--sim-duration`, filtered/unfiltered labels, 45 tests), `8687ab8` (INSTALL.md fresh-venv verification log, README tests section, tracker row), plus the commit adding this file and the refreshed screenshots (message starting `[ui] contribution report`; see `git log -- reports/contributions/ui.md`).

Demo metrics `[SIMULATED]` (from `reports/demo/demo_metrics.json`): mean |heading error vs sim truth| 21.40° before calibration (n = 161) and 0.418° after (n = 120); fit by `heading_core.Calibration.fit` on 681 samples, residual 0.0156 µT; `motor_interference` shows DEGRADED with FIELD_MAGNITUDE_OUT_OF_RANGE, HIGH_NOISE.

## 2. Tests actually executed
All from the repo root. Environment: Python 3.13.5, pytest 9.2.0, numpy 2.5.5, jsonschema 4.26.0, google-chrome (headless), Node v24.22.1. Results copied from the console output.

Re-run now, 2026-11-27 00:49–00:51 IST, HEAD `8687ab8`, system Python:

| Command | Result |
|---|---|
| `python3 -m pytest app/tests -q` | **45 passed** in 19.92 s |
| `python3 -m pytest tests/test_t6_app.py -q` (Auditor's app tests) | **10 passed** |
| `python3 -m pytest tests/test_t6_claims.py -q` (Auditor's claims test, with this file present) | **1 failed, 3 passed**; the one failure is `reports/contributions/maths.md:30` (details below) |

Earlier executed results (not re-run in this session):

| When / commit | Command | Result |
|---|---|---|
| `516f80c` | `python3 -m pytest app/tests/test_app_ui_headless.py -q`, 10 consecutive runs | **10/10 passed** (3/3 each, about 4 s per run); fixed the flake where the badge showed NO DATA once |
| `516f80c` | `python3 -m pytest app/tests -q`, 3 runs | 44 passed ×3 |
| `516f80c` | `python3 -m pytest tests/test_t6_app.py tests/test_t6_claims.py -q` | 14 passed |
| before `41bb756` | `python3 -m pytest app/tests -q`, 3 runs | 45 passed ×3 |

Fresh-clone verification of `INSTALL.md` (2026-11-26/27 night IST): `git clone /workspace/heading-monitor /tmp/hm-clone` at `41bb756`, `python3 -m venv /tmp/hm-venv`, `pip install -r requirements.txt`, pyserial not installed:

| Command | Result |
|---|---|
| `python -m pytest app/tests -q` | 45 passed |
| `python -m pytest tests -q` | 105 passed |
| `python -m pytest heading_core/tests -q` | 76 passed |
| `python -m pytest docs/math/sensor-spec -q` | 23 passed |
| `python -m pytest sim/tests -q` | 152 passed, 44 skipped (sim's deliberate N/A spec keys) |
| `python -m pytest firmware_bridge/tests -q` | 94 passed, 1 skipped (pyserial absent); 95 passed after `pip install pyserial` |
| `python -m pytest docs/firmware/research -q` | 4 passed |
| all seven paths in one run, and bare `python -m pytest -q` | **499 passed, 45 skipped** |
| `python -m app --source sim:tilted_spin --port 0` | sensor OK, source sim, estimator heading_core, 96/96 accepted |
| `python -m app --source replay:reports/demo/demo_tilted_spin_recording.jsonl --port 0` | OK, source sim (badge SIMULATED), 99/99 accepted |
| `python -m app --source ingest --port 0` | NO DATA, "no valid sample received yet" (expected) |
| `python -m app --source serial:/dev/ttyNONE --port 0` | FAULT, pyserial missing; with pyserial: FAULT, "could not open port /dev/ttyNONE" |

Claims test: `python3 -m pytest tests/test_t6_claims.py -q` gave **1 failed, 3 passed** on `8687ab8`, both before and after this file was added (ui.md adds no failure). The single failure is `test_Q1b_navigation_claims`, flagging `reports/contributions/maths.md:30` (the Mathematics & Sensor Scientist's file, not mine). No app/ or ui.md line is flagged; app/ and reports/demo lines appear only in the informational inventory because they negate position features.

Screenshots in this commit were produced by `/workspace/heading-monitor-runlogs/make_t5_screenshots.py` (real app via `run_app --port 0`, headless Chrome over CDP) and checked by eye: badge SIMULATED or NO DATA as expected, GPS Available/3D/9/0.9 for the ingest sample with `gps`, all values Unknown after the sample went stale.

## 3. Open limitations
Full text in `app/README.md` → LIMITATIONS (mirrored in the T5 row):
- U0. Heading only by PM decision: no position, coordinate, map, speed, course or distance features. The GPS indicator reads the optional `sample.gps` {fix, num_sat, hdop}; no current source (sim) emits it, so it normally reads Unknown. firmware_bridge's MSP_RAW_GPS path is untested with the app.
- U1. `mag_raw` is optional (CAN-L4-3100 sends scaled field, no raw counts).
- U2. Accuracy shown is precision (noise 1σ), quality and calibration residual, not absolute accuracy; error vs truth exists only for simulated data. Nothing here is hardware-verified.
- U3. The serial path was never run against a real flight controller, a live firmware_bridge session or the CAN-L4-3100; only a non-existent port (FAULT) was exercised.
- U4. Replay keeps the original `source` (a replayed sim log shows SIMULATED; transport shown separately).
- U5. Stubs exist but are inactive (heading_core and sim are real); firmware_bridge is never stubbed.
- U6. The calibration wizard shows coverage but does not guide the user per orientation.
- U7. One source per process; switching needs a restart; only one process can hold port 8080.
- U8. Local only, no authentication.
- U9. History is in memory (6000 samples); use recording for longer runs.
- U10. UI checked automatically and by screenshots only; human usability not assessed; layout checked at 1440–1600 px width only.
- The `reports/screenshots/t5_*.png` committed in `84fc231`/`516f80c` showed the earlier "calibrated/raw" labels; refreshed in this commit to the current "Measured (filtered)" / "Unfiltered" labels. Screenshots in older commits remain outdated.
- The demo video omits the stale/NO DATA scene so the SIMULATED badge stays visible throughout; stale → Unknown is covered by `t5_no_current_data_unknown.png` and the headless test instead.
- The `calibration_applied` screenshot shows DEGRADED / TILT_TOO_LARGE because the calibration_dance scenario is still tumbling; that is the real app state at capture time.

## 4. Money spent and paid tools
**Money spent: none. Paid tools or services: none.** Free tools used: Python 3 standard library (HTTP server, WebSocket, subprocess), pytest, numpy, jsonschema (via the shared requirements), headless Google Chrome driven over the DevTools protocol, ffmpeg (libx264) for the demo video, Node.js for the front-end maths tests, git. No CDN, Playwright, paid API or cloud service.
