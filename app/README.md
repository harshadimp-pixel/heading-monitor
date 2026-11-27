# app/ — Heading-monitor web UI (T5)

Owner: UI & Software Developer. Local browser dashboard for the virtual RM3100 + Matek FC heading monitor.
Python standard library only (no new dependencies), vanilla JS + SVG/canvas, no CDN and no build step.

## Run

```bash
cd /workspace/heading-monitor
python -m app --source sim                     # T3 simulator (default scenario)
python -m app --source sim:tilted_spin         # any scenario listed by `python -m sim --list-scenarios`
python -m app --source replay:path/to/log.jsonl [--speed 2] [--loop]
python -m app --source serial:/dev/ttyACM0 [--baud 115200]   # via firmware_bridge (T4)
python -m app --source ingest                  # accept Samples POSTed to /api/sample
# open http://localhost:8080
```

Other options: `--port 8080` (`--port 0` = OS-assigned ephemeral port, printed in the start-up log), `--host 127.0.0.1 --rate 20 --seed N --sim-duration S --declination DEG --stale 2 --calibration file.json --verified-devices FILE -v`.
`--verified-devices` (default `config/verified_devices.json`, owned by Firmware, ships empty) is the D8 allowlist; the app
reads it AND passes the same file to `firmware_bridge --verified-devices` so both agree.
With `--declination 0` (default) every heading is **magnetic**. A non-zero declination is passed to heading_core,
and the UI then labels headings as true.

Tests (stdlib + pytest; the UI test uses headless Chrome if it is installed, otherwise it is skipped):

```bash
python -m pytest app/tests -q
```

## Architecture

```
 source (one per process)                     app (this package)                         browser
 ───────────────────────                      ──────────────────                         ───────
 sim[:scenario]  -> `python -m sim ... --realtime`  ┐
 replay:<file>   -> JSONL file reader (paced by t)  ├─> Sample ─> hub.emit ─> validate ─> core_adapter ─> record ─┐
 serial:<port>   -> `python -m firmware_bridge ...` │         (contracts/       (required    (heading_core       │
 ingest          -> POST /api/sample               ┘          sample.schema)    fields)      HeadingEstimator)  │
                                                                                                                 v
                              history ring (6000) · calibration wizard · recorder (CSV/JSONL) · reference heading
                                                                                                                 │
                              Broadcaster (10 Hz) ── WebSocket /ws ──> static/app.js (compass, charts, tables) <─┘
                                                     REST /api/*   <── buttons (reference, calibration, record, test)
```

| File | Purpose |
|---|---|
| `__main__.py` | CLI (`python -m app`) |
| `sources.py` | sim / replay / serial / ingest sources; Sample validation |
| `core_adapter.py` | the only place heading_core is called (`Calibration.fit/from_dict/to_dict`, `HeadingEstimator.update`) |
| `_stubs.py` | **LOCAL STUBS**, used only while a team module is missing or raises `NotImplementedError` |
| `hub.py` | state, history, accuracy/noise estimate, sensor status, calibration wizard, recorder, CSV |
| `server.py` | stdlib `ThreadingHTTPServer` + minimal RFC 6455 WebSocket (server→client push) |
| `static/` | `index.html`, `style.css`, `app.js` (UI), `headingmath.js` (display maths, unit tested in Node) |
| `tests/` | HTTP/WebSocket smoke tests, heading maths tests, adapter tests, headless-Chrome DOM test |

### Integration with the other teams (ARCHITECTURE.md interfaces only)
* **heading_core (T2):** `HeadingEstimator(calibration, declination_deg).update(sample)` gives each HeadingEstimate.
  `Calibration.fit(samples)` runs the wizard, and `to_dict/from_dict` handles save and load. If a call raises
  `NotImplementedError`, the stub answers instead, and the UI shows `heading estimator: STUB`. Any other exception from
  heading_core is shown as an error (sensor status FAULT). It is never hidden by falling back to the stub.
* **sim (T3):** started as `python -m sim --rate R --duration 86400 --realtime [--scenario S] [--seed N]`. If the module is
  missing (or exits with `NotImplementedError` before emitting anything), `_stubs.StubSim` is used. Its samples still say
  `source:"sim"`, and the transport line shows `STUB`.
