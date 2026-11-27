"""D8 (ARCHITECTURE.md 2026-11-27): a serial connection is not proof of hardware.

SIMULATED  <- fake FC transport, or a device reporting fc_variant SIML / board SIMF (always wins)
UNVERIFIED <- any other live device: unknown/non-allowlisted UID, failed/short/missing UID or identity query
HARDWARE   <- live device whose MSP_UID matches config/verified_devices.json (here: a TEMPORARY tmp_path file)
Identity frames are hand-built (frames.py), independently of the bridge's encoder. Nothing here is hardware.
"""
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from firmware_bridge import msp
from firmware_bridge.bridge import ALLOWED_REQUESTS, Poller, replay
from firmware_bridge.fake_fc import FakeFC, FakeFCTransport
from firmware_bridge.identity import (DEFAULT_ALLOWLIST_PATH, DeviceIdentity, classify, load_allowlist,
                                      lookup_uid, normalise_uid)
from firmware_bridge.sample import validate_sample
from . import frames as F

ROOT = Path(__file__).resolve().parents[2]
BK = {"profile": "inav-msp-mag", "mag_ut_per_lsb": None, "accel_lsb_per_g": None}

UID_BYTES = bytes.fromhex("3a0027000d51333137363834")   # hand-picked, not a real board
UID_HEX = UID_BYTES.hex()
OTHER_UID = bytes.fromhex("ffeeddccbbaa998877665544")


def board_info(board=b"MKH7", target=b"MATEKH743"):
    # INAV fc_msp.c L494-530: boardIdentifier[4], u16 hwRevision, u8 osd, u8 capabilities, u8 len + targetName
    return board + struct.pack("<HBB", 0, 2, 0b011) + bytes([len(target)]) + target


def identity_replies(variant=b"INAV", board=b"MKH7", uid=UID_BYTES):
    r = {1: bytes([0, 2, 5]), 2: variant, 3: bytes([8, 0, 1]), 4: board_info(board)}
    if uid is not None:
        r[160] = uid
    return r


class ScriptedDevice:
    """A NON-sim transport (kind 'hardware') answering with hand-built frames: stands in for 'whatever is on
    the serial port'. cmd -> payload bytes; b'!' -> error frame; missing -> no reply."""
    kind = "hardware"

    def __init__(self, replies, version_frames=F.v1):
        self.replies = dict(replies)
        self.replies.setdefault(102, F.RAW_IMU)
        self.replies.setdefault(108, F.ATT)
        self.rx = bytearray()
        self.sent = []
        self.fr = version_frames

    def write(self, data):
        for f in msp.MSPParser().feed(data):
            self.sent.append(f.cmd)
            if f.cmd in self.replies:
                p = self.replies[f.cmd]
                self.rx.extend(self.fr(f.cmd, b"", d=b"!") if p == b"!" else self.fr(f.cmd, p))

    def read(self, n=4096, timeout=0.0):
        out = bytes(self.rx[:n]); del self.rx[:n]; return out

    def tick(self):
        pass

    def close(self):
        pass


def fake_clock():
    st = {"t": 0.0}
    def clock():
        st["t"] += 0.001
        return st["t"]
    def sleep(s):
        st["t"] += s
    return clock, sleep


def run(tr, allowlist, n=3, **kw):
    clock, sleep = fake_clock()
    out = list(Poller(tr, BK, 1, 20, clock=clock, sleep=sleep, allowlist=allowlist, **kw).run(max_samples=n))
    assert out and all(validate_sample(s) == [] for s in out)
    return out


def tmp_allowlist(tmp_path, *uids, label="bench FC #1"):
    p = tmp_path / "verified_devices.json"
    p.write_text(json.dumps({"devices": [{"uid": u, "label": label} for u in uids]}))
    return load_allowlist(p)


def badge(s):
    """The D8 contract in one place (docs/firmware/D8_PROVENANCE.md)."""
    m = s["meta"]
    if s["source"] == "sim" or m.get("provenance") == "simulated":
        return "SIMULATED"
    if s["source"] == "hardware":
        return "HARDWARE" if m.get("provenance") == "verified" else "UNVERIFIED SOURCE"
    return "REPLAY"


# ---- shipped allowlist ----------------------------------------------------------------------------
def test_shipped_allowlist_is_empty_and_well_formed():
    data = json.loads(DEFAULT_ALLOWLIST_PATH.read_text())
    assert data["devices"] == [] and load_allowlist() == {}
    assert DEFAULT_ALLOWLIST_PATH == ROOT / "config" / "verified_devices.json"


