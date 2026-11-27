# D8 spec review (T6)

Sources: ARCHITECTURE.md D8 entry (PM, 1bef73e) and the bridge contract docs/firmware/D8_PROVENANCE.md (Firmware, e37430b).
T6 tests: `tests/test_t6_d8_bridge.py` (bridge CLI, black-box) and `tests/test_t6_d8_provenance.py` (app plus rendered badge, black-box).
Both use `tests/t6_msp_device.py`, an independent MSP device emulator on a virtual pty, and the product FakeFC served on a pty. [SIMULATED]; no hardware.

## Ambiguities in ARCHITECTURE D8 (1bef73e) and how they were resolved

| # | Ambiguity in the D8 text | Resolved by D8_PROVENANCE.md (e37430b)? | T6 test position |
|---|---|---|---|
| A1 | Schema of config/verified_devices.json not defined | Yes: `{"devices":[{"uid","label"}]}`; a missing or malformed file counts as empty (fail closed) | Tests use that schema. A bare list or a non-list `devices` value must not verify anything |
| A2 | UID string format not defined | Yes: 24 hex characters from the 12 MSP_UID payload bytes in wire order. Case, `0x`, `:`, `-` and spaces are normalised | Normalisation is tested. Truncated, extended, reversed, one-bit-off, zero, empty, wildcard and prefix entries must not verify |
| A3 | Precedence when a device reports SIML/SIMF **and** an allowlisted UID | Yes: SIML/SIMF always wins and the sample becomes sim/simulated | Tested |
| A4 | Whether SIML/SIMF matching is case-sensitive, and the meaning of "SIML **and** SIMF" vs "or" | Contract: `fc_variant == "SIML"` **or** `board_id == "SIMF"` (exact) | Variants such as `siml`, `SIM `, `S1ML` and `SIMX` may be SIMULATED or UNVERIFIED but never verified or HARDWARE |
| A5 | Who decides HARDWARE: the bridge or the app? | Both. The bridge sets `meta.provenance`; the app may show HARDWARE only for hardware + verified + its own serial transport | App tests check the rendered badge and `live_hardware`. Ingest or replay of a file claiming `verified` must not give HARDWARE |
| A6 | How "reported by device" is shown | The contract says to show `board_id`, `fc_variant` and `target_name` as "reported by device" | The app test requires the text "reported by device" and the reported board id in the page |
| A7 | Behaviour when the identity changes mid-session (device swapped on the same port) | Not handled: identity is read once at connect (contract Limits) | Not testable black-box without a reconnect. Recorded as a limitation |

## Unresolved limitations (not defects)
- **F11 (Firmware), confirmed by T6:** identity, including the UID, is self-reported over the same wire. T6's emulator, with no hardware involved, reports an allowlisted UID and is classed as `hardware/verified` (`test_F11_emulated_device_reporting_allowlisted_uid_is_accepted`). The allowlist therefore proves only that a device reported a UID that once passed the HV checklist. It is not cryptographic proof. This is unresolved and has no fix in a virtual project.
- Identity is read once at connect (A7). `--passive` mode never queries, so it is always unverified (fail closed).

## Findings at e37430b (bridge half)
- **UID length (T6 finding, fixed by Firmware as F12 in edc3ee0):** at e37430b an MSP_UID reply longer than 12 bytes was truncated to its first 12 bytes (`identity.py` `p[:12].hex()`). A non-conforming 13-byte reply whose prefix was allowlisted was therefore classed as **verified**. T6 test `test_non_allowlisted_uid_unverified[extended]` failed at e37430b/af640ae. Firmware saw the test and fixed it in edc3ee0 (exactly 12 bytes required). It was not filed as a separate defect, and it is re-verified in the D8 rerun.
