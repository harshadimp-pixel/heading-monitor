# Virtual Heading Monitor (RM3100 + Matek FC)

Shared project repository for the AI drone research team. Coordinator: Project Manager & CTO.

Goal: a working **virtual** heading-monitoring application built around our existing PNI RM3100
magnetometer and Matek flight controller. "Virtual" means it must run end to end on simulated or
replayed data today, and accept real FC telemetry through the same interface when hardware is attached.

**Acceptance boundary (virtual only):** current acceptance covers simulated and replayed data only. No physical flight hardware has been operated, the app does not provide autonomous navigation (compass heading only), and no paid services have been used. Status: **CONDITIONAL PASS: corrections in progress, pending independent Codex re-verification.** See `reports/FINAL_REPORT.md` and `PROJECT_STATUS.md`.

Install: follow `INSTALL.md`. Prerequisites (Python, venv, `requirements.txt`, optional pyserial, and the headless Chrome/Chromium used by the UI tests) are recorded in `docs/INSTALL_PREREQS.md`.

## Layout
| Path | Owner | Contents |
|---|---|---|
| `docs/hardware/` | Hardware Research Engineer | RM3100 + Matek FC facts, wiring, sources |
| `heading_core/` + `docs/math/` | Mathematics & Sensor Scientist | heading math, calibration, filtering |
| `sim/` | Simulation Developer | RM3100/FC sensor simulator emitting the sample contract |
| `firmware_bridge/` + `docs/firmware/` | Firmware Specialist | FC config, MSP/MAVLink telemetry reader emitting the sample contract |
| `app/` | UI & Software Developer | the heading-monitor application (backend + UI) |
| `tests/` + `reports/` | Testing & Technical Auditor | independent tests, audit and verification reports |
| `contracts/`, `TEAM_TRACKER.md`, `ARCHITECTURE.md` | PM & CTO | interfaces, tracker, decisions |

See also TEAM_RULES.md (owner rules, binding).

## Ground rules (non-negotiable)
1. **Evidence labelling.** Every performance claim is tagged `[SIMULATED]`, `[REPLAYED]`, `[DATASHEET]`
   or `[HARDWARE-VERIFIED]`. `[HARDWARE-VERIFIED]` requires a raw log from the physical RM3100/Matek
   FC committed under `reports/hardware_logs/` plus the auditor's sign-off. Nobody on this team has
   that yet, so no claim may carry it.
2. The UI must show the active data source at all times. The badge is derived from the sample's `source` field plus provenance (transport, self-reported device identity, allowlist match, and `meta.original_source` where present). A serial connection is not proof of hardware. HARDWARE requires a live serial sample whose device UID is in `config/verified_devices.json` (the file ships empty). A simulator that reports `SIML`/`SIMF` is shown as SIMULATED; any other unknown serial device is UNVERIFIED SOURCE. Replayed hardware is shown as 'REPLAY (recorded hardware)'; hardware via ingest is UNVERIFIED SOURCE; otherwise SIMULATED, REPLAY, or NO DATA.
3. Stick to the interfaces in `contracts/`. Changes go through the PM (note it in TEAM_TRACKER.md).
4. Python 3.10+, standard tooling (`pip install -r requirements.txt`, `pytest`). Keep deps small.
5. Update your row in `TEAM_TRACKER.md` when you start, block, or finish. Commit with your role as prefix,
   e.g. `git commit -m "[sim] add noise model"`.
6. Never purchase anything or sign up for paid services; raise it with the PM.
