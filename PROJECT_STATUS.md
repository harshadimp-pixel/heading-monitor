# Project Status — Virtual Heading Monitor (RM3100 + Matek FC)

**Last updated:** 2026-11-27 12:05 IST (Asia/Calcutta) by PM & CTO

**Acceptance boundary (virtual only):** Acceptance covers **simulated and replayed data only**. No physical flight hardware was operated. No autonomous navigation exists (the application reports compass heading only). No paid services were used.

**Visibility:** The GitHub repository is **public by owner decision** (2026-11-27). It stays public while this work is finished and Codex re-verifies; the owner then plans to make it private. No secrets, tokens, credentials or personal data may be committed.

**Overall:** **CONDITIONAL PASS: corrections in progress, pending independent Codex re-verification.** An independent Codex audit of commit `f1a0e3e` issued a CONDITIONAL PASS for the virtual scope. The D8 serial-provenance corrections, the allowlisted-device label, and the recording-name flake fix are implemented and pushed; the Auditor's official rerun on a fresh clone of the final HEAD is outstanding. Hardware validation is **NOT RUN**. Nothing is labelled hardware-verified: `reports/hardware_logs/` does not exist. Consolidated report: `reports/FINAL_REPORT.md` (to be refreshed after the Auditor's figures).

## Phase
| Phase | Status |
|---|---|
| 0. Scaffold repo, contracts, rules | DONE |
| 1. Research + core modules (T1–T4) | DONE (Auditor: PASS, virtual scope; T4 updated for D8) |
| 2. Application (T5) | DONE (Auditor: PASS; D6 CLOSED). D8 badge/provenance and the flaky-recording fix are implemented; official re-verification pending |
| 3. Independent verification (T6) | Auditor v3.1 **PASS (virtual scope only)** recorded; **v4 re-verification in progress** after D8, the label change and `3cf0d1f` |
| 4. Integration + consolidated report (T7) | IN-PROGRESS — FINAL_REPORT refresh waits on the Auditor's official figures |

## Tasks
| ID | Status | Summary |
|---|---|---|
| T1 | PASS (Auditor) | Hardware fact sheet and datasheet checks. Exact FC model still UNKNOWN. Nothing measured on the team's hardware. |
| T2 | PASS (Auditor) | heading_core + docs/math; D1 and D3 closed; residual limitation 14a / L-D3 documented. |
| T3 | PASS (Auditor) | Simulator, 8 scenarios, 152 tests + 44 documented N/A skips (see `reports/audit/skipped_tests.md`). |
| T4 | PASS (Auditor, pre-D8); D8 implemented | firmware_bridge + FC_SETUP.md. D8 identity/allowlist: e37430b, F12 fix edc3ee0, label docs 3066359. Live FC never connected. |
| T5 | PASS (Auditor, pre-D8); D8 implemented | App UI. D6 closed. D8: e538cea, hardening 6c1e5b5, label 479a72c, flake fix 3cf0d1f (unique recording names). |
| T6 | IN-PROGRESS (v4) | Official fresh-clone rerun outstanding at HEAD (`1f3883e`, code HEAD `3cf0d1f` + D11 `03fc993`). Earlier: D8 filed, A10c rewritten, F11 spoof tests, label assertions `1ddd6b9`, Chrome temp-dir cleanup `03fc993`. Previous official: v3.1 PASS (virtual scope) at `02c0ec0`. |
| T7 | IN-PROGRESS | `reports/FINAL_REPORT.md` needs a refresh after the Auditor's official figures (D8 status, label, suite counts, public-repo wording). |
| T8 | IN-PROGRESS | owner assigned this role 2026-11-26; no code ownership |

## Unresolved defects
| ID | Severity | Status | Summary |
|---|---|---|---|
| D8 | Priority 1 (Codex audit of `f1a0e3e`) | IMPLEMENTED, official close pending T6 rerun | A serial connection is not proof of hardware. A fake FC that reports `SIML`/`SIMF` shows SIMULATED; an unknown serial device shows UNVERIFIED SOURCE; an allowlisted live serial device shows **ALLOWLISTED DEVICE (identity not authenticated)** (not HARDWARE). The allowlist (`config/verified_devices.json`) ships empty. Decision in `ARCHITECTURE.md` (`1bef73e`, later interface updates). A UID is self-reported and spoofable (F11/L11). This supersedes L-SER. |
| D9 | MINOR | REVIEW | Relabel `test_e2e_bridge_over_pty` as an F11 spoofable-UID limitation demonstration, not hardware validation. UI change landed in `479a72c`; official close pending T6. |
| D11 | (Auditor, self-reported) | REVIEW | Headless Chrome leaked ~36 MB per launch into `/tmp`. T6 DOM helpers now use a private TMPDIR and remove it (`03fc993`). |

## Closed defects
D1 (MAJOR, CLOSED), D2 (MINOR, CLOSED), D3 (MAJOR, CLOSED), D4 (MAJOR, CLOSED), D5 (MINOR, CLOSED), D6 (CRITICAL, CLOSED at `f058c9a` / `0c25062`), D7 (MINOR, **CLOSED** in `02c0ec0` after the R8 wording update in `2564266`). F12 (UID truncation) FIXED in `edc3ee0`.

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
- Latest **official** Auditor whole-repo run (2026-11-27 01:25 IST, `0c25062`): **513 passed, 44 skipped, 0 failed** [SIMULATED]. This predates D8. A v4 official rerun on a fresh clone is outstanding.
- Developer-reported figures after D8 (not official): UI at `479a72c` reported 651 passed, 44 skipped with pyserial, and 37/37 integration (UI-run). Firmware at `3066359` reported 140 passed, 2 skipped for bridge + research.
- Integrated end-to-end at `f058c9a` (pre-D8): **30/30 PASS**, including the then-current A10c (virtual pty shown as HARDWARE, logged as L-SER). A10c has been rewritten; that result is not the acceptance criterion going forward.
- Hardware validation checklist HV1–HV9: **NOT RUN**.
- Spend: none. No paid services were used.

See `reports/FINAL_REPORT.md` for the consolidated report, `docs/INSTALL_PREREQS.md` for install and browser-test prerequisites, TEAM_TRACKER.md for per-task detail, BLOCKERS.md for open issues, and TEST_RESULTS.md for executed Auditor tests.
