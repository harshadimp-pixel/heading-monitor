# Contribution: Testing & Technical Auditor (T6)

**Evidence level:** every result below is **[SIMULATED]** or **[REPLAYED]**; RM3100 constants are [DATASHEET]; MSP scaling is [SOURCE-CODE]. **Nothing is `[HARDWARE-VERIFIED]`.** No RM3100, Matek FC or CAN node was connected, and `reports/hardware_logs/` does not exist.

## 1. Deliverables and paths
| Deliverable | Path |
|---|---|
| Test plan: criteria H1–H7, C1–C5, E1–E6, F1–F2, S1–S4, A1, R1–R2, M1–M4, U1–U5, K1, Q1–Q4, severity and verdict rules | `reports/TEST_PLAN.md` |
| Independent test suite (111 tests, black-box; own reference model and own MSP encoders/CRC) | `tests/` (`refmodel.py`, `msp_frames.py`, `test_t6_*.py`) |
| Final verification report v2.0: verdict per deliverable, per criterion, defects, overall verdict | `reports/verification_report.md` |
| Executed results with commands and SHAs | `TEST_RESULTS.md` |
| (A) Integrated end-to-end harness and results | `reports/audit/integration_run.py`, `reports/audit/integration_results.md`, `reports/audit/raw/` |
| (B) Requirements traceability R1–R8, N1–N6 | `reports/audit/traceability.md` |
| (C) Whole-repo claims audit | `reports/audit/claims_audit.md` |
| (D) TEAM_RULES compliance (13 rules, incl. spend) | `reports/audit/team_rules_compliance.md` |
| D3 frozen-sensor regression matrix | `reports/audit/raw/d3_regress.py`, `raw/d3_regress_c942d6f.log` |
| Defect rows D1–D6, T6 row, T6 Limitations | `TEAM_TRACKER.md` (T6 lines only) |

**Overall verdict (v3.0, after the D6 re-test): PASS for the virtual scope; completion APPROVED for the virtual scope only. D6 is closed; D7 (MINOR, docs) is open and non-blocking. Nothing is hardware-verified.**

## 1b. v4 (D8 round, 2026-11-27 ~10:00–11:30 IST)
- **D8 (CRITICAL):** T6 filed and owns it, withdrew L-SER, and rewrote A10c (fails on any HARDWARE or live record for a fake FC or pty). New steps A10d–A10i and A10z.
- **New T6 black-box suites:**
  - `tests/test_t6_d8_bridge.py` (32 cases; found the UID truncation bug → Firmware F12);
  - `tests/test_t6_d8_provenance.py` (30 cases, app + rendered DOM);
  - `tests/t6_msp_device.py` (MSP device emulator on a pty);
  - F11 spoof demonstrations.
- **New reports:** `reports/audit/skipped_tests.md` (generated from an actual `pytest -rs` run; 44 skips, none hides a required check) and `reports/audit/d8_spec_review.md`.
- **Chrome fix:** fresh temporary profile plus `--incognito` in the integration runner.
- **Other checks:** Python 3.12.16 and 3.10.22 runs; N6 re-trace and gitleaks/rg scan (0 findings); Codex cross-check (MC 0.301° reproduced exactly).
- **Badge-label decision:** "ALLOWLISTED DEVICE (identity not authenticated)".
- **D9 (MINOR, T5):** filed for the labelling of UI's spoof test.
- **Verdict and figures:** verification_report.md §0 and TEST_RESULTS.md.

