"""meta.mag_quant_uT and meta.fc_mag_calibrated (ARCHITECTURE.md 2026-11-27 decisions)."""
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from firmware_bridge import msp
from firmware_bridge.bridge import ALLOWED_REQUESTS, Poller, replay
from firmware_bridge.fake_fc import FakeFC, FakeFCTransport
from firmware_bridge.sample import SampleBuilder, validate_sample
from firmware_bridge.scaling import decode_calibration_data, fc_mag_calibration_state
from . import frames as F

ROOT = Path(__file__).resolve().parents[2]
BK = {"profile": "inav-msp-mag", "mag_ut_per_lsb": None, "accel_lsb_per_g": None}


def cal_payload(mag_zero=(0, 0, 0), mag_gain=(1024, 1024, 1024)):
    # hand-built INAV MSP_CALIBRATION_DATA: u8 flags, accZero[3], accGain[3], magZero[3], u16 opflow, magGain[3]
    return (bytes([0x3F]) + struct.pack("<3h", 1, -2, 3) + struct.pack("<3h", 4096, 4090, 4100)
            + struct.pack("<3h", *mag_zero) + struct.pack("<H", 0) + struct.pack("<3h", *mag_gain))


def fake_clock():
    st = {"t": 0.0}
    def clock():
        st["t"] += 0.001
        return st["t"]
    def sleep(s):
        st["t"] += s
    return clock, sleep


# ---- decoder / state logic --------------------------------------------------------------------
def test_decode_calibration_data_layout():
    d = decode_calibration_data(cal_payload((-12, 34, -56), (1000, 1100, 980)))
    assert d["acc_calib_axis_flags"] == 0x3F and d["acc_zero"] == [1, -2, 3]
    assert d["mag_zero"] == [-12, 34, -56] and d["mag_gain"] == [1000, 1100, 980]
    assert len(cal_payload()) == 27
    with pytest.raises(ValueError):
        decode_calibration_data(cal_payload()[:26])


@pytest.mark.parametrize("zero,gain,variant,expect", [
    ((0, 0, 0), (1024, 1024, 1024), "INAV", False),        # confirmed neutral
    ((5, 0, 0), (1024, 1024, 1024), "INAV", True),         # offset set
    ((0, 0, 0), (1024, 1024, 1000), "INAV", True),         # one gain changed
    ((0, 0, 0), (0, 0, 0), "INAV", "unknown"),             # build without USE_MAG writes zeros
    ((0, 0, 0), (1024, 1024, 1024), "BTFL", "unknown"),    # layout not verified for Betaflight
    ((0, 0, 0), (1024, 1024, 1024), None, "unknown"),      # FC variant not known
])
def test_calibration_state(zero, gain, variant, expect):
    cal = decode_calibration_data(cal_payload(zero, gain))
    assert fc_mag_calibration_state(cal, variant) == expect


def test_unavailable_is_unknown():
    assert fc_mag_calibration_state(None, "INAV") == "unknown"
    b = SampleBuilder("hardware")
    s = b.from_raw_imu(0, {"acc": [0, 0, 512], "gyro": [0, 0, 0], "mag": [1, 2, 3]})
    assert s["meta"]["fc_mag_calibrated"] == "unknown" and "fc_mag_cal" not in s["meta"]


# ---- mag_quant_uT ------------------------------------------------------------------------------
@pytest.mark.parametrize("profile,kw,q", [
    ("inav-msp-mag", {}, 0.1),
    ("inav-rm3100-spi", {}, 256 / 75),
    ("betaflight", {"mag_ut_per_lsb": 0.25}, 0.25),
])
def test_mag_quant_per_profile(profile, kw, q):
    s = SampleBuilder("hardware", profile, **kw).from_raw_imu(0, {"acc": [0, 0, 512], "gyro": [0] * 3, "mag": [1, 2, 3]})
    assert s["meta"]["mag_quant_uT"] == pytest.approx(q)
    assert validate_sample(s) == []


def test_mag_quant_sensor_compass_is_0p1():
    s = SampleBuilder("hardware", "inav-rm3100-spi").from_sensor_compass(
        0, {"instance": 0, "time_ms": 0, "mag_mgauss": [1, 2, 3]})
    assert s["meta"]["mag_quant_uT"] == 0.1


# ---- read-only safety -------------------------------------------------------------------------
def test_allowlist_read_only():
    assert msp.MSP_CALIBRATION_DATA == 14 and 14 in ALLOWED_REQUESTS
    for write_cmd in (15, 205, 206, 239, 250, 0x1004):   # SET_CALIBRATION_DATA, ACC_CALIBRATION, MAG_CALIBRATION, SET_ACC_TRIM, EEPROM_WRITE, COMMON_SET_SETTING
        assert write_cmd not in ALLOWED_REQUESTS


