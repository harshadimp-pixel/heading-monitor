# T6 Verification Report: v5 FINAL (D8 re-verification, badge-label decision, flake fix 3cf0d1f)

Auditor: Testing & Technical Auditor (T6). Updated 2026-11-27 ~12:20 IST.
**Code under test:** fresh `git clone`s (porcelain-clean) or clean `git archive` exports only, never the shared working tree. Private venvs under /workspace/audit (never /tmp/hm-venv), private TMPDIR/HOME per run.
- **Final code HEAD `03fc993`** = UI's flake fix `3cf0d1f` (on 479a72c: label + D9) + T6's D11 helper fix (tests only). Fresh clone: full suite on Python 3.13.5, 3.12.16 and 3.10.22, integration with and without pyserial, concurrent-run stress before/after the fix (§2i). No UI/firmware commit after 3cf0d1f was pending (origin checked at ~12:10 IST).
- **Confirmation at `b1a2153`** (= 03fc993 + T6's D13 test-helper fix, no product-code change), fresh clone, Python 3.13.5: suite 652 passed, 44 skipped, 0 failed; integration 37/37; no-pyserial 31/37.
- **Earlier v4 run at `1ddd6b9`** (= 479a72c + T6 tests): 651/44/0 on all three Pythons, integration 37/37 and 31/37. The provisional run at `25e308d` (before the label) is kept in TEST_RESULTS.md.
- **Earlier v4 run at `8343656`** (edc3ee0 + T6 commits): suite 638/44/0 on all three Python versions; integration 35/35 (old A10f criterion). Kept as history in TEST_RESULTS.md.
- **v3.x** (0c25062 / f058c9a) is kept below as history. Its L-SER acceptance is **WITHDRAWN** (superseded by D8).

Environment: Linux box. Three private venvs from `requirements.txt`, all with optional pyserial 3.5, pytest 9.2.0 and jsonschema 4.26.0:
- Python 3.13.5 with numpy 2.5.5;
- Python 3.12.16 with numpy 2.5.5 (uv);
- Python 3.10.22 with numpy 2.2.6 (uv).

Google Chrome 156.0.8078.47 headless, run with a fresh temporary `--user-data-dir` plus `--incognito` and a private per-launch TMPDIR (D11), all removed afterwards; the integration run used `HOME` set to an empty temporary directory. Node runs the app's own `headingmath.js`.
Companion documents in `reports/audit/`:
- `integration_results.md`, `traceability.md`, `claims_audit.md`, `team_rules_compliance.md`;
- `skipped_tests.md`, `d8_spec_review.md`;
- raw evidence in `raw/`.

Executed counts: `TEST_RESULTS.md`.

Evidence labels: every accuracy and robustness result is **[SIMULATED]** or **[REPLAYED]**; RM3100 constants are **[DATASHEET]**; MSP scaling is **[SOURCE-CODE]**. **Nothing is [HARDWARE-VERIFIED]:** `reports/hardware_logs/` does not exist.

## 0. OVERALL VERDICT: **PASS (virtual scope), pending independent Codex re-verification**
This verdict is **not unconditional**. It covers the virtual (simulated/replayed) scope only, and nothing is hardware-verified. It stays pending an independent Codex re-verification of `03fc993`/`b1a2153`.
Reasons:
1. **The software runs.** For every step T6 started a fresh app on a PID-verified ephemeral port: **integration **37/37 with pyserial**. Without pyserial: 31/37, and all 6 serial D8 steps (A10c–A10g, A10i) are reported as FAIL 'NOT RUN', never as passes** at `03fc993` (fresh clone; same at `b1a2153`), covering:
   - 8 sim scenarios plus motor interference;
   - 7 example-log replays;
   - fake FC capture → replay → app, and fake FC → bridge → app;
   - the calibration wizard;
   - frozen/stale data and a missing serial port;
   - headless-Chrome checks of the badge, heading, warnings, GPS 'Unknown' and banners;
   - D6 edge cases;
   - **D8 steps A10c–A10i and A10z.**
2. **All suites green at `03fc993`:** **652 passed, 44 skipped, 0 failed** on Python 3.13.5, 652/44/0 on 3.12.16 and 652/44/0 on 3.10.22 (and 652 passed, 44 skipped, 0 failed at `b1a2153` on 3.13.5). The 44 skips are listed one by one in `skipped_tests.md`; all are N/A spec keys asserted analytically elsewhere, and none hides a required check.
3. **D8 (CRITICAL, serial treated as proof of hardware): CLOSED (virtual scope). The functional fix, the label, D9 and the reruns at 1ddd6b9 and 03fc993 are all verified; F11 remains an unresolved limitation** (§2e).
   - A fake FC on a virtual pty shows SIMULATED; unknown or unidentified devices show UNVERIFIED SOURCE.
   - The shipped allowlist is empty, so **no path can show the allowlisted live badge in the shipped configuration**.
   - Forged provenance in ingest, replay and sim samples is ignored.
   - The F12 UID-length bug found by T6 is fixed.
   - L-SER is withdrawn. **F11** (self-reported, spoofable UID) is recorded as an unresolved limitation.
4. **Badge-label decision (§2d)**, accepted by the PM in d5374a1: the allowlisted badge reads "ALLOWLISTED DEVICE (identity not authenticated)" and never the bare word HARDWARE.
5. **Flake resolved (§2i):** the intermittent app/tests failure is the recording-name collision D12, reproduced by T6 (4/12 concurrent runs failed at 1ddd6b9, rec_race 5/5 collisions) and gone after 3cf0d1f (0/12, 0/5). The 11:45–11:48 IST burst was ENOSPC on `/` (Chrome temp leak, D10/D11) amplified by a T6 helper weakness (D13, fixed); not a product defect.
6. **All required reports exist**, and the claims audit is clean. No text calls an allowlist match proof of physical authenticity (§2g).

Open, non-blocking: 
- **F11:** the MSP UID is self-reported and spoofable; an allowlist match is administrative trust, not hardware authentication (documented; shipped allowlist empty).
- **No hardware validation:** nothing is [HARDWARE-VERIFIED]; `reports/hardware_logs/` does not exist. The HARDWARE_VALIDATION_CHECKLIST has to be run on the real RM3100 + Matek FC before any hardware claim.
- **L-D3 and the other v3 limitations** (LIMITATIONS below) are unchanged.
- **D10 (MINOR, T5, OPEN):** `app/tests/test_app_ui_headless.py` via `_cdp.py` leaves about 38 Chrome temp dirs (about 319 MB) in $TMPDIR per run. This is test-environment only and does not affect the product, but on a shared box it fills `/` (it contributed to the 11:45 IST ENOSPC).
- **PM notes:** add a CHANGELOG entry for d5374a1 (REQUIREMENTS.md:3); fix FINAL_REPORT.md:7 and :75, which still say PRIVATE (N6); if FINAL_REPORT quotes this §0, quote the verdict verbatim, including 'pending independent Codex re-verification'; the untracked `pytest-of-box/` in the shared checkout (11:46 IST, ENOSPC fallback) should be removed by whoever created it.
- **No rejected positioning, distance or GPS-independent-navigation claim** was found in the deliverables (claims_audit.md).

## 1. Verdict per deliverable (v5 FINAL)
| Deliverable | Owner | Verdict | Evidence (one line) |
|---|---|---|---|
| T1 hardware fact sheet (`docs/hardware/`) | HW Research | **PASS** | Unchanged since v3 [DATASHEET]. |
| T2 heading_core + `docs/math/` | Math | **PASS** | 76 owner tests + 27 docs tests pass; MC accuracy reproduced byte-for-byte (ellipsoid fit 0.301° RMS, §2f). |
| T3 simulator (`sim/`) | Sim | **PASS** | 152 passed + 44 documented N/A skips (skipped_tests.md); A1/A1b. |
| T4 firmware_bridge + FC_SETUP + D8_PROVENANCE | FW | **PASS (virtual scope)** | 138 bridge tests; T6 bridge black-box 32/32, including F12 `[extended]` and the F11 spoof; SIML/SIMF beats an allowlisted UID; fail-closed allowlist. F11 documented (b27644a). |
| T5 app (`app/`) | UI | **PASS (virtual scope)** (D10 open, MINOR, test-env) | App tests 86/86 at 03fc993 (including 12 forged-claim and 19 D8 serial); T6 app/DOM black-box 30/30; A10c–A10i; server-side trust boundary (6c1e5b5). Label and banner implemented (479a72c) and verified in the DOM; D9 closed; D12 recording collision fixed (3cf0d1f) and verified (0/12 concurrent failures). D10 (Chrome temp leak in `app/tests` headless tests, test-env only) open, MINOR. |
| PM docs | PM | **PASS** (with notes) | R8, README rule 2 and ARCHITECTURE match the D8 behaviour and the label decision (d5374a1, verified word for word, §2d). Notes: no CHANGELOG entry for d5374a1 (REQUIREMENTS.md:3 requires one); FINAL_REPORT.md:7 and :75 still say PRIVATE (N6). |
| T6 (TEST_PLAN, tests, reports, audit) | QA | complete | T6 tests 173 (111 + 32 bridge + 30 app/DOM); D8 regression suites; skipped_tests.md; harness Chrome fix. Self-reported D11 (Chrome temp leak in T6 helpers) and D13 (repo-copy recursion when temp falls back into the checkout) both fixed and verified. |

## 2d. Badge-label decision (T6, D8 / F11): "ALLOWLISTED DEVICE (identity not authenticated)" replaces HARDWARE
**Decision:** a live sample from the app's own serial source, whose self-reported UID the app re-checks and finds in `config/verified_devices.json`, must be displayed as:
- **Badge (exact constant text):** `ALLOWLISTED DEVICE (identity not authenticated)`
- **Banner (exact text):** `Live serial device whose self-reported UID is on the local allowlist. The UID is not cryptographic proof; this is not hardware verification.`
- The internal values do not change: `sample.source = "hardware"`, `meta.provenance = "verified"`, `device_verified`/`live_hardware = true`. Only the displayed text changes.
- The bare word **HARDWARE must never appear alone as the badge**. The old banner wording "from a verified device" must go.

**Reasons:**
1. **F11, demonstrated by T6.** MSP identity (variant, board, UID) is self-reported over the same wire.
   - T6's emulator on a virtual pty, with no hardware behind it, claims INAV/MKF4 and an allowlisted UID. It passes the allowlist and is rendered with the allowlisted live badge (`test_d8_F11_spoof_*`, `test_F11_emulated_device_reporting_allowlisted_uid_is_accepted[MKH7|MKF4]`, integration A10f).
   - An allowlist match is therefore an **administrative trust decision**, not hardware authentication. A badge reading HARDWARE would assert something the system cannot know.
2. **N4.** No simulated result may be presented as hardware. Under the old text, the F11 spoof (a simulator) would be shown as HARDWARE.
3. **The claims rules.** Nothing may imply [HARDWARE-VERIFIED] evidence without a committed hardware log and the Auditor's sign-off. "HARDWARE" with "from a verified device" reads as verification.
4. **No loss of function.** The allowlist ships empty, so no user sees this badge today. If an entry is ever added after the hardware-validation checklist, the new label still distinguishes it from UNVERIFIED SOURCE.

**Status:**
- **PM docs: accepted and verified.** T6 checked d5374a1 word for word: ARCHITECTURE.md carries the exact badge and banner text, and README rule 2 and REQUIREMENTS R8 carry the badge text, F11 and "not hardware verification". It contains no allowlist-as-authenticity wording. The one gap is that no CHANGELOG entry was added for this R8 change (note to the PM).
- **UI implementation: IMPLEMENTED in 479a72c and verified by T6. Headless Chrome A10f shows the badge 'ALLOWLISTED DEVICE (identity not authenticated)' and the exact decided banner; A10z found no bare-HARDWARE badge in any of the 10 DOM dumps. Source inspection: `badgeInfo` never returns the internal `SOURCE_LABEL.hardware` text for source 'hardware', and the page only displays `badgeInfo().text`. T6 U2 now asserts this for 30 transport/verification combinations.** T6 tests now assert it exactly:
  - `tests/test_t6_d8_provenance.py::_assert_allowlisted_rendering` checks the badge equals the label, is not bare HARDWARE, the banner contains "self-reported UID", "not cryptographic proof" and "not hardware verification", and does not say "verified device";
  - integration A10f checks the same;
  - A10z checks that no rendered badge in the whole run is bare HARDWARE.
- Note for UI: `HARDWARE_LABEL` also feeds the pure `badgeLabel()` mapping. T6 U2 accepts either text there, because no displayed badge uses `badgeLabel` for hardware.

## 2e. D8 re-test (bridge e37430b + F12 edc3ee0 + b27644a docs; app e538cea + 6c1e5b5 hardening; PM 1bef73e/53f8bf7/d5374a1)
**Black-box, T6-owned (no product code written by T6):**
- **`tests/test_t6_d8_bridge.py` (bridge CLI, 32 cases):**
  - the shipped empty allowlist;
  - fake FC (pty and `--fake-fc`) → sim/simulated;
  - with an empty allowlist nothing is ever verified, even the allowlisted UID, a missing UID or failed identity;
  - allowlisted UID → verified, with normalisation;
  - non-allowlisted UIDs all fail: other, missing, truncated, **extended (F12)**, zero, byte-reversed, one-bit-off;
  - malformed allowlists (empty entry, wildcard, prefix, bad JSON, bare list, non-list) fail closed;
  - SIML/SIMF beats an allowlisted UID;
  - spelling variants are never verified;
  - replay is never verified;
  - F11 spoof (MKH7, MKF4) accepted, labelled as a limitation.
- **`tests/test_t6_d8_provenance.py` (app + rendered DOM, 30 cases):**
  - fake FC over a pty → SIMULATED;
  - unknown device (5 variants) → UNVERIFIED SOURCE with "reported by device";
  - spelling variants (6) are never the allowlisted badge;
  - allowlisted UID → exact decided label and banner;
  - non-allowlisted or spoofed UIDs (7) → UNVERIFIED;
  - SIML + allowlisted UID → not allowlisted;
  - replay with forged provenance → 'REPLAY (recorded hardware)';
  - ingest variants (4) never live;
  - F11 spoof INAV/MKF4.
- **History:**
  - 1bef73e (before the fix): 24 failed, 5 passed.
  - af640ae: 14 failed (bridge fixed, UI not yet).
  - 8343656: 30/30 and 32/32 (old label criterion).
  - 25e308d: 28/30 (before the label landed).
  - 1ddd6b9: app/DOM 30/30 and bridge 32/32, with the exact label and banner asserted.
  - **03fc993 and b1a2153 (final): unchanged, 30/30 and 32/32** (inside the full suites).
- **Integration (headless Chrome DOM):**
  - **A10c:** product fake FC on a pty → SIMULATED, 0 live. This step FAILS on any HARDWARE or live record.
  - **A10d and A10e:** unknown and unidentified devices → UNVERIFIED SOURCE.
  - **A10f:** F11 limitation demonstration with the exact label and banner.
  - **A10g:** UID one bit off → UNVERIFIED SOURCE.
  - **A10h:** shipped allowlist empty.
  - **A10i (new for 6c1e5b5):** forged ingest samples POSTed into a running serial app with a non-empty allowlist. They claim the allowlisted UID, `provenance: verified`, `device_verified` and `live_hardware`, and must never be live or allowlisted.
  - **A10z:** no bare-HARDWARE badge anywhere.
  - **Without pyserial,** every serial D8 step is reported as **FAIL (NOT RUN)**, never as a pass and never silently omitted.
- **Firmware claims:**
  - "my bridge file gives 31 passed" → confirmed as **32/32**, because T6 added the MKF4 spoof case after that count;
  - "test_t6_msp 16 passed" → confirmed inside the full suite;
  - F12 (exactly 12 bytes; short/long → uid null, unverified) → confirmed by `[extended]`/`[truncated]` in both T6 files.
- **UI claims:**
  - "35/35 with pyserial" → T6 got 35/35 at 8343656 with the earlier harness.
  - "37/37 with pyserial, 31/37 without (A10c–g and A10i NOT RUN)" at 479a72c → **T6 reproduced both: 37/37 and 31/37** at 1ddd6b9 and again at 03fc993 (fresh clone), with the 6 NOT RUN steps counted as failures.
  - "badgeLabel still maps hardware to 'HARDWARE' but the page never displays it" → confirmed by source inspection and the DOM (§2d). T6's U2 no longer forces that internal mapping; it now asserts the displayed badge.
  - **UI's uncaptured app/tests failure (2 failed, 83 passed, 1 of 3 runs)** → reproduced and root-caused as D12, fixed by 3cf0d1f, verified (§2i).
- **D9 (MINOR, T5): **CLOSED.** The test is renamed `test_e2e_virtual_pty_allowlist_mechanism_and_F11_spoof_limitation_not_hardware_validation`; its docstring says 'LIMITATION DEMONSTRATION (F11), NOT hardware validation'; 3/3 cases pass at 1ddd6b9.** `app/tests/test_app_d8_serial_provenance.py::test_e2e_bridge_over_pty` drives an emulator reporting an allowlisted UID. It is an **F11 limitation demonstration, not hardware validation**, and no T6 report counts it as hardware validation.
- **D8 status: CLOSED (virtual scope). The functional fix, the label, D9 and the rerun at 1ddd6b9 are all verified; F11 remains an unresolved limitation.**

## 2f. Codex cross-check (Codex audit of f1a0e3e, relayed by the PM; the Codex report itself is not in the repo)
| Figure | Codex | T6 | Explanation |
|---|---|---|---|
| Suite | 513/44/0 at f1a0e3e, Python 3.12.14 | 513/44/0 at 0c25062 (f1a0e3e is docs-only on top of it); 638/44/0 at 8343656 on 3.13.5, 3.12.16 and 3.10.22; 651/44/0 at `1ddd6b9`; **652/44/0 at `03fc993`** (+1 UI regression test from 3cf0d1f) | **Match.** The extra tests at later commits are the D8 tests from Firmware, UI and T6. The patch version 3.12.14 vs 3.12.16 is not material. |
| MC accuracy, ellipsoid fit | 0.301° RMS | **0.301° RMS** (P95 0.605°, max 1.751°, N = 100 000); output identical to docs/math/accuracy_results.md (`python -m heading_core.experiments.accuracy_mc --trials 200 --seed 2026`, run at 8343656; raw/accuracy_mc_8343656.md) | **Match.** |
| Tilted-spin RMSE (A1, uncalibrated, after 1 s) | 0.41° | 0.41° at f058c9a; 0.42° at 8343656; 0.42° at `1ddd6b9`; **0.41° at `03fc993`** | Real-time pacing makes the sample set vary slightly from run to run (±0.01°). Not material. |
| Wizard RMSE (A5) | 0.72° | 0.72°; 0.70° at `1ddd6b9`; **0.72° at `03fc993`** (0.68–0.72° across runs: run-to-run variation of the real-time sample collection, not material) | **Match.** |
| Requirements | 10 delivered / 3 partial / 1 unmet | v3: 13/1/0; v4: 13/1/0 | **Codex was right at f1a0e3e.** R8 and N4 were really partial (D8: serial treated as hardware, which T6 had wrongly accepted as L-SER). N6 was unmet because the text said "private" while the repo was public, and T6's earlier unauthenticated 404 is no longer valid evidence. R6 is partial in both counts. After D8 and the N6 amendment (29ccbda), all re-tested, T6 counts 13/1/0, pending Codex's re-verification. |
| Integration runner | 25/30 (Chrome could not create its default profile) | fixed | `integration_run.py` now uses a fresh `--user-data-dir` (mkdtemp) plus `--incognito` and removes it afterwards. Verified with an empty temporary HOME (35/35 at 8343656), and the old command was shown to fail with a read-only HOME. A fresh profile *without* `--incognito` hung for 30–60 s in Chrome 156, which is why both flags are used. `app/tests/_cdp.py` (UI) already uses a temporary `--user-data-dir`, so no defect was filed. `docs/math/sensor-spec/render_pdf.sh` uses the default profile; it is a doc tool only (INFO for T2). |

## 2g. N6 re-trace, secrets and personal-data scan (repo PUBLIC by owner decision, 29ccbda)
- **Visibility:** the GitHub API reports `private: false`, `visibility: public`, which matches amended N6 → **Delivered**.
- **gitleaks 8.28.0:**
  - full history (all commits, `git log -p`): **0 findings**;
  - working tree at 29ccbda: **0 findings**;
  - redacted JSON reports in `raw/gitleaks_*_redacted.json`.
- **rg sweep:**
  - no `.env`, private-key or `.pem` files; no AWS/GitHub/Slack/OpenAI-style tokens;
  - no `/home/<user>` paths; phone-number matches were all false positives (numeric data).
- **Personal data (LOW/INFO, owner to decide):**
  - the owner's full name at REQUIREMENTS.md:3 and first name at HARDWARE_VALIDATION_CHECKLIST.md:3;
  - the GitHub username in FINAL_REPORT.md and the audit docs (it is part of the repo URL anyway);
  - e-mail addresses: only the public vendor address service@mateksys.com; commit metadata uses role@heading-monitor.local.
- **Device identifiers:** the UIDs in tests and docs (`3a0027…`, `ffeedd…`, and T6's `36 54 00 2b …`) are synthetic and documented as not a real board.
- **No CRITICAL finding.** No secret values are reproduced here.
- **Doc inconsistency (PM):** FINAL_REPORT.md:7 ("visibility last confirmed PRIVATE") and :75 (N6 "private repository") contradict 29ccbda.
- **Allowlist wording sweep:** T6 searched every report, README and requirement for allowlist-as-authenticity wording.
  - Firmware docs (b27644a), app/README and PM docs (d5374a1) all state "not hardware authentication / not cryptographic proof".
  - The only offending text was the app banner "Live hardware samples from a verified device" (app.js:217), which the label decision replaces (IMPLEMENTED in 479a72c and verified by T6. Headless Chrome A10f shows the badge 'ALLOWLISTED DEVICE (identity not authenticated)' and the exact decided banner; A10z found no bare-HARDWARE badge in any of the 10 DOM dumps. Source inspection: `badgeInfo` never returns the internal `SOURCE_LABEL.hardware` text for source 'hardware', and the page only displays `badgeInfo().text`. T6 U2 now asserts this for 30 transport/verification combinations).

## 2h. Python versions
The full suite was run on 3.13.5, 3.12.16 and 3.10.22 (uv-managed CPython, free) at 8343656, 1ddd6b9 and 03fc993; raw logs `raw/pytest_py3.12_03fc993.log`, `raw/pytest_py3.10_03fc993.log`. Results are identical across versions (TEST_RESULTS.md). N1 (Python 3.10+) is now actually exercised on 3.10.

## 2i. Flake investigation, the 11:45–11:48 IST failure burst, and test-environment defects
**1. UI's uncaptured app/tests failure (2 failed / 83 passed, 1 of 3 runs, before 3cf0d1f).**
- **T6 runs at 1ddd6b9:**
  - one test at a time, a private export per run, private venv: **13/13 app/tests runs passed** (85/85 each, about 31 s);
  - shuffled order (seed 1001): 1/1 passed (the other shuffled runs were stopped when the disk filled; see 2);
  - **virtual-serial subset** (app D8 serial, bridge pty modes, bridge D8, T6 D8 bridge + app/DOM, 139 tests): **15/15 runs passed**. Runs 16–18 failed only with `OSError: [Errno 28] No space left on device` (see 2), not on any assertion.
  - **Flake rate when runs are isolated: 0/28 for that cause.**
- **Mechanism reproduced independently by T6** (`/workspace/audit/rec_race.py`, 1ddd6b9):
  - Two app processes in the same checkout start a CSV recording in the same second, and **both get the same file name 5/5 times** (`rec-YYYYmmdd-HHMMSS.csv`, opened with mode "w"). One process truncates or overwrites the other's recording.
  - This only happens when runs share a checkout (the shared working copy, two dashboards). That matches UI's root cause: per-second recording names plus a fixed calibration test name, giving HTTP 404s.
  - Filed as **D12 (MAJOR, T5)**: silent loss of recording data with two concurrent instances, and a flaky required test.
  - **UI fix 3cf0d1f:** names use milliseconds + pid + counter and are opened exclusively. T6's before/after concurrent stress is in point 4.
- T6 cannot attribute UI's original uncaptured failure with certainty (no output was kept). The mechanism above is reproduced and consistent with it.

**2. The 11:45–11:48 IST burst (UI saw tests/ give 23 failed + 34 errors in the shared copy, recovered by 11:52). Cause: the box's root filesystem was 100 % full (ENOSPC). This is not a race in T6 tests and not the shared venv.**
- **Evidence:**
  - T6's own serial runs 16 (11:45:16) and 18 (11:46:38) failed with `No space left on device` on `/tmp/t6_d8_*` and `/tmp/pytest-of-box/...`.
  - At about 11:47, `df` showed `/` (which holds /tmp and /tmp/hm-venv) at 128G/128G, 100 %.
  - /tmp held about 132 GB of leftover headless-Chrome temp dirs: 2316 `scoped_dir*` (about 80 GB) and 7676 `.com.google.Chrome.*` (about 48 GB), plus about 4 GB of `com.google.Chrome.*`.
  - T6 deleted only such Chrome temp dirs older than 10 minutes at about 11:48. `/` dropped to 27 G used (21 %), and every later run passed. That matches "recovered by 11:52".
- **Why tests/ is sensitive:** the T6 D8 tests copy the repo and allowlists into fresh `tempfile.mkdtemp()` dirs under /tmp, and pytest's `tmp_path` lives there too. On ENOSPC they error in setup. They do not share state with other runs: every path is unique and nothing is written into the checkout.
- **Root cause of the leak:** Chrome 156 `--headless=new --dump-dom` leaves about 36 MB per launch in `$TMPDIR` and never removes it (reproduced: 1 launch → 2 new dirs, 36 MB). The temporary `--user-data-dir` cleanup does not cover these dirs.
- **Who leaked:** every headless-Chrome user on the box.
  - **T6's own helpers leaked**, and the 18-run flake loop (about 30 launches per run) added roughly 20 GB in about 20 minutes → **D11 (MINOR, T6, self-reported) CLOSED in 03fc993**. Each launch now gets a private TMPDIR containing the profile, removed afterwards; T6 verified 0 leftovers after a full `tests/test_t6_d8_provenance.py` run (30 passed).
  - **UI's `app/tests/test_app_ui_headless.py` (CDP driver `_cdp.py`) leaks 38 dirs (319 MB) per run** (measured with a private TMPDIR) → **D10 (MINOR, T5) OPEN.** Suggested fix: pass `env={**os.environ, "TMPDIR": self.tmp}` to the Chrome launch in `_cdp.py` (T6 did not edit it).

**3. The pkill window (10:28–10:38 IST).** T6's 3.12/3.10 runs at 8343656 overlapped it but finished with complete summaries (638/44/0). Nothing was killed, and no partial result was counted.

**4. Final concurrent-run stress (fresh clones):** two `app/tests` loops run **at the same time in the same fresh clone** (6 runs each, private venv), to reproduce UI's overlapping-run condition.
   | Code | Concurrent runs with a failure | Failures seen | 
   |---|---|---|
   | 1ddd6b9 (before 3cf0d1f) | **4 / 12** (loop a 1/6, loop b 3/6) | `test_replay_of_hardware_log_is_relabelled_and_recorded` ×3, `test_gps_in_recordings` ×1, all `HTTP Error 404` on the recording download, the same as UI's root cause |
   | 03fc993 (3cf0d1f + T6 D11) | **0 / 12** (86/86 each) | none |
   - `rec_race.py` (two apps start a recording at the same moment, 5 trials): **1ddd6b9: 5/5 collisions** (`rec-20261127-120500.csv` twice) → **03fc993: 0/5** (for example `rec-20261127-120507-061-p1447787-1.csv` vs `…-068-p1447788-1.csv`).
   - Raw: `raw/stress_03fc993/` (`stress_<sha>_<loop>_<n>.log`, `rec_race_<sha>.log`, `status`).
   - **T6 agrees with UI's root cause** (7/16 before and 0/30 after on UI's side; T6 got 4/12 and 0/12). **D12 is CLOSED (verified).** With 0 failures in 12 concurrent runs plus every full-suite run passing on three Python versions, T6 has no remaining evidence of a flaky required test.

**5. A second T6 test weakness found while explaining the burst: D13 (MINOR, T6, self-reported) CLOSED in b1a2153.**
- When `/` is full, Python's `tempfile` (and pytest's basetemp) **silently fall back to the current directory**. Evidence of this: at 11:46:02–11:47:13 IST someone ran pytest in the shared checkout and it created `/workspace/heading-monitor/pytest-of-box/` there (containing T6's `test_M3_*` tmp dirs, so it was a run of tests/). That untracked directory is still in the shared tree; it is not T6's and T6 did not delete it.
- T6's D8 helpers then copied the repo into a temp dir *inside the repo*, and `copytree` recursed (`…/t6_d8_x/repo/t6_d8_x/repo/…` → `shutil.Error`). T6's own serial run 19 (11:47:29) shows exactly this: 15 `shutil.Error`.
- **Reproduced deterministically** with `TMPDIR=<clone root>`: 03fc993 gives **15 passed / 15 errors**; with the fix (the copy now ignores T6's own temp dirs and `pytest-of-*`) it gives **30 passed** (`raw/stress_03fc993/d13_tmpdir_in_repo_{pre,post}.log`).
- **Conclusion on the burst:** UI's 23 failed + 34 errors came from **ENOSPC on `/`** (writes failing outright), **amplified by D13** (T6's repo-copy recursion once temp dirs fell back into the checkout). It was not a race between runs, not the shared `/tmp/hm-venv` as such (the venv was not modified; only the space it sits on was full), and not a product defect. T6's tests use unique `mkdtemp` dirs and ephemeral PID-checked ports, and they write nothing into the checkout.


---
*Sections 2a–3 below are the v3.x text, kept as history. Where they mention L-SER or say "A10c … Yes, by design", that is **superseded by D8 (§2e)**.*

## 2a. D6 re-test (v3 history) (fix 0ca6b0f, decisions eacf8a2 and c831574)
- **A8:** 20 replayed `hardware` lines → 20 records with source=replay, meta.original_source=hardware and transport=replay, none live. The app's own `badgeInfo` (run in Node) gives "REPLAY (recorded hardware)".
- **A8b (headless Chrome):** the badge reads `REPLAY (recorded hardware)`. The banner reads "[REPLAYED] Recorded hardware log played back from a file. This is recorded data, not a live sensor stream. Nothing here is hardware-verified."
- **A10a, can a replayed file defeat the relabel? No.**
  - `HARDWARE` and `Hardware` are rejected by the schema enum.
  - `hardware` + `meta.original_source: sim/replay` → relabelled, with original_source forced to `hardware`.
  - Top-level `transport: "serial"` and `live_hardware: true` in a file are ignored (transport comes from the app's own `--source`).
  - `replay` + `original_source: "HARDWARE"` or an object → plain REPLAY.
  - No record became hardware, live, HARDWARE or UNVERIFIED.
  - Accepted residual (PM c831574, app LIMITATIONS 4): a file can *claim* `original_source: "hardware"`. It is still labelled non-live.
- **A10b, ingest:** `hardware` POSTs, including injected `transport: "serial"` and `live_hardware: true`, keep source=hardware. Transport is ingest, the live flag is 0, the badge reads **UNVERIFIED SOURCE**, and the banner reads "[UNVERIFIED] … not a live serial source".
- **[SUPERSEDED by D8, §2e] A10c, can a live/serial path show HARDWARE when the data is not real hardware? Yes, by design (v3 view, withdrawn).** A virtual pty driven by the fake FC, with no device at all, is shown as HARDWARE with the banner "Live hardware samples (serial)". The serial transport cannot tell a pty from a flight controller. This is contract-conformant ("hardware only from a live port"), needs a deliberate set-up, and is already noted for the bridge test in firmware_bridge/README:81. It is recorded as **limitation L-SER**; T6 recommends a line in the app/README LIMITATIONS. Conversely, no non-serial path reaches HARDWARE (A2, A3b, A4, A8, A10a, A10b).
- **UI's claims checked:** "integration 27/27" → T6 got 30/30 (27 + 3 new A10 steps). "tests/ 111 passed" → confirmed. "repo 512/45 skipped" → T6 got 513/44: the bridge pty test runs with pyserial installed, and one more test than at their count. "52 app tests" → confirmed.
- **Pushed?** `git ls-remote origin main` = `0c25062` = local HEAD, so T6's commits bf7b406 and 3c99f1a are on the remote. Verified with a read-only query; T6 did not push.
- **D6 → CLOSED.**

## 2b. Is the UNVERIFIED SOURCE ingest badge consistent with R8 and the contracts?
- **Contracts: consistent.** `contracts/sample.schema.json` is unchanged. `source` keeps the enum sim/replay/hardware, and ingest keeps `sample.source="hardware"`, so the recorded data and the JSONL/CSV exports are unchanged. `meta` is a free object, so `original_source`/`replayed_from` are allowed; the bridge already used them. `transport`/`original_source`/`live_hardware` are app-internal record fields, not Sample fields.
- **R8: deviates from the literal wording, consistent with its intent.** R8 says the badge is "(SIMULATED / REPLAY / HARDWARE) driven only by the sample's `source` field". The app now shows five labels, keyed on `sample.source` and refined by `meta.original_source` and the transport. For ingest `hardware` the badge (UNVERIFIED SOURCE) does not equal the plain mapping of `sample.source` (HARDWARE). Every deviation is in the conservative direction: it never upgrades data to live or hardware. It is required by N4 and the README "show the active data source" rule, and the PM decided it explicitly (ARCHITECTURE eacf8a2, c831574).
- **Gap:** REQUIREMENTS.md R8 ("Changes require a CHANGELOG entry"), README rule 2 and CHANGELOG were not updated → **D7 (MINOR, PM)**. Suggested R8 wording: "badge derived from sample.source; HARDWARE only for a live serial transport; replayed hardware → 'REPLAY (recorded hardware)'; hardware via ingest → 'UNVERIFIED SOURCE'". Not blocking: this is a documentation consistency fix, and the behaviour is verified.
- T6 test U2/U3 (pure `badgeLabel` mapping) is unchanged and passes. The displayed badge is covered by A8b, A9a/b and A10b.

## 2c. v3.1 addendum (2026-11-27 ~01:40 IST): D7 re-check, push check, FINAL_REPORT check

Sections 0 and 1 above are the v3.0 text and are left unchanged, because `reports/FINAL_REPORT.md` §9 quotes §0 verbatim (checked: the quote is identical). Since 0c25062 the only commits are a88e8d1 (T6 reports) and 2564266 (PM: CHANGELOG.md, PROJECT_STATUS.md, README.md, REQUIREMENTS.md, TEAM_TRACKER.md, reports/FINAL_REPORT.md). No code, tests or contracts changed, so the suite result 513 passed / 44 skipped / 0 failed at 0c25062 stands. Only `tests/test_t6_claims.py` was re-run, on a clean export of 2564266: 4 passed (FINAL_REPORT.md is in scope, with 0 applied hardware tags and 0 navigation claims).

**D7: CLOSED.** The new REQUIREMENTS.md R8, README rule 2 and CHANGELOG entry say that the badge comes from `sample.source`, that HARDWARE is shown only for a live serial transport, that replayed hardware shows as 'REPLAY (recorded hardware)', that hardware via ingest shows as 'UNVERIFIED SOURCE', and that everything else shows as SIMULATED or REPLAY. This matches the `badgeInfo` behaviour T6 tested (A8, A8b, A10a and A10b): no path upgrades replayed or ingest data to live. It adds no position, navigation or hardware-performance claim. Two notes, not defects:
- 'REPLAY (recorded simulator)' and NO DATA are not named; both are covered by "otherwise SIMULATED or REPLAY".
- "Live serial transport" means the transport type. A virtual pty fed by the fake FC also counts (**L-SER**, LIMITATIONS item 6), and the requirement text does not repeat that caveat.

With D7 closed, the PM docs deliverable is **PASS**.

**Push:** `git ls-remote origin main` = 2564266, and a88e8d1 is its parent (`git merge-base --is-ancestor`). This was a read-only check.

**FINAL_REPORT.md (PM-owned, not edited by T6):** its T6 verdict, figures and evidence labels are accurate. Minor wording issues were reported to the PM separately. Overall verdict unchanged: **PASS (virtual scope only)**; completion APPROVED for that scope only; nothing is hardware-verified.

## 2. D3 re-test and regression check (PM request, f31784a / c942d6f)
- PM claim "499 passed, 45 skipped, 0 failed at c942d6f": **reproduced**. T6 got 501 passed / 44 skipped at c942d6f, which includes 2 extra T6 tests written during this re-test: 499 + 2. The 45th skip is `firmware_bridge/tests/test_bridge_modes.py` (pty serial), which skips when pyserial is absent (INSTALL.md:80). T6 has pyserial, and that test passes.
- E3b stress 20 × 60 s, stationary, 15 nT, 0.1 µT steps: **0/20** falsely stale (was 4/20). Single sessions 0/600.
- Frozen-sensor regression matrix (`reports/audit/raw/d3_regress.py`, output `raw/d3_regress_c942d6f.log`; also tests E3c–E3g):
  - mag-only frozen, **no gyro and no accel**: SENSOR_STALE after 0.5 s (with and without quant meta, and on-grid via inference) → **D1 not reopened**.
  - all channels frozen → SENSOR_STALE 0.5 s. Frozen off-grid mag + live accel → MAG_STALE 0.5 s.
  - frozen quantised mag + gyro 20°/s → MAG_STALE 0.2 s; + 10° tilt change with no gyro → 1.7 s.
  - **Not detected (limitation, not defect):** frozen quantised mag with live accel and (a) a stationary vehicle, (b) a gyro below the 1°/s deadband, or (c) **no gyro during a level yaw turn**. This is the consequence of PM decision (a), `quant_nogyro_time_rule=False`. It is documented in HEADING_MATH 14a and ARCHITECTURE 1befc7b. Mitigation: the MSP bridge always emits gyro_dps, so case (c) affects only gyro-less sources. T6 records it as **L-D3** (below). D1 stays closed because a frozen sensor with no accel or gyro is still flagged.

### 3a. The 44 skips
All 44 are `sim/tests/test_spec_cases.py` cases where T2's sensor spec has a quantity the simulator does not model. They are marked N/A by T3's spec_check (36 PASS / 44 N/A / 0 MISMATCH):
- TC03 circular statistics (4)
- TC05/06/14 first-order formulas (3)
- TC08 dipole/wire source models (4)
- TC09–TC12, TC17, TC18, TC20 navigation/geodesy/dead reckoning/grid convergence (29)
- TC13 WMM/analytic (3)
- TC19 generic 0.15 µT part (1)

None maps to R1–R8. The navigation ones are out of scope by the heading-only rule. Circular statistics, formulas and declination are tested in heading_core and sensor-spec (23 passed). The interference source model is [ASSUMED] k·I (a limitation, not a hidden check). **No skip hides a required check.**

## 3. Results per criterion (403976b, re-run at c942d6f / 471724e / dc3123a)
| ID | Result | Evidence [SIMULATED] |
|---|---|---|
| H1 level sweep 0..359 | PASS | max err ≤ 0.01° vs the T6 reference model (itself checked against a textbook formula to 1e-6°) |
| H2 cardinals / clockwise | PASS | N=0, E=90, S=180, W=270 |
| H3 output range | PASS | 10 000 random attitudes all in [0,360); edge cases 359.999 and 0.001 handled |
| H4 tilt ±30°, noise-free | PASS | ≤ 0.1° (inclination 20/40/60/70°, 24 yaws, 13×13 tilt grid) |
| H5 tilt, noisy | PASS | RMSE 0.628°, max 2.317° |
| H6 declination | PASS | d ∈ {-30,-1.5,0,0.5,15,180}; 359° + 2° → 1.0° |
| H7 degenerate geometry | PASS | no crash; each case returns either a NaN or error, or a flagged result |
| C1 hard iron | PASS | estimated (35.004, -21.998, 40.003) vs true (35, -22, 40) µT |
| C2 soft iron | PASS | relative std of |B| 0.31 %, direction error 0.251° rms |
| C3 calibrated heading | PASS | 0.354° RMSE calibrated vs 82.4° uncalibrated |
| C4 fit robustness | PASS | <10 points or yaw-only data → ValueError; NaN rows dropped and the fit is still good |
| C5 serialisation | PASS | round-trip diff ≤ 1e-9 |
| E1 NaN/inf input | PASS | flagged; filter recovers within 1° |
| E2 field out of range | PASS | FIELD_MAGNITUDE_OUT_OF_RANGE raised at ×0.3, ×2 and ×20 |
| E3 frozen sensor (identical samples, 3 s) | PASS | SENSOR_STALE, quality 0.05 → **D1 closed** |
| E3b stress (20 × 60 s) | 0aaa066 and 1befc7b: **FAIL** 4/20; **c942d6f (f31784a): PASS 0/20** | Before f31784a: (seed 5, 48 flagged samples), (7, 591), (11, 129), (14, 345); the cause was the no-gyro 5 s time rule (T6 showed 4/20 with `quant_nogyro_time_rule=True`, 0/20 with False at 1befc7b). At c942d6f, 0/20 sessions are flagged. meta.mag_quant_uT = 0.1, noise 15 nT [DATASHEET]. |
| E3c frozen mag during a 20°/s turn (gyro present, quantised) | PASS | MAG_STALE after 0.2 s, quality 0.024 |
| E3d stationary mag-only freeze, quantised, live accel, no gyro | OBSERVATION (documented limitation 14a) | 0/1200 samples flagged over 60 s: undetectable by design |
| E3e mag-only frozen (no accel, no gyro), with/without quant meta | PASS | SENSOR_STALE after 0.5 s, quality 0.035: **D1 not reopened** |
| E3f frozen off-grid mag, live accel, no gyro | PASS | MAG_STALE after 0.5 s |
| E3g frozen quantised mag, +10° pitch over 5 s, no gyro | PASS | MAG_STALE after 1.7 s |
| D3 matrix F10: frozen quantised mag during a level 20°/s yaw turn, **no gyro** | OBSERVATION → limitation L-D3 | not flagged (quality 0.99). Documented in HEADING_MATH 14a. The MSP bridge always supplies gyro_dps (MSP_RAW_IMU), so this affects only gyro-less sources (e.g. DroneCAN-only or hand-made logs). |
| E3b single 30 s session | 403976b: **FAIL**; 0aaa066 and c942d6f: PASS (0/600 flagged, min quality 0.983) | At 403976b: At σ = 15 nT [DATASHEET] with 0.1 µT steps: 55/600 samples flagged MAG_STALE (first at 4.6 s), min quality 0.296. Same result with and without `meta.mag_quant_uT`. At σ = 0.05 µT [ASSUMED]: 0/600. Frozen case with meta still flagged (PASS). → **D3** |
| E4 time anomalies | PASS | no crash; back within 1° |
| E5 interference step 25 µT | PASS | flagged at the onset sample; 13.1° error during the disturbance (reported, not gated) |
| E6 missing accel / malformed | PASS | NO_ACCEL plus level assumption; malformed input rejected |
| F1 wrap-invariant smoothing | PASS | behaviour identical across 0/360 and 180 (diff 1.4e-13); 4.5° lag on a 25°/s ramp (tuning property, reported) |
| F2 step 90° | PASS | within 1° after 42 samples (0.84 s at 50 Hz) |
| K1 schema + source passthrough | PASS | |
| R1 repeatability, identical input ×5 | PASS | spread 0.0° |
| A1/R2 end-to-end, 5 seeds × 20 s | PASS | RMSE mean±std: static 0.371±0.254, yaw_spin 0.527±0.241, tilted_spin 0.549±0.226, hard_iron 0.528±0.243, soft_iron 0.527±0.242 (calibrated from a separate calibration_dance), high_noise 0.846±0.229 |
| A1 motor_interference | PASS (flag) | warnings raised; RMSE 16.3° during interference (no target) |
| S1-S4 simulator | PASS | see T3 row |
| M1 decode exact (v1, v2) | PASS | RAW_IMU and ATTITUDE payloads decoded exactly; bridge encoder byte-identical to the T6 encoder (CRC-8/DVB-S2 check value 0xBC verified) |
| M2 robustness | PASS | byte-by-byte and random chunking OK; bad XOR and bad CRC rejected; every payload single-bit flip rejected; truncated → resync; short length mismatch rejected; error frames reported. Fuzz over 2000 streams: 98.8 % of valid frames recovered. 4 corrupted v2 frames passed the 8-bit CRC (size-byte collisions, inherent 1/256); **0 leaked** into samples or attitude (payload-length check). |
| M2 long-length resync | OBSERVATION | A corrupted length byte claiming 200 bytes holds back the 3 following valid frames until 156 more bytes arrive. Live polling: a few cycles of delay. End of a binary replay: those frames are lost. Not gated. |
| M3 source labelling + schema | PASS | `--fake-fc` → 50/50 samples with source=sim, schema-valid. `--replay` of hardware-labelled JSONL → source=replay with `original_source` kept. Binary replay with garbage → 4/4 valid. Malformed Sample lines: at 997d00f, 2 of 3 emitted lines were schema-invalid (**D4**); at 403976b they are skipped (**D4 closed**). |
| M4 INAV scaling | PASS | 512 LSB/g, mGauss → 0.1 µT, FLU→FRD (x,-y,-z): level → accel (0,0,-1) g [SOURCE-CODE, not hardware-checked] |
| U1 app starts (own instance) | PASS | Ephemeral port; `ss -ltnp` listener PID == PID launched by T6 (e.g. pid 82508, port 60061); 29 sim records in 1.5 s; port released after shutdown. **The earlier Phase-1 U1 PASS is withdrawn:** it may have hit the UI developer's :8080 instance. |
| U2 source badge | PASS | Records cycling through sim/replay/hardware: badge (the UI's own `headingmath.js` in Node) maps exactly in 10/10. Non-contract values ("SIMULATED", "", null, "sensor", "HARDWARE") → no badge (NO DATA); nothing is inferred. |
| U3 displayed value | PASS | App `heading_deg` vs a fresh heading_core fed the same samples: max diff 0.0°. Steady display: 359.96 → "0.0", 359.94 → "359.9", 0.04 → "0.0", 0.06 → "0.1", 180 → "180.0", 89.95 → "90.0"; "360.0" never shown. |
| U4 errors / quality / staleness | PASS | 3× field → FIELD_MAGNITUDE_OUT_OF_RANGE, quality 0.003. 2-element mag → HTTP 422, counted invalid. 2.2 s silence with `--stale 1.5` → sensor_status STALE. |
| U5 CSV export | PASS | export equals history to ≤ 1e-6 |
| Q1a hardware tag | PASS | at dc3123a: 0 applied tags; 30 mentions excluded and each confirmed by hand (audit/claims_audit.md) |
| Q1b positioning / navigation | PASS | at dc3123a: 0 rejected from 89 inventory lines (audit/claims_audit.md) |
| Q3 LIMITATIONS present | PASS | docs/hardware, docs/math, sim, docs/firmware, firmware_bridge, app |

### Accuracy-figure inputs, kept separate (PM request)
**[DATASHEET]:** RM3100 noise 15 nT rms and gain 75 LSB/µT at CC200; range ±800 µT. Source: PNI RM3100 User Manual Table 3-1, re-read by T6 in `/workspace/hwsrc/RM3100-User-Manual.pdf`.
**[SOURCE-CODE]:** MSP mag quantisation 0.1 µT (int16 mGauss) and accel 1/512 g, per `firmware_bridge/scaling.py` and FC_SETUP.md §6 (INAV source).
**[ASSUMED]** (no external source; sim constants or T6 choices):
- accel noise 0.003 g and accel bias σ 0.01 g
- gyro noise 0.05 °/s and gyro bias σ 0.3 °/s
- FC attitude noise 0.3°
- high_noise scenario: env noise 1.0 µT and IMU ×5
- hard-iron (25,-15,10) µT and the soft-iron matrices
- motor k (0.8,-0.4,1.5) µT/A
- Earth field 50 µT, inclination 60°, declination 0
- T6 tests: 0.15 µT / 0.005 g noise in H5 and C1-C3, 0.002 g accel and 0.05 µT environment noise in E3b

The accel bias (0.01 g, about 0.57° of tilt) is the main contributor to the A1 RMSE figures.
| INT integrated end-to-end (audit/integration_results.md) | **30/30 PASS at f058c9a** (25/27 at 471724e) | A1 8/8 scenarios sim→heading_core→app; A1b motor interference warned (76/76 bad samples flagged); A2 7/7 example logs; A3a/b fake-FC `--capture` → `--replay` → app (REPLAY badge); A4 fake-FC → bridge → app: SIMULATED, never HARDWARE; A5 wizard 0.72°; A6 frozen/stale; A7/A7b missing port → FAULT, no data; A9a/b headless Chrome: badge, heading, warnings, GPS 'Unknown'. A8/A8b now pass (D6 closed); A10a–c D6 edge cases |
| A8/A8b badge for replayed hardware-labelled log | 471724e: FAIL → D6; **f058c9a: PASS** | 'REPLAY (recorded hardware)', banner says not live |


## 4. Defects
| ID | Sev | Owner | Status | Summary |
|---|---|---|---|---|
| D1 | MAJOR | T2 | **CLOSED** | Frozen sensor not flagged; fixed 758faeb; still flagged after the D3 change (E3, E3e, A6). |
| D2 | MINOR | PM | **CLOSED** | Blanket commit; verified fixed. |
| D3 | MAJOR | T2 + PM rule | **CLOSED** (f31784a, re-tested at c942d6f) | False MAG_STALE on a stationary quantised sensor; E3b stress 0/20. Residual stationary/no-gyro blind spot → limitation L-D3 (HEADING_MATH 14a). |
| D4 | MAJOR | T4 | **CLOSED** | Bridge replay forwarded schema-invalid lines; fixed 403976b. |
| D5 | MINOR | T6 | **CLOSED** (self-reported) | Accidental HEAD detach; repaired (84fc231). |
| D6 | CRITICAL | T5 + PM | **CLOSED** (fix 0ca6b0f; decisions eacf8a2, c831574; T6 re-test at f058c9a/0c25062) | A replayed hardware-labelled log was shown as HARDWARE + "Live hardware samples." (found at 471724e). Now 'REPLAY (recorded hardware)' with a not-live banner; the relabel cannot be bypassed (A10a). |
| D7 | MINOR | PM | **CLOSED** (re-checked at 2564266, §2c) | REQUIREMENTS R8 / README rule 2 / CHANGELOG not updated for the accepted badge rules (5 labels; ingest hardware → UNVERIFIED SOURCE; replayed hardware → REPLAY (recorded hardware)). See §2b. |
| D8 | CRITICAL | T4 + T5 (+PM decision 1bef73e) | **CLOSED** (virtual scope; T6 reruns at 1ddd6b9 = 479a72c + T6 tests and at 03fc993 = 3cf0d1f + T6, §2e) | A serial connection was treated as proof of hardware: a fake FC on a virtual pty showed HARDWARE (previously accepted as L-SER, now withdrawn). Fixed in e37430b + F12 edc3ee0 (bridge) and e538cea + 6c1e5b5 + 479a72c (app, including the decided label). T6 found the F12 UID-truncation bug. Residual limitation F11. |
| D9 | MINOR | T5 | **CLOSED** (479a72c, verified at 1ddd6b9 and 03fc993) | UI's pty e2e test, which expects the allowlisted badge for an emulator, was relabelled `test_e2e_virtual_pty_allowlist_mechanism_and_F11_spoof_limitation_not_hardware_validation` (F11 limitation demonstration, not hardware validation). |
| D10 | MINOR | T5 | **OPEN** (test environment only) | `app/tests/test_app_ui_headless.py` (CDP driver `_cdp.py`) leaves about 38 headless-Chrome temp dirs (about 319 MB) in $TMPDIR per run (measured with a private TMPDIR). On the shared box this helped fill `/` at about 11:45 IST. Suggested fix: launch Chrome with `env={**os.environ, 'TMPDIR': <private tmp>}` and remove it afterwards. Product unaffected. |
| D11 | MINOR | T6 | **CLOSED** (self-reported; 03fc993) | T6's headless-Chrome helpers (test_t6_d8_provenance `_dom`, integration_run `dom`) leaked about 36 MB per launch into /tmp; T6's flake loop added about 20 GB. Each launch now uses a private TMPDIR + profile that is removed afterwards; 0 leftovers verified (integration at 03fc993: TMPDIR empty after the run). |
| D12 | MAJOR | T5 | **CLOSED** (fix 3cf0d1f; verified by T6 at 03fc993, §2i) | Recording file names had 1 s resolution and were opened with 'w': two app instances in one checkout that start recording in the same second write the same file (silent data loss) → app/tests flake (HTTP 404). T6 repro: rec_race 5/5 collisions and 4/12 concurrent app/tests runs failing at 1ddd6b9 → 0/5 and 0/12 at 03fc993. |
| D13 | MINOR | T6 | **CLOSED** (self-reported; b1a2153) | When `/` is full, tempfile/pytest fall back to the CWD; T6's repo-copy helpers then copied the repo into itself (recursive `shutil.Error`), which amplified UI's 11:45–11:48 IST burst. The copy now ignores T6's own temp dirs; repro with TMPDIR=<repo>: 15 passed/15 errors → 30 passed. |
## 5. Claims audit → `reports/audit/claims_audit.md`
At 0c25062: 0 applied hardware tags (44 mentions, new ones confirmed by hand; 30 at dc3123a); 0 hardware-performance claims; 0 positioning, distance or GPS-independent navigation claims (89 inventory lines adjudicated). The GPS indicator is availability-only, with coordinates stripped. Runtime claim issue: D6.

## 6. TEAM_RULES compliance → `reports/audit/team_rules_compliance.md`
13/13 PASS as far as verifiable. Spend: none found (requirements are OSS; no keys, purchases or paid APIs; all contribution reports state none). Disclosed rule-1 incidents: D5 and 9b808b5 (T6), d211e80 (sim); all repaired.

## 7. Traceability → `reports/audit/traceability.md`
v4/v5 (1ddd6b9; re-confirmed at 03fc993 and b1a2153): Delivered 13 (R1–R5, R7, R8, N1–N6; R8 and N4 for the virtual scope, with limitation F11); Partial 1 (R6: live MSP to a real FC not runnable without hardware); Not delivered 0. Codex's 10/3/1 is explained in §2f.

## LIMITATIONS (T6, unresolved)
1. All results are [SIMULATED] or [REPLAYED] against an idealised uniform-field model. **None transfer to the physical RM3100 or Matek FC.** No hardware log exists, so [HARDWARE-VERIFIED] sign-off is impossible (HARDWARE_VALIDATION_CHECKLIST not run).
2. Exact Matek FC model and firmware are unknown (T1 L1). INAV axis convention, mag scaling and pitch sign are [SOURCE-CODE] only.
3. MSP tests use hand-built frames and the fake FC; real USB timing, rate limits and partial reads are untested. Live `serial:` was only tested against a missing port.
4. **L-D3:** in quantised mode a frozen mag is undetectable on a stationary vehicle, below 1°/s, or during a level yaw turn when no gyro is supplied (PM decision (a)). The opt-in `quant_nogyro_time_rule=True` catches long freezes but brings back about 4/20 false alarms in T6's stress test.
5. App ingest trusts the client-declared `source` (documented).
6. ~~L-SER~~ **WITHDRAWN** (v4): it was defect D8, now fixed (§2e).
   **F11 (unresolved):** the device identity (variant, board, UID) is self-reported over MSP and spoofable. A simulator reporting an allowlisted UID passes the allowlist (A10f and the T6 spoof tests). An allowlist match is an administrative trust decision, not hardware authentication, and it does not validate the measurements. The identity is read once at connect, so a device swap mid-session is not re-checked. The allowlist ships empty.
   The app also trusts `meta.original_source` written in a replay file (accepted, c831574), but only ever as a non-live label. pyserial is an optional dependency; without it, every serial D8 integration step reports FAIL (NOT RUN).
7. UI checks use DOM text from headless Chrome (badge, heading, warnings, GPS, banner); pixels and human readability were not assessed. Demo video and screenshots were not inspected frame by frame.
8. The default `--sim-duration 86400` stretches the motor_interference profile over 24 h, so in a short live demo interference does not appear unless `--sim-duration` is set (A1 vs A1b).
9. F1 lag (4.5° on a 25°/s ramp) and E5 interference error (13°) are reported, not gated. T6 numeric targets have not been reviewed by the owner. Python 3.13.5, 3.12.16 and 3.10.22 were all tested (v4). Wizard RMSE varies run to run (0.68–0.72°) because collection is real-time.
