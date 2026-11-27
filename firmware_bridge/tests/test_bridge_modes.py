import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from firmware_bridge import msp
from firmware_bridge.bridge import BridgeError, Poller, frames_to_samples, replay
from firmware_bridge.fake_fc import FakeFC, FakeFCTransport
from firmware_bridge.sample import SampleBuilder, validate_sample
from . import frames as F

ROOT = Path(__file__).resolve().parents[2]
BK = {"profile": "inav-msp-mag", "mag_ut_per_lsb": None, "accel_lsb_per_g": None}


def fake_clock():
    st = {"t": 0.0}
    def clock():
        st["t"] += 0.001
        return st["t"]
    def sleep(s):
        st["t"] += s
    return clock, sleep


@pytest.mark.parametrize("ver", [1, 2, 21])
def test_fake_fc_poll_is_sim(ver):
    clock, sleep = fake_clock()
    tr = FakeFCTransport(FakeFC())
    samples = list(Poller(tr, BK, ver, 20, clock=clock, sleep=sleep).run(max_samples=5))
    assert len(samples) == 5
    for s in samples:
        assert s["source"] == "sim" and validate_sample(s) == []
        assert s["meta"]["msp_version"] == ver and s["meta"]["fc_variant"] == "SIML"  # D8: fake FC identifies as SIML
    assert samples[-1]["t"] > samples[0]["t"]


def test_sim_label_cannot_be_overridden():
    # source comes from the transport class, never from caller kwargs
    tr = FakeFCTransport()
    with pytest.raises(TypeError):
        Poller(tr, {**BK, "source": "hardware"})
    assert FakeFCTransport.kind == "sim"


def test_raw_imu_error_frames_stop_with_clear_error():
    clock, sleep = fake_clock()
    tr = FakeFCTransport(FakeFC(variant="ARDU", support_raw_imu=False))
    with pytest.raises(BridgeError, match="MSP_RAW_IMU"):
        list(Poller(tr, BK, 1, 20, clock=clock, sleep=sleep).run(max_samples=3))


def test_poller_refuses_write_commands():
    p = Poller(FakeFCTransport(), BK)
    with pytest.raises(BridgeError):
        p.send(205)   # MSP_SET_RAW_RC-class / any non-whitelisted id


def test_frames_to_samples_uses_latest_attitude():
    class St: attitude = None; raw_imu_errors = 0
    frs = msp.MSPParser().feed(F.v1(108, F.ATT) + F.v1(102, F.RAW_IMU) + F.v2(0x1F04, F.COMPASS, b"<"))
    out = frames_to_samples(frs, 1.0, SampleBuilder("replay"), St)
    assert len(out) == 2 and out[0]["fc_attitude_deg"]["yaw"] == 271.0
    assert out[1]["meta"]["msg"] == "MSP2_SENSOR_COMPASS"


def test_replay_raw_binary(tmp_path):
    f = tmp_path / "cap.bin"
    f.write_bytes(b"junk" + F.v1(108, F.ATT) + F.v1(102, F.RAW_IMU) + F.v2(102, F.RAW_IMU)[:-1] + b"\x00"
                  + F.v2(102, F.RAW_IMU))
    out = list(replay(str(f), BK, rate_hz=10))
    assert [s["t"] for s in out] == [0.0, 0.1]          # corrupted middle frame dropped
    assert all(s["source"] == "replay" and validate_sample(s) == [] for s in out)


def test_replay_sample_jsonl_relabels(tmp_path):
    f = tmp_path / "in.jsonl"
    f.write_text(json.dumps({"t": 1.0, "source": "hardware", "mag_uT": [1, 2, 3]}) + "\n\n"
                 + json.dumps({"t": 1.1, "source": "sim", "mag_uT": [1, 2, 3], "meta": {"x": 1}}) + "\n")
    out = list(replay(str(f), BK))
    assert [s["source"] for s in out] == ["replay", "replay"]
    assert [s["meta"]["original_source"] for s in out] == ["hardware", "sim"]
    assert out[1]["meta"]["x"] == 1