* **firmware_bridge (T4):** started as `python -m firmware_bridge --port P --baud B`. **Never stubbed.** If it is missing
  or fails, the UI shows FAULT / NO DATA and every value reads Unknown.

## What the UI shows

| Panel | Contents |
|---|---|
| Header | **DATA SOURCE badge**, derived from the latest sample's `source` field (plus `meta.original_source`; see D6 below): SIMULATED (`sim`), REPLAY (recorded hardware) (`replay` + original_source `hardware`), REPLAY (recorded simulator), REPLAY, and **ALLOWLISTED DEVICE (identity not authenticated)** (formerly HARDWARE; label decision d5374a1) only for `hardware` samples from the app's own serial source whose device is verified (D8: bridge `meta.provenance == "verified"` AND the reported UID is in the app's allowlist), with the banner "Live serial device whose self-reported UID is on the local allowlist. The UID is not cryptographic proof; this is not hardware verification." Internally such samples stay `source: "hardware"`, `device_status: "verified"`. Every other `hardware` sample (serial unverified, ingest) shows UNVERIFIED SOURCE and is never presented as live. Over serial, the device's board, variant, target and UID are shown under the badge, each labelled "reported by device". NO DATA when nothing current exists. The transport (CLI `--source`) is shown in small text. An evidence banner follows the badge; for replayed data it says the data is recorded, not a live sensor stream. |
| Heading | SVG compass rose: ticks every 10°, numbers every 30°, N/E/S/W. It has three distinct indicators: measured heading needle in cyan (heading_core `heading_deg`: filtered estimate, using the calibration when one is applied), unfiltered needle in grey (heading_core `heading_raw_deg`: instantaneous, before smoothing), and the reference marker as an amber dashed line with a rim triangle. Below it: the numeric measured and unfiltered heading with a 16-point cardinal; calibration state is shown in the status panel and \|B\| raw vs calibrated in the field panel; a reference heading input with slider, "use current", clear, or click on the rose; and the signed deviation (measured − reference) wrapped to (−180, 180]. |
| Sensor status & accuracy | Status: OK / DEGRADED / FAULT / STALE / NO DATA, with the reason. Also: last-sample age, rate, accepted/invalid counts, heading_core quality (0–1) with quality bar, short-term noise 1σ, calibration state and residual, error versus sim truth (simulated data only), and warnings. |
| Roll / pitch | Artificial-horizon canvas plus numbers, taken from the HeadingEstimate. |
| GPS availability (status only) | A read-only indicator driven only by the optional `sample.gps` object `{fix, num_sat, hdop}`. It shows Available (2d/3d fix), Unavailable (fix `none`) or **Unknown** (gps absent, fix `unknown`, invalid gps object, or stale data), plus Fix, Satellites and HDOP, each Unknown when not reported. There are no coordinates, map, speed, course or distance anywhere in the app. |
| Magnetic field | Bx/By/Bz (µT, body frame), raw and calibrated \|B\|, and a time plot of the 3 axes plus \|B\|. `mag_raw` (RM3100 counts) is **optional**: it is shown when a sample carries it, otherwise it reads Unknown. The CAN-L4-3100 / DroneCAN stream never carries it. |
| Heading history | Time plot of measured, unfiltered, reference and sim truth (30 s – 5 min), with gaps where data is missing. Below it, a table of the last 20 samples. |
| Calibration wizard | Start/stop collecting, live coverage (12 yaw bins, 8 axis-sign octants), **Fit** (heading_core `Calibration.fit`), review the parameters, Apply / Remove, Save JSON (`app/calibrations/`), Download, Load a saved file, Upload JSON. A bad file keeps the previous calibration. |
| Recording & export | **Export history CSV** (in-memory ring) · Record CSV or JSONL to `app/recordings/` with download links (unique names `rec-<date>-<time>-<ms>-p<pid>-<n>.csv|jsonl`, never overwritten). JSONL recordings are the original contract Samples, so they can be replayed with `--source replay:`. |
| Test controls (app-side) | Pause intake / inject a 5 s dropout. These drop samples inside the app to exercise Unknown/stale handling, and are labelled as such. |

### Heading only
This app shows **heading only**: orientation, i.e. the direction the sensor's forward (x) axis points, clockwise from
magnetic north (true north only if a declination is configured). It comes from the magnetometer and is
tilt-compensated with the accelerometer. Heading is orientation, not movement or position. A vehicle can point one
way and travel another (wind, drift, reversing). The app has no position, coordinate, map, speed, course or
distance features (PM decision, 2026-11-27). It keeps only one GPS availability status indicator, because the
owner asked for GPS availability. It is fed only by `sample.gps` {fix, num_sat, hdop} and shows Unknown when not reported.

### Unknown / stale rules
* A value that was not measured, not reported, or is older than **2 s** (default; `--stale S`) is shown as **Unknown**,
  never as 0. When a stale value exists, the last value is shown in a separate "STALE: last value … at hh:mm:ss
  (not current)" line, and the badge switches to NO DATA.
* A lost WebSocket connection also makes everything Unknown.
* CSV: an empty cell means unknown or not reported. `gps_status` is `available` / `unavailable` / `unknown`.

## Data interfaces

### Sample in (contracts/sample.schema.json, unchanged)
Required: `t` (s, monotonic), `source` (`sim|replay|hardware`), `mag_uT` [3]. Optional: `accel_g`, `gyro_dps`,
`mag_raw` (3 ints, **absent on the CAN-L4-3100 hardware stream**; validated only if present), `rm3100_cycle_count`, `fc_attitude_deg`, `truth` (sim only), `meta`, `gps` {fix: none|2d|3d|unknown, num_sat ≥ 0 int, hdop ≥ 0}. Invalid samples are counted and
rejected (missing fields, wrong source enum, non-finite vectors). An invalid `gps` object does **not** reject the heading
sample: GPS is shown as Unknown, `counts.gps_invalid` is incremented and the error is shown in the UI.

`POST /api/sample` (only with `--source ingest`) takes one Sample or a JSON array of Samples.
It returns 200 `{"ok":true,"accepted":n}`, 422 with per-sample errors, or 409 if the app is not in ingest mode.
```bash
curl -X POST localhost:8080/api/sample -H 'Content-Type: application/json' \
  -d '{"t":0.0,"source":"sim","mag_uT":[26.0,-15.0,40.0],"accel_g":[0,0,-1]}'
```

### Out
* `GET /ws` (WebSocket). Message types: `hello` (status plus up to 1500 recent records), then `update` at 10 Hz
  (status plus new records). Record fields: `seq, recv_ms, recv_time_iso, t, source, mag_uT, accel_g,
  field_raw_uT, heading_deg, heading_raw_deg, roll_deg, pitch_deg, field_uT, calibrated, quality, warnings,
  noise_1sigma_deg, reference_deg, deviation_deg, truth_heading_deg, sim_error_deg, sensor_status,
  estimator_backend, error, gps_status, gps_fix, gps_num_sat, gps_hdop, gps_error, mag_raw, rm3100_cycle_count`. `null` means unknown.
* `GET /api/health` (liveness), `GET /api/status`, `GET /api/history?since=<seq>`, `GET /api/export.csv`.
* `POST /api/reference {"deg": number|null}`, `POST /api/control {"paused": bool} | {"dropout_s": n}`.
* `POST /api/calib/{start,stop,fit,apply,clear,save,load}`, `GET /api/calib/{list,current}`.
* `POST /api/record/{start,stop}` (`{"format":"csv"|"jsonl"}`), `GET /api/recordings`, `GET /recordings/<name>`.

### D6: replayed hardware is never shown as live (ARCHITECTURE.md, PM decision 2026-11-27)
* `--source replay:<file>`: every sample with `source:"hardware"` is relabelled on read to `source:"replay"`, with
  `meta.original_source:"hardware"` and `meta.replayed_from:<file>` (the same fields `firmware_bridge --replay` sets;
  `app/sources.py: relabel_replayed_sample`). Other meta keys are kept. Samples with `source:"sim"` or `"replay"` are
  not changed, so a replayed sim log still shows SIMULATED.
* Each history/WebSocket record carries `source` (after relabelling), `original_source` (copied from
  `meta.original_source`, never inferred), `transport` (`sim|replay|serial|ingest`, from `--source`) and
  `live_hardware` (true only for `source:"hardware"` via `serial`).
* Recordings keep the relabelled data: CSV has `source`, `original_source`, `transport` columns; JSONL stores the
  relabelled Sample including `meta.original_source`.
* `ingest` keeps `sample.source` as posted (contract), but a `hardware` sample via ingest shows UNVERIFIED SOURCE
  and a banner saying it is not a live serial source.

### D8: a serial connection is not proof of hardware (ARCHITECTURE.md D8; contract docs/firmware/D8_PROVENANCE.md)
Applied by the hub to every sample on the serial transport (`app/provenance.py`), in order:
1. device reports `fc_variant == "SIML"` or `board_id == "SIMF"`, or `meta.provenance == "simulated"`, or `source == "sim"`
   → SIMULATED (a `hardware` label is mapped to `sim`, `meta.source_mapped_from: "hardware"`). Wins over the allowlist.
2. no `meta.device_identity` → UNVERIFIED SOURCE (`device_status: no_identity`)
3. no valid UID (24 hex) → UNVERIFIED (`no_uid`)
4. UID not in the allowlist → UNVERIFIED (`uid_not_listed`)
5. UID listed but the bridge did not set `meta.provenance: "verified"` (or set nothing, e.g. an older bridge) →
   UNVERIFIED (`bridge_unverified`)
6. otherwise → **ALLOWLISTED DEVICE (identity not authenticated)** (`device_status: verified`, `live_hardware: true`). "Verified" here means only that the
   self-reported UID is on an administratively trusted list (F11): not hardware authentication.

**Trust boundary (D8 hardening).** The sample's own claims are never trusted. `meta.provenance: "verified"`,
`meta.live_hardware`, or top-level `live_hardware` / `device_verified` / `transport` / `device_status` in a sample
cannot make it allowlisted. The server builds each record from a fixed whitelist and computes `transport`,
`device_status`, `device_verified` and `live_hardware` itself.

Verification needs both of these:
1. The sample arrived through `hub.source_emit`. That is the callable `__main__` hands only to the app's own
   source, so for a serial hub it is the app's own `firmware_bridge` subprocess.
2. The app re-checks the reported UID against its own allowlist (`--verified-devices`).

A serial-hub sample that reaches `hub.emit` any other way gets `device_status: untrusted_channel` and is not verified.
The bridge's `provenance: "verified"` is an extra necessary condition (rule 5). It can only remove the allowlisted
badge, never grant it.

The frontend's `badgeInfo` takes only the server-computed `record.transport` and `record.device_verified`. It never
reads `meta`, `provenance` or `live_hardware`.

**Label (Auditor decision, accepted by the PM in d5374a1).** The badge reads "ALLOWLISTED DEVICE (identity not authenticated)". It is defined once, as
`HARDWARE_LABEL` in `static/headingmath.js`; the banner text is `ALLOWLISTED_BANNER` in the same file. The plain word
HARDWARE is no longer ever displayed. `badgeLabel`/`SOURCE_LABEL` remain only as the contract source-name map
(`hardware` → "HARDWARE"), which the Auditor's `tests/test_t6_app.py` checks; the page never shows it. The badge
uses smaller type for this label and may wrap to two lines; it was checked at 1440 px and 700 px wide (no overflow).
The allowlist is read with `firmware_bridge.identity.load_allowlist` (fail closed: missing/malformed = empty); a
fail-closed mirror is used only if that module is not importable. `/api/status` shows `verified_devices` (path, count,
loader) and `source_status.command` (the bridge command line, including `--verified-devices`). Replay (D6) and ingest
never consult the allowlist and are never allowlisted. Records and CSV carry `device_status`, `device_verified` and the
reported `device_board/variant/uid` (CSV `*_reported`).

CSV columns: `recv_time_iso, t, source, heading_deg, heading_raw_deg, reference_deg, deviation_deg, roll_deg,
pitch_deg, bx_uT, by_uT, bz_uT, field_raw_uT, field_cal_uT, calibrated, quality, noise_1sigma_deg, warnings,
sensor_status, estimator_backend, truth_heading_deg_sim_only, gps_status, gps_fix, gps_num_sat, gps_hdop, mag_raw_x, mag_raw_y, mag_raw_z, original_source, transport, device_status, device_verified, device_board_reported, device_variant_reported, device_uid_reported`
(the `mag_raw_*` cells are empty when the sample has no raw counts).

## Tests (run 2026-11-27, real results)
`python -m pytest app/tests -q` gives **52 passed**, about 24 s per run, after the D6 fix (2026-11-27, about 01:01–01:09 IST):
three consecutive full runs 52/52, and `test_app_ui_headless.py` 5 consecutive runs 5/5. Whole repo `python -m pytest -q`:
512 passed, 45 skipped; `tests/` (T6): 111 passed. The Auditor's `reports/audit/integration_run.py` run with output to
/tmp gave 27/27, including A8 and A8b. Before D6 (commit 41bb756): 45 passed, also on a fresh clone in a fresh venv
(see `INSTALL.md`, Verification log).
`app/tests/test_app_ui_headless.py` passed 10 consecutive times (3/3 each, about 4 s). The auditor's
`tests/test_t6_app.py` and `tests/test_t6_claims.py` give 14 passed. `test_sim_duration_end_goes_stale` checks that
when the sim ends (`--sim-duration`) the app goes stale and shows Unknown. Label semantics: "Measured heading" is the
filtered estimate (`heading_deg`). "Unfiltered" is `heading_raw_deg`, the instantaneous value before smoothing, and
it is calibrated whenever a calibration is applied.
Environment: Python 3.13.5, pytest 9.2.0, Node 24 for the JS mapping tests, google-chrome headless for the 5 DOM tests.
Every test starts its own app with `--port 0` (OS-assigned ephemeral port, read back from the start-up log line), never 8080.
The headless smoke tests need no browser:
* start-up, `GET /` and `GET /api/health` (`test_sim_source_serves_ui_and_streams`)
* samples from the real sim over WebSocket (`test_sim_source_serves_ui_and_streams`, `test_badge_matches_sim_source_over_websocket`)
* the badge equals `sample.source` for every pushed record in a mixed sim/replay/hardware sequence, checked on the
  server payload and through the frontend `badgeLabel` mapping run in Node
  (`test_badge_always_equals_sample_source_for_every_pushed_record`)
* calibration fit → apply → save → clear → load (by name and by uploaded JSON), with an exact JSON round-trip
  (`test_calibration_wizard_fit_apply_save_load`)
* GPS availability: absent → Unknown, present → fix/satellites/HDOP passed through, invalid → heading kept and GPS
  Unknown, stale → Unknown, plus CSV columns and CSV/JSONL recordings (`test_gps_availability_absent_present_invalid`,
  `test_gps_in_recordings`); rendered values in headless Chrome (`test_gps_indicator_renders_fix_sats_hdop`)
* D6 (`test_app_d6_replay.py`): the relabel uses the same fields as `firmware_bridge.bridge.replay`; app replay of a
  hardware JSONL gives `source:"replay"` + `original_source:"hardware"` in history, CSV and JSONL recordings; a sim
  replay is unchanged; ingest `hardware` is not live; the frontend `badgeInfo` mapping in Node. In headless Chrome:
  badge `REPLAY (recorded hardware)` with a banner that does not contain "Live"
  (`test_d6_replayed_hardware_log_shows_replay_badge_not_live`), and a replayed sim log stays SIMULATED.
* D8 (`test_app_d8_serial_provenance.py`):
  * allowlist loader fails closed; the shipped allowlist is empty;
  * every serial rule: verified, `uid_not_listed`, `no_uid`, `no_identity`, `bridge_unverified`, and SIML/SIMF → sim;
  * records and CSV;
  * the default allowlist never gives the allowlisted badge;
  * replay and ingest are unchanged;
  * the bridge command line carries `--verified-devices <same file>`;
  * `test_e2e_virtual_pty_allowlist_mechanism_and_F11_spoof_limitation_not_hardware_validation` (D9; 3 cases):
    the real bridge on a virtual pty driven by the bridge's FakeFC script. It demonstrates the allowlist mechanism
    and the spoofable-UID limitation F11 (a script reporting an allowlisted UID gets the allowlisted badge). It is
    NOT hardware validation. These cases skip without pyserial.
* D8 hardening (`test_app_d8_forged_claims.py`): samples claiming `provenance:"verified"` and `live_hardware:true`,
  with an allowlisted UID:
  * ingested → UNVERIFIED SOURCE;
  * replayed hardware → `REPLAY (recorded hardware)`;
  * simulated (ingest, replay or serial) → SIMULATED;
  * serial with a UID not in the app's allowlist → UNVERIFIED;
  * serial outside the app's own source → `untrusted_channel`;
  * serial with an allowlisted UID → ALLOWLISTED DEVICE (identity not authenticated).
  It also checks that the record never copies sample claims, that `app.js` reads no sample-claim fields, and that the
  label is a single constant.
* Headless Chrome D8 checks: `test_d8_serial_badges_and_reported_by_device_labels` and
  `test_d8_forged_ingest_claims_show_unverified`.
* Flaky-suite fix (2026-11-27, `test_recording_names_never_collide_across_processes`):
  * **Root cause:** recordings were named per second (`rec-YYYYmmdd-HHMMSS`) in the shared `app/recordings/`, and the
    calibration test used the fixed name `pytest_tmp_cal`. Two test runs overlapping in one checkout, each starting
    a recording in the same second, got the same file. One run truncated or deleted the other's, and the download
    returned 404 in `test_replay_of_hardware_log_is_relabelled_and_recorded` / `test_gps_in_recordings`.
  * **Fix:** names now carry a millisecond stamp, the process id and a per-process counter
    (`rec-YYYYmmdd-HHMMSS-mmm-p<pid>-<n>`), and the file is opened exclusively. The calibration test uses a per-process
    unique name. The 1.1 s sleep that kept names apart is gone.
  * **Evidence**, venv with pyserial, two app/tests loops at once in the same fresh clone:
    * before the fix: 7 of 16 runs failed (9 failures, all HTTP 404 on a recording download);
    * after the fix: 0 of 30 runs failed;
    * a fresh clone alone, before the fix: 0 of 30 runs failed.
    * after the fix, shared checkout: 83 passed / 3 skipped ×3 (system python), 86 passed (venv). One venv batch at
      11:45–11:48 IST had unexplained failures that did not recur (see reports/contributions/ui.md).
* `mag_raw` optional (`test_mag_raw_is_optional`), Unknown/stale (`test_ingest_unknown_until_data_then_stale_...`),
  replay + CSV export, JSONL recording, serial without hardware gives FAULT with no fabricated data, heading maths and
  wrap/deviation, stub fallback versus real-module errors.

The headless-Chrome DOM tests are deterministic:
* Chrome is driven over the DevTools protocol (stdlib only, `app/tests/_cdp.py`) on the **real clock**. There is no
  `--virtual-time-budget` fast-forward. That fast-forward had made data look stale and caused an occasional
  NO DATA failure.
* Each test waits, with a bounded timeout of 15 s, until `window.__hmProbe().renderedSeq` reaches the seq of a specific
  sample. It then reads the DOM once and asserts. The retry/wait covers readiness only, never the assertions.
* A third DOM test checks that stale data renders Unknown and NO DATA (`--stale 1`).

## LIMITATIONS
0. **Heading only (PM decision 2026-11-27).** Position, coordinates, map, speed, course-over-ground and distance
   features were removed. Only a read-only GPS availability indicator remains. It is wired to the optional
   `sample.gps` object {fix, num_sat, hdop} (PM decision, commit 9d0552f). The contract has no coordinates and the app
   shows none. Neither the T3 sim nor any other current source emits `gps`, so in normal runs the indicator reads
   Unknown. The app does not fake GPS data. MSP_RAW_GPS wiring in firmware_bridge is T4 scope and untested here.
1. **`mag_raw` is optional.** The real hardware is a Matek CAN-L4-3100 (RM3100 behind AP_Periph, DroneCAN), whose
   stream carries scaled field, not raw counts. The app works without `mag_raw`, shows it only when present, and rejects
   malformed values (422) rather than crashing.
2. **Accuracy is not absolute.** Shown are heading_core `quality`, short-term noise 1σ (from 2nd differences, which
   remove a constant turn rate; precision only), and calibration residual. Error versus truth exists only for
   simulated data. Real absolute accuracy needs an independent reference and is Unknown.
   Nothing here is hardware-verified.
3. **Serial path never run against a real FC.** `serial:` runs `python -m firmware_bridge --port P --baud B` (T4,
   CLI verified compatible via `--help`). It has only been exercised with a non-existent port, where it reports FAULT and no data. It
   has never been run against a real flight controller, a live firmware_bridge session or the CAN-L4-3100.
   Everything here is virtual. The D8 serial path was exercised only with the bridge's FakeFC on a pty (virtual
   serial), never with a physical device.
