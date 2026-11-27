"""T6 black-box tests of the firmware_bridge half of D8 (ARCHITECTURE.md 1bef73e; contract docs/firmware/D8_PROVENANCE.md
at e37430b). Only the CLI `python -m firmware_bridge` is run; the device on the other end of a virtual pty is either the
product FakeFC (default constructor) or T6's own MSPDevice emulator (tests/t6_msp_device.py). [SIMULATED]; no hardware.

Checks: source + meta.provenance per path; empty shipped allowlist => nothing verified; allowlist fail-closed;
SIML/SIMF always wins; replay never verified; F11 (self-reported UID is spoofable) characterised, not fixed.
"""
import json, os, shutil, subprocess, sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
PY = sys.executable
try:
    import serial  # noqa: F401
except Exception:
    pytest.skip("NOT RUN: pyserial missing, the serial path cannot be exercised", allow_module_level=True)
if not hasattr(os, "openpty"):
    pytest.skip("NOT RUN: openpty unavailable", allow_module_level=True)

from t6_msp_device import MSPDevice, ProductFakeFCOnPty  # noqa: E402

UID = bytes([0x36, 0x54, 0x00, 0x2B, 0x11, 0x47, 0x33, 0x30, 0x39, 0x38, 0x31, 0x01])
UIDHEX = UID.hex()


def bridge(args, dev=None, n=6, timeout=60):
    cmd = [PY, "-m", "firmware_bridge", *(["--port", dev.port] if dev else []), "--count", str(n), *args]
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    finally:
        if dev: dev.close()
    s = [json.loads(l) for l in p.stdout.splitlines() if l.strip().startswith("{")]
    assert s, f"bridge emitted no samples; rc={p.returncode} stderr={p.stderr[-800:]!r}"
    return s


def prov(s):
    return sorted({(x["source"], (x.get("meta") or {}).get("provenance")) for x in s})


def allow(tmp_path, entries, raw=None):
    f = tmp_path / "allow.json"
    f.write_text(raw if raw is not None else json.dumps({"devices": [{"uid": u, "label": "T6 temp"} for u in entries]}))
    return ["--verified-devices", str(f)]


def test_shipped_allowlist_file_is_empty():
    d = json.load(open(os.path.join(ROOT, "config", "verified_devices.json")))
    assert d.get("devices") == [], d


def test_fake_fc_on_pty_is_sim_simulated():
    s = bridge([], ProductFakeFCOnPty())
    assert prov(s) == [("sim", "simulated")]
    ident = s[-1]["meta"]["device_identity"]
    assert ident.get("self_reported") is True and ident.get("fc_variant") == "SIML" and ident.get("board_id") == "SIMF", ident


def test_fake_fc_mode_is_sim_simulated():
    assert prov(bridge(["--fake-fc"])) == [("sim", "simulated")]


@pytest.mark.parametrize("cfg", [dict(variant="INAV", board="MKH7", uid=UID), dict(variant="INAV", board="MKH7", uid=None),
                                 dict(variant=None, board=None, uid=None), dict(identity=False)],
                         ids=["allowlisted_uid_but_shipped_empty_list", "uid_missing", "identity_errors", "identity_failed"])
def test_shipped_empty_allowlist_never_verified(cfg):
    """With the shipped (empty) allowlist nothing can be verified, not even the UID T6 allowlists elsewhere."""
    s = bridge([], MSPDevice(**cfg))
    assert prov(s) == [("hardware", "unverified")], prov(s)
    assert all(x["meta"]["device_identity"].get("self_reported") is True for x in s)


def test_unknown_device_identity_is_reported_not_trusted():
    s = bridge([], MSPDevice(variant="BTFL", board="S7X2", uid=bytes([0x99] * 12)))
    assert prov(s) == [("hardware", "unverified")]
    i = s[-1]["meta"]["device_identity"]
    assert i["fc_variant"] == "BTFL" and i["board_id"] == "S7X2" and i["uid"] == "99" * 12 and i["self_reported"] is True, i


