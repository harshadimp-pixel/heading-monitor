# D8 provenance contract: firmware_bridge → app (for the UI & Software Developer)

Decision: ARCHITECTURE.md, PM D8 (2026-11-27, commit 1bef73e). **A serial connection is not proof of hardware.**
Implemented in `firmware_bridge` (`identity.py`, `sample.py`, `bridge.py`). **No schema change:** everything new is in
`meta` (an open object in `contracts/sample.schema.json`); `source` keeps its enum `sim | replay | hardware`.
Evidence: source-derived + hand-built frames + simulated. Nothing here is hardware-verified.

> **What `verified` means:** `provenance: "verified"` means only that the device's self-reported UID matches an administratively trusted list (`config/verified_devices.json`). It is NOT hardware authentication or proof of device identity, and NOT validation of current measurements or sensor correctness. The production allowlist stays empty. Whether the UI label for this case becomes ALLOWLISTED DEVICE is pending the Auditor's decision (no code or label change yet).

## Fields on every Sample the bridge emits

| Field | Values | Meaning |
|---|---|---|
| `source` | `sim` / `hardware` / `replay` | `sim` for the fake FC **or any device reporting `SIML`/`SIMF`**; `hardware` for any other live serial device (verified or not); `replay` for `--replay` |
| `meta.provenance` | `"simulated"` / `"unverified"` / `"verified"` | the only field that may unlock HARDWARE; `"verified"` only on a live serial session whose UID is in `config/verified_devices.json`. Means only "self-reported UID is on the administratively trusted list": not hardware authentication, not proof of identity, not validation of measurements |
| `meta.provenance_reason` | short text | why (e.g. `UID not in config/verified_devices.json`, `no device UID (MSP_UID error)`) |
| `meta.verified_device_label` | string | present only when `provenance == "verified"` (the allowlist entry's `label`) |
| `meta.device_identity` | object, see below | what the device **reported about itself**; `self_reported: true` always. Show as "reported by device" |

`meta.device_identity`:
```json
{"self_reported": true, "api_version": "2.5", "msp_protocol_version": 0, "fc_variant": "INAV",
 "fc_version": "8.0.1", "fc_version_string": null, "board_id": "MKH7", "hw_revision": 0,
 "target_name": "MATEKH743", "uid": "3a0027000d51333137363834",
 "query": {"api_version": "ok", "fc_variant": "ok", "fc_version": "ok", "board_info": "ok", "uid": "ok"}}
```
Any value can be `null`. `query.*` is `ok | error | short | no_reply | not_queried`, and for `uid` also `bad_length`.
`MSP_UID` must be **exactly 12 bytes**: fewer → `short`, more → `bad_length`; in both cases `uid` is `null` (never
truncated) and the sample is `unverified`. Allowlist matching is exact equality of the normalised 24-hex UID (no
prefix matching). `--passive` sends no queries, so
everything stays `not_queried` (unverified). Older bridge output and other producers have no `meta.provenance`.

## Badge rule (what the app should render)

Evaluate in order:
1. `source == "sim"` **or** `meta.provenance == "simulated"` → **SIMULATED**
2. `source == "replay"` → the existing D6 REPLAY rules (`meta.original_source`); never live, never HARDWARE
3. `source == "hardware"` **and** `meta.provenance == "verified"` **and** the transport is the app's own serial source → **HARDWARE**
4. `source == "hardware"` otherwise (provenance `unverified`, missing, or anything else; or ingest) → **UNVERIFIED SOURCE**,
   with `device_identity.board_id / fc_variant / target_name` shown as "reported by device"

The bridge itself never outputs `source:"hardware"` with `provenance:"verified"` unless the UID matched, and the
shipped allowlist is empty, so **today nothing can display HARDWARE** (D8 item 4).

## Bridge rules (classify, `firmware_bridge/identity.py`)
1. Fake-FC transport (`--fake-fc`) → `sim` / `simulated`. The fake FC reports variant `SIML`, board `SIMF`.
2. Reported `fc_variant == "SIML"` **or** `board_id == "SIMF"` → `sim` / `simulated` (`replay` / `simulated` on replay).
   **SIML/SIMF always wins**, even if that device's UID is allowlisted: a simulator can never be made "verified".
3. Replay → `replay`. Captures/raw bytes: `simulated` if the recorded identity is SIML/SIMF, else `unverified`; the
   allowlist is **never consulted on replay**. Sample JSONL keeps the recorded `meta.provenance` as written (it is
   never upgraded; a file can claim anything, and the source is `replay`, so it never shows HARDWARE).
4. Live serial + `MSP_UID` reply whose 24-hex UID is in the allowlist → `hardware` / `verified` (allowlist match of a
   self-reported UID only; see the note at the top).
5. Everything else live (unknown device, UID not listed, UID query error/short/bad_length/no reply, no identity at all, passive
   mode) → `hardware` / `unverified`.

## Allowlist `config/verified_devices.json`
`{"devices": [{"uid": "<24 hex = 12 MSP_UID payload bytes in wire order>", "label": "..."}]}`. Ships empty. Missing or
malformed file → treated as empty (fail closed). Case, `0x`, `:`/`-`/spaces are normalised. Add an entry only after
the HV checklist passes with the Auditor's sign-off and a committed hardware log. CLI: `--verified-devices FILE`.

## Limits
Identity is self-reported over the same wire: any device or script can claim any variant, board or UID. A UID is
not cryptographic proof; the allowlist only says "this is the UID that passed the HV checklist". Identity is read
once at connect (a device swapped on the same port mid-session is not detected).