def test_bridge_never_sends_non_allowlisted_commands():
    sent = []
    class Spy(FakeFCTransport):
        def write(self, data):
            sent.extend(f.cmd for f in msp.MSPParser().feed(data))
            super().write(data)
    clock, sleep = fake_clock()
    list(Poller(Spy(FakeFC()), BK, 1, 20, clock=clock, sleep=sleep, cal_refresh_s=0.2).run(max_samples=30))
    assert set(sent) <= ALLOWED_REQUESTS and sent.count(14) >= 2   # initial + periodic refresh


# ---- end-to-end via fake FC (source='sim') ------------------------------------------------------
@pytest.mark.parametrize("fc_kw,expect", [
    ({}, False),
    ({"mag_zero": (10, -3, 7), "mag_gain": (980, 1010, 1050)}, True),
    ({"support_calibration_data": False}, "unknown"),          # FC answers '!' error frame
    ({"variant": "BTFL"}, "unknown"),
])
def test_poller_sets_fc_mag_calibrated(fc_kw, expect):
    clock, sleep = fake_clock()
    out = list(Poller(FakeFCTransport(FakeFC(**fc_kw)), BK, 2, 20, clock=clock, sleep=sleep).run(max_samples=3))
    for s in out:
        assert s["source"] == "sim"
        assert s["meta"]["fc_mag_calibrated"] == expect
        assert s["meta"]["mag_quant_uT"] == 0.1
        assert validate_sample(s) == []


def test_calibration_change_mid_run_is_picked_up():
    clock, sleep = fake_clock()
    fc = FakeFC()
    it = Poller(FakeFCTransport(fc), BK, 1, 20, clock=clock, sleep=sleep, cal_refresh_s=0.5).run(max_samples=40)
    first = next(it)
    assert first["meta"]["fc_mag_calibrated"] is False
    fc.mag_zero = (40, 0, 0)
    assert list(it)[-1]["meta"]["fc_mag_calibrated"] is True


# ---- replay -----------------------------------------------------------------------------------
def test_raw_binary_replay_with_and_without_calibration_frame(tmp_path):
    a = tmp_path / "with.bin"
    a.write_bytes(F.v1(2, b"INAV") + F.v1(14, cal_payload()) + F.v1(102, F.RAW_IMU))
    (s,) = list(replay(str(a), BK))
    assert s["source"] == "replay" and s["meta"]["fc_mag_calibrated"] is False and s["meta"]["mag_quant_uT"] == 0.1
    b = tmp_path / "noncal.bin"
    b.write_bytes(F.v2(2, b"INAV") + F.v2(14, cal_payload((3, 3, 3))) + F.v2(102, F.RAW_IMU))
    assert list(replay(str(b), BK))[0]["meta"]["fc_mag_calibrated"] is True
    c = tmp_path / "none.bin"
    c.write_bytes(F.v1(102, F.RAW_IMU))
    (s,) = list(replay(str(c), BK))
    assert s["meta"]["fc_mag_calibrated"] == "unknown" and s["meta"]["mag_quant_uT"] == 0.1
    d = tmp_path / "short.bin"   # truncated calibration payload -> unknown, sample still emitted
    d.write_bytes(F.v1(2, b"INAV") + F.v1(14, cal_payload()[:20]) + F.v1(102, F.RAW_IMU))
    assert list(replay(str(d), BK))[0]["meta"]["fc_mag_calibrated"] == "unknown"


def test_capture_replay_preserves_calibration_state(tmp_path):
    cap = tmp_path / "cap.jsonl"
    r = subprocess.run([sys.executable, "-m", "firmware_bridge", "--fake-fc", "--count", "3", "--capture", str(cap)],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    rep = list(replay(str(cap), {**BK, "_profile_explicit": False}))
    assert rep and all(s["source"] == "replay" and s["meta"]["fc_mag_calibrated"] is False
                       and s["meta"]["mag_quant_uT"] == 0.1 for s in rep)


def test_sample_jsonl_replay_keeps_but_never_invents(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text(json.dumps({"t": 0, "source": "hardware", "mag_uT": [1, 2, 3],
                             "meta": {"mag_quant_uT": 0.1, "fc_mag_calibrated": False}}) + "\n"
                 + json.dumps({"t": 1, "source": "sim", "mag_uT": [1, 2, 3]}) + "\n")
    a, b = list(replay(str(f), BK))
    assert a["meta"]["mag_quant_uT"] == 0.1 and a["meta"]["fc_mag_calibrated"] is False
    assert "mag_quant_uT" not in b["meta"] and "fc_mag_calibrated" not in b["meta"]
