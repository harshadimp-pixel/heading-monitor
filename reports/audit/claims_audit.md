# Claims audit, whole repo (T6)

**v4 (2026-11-27, D8):** §4 runtime claims are updated for D8, the label decision and F11. The text scan (`tests/test_t6_claims.py`) is part of the full suite at the final HEAD (TEST_RESULTS.md); v5 re-run at 03fc993 and b1a2153: passed. The flake fix 3cf0d1f adds no positioning, distance or navigation claim.

Scope: every tracked text file at HEAD **`dc3123a`** (clean `git archive` export), including the contribution reports, `reports/demo/` and INSTALL.md added in the last hour.
Tool: `tests/test_t6_claims.py` (T6), run as `python -m pytest tests/test_t6_claims.py -s` → **4 passed** (Q1a, Q1a rule self-check, Q1b, Q3). Raw: `/workspace/audit/claims_dc3123a.log` (box). T6 also read the new documents by hand.

**Re-run after the D6 fix (2026-11-27 ~01:25 IST, HEAD `0c25062`):** `tests/test_t6_claims.py` → 4 passed (Q1a, Q1a self-check, Q1b, Q3). There are 0 applied hardware tags and now **44 mentions** (30 at dc3123a). Lines that are new or moved: app.js:215/217 (the new banners; app.js:211 is gone), app/README.md:193, ui.md:4/20/29/94, PROJECT_STATUS.md:4/44, and T6's own audit documents and raw DOM dumps. T6 read each of these by hand: each says the data is not hardware-verified, or describes the not-live/recorded banner. Q1b: 0 navigation claims. The list below is the 30 confirmed at `dc3123a`.

## 1. Evidence labels / hardware tag (Q1a)
Rule (unchanged, PM-requested refinement): a line containing "[HARDWARE-VERIFIED]", "hardware-verified" or "hardware verified" is a **mention** only if the same line has a rule/negation cue (no, not, nothing, none, never, cannot, requires, until, before any, must not, may not, only if/when/after, without a, is/are not, carries). Any other occurrence is **applied** and fails while `reports/hardware_logs/` is missing. The self-test proves that "Heading RMSE 0.4 deg [HARDWARE-VERIFIED]" and a table cell "HARDWARE-VERIFIED" are still caught.

Result: **0 applied tags. 30 mentions, each read and confirmed by T6** to state that nothing is hardware-verified or to explain the rule:

- `README.md:24`
- `BLOCKERS.md:5`
- `PROJECT_STATUS.md:16`
- `TEAM_TRACKER.md:11`
- `TEAM_TRACKER.md:45`
- `REQUIREMENTS.md:19`
- `reports/HARDWARE_VALIDATION_CHECKLIST.md:4`
- `reports/demo/README.md:4`
- `reports/demo/README.md:21`
- `reports/demo/make_demo.py:30`
- `reports/contributions/firmware.md:3`
- `reports/contributions/hub.md:15`
- `reports/contributions/hardware.md:4`
- `reports/contributions/ui.md:4`
- `reports/contributions/ui.md:20`
- `reports/contributions/ui.md:74`
- `reports/contributions/sim.md:8`
- `reports/contributions/maths.md:4`
- `docs/firmware/FC_SETUP.md:3`
- `docs/firmware/FC_SETUP.md:199`
- `docs/math/HEADING_MATH.md:6`
- `docs/hardware/FACTSHEET.md:6`
- `docs/hardware/FACTSHEET.md:357`
- `docs/hardware/key_numbers.json:2`
- `app/README.md:172`
- `app/static/app.js:211`
- `app/static/index.html:26`
- `firmware_bridge/README.md:5`
- `firmware_bridge/scaling.py:5`
- `sim/README.md:8`

Special case: `app/static/app.js:211` is the banner text for `source:"hardware"`: "Live hardware samples. Accuracy is not hardware-verified…". As text it is a correct mention. At 471724e it was shown for a **replayed** hardware-labelled file (A8b), where "Live" is false. That was D6 (CRITICAL), now CLOSED: at 0ca6b0f the banner reads "Live hardware samples (serial)" and is used only for the serial transport.

## 2. Hardware-performance claims without a hardware log
**None found.** `reports/hardware_logs/` does not exist, so no result may be [HARDWARE-VERIFIED], and none is.
- Every RM3100 number is tagged [DATASHEET] / [OFFICIAL-DOC] / [SOURCE-CODE] / [DERIVED] (FACTSHEET, key_numbers.json, contributions/hardware.md). T6 independently re-read PNI UM Table 3-1 (gain 20/38/75 LSB/µT, noise 30/20/15 nT, ±800 µT).
- The range conflict ±800 vs ±1100 µT is disclosed (hardware.md L4, sim.md 2).
- Accuracy tables (docs/math/accuracy_results.md, maths.md) are labelled [SIMULATED]. maths.md:66 says openly that the table was copied, not re-run.
- reports/demo (video, screenshots, make_demo.py) carries the caption "Simulated data — not hardware-verified. Compass heading only; no position or navigation."
- INSTALL.md: "Live FC (untested on hardware)".
- FC_SETUP.md: INAV scaling and axis signs are "[SOURCE-CODE], not hardware-verified". The "fine for heading" claim for 0.1 µT steps is backed only by a [SIMULATED] quantisation study, and is labelled that way.

