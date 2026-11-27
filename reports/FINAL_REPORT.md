# Final report — Virtual Heading Monitor (RM3100 + Matek FC)

**Acceptance boundary (virtual only):** Acceptance in this report covers **simulated and replayed data only**. No physical flight hardware was operated. The application does not provide autonomous navigation (it reports compass heading only). No paid services were used.

**Status of this document:** **CONDITIONAL PASS: corrections in progress, pending independent Codex re-verification.** An independent Codex audit of commit `f1a0e3e` issued a CONDITIONAL PASS for the virtual scope. This revision records the Priority-2 documentation corrections (R8/D7/D8 wording, skipped-test inventory, install prerequisites, and this boundary). Priority-1 serial provenance (D8) is being applied by firmware and UI and has not yet been independently re-verified. Individual module suites being green was never treated as sufficient for completion, and completion is not declared unconditional until Codex re-verifies the corrections.

**Repository:** https://github.com/harshadimp-pixel/heading-monitor (visibility last confirmed PRIVATE by the PM via `gh repo view`; an unauthenticated request returns 404, which is consistent with private. Do not change visibility).
**Auditor-executed results** quoted below remain those recorded at commits `0c25062` (suites and claims audit) and `f058c9a` (integration 30/30), as written in `reports/verification_report.md` (FINAL v3.0) and `TEST_RESULTS.md`, with the D7 close addendum in `02c0ec0`. Those figures are the last completed official QA, not a post-D8 result.
**PM documentation update** (this revision): 2026-11-27, after the Codex review of `f1a0e3e` and the D8 decision in `1bef73e`. The PM also re-ran `python3 -m pytest -q -rs` on the tree at `1bef73e` and obtained **513 passed, 44 skipped** in 139.51 s, matching `reports/audit/skipped_tests.md`.

**Evidence labels used here:** `[SIMULATED]`, `[REPLAYED]`, `[DATASHEET]`. No result in this project carries a hardware-verified evidence label: `reports/hardware_logs/` does not exist (`reports/verification_report.md`).

**Last completed Auditor verdict (virtual scope only, v3.0 / v3.1):** PASS, with project completion then approved for the virtual (simulated and replayed) scope. Hardware performance is not verified. That wording is quoted in §9. It is **superseded as the current project status** by the Codex CONDITIONAL PASS and the D8 corrections still in progress.

---

## Executive summary

The application is a **virtual magnetic-heading monitor** for a PNI RM3100 magnetometer on a Matek CAN-L4-3100 (AP_Periph) module, intended to attach later to a Matek flight controller. It runs end to end on the T3 simulator and on recorded-log replay. The live MSP serial path has been exercised against a missing port, a fake flight controller, and (as a documented limitation) a virtual pty; it has **not** been run against a real flight controller.

The Testing & Technical Auditor's last completed official verification (v3.0, about 01:30 IST on 2026-11-27, D7 closed in v3.1 / `02c0ec0`) was **PASS for the virtual scope only**, with project completion then approved for that scope (`reports/verification_report.md`). Per-deliverable verdicts at that time: T1–T5 **PASS**; PM docs **PASS** (D7 subsequently CLOSED). Nothing is physically confirmed on hardware. After the Codex audit of `f1a0e3e`, the current status is **CONDITIONAL PASS: corrections in progress, pending independent Codex re-verification**.

Of the agreed requirements (`REQUIREMENTS.md` R1–R8, N1–N6), the Auditor traces **13 as delivered** in the virtual scope, **1 as partial** (R6: live MSP to a real Matek FC was never run), and **0 as not delivered** (`reports/audit/traceability.md`).

The latest independent whole-repo run, at `0c25062`, is **513 passed, 44 skipped, 0 failed** (`python -m pytest -q -rs`; `TEST_RESULTS.md`). Integrated end-to-end testing at `f058c9a` is **30/30 PASS**, including tightened A8/A8b and new edge cases A10a–c (`reports/audit/integration_results.md`). Defect **D6 (CRITICAL) is CLOSED**: a replay of recorded hardware now shows **REPLAY (recorded hardware)** and a banner that the data is not live.

