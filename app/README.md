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

Other options: `--port 8080 --host 127.0.0.1 --rate 20 --seed N --declination DEG --stale 2 --calibration file.json -v`.
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
| Header | **DATA SOURCE badge**: SIMULATED / REPLAY / HARDWARE, mapped only from the latest sample's `source` field. It shows NO DATA when nothing current exists. The transport (CLI `--source`) is shown separately, in small text, and is never used for the badge. An evidence banner follows the source. |
| Heading | SVG compass rose: ticks every 10°, numbers every 30°, N/E/S/W. It has three distinct indicators: measured (calibrated) needle in cyan, raw needle in grey, reference marker as an amber dashed line with a rim triangle. Below it: numeric calibrated and raw heading with a 16-point cardinal; a reference heading input with slider, "use current", clear, or click on the rose; and the signed deviation (measured − reference) wrapped to (−180, 180]. |
| Sensor status & accuracy | Status: OK / DEGRADED / FAULT / STALE / NO DATA, with the reason. Also: last-sample age, rate, accepted/invalid counts, heading_core quality (0–1) with quality bar, short-term noise 1σ, calibration state and residual, error versus sim truth (simulated data only), and warnings. |
| Roll / pitch | Artificial-horizon canvas plus numbers, taken from the HeadingEstimate. |
| GPS availability (status only) | A single read-only indicator: Available / Unavailable / **Unknown**. It is always Unknown today because the Sample contract has no GPS field. There are no coordinates, map, speed, course or distance anywhere in the app. |
| Magnetic field | Bx/By/Bz (µT, body frame), raw and calibrated \|B\|, and a time plot of the 3 axes plus \|B\|. `mag_raw` (RM3100 counts) is **optional**: it is shown when a sample carries it, otherwise it reads Unknown. The CAN-L4-3100 / DroneCAN stream never carries it. |
| Heading history | Time plot of measured, raw, reference and sim truth (30 s – 5 min), with gaps where data is missing. Below it, a table of the last 20 samples. |
| Calibration wizard | Start/stop collecting, live coverage (12 yaw bins, 8 axis-sign octants), **Fit** (heading_core `Calibration.fit`), review the parameters, Apply / Remove, Save JSON (`app/calibrations/`), Download, Load a saved file, Upload JSON. A bad file keeps the previous calibration. |
| Recording & export | **Export history CSV** (in-memory ring) · Record CSV or JSONL to `app/recordings/` with download links. JSONL recordings are the original contract Samples, so they can be replayed with `--source replay:`. |
| Test controls (app-side) | Pause intake / inject a 5 s dropout. These drop samples inside the app to exercise Unknown/stale handling, and are labelled as such. |

### Heading only
This app shows **heading only**: orientation, i.e. the direction the sensor's forward (x) axis points, clockwise from
magnetic north (true north only if a declination is configured). It comes from the magnetometer and is
tilt-compensated with the accelerometer. Heading is orientation, not movement or position. A vehicle can point one
way and travel another (wind, drift, reversing). The app has no position, coordinate, map, speed, course or
distance features (PM decision, 2026-11-27). It keeps only one GPS availability status indicator, because the
owner asked for GPS availability, and that indicator shows Unknown when not reported.

### Unknown / stale rules
* A value that was not measured, not reported, or is older than **2 s** (default; `--stale S`) is shown as **Unknown**,
  never as 0. When a stale value exists, the last value is shown in a separate "STALE: last value … at hh:mm:ss
  (not current)" line, and the badge switches to NO DATA.
* A lost WebSocket connection also makes everything Unknown.
* CSV: an empty cell means unknown or not reported. `gps_status` is the literal `unknown`.

## Data interfaces

