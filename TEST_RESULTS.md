# Test Results

Only tests that were actually executed appear here, with command, date, environment and raw outcome.
Every result carries an evidence label. Maintained by the Testing & Technical Auditor (summary). Detail is in reports/verification_report.md and reports/audit/.

Environment: Linux box. Private venvs (under /workspace/audit, never /tmp/hm-venv) built from `requirements.txt` plus pyserial 3.5: Python 3.13.5 (numpy 2.5.5), 3.12.16 (numpy 2.5.5) and 3.10.22 (numpy 2.2.6), all with pytest 9.2.0 and jsonschema 4.26.0. Google Chrome 156.0.8078.47 headless with a fresh temporary profile and private per-launch TMPDIR; Node.
Code: fresh `git clone`s or clean `git archive <sha>` exports (never the shared working tree), plus T6 `tests/` as committed with this file. Latest run by T6 on 2026-11-27, 11:54–12:17 IST (v5 final, fresh clones of 03fc993 and b1a2153).

## v5 FINAL run (flake fix 3cf0d1f): 2026-11-27, 11:54–12:17 IST
Code: **fresh `git clone` (porcelain-clean) at 03fc993** = UI's 3cf0d1f (flake fix, on 479a72c) + T6's D11 helper fix (tests only), and confirmation at **b1a2153** (+ PM docs-only 1f3883e/83f38b7 and T6's D13 helper fix, tests only; no product-code change). No later UI commit was pending (origin checked). Private venvs; private HOME/TMPDIR under /workspace/audit; every app on an ephemeral PID-verified port, never 8080.

| Date (IST) | Test / suite | Command | Commit | Result | Evidence |
|---|---|---|---|---|---|
| 2026-11-27 11:55 | **Whole repo, Python 3.13.5** | `python -m pytest -q -rs -p no:cacheprovider --junitxml` (clone root) | 03fc993 | **652 passed, 44 skipped, 0 failed** (app 86 incl. UI's new regression test) | [SIMULATED] raw/pytest_rs_03fc993.log, raw/junit_03fc993.xml |
| 2026-11-27 12:01 | Whole repo, Python 3.12.16 | same | 03fc993 | **652 passed, 44 skipped, 0 failed** | raw/pytest_py3.12_03fc993.log |
| 2026-11-27 12:01 | Whole repo, Python 3.10.22 (numpy 2.2.6) | same | 03fc993 | **652 passed, 44 skipped, 0 failed** | raw/pytest_py3.10_03fc993.log |
| 2026-11-27 11:56 | **Integration A1–A10z** (headless Chrome, temp profile, private TMPDIR, empty HOME) | `HOME=$(mktemp -d) TMPDIR=$(mktemp -d) python reports/audit/integration_run.py <clone> <out>` | 03fc993 | **37/37 PASS**; 0 Chrome temp leftovers; tilted-spin 0.41°, wizard 0.72° | [SIMULATED]/[REPLAYED] raw/integration_results.json |
| 2026-11-27 11:57 | Integration **without pyserial** | same + `PYTHONPATH=<stub>` | 03fc993 | 31/37: **6 serial D8 steps FAIL 'NOT RUN'** (A10c–A10g, A10i), never a pass | raw/integration_results_noserial.json |
| 2026-11-27 12:02–12:05 | **Concurrent stress, before the fix**: 2 app/tests loops in the same fresh clone, 6 runs each | `pytest app/tests` ×2 in parallel | 1ddd6b9 | **4/12 runs failed** (HTTP 404 on recordings: test_replay_of_hardware_log_is_relabelled_and_recorded ×3, test_gps_in_recordings ×1) | raw/stress_03fc993/ |
| 2026-11-27 12:05–12:08 | **Concurrent stress, after the fix** | same | 03fc993 | **0/12 runs failed** (86/86 each) | raw/stress_03fc993/ |
| 2026-11-27 12:05 | rec_race (2 apps start recording simultaneously, 5 trials) | `python rec_race.py 5` | 1ddd6b9 → 03fc993 | **5/5 name collisions → 0/5** (D12 closed) | raw/stress_03fc993/rec_race_*.log |
| 2026-11-27 12:10 | D13 repro: T6 D8 app/DOM tests with TMPDIR inside the checkout | `TMPDIR=<clone> pytest tests/test_t6_d8_provenance.py` | 03fc993 → fix | 15 passed/15 errors → **30 passed** | raw/stress_03fc993/d13_*.log |
| 2026-11-27 12:14 | **Confirmation: whole repo, Python 3.13.5** | same | b1a2153 | **652 passed, 44 skipped, 0 failed** | raw/pytest_rs_b1a2153.log |
| 2026-11-27 12:16 | Confirmation: integration with / without pyserial | same | b1a2153 | **37/37** / 31/37 (6 NOT RUN = FAIL) | raw/integration_*_b1a2153 |
| 2026-11-27 | skipped_tests.md regenerated | `gen_skipped_tests.py` | 03fc993 | 44 skips, 0 uncategorised, 0 hiding a required check | reports/audit/skipped_tests.md |

## v4 run (D8 re-verification): 2026-11-27, 11:13–11:22 IST, plus flake hunt 11:22–11:51 IST
Code: clean `git archive 1ddd6b9`. That is UI's final 479a72c (label + D9) plus T6's test/harness commit, with no product-code difference. Every app instance runs on an ephemeral port, PID-verified, never the 8080 instance (app/tests assert `port != 8080`). All work dirs are unique under /workspace/audit (no shared /tmp paths).

| Date (IST) | Test / suite | Command | Commit | Result | Evidence |
|---|---|---|---|---|---|
| 2026-11-27 11:16 | **Whole repo, Python 3.13.5** | `python -m pytest -q -rs --junitxml` (repo root) | 1ddd6b9 | **651 passed, 44 skipped, 0 failed** (heading_core 76, docs 27, sim 152+44 N/A, firmware_bridge 138, app 85, T6 173) | [SIMULATED] raw/pytest_rs_1ddd6b9.log, raw/junit_1ddd6b9.xml |
| 2026-11-27 11:22 | Whole repo, Python 3.12.16 (uv) | same | 1ddd6b9 | **651 passed, 44 skipped, 0 failed** | raw/pytest_py3.12_1ddd6b9.log |
| 2026-11-27 11:22 | Whole repo, Python 3.10.22 (uv, numpy 2.2.6) | same | 1ddd6b9 | **651 passed, 44 skipped, 0 failed** | raw/pytest_py3.10_1ddd6b9.log |
| 2026-11-27 11:17 | **Integration A1–A10z, headless Chrome, fresh temp profile, empty temp HOME** | `HOME=$(mktemp -d) python reports/audit/integration_run.py <export> <out>` | 1ddd6b9 | **37/37 PASS**: D8 A10c–A10i + A10z; A10f shows exactly 'ALLOWLISTED DEVICE (identity not authenticated)' and the decided banner (F11 limitation demo, NOT hardware validation) | [SIMULATED]/[REPLAYED] raw/integration_results.json |
| 2026-11-27 11:18 | Integration **without pyserial** (`import serial` stubbed to fail) | same + `PYTHONPATH=<stub>` | 1ddd6b9 | 31/37: **all 6 serial D8 steps reported FAIL 'NOT RUN'** (never a pass) | raw/integration_results_noserial.json |
| 2026-11-27 | T6 D8 suites | inside the whole-repo run | 1ddd6b9 | test_t6_d8_bridge 32/32 (F12 `[extended]` passes; F11 spoof MKH7/MKF4 demonstrated); test_t6_d8_provenance 30/30 (exact label + banner) | [SIMULATED] |
| 2026-11-27 | skipped_tests.md regenerated | `gen_skipped_tests.py` from junit + `-rs` log | 1ddd6b9 | 44 skips, 0 uncategorised, 0 hiding a required check | raw/ |
| 2026-11-27 11:22–11:51 | Flake hunt on app/tests and the serial D8 set, isolated exports | serial loops + shuffled `pytest.main(nodes)` | 1ddd6b9 | app/tests default order **13/13** passed (85/85); shuffled 1/1; serial D8 set (139 tests) **15/15** clean; runs 16–19 failed **only** from ENOSPC on `/` (16–18: `No space left on device`; 19: temp dir fell back into the checkout → T6 copytree recursion, D13). No product flake when isolated; the mechanism needs overlapping runs in one checkout (see v5) | [SIMULATED] verification_report §2i |
| 2026-11-27 10:39 | MC accuracy reproduction (Codex cross-check) | `python -m heading_core.experiments.accuracy_mc --trials 200 --seed 2026` | 8343656 | ellipsoid fit **0.301° RMS** (P95 0.605°, max 1.751°); output identical to docs/math/accuracy_results.md | [SIMULATED] raw/accuracy_mc_8343656.md |
| 2026-11-27 ~10:15 | Secrets scan | gitleaks 8.28.0 (full history + tree) + rg | 29ccbda | 0 findings; personal data LOW/INFO only (verification_report §2g) | raw/gitleaks_*_redacted.json |

Earlier v4 runs:
| Date (IST) | Test / suite | Commit | Result |
|---|---|---|---|
| 2026-11-27 10:57 | Whole repo on 3.13.5, 3.12.16 and 3.10.22 (T6 label tests overlaid) | 25e308d (before the UI label) | 649 passed, 44 skipped, **2 failed**: the 2 exact-label assertions; expected, because the label had not landed (raw/pytest_rs_25e308d.log) |
| 2026-11-27 10:58 | Integration (new harness) | 25e308d | 35/37: A10f/A10z FAIL (bare HARDWARE still shown); no-pyserial 31/37 |
| 2026-11-27 10:30 | Whole repo, 3.13.5 | 8343656 | 638 passed, 44 skipped, 0 failed (raw/pytest_rs_8343656.log) |
| 2026-11-27 10:38 | Whole repo, 3.12.16 / 3.10.22 | 8343656 | 638/44/0 each. Ran during UI's `pkill -f pytest` window (10:28–10:38) but **completed with full summaries**, so nothing was killed (raw/pytest_py3.1x_8343656.log) |
| 2026-11-27 10:31 | Integration (previous harness) | 8343656 | 35/35 |
| 2026-11-27 ~10:05 | Whole repo, 3.13.5 / 3.12.16 / 3.10.22 | af640ae | 545/44/0 each |
| 2026-11-27 ~09:50 | T6 D8 suites before the fixes | 1bef73e; af640ae | app/DOM 24 failed / 5 passed at 1bef73e (pre-fix); bridge 30 passed / 1 failed at af640ae (`[extended]` → F12) |

## v3.1 addendum (D7 re-check): 2026-11-27 ~01:40 IST
| Date (IST) | Test / suite | Command | Commit | Result | Evidence |
|---|---|---|---|---|---|
| 2026-11-27 01:38 | Claims audit (incl. new reports/FINAL_REPORT.md) | `python -m pytest tests/test_t6_claims.py -q -s` on clean export | 2564266 | 4 passed; 0 applied hardware tags, 0 nav claims | [SOURCE-CODE] |

Since 0c25062 only docs changed (a88e8d1, 2564266), so the full suites were not re-run; 513 passed / 44 skipped / 0 failed at 0c25062 stands.

## Latest run (final verification v3.0, D6 re-test) — 2026-11-27 ~01:15–01:30 IST
| Date (IST) | Test / suite | Command | Commit | Result | Evidence |
|---|---|---|---|---|---|
| 2026-11-27 01:25 | **Whole repo** (all owner suites + T6) | `python -m pytest -q -rs` (repo root) | 0c25062 (HEAD) | **513 passed, 44 skipped, 0 failed** | [SIMULATED] |
| 2026-11-27 01:22 | heading_core / sensor-spec / sim / firmware_bridge / app | `python -m pytest <dir> -q` | 0c25062 | 76 / 23 / 152 (+44 N/A) / 95 / 52 passed | [SIMULATED] |
| 2026-11-27 01:22 | T6 independent suite (incl. claims) | `python -m pytest tests -q` | 0c25062 | 111 passed | [SIMULATED] |
| 2026-11-27 01:17 | **Integrated end-to-end A1–A10** (incl. D6 A8/A8b, edge cases A10a–c, headless Chrome) | `python reports/audit/integration_run.py <export> <out>` | f058c9a (= HEAD minus PROJECT_STATUS.md) | **30/30 PASS** → D6 CLOSED | [SIMULATED]/[REPLAYED] |
| 2026-11-27 01:25 | Claims audit | `pytest tests/test_t6_claims.py -s` | 0c25062 | 4 passed; 0 applied hardware tags (44 mentions), 0 nav claims | n/a |
| 2026-11-27 01:20 | Remote check (read-only) | `git ls-remote origin main` | - | remote main = 0c25062 = local HEAD (T6 commits bf7b406, 3c99f1a are on the remote) | n/a |

## Previous run (final verification v2.0)
| Date (IST) | Test / suite | Command | Commit | Result | Evidence |
|---|---|---|---|---|---|
| 2026-11-27 01:05 | **Whole repo** (all owner suites + T6) | `python -m pytest -q -rs` (repo root) | dc3123a | **506 passed, 44 skipped, 0 failed** | [SIMULATED] |
| 2026-11-27 00:50 | Whole repo (check of PM claim 499/45) | `python -m pytest -q` | c942d6f | 501 passed, 44 skipped (= PM's 499 + 2 new T6 tests; PM's 45th skip = pty serial test without pyserial) | [SIMULATED] |
| 2026-11-27 00:55 | heading_core owner suite | `python -m pytest heading_core/tests -q` | 471724e | 76 passed | [SIMULATED] |
| 2026-11-27 00:55 | sensor-spec | `python -m pytest docs/math/sensor-spec -q` | 471724e | 23 passed | [SIMULATED] |
| 2026-11-27 00:55 | sim owner suite | `python -m pytest sim/tests -q` | 471724e | 152 passed, 44 skipped (spec-check N/A) | [SIMULATED] |
| 2026-11-27 00:55 | firmware_bridge owner suite | `python -m pytest firmware_bridge/tests -q` | 471724e | 95 passed | [SIMULATED] |
| 2026-11-27 00:55 | app owner suite | `python -m pytest app/tests -q` | 471724e | 45 passed | [SIMULATED] |
| 2026-11-27 01:05 | T6 independent suite | `python -m pytest tests -q -s` | dc3123a | 111 passed | [SIMULATED] |
| 2026-11-27 00:50 | D3 re-test: E3b stress 20×60 s | `pytest tests/test_t6_stale_quant.py -s` | c942d6f | 0/20 falsely stale (was 4/20 at 1befc7b) → D3 closed | [SIMULATED] |
| 2026-11-27 00:50 | Frozen-sensor regression matrix F1–F10 | `python reports/audit/raw/d3_regress.py` | c942d6f | F1–F5, F7, F8 flagged (0.2–1.7 s); F6, F9, F10 not flagged (documented limitation 14a) | [SIMULATED] |
| 2026-11-27 00:55 | **Integrated end-to-end** A1–A9 | `python reports/audit/integration_run.py <export> <out>` | 471724e | **25/27 PASS; FAIL A8, A8b → D6 (CRITICAL)** | [SIMULATED]/[REPLAYED] |
| 2026-11-27 01:05 | Claims audit | `pytest tests/test_t6_claims.py -s` | dc3123a | 4 passed; 0 applied hardware tags, 30 mentions, 0 nav claims | n/a |

## Earlier runs (history)
| Date (IST) | Test / suite | Command | Commit | Result | Evidence | Run by |
|---|---|---|---|---|---|---|
| 2026-11-27 | T6 independent suite (all) | `python -m pytest tests -q -s` | 403976b | **102 passed, 2 failed** (both are E3b → D3) | [SIMULATED] | T6 |
| 2026-11-27 | heading_core owner suite | `python -m pytest heading_core/tests` | 403976b | 59 passed | [SIMULATED] | T6 |
| 2026-11-27 | math sensor-spec | `python -m pytest docs/math/sensor-spec` | 403976b | 23 passed | [SIMULATED] | T6 |
| 2026-11-27 | sim owner suite | `python -m pytest sim/tests` | 403976b | 80 passed | [SIMULATED] | T6 |
| 2026-11-27 | firmware_bridge owner suite | `python -m pytest firmware_bridge/tests` | 403976b | 64 passed, 1 skipped (no pyserial); 65 passed with pyserial | [SIMULATED] hand-built frames | T6 |
| 2026-11-27 | app owner suite | `python -m pytest app/tests` | 403976b | 40 passed | [SIMULATED] | T6 |
| 2026-11-27 | T6 independent suite (all, incl. E3b stress) | `python -m pytest tests -q -s` | 0aaa066 | **104 passed, 1 failed** (E3b stress, D3) | [SIMULATED] | T6 |
| 2026-11-27 | heading_core / sensor-spec / sim / firmware_bridge / app owner suites | `python -m pytest <suite>` | 0aaa066 | 67 / 23 / 80 / 65 / 40 passed | [SIMULATED] | T6 |
| 2026-11-27 | firmware_bridge owner suite | same | 997d00f | 41 passed, 1 skipped | [SIMULATED] | T6 |
| 2026-11-27 | T6 MSP replay of malformed Sample JSONL | `tests/test_t6_msp.py::test_M3_replay_malformed_sample_lines` | 997d00f → 403976b | FAIL (2/3 invalid emitted) → PASS | [SIMULATED] | T6 |

Key numbers [SIMULATED]:
- **Heading:** level error ≤ 0.01°; tilt ±30° noise-free ≤ 0.1°; noisy tilt RMSE 0.628° (max 2.317°).
- **Calibration:** hard iron recovered to ≤ 0.004 µT; calibrated heading 0.354° vs 82.4° uncalibrated.
- **End-to-end RMSE** (5 seeds, mean±std): static 0.371±0.254°, yaw_spin 0.527±0.241°, tilted_spin 0.549±0.226°, hard_iron 0.528±0.243°, soft_iron 0.527±0.242°, high_noise 0.846±0.229°. motor_interference 16.3° (flagged).
- **Repeatability:** spread 0.0° on identical input; sim output byte-identical per seed.
- **MSP fuzz** (2000 streams): 98.8 % of valid frames recovered; 0 corrupted frames leaked into samples.
- **Dashboard:** display vs core diff 0.0°; badge matched sample.source 10/10; 359.96 → "0.0".
- **E3b (D3):** at 15 nT [DATASHEET] noise with 0.1 µT quantisation. At 403976b: 55/600 samples falsely MAG_STALE. At 0aaa066: the single session is clean, but 4/20 sixty-second sessions are falsely stale.

Inputs: [DATASHEET] RM3100 noise 15 nT and gain 75 LSB/µT (PNI UM Table 3-1). All IMU, interference and field parameters are [ASSUMED]; see verification_report.md §3.