def test_allowlist_parsing_and_normalisation(tmp_path):
    al = tmp_allowlist(tmp_path, ":".join(UID_HEX[i:i + 2].upper() for i in range(0, 24, 2)), "0xZZ", "abc")
    assert set(al) == {UID_HEX} and lookup_uid(UID_HEX, al)["label"] == "bench FC #1"
    assert normalise_uid("0x" + UID_HEX.upper()) == UID_HEX and normalise_uid("12") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert load_allowlist(bad) == {} and load_allowlist(tmp_path / "missing.json") == {}


def test_identity_requests_are_allowlisted_read_only():
    for c in (1, 2, 3, 4, 160):
        assert c in ALLOWED_REQUESTS
    assert not ({5, 11, 15, 200, 201, 205, 206, 250} & ALLOWED_REQUESTS)   # SET_*/reboot/eeprom-write style


# ---- decoders ---------------------------------------------------------------------------------------
def frame(cmd, payload, d=">"):
    return msp.MSPFrame(1, d, cmd, payload)


def test_identity_decoding_inav_layouts():
    i = DeviceIdentity()
    for c, p in identity_replies().items():
        assert i.update(frame(c, p))
    m = i.as_meta()
    assert m["self_reported"] is True
    assert (m["api_version"], m["msp_protocol_version"], m["fc_variant"], m["fc_version"]) == ("2.5", 0, "INAV", "8.0.1")
    assert (m["board_id"], m["hw_revision"], m["target_name"], m["uid"]) == ("MKH7", 0, "MATEKH743", UID_HEX)
    assert set(m["query"].values()) == {"ok"}


def test_betaflight_fc_version_pstring_and_board_info_tail():
    i = DeviceIdentity()
    i.update(frame(3, bytes([25, 12, 0]) + bytes([7]) + b"2025.12"))
    bf_board = board_info(b"S7X2", b"STM32H743") + bytes([0, 0]) + bytes(32)   # name/manuf pstrings + signature
    i.update(frame(4, bf_board))
    assert i.fields["fc_version"] == "25.12.0" and i.fields["fc_version_string"] == "2025.12"
    assert i.fields["board_id"] == "S7X2" and i.fields["target_name"] == "STM32H743"


@pytest.mark.parametrize("cmd,payload,key", [(1, b"\x00\x02", "api_version"), (2, b"IN", "fc_variant"),
                                             (3, b"\x08", "fc_version"), (4, b"MK", "board_info"),
                                             (160, UID_BYTES[:11], "uid")])
def test_short_identity_replies(cmd, payload, key):
    i = DeviceIdentity()
    i.update(frame(cmd, payload))
    assert i.query[key] == "short"
    assert i.fields[{"board_info": "board_id"}.get(key, key)] is None


def test_error_reply_and_no_reply():
    i = DeviceIdentity()
    i.update(frame(160, b"", d="!"))
    i.mark_no_reply([1, 2, 3, 4, 160])
    assert i.query["uid"] == "error" and i.query["fc_variant"] == "no_reply"


# ---- SIMULATED ------------------------------------------------------------------------------------
def test_fake_fc_is_simulated_even_if_its_uid_is_allowlisted(tmp_path):
    fc = FakeFC()
    al = tmp_allowlist(tmp_path, fc.uid.hex())
    for s in run(FakeFCTransport(fc), al):
        assert s["source"] == "sim" and s["meta"]["provenance"] == "simulated" and badge(s) == "SIMULATED"
        assert s["meta"]["device_identity"]["fc_variant"] == "SIML"
        assert s["meta"]["device_identity"]["board_id"] == "SIMF"
        assert "verified_device_label" not in s["meta"]


@pytest.mark.parametrize("variant,board", [(b"SIML", b"SIMF"), (b"SIML", b"MKH7"), (b"INAV", b"SIMF")])
def test_sim_identity_over_a_serial_like_transport_is_simulated_and_wins_over_allowlist(tmp_path, variant, board):
    # e.g. the fake FC behind a virtual pty: SIML/SIMF always wins, even with an allowlisted UID (anti-spoof)
    al = tmp_allowlist(tmp_path, UID_HEX)
    for s in run(ScriptedDevice(identity_replies(variant, board)), al):
        assert s["source"] == "sim" and s["meta"]["provenance"] == "simulated" and badge(s) == "SIMULATED"


