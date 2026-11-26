"""Optional `gps` availability object from MSP_RAW_GPS (106). Hand-built frames, SIMULATED only.

Payload layout per INAV fc_msp.c L1044-1053 @ fce6c94:
  u8 fixType, u8 numSat, i32 lat, i32 lon, u16 alt, u16 groundSpeed, u16 groundCourse, u16 hdop (18 bytes)
"""
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from firmware_bridge import msp
from firmware_bridge.bridge import ALLOWED_REQUESTS, Poller, replay, scrub_position_fields
from firmware_bridge.fake_fc import FakeFC, FakeFCTransport
from firmware_bridge.sample import SampleBuilder, validate_sample
from firmware_bridge.scaling import decode_raw_gps_availability, redact_raw_gps_payload
from . import frames as F

ROOT = Path(__file__).resolve().parents[2]
BK = {"profile": "inav-msp-mag", "mag_ut_per_lsb": None, "accel_lsb_per_g": None}

# Sentinel "coordinates" (not a real place) - distinctive values we can search the output for.
LAT, LON, ALT, SPD, CRS, HDOP = 123456789, -98765432, 4321, 1717, 2929, 155
SENTINEL_STRINGS = [str(v) for v in (LAT, LON, ALT, SPD, CRS, HDOP)] + ["12.3456789", "-9.8765432"]
FORBIDDEN_KEYS = {"lat", "lon", "lng", "latitude", "longitude", "alt", "altitude", "speed", "ground_speed",
                  "course", "ground_course", "hdop", "llh", "position", "coordinates"}


def gps_payload(fix=2, nsat=11):
    p = struct.pack("<BBiiHHHH", fix, nsat, LAT, LON, ALT, SPD, CRS, HDOP)
    assert len(p) == 18
    return p


def fake_clock():
    st = {"t": 0.0}
    def clock():
        st["t"] += 0.001
        return st["t"]
    def sleep(s):
        st["t"] += s
    return clock, sleep


def all_keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from all_keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from all_keys(v)


def assert_no_position(samples):
    for s in samples:
        assert not (set(k.lower() for k in all_keys(s)) & FORBIDDEN_KEYS), s
        text = json.dumps(s)
        for sv in SENTINEL_STRINGS:
            assert sv not in text, (sv, s)
        if "gps" in s:
            assert set(s["gps"]) <= {"fix", "num_sat"}


# ---- decoder ------------------------------------------------------------------------------------
@pytest.mark.parametrize("fix,expect", [(0, "none"), (1, "2d"), (2, "3d"), (7, "unknown")])
def test_decode_fix_mapping(fix, expect):
    assert decode_raw_gps_availability(gps_payload(fix, 9)) == {"fix": expect, "num_sat": 9}


def test_decode_returns_only_fix_and_num_sat_and_short_raises():
    assert set(decode_raw_gps_availability(gps_payload())) == {"fix", "num_sat"}
    with pytest.raises(ValueError):
        decode_raw_gps_availability(gps_payload()[:17])


def test_redaction_keeps_only_first_two_bytes():
    r = redact_raw_gps_payload(gps_payload(2, 11))
    assert r == bytes([2, 11]) + bytes(16)


def test_allowlist_has_106_and_it_is_read_only():
    assert msp.MSP_RAW_GPS == 106 and 106 in ALLOWED_REQUESTS
    assert 201 not in ALLOWED_REQUESTS   # MSP_SET_RAW_GPS (write) must never be allowed


# ---- hand-built 106 frames (v1, v2 native, v2-over-v1) through replay --------------------------
@pytest.mark.parametrize("enc", ["v1", "v2", "v21"])
def test_hand_built_106_frame_replay(tmp_path, enc):
    if enc == "v1":
        fr = lambda c, p: F.v1(c, p)
    elif enc == "v2":
        fr = lambda c, p: F.v2(c, p)
    else:
        fr = lambda c, p: msp.encode_v2_over_v1(c, p, ">")
    f = tmp_path / f"{enc}.bin"
    f.write_bytes(fr(2, b"INAV") + fr(106, gps_payload(2, 11)) + fr(102, F.RAW_IMU))
    (s,) = list(replay(str(f), BK))
    assert s["source"] == "replay" and s["gps"] == {"fix": "3d", "num_sat": 11}
    assert validate_sample(s) == []
    assert_no_position([s])