### Sample in (contracts/sample.schema.json, unchanged)
Required: `t` (s, monotonic), `source` (`sim|replay|hardware`), `mag_uT` [3]. Optional: `accel_g`, `gyro_dps`,
`mag_raw` (3 ints, **absent on the CAN-L4-3100 hardware stream**; validated only if present), `rm3100_cycle_count`, `fc_attitude_deg`, `truth` (sim only), `meta`. Invalid samples are counted and
rejected (missing fields, wrong source enum, non-finite vectors).

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
  estimator_backend, error, gps_status, mag_raw, rm3100_cycle_count`. `null` means unknown.
* `GET /api/health` (liveness), `GET /api/status`, `GET /api/history?since=<seq>`, `GET /api/export.csv`.
* `POST /api/reference {"deg": number|null}`, `POST /api/control {"paused": bool} | {"dropout_s": n}`.
* `POST /api/calib/{start,stop,fit,apply,clear,save,load}`, `GET /api/calib/{list,current}`.
* `POST /api/record/{start,stop}` (`{"format":"csv"|"jsonl"}`), `GET /api/recordings`, `GET /recordings/<name>`.

CSV columns: `recv_time_iso, t, source, heading_deg, heading_raw_deg, reference_deg, deviation_deg, roll_deg,
pitch_deg, bx_uT, by_uT, bz_uT, field_raw_uT, field_cal_uT, calibrated, quality, noise_1sigma_deg, warnings,
sensor_status, estimator_backend, truth_heading_deg_sim_only, gps_status, mag_raw_x, mag_raw_y, mag_raw_z`
(the `mag_raw_*` cells are empty when the sample has no raw counts).

## Tests (run 2026-11-27, real results)
`python -m pytest app/tests -v` gives **40 passed** in about 10 s (Python 3.13.5, pytest 9.2.0, Node 24 for the JS
mapping tests, google-chrome headless for the DOM test). The headless smoke tests need no browser:
* start-up on a free port, `GET /` and `GET /api/health` (`test_sim_source_serves_ui_and_streams`)
* samples from the real sim over WebSocket (`test_sim_source_serves_ui_and_streams`, `test_badge_matches_sim_source_over_websocket`)
* the badge equals `sample.source` for every pushed record in a mixed sim/replay/hardware sequence, checked on the
  server payload and through the frontend `badgeLabel` mapping run in Node
  (`test_badge_always_equals_sample_source_for_every_pushed_record`)
* calibration fit → apply → save → clear → load (by name and by uploaded JSON), with an exact JSON round-trip
  (`test_calibration_wizard_fit_apply_save_load`)
* `mag_raw` optional (`test_mag_raw_is_optional`), Unknown/stale (`test_ingest_unknown_until_data_then_stale_...`),
  replay + CSV export, JSONL recording, serial without hardware gives FAULT with no fabricated data, heading maths and
  wrap/deviation, stub fallback versus real-module errors.

## LIMITATIONS
0. **Heading only (PM decision 2026-11-27).** Position, coordinates, map, speed, course-over-ground and distance
   features were removed. Only a read-only GPS availability indicator remains, and it is always Unknown because the
   Sample contract has no GPS field. Wiring it needs a PM-approved optional field (e.g. `gps_fix`). No fields were
   invented.
1. **`mag_raw` is optional.** The real hardware is a Matek CAN-L4-3100 (RM3100 behind AP_Periph, DroneCAN), whose
   stream carries scaled field, not raw counts. The app works without `mag_raw`, shows it only when present, and rejects
   malformed values (422) rather than crashing.
2. **Accuracy is not absolute.** Shown are heading_core `quality`, short-term noise 1σ (from 2nd differences, which
   remove a constant turn rate; precision only), and calibration residual. Error versus truth exists only for
   simulated data. Real absolute accuracy needs an independent reference and is Unknown.
   Nothing here is hardware-verified.
3. **Serial path untested against hardware.** `serial:` runs `python -m firmware_bridge --port P --baud B` (T4,
   CLI verified compatible via `--help`). It has only been exercised with a non-existent port, where it reports FAULT and no data. It
   has not been run against a real bridge, FC or CAN-L4-3100. Everything here is virtual.
4. **Replay keeps the original `source`.** A JSONL file recorded from the simulator still says `source:"sim"`, so the
   badge shows SIMULATED while the transport line shows `replay`. This follows the "badge from sample.source only"
   rule. A replayer that rewrites `source` to `replay` belongs in T3/T4/PM scope.
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