def test_cli_fake_fc_with_allowlisted_fake_uid_stays_sim(tmp_path):
    p = tmp_path / "vd.json"
    p.write_text(json.dumps({"devices": [{"uid": FakeFC().uid.hex(), "label": "spoof"}]}))
    r = subprocess.run([sys.executable, "-m", "firmware_bridge", "--fake-fc", "--count", "3",
                        "--verified-devices", str(p)], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    out = [json.loads(l) for l in r.stdout.splitlines()]
    assert out and all(s["source"] == "sim" and s["meta"]["provenance"] == "simulated" for s in out)


# ---- UNVERIFIED -----------------------------------------------------------------------------------
@pytest.mark.parametrize("enc", [F.v1, F.v2])
def test_unknown_device_non_allowlisted_uid_is_unverified(tmp_path, enc):
    al = tmp_allowlist(tmp_path, OTHER_UID.hex())
    for s in run(ScriptedDevice(identity_replies(), enc), al):
        assert s["source"] == "hardware" and s["meta"]["provenance"] == "unverified"
        assert badge(s) == "UNVERIFIED SOURCE"
        di = s["meta"]["device_identity"]
        assert di["self_reported"] is True and di["uid"] == UID_HEX and di["fc_variant"] == "INAV"
        assert "not in config/verified_devices.json" in s["meta"]["provenance_reason"]


@pytest.mark.parametrize("uid_reply,status", [(b"!", "error"), (None, "no_reply"), (UID_BYTES[:8], "short")])
def test_failed_uid_query_is_unverified_even_with_allowlist(tmp_path, uid_reply, status):
    al = tmp_allowlist(tmp_path, UID_HEX)
    rep = identity_replies(uid=None)
    if uid_reply is not None:
        rep[160] = uid_reply
    for s in run(ScriptedDevice(rep), al):
        assert s["source"] == "hardware" and s["meta"]["provenance"] == "unverified"
        assert s["meta"]["device_identity"]["query"]["uid"] == status
        assert s["meta"]["device_identity"]["uid"] is None


def test_no_identity_replies_at_all_is_unverified(tmp_path):
    al = tmp_allowlist(tmp_path, UID_HEX)
    for s in run(ScriptedDevice({}), al):
        assert s["source"] == "hardware" and s["meta"]["provenance"] == "unverified"
        assert set(s["meta"]["device_identity"]["query"].values()) == {"no_reply"}


def test_default_shipped_allowlist_means_nothing_is_verified():
    clock, sleep = fake_clock()
    s = next(Poller(ScriptedDevice(identity_replies()), BK, 1, 20, clock=clock, sleep=sleep).run(max_samples=1))
    assert s["meta"]["provenance"] == "unverified"


def test_passive_mode_sends_nothing_and_is_unverified(tmp_path):
    dev = ScriptedDevice({})
    dev.rx.extend(F.v2(0x1F04, F.COMPASS))   # AP_Periph pushing MSP2_SENSOR_COMPASS
    al = tmp_allowlist(tmp_path, UID_HEX)
    clock, sleep = fake_clock()
    s = next(Poller(dev, BK, 2, 20, clock=clock, sleep=sleep, passive=True, allowlist=al).run(max_samples=1))
    assert dev.sent == [] and s["source"] == "hardware" and s["meta"]["provenance"] == "unverified"


# ---- HARDWARE (only via allowlisted UID) ------------------------------------------------------------
@pytest.mark.parametrize("enc", [F.v1, F.v2])
def test_allowlisted_uid_is_the_only_hardware_path(tmp_path, enc):
    al = tmp_allowlist(tmp_path, UID_HEX.upper(), label="owner bench H743")
    out = run(ScriptedDevice(identity_replies(), enc), al)
    for s in out:
        assert s["source"] == "hardware" and s["meta"]["provenance"] == "verified" and badge(s) == "HARDWARE"
        assert s["meta"]["verified_device_label"] == "owner bench H743"
        assert s["meta"]["device_identity"]["self_reported"] is True


def test_classify_table():
    i = DeviceIdentity()
    for c, p in identity_replies().items():
        i.update(frame(c, p))
    al = {UID_HEX: {"uid": UID_HEX}}
    assert classify("hardware", i, al)[:2] == ("hardware", "verified")
    assert classify("hardware", i, {})[:2] == ("hardware", "unverified")
    assert classify("hardware", None, al)[:2] == ("hardware", "unverified")
    assert classify("replay", i, al)[:2] == ("replay", "unverified")      # replay never verified
    assert classify("sim", i, al)[:2] == ("sim", "simulated")


# ---- replay ------------------------------------------------------------------------------------------
def test_raw_replay_of_allowlisted_device_is_never_verified(tmp_path, monkeypatch):
    f = tmp_path / "dev.bin"
    f.write_bytes(b"".join(F.v1(c, p) for c, p in identity_replies().items()) + F.v1(102, F.RAW_IMU))
    (s,) = list(replay(str(f), BK))
    assert s["source"] == "replay" and s["meta"]["provenance"] == "unverified"
    assert s["meta"]["device_identity"]["uid"] == UID_HEX


def test_raw_replay_of_sim_identity_is_simulated(tmp_path):
    f = tmp_path / "sim.bin"
    f.write_bytes(F.v1(2, b"SIML") + F.v1(4, board_info(b"SIMF")) + F.v1(102, F.RAW_IMU))
    (s,) = list(replay(str(f), BK))
    assert s["source"] == "replay" and s["meta"]["provenance"] == "simulated"
    assert s["meta"]["original_source"] == "sim"


def test_capture_of_fake_fc_replays_as_simulated(tmp_path):
    cap = tmp_path / "cap.jsonl"
    r = subprocess.run([sys.executable, "-m", "firmware_bridge", "--fake-fc", "--count", "3", "--capture", str(cap)],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    rep = list(replay(str(cap), {**BK, "_profile_explicit": False}))
    assert rep and all(s["source"] == "replay" and s["meta"]["provenance"] == "simulated"
                       and s["meta"]["original_source"] == "sim" for s in rep)


def test_sample_jsonl_replay_keeps_recorded_provenance_but_is_replay(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text(json.dumps({"t": 0, "source": "hardware", "mag_uT": [1, 2, 3],
                             "meta": {"provenance": "unverified"}}) + "\n"
                 + json.dumps({"t": 1, "source": "hardware", "mag_uT": [1, 2, 3],
                               "meta": {"provenance": "verified"}}) + "\n")
    a, b = list(replay(str(f), BK))
    assert a["source"] == b["source"] == "replay"
    assert a["meta"]["provenance"] == "unverified" and b["meta"]["provenance"] == "verified"
    assert badge(a) == badge(b) == "REPLAY"


# ---- F12 regression: UID length must be exactly 12, lookup must be exact equality ---------------------
@pytest.mark.parametrize("uid_reply,status", [
    (UID_BYTES + b"\x00", "bad_length"),          # allowlisted UID + 1 extra byte (Auditor's 'extended' case)
    (UID_BYTES + OTHER_UID, "bad_length"),        # allowlisted UID + 12 extra bytes
    (UID_BYTES[:11], "short"),                    # allowlisted UID minus its last byte
    (UID_BYTES[:4], "short"),
])
@pytest.mark.parametrize("enc", [F.v1, F.v2])
def test_uid_with_allowlisted_prefix_but_wrong_length_is_unverified(tmp_path, uid_reply, status, enc):
    al = tmp_allowlist(tmp_path, UID_HEX)
    for s in run(ScriptedDevice(identity_replies(uid=uid_reply), enc), al):
        assert s["source"] == "hardware" and s["meta"]["provenance"] == "unverified", s["meta"]
        assert s["meta"]["device_identity"]["uid"] is None
        assert s["meta"]["device_identity"]["query"]["uid"] == status
        assert "verified_device_label" not in s["meta"]


def test_uid_decoder_never_truncates():
    i = DeviceIdentity()
    i.update(frame(160, UID_BYTES))
    assert i.fields["uid"] == UID_HEX and i.query["uid"] == "ok"
    i.update(frame(160, UID_BYTES + b"\x01"))        # a later bad reply clears the earlier good UID
    assert i.fields["uid"] is None and i.query["uid"] == "bad_length"


def test_allowlist_lookup_is_exact_equality_not_prefix(tmp_path):
    al = tmp_allowlist(tmp_path, UID_HEX, UID_HEX + "00", UID_HEX[:22])   # only the 24-hex entry is valid
    assert set(al) == {UID_HEX}
    assert lookup_uid(UID_HEX, al) is not None
    assert lookup_uid(UID_HEX + "00", al) is None and lookup_uid(UID_HEX[:22], al) is None
    assert lookup_uid(UID_HEX[:-1] + "5", al) is None
    assert lookup_uid(None, al) is None and lookup_uid(UID_HEX, None) is None and lookup_uid(UID_HEX, {}) is None


def test_replay_with_overlong_uid_has_no_uid(tmp_path):
    f = tmp_path / "long.bin"
    f.write_bytes(b"".join(F.v1(c, p) for c, p in identity_replies(uid=UID_BYTES + b"\x00").items())
                  + F.v1(102, F.RAW_IMU))
    (s,) = list(replay(str(f), BK))
    assert s["source"] == "replay" and s["meta"]["provenance"] == "unverified"
    assert s["meta"]["device_identity"]["uid"] is None
    assert s["meta"]["device_identity"]["query"]["uid"] == "bad_length"
