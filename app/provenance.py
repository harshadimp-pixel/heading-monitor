"""D8 (ARCHITECTURE.md, PM 2026-11-27, from the Codex audit): a serial connection is NOT proof of hardware.

App-side adapter, applied by the hub to every sample that arrives over the serial transport:
  * device self-identifies as a simulator (FC variant "SIML" or board id "SIMF") -> source "sim" (SIMULATED)
  * meta.device_identity.uid is in config/verified_devices.json                 -> stays "hardware", verified
  * anything else (no identity, no uid, uid not listed, allowlist missing/bad)  -> stays "hardware", NOT verified;
    the UI shows UNVERIFIED SOURCE with board/variant labelled "reported by device".
HARDWARE is displayed only for verified samples. config/verified_devices.json ships empty, so today nothing shows HARDWARE.

Ownership: firmware_bridge (T4) owns the identity query, the field names and the allowlist loader/file
(config/verified_devices.json). This module uses firmware_bridge.identity.load_allowlist/normalise_uid when they are
importable and otherwise falls back to a fail-closed mirror of the same format. Points not fixed by ARCHITECTURE.md
are listed in OPEN_QUESTIONS.
"""
from __future__ import annotations

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ALLOWLIST = os.path.join(ROOT, "config", "verified_devices.json")
SIM_VARIANT, SIM_BOARD = "SIML", "SIMF"

# firmware_bridge (T4) owns the identity fields and the allowlist loader. Use its loader when it is importable
# (firmware_bridge/identity.py: load_allowlist, normalise_uid); otherwise a fail-closed mirror of the same format.
try:  # pragma: no cover - depends on what T4 has landed
    from firmware_bridge import identity as _fw
    if not (hasattr(_fw, "load_allowlist") and hasattr(_fw, "normalise_uid")):
        _fw = None
except Exception:  # pragma: no cover
    _fw = None

# Field names as used by firmware_bridge/identity.py (DeviceIdentity.as_meta), e37430b.
# ARCHITECTURE.md D8 itself names only meta.device_identity and the UID; see OPEN_QUESTIONS.
VARIANT_KEY, BOARD_KEY, UID_KEY = "fc_variant", "board_id", "uid"
OPEN_QUESTIONS = (
    "ARCHITECTURE.md D8 does not name the device_identity keys; the app uses fc_variant / board_id / uid / "
    "target_name and meta.provenance as in docs/firmware/D8_PROVENANCE.md (committed by Firmware in e37430b), "
    "with meta.fc_variant as a fallback for the variant",
    "uid format: 24 lowercase hex chars (12 MSP_UID bytes, wire order), normalised as in identity.normalise_uid",
    "allowlist schema: {\"devices\": [{\"uid\": ..., \"label\": ...}]} (as in config/verified_devices.json)",
    "the Python loader (firmware_bridge.identity.load_allowlist) is not listed as an ARCHITECTURE interface",
    "app always passes its allowlist file to firmware_bridge --verified-devices (when the D8 bridge is importable); "
    "the flag is not in the ARCHITECTURE CLI line yet",
)


def normalise_uid(uid):
    if _fw is not None:
        return _fw.normalise_uid(uid)
    if not isinstance(uid, str):
        return None
    h = re.sub(r"[\s:\-]", "", uid.strip().lower())
    if h.startswith("0x"):
        h = h[2:]
    return h if re.fullmatch(r"[0-9a-f]{24}", h) else None


def _fallback_load(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    devices = data.get("devices") if isinstance(data, dict) else None
    for e in devices if isinstance(devices, list) else []:
        if isinstance(e, dict):
            u = normalise_uid(e.get("uid"))
            if u:
                out[u] = e
    return out


def load_verified_devices(path: str | None = None):
    """Return (set_of_normalised_uids, info). Fail closed: missing or malformed file -> empty set."""
    path = path or DEFAULT_ALLOWLIST
    info = {"path": path, "exists": os.path.isfile(path), "count": 0, "error": None,
            "loader": "firmware_bridge.identity.load_allowlist" if _fw is not None else "app fallback (D8)"}
    entries = _fw.load_allowlist(path) if _fw is not None else _fallback_load(path)
    uids = set(entries)
    info["count"] = len(uids)
    if not info["exists"]:
        info["error"] = "file not found; treated as empty (nothing can show HARDWARE)"
    elif not uids:
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            ok = isinstance(doc, dict) and isinstance(doc.get("devices"), list) and not doc["devices"]
        except (OSError, ValueError):
            ok = False
        if not ok:
            info["error"] = "no valid entries ({\"devices\": [{\"uid\": <24 hex>}]}); treated as empty"
    return uids, info


def reported_identity(sample: dict) -> dict:
    """Identity values as REPORTED BY THE DEVICE (never verified here)."""
    meta = sample.get("meta") if isinstance(sample.get("meta"), dict) else {}
    ident = meta.get("device_identity") if isinstance(meta.get("device_identity"), dict) else None
    d = ident or {}

    def txt(v):
        return v.strip() if isinstance(v, str) and v.strip() else None
    return {"has_identity": ident is not None, "variant": txt(d.get(VARIANT_KEY)) or txt(meta.get("fc_variant")),
            "board": txt(d.get(BOARD_KEY)), "uid": txt(d.get(UID_KEY)), "target": txt(d.get("target_name")),
            "bridge_provenance": txt(meta.get("provenance"))}


def apply_serial_provenance(sample: dict, allowlist: set):
    """Return (sample_out, device) for a sample received over the serial transport. Input is not mutated.
    HARDWARE needs BOTH: the bridge classified the sample meta.provenance == "verified" (docs/firmware/D8_PROVENANCE.md
    badge rule 3) AND the reported uid is in the app's own allowlist (defence in depth). Missing provenance (older
    bridge, other producers) is never verified. SIML/SIMF always wins (anti-spoof)."""
    rep = reported_identity(sample)
    dev = dict(rep, verified=False, status=None)
    src = sample.get("source")
    if rep["variant"] == SIM_VARIANT or rep["board"] == SIM_BOARD or rep["bridge_provenance"] == "simulated":
        dev["status"] = "simulator"
        if src == "hardware":
            s = dict(sample)
            meta = dict(s.get("meta") or {})
            meta["source_mapped_from"] = "hardware"
            meta["source_mapped_by"] = "app D8 adapter (device reports SIML/SIMF)"
            s["meta"], s["source"] = meta, "sim"
            return s, dev
        return sample, dev
    if src != "hardware":
        dev["status"] = "not_hardware"
        return sample, dev
    uid = normalise_uid(rep["uid"]) if rep["uid"] else None
    if not rep["has_identity"]:
        dev["status"] = "no_identity"
    elif not uid:
        dev["status"] = "no_uid"
    elif uid not in allowlist:
        dev["status"] = "uid_not_listed"
    elif rep["bridge_provenance"] != "verified":
        dev["status"] = "bridge_unverified"
    else:
        dev["status"], dev["verified"] = "verified", True
    return sample, dev