def test_hand_built_v1_frame_bytes_are_as_specified():
    p = gps_payload(1, 5)
    fr = F.v1(106, p)
    assert fr[:5] == b"$M>" + bytes([18, 106]) and fr[5:7] == bytes([1, 5])
    (frame,) = msp.MSPParser().feed(fr)
    assert frame.cmd == 106 and frame.payload == p


@pytest.mark.parametrize("name,stream", [
    ("no_gps_frame", F.v1(2, b"INAV") + F.v1(102, F.RAW_IMU)),
    ("error_frame", F.v1(2, b"INAV") + F.v1(106, b"", d=b"!") + F.v1(102, F.RAW_IMU)),
    ("short_payload", F.v1(2, b"INAV") + F.v1(106, gps_payload()[:10]) + F.v1(102, F.RAW_IMU)),
    ("not_inav", F.v1(2, b"BTFL") + F.v1(106, gps_payload()) + F.v1(102, F.RAW_IMU)),
    ("variant_unknown", F.v1(106, gps_payload()) + F.v1(102, F.RAW_IMU)),
])
def test_gps_omitted_when_unavailable(tmp_path, name, stream):
    f = tmp_path / f"{name}.bin"
    f.write_bytes(stream)
    (s,) = list(replay(str(f), BK))
    assert "gps" not in s and validate_sample(s) == []
    assert_no_position([s])


def test_error_after_good_clears_gps(tmp_path):
    f = tmp_path / "e.bin"
    f.write_bytes(F.v1(2, b"INAV") + F.v1(106, gps_payload()) + F.v1(102, F.RAW_IMU)
                  + F.v2(106, b"", d=b"!") + F.v1(102, F.RAW_IMU))
    a, b = list(replay(str(f), BK))
    assert a["gps"]["fix"] == "3d" and "gps" not in b


def test_no_fix_reported_as_none_with_zero_sats(tmp_path):
    f = tmp_path / "n.bin"
    f.write_bytes(F.v1(2, b"INAV") + F.v1(106, struct.pack("<BBiiHHHH", 0, 0, 0, 0, 0, 0, 0, 9999))
                  + F.v1(102, F.RAW_IMU))
    assert list(replay(str(f), BK))[0]["gps"] == {"fix": "none", "num_sat": 0}


def test_stale_gps_is_dropped():
    b = SampleBuilder(source="sim", **BK)
    b.fc_variant = "INAV"
    b.set_gps({"fix": "3d", "num_sat": 8}, t=0.0)
    from firmware_bridge.scaling import decode_raw_imu
    raw = decode_raw_imu(F.RAW_IMU)
    assert b.from_raw_imu(4.9, raw, None)["gps"]["num_sat"] == 8
    assert "gps" not in b.from_raw_imu(5.1, raw, None)


# ---- live poll against the fake FC (source='sim') ------------------------------------------------
@pytest.mark.parametrize("version", [1, 2, 21])
def test_poller_sim_gps(version):
    clock, sleep = fake_clock()
    out = list(Poller(FakeFCTransport(FakeFC(gps_fix_type=1, gps_num_sat=6)), BK, version, 20,
                      clock=clock, sleep=sleep).run(max_samples=5))
    assert out and all(s["source"] == "sim" and s["gps"] == {"fix": "2d", "num_sat": 6} for s in out)
    assert all(validate_sample(s) == [] for s in out)
    text = json.dumps(out)
    for sv in ("2052807258", "2069584763"):   # fake FC's sentinel lat/lon (0x7A5A5A5A, 0x7B5B5B5B)
        assert sv not in text
    assert_no_position(out)


def test_poller_no_gps_on_fc_omits_gps():
    clock, sleep = fake_clock()
    out = list(Poller(FakeFCTransport(FakeFC(gps_fix_type=None)), BK, 1, 20,
                      clock=clock, sleep=sleep).run(max_samples=5))
    assert out and all("gps" not in s for s in out)