def test_allowlisted_uid_is_verified(tmp_path):
    s = bridge(allow(tmp_path, [UIDHEX]), MSPDevice(variant="INAV", board="MKH7", uid=UID))
    assert prov(s) == [("hardware", "verified")], prov(s)
    assert s[-1]["meta"].get("verified_device_label") == "T6 temp"


def test_allowlist_uid_normalisation(tmp_path):
    """Contract: case, 0x, ':', '-' and spaces are normalised."""
    fancy = "0x" + ":".join(UIDHEX[i:i + 2].upper() for i in range(0, 24, 2))
    assert prov(bridge(allow(tmp_path, [fancy]), MSPDevice(uid=UID))) == [("hardware", "verified")]


@pytest.mark.parametrize("uid", [bytes([0x99] * 12), None, UID[:11], UID + b"\x00", bytes(12), bytes(reversed(UID)),
                                 UID[:-1] + bytes([UID[-1] ^ 1])],
                         ids=["other", "missing", "truncated", "extended", "zero", "byte_reversed", "one_bit_off"])
def test_non_allowlisted_uid_unverified(tmp_path, uid):
    s = bridge(allow(tmp_path, [UIDHEX]), MSPDevice(variant="INAV", board="MKH7", uid=uid))
    assert prov(s) == [("hardware", "unverified")], prov(s)


@pytest.mark.parametrize("entries,raw", [([""], None), (["*"], None), ([UIDHEX[:12]], None), (None, "{not json"),
                                          (None, json.dumps([UIDHEX])), (None, json.dumps({"devices": UIDHEX}))],
                         ids=["empty_uid_entry", "wildcard", "prefix_entry", "malformed_json", "bare_list", "devices_not_list"])
def test_allowlist_fail_closed(tmp_path, entries, raw):
    s = bridge(allow(tmp_path, entries or [], raw), MSPDevice(variant="INAV", board="MKH7", uid=UID))
    # bare_list is not the documented schema; fail closed means unverified
    assert prov(s) == [("hardware", "unverified")], prov(s)


@pytest.mark.parametrize("variant,board", [("SIML", "MKH7"), ("INAV", "SIMF"), ("SIML", "SIMF")])
def test_sim_identity_always_wins_over_allowlisted_uid(tmp_path, variant, board):
    s = bridge(allow(tmp_path, [UIDHEX]), MSPDevice(variant=variant, board=board, uid=UID))
    assert prov(s) == [("sim", "simulated")], prov(s)


@pytest.mark.parametrize("variant,board", [("siml", "simf"), ("SIM ", "SIM "), ("S1ML", "S1MF")])
def test_sim_spelling_variants_never_verified(tmp_path, variant, board):
    s = bridge(allow(tmp_path, [UIDHEX]), MSPDevice(variant=variant, board=board, uid=bytes([0x99] * 12)))
    assert all(p != "verified" for _, p in prov(s)), prov(s)


def test_replay_never_verified(tmp_path):
    f = tmp_path / "claims_verified.jsonl"
    with open(f, "w") as fh:
        for i in range(10):
            fh.write(json.dumps({"t": i * 0.05, "source": "hardware", "mag_uT": [25.0, -3.0, 43.0], "accel_g": [0, 0, -1],
                                 "meta": {"provenance": "verified", "device_identity": {"uid": UIDHEX}}}) + "\n")
    s = bridge(["--replay", str(f)] + allow(tmp_path, [UIDHEX]), n=10)
    assert {x["source"] for x in s} == {"replay"}, prov(s)
    assert not [x for x in s if x["source"] == "hardware"]


def test_F11_emulated_device_reporting_allowlisted_uid_is_accepted(tmp_path):
    """CHARACTERISATION of limitation F11, not a pass of security: T6's emulator (no hardware) that simply reports an
    allowlisted UID is classified hardware/verified. The UID is self-reported and not cryptographic proof."""
    s = bridge(allow(tmp_path, [UIDHEX]), MSPDevice(variant="INAV", board="MKH7", uid=UID))
    assert prov(s) == [("hardware", "verified")]