4. **Replay labels (D6, closed by the Auditor in a88e8d1).** A replayed `hardware` sample becomes `source:"replay"`
   with `meta.original_source:"hardware"` and shows REPLAY (recorded hardware), never live. A replayed sim log keeps
   `source:"sim"` and shows SIMULATED, with the transport shown as replay. The relabel mirrors the three fields of
   `firmware_bridge --replay` rather than importing it, because the bridge's Python helper is not an ARCHITECTURE
   interface (CLI only) and it relabels sim too. The app trusts `meta.original_source` as written in the file; a file
   could claim anything. ALLOWLISTED DEVICE (identity not authenticated) is shown only for a verified serial device (D8, item 11).
5. **Stubs.** `_stubs.py` (min/max hard-iron + diagonal scale calibration, no smoothing, simple quality, simple
   simulator) is used only when the real module is missing or raises `NotImplementedError`. In the current repo state,
   heading_core (T2) and sim (T3) are real and the stubs are **inactive** (the UI shows which backend is in use).
   firmware_bridge is never stubbed.
6. **Calibration wizard is not guided per axis.** It shows coverage (yaw bins / octants) but does not tell the user which
   orientation is missing. A fit on poor coverage (e.g. a pure yaw spin) is rejected by heading_core with its error
   message.