def test_capture_then_replay_roundtrip(tmp_path):
    cap = tmp_path / "cap.jsonl"
    r = subprocess.run([sys.executable, "-m", "firmware_bridge", "--fake-fc", "--count", "4",
                        "--msp-version", "2", "--capture", str(cap)],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    live = [json.loads(l) for l in r.stdout.splitlines()]
    assert len(live) == 4 and all(s["source"] == "sim" for s in live)
    rep = list(replay(str(cap), {**BK, "_profile_explicit": False}))
    assert len(rep) >= 4
    assert [s["mag_uT"] for s in rep[:4]] == [s["mag_uT"] for s in live]
    assert all(s["source"] == "replay" for s in rep)


def test_cli_replay_and_missing_pyserial_message(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text(json.dumps({"t": 0, "source": "sim", "mag_uT": [1, 2, 3]}) + "\n")
    r = subprocess.run([sys.executable, "-m", "firmware_bridge", "--replay", str(f)],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and json.loads(r.stdout)["source"] == "replay"
    try:
        import serial  # noqa: F401
        have = True
    except ImportError:
        have = False
    if not have:
        r = subprocess.run([sys.executable, "-m", "firmware_bridge", "--port", "/dev/null-nonexistent"],
                           cwd=ROOT, capture_output=True, text=True, timeout=60)
        assert r.returncode == 2 and "pip install pyserial" in r.stderr


def test_cli_modes_mutually_exclusive():
    r = subprocess.run([sys.executable, "-m", "firmware_bridge", "--fake-fc", "--port", "/dev/x"],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "not allowed" in r.stderr


@pytest.mark.skipif(not hasattr(os, "openpty"), reason="needs a POSIX pty")
@pytest.mark.parametrize("fc_kw,source,prov", [
    ({}, "sim", "simulated"),                          # D8: fake FC (SIML/SIMF) behind a serial port -> SIMULATED
    ({"variant": "INAV", "board_id": "MKH7"}, "hardware", "unverified"),   # unknown device -> UNVERIFIED
])
def test_serial_transport_over_virtual_pty(fc_kw, source, prov):
    """Exercises the pyserial path end-to-end against a *virtual* pty driven by FakeFC.
    No physical device. D8: a serial connection is not proof of hardware; the 'hardware' label here
    is never 'verified' (shipped allowlist is empty). Nothing from this test is a hardware result."""
    pytest.importorskip("serial")
    import threading
    from firmware_bridge.bridge import SerialTransport
    master, slave = os.openpty()
    import tty
    tty.setraw(slave)
    fc = FakeFC(**fc_kw)
    stop = threading.Event()

    def serve():
        while not stop.is_set():
            try:
                data = os.read(master, 1024)
            except OSError:
                return
            for fr in fc.parser.feed(data):
                os.write(master, fc.handle(fr))
    th = threading.Thread(target=serve, daemon=True)
    th.start()
    tr = SerialTransport(os.ttyname(slave), 115200)
    try:
        out = list(Poller(tr, BK, 1, 50).run(max_samples=3))
    finally:
        stop.set(); tr.close(); os.close(slave); os.close(master)
    assert len(out) == 3 and all(s["source"] == source and s["meta"]["provenance"] == prov
                                 and validate_sample(s) == [] for s in out)


def test_fake_fc_output_frame_convention():
    """Fake FC emits INAV-convention (forward-left-up) vectors; the bridge must output FRD:
    level accel (0,0,-1) g, field z > 0 (northern hemisphere), heading = FC yaw."""
    import math
    clock, sleep = fake_clock()
    out = list(Poller(FakeFCTransport(FakeFC(yaw_rate_dps=90)), BK, 2, 20, clock=clock, sleep=sleep)
               .run(max_samples=20))
    for s in out:
        assert s["accel_g"] == [0.0, 0.0, -1.0]
        m = s["mag_uT"]
        assert m[2] > 0
        hdg = math.degrees(math.atan2(-m[1], m[0])) % 360
        d = (hdg - s["fc_attitude_deg"]["yaw"] + 180) % 360 - 180
        assert abs(d) < 6     # fake yaw is integer degrees + one poll of lag at 90 deg/s
        assert s["gyro_dps"][2] == 90.0   # clockwise yaw positive about FRD z


def test_replay_skips_schema_invalid_sample_lines(tmp_path, capfd):
    f = tmp_path / "bad.jsonl"
    rows = [{"t": 0, "source": "sim", "mag_uT": [1, 2]}, {"t": 0.1, "source": "sim", "mag_uT": ["a", 1, 2]},
            {"t": "x", "source": "sim", "mag_uT": [1, 2, 3]}, {"t": 0.2, "source": "sim", "mag_uT": [20, 1, 40]}]
    f.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
    out = list(replay(str(f), BK))
    assert [s["t"] for s in out] == [0.2] and validate_sample(out[0]) == []
    assert "invalid Sample skipped" in capfd.readouterr().err
