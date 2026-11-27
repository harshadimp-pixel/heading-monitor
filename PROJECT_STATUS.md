# Project Status — Virtual Heading Monitor (RM3100 + Matek FC)

**Last updated:** 2026-11-27 12:22 IST (Asia/Calcutta) by PM & CTO

**Acceptance boundary (virtual only):** Acceptance covers **simulated and replayed data only**. No physical flight hardware was operated. No autonomous navigation exists (the application reports compass heading only). No paid services were used.

**Visibility:** The GitHub repository is **public by owner decision** (2026-11-27). It stays public while this work is finished and Codex re-verifies; the owner then plans to make it private. A secrets scan with gitleaks 8.28.0 found 0 findings in the full history and tree. No secrets, tokens, credentials or personal data may be committed.

**Overall:** **PASS (virtual scope), pending independent Codex re-verification** (Auditor v5 FINAL, `reports/verification_report.md` §0). This verdict is **not unconditional**. Nothing is hardware-verified: `reports/hardware_logs/` does not exist. Hardware validation is **NOT RUN**. Consolidated report: `reports/FINAL_REPORT.md`.

## Phase
| Phase | Status |
|---|---|
| 0. Scaffold repo, contracts, rules | DONE |
| 1. Research + core modules (T1–T4) | DONE (Auditor: PASS, virtual scope) |
| 2. Application (T5) | DONE (Auditor: PASS, virtual scope; D10 OPEN, MINOR, test hygiene) |
| 3. Independent verification (T6) | Auditor v5 FINAL **PASS (virtual scope), pending independent Codex re-verification** at `03fc993` / `b1a2153` |
| 4. Integration + consolidated report (T7) | REVIEW — FINAL_REPORT refreshed to Auditor v5; Codex re-verification is the next step |

## Tasks
| ID | Status | Summary |
|---|---|---|
| T1 | PASS (Auditor) | Hardware fact sheet and datasheet checks. Exact FC model still UNKNOWN. Nothing measured on the team's hardware. |
| T2 | PASS (Auditor) | heading_core + docs/math; D1 and D3 closed; residual limitation 14a / L-D3 documented. |
| T3 | PASS (Auditor) | Simulator, 8 scenarios, 152 tests + 44 documented N/A skips (see `reports/audit/skipped_tests.md`). |
| T4 | PASS (Auditor, virtual scope) | firmware_bridge + FC_SETUP.md. D8 identity/allowlist: e37430b, F12 fix edc3ee0, label docs 3066359. Live FC never connected. |
| T5 | PASS (Auditor, virtual scope); D10 OPEN | App UI. D6 closed. D8: e538cea, hardening 6c1e5b5, label 479a72c. D9 closed. D12 flake fix 3cf0d1f. D10 (Chrome temp leak in headless UI tests) remains OPEN, MINOR. |
| T6 | DONE (v5 FINAL) | Fresh-clone rerun at `03fc993` / `b1a2153`: 652 passed, 44 skipped, 0 failed on Python 3.13.5, 3.12.16 and 3.10.22; integration 37/37 with pyserial, 31/37 without (6 serial D8 steps FAIL NOT RUN). Verdict: PASS (virtual scope), pending independent Codex re-verification. |
| T7 | REVIEW | `reports/FINAL_REPORT.md` refreshed to Auditor v5 figures, D8 close, allowlisted-device label, public-repo wording and next steps. Codex re-verification outstanding. |
| T8 | IN-PROGRESS | owner assigned this role 2026-11-26; no code ownership |

## Unresolved defects
| ID | Severity | Status | Summary |
|---|---|---|---|
| D10 | MINOR (test environment, UI) | OPEN | `app/tests/test_app_ui_headless.py` (`_cdp.py`) leaves about 38 Chrome temp dirs (about 319 MB) per run. Test hygiene only; product behaviour is unaffected. Suggested fix: private TMPDIR or user-data-dir, then clean up. |

## Closed defects
D1 (MAJOR, CLOSED), D2 (MINOR, CLOSED), D3 (MAJOR, CLOSED), D4 (MAJOR, CLOSED), D5 (MINOR, CLOSED), D6 (CRITICAL, CLOSED at `f058c9a` / `0c25062`), D7 (MINOR, CLOSED in `02c0ec0`). **D8 (CRITICAL, CLOSED, virtual scope)** at `1ddd6b9` / `03fc993` / `b1a2153`: a serial connection is not proof of hardware; SIML/SIMF → SIMULATED; unknown serial → UNVERIFIED SOURCE; allowlisted live serial → **ALLOWLISTED DEVICE (identity not authenticated)** (not HARDWARE). Residual limitation F11/L11 (self-reported UID is spoofable). D9 CLOSED (`479a72c`). D11 CLOSED (`03fc993`). D12 CLOSED (`3cf0d1f`). D13 CLOSED (`b1a2153`). F12 (UID truncation) FIXED in `edc3ee0`. L-SER is withdrawn (superseded by D8).

## Open blockers
| ID | Status | Summary |
|---|---|---|
| B1 | OPEN (accepted for virtual phase) | No physical RM3100 + Matek FC is connected to the project environment |
| B2 | OPEN | Exact Matek FC model and firmware (INAV/ArduPilot/Betaflight) on the team's board unknown |
| B3 | OPEN (non-blocking) | firmware_bridge cannot undo INAV's mag calibration normalisation |
| B4 | OPEN (non-blocking) | INAV 10 is still a release candidate |

## Evidence status
- Hardware-verified results: **none**. No committed hardware log and no auditor hardware sign-off exist, so nothing carries that label.
- All performance figures and executed tests are [SIMULATED] or [REPLAYED] unless labelled [DATASHEET].
- Latest **official** Auditor whole-repo run (2026-11-27, 11:54–12:17 IST, fresh clones of `03fc993` / `b1a2153`): **652 passed, 44 skipped, 0 failed** on Python 3.13.5, 3.12.16 and 3.10.22 [SIMULATED]. Integration **37/37** with pyserial; 31/37 without pyserial (6 serial D8 steps FAIL 'NOT RUN').
- Historical official (pre-D8, v3.0): 513 passed, 44 skipped, 0 failed at `0c25062`; integration 30/30 at `f058c9a`. Intermediate v4: 638/44/0 at `8343656`; 651/44/0 at `1ddd6b9`.
- Codex cross-check (`reports/verification_report.md` §2f): tilted-spin 0.41°, wizard 0.72°, MC ellipsoid fit 0.301° RMS — all match.
- Traceability: 13 delivered, 1 partial (R6), 0 unmet. N6 re-traced as PUBLIC.
- gitleaks 8.28.0: 0 findings in history and tree. UIDs are synthetic.
- Hardware validation checklist HV1–HV9: **NOT RUN**.
- Spend: none. No paid services were used.

See `reports/FINAL_REPORT.md` for the consolidated report, `docs/INSTALL_PREREQS.md` for install and browser-test prerequisites, TEAM_TRACKER.md for per-task detail, BLOCKERS.md for open issues, and TEST_RESULTS.md for executed Auditor tests.
