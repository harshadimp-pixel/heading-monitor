"""D8: self-reported device identity over MSP and source/provenance classification.

ARCHITECTURE.md 2026-11-27 (PM, D8): a serial connection is not proof of hardware.

Read-only identity requests (payload layouts verified in source, INAV pinned maintenance-10.x @fce6c94,
src/main/fc/fc_msp.c; Betaflight master src/main/msp/msp.c; ArduPilot master AP_MSP_Telem_Backend.cpp):

  MSP_API_VERSION (1)   INAV L478-482 / BF L715-719 / AP L665-679:
                        u8 mspProtocolVersion, u8 apiMajor, u8 apiMinor                       (3 bytes, all three)
  MSP_FC_VARIANT  (2)   INAV L484-486 / BF L721-723 / AP L697-701: 4 ASCII ("INAV", "BTFL", "ARDU")
  MSP_FC_VERSION  (3)   INAV L488-492, AP L681-695: u8 major, u8 minor, u8 patch                 (3 bytes)
                        BF L725-733: u8 (year-2000), u8 month, u8 patch, then a pstring (u8 len + text)
                        with the full version string (API >= 1.47, not on HD-VTX ports).
  MSP_BOARD_INFO  (4)   INAV L494-530: 4 ASCII boardIdentifier, u16 hwRevision, u8 osd(0/2), u8 capabilities,
                        u8 len + targetName.  BF L741-: same first 9 bytes + targetName pstring, then board-name
                        and manufacturer pstrings and a 32-byte signature (ignored here).  AP L1447-1469: board id
                        "ARDU", u16 hw_rev, u8 aio, u8 caps, u8 len + firmware string (stored as target_name).
  MSP_UID       (160)   INAV L1191-1195 / BF L864-868: 3x u32 LE U_ID_0..2 (MCU 96-bit unique ID);
                        AP L1484-1491: 12 raw bytes from get_system_id_unformatted.  Exactly 12 payload bytes are
                        required (shorter -> 'short', longer -> 'bad_length', both = no UID); kept in wire
                        order as 24 lowercase hex chars (no byte swapping, no truncation).

Everything here is SELF-REPORTED by whatever is on the other end of the port. It can be spoofed; a UID is not
cryptographic proof. The allowlist only narrows "unverified" to "matches a UID someone signed off".
"""
from __future__ import annotations

import json
import os
import re
import struct
from pathlib import Path

from . import msp

SIM_FC_VARIANT = "SIML"
SIM_BOARD_ID = "SIMF"

IDENTITY_REQUESTS = (msp.MSP_API_VERSION, msp.MSP_FC_VARIANT, msp.MSP_FC_VERSION, msp.MSP_BOARD_INFO, msp.MSP_UID)
_KEY = {msp.MSP_API_VERSION: "api_version", msp.MSP_FC_VARIANT: "fc_variant", msp.MSP_FC_VERSION: "fc_version",
        msp.MSP_BOARD_INFO: "board_info", msp.MSP_UID: "uid"}

DEFAULT_ALLOWLIST_PATH = Path(__file__).resolve().parents[1] / "config" / "verified_devices.json"

PROVENANCE_SIMULATED = "simulated"
PROVENANCE_UNVERIFIED = "unverified"
PROVENANCE_VERIFIED = "verified"


def _ascii(b: bytes) -> str:
    s = b.decode("ascii", "replace").rstrip("\x00 ")
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in s)


def normalise_uid(uid) -> str | None:
    if not isinstance(uid, str):
        return None
    h = re.sub(r"[\s:\-]", "", uid.strip().lower())
    if h.startswith("0x"):
        h = h[2:]
    return h if re.fullmatch(r"[0-9a-f]{24}", h) else None