## 3. Heading only vs position / movement / navigation (Q1b)
**No claim rejected.** 89 lines matched the navigation inventory. None is a capability claim. Every one falls into one of these:
- **Explicit negation / scope rules**: app/README U0 "Heading is orientation, not movement or position… no position, coordinate, map, speed, course or distance"; index.html and app.js gpsNote; HEADING_MATH.md §1 and item 17 (binding scope rule: heading_core never provides position, displacement or distance; DR numbers are error analysis only).
- **Error analysis / education**: docs/math/sensor-spec SPEC.md §4 (heading vs track vs distance vs position; §4.6 "a perfect compass alone cannot give position", with a null-space test), TC10/TC12/TC17/TC18. T6 recomputed 34.8995 / 999.3908 / 34.9048 / 17.4524 m. These are adjudicated OK by path in the test, after a manual read.
- **GPS availability only**: contracts `gps {fix, num_sat, hdop}` "availability only (no position used)"; the bridge decodes only fixType/numSat from MSP_RAW_GPS, and zeroes or strips coordinates, speed, course and alt (bridge.py:270-278, scaling.py:89; fake_fc uses non-zero sentinels to prove the stripping). The UI shows Available/Unavailable/**Unknown** (A9a rendered `gpsStatus='Unknown'`). This tells you whether GPS has a fix, not where you are, and is not GPS-independent navigation.
- **Not navigation**: sim spec_check N/A reasons ("navigation… not modelled"), CSS `position:sticky`, a WebSocket `location.host`, "location-dependent" field magnitude.
- At HEAD~1 (`ed3961c`), `reports/contributions/maths.md:30` read "dead-reckoning scope rule". Q1b flagged it (the line has no negation). On manual reading it referred to the rule *forbidding* DR. Math reworded it in `dc3123a` ("heading-only scope rule (no position or navigation)"), and Q1b passes at HEAD. Not a defect.

## 4. Runtime claims (what the running app tells the user)
- Badge/banner for sim and replay data: correct (A1, A2, A3b, A4, A9a, A9b).
- D6 (CRITICAL, found at 471724e) is **CLOSED** after 0ca6b0f. A replayed hardware-labelled file now shows "REPLAY (recorded hardware)" with a not-live banner (A8, A8b at f058c9a), and the relabel could not be defeated (A10a). An ingest `hardware` sample shows UNVERIFIED SOURCE (A10b).
- ~~Limitation L-SER~~ **WITHDRAWN (v4).** The behaviour where a virtual serial port fed by a simulator was shown as live HARDWARE is defect **D8 (CRITICAL)**, fixed in e37430b/edc3ee0 (bridge) and e538cea/6c1e5b5 (app) and re-tested by T6 (verification_report §2e). The fake FC now shows SIMULATED and unknown devices show UNVERIFIED SOURCE (A10c–A10e, A10g).
- **D8 label decision (v4, §2d; PM d5374a1).** The allowlisted live badge reads "ALLOWLISTED DEVICE (identity not authenticated)", with the banner "Live serial device whose self-reported UID is on the local allowlist. The UID is not cryptographic proof; this is not hardware verification." The previous text "HARDWARE" with "Live hardware samples from a verified device" over-stated an administrative allowlist match as verification, and is being replaced (status in verification_report §2d).
- **Limitation F11.** The device identity is self-reported. A simulator that reports an allowlisted UID passes the allowlist (T6 spoof tests, A10f). **No T6 report, test or traceability text treats an allowlist match as proof of physical authenticity or as hardware validation.** T6 swept the repo for that wording at v4 (verification_report §2g). UI's `test_e2e_bridge_over_pty` is an F11 limitation demonstration, not hardware validation (D9).
- Ingest (`POST /api/sample`) keeps the client-declared `source`, but hardware via ingest is always UNVERIFIED SOURCE and never live. Since 6c1e5b5 any sample-supplied `provenance`, `device_verified` or `live_hardware` is ignored; T6 A10b and A10i plus the app/DOM ingest tests confirm this. `POST /api/sample` is refused (409) unless the app runs with `--source ingest`.

## LIMITATIONS of this audit
- Text pattern scan plus manual reading; claims phrased in ways no pattern covers could be missed in text T6 did not read. T6 read every matched line in context, plus README, REQUIREMENTS, TEAM_RULES, the ARCHITECTURE decision log, the INSTALL.md serial/pyserial sections, the demo README caption, app/README §U0/U4 and HEADING_MATH 14a. The contribution reports were checked by pattern scan plus a hand read of the matched lines, not cover to cover.
- Binary assets (png, mp4) were not inspected frame by frame; only make_demo.py and the demo README caption were checked.