**D7 (MINOR, documentation)** is **CLOSED**: `REQUIREMENTS.md` R8, README rule 2 and `CHANGELOG.md` were updated in `2564266` and re-checked by the Auditor (`02c0ec0`). **D8** (Priority 1, Codex audit of `f1a0e3e`) then changed R8 again: the badge is derived from `sample.source` plus provenance, and HARDWARE requires an allowlisted verified device. D8 is **in progress** (decision `1bef73e`; firmware/UI implementation and the Auditor's A10c rewrite are outstanding). It supersedes limitation L-SER.

A PM smoke test on ephemeral ports (8080 was not used) confirmed a live `sim:tilted_spin` session with `latest_sample_source="sim"` and a numeric heading, and a replay of a simulated example log that kept `source="sim"` (badge SIMULATED) with transport `replay` and a numeric heading. The PM re-ran `python3 -m pytest -q` and obtained **513 passed, 44 skipped** in 133.01 s, matching the Auditor's official count.

Open limitations that remain in force include **L-D3** (a frozen quantised magnetometer can go undetected when still, slower than 1°/s, or in a level turn with no gyro). **L-SER** (a virtual serial port fed by the fake FC shown as HARDWARE) is **superseded by D8**, which is in progress: a serial connection is not proof of hardware; a fake FC must show SIMULATED; an unknown serial device must show UNVERIFIED SOURCE; HARDWARE requires a UID in `config/verified_devices.json` (ships empty). Until D8 lands and is re-tested, the pre-D8 committed code can still exhibit the L-SER behaviour. Hardware validation items HV1–HV9 are all **NOT RUN**. Development spend reported by every contribution file is **none**, with **no paid tools or services**. Platform subscription costs are outside this project's scope and were not tracked.

This application monitors **compass heading only**. It does not measure movement, geographic position or navigation (see the section immediately below).

---

## Compass heading versus movement, position and navigation

This application measures **only compass heading**: the orientation of the magnetometer’s x-axis (the body forward axis, projected on the horizontal plane) relative to **magnetic north**. It reports **true north only if a magnetic declination is configured** as a user constant (`REQUIREMENTS.md` R4; `docs/math/HEADING_MATH.md` §1; `app/README.md` LIMITATIONS 0).

It does **not** measure:

- movement or speed
- track or course over ground
- geographic position
- navigation, path, or a map

A vehicle can point one way and travel another. Heading is the direction the nose points; course over ground is the direction of travel. Those are different quantities, and this software computes only the first (`docs/math/HEADING_MATH.md` §1).

The GPS indicator, when present, shows **only fix status, satellite count and HDOP**. The sample contract has **no coordinates**, and the app shows none (`app/README.md` LIMITATIONS 0; `firmware_bridge` drops or zeroes lat/lon/alt/speed/course — `docs/firmware/FC_SETUP.md` L10; checklist HV9). A missing, invalid or stale `gps` object is shown as Unknown. The simulator does not emit `gps`, so in normal simulated runs the indicator reads Unknown.

`heading_core` does not provide a position, displacement or distance feature. Figures that turn a heading error into a path error are analysis only, not a product capability (`docs/math/HEADING_MATH.md` §13 items 16–17).

---

## 1. Original requirements versus delivered functionality

Source of the requirements: `REQUIREMENTS.md` (agreed v1.0, 2026-11-26; R8 wording first clarified for D7 on 2026-11-27, then updated again for D8 — see `CHANGELOG.md` and the R8 / D7 / D8 note below). Traceability in the table is the Auditor’s independent check at `0c25062`: `reports/audit/traceability.md`, which still describes the pre-D8 / D7-pending text. Every “Delivered” status below is **for the virtual scope only** ([SIMULATED] / [REPLAYED]). Nothing in the traceability table is physically confirmed on hardware. R8 behaviour is being tightened by D8 and is not re-verified yet.

| Req | Requirement (short, from `REQUIREMENTS.md` as audited) | Auditor status | Evidence cited by the Auditor |
|---|---|---|---|
| R1 | Live magnetic heading 0–360°, numeric value and compass rose | **Delivered** [SIMULATED] | H1–H3; integration A1 (8 scenarios, headings in [0, 360)); U3 display rounding; A9a `headingValue='30.8° NNE'`; SVG compass in `index.html` |
| R2 | Tilt-compensate heading using accelerometer/attitude; show roll and pitch | **Delivered** [SIMULATED] | H4 ≤ 0.1° up to ±30° tilt; H5 noisy RMSE 0.628°; A1 tilted_spin 0.41° (uncalibrated, no iron, at `f058c9a`); `rollValue`/`pitchValue` rendered. FC attitude/INAV axis signs are [SOURCE-CODE], not checked on hardware |
| R3 | Hard-iron and soft-iron ellipsoid calibration, in-app wizard, save/load | **Delivered** [SIMULATED] | C1–C5; integration A5: collect 304/300 → fit offset (11.85, −8.11, 4.99) vs truth (12, −8, 5) µT → apply (0.72° RMSE) → save/list/clear/load |
| R4 | Optional magnetic declination to report true heading | **Delivered** [SIMULATED] | H6; app `--declination` labels heading as true. Declination is a user constant; there is no WMM model (documented limitation) |
| R5 | Field magnitude, 3-axis field, heading-quality indicator and warnings | **Delivered** [SIMULATED] | E2; U4; A9b; A1b (76/76 samples with > 5° error carried a warning); A6; D3 re-test E3b–E3g |
| R6 | Interchangeable sources via one Sample contract: simulator, recorded-log replay, live Matek FC over MSP (USB serial) | **Partial** | sim: A1 8/8. replay: A2 7/7, A3b. MSP path: A3a/A4 against `--fake-fc` and M1–M4. **Live MSP over USB to a real Matek FC was never run** (BLOCKERS B1). A7: a missing port gives FAULT and no fabricated data |
| R7 | Record sessions to JSONL/CSV | **Delivered** [SIMULATED] | U5; covered by the owner's app tests (52 at `0c25062`), re-run by T6. T6 did not drive the record buttons itself |
| R8 | Persistent DATA SOURCE badge derived from the sample's `source` field plus provenance; HARDWARE requires an allowlisted verified device (current wording — see the D7/D8 note below) | **Delivered** for the D6/D7 behaviour [SIMULATED]; **D8 wording is now in REQUIREMENTS.md, implementation and re-test pending** | D7 CLOSED in `02c0ec0`. D6 CLOSED: A8/A8b replayed hardware → source=replay, `meta.original_source=hardware`, badge 'REPLAY (recorded hardware)', not-live banner; A10a cannot be bypassed; A10b ingest hardware → UNVERIFIED SOURCE, never live. The v3.0 A10c observation (virtual pty shown as HARDWARE, L-SER) is **not** the D8 rule. D8: a serial connection is not proof of hardware; SIML/SIMF → SIMULATED; unknown serial → UNVERIFIED SOURCE; HARDWARE only if the UID is in `config/verified_devices.json` (ships empty). |
| N1 | Runs locally on Linux with Python 3.10+, free/open-source dependencies only | **Delivered** | Linux, Python 3.13.5, clean venv from `requirements.txt`. Python 3.10 itself was not tested |
| N2 | All experiments virtual; no hardware purchases or paid services without owner approval | **Delivered** (as far as verifiable) | `reports/audit/team_rules_compliance.md` rules 8–10; all contribution reports state spend: none |
| N3 | Every module executed and tested; independent tests by the Auditor | **Delivered** | Owner suites re-run at `0c25062`: heading_core 76, sensor-spec 23, sim 152 (+44 N/A skips), firmware_bridge 95, app 52, T6 111; repo root 513 passed, 44 skipped, 0 failed; integration 30/30 |
| N4 | Evidence labelling; no simulated result presented as hardware performance | **Delivered** (D6/D7); D8 tightens the residual | Claims audit at `0c25062`: 0 applied hardware tags, 0 hardware-performance claims. After the D6 fix, replayed hardware is labelled recorded and not live; ingest hardware is UNVERIFIED; fake-FC via `--fake-fc` is SIMULATED. Residual L-SER (virtual pty shown as HARDWARE) is superseded by D8, which is in progress. |
| N5 | All unresolved limitations documented | **Delivered** | LIMITATIONS sections in docs/hardware, docs/math, sim, docs/firmware, firmware_bridge, app; `BLOCKERS.md`; HEADING_MATH 14a; L-D3 remains. L-SER is superseded by D8 (in progress). Install/browser-test prerequisites are in `docs/INSTALL_PREREQS.md`. Skipped tests are in `reports/audit/skipped_tests.md`. |
| N6 | Work kept in this private repository; each bot commits its completed work | **Delivered** (partly verifiable) | Role-prefixed commits present. An unauthenticated request for the GitHub URL returns 404, consistent with a private repo (T6 cannot see repo settings) |

**Traceability totals** (`reports/audit/traceability.md`, also `reports/verification_report.md` §7, at the v3.0 audit): **Delivered 13** (R1–R5, R7, R8, N1–N6; R8 behaviour delivered, its then-current wording pending D7 at that audit); **Partial 1** (R6); **Not delivered 0**. D7 was closed in `02c0ec0`. D8 reopens the R8 *implementation* against the tightened wording; the Auditor's traceability file has not yet been re-run.

Auditor verdicts per deliverable (`reports/verification_report.md` §1, v3.0): T1 **PASS**, T2 **PASS**, T3 **PASS**, T4 **PASS**, T5 **PASS** (D6 closed), PM docs **PASS with D7 (MINOR) open** at that audit. D7 is **CLOSED** (`02c0ec0`). Current PM-docs status: updated for D8, awaiting Codex / Auditor re-verification.

---

## 2. Actual test execution results

Only executed results are summarised here, with the command, commit and count taken from the cited file, or from the PM run in §2.3. Environment for the Auditor’s final verification: Linux box, Python 3.13.5, clean venv from `requirements.txt` (numpy 2.5.5, pytest 9.2.0, jsonschema 4.26.0, pyserial listed as optional and verified present); Google Chrome 156 headless; Node. Code was run from clean `git archive` exports, not the shared working tree (`TEST_RESULTS.md`, `reports/verification_report.md`).

### 2.1 Auditor final verification v3.0 (`TEST_RESULTS.md`, `reports/verification_report.md`)

Latest T6 run: 2026-11-27, about 01:15–01:30 IST (`TEST_RESULTS.md`). The verification report is dated about 01:30 IST.

| Date (IST) | Suite | Command | Commit | Result | Source |
|---|---|---|---|---|---|
| 2026-11-27 01:25 | Whole repo (all owner suites + T6) | `python -m pytest -q -rs` (repo root) | `0c25062` | **513 passed, 44 skipped, 0 failed** | `TEST_RESULTS.md` |
| 2026-11-27 01:22 | heading_core / sensor-spec / sim / firmware_bridge / app | `python -m pytest <dir> -q` | `0c25062` | 76 / 23 / 152 (+44 N/A) / 95 / 52 passed | `TEST_RESULTS.md` |
| 2026-11-27 01:22 | T6 independent suite (incl. claims) | `python -m pytest tests -q` | `0c25062` | 111 passed | `TEST_RESULTS.md` |
| 2026-11-27 01:17 | Integrated end-to-end A1–A10 | `python reports/audit/integration_run.py <export> <out>` | `f058c9a` (= HEAD minus PROJECT_STATUS.md at audit time) | **30/30 PASS** → D6 CLOSED | `TEST_RESULTS.md` [SIMULATED]/[REPLAYED] |
| 2026-11-27 01:25 | Claims audit | `pytest tests/test_t6_claims.py -s` | `0c25062` | 4 passed; 0 applied hardware tags (44 mentions), 0 nav claims | `TEST_RESULTS.md` |

The 44 skips at `0c25062` are `sim/tests/test_spec_cases.py` cases marked N/A by T3’s spec check (36 PASS / 44 N/A / 0 MISMATCH). The Auditor states that no skip hides a required check (`reports/verification_report.md` §3a).

Per-suite breakdown at `0c25062` also appears in `reports/verification_report.md` §0: heading_core 76, sensor-spec 23, sim 152 (+44 N/A), firmware_bridge 95, app 52, T6 111.

Selected criterion results, all **[SIMULATED]**, from `reports/verification_report.md` and the key-numbers list in `TEST_RESULTS.md` (unchanged numeric targets from the earlier run, except where the v3.0 integration re-run is cited):

| Area | Result (as recorded) |
|---|---|
| Heading | Level error ≤ 0.01°; tilt ±30° noise-free ≤ 0.1°; noisy tilt RMSE 0.628° (max 2.317°) |
| Calibration | Hard iron recovered to ≤ 0.004 µT (C1: (35.004, −21.998, 40.003) vs (35, −22, 40) µT); calibrated heading 0.354° vs 82.4° uncalibrated |
| End-to-end RMSE (5 seeds, mean±std, A1/R2, earlier T6 criterion run) | static 0.371±0.254°; yaw_spin 0.527±0.241°; tilted_spin 0.549±0.226°; hard_iron 0.528±0.243°; soft_iron 0.527±0.242°; high_noise 0.846±0.229°. motor_interference 16.3° (flagged) |
| Repeatability | spread 0.0° on identical input |
| MSP fuzz (2000 streams) | 98.8 % of valid frames recovered; 0 corrupted frames leaked into samples |
| Dashboard | display vs core diff 0.0°; 359.96 → "0.0" |
| E3b after the D3 fix | 0/20 sixty-second sessions falsely stale; single sessions 0/600 |

Inputs kept separate (`reports/verification_report.md`, “Accuracy-figure inputs”): RM3100 noise 15 nT and gain 75 LSB/µT at cycle count 200 are **[DATASHEET]** (PNI User Manual Table 3-1). IMU, interference and field parameters used in those runs are **[ASSUMED]**.

### 2.2 Owner-executed re-runs (`reports/contributions/`)

These were run by the module owners, at the commits they name, and are **not** a substitute for the Auditor’s independent counts above. All performance numbers they report are [SIMULATED] unless tagged [DATASHEET]. The UI contribution was later updated for the post-D6 state (`1e37a34`): app/tests 52 passed (×3), headless 5×5, `tests/` 111, a working-tree repo run of 512 passed / 45 skipped, and a local integration 27/27. The Auditor independently got **513 passed / 44 skipped** (pyserial present, so the pty test runs) and **30/30** integration including A10a–c (`reports/verification_report.md` §2a).

Earlier owner full-repo totals that still show the then-open D3 failure (`reports/contributions/sim.md` at `40d8ca2`, `reports/contributions/firmware.md` at `d0562e5`) are historically accurate for those commits only.

Maths at `c942d6f` (`reports/contributions/maths.md`): `python -m pytest heading_core/tests tests` → **181 passed** in 105.29 s; sensor-spec **23 passed**. Monte Carlo figures copied from `docs/math/accuracy_results.md` (command `python -m heading_core.experiments.accuracy_mc --trials 200 --seed 2026`), all **[SIMULATED]**, at ±30° tilt: ellipsoid calibration RMS 0.301° (P95 0.605°, max 1.751°); hard-iron only 2.994°; raw 29.505°; no tilt compensation 16.129°.

Hardware (`reports/contributions/hardware.md`): `verify_datasheet.py` **66/66 PASS**; `python3 docs/hardware/check_key_numbers.py` exits 0. Those checks prove the numbers appear in the PNI documents, not that this unit meets them.

### 2.3 PM full-suite run (this report)

Environment: `/workspace/venvs/hm` (Python 3.13.5, numpy 2.5.5, pytest 9.2.0, pyserial 3.5), repository root `/workspace/heading-monitor`, working tree based on `a88e8d1` with only documentation changes and this report uncommitted. 2026-11-27, 01:29:44–01:31:57 IST (Asia/Calcutta).

```
. /workspace/venvs/hm/bin/activate
python3 -m pytest -q
```

Result: **513 passed, 44 skipped** in 133.01 s (0:02:13), exit code 0. This matches the Auditor's official count at `0c25062` (`TEST_RESULTS.md`).

### 2.4 Earlier Auditor runs (history)

From `TEST_RESULTS.md`: at `dc3123a`, whole-repo **506 passed, 44 skipped, 0 failed**, and integration at `471724e` was **25/27** (A8/A8b → D6). At `403976b` and `0aaa066`, E3b / D3 still failed. Those failures are closed and are not part of the current suite result.

---

## 3. Integrated application test results

### 3.1 Auditor integration (official)

Source: `reports/audit/integration_results.md`. Run by T6 on 2026-11-27 at about 01:17 IST, on a clean `git archive f058c9a` export (D6 fix `0ca6b0f` and PM decisions `eacf8a2`, `c831574`). The report states that `0c25062` changes only `PROJECT_STATUS.md`, so the integration results stand for that suite HEAD. Harness: `reports/audit/integration_run.py`. Each app step starts a fresh `python -m app --host 127.0.0.1 --port <ephemeral>`, checks that the listening PID is the one just launched, and never uses a developer instance on :8080.

**Summary: 30 / 30 PASS.** A8 and A8b, which failed at `471724e`, now pass. Their criteria were tightened, and A10a–c were added.

| Step | What | Result (at `f058c9a`) |
|---|---|---|
| A1 | sim:static → heading_core → app | **PASS** (uncalibrated RMSE 0.29°) |
| A1 | sim:yaw_spin → heading_core → app | **PASS** (0.32°) |
| A1 | sim:tilted_spin → heading_core → app | **PASS** (0.41°) |
| A1 | sim:calibration_dance → heading_core → app | **PASS** (13.91° uncalibrated, as expected with injected iron and motion) |
| A1 | sim:hard_iron → heading_core → app | **PASS** (10.57° uncalibrated) |
| A1 | sim:soft_iron → heading_core → app | **PASS** (10.56° uncalibrated) |
| A1 | sim:motor_interference → heading_core → app | **PASS** (0.32°; default `--sim-duration 86400` stretches the profile — see A1b) |
| A1 | sim:high_noise → heading_core → app | **PASS** (0.35°) |
| A1b | sim:motor_interference with `--sim-duration 10` | **PASS** (samples with error > 5° carried a warning; earlier run 76/76) |
| A2 | replay of 7 example logs under `sim/examples/` | **PASS** |
| A3a | fake-FC `--capture` → `firmware_bridge --replay` | **PASS** |
| A3b | that replay → app | **PASS** |
| A4 | firmware_bridge `--fake-fc` POSTed to app ingest | **PASS** (badge SIMULATED, never HARDWARE) |
| A5 | calibration wizard start/stop/fit/apply/save/clear/load | **PASS** (RMSE after apply 0.72°) |
| A6 | frozen then stale data | **PASS** |
| A7 | app `serial:` to a missing port | **PASS** (FAULT, no hardware samples fabricated) |
| A7b | `firmware_bridge --port` missing | **PASS** (exit 2) |
| A8 | app replay of a hardware-labelled log | **PASS** (badge REPLAY (recorded hardware); source=replay, original_source=hardware, not live) |
| A9a | headless Chrome, sim:yaw_spin | **PASS** (badge SIMULATED, heading `30.8° NNE`, GPS Unknown) |
| A9b | headless Chrome, 3× field | **PASS** |
| A8b | headless Chrome, hardware-labelled replay | **PASS** (badge REPLAY (recorded hardware); banner says recorded, not live) |
| A10a | replayed file cannot defeat the D6 relabel | **PASS** |
| A10b | ingest of source=hardware (including injected transport=serial) | **PASS** (UNVERIFIED SOURCE, never live) |
| A10c | serial transport over a virtual pty (fake FC) | **v3.0: PASS as an observation** (showed HARDWARE via serial → then logged as L-SER). **Not the D8 acceptance criterion.** D8 requires this path to show SIMULATED when the device reports `SIML`/`SIMF`, and UNVERIFIED SOURCE for any other unverified serial origin — never a misleading HARDWARE badge. The Auditor is rewriting A10c; re-test pending. |

A1 RMSE values are for the **uncalibrated** app after the first second. Calibrated end-to-end figures are in §2 (A1/R2 and A5).

### 3.2 PM smoke test

Run by the PM on 2026-11-27 at 01:29 IST (Asia/Calcutta), from `/workspace/heading-monitor`, using `/workspace/venvs/hm/bin/python` (Python 3.13.5). Both processes used `--port 0` (INSTALL.md). The existing dashboard on `127.0.0.1:8080` (pid 267501) was not used and was still listening on the same pid afterwards.

#### 3.2.1 Simulator (`sim:tilted_spin`)

Command:

```
/workspace/venvs/hm/bin/python -m app --source sim:tilted_spin --port 0 --rate 20 --seed 3
```

Process stdout:

```
2026-11-27 01:29:20,930 INFO root: Heading monitor UI on http://127.0.0.1:37101  (source sim:tilted_spin)
```

`GET http://127.0.0.1:37101/api/status` (fields that confirm the source label, health and counts):

- `source_spec`: `"sim:tilted_spin"`
- `source_status.transport`: `"sim"`, `state`: `"running"`, `backend`: `"sim (T3, real module)"`
- `latest_sample_source`: `"sim"` — this is the contract value that the UI maps to the **SIMULATED** badge
- `sensor_status`: `"OK"`
- `core.estimator_backend`: `"heading_core"`
- `counts`: received 67, accepted 67, invalid 0
- `gps.status`: `"unknown"` (no coordinates; the status note states that none are used)

`GET http://127.0.0.1:37101/api/history?since=0`: 68 records. Last record:

```
{"seq": 68, "source": "sim", "heading_deg": 59.84272517453962,
 "heading_raw_deg": 59.94182259867286, "sensor_status": "OK",
 "warnings": ["NOT_CALIBRATED"], "transport": "sim",
 "original_source": null, "estimator_backend": "heading_core"}
```

The process was then stopped (pid 288374). [SIMULATED]

#### 3.2.2 Replay of a simulated example log

Command:

```
/workspace/venvs/hm/bin/python -m app --source replay:sim/examples/static_10hz_5s_seed42.jsonl --port 0 --speed 5 --loop
```

Process stdout:

```
2026-11-27 01:29:24,524 INFO root: Heading monitor UI on http://127.0.0.1:37891  (source replay:sim/examples/static_10hz_5s_seed42.jsonl)
```

`GET http://127.0.0.1:37891/api/status`:

- `source_spec`: `"replay:sim/examples/static_10hz_5s_seed42.jsonl"`
- `source_status.transport`: `"replay"`, `state`: `"running"`, `backend`: `"app file reader"`
- `latest_sample_source`: `"sim"` — a replayed simulated log keeps `source:"sim"`, so the badge stays **SIMULATED**, with the transport shown as replay (ARCHITECTURE.md / D6 rule for sim data)
- `sensor_status`: `"OK"`
- `counts`: received 174, accepted 174, invalid 0

`GET http://127.0.0.1:37891/api/history?since=0`: 175 records. Last record:

```
{"seq": 175, "source": "sim", "heading_deg": 29.294269481897825,
 "heading_raw_deg": 29.029709424547914, "sensor_status": "OK",
 "warnings": ["NOT_CALIBRATED"], "transport": "replay",
 "original_source": null, "estimator_backend": "heading_core"}
```

The process was then stopped (pid 288468). [REPLAYED] of [SIMULATED] data.

After both runs, `127.0.0.1:8080` was still held by pid 267501.

---

## 4. Screenshots and demonstration video

All of the following are **[SIMULATED]**: they were produced from the real running app fed by the T3 simulator, or from a replay of a recording the app made of that simulator (`reports/demo/README.md`). The Auditor did not inspect the video frame by frame (`reports/verification_report.md` LIMITATIONS item 7). The UI developer reports inspecting extracted frames at 4, 14, 22, 28, 36, 47, 57, 64 and 70 s (`reports/demo/README.md`).

### Demonstration video

- Video: [reports/demo/demo.mp4](demo/demo.mp4) — 71.5 s (ui.md: 71.48 s), 1440×900, H.264 (libx264, yuv420p, 25 fps), about 2.5 MB (2,463,884 bytes) (`reports/demo/README.md`, `reports/contributions/ui.md`).
- How to reproduce: `python3 reports/demo/make_demo.py` (needs Chrome and ffmpeg; see [reports/demo/README.md](demo/README.md)).

Every frame carries the overlay *“Simulated data — not hardware-verified. Compass heading only; no position or navigation.”* and a persistent DATA SOURCE badge.

Scenes, in order (`reports/demo/README.md`):

| Still | Scene |
|---|---|
| [01_startup_uncalibrated.png](demo/01_startup_uncalibrated.png) | Start-up on `sim:calibration_dance`, uncalibrated |
| [02_calibration_fit.png](demo/02_calibration_fit.png) | Calibration wizard after `heading_core.Calibration.fit` (ellipsoid) |
| [03_after_calibration.png](demo/03_after_calibration.png) | Calibration applied. Mean \|heading error\| vs sim truth in the recorded run: **21.4° before → 0.42° after** (161 / 120 samples, fit residual 0.016 µT rms) [SIMULATED]. Exact values in [demo_metrics.json](demo/demo_metrics.json): 21.3987° (n = 161) and 0.4185° (n = 120), residual 0.0156 µT, 681 fit samples |
| [04_tilted_spin.png](demo/04_tilted_spin.png) | `sim:tilted_spin` |
| [05_motor_interference.png](demo/05_motor_interference.png) | `sim:motor_interference` (`--sim-duration 40`): DEGRADED, FIELD_MAGNITUDE_OUT_OF_RANGE, HIGH_NOISE |
| [06_replay.png](demo/06_replay.png) | Replay of the scene-4 recording. Badge stays SIMULATED because each sample still says `source:"sim"`; the transport line shows replay |

The stale / NO DATA behaviour is intentionally omitted from the video so the badge never changes away from SIMULATED/REPLAY (`reports/demo/README.md`). That case is covered by the screenshot below.

### App screenshots (`reports/screenshots/`)

Refreshed in `ed3961c` to the current heading labels (`reports/contributions/ui.md`):

| File | What |
|---|---|
| [t5_dashboard_sim_tilted_spin.png](screenshots/t5_dashboard_sim_tilted_spin.png) | Dashboard on `sim:tilted_spin` |
| [t5_calibration_applied_sim_calibration_dance.png](screenshots/t5_calibration_applied_sim_calibration_dance.png) | Calibration applied on `sim:calibration_dance` (DEGRADED / TILT_TOO_LARGE is the real state while the dance is still tumbling) |
| [t5_gps_indicator_ingest_sim_sample.png](screenshots/t5_gps_indicator_ingest_sim_sample.png) | GPS availability indicator via ingest (fix / sats / HDOP only) |
| [t5_no_current_data_unknown.png](screenshots/t5_no_current_data_unknown.png) | No current data → values Unknown |

---

## 5. Known limitations and unresolved issues

This section collects limitations as they are written in the cited files. It does not add new technical claims.

### 5.1 Defects D1–D8

Status for D1–D6 is taken from `reports/verification_report.md` §4. D7 was moved to REVIEW in the first edition of this report and is now **CLOSED** (`02c0ec0`). D8 was opened from the Codex audit of `f1a0e3e`.

| ID | Severity | Owner | Status | Summary |
|---|---|---|---|---|
| D1 | MAJOR | T2 | **CLOSED** | Frozen sensor not flagged; fixed in `758faeb`; still flagged after the D3 change (E3, E3e, A6) |
| D2 | MINOR | PM | **CLOSED** | Blanket commit of other owners’ WIP and `__pycache__`; verified fixed |
| D3 | MAJOR | T2 + PM rule | **CLOSED** (`f31784a`, re-tested at `c942d6f`) | False MAG_STALE on a stationary quantised sensor; E3b stress 0/20. Residual blind spot documented as limitation 14a / **L-D3** |
| D4 | MAJOR | T4 | **CLOSED** | Bridge replay forwarded schema-invalid lines; fixed in `403976b` |
| D5 | MINOR | T6 (self-reported) | **CLOSED** | Accidental HEAD detach; repaired (`84fc231`) |
| D6 | CRITICAL | T5 + PM | **CLOSED** (fix `0ca6b0f`; decisions `eacf8a2`, `c831574`; T6 re-test at `f058c9a` / `0c25062`) | Replayed hardware-labelled log had been shown as HARDWARE + “Live hardware samples.” It now shows 'REPLAY (recorded hardware)' with a not-live banner; the relabel cannot be bypassed (A10a) |
| D7 | MINOR | PM | **CLOSED** (`02c0ec0`; wording landed in `2564266`) | REQUIREMENTS R8 / README rule 2 / CHANGELOG had not described the accepted five-label badge rules. The D7 wording (badge derived from sample.source; HARDWARE only for a live serial transport; replayed hardware → 'REPLAY (recorded hardware)'; hardware via ingest → 'UNVERIFIED SOURCE') was accepted and closed. **D8 then replaced that HARDWARE rule** — see the next row. |
| D8 | Priority 1 (Codex, `f1a0e3e`) | T4 + T5 + PM | **IN PROGRESS** (decision `1bef73e`) | A serial connection is not proof of hardware. `firmware_bridge` must read the device's self-reported identity (MSP_API_VERSION, MSP_FC_VARIANT, MSP_FC_VERSION, MSP_BOARD_INFO, MSP_UID) into `meta.device_identity` as values reported by the device, not verified. A fake FC / simulator that reports variant `SIML` or board id `SIMF` is mapped to `source: "sim"` (badge SIMULATED). Any other serial origin, including unknown, unidentified or failed identity, is UNVERIFIED SOURCE. HARDWARE appears only when the device UID is in `config/verified_devices.json` (ships empty; an entry requires HV checklist pass, Auditor sign-off, and a committed hardware log). Today, nothing should be able to display HARDWARE. This supersedes L-SER. Re-test of A10c and the full suites is outstanding. |

### 5.2 Blockers B1–B4 (`BLOCKERS.md`)

| ID | Issue | Status |
|---|---|---|
| B1 | No physical RM3100 + Matek FC is connected to the project environment. No result can carry a hardware-verified evidence label; the serial path was tested only against constructed MSP frames | **OPEN** (accepted for the virtual phase) |
| B2 | Exact Matek FC model and firmware (INAV / ArduPilot / Betaflight) on the team’s board are unknown | **OPEN** (documented assumption, not a stop) |
| B3 | `firmware_bridge` cannot undo INAV’s mag-calibration normalisation: after INAV mag calibration, MSP_RAW_IMU mag is dimensionless, not mGauss. `mag_uT` is only correct while `magzero=0` and `maggain=1024` | **OPEN** (non-blocking). Workaround: leave INAV mag calibration unset and let `heading_core` calibrate |
| B4 | INAV 10 is still a release candidate (10.0.0-rc2, 2026-09-29; stable planned December 2026); setup steps are pinned to `maintenance-10.x` @ `fce6c94` | **OPEN** (non-blocking) |

### 5.3 L-D3 (still open) and L-SER (superseded by D8, in progress)

These items were called out in `reports/verification_report.md` (overall verdict and LIMITATIONS items 4 and 6) at the v3.0 audit.

- **L-D3 (still open).** In quantised mode a frozen magnetometer is undetectable on a stationary vehicle, below 1°/s, or during a level yaw turn when no gyro is supplied (PM D3 decision (a), `quant_nogyro_time_rule=False`). The opt-in `quant_nogyro_time_rule=True` catches long freezes but brought back about 4/20 false alarms in T6's stress test. Same residual as `docs/math/HEADING_MATH.md` §13 item 14a.
- **L-SER, superseded by D8 (in progress).** At the v3.0 audit, the serial transport could not tell a virtual pty (for example one fed by the fake FC) from a real flight controller, and such data was shown as live HARDWARE (integration A10c). That was recorded as limitation L-SER in `reports/verification_report.md`. The Codex audit of `f1a0e3e` rejected that behaviour. The D8 decision (`ARCHITECTURE.md`, `1bef73e`) replaces it: a serial connection is not proof of hardware; a device reporting `SIML`/`SIMF` is SIMULATED; any other unverified serial origin is UNVERIFIED SOURCE; HARDWARE requires an allowlisted UID. Until D8 is merged and A10c is re-run, committed pre-D8 code can still exhibit the old L-SER behaviour. The app still trusts `meta.original_source` written in a replay file (accepted, `c831574`), but only ever as a non-live label.

### 5.4 App limitations (`app/README.md` § LIMITATIONS)

There is no separate `app/LIMITATIONS` file; the list lives in `app/README.md`. Numbered 0–10 (post-D6 item 4: the app trusts `original_source` as written in the file, and only uses it for a non-live label):

0. Heading only (PM decision). Position, coordinates, map, speed, course-over-ground and distance features were removed. Only a read-only GPS availability indicator remains (`sample.gps` = fix, num_sat, hdop). The contract has no coordinates and the app shows none. The current simulator does not emit `gps`, so the indicator normally reads Unknown.
1. `mag_raw` is optional (the CAN-L4-3100 stream is a scaled field, not raw counts).
2. Accuracy shown is quality, short-term noise and calibration residual, not absolute accuracy. Error versus truth exists only for simulated data. Nothing here is hardware-verified.
3. The serial path has never been run against a real flight controller or the CAN-L4-3100; only a non-existent port (FAULT, no data) in owner tests. (Separately, the Auditor’s then-current L-SER finding in `reports/verification_report.md`, not app README item 3, was that a virtual pty fed by the fake FC showed HARDWARE. That finding is superseded by D8, in progress.)
4. Replay of simulated logs keeps `source:"sim"` (badge SIMULATED; transport shown separately). Replayed hardware is relabelled `source:"replay"` with `meta.original_source="hardware"` and shown as REPLAY (recorded hardware), not live. The file’s written `original_source` is trusted only for that non-live label.
5. Local stubs exist but are inactive in the current repo (heading_core and sim are real). firmware_bridge is never stubbed.
6. The calibration wizard shows coverage but does not guide the user to a missing orientation.
7. One source per process; switching requires a restart; only one process can bind port 8080.
8. Local only, no authentication; default bind is 127.0.0.1.
9. History is in memory (last 6000 samples, about 5 min at 20 Hz).
10. UI verification is automated plus screenshots. Human usability has not been assessed. Layout was checked at 1600 px width only (`ui.md` also notes 1440–1600 px).

### 5.5 Heading-math limitations (`docs/math/HEADING_MATH.md` §13)

Unresolved items 1–17, including 14a, are unchanged in substance:

1. No hardware validation. All numbers are [SIMULATED] or [DATASHEET].
2. Accelerometer-only tilt is wrong under dynamic acceleration; no attitude filter is implemented.
3. Accelerometer sign of real FC data is unverified; the firmware bridge must convert to specific force (level = (0, 0, −1) g).
4. Magnetometer-to-body misalignment is not observable by the ellipsoid fit (±0.02 skew already doubles RMS error, 0.30° → 0.69° [SIMULATED]).
5. Calibration needs full 3-D coverage; the fit is plain algebraic least squares, not outlier-robust; there is no automatic coverage accept/reject gate.
6. Time-varying motor/ESC interference is detected, not compensated.
7. Risk of double calibration if the FC or AP_Periph already applies offsets.
8. Declination is a user-supplied constant; no WMM/IGRF, no location input, no grid north.
9. Heading is ill-conditioned near a vertical field (high dip); tilt near ±90° pitch is not supported.
10. The quality metric is heuristic; thresholds are not tuned on data.
11. HIGH_NOISE without gyro conflates noise and lag on fast turns.
12. Monte Carlo noise/bias parameters are assumptions, not measurements of this board.
13. Warning codes are frozen by PM decision; some conditions (for example FC calibration active) have no dedicated code.
14. Frozen-data and quantised-mode thresholds are **PROVISIONAL** until a hardware replay log exists. A sensor stuck at a noisy value, or slowly drifting, is not detected.
14a. Residual of D3 / **L-D3**: a mag-only freeze on a stationary vehicle cannot be detected on quantised hardware. Detection needs rotation > 3° beyond a 1°/s deadband, or a > 3° tilt change. Default `quant_nogyro_time_rule=False`.
15. Temperature drift, RM3100 linearity (0.5 % [DATASHEET]) and cycle-count changes are not modelled.
16. Heading is not course over ground; no speed, distance or place estimate is provided.
17. Scope rule: `heading_core` does not and will not provide a position, displacement or distance feature; path-error figures are analysis only.

### 5.6 Hardware fact-sheet limitations L1–L17 (`docs/hardware/FACTSHEET.md` §8)

The fact sheet lists these as unresolved as of 2026-11-27 IST. Numbering in the file places L16, L17, L15, L14 after L13; all seventeen identifiers are present.

- **L1** Exact Matek FC model and its firmware are UNKNOWN; §3 is a candidate list only.
- **L2** Nothing in the sheet is hardware-verified; all numbers are [DATASHEET] / [OFFICIAL-DOC] / [SOURCE-CODE] / [DERIVED].
- **L3** PNI publishes gain/noise only for cycle counts 50/100/200; other cycle counts are UNKNOWN.
- **L4** PNI range conflict: ±800 µT (user manual) vs ±1100 µT (product page / sales sheet).
- **L5** PNI manual inconsistencies (SA0/SA1 mapping, DRDM bits, CMM example, “~430 Hz” vs 147 Hz) are not resolvable without PNI or hardware.
- **L6** REVID value (0x22) comes only from INAV source, not from PNI documentation.
- **L7** Whether PNI “Noise” is RMS or peak-to-peak is not stated.
- **L8** CAN-L4-3100 MSP output rate and DroneCAN effective rate on this unit are UNKNOWN (code caps DroneCAN at 25 Hz).
- **L9** MSP availability on the pre-installed MatekL431-GPS firmware is version-dependent and unverified.
- **L10** Reason for Matek’s INAV `align_mag = CW90` and the module’s true output frame are unverified (needs a physical rotation test).
- **L11** Betaflight DroneCAN magnetometer support is new (2026-07) and untested here; inclusion in Matek H743 builds is UNKNOWN.
- **L12** H743-MINI, F405-HDTE/WMN/MINI-TE, H7A3 boards were not verified (CAN/I2C pads UNKNOWN).
- **L13** H743-WING V3 / H743-SLIM V3 specs were read from reseller copies (mateksys.com URLs returned 404 to the fetcher).
- **L14** mateksys.com pages may change; values captured 2026-11-26. Source files are not mirrored in the repo (copyright); hashes are in `docs/hardware/SOURCES.md`.
- **L15** `COMPASS_TYPEMASK` → `COMPASS_DISBLMSK` rename: first ArduPilot release containing it not identified.
- **L16** PNI manual naming mismatch: URL says V11.0, PDF metadata says V15.0, page footers say V16.0. Values are cited from the content (V16.0).
- **L17** Matek H743-WLITE values were read from search-engine extracts, not from a full page fetch.

### 5.7 Other Auditor limitations

From `reports/verification_report.md` “LIMITATIONS (T6, unresolved)”, in addition to L-D3 (still open) and L-SER (now superseded by D8, in progress):

1. All results are [SIMULATED] or [REPLAYED] against an idealised uniform-field model. None transfer to the physical RM3100 or Matek FC.
2. Exact Matek FC model and firmware are unknown (T1 L1). INAV axis convention, mag scaling and pitch sign are [SOURCE-CODE] only.
3. MSP tests use hand-built frames and the fake FC; real USB timing, rate limits and partial reads are untested. Live `serial:` was only tested against a missing port (plus the v3.0 virtual-pty observation then logged as L-SER, which D8 is replacing).
5. App ingest trusts the client-declared `source`.
7. UI checks use DOM text from headless Chrome; pixels and human readability were not assessed by T6.
8. Default `--sim-duration 86400` stretches the motor_interference profile over 24 h.
9. F1 lag (4.5° on a 25°/s ramp) and E5 interference error (13°) are reported, not gated. T6 numeric targets have not been reviewed by the owner. Python 3.10 was not tested (3.13.5 only).

Further firmware and simulator limitations are in `docs/firmware/FC_SETUP.md` (L1–L10), `docs/firmware/RM3100_COMPATIBILITY.md`, `firmware_bridge/README.md` and `sim/README.md`.

### 5.8 Owner inputs still needed

From `docs/hardware/FACTSHEET.md` §7 and `BLOCKERS.md` B2. Until these are supplied, setup guides have to cover variants, and no hardware log can be interpreted against a known configuration:

1. **Exact Matek FC model** (silkscreen name and version, for example “H743-WING V3” or “F405-WTE”). This decides CAN versus MSP-only and the FC-side pins.
2. **Firmware on the FC** (INAV / ArduPilot / Betaflight, and the version). This decides the bridge protocol and the magnetometer path.
3. **Firmware on the CAN-L4-3100** (MatekL431-GPS versus -Periph, and the version). This decides whether MSP output is available.
4. **Whether the module is genuine Matek** (the fact sheet records a counterfeit warning as an open question).
5. **Mounting** on the airframe (arrow direction, distance from power wiring).
6. (Optional, same list.) Whether resolution better than float16-Gauss / 0.1 µT (MSP) is required.

---

## 6. Simulated functionality versus physically verified functionality

**Physically verified functionality: none.** `reports/hardware_logs/` does not exist. No item in this project has been given a hardware-verified evidence label (`reports/verification_report.md`; `reports/HARDWARE_VALIDATION_CHECKLIST.md`).

The checklist itself states: “Status: **NOT RUN. Nothing here is verified.**” It is to be run by the owner when hardware is available, on the bench, with propellers removed.

| ID | Check (`reports/HARDWARE_VALIDATION_CHECKLIST.md`) | Status |
|---|---|---|
| HV1 | MSP link: FC answers MSP_RAW_IMU and MSP_ATTITUDE over USB (MSPv1, v2, v2-over-v1) | **NOT RUN** |
| HV2 | Accelerometer sign and scale (body frame FRD, level = (0, 0, −1) g) | **NOT RUN** |
| HV3 | Gyro sign and mag heading follow FC yaw (clockwise rotation) | **NOT RUN** |
| HV4 | Neutral FC calibration, field magnitude and vertical sign (units µT) | **NOT RUN** |
| HV5 | Attitude pitch and roll signs (aerospace convention) | **NOT RUN** |
| HV6 | Node UART baud and INAV serial port settings | **NOT RUN** |
| HV7 | `align_mag = CW90` is correct for our mounting | **NOT RUN** |
| HV8 | Capture → replay reproduces the same samples | **NOT RUN** |
| HV9 | (Optional) GPS availability indicator, and no position anywhere in the logs | **NOT RUN** |

| Capability | What exists today | Physically verified? |
|---|---|---|
| Live magnetic heading, rose, roll/pitch, quality, warnings | Yes, on sim and replay ([SIMULATED] / [REPLAYED]; §2–§3) | None |
| Ellipsoid calibration wizard, save/load | Yes, on sim ([SIMULATED]; A5, demo scene 3) | None |
| Optional declination (true heading) | Yes, unit-tested ([SIMULATED]; H6) | None |
| Simulator and JSONL/CSV recording/replay | Yes ([SIMULATED] / [REPLAYED]) | None |
| MSP decode, scaling, fake-FC, missing-port FAULT | Yes, against hand-built frames and a fake FC ([SOURCE-CODE] / [SIMULATED]) | None. Live `serial:` to a real Matek FC has not been run |
| RM3100 gain, noise, cycle-count table | Desk research against PNI documents, 66/66 automated checks ([DATASHEET]) | None. Those checks prove the numbers appear in the PDFs, not that this unit meets them |
| INAV / ArduPilot / AP_Periph path and pin advice | Desk research against pinned source (`docs/firmware/`) | None |
| End-to-end heading accuracy on the physical sensor | No committed hardware log | None |

Datasheet figures used by the math and sim (for example gain 75 LSB/µT and noise 15 nT at cycle count 200) are **[DATASHEET]** only (`docs/hardware/FACTSHEET.md`). They are not measurements of the team’s module.

---

## 7. Complete source code and installation instructions

The complete source is this private repository. Layout from `README.md`:

| Path | Owner | Contents |
|---|---|---|
| `docs/hardware/` | Hardware Research Engineer | RM3100 + Matek FC facts, wiring, sources, verification scripts |
| `heading_core/` + `docs/math/` | Mathematics & Sensor Scientist | heading math, calibration, filtering |
| `sim/` | Simulation Developer | RM3100/FC sensor simulator emitting the sample contract |
| `firmware_bridge/` + `docs/firmware/` | Firmware Specialist | FC setup, MSP telemetry reader emitting the sample contract |
| `app/` | UI & Software Developer | heading-monitor application (backend + UI) |
| `tests/` + `reports/` | Testing & Technical Auditor | independent tests, audit and verification reports |
| `contracts/`, `TEAM_TRACKER.md`, `ARCHITECTURE.md` | PM & CTO | interfaces, tracker, decisions |
| `REQUIREMENTS.md`, `BLOCKERS.md`, `INSTALL.md`, `TEAM_RULES.md`, `TEST_RESULTS.md` | PM / UI / Auditor as labelled | project documents |

Also at the repository root: `CHANGELOG.md`, `PROJECT_STATUS.md`, `requirements.txt`.

### Installation

Full, verified instructions: **[INSTALL.md](../INSTALL.md)**. The UI developer followed that file on a fresh clone in a fresh venv at commit `41bb756` (Python 3.13.5). That log is at the end of `INSTALL.md`.

Quick start (from `INSTALL.md` §§2–3), run from the repository root:

```bash
git clone <repo-url-or-path> heading-monitor
cd heading-monitor
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt          # numpy, pytest, jsonschema; pyserial is listed as optional
python -m app --source sim               # then open http://localhost:8080
```

Useful variants, also from `INSTALL.md`: `python -m app --source sim:<scenario>`, `python -m app --source replay:<file>`, `python -m app --source ingest`, and `python -m app --source serial:/dev/ttyACM0 --baud 115200` (the last needs a real FC and has not been run on one). `--port 0` picks a free port.

Tests: `python -m pytest -q` from the repo root, or the per-suite commands in `INSTALL.md` §4.

Prerequisite note in `INSTALL.md`: Python 3.10+ is required; the documented verification used 3.13.5. The Auditor has not tested Python 3.10.

---

## 8. Hardware compatibility findings

All findings in this section are desk research plus synthetic simulation. **None were confirmed on the team’s hardware.**

### 8.1 Sensor and module (`docs/hardware/FACTSHEET.md`)

- The sensor is a PNI RM3100. Key [DATASHEET] numbers at cycle count 50/100/200: gain 20/38/75 LSB/µT, noise 30/20/15 nT, I2C addresses 0x20–0x23. Default cycle count is 200. Field-range documents conflict: **±800 µT** in the user manual versus **±1100 µT** on the product page; the fact sheet uses ±800 µT as the conservative figure.
- The module the team owns is the **Matek CAN-L4-3100**: an RM3100 on SPI behind an STM32L431 running ArduPilot **AP_Periph**. The flight controller never sees RM3100 registers or raw counts. It receives an already-scaled field: DroneCAN `MagneticFieldStrength` as float16 Gauss at ≤ 25 Hz, or MSP `MSP2_SENSOR_COMPASS` as int16 milligauss (0.1 µT) over UART2.
- The exact Matek FC model is **UNKNOWN**. Candidate boards and firmware paths are listed in FACTSHEET §3–§4.
- Automated re-check of PNI documents: 66/66 PASS (`docs/hardware/verify_datasheet.py`, `docs/hardware/VERIFICATION.md`, `reports/contributions/hardware.md`). The Auditor re-read PNI User Manual Table 3-1 and reports that it matches `key_numbers.json` (`reports/verification_report.md` T1 row).

### 8.2 Firmware paths (`docs/firmware/RM3100_COMPATIBILITY.md`, `docs/firmware/FC_SETUP.md`)

Pinned source (as cited in those documents): ArduPilot master `6034266`; INAV `maintenance-10.x` `fce6c94` (FC_SETUP notes that `RM3100_COMPATIBILITY.md` labels this commit “master”, but on GitHub it is the head of `maintenance-10.x`, while `master` is `940b928`); Betaflight master `f511ed9`.

Key compatibility findings, all [SOURCE-CODE] or [SIMULATED]:

- **Preferred path for INAV (primary in FC_SETUP):** node TX2 → FC UART RX, `mag_hardware = MSP`, `align_mag = CW90`. The bridge reads `MSP_RAW_IMU` and `MSP_ATTITUDE` over USB. INAV 10 has no DroneCAN magnetometer handler, so DroneCAN is not a viable INAV path.
- **INAV’s native SPI RM3100 driver** keeps `count24 >> 8` (about 3.41 µT/LSB). A synthetic simulation in `docs/firmware/research/` gives up to **13.5°** heading error at |H| = 20 µT before calibration (`reports/contributions/firmware.md`). That is not the path this project uses with the CAN-L4-3100.
- **ArduPilot on a CAN-capable Matek H743:** DroneCAN (`CAN_P1_DRIVER=1`, `CAN_D1_PROTOCOL=1`, `COMPASS_DISBLMSK`). The heading-monitor bridge is **MSP-only**; MAVLink is not implemented (FC_SETUP L4). ArduPilot on F405 without CAN would also need MAVLink.
- **Betaflight:** no RM3100 bus driver was verified; a DroneCAN magnetometer subscriber exists behind `ENABLE_DRONECAN`, but which release or Matek target ships it is unconfirmed.
- **Quantisation of the intended MSP path** [SIMULATED]: at |H| = 20 µT, int16 mGauss worst-case heading error 0.291° (1.146° at |H| = 5 µT) (`reports/contributions/firmware.md`).
- **Conventions the bridge assumes** (FC_SETUP §6), not checked on hardware: mag in 0.1 µT steps; accel 512 LSB/g; INAV forward-left-up mapped to FRD so that a level board reads (0, 0, −1) g; INAV pitch sign negated. Gyro sign is described as the weakest inferred link (FC_SETUP L2).
- **Neutral FC calibration** must be left unset (`magzero = 0`, `maggain = 1024`) or field magnitude warnings will be wrong (BLOCKERS B3).
- AP_Periph does not compute heading; it sends a field vector. The only heading an AP_Periph node sends is GNSS moving-baseline yaw, which this app does not use (`RM3100_COMPATIBILITY.md` §1).

---

## 8a. Skipped tests

The official skip inventory is `reports/audit/skipped_tests.md` (Auditor, generated from a clean export of `1bef73e` by `python -m pytest -q -rs`). That file lists every skipped test, the exact skip reason, a category, and whether the skip hides a required check.

The PM independently ran `/workspace/venvs/hm/bin/python -m pytest -q -rs` on 2026-11-27 (Asia/Calcutta) on the tree at `1bef73e`, with pyserial, `google-chrome` and Node present, and obtained the same totals: **513 passed, 44 skipped**, 0 failed, in 139.51 s. All 44 skips were in `sim/tests/test_spec_cases.py` (the simulator's N/A cross-checks against the T2 sensor-spec keys). The reasons and grouping match the Auditor's file.

Summary, from `reports/audit/skipped_tests.md`:

| Category | Count |
|---|---|
| Out of scope: navigation / position / distance (heading-only rule; these quantities are not modelled) | 29 |
| Analysis formula, not a simulator quantity | 9 |
| Interference source model not in sim (motor field is k*I, [ASSUMED]) | 4 |
| Declination error model not in sim (uniform field) | 1 |
| Non-RM3100 parameter (generic 0.15 µT LSB part) | 1 |

Uncategorised: 0. Skips that may hide a required check: **0**. The corresponding analytic keys are asserted by `docs/math/sensor-spec/test_reference.py`, which passed in the same official run.

These 44 are the official skip set when pyserial, Chrome/Chromium and Node are present. Additional *environment* skips exist in the code but did not fire in that run; they are documented in `docs/INSTALL_PREREQS.md`:

- the five tests in `app/tests/test_app_ui_headless.py` if no `google-chrome`, `chromium` or `chromium-browser` is on `PATH`;
- Node-based badge/maths tests if `node` is not on `PATH`;
- the firmware_bridge pty serial test if pyserial is missing or the OS has no POSIX pty.

If the Auditor later refreshes `reports/audit/skipped_tests.md` after D8 lands, this section should be reconciled with that update. Installation and browser-test prerequisites are recorded in `docs/INSTALL_PREREQS.md` (the step-by-step walkthrough in `INSTALL.md` remains UI-owned).

---

## 9. Auditor’s independent PASS/FAIL verdict

The last completed official written verdict is in `reports/verification_report.md` (T6 Verification Report — FINAL v3.0, after the D6 re-test), at Auditor-tested commits `0c25062` / `f058c9a`. It is quoted below exactly from that file, section 0. **It is the historical v3.0 result.** The current project status is **CONDITIONAL PASS: corrections in progress, pending independent Codex re-verification** (Codex audit of `f1a0e3e`; D8 in progress).

> ## 0. OVERALL VERDICT: **PASS (virtual scope only)**. Project completion **APPROVED for the virtual (simulated/replayed) scope**; hardware performance is NOT verified.
> Reasons:
> 1. **The software runs.** T6 started a fresh app on a PID-verified ephemeral port for every step: **30/30 integration steps pass**.
>    - All 8 sim scenarios ran through heading_core and the app, plus motor interference with a short sim duration.
>    - 7 example-log replays; fake-FC `--capture` → `--replay` → app; fake-FC → bridge → app (SIMULATED).
>    - Calibration wizard; frozen and stale data; missing serial port.
>    - Headless Chrome checked the badge, heading, warnings, GPS "Unknown", and the replay and ingest badges and banners.
>    - D6 edge cases A10a–c.
> 2. **All suites green at HEAD 0c25062:** repo root **513 passed, 44 skipped, 0 failed**.
>    - Per suite: heading_core 76, sensor-spec 23, sim 152 (+44 out-of-scope N/A skips, §3a), firmware_bridge 95, app 52, T6 111.
> 3. **D6 (CRITICAL) is CLOSED** after T6's independent re-test, and so are D3 (MAJOR) and D1 (MAJOR).
> 4. **All required reports exist:**
>    - FACTSHEET, HEADING_MATH, FC_SETUP;
>    - the sim, firmware_bridge and app READMEs, and INSTALL;
>    - TEST_PLAN, this report, TEST_RESULTS;
>    - seven contribution reports;
>    - audit A–D.
> 5. **Claims audit:** 0 applied hardware tags, 0 hardware-performance claims, 0 positioning or navigation claims. TEAM_RULES: 13/13 (with disclosed, repaired incidents).
>
> Open, non-blocking:
> - **D7 (MINOR, PM docs):** the R8 wording in REQUIREMENTS.md and the README rule 2 badge list don't reflect the accepted D6 and ingest badge rules, and there is no CHANGELOG entry (§2b).
> - **Limitations:** L-D3 (frozen-mag blind spots in quantised mode) and L-SER (a virtual serial port shows HARDWARE). See LIMITATIONS.
>
> The approval covers the virtual scope only. Every number is [SIMULATED]/[REPLAYED]. Hardware validation (HARDWARE_VALIDATION_CHECKLIST, BLOCKERS B1) has not been run.

Per-deliverable verdicts from the same report (§1): T1 **PASS**, T2 **PASS**, T3 **PASS**, T4 **PASS**, T5 **PASS**, PM docs **PASS with D7 (MINOR) open**.

The quoted D7 item describes the documentation gap **at the time of the v3.0 audit**. The D7 wording was then fixed in `2564266`, and the Auditor re-checked it and closed D7 in `02c0ec0`; the v3.1 addendum left the official PASS (virtual scope only) unchanged. The quoted L-SER item is **superseded by D8** (in progress). The current status is no longer an unconditional PASS: see the acceptance boundary at the top of this report.

---

## 10. Total development expenses

Figures below are taken only from the “Money spent” sections of `reports/contributions/*.md`. No file in that directory reports a non-zero amount or a paid tool.

| Contribution file | Money spent (as written) | Paid tools or services (as written) |
|---|---|---|
| `reports/contributions/hardware.md` | None | No purchases, sign-ups or paid services. Free public pages, public GitHub source, curl, poppler-utils, Python 3 standard library |
| `reports/contributions/maths.md` | None | No purchases, subscriptions, paid APIs or paid services. Only free tools and libraries. “No paid tools or services.” |
| `reports/contributions/sim.md` | None | No purchases, subscriptions, paid APIs or paid services. Python, numpy (BSD), pytest (MIT), jsonschema (MIT), git; public pages and public GitHub source |
| `reports/contributions/firmware.md` | none | none. Python, pytest, optional pyserial, public firmware source and docs. pymavlink (free) is approved but not yet used |
| `reports/contributions/ui.md` | none | none. Python standard library, pytest, numpy, jsonschema, headless Google Chrome, ffmpeg, Node.js, git. No CDN, Playwright, paid API or cloud service |
| `reports/contributions/auditor.md` | none | none. Python, numpy, pytest, jsonschema, pyserial, git, Google Chrome (already on the box), Node.js, poppler-utils. No sign-ups, subscriptions, API keys or cloud services |
| `reports/contributions/hub.md` | none | none |

`reports/audit/team_rules_compliance.md`, as summarised in `reports/verification_report.md` §6: “Spend: none found (requirements are OSS; no keys, purchases or paid APIs; all contribution reports state none).”

**Total development expenses reported in the contribution files: none (no paid tools).** No contribution file states a currency amount such as “$0”; they all say “none”.

Platform subscription costs (the environment in which this team works) are **outside the project’s scope and were not tracked**.

---

## Notes for the PM (remaining file differences, not new tests)

1. Official executed results remain those at `0c25062` (suites) and `f058c9a` (integration), packaged in `a88e8d1`, with D7 closed in `02c0ec0`. A later PM `pytest -q -rs` on the tree at `1bef73e` reproduced 513 passed, 44 skipped (see §8a and `reports/audit/skipped_tests.md`). D8 has not yet been re-tested officially.
2. Some earlier owner contribution files (`reports/contributions/maths.md`, `sim.md`, `firmware.md`) were written before D3 and/or D6 were closed and should be read together with the v3.0 verification report.
3. FACTSHEET §8 list order is L1–L13, then L16, L17, L15, L14. All seventeen labels exist.
4. `docs/firmware/FC_SETUP.md` §0 notes that `RM3100_COMPATIBILITY.md` labels INAV `fce6c94` as master, whereas that commit is the head of `maintenance-10.x`.
5. After D8 lands and the Auditor re-runs the suites and the 30 integration checks (with the rewritten A10c), this report still needs a follow-up pass: refresh the suite/integration counts, close or re-state D8, and replace any residual pre-D8 L-SER / “HARDWARE only via serial” citations that live in Auditor-owned files (`reports/verification_report.md`, `reports/audit/traceability.md`, `reports/audit/integration_results.md`, `TEST_RESULTS.md`) and in UI/firmware READMEs. Those files were not edited in this documentation commit.

No number in the body of this report was invented. Where a figure could not be taken from a file or from the PM commands recorded in §2.3 and §3.2, it is omitted.