7. **Single source per process.** Switching source means restarting `python -m app`. One process holds port 8080, so
   running a second instance (e.g. T6's U1 test) while one is already running fails to bind.
8. **Local only, no auth.** Binds 127.0.0.1 by default. There is no authentication; do not expose it on a network.
9. **History is in memory** (last 6000 samples ≈ 5 min at 20 Hz). Use recording for longer runs.
10. **UI verification** is automated (HTTP/WebSocket tests plus a headless-Chrome DOM check plus screenshots).
    Human usability has not been assessed. The layout was checked at 1600 px width only.
11. **D8 device identity is self-reported.** Board, variant, target and UID come from the device (MSP) and can be
    spoofed; a UID is not cryptographic proof. The allowlisted badge ("ALLOWLISTED DEVICE (identity not authenticated)", formerly HARDWARE) needs the bridge's
    `provenance: "verified"` AND the UID in `config/verified_devices.json`, which ships empty, so today nothing
    displays it.
    "Verified" means only that a self-reported UID is on an administratively trusted list. It is not
    authentication and not a check that the measurements are valid. Forged claims in the sample itself
    (`provenance`, `live_hardware`) are ignored (tests: `test_app_d8_forged_claims.py`). A process that controls the
    serial device can still report an allowlisted UID; that is outside what the app can detect. Identity is read once at
    connect. The `device_identity` key names follow docs/firmware/D8_PROVENANCE.md; ARCHITECTURE.md D8 does not
    list them. The bridge's Python loader is imported directly although ARCHITECTURE lists only its CLI.
