# Project Status — Virtual Heading Monitor (RM3100 + Matek FC)

**Last updated:** 2026-11-27 10:06 IST (Asia/Calcutta) by PM & CTO

**Acceptance boundary (virtual only):** Acceptance covers **simulated and replayed data only**. No physical flight hardware was operated. No autonomous navigation exists (the application reports compass heading only). No paid services were used.

**Overall:** **CONDITIONAL PASS: corrections in progress, pending independent Codex re-verification.** An independent Codex audit of commit `f1a0e3e` issued a CONDITIONAL PASS for the virtual scope. The Auditor's last completed official verdict (v3.0 / v3.1) remains **PASS for the virtual scope only**; that result is not withdrawn, but completion is not declared unconditional until the D8 serial-provenance corrections and this documentation update are re-verified. Hardware validation is **NOT RUN**. Nothing is labelled hardware-verified: `reports/hardware_logs/` does not exist. Consolidated report: `reports/FINAL_REPORT.md`.

## Phase
| Phase | Status |
|---|---|
| 0. Scaffold repo, contracts, rules | DONE |
| 1. Research + core modules (T1–T4) | DONE (Auditor: PASS, virtual scope) |
| 2. Application (T5) | DONE (Auditor: PASS; D6 CLOSED). D8 (serial provenance) in progress in firmware/UI |
| 3. Independent verification (T6) | Auditor v3.1 **PASS (virtual scope only)** recorded; **re-verification pending** after D8 and these documentation corrections |
| 4. Integration + consolidated report (T7) | IN-PROGRESS — documentation corrections after the Codex CONDITIONAL PASS; FINAL_REPORT being kept in step |

## Tasks
| ID | Status | Summary |
|---|---|---|
| T1 | PASS (Auditor) | Hardware fact sheet and datasheet checks. Exact FC model still UNKNOWN. Nothing measured on the team's hardware. |
| T2 | PASS (Auditor) | heading_core + docs/math; D1 and D3 closed; residual limitation 14a / L-D3 documented. |
| T3 | PASS (Auditor) | Simulator, 8 scenarios, 152 tests + 44 documented N/A skips (see `reports/audit/skipped_tests.md`). |
| T4 | PASS (Auditor, pre-D8) | firmware_bridge + FC_SETUP.md; 95 tests with pyserial at the v3.0 audit. Live FC never connected. D8 identity/allowlist implementation in progress. |
| T5 | PASS (Auditor, pre-D8) | App UI; D6 closed (replayed hardware is REPLAY (recorded hardware), not live). D8 badge/provenance update in progress. |
| T6 | PASS (Auditor v3.1); re-run pending | Final verification v3.0/v3.1: 513 passed, 44 skipped, 0 failed at `0c25062`; integration 30/30 at `f058c9a`. D7 CLOSED in `02c0ec0`. Codex CONDITIONAL PASS at `f1a0e3e`. Official re-run after D8 is outstanding. |
| T7 | IN-PROGRESS | `reports/FINAL_REPORT.md` updated for the Codex CONDITIONAL PASS, D7/R8/D8 wording, skipped-test inventory, and the virtual-only boundary. Hardware validation NOT RUN. |
| T8 | IN-PROGRESS | owner assigned this role 2026-11-26; no code ownership |

## Unresolved defects
| ID | Severity | Status | Summary |
|---|---|---|---|
| D8 | Priority 1 (Codex audit of `f1a0e3e`) | IN PROGRESS | A serial connection is not proof of hardware. A fake FC that reports `SIML`/`SIMF` must show SIMULATED; an unknown serial device must show UNVERIFIED SOURCE; HARDWARE requires a UID match in `config/verified_devices.json` (ships empty). Decision recorded in `ARCHITECTURE.md` (`1bef73e`). Firmware and UI are applying the change; the Auditor is rewriting A10c. This supersedes L-SER. |

## Closed defects
D1 (MAJOR, CLOSED), D2 (MINOR, CLOSED), D3 (MAJOR, CLOSED), D4 (MAJOR, CLOSED), D5 (MINOR, CLOSED), D6 (CRITICAL, CLOSED at `f058c9a` / `0c25062`), D7 (MINOR, **CLOSED** in `02c0ec0` after the R8 wording update in `2564266`). D8, opened after D7 closed, changes R8 again (see above).

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
- Latest completed Auditor whole-repo run (2026-11-27 01:25 IST, `0c25062`): **513 passed, 44 skipped, 0 failed** [SIMULATED]. The 44 skips are listed in `reports/audit/skipped_tests.md`.
- Integrated end-to-end A1–A10 (2026-11-27 01:17 IST, `f058c9a`): **30/30 PASS** [SIMULATED]/[REPLAYED], including the then-current A10c observation (virtual pty shown as HARDWARE, logged as L-SER). A10c is being rewritten for D8; that result is not the acceptance criterion going forward.
- PM suite on the tree at `1bef73e` (2026-11-27, `python3 -m pytest -q -rs`, pyserial + Chrome + Node present): **513 passed, 44 skipped** in 139.51 s, matching the official skip list.
- Hardware validation checklist HV1–HV9: **NOT RUN**.
- Spend: none. No paid services were used.

See `reports/FINAL_REPORT.md` for the consolidated report, `docs/INSTALL_PREREQS.md` for install and browser-test prerequisites, TEAM_TRACKER.md for per-task detail, BLOCKERS.md for open issues, and TEST_RESULTS.md for executed Auditor tests.