class DeviceIdentity:
    """Accumulates identity replies. query status per request: ok | error | short | bad_length (uid only:
    more than 12 bytes) | no_reply | not_queried."""

    def __init__(self):
        self.fields: dict = {"api_version": None, "msp_protocol_version": None, "fc_variant": None,
                             "fc_version": None, "fc_version_string": None, "board_id": None,
                             "hw_revision": None, "target_name": None, "uid": None}
        self.query = {k: "not_queried" for k in _KEY.values()}

    # -- decoding -------------------------------------------------------------------------------
    def update(self, frame: msp.MSPFrame) -> bool:
        """Feed any frame; returns True if it was an identity reply (ok, error or short)."""
        key = _KEY.get(frame.cmd)
        if key is None or frame.direction == "<":
            return False
        if frame.is_error:
            self.query[key] = "error"
            self._clear(key)
            return True
        p = frame.payload
        try:
            if frame.cmd == msp.MSP_API_VERSION:
                if len(p) < 3:
                    raise ValueError
                self.fields["msp_protocol_version"] = p[0]
                self.fields["api_version"] = f"{p[1]}.{p[2]}"
            elif frame.cmd == msp.MSP_FC_VARIANT:
                if len(p) < 4:
                    raise ValueError
                self.fields["fc_variant"] = _ascii(p[:4])
            elif frame.cmd == msp.MSP_FC_VERSION:
                if len(p) < 3:
                    raise ValueError
                self.fields["fc_version"] = f"{p[0]}.{p[1]}.{p[2]}"
                if len(p) >= 4 and len(p) >= 4 + p[3] and p[3] > 0:   # Betaflight pstring
                    self.fields["fc_version_string"] = _ascii(p[4:4 + p[3]])
            elif frame.cmd == msp.MSP_BOARD_INFO:
                if len(p) < 4:
                    raise ValueError
                self.fields["board_id"] = _ascii(p[:4])
                if len(p) >= 6:
                    self.fields["hw_revision"] = struct.unpack_from("<H", p, 4)[0]
                if len(p) >= 9 and len(p) >= 9 + p[8]:
                    self.fields["target_name"] = _ascii(p[9:9 + p[8]]) or None
            elif frame.cmd == msp.MSP_UID:
                # exactly 12 bytes (INAV/BF 3x u32, AP 12 raw bytes). Never truncate: a longer reply that starts
                # with an allowlisted UID must NOT verify (F12, found by the Auditor's T6 D8 tests).
                if len(p) < 12:
                    raise ValueError
                if len(p) != 12:
                    self.query["uid"] = "bad_length"
                    self._clear("uid")
                    return True
                self.fields["uid"] = p.hex()
        except ValueError:
            self.query[key] = "short"
            self._clear(key)
            return True
        self.query[key] = "ok"
        return True

    def _clear(self, key: str) -> None:
        for f in {"api_version": ("api_version", "msp_protocol_version"), "fc_variant": ("fc_variant",),
                  "fc_version": ("fc_version", "fc_version_string"),
                  "board_info": ("board_id", "hw_revision", "target_name"), "uid": ("uid",)}[key]:
            self.fields[f] = None

    def mark_no_reply(self, cmds) -> None:
        for c in cmds:
            k = _KEY[c]
            if self.query[k] == "not_queried":
                self.query[k] = "no_reply"

    @property
    def is_sim(self) -> bool:
        return self.fields["fc_variant"] == SIM_FC_VARIANT or self.fields["board_id"] == SIM_BOARD_ID

    def as_meta(self) -> dict:
        return {"self_reported": True, **self.fields, "query": dict(self.query)}


# -- allowlist ---------------------------------------------------------------------------------------
def load_allowlist(path: str | os.PathLike | None = None) -> dict:
    """uid(hex, normalised) -> entry. Missing or malformed file -> {} (fail closed: nothing verified)."""
    p = Path(path) if path is not None else DEFAULT_ALLOWLIST_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
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


def lookup_uid(uid: str | None, allowlist: dict | None) -> dict | None:
    u = normalise_uid(uid)
    return allowlist.get(u) if (u and allowlist) else None


# -- classification ----------------------------------------------------------------------------------
def classify(base_source: str, identity: DeviceIdentity | None, allowlist: dict | None):
    """-> (source, provenance, reason, verified_entry_or_None).

    Rules (in order; first match wins):
      1. base 'sim' (FakeFCTransport)                       -> sim / simulated
      2. reported fc_variant SIML or board_id SIMF          -> sim (or replay) / simulated   [SIML/SIMF ALWAYS WINS,
                                                               even if the UID is allowlisted: anti-spoof]
      3. base 'replay'                                      -> replay / unverified (never verified)
      4. base 'hardware' + UID in allowlist                 -> hardware / verified
      5. base 'hardware' otherwise (unknown, no/failed UID) -> hardware / unverified
    """
    if base_source == "sim":
        return "sim", PROVENANCE_SIMULATED, "simulated transport (fake FC)", None
    if identity is not None and identity.is_sim:
        f = identity.fields
        why = f"device reports fc_variant={f['fc_variant']!r} board_id={f['board_id']!r} (SIML/SIMF = simulator)"
        return ("replay" if base_source == "replay" else "sim"), PROVENANCE_SIMULATED, why, None
    if base_source == "replay":
        return "replay", PROVENANCE_UNVERIFIED, "replayed capture; replay is never verified", None
    uid = identity.fields["uid"] if identity is not None else None
    if uid is None:
        st = identity.query["uid"] if identity is not None else "not_queried"
        return "hardware", PROVENANCE_UNVERIFIED, f"no device UID (MSP_UID {st})", None
    entry = lookup_uid(uid, allowlist)
    if entry is not None:
        return "hardware", PROVENANCE_VERIFIED, "UID matches config/verified_devices.json", entry
    return "hardware", PROVENANCE_UNVERIFIED, "UID not in config/verified_devices.json", None