## 1c. v5 (flake fix and final rerun, 2026-11-27 ~11:50–12:20 IST)
- **Flake:** independently reproduced UI's intermittent app/tests failure as **D12 (MAJOR, T5)**, a recording-name collision between concurrent instances (silent overwrite, HTTP 404 in tests). Verified UI's fix 3cf0d1f in fresh clones: concurrent stress 4/12 → 0/12, rec_race 5/5 → 0/5.
- **Disk-full burst (11:45–11:48 IST):** traced to ENOSPC on `/` caused by leaked headless-Chrome temp dirs (about 132 GB; T6 removed only Chrome temp dirs older than 10 min). Filed **D10** (T5 headless tests leak about 319 MB per run). Self-reported and fixed **D11** (T6 helpers leaked too) and **D13** (T6 repo copy recursed once temp dirs fell back into the checkout).
- **Final rerun:** fresh clone 03fc993, private venvs: 652/44/0 on 3.13.5/3.12.16/3.10.22; integration 37/37, 31/37 without pyserial (NOT RUN = FAIL); confirmed at b1a2153.
- **Verdict:** verification_report.md §0.

## 2. Tests actually executed (by T6, from clean `git archive` exports, venv from requirements.txt + pyserial, Python 3.13.5; v4 also on 3.12.16 and 3.10.22, see TEST_RESULTS.md)
| Command | Commit | Result |
|---|---|---|
| `python -m pytest -q -rs` (repo root, all suites) | 0c25062 | 513 passed, 44 skipped, 0 failed (506 at dc3123a) |
| `python reports/audit/integration_run.py <export> <out>` (D6 re-test, A1–A10) | f058c9a | 30/30 PASS → D6 closed |
| `python -m pytest -q` (repo root; check of PM's 499/45 claim) | c942d6f | 501 passed, 44 skipped (= 499 + 2 new T6 tests; PM's 45th skip = pty serial test without pyserial) |
| `python -m pytest heading_core/tests` / `docs/math/sensor-spec` / `sim/tests` / `firmware_bridge/tests` / `app/tests` | 471724e | 76 / 23 / 152 (+44 N/A skips) / 95 / 45 passed |
| `python -m pytest tests -q -s` (T6 suite) | dc3123a | 111 passed |
| `python reports/audit/integration_run.py <export> <out>` | 471724e | 25/27 PASS; A8, A8b FAIL → D6 (found) |
| `pytest tests/test_t6_stale_quant.py -s` (D3 re-test) | c942d6f | E3b stress 0/20 falsely stale (was 4/20); E3c–E3g pass |
| `python reports/audit/raw/d3_regress.py` | c942d6f | F1–F5, F7, F8 flagged in 0.2–1.7 s; F6, F9, F10 not flagged (documented limitation) |
| `pytest tests/test_t6_claims.py -s` | dc3123a | 4 passed; 0 applied hardware tags, 30 mentions confirmed by hand, 0 navigation claims |
Earlier runs (403976b, 0aaa066, 1befc7b) are listed in TEST_RESULTS.md.

## 3. Open limitations
1. Nothing transfers to real hardware; all evidence is simulated or replayed, with an idealised uniform field.
2. MSP tested only with hand-built frames and the fake FC; live USB serial never run.
3. L-D3: in quantised mode a frozen mag is undetectable when stationary, below the 1°/s gyro deadband, or in a level yaw turn without gyro (PM decision (a), HEADING_MATH 14a).
4. ~~L-SER~~ withdrawn; it was defect D8, now fixed and re-tested. **F11:** the device UID is self-reported and spoofable, so an allowlist match is an administrative trust decision, not hardware authentication. Its badge reads "ALLOWLISTED DEVICE (identity not authenticated)" (T6 decision, §2d). The identity is read once at connect. Ingest keeps the client-declared source, shown as UNVERIFIED SOURCE.
5. UI checked through headless-Chrome DOM text and the API, not pixels; the demo video was not inspected frame by frame.
6. T6's numeric targets have not been reviewed by the owner.
7. Process incidents caused by T6 (disclosed and repaired): D5 (HEAD detach, cherry-picked as 84fc231) and 9b808b5 (tracker row revert, fixed in 0aaa066).

## 4. Money spent and paid tools or services
- Money spent: **none**.
- Paid tools or services: **none**. Only free tools were used: Python, numpy, pytest, jsonschema, pyserial, git, Google Chrome (headless, already on the box), Node.js, poppler-utils, uv (free CPython 3.12/3.10 builds), gitleaks (OSS). No sign-ups, subscriptions, API keys or cloud services.