def test_poller_no_reply_omits_and_stops_asking():
    class Mute(FakeFCTransport):
        def write(self, data):
            for f in self.fc.parser.feed(data):
                if f.direction == "<" and f.cmd != 106:
                    self.rx.extend(self.fc.handle(f))
    clock, sleep = fake_clock()
    p = Poller(Mute(FakeFC()), BK, 1, 20, clock=clock, sleep=sleep, gps_period_s=0.0)
    out = list(p.run(max_samples=6))
    assert out and all("gps" not in s for s in out) and p.gps_enabled is False


def test_poller_does_not_ask_non_inav_or_when_disabled():
    for fc_kw, kw in (({"variant": "BTFL"}, {}), ({}, {"gps": False})):
        sent = []
        class Spy(FakeFCTransport):
            def write(self, data):
                sent.extend(f.cmd for f in msp.MSPParser().feed(data))
                super().write(data)
        clock, sleep = fake_clock()
        out = list(Poller(Spy(FakeFC(**fc_kw)), BK, 1, 20, clock=clock, sleep=sleep, **kw).run(max_samples=3))
        assert 106 not in sent and all("gps" not in s for s in out)


def test_poller_gps_request_rate_limited():
    sent = []
    class Spy(FakeFCTransport):
        def write(self, data):
            sent.extend(f.cmd for f in msp.MSPParser().feed(data))
            super().write(data)
    clock, sleep = fake_clock()
    list(Poller(Spy(FakeFC()), BK, 1, 20, clock=clock, sleep=sleep).run(max_samples=60))   # ~3 s at 20 Hz
    assert 2 <= sent.count(106) <= 5 and set(sent) <= ALLOWED_REQUESTS


# ---- capture + Sample-JSONL replay --------------------------------------------------------------
def test_capture_file_has_coordinates_zeroed_and_replays(tmp_path):
    cap = tmp_path / "cap.jsonl"
    r = subprocess.run([sys.executable, "-m", "firmware_bridge", "--fake-fc", "--count", "3", "--capture", str(cap)],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    out = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
    assert out and all(s["source"] == "sim" and s["gps"] == {"fix": "3d", "num_sat": 12} for s in out)
    assert_no_position(out)
    raw = cap.read_text()
    for sentinel in ("5a5a5a7a", "5b5b5b7b", "7c7c", "7d7d", "7e7e", "7f7f"):  # LE hex of fake-FC sentinels
        assert sentinel not in raw
    gps_frames = [f for line in raw.splitlines()[1:] if "rx" in json.loads(line)
                  for f in msp.MSPParser().feed(bytes.fromhex(json.loads(line)["rx"])) if f.cmd == 106]
    assert gps_frames and all(f.payload == bytes([2, 12]) + bytes(16) for f in gps_frames)
    rep = list(replay(str(cap), {**BK, "_profile_explicit": False}))
    assert rep and all(s["source"] == "replay" and s["gps"] == {"fix": "3d", "num_sat": 12} for s in rep)


def test_sample_jsonl_replay_scrubs_position_and_keeps_contract_gps(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text(json.dumps({"t": 0, "source": "hardware", "mag_uT": [1, 2, 3], "lat": 12.3456789,
                             "gps": {"fix": "3d", "num_sat": 9, "lat": 12.3456789, "lon": -9.8765432},
                             "meta": {"altitude": 4321, "course": 2929}}) + "\n"
                 + json.dumps({"t": 1, "source": "sim", "mag_uT": [1, 2, 3]}) + "\n")
    a, b = list(replay(str(f), BK))
    assert a["source"] == "replay" and a["gps"] == {"fix": "3d", "num_sat": 9}
    assert "gps" not in b
    assert_no_position([a, b])


def test_scrub_helper():
    s = scrub_position_fields({"t": 0, "gps": {"fix": "2d", "hdop": 1.2, "speed": 3}, "meta": {"lon": 1}})
    assert s == {"t": 0, "gps": {"fix": "2d", "hdop": 1.2}, "meta": {}}


def test_invalid_gps_in_sample_jsonl_is_rejected(tmp_path):
    f = tmp_path / "bad.jsonl"
    f.write_text(json.dumps({"t": 0, "source": "hardware", "mag_uT": [1, 2, 3], "gps": {"fix": "4d"}}) + "\n")
    assert list(replay(str(f), BK)) == []
