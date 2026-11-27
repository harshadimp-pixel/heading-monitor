# Contribution report — UI & Software Developer (T5, `app/`)

**Status:** T5 at REVIEW (PM accepted pending the Auditor's sign-off). D6 (CRITICAL, replayed hardware shown as live) fixed in `0ca6b0f` and set to REVIEW; the Auditor re-runs A8/A8b and closes it.
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
| `app/tests/` | 52 tests: core adapter, heading maths (Python + Node), HTTP/WebSocket smoke tests, D6 replay-labelling tests (`test_app_d6_replay.py`), 5 headless-Chrome DOM tests driven over the DevTools protocol; all on ephemeral ports |
| `app/README.md` | Run, architecture, UI table, heading-only section, Unknown/stale rules, data interfaces, tests, LIMITATIONS 0–10 |
| `INSTALL.md` | Clean install, running each source, running every test suite, real verification log from a fresh clone + fresh venv |
| `reports/demo/demo.mp4` | 71.48 s, 1440×900, H.264 25 fps, 2,463,884 bytes; real app on ephemeral ports; SIMULATED badge and the caption "Simulated data — not hardware-verified. Compass heading only; no position or navigation." on every frame |
| `reports/demo/*.png`, `README.md`, `make_demo.py`, `demo_metrics.json`, `demo_tilted_spin_recording.jsonl` | Stills `01`–`06`, exact commands, the reproducible script, measured scene metrics `[SIMULATED]`, and the JSONL replayed in scene 6 |
| `reports/screenshots/t5_*.png` | 4 screenshots of the real running app: dashboard (`sim:tilted_spin`), calibration applied (`sim:calibration_dance`), GPS indicator (ingest), no current data → Unknown. Refreshed in this commit to the current labels |
| `TEAM_TRACKER.md` (T5 row + UI changelog lines) | Status, test counts, limitations mirror |

Commits: `84fc231` (T5 → REVIEW: app, 40 tests, LIMITATIONS, screenshots), `516f80c` (GPS indicator wired to `sample.gps`, all tests on `--port 0`, deterministic headless UI tests), `41bb756` (demo video, INSTALL.md, `--sim-duration`, filtered/unfiltered labels, 45 tests), `8687ab8` (INSTALL.md fresh-venv verification log, README tests section, tracker row), `0ca6b0f` (D6 fix: replay relabelling, REPLAY (recorded hardware) badge, not-live banner, ingest UNVERIFIED SOURCE, provenance in CSV/JSONL, 52 tests), `ed3961c` (this file + refreshed screenshots), plus the commit updating this file and the refreshed screenshots (message starting `[ui] contribution report`; see `git log -- reports/contributions/ui.md`).

### D6 fix (`0ca6b0f`, per the PM decision in ARCHITECTURE.md)
- `--source replay:<file>`: every sample with `source:"hardware"` is relabelled to `source:"replay"` with `meta.original_source:"hardware"` and `meta.replayed_from:<file>` (the same fields `firmware_bridge --replay` sets; a test compares the two). Other meta keys are kept. `sim` and `replay` samples are unchanged, so a replayed sim log still shows SIMULATED with the transport shown as replay.
- Badge: **REPLAY (recorded hardware)**. Banner: "[REPLAYED] Recorded hardware log played back from a file. This is recorded data, not a live sensor stream. Nothing here is hardware-verified."
- HARDWARE (and a live banner) appears only for `source:"hardware"` arriving over the serial transport. A `hardware`-labelled sample posted via `ingest` keeps its label (contract; the Auditor's U2 test relies on it) but shows **UNVERIFIED SOURCE** with a banner saying it is not a live serial source.
- Records carry `original_source` (copied from meta, never inferred), `transport` and `live_hardware`; CSV gains `original_source`, `transport` columns; JSONL recordings store the relabelled Sample including `meta.original_source`.
- The relabel mirrors the bridge's fields instead of importing its helper: the bridge's Python function is not an ARCHITECTURE interface (CLI only), and it relabels sim samples too.

Demo metrics `[SIMULATED]` (from `reports/demo/demo_metrics.json`): mean |heading error vs sim truth| 21.40° before calibration (n = 161) and 0.418° after (n = 120); fit by `heading_core.Calibration.fit` on 681 samples, residual 0.0156 µT; `motor_interference` shows DEGRADED with FIELD_MAGNITUDE_OUT_OF_RANGE, HIGH_NOISE.

### D8 fix (app side; ARCHITECTURE.md D8 at `1bef73e`, contract `docs/firmware/D8_PROVENANCE.md` at `e37430b`)
- A serial connection is no longer proof of hardware. The hub runs `app/provenance.py` on every serial sample.
  It shows HARDWARE only when all of these hold: `source == "hardware"`, the bridge set `meta.provenance == "verified"`,
  and the reported `meta.device_identity.uid` is in `config/verified_devices.json`.
- That file belongs to Firmware and ships empty, so today no sample shows HARDWARE.
- SIML/SIMF (fake FC) or `provenance == "simulated"` shows SIMULATED, even if the UID is allowlisted.
- These cases show UNVERIFIED SOURCE: no identity, no valid UID, UID not listed, or the bridge did not verify.
- Board, variant, target and UID appear under the badge as "… (reported by device)".
- The app passes the same file to `firmware_bridge --verified-devices`. The app flag is `--verified-devices`;
  its default is `config/verified_devices.json`.
- The allowlist is read with Firmware's `load_allowlist`, which fails closed. A mirror is used only if that loader
  cannot be imported.
- Replay (D6) and ingest are unchanged.
- New tests: `app/tests/test_app_d8_serial_provenance.py`, which includes a pty FakeFC end-to-end run that needs
  pyserial, plus a headless D8 badge/label test.

### D8 hardening (after external review of `e538cea`)
- The badge never trusts a sample's own claims: `meta.provenance: "verified"`, `meta.live_hardware`, or top-level
  `live_hardware` / `device_verified` / `transport`.
- The server builds each record from a whitelist and computes verification itself. A sample counts as verified only
  when it arrived through `hub.source_emit`, the callable handed only to the app's own source, on a serial hub, AND
  the app re-checks the reported UID against its own allowlist.
- Any other caller gets `untrusted_channel`.
- The frontend uses only the server's `transport` and `device_verified` fields.
- The label is the single constant `HARDWARE_LABEL`. The Auditor is still deciding on the text.
- Tests: `app/tests/test_app_d8_forged_claims.py` (12), plus the headless test
  `test_d8_forged_ingest_claims_show_unverified`.

### D8 label decision + D9 (2026-11-27; label from the Auditor, accepted by the PM in `d5374a1`)
- **Badge and banner:**
  - The allowlisted badge now reads **"ALLOWLISTED DEVICE (identity not authenticated)"**, defined once as
    `HARDWARE_LABEL` in `app/static/headingmath.js`.
  - Banner, exactly: "Live serial device whose self-reported UID is on the local allowlist. The UID is not
    cryptographic proof; this is not hardware verification." It is defined once as `ALLOWLISTED_BANNER`.
  - Internally nothing changed: `source: "hardware"`, `device_status: "verified"`, `live_hardware: true`.
  - The bare word HARDWARE is never displayed. `badgeLabel`/`SOURCE_LABEL` stay as the contract source-name map that
    the Auditor's `tests/test_t6_app.py` uses.
  - The badge uses smaller type and may wrap. I checked it in screenshots at 1440 px and 700 px: two lines, no
    overflow. A headless test asserts there is no overflow.
- **D9:** the pty end-to-end test is renamed
  `test_e2e_virtual_pty_allowlist_mechanism_and_F11_spoof_limitation_not_hardware_validation`.
  - Its case ids include `spoofed_allowlisted_uid_passes_LIMITATION_F11`.
  - Its docstring and assert messages say it demonstrates the allowlist mechanism and the spoofable-UID limitation
    F11, not hardware validation.
  - Its expectations match the Auditor's F11 test (8343656).
  - No Auditor test or script references the old name; only TEAM_TRACKER and an old junit artifact mention it.
- **OPEN_QUESTIONS** in `app/provenance.py` is trimmed to the one point ARCHITECTURE D8 item 6
  (53f8bf7, 03ceee3) does not cover: the display-only `meta.fc_variant` fallback.

## 2. Tests actually executed
All from the repo root. Environment: Python 3.13.5, pytest 9.2.0, numpy 2.5.5, jsonschema 4.26.0, google-chrome (headless), Node v24.22.1. Results copied from the console output.

After the D6 fix, 2026-11-27 about 01:01–01:11 IST, working tree that became `0ca6b0f`, system Python:

| Command | Result |
|---|---|
| `python3 -m pytest app/tests -q`, 3 consecutive runs | **52 passed** ×3 (24.09 s, 23.91 s, 24.01 s) |
| `python3 -m pytest app/tests/test_app_ui_headless.py -q`, 5 consecutive runs | **5 passed** ×5 (5.0–5.7 s each) |
| `python3 -m pytest tests/ -q` (all Auditor `test_t6_*`) | **111 passed** in 45.49 s |
| `python3 -m pytest -q` (whole repo) | **512 passed, 45 skipped** in 133.23 s (finished 01:09:34 IST) |
| `python3 reports/audit/integration_run.py /workspace/heading-monitor /tmp/d6_integ` (Auditor's script; output to /tmp, no repo files written) | **27/27 passed**, incl. A8 (file `source=hardware` → app records `source=['replay']`) and A8b (headless Chrome: badge 'REPLAY (recorded hardware)', banner "...recorded data, not a live sensor stream...") |
| `python3 -m pytest tests/test_t6_claims.py -q` | **4 passed** (the earlier `maths.md:30` failure was fixed by its owner in `dc3123a`); re-run against this updated file at 01:14 IST: 4 passed |

The Auditor's own A8/A8b sign-off is still pending; the 27/27 above is my run of their script, not their verdict.

Earlier run, 2026-11-27 00:49–00:51 IST, HEAD `8687ab8`, system Python (pre-D6):

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

Claims test history: `python3 -m pytest tests/test_t6_claims.py -q` gave **1 failed, 3 passed** on `8687ab8`, both before and after this file was added (ui.md adds no failure). The single failure is `test_Q1b_navigation_claims`, flagging `reports/contributions/maths.md:30` (the Mathematics & Sensor Scientist's file, not mine). No app/ or ui.md line is flagged; app/ and reports/demo lines appear only in the informational inventory because they negate position features.

Screenshots in this commit were produced by `/workspace/heading-monitor-runlogs/make_t5_screenshots.py` (real app via `run_app --port 0`, headless Chrome over CDP) and checked by eye: badge SIMULATED or NO DATA as expected, GPS Available/3D/9/0.9 for the ingest sample with `gps`, all values Unknown after the sample went stale.

### D8 runs (2026-11-27, 10:11–10:15 IST, real output)
- `app/tests`, system python (no pyserial; the 3 pty end-to-end tests skip): 69 passed, 3 skipped, ×3.
- `app/tests` in a venv with pyserial (`pip install -r requirements.txt`): 72 passed, ×3. No skips.
- `app/tests/test_app_ui_headless.py`: 6 passed, ×5.
- `tests/` (Auditor): 111 passed, 2 skipped.

### D8 hardening runs (2026-11-27, 10:28–10:38 IST, real output)
- `app/tests`, system python: 82 passed, 3 skipped, ×3. The 3 pty end-to-end tests skip because pyserial is missing.
- `app/tests`, pyserial venv: 85 passed, ×3.
- `app/tests/test_app_ui_headless.py`: 7 passed, ×5.
- `tests/`: 111 passed, 2 skipped.
- Whole repo, system python: 584 passed, 51 skipped.
- `reports/audit/integration_run.py`, output to /tmp:
  - pyserial venv: 35/35. A10a–A10h all passed, including A10f, the allowlisted-UID spoof demonstration.
  - System python: 29/30. A10c did not run because pyserial is missing.
- This is my own run of the Auditor's script, not the Auditor's sign-off.

### Label + D9 runs (2026-11-27, 10:45–11:08 IST, real output)
| Run | System python, no pyserial | Venv with pyserial |
|---|---|---|
| `app/tests` | 82 passed, 3 skipped, ×3 | 85 passed in 2 of the first 3 runs; the other run: 2 failed, 83 passed in 101 s (details not captured); 5 reruns: 85 passed each |
| Headless browser file | 7 passed, ×3 | — |
| `tests/` | 111 passed, 2 skipped | 173 passed |
| Whole repo | 584 passed, 51 skipped | 651 passed, 44 skipped |
| `integration_run.py`, output to /tmp | 31/37 (A10c–g and A10i NOT RUN, no pyserial) | 37/37 |

These are my runs, not the Auditor's sign-off.

### Flaky app/tests: root cause and fix (2026-11-27, 11:11–11:52 IST)
- **Root cause:** recordings were named per second (`rec-YYYYmmdd-HHMMSS`) in the shared `app/recordings/`, and the
  calibration test used a fixed name. Two app/tests runs overlapping in one checkout overwrote or deleted each
  other's files. The download then returned HTTP 404, in `test_replay_of_hardware_log_is_relabelled_and_recorded`
  and `test_gps_in_recordings`.
- **Fix:**
  - recording names now carry milliseconds, the process id and a counter, and the file is opened exclusively;
  - the calibration test uses a per-process unique name;
  - the 1.1 s sleep that kept names apart is removed;
  - new regression test `test_recording_names_never_collide_across_processes`.
- **Evidence**, pyserial venv, logs in /tmp/hm-flaky*:

| Condition | Runs failed |
|---|---|
| Fresh clone, one loop, before the fix | 0 / 30 |
| Two concurrent loops in one fresh clone, before the fix | 7 / 16 (9 failures, all 404 on a recording download) |
| The same two concurrent loops, after the fix | 0 / 30 |

- **Shared copy after the fix:**
  - system python: 83 passed, 3 skipped, ×3;
  - venv: 86 passed (final confirmation run).
- **Not explained:** a venv batch at 11:45–11:48 IST gave 3–5 failed (plus errors) per app/tests run, and 23
  failed / 34 errors in `tests/`. The next venv run, at about 11:52, gave 86 passed. I captured only the summary
  lines, and per the PM I did not investigate further. `/tmp/hm-venv` is also used by other agents' processes.

## 3. Open limitations
Full text in `app/README.md` → LIMITATIONS (mirrored in the T5 row):
- U0. Heading only by PM decision: no position, coordinate, map, speed, course or distance features. The GPS indicator reads the optional `sample.gps` {fix, num_sat, hdop}; no current source (sim) emits it, so it normally reads Unknown. firmware_bridge's MSP_RAW_GPS path is untested with the app.
- U1. `mag_raw` is optional (CAN-L4-3100 sends scaled field, no raw counts).
- U2. Accuracy shown is precision (noise 1σ), quality and calibration residual, not absolute accuracy; error vs truth exists only for simulated data. Nothing here is hardware-verified.
- U3. The serial path was never run against a real flight controller, a live firmware_bridge session or the CAN-L4-3100; only a non-existent port (FAULT) was exercised.
- U4. Replay labels (D6 fixed in `0ca6b0f`, pending the Auditor's re-run): replayed `hardware` samples become `source:"replay"` + `meta.original_source:"hardware"` and show REPLAY (recorded hardware), never live; a replayed sim log keeps `source:"sim"` and shows SIMULATED. The app trusts `meta.original_source` as written in a file. HARDWARE is shown only for the serial transport, which has never run against a real FC (U3); a `hardware` label via ingest shows UNVERIFIED SOURCE.
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
