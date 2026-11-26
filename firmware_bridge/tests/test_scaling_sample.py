import json
from pathlib import Path

import pytest

from firmware_bridge import scaling
from firmware_bridge.sample import SampleBuilder, validate_sample
from . import frames as F

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "sample.schema.json").read_text())


def schema_ok(s):
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(s, SCHEMA)
    assert validate_sample(s) == []


def test_decode_raw_imu_and_attitude():
    raw = scaling.decode_raw_imu(F.RAW_IMU)
    assert raw == {"acc": [10, -20, 512], "gyro": [1, -2, 30], "mag": [250, -123, 433]}
    att = scaling.decode_attitude(F.ATT)
    assert att == {"roll": 15.2, "pitch": -20.5, "yaw": 271.0}
    with pytest.raises(ValueError):
        scaling.decode_raw_imu(F.RAW_IMU[:17])


def test_attitude_negative_yaw_wrapped():
    import struct
    assert scaling.decode_attitude(struct.pack("<3h", 0, 0, -90))["yaw"] == 270.0


def test_inav_msp_mag_scaling_is_mgauss():
    s = SampleBuilder("hardware", "inav-msp-mag").from_raw_imu(1.0, scaling.decode_raw_imu(F.RAW_IMU))
    # raw (INAV forward-left-up) mag (250,-123,433) mG -> FRD (x,-y,-z) * 0.1 uT
    assert s["mag_uT"] == [25.0, 12.3, -43.3]
    assert s["accel_g"] == [10 / 512, 20 / 512, -1.0]
    assert s["gyro_dps"] == [1.0, 2.0, -30.0]
    schema_ok(s)


def test_inav_rm3100_spi_scaling():
    b = SampleBuilder("replay", "inav-rm3100-spi")
    s = b.from_raw_imu(0.0, {"acc": [0, 0, 512], "gyro": [0, 0, 0], "mag": [75, 0, -3]})
    assert s["mag_uT"][0] == pytest.approx(256.0)    # 75 LSB * 256/75
    assert s["mag_uT"][2] == pytest.approx(3 * 256 / 75)   # z flipped FLU->FRD
    # cross-check against the INAV driver arithmetic: raw24 -> (raw24 << 8) >> 16 == raw24 >> 8
    raw24 = 50 * 75                                   # 50 uT at 75 LSB/uT
    lsb = (raw24 << 8) >> 16
    assert lsb * b.mag_scale == pytest.approx(50.0, abs=256 / 75)
    schema_ok(s)


def test_betaflight_requires_explicit_scale():
    with pytest.raises(ValueError):
        SampleBuilder("hardware", "betaflight")
    s = SampleBuilder("hardware", "betaflight", mag_ut_per_lsb=0.5).from_raw_imu(
        0.0, scaling.decode_raw_imu(F.RAW_IMU))
    assert "accel_g" not in s and s["mag_uT"] == [125.0, 61.5, -216.5]
    schema_ok(s)


def test_sensor_compass_message():
    msg = scaling.decode_sensor_compass(F.COMPASS)
    assert msg == {"instance": 0, "time_ms": 123456, "mag_mgauss": [215, -100, 400]}
    s = SampleBuilder("hardware", "inav-rm3100-spi").from_sensor_compass(2.0, msg)
    assert s["mag_uT"] == [21.5, -10.0, 40.0]          # always mGauss, profile-independent
    schema_ok(s)


def test_sample_with_attitude_schema():
    s = SampleBuilder("sim").from_raw_imu(0.5, scaling.decode_raw_imu(F.RAW_IMU),
                                          scaling.decode_attitude(F.ATT))
    # INAV pitch -20.5 (nose up) -> aerospace +20.5
    assert s["fc_attitude_deg"] == {"roll": 15.2, "pitch": 20.5, "yaw": 271.0}
    assert "mag_raw" not in s   # MSP values are not RM3100 raw counts; kept in meta.msp_raw_imu
    schema_ok(s)


def test_validator_catches_errors():
    assert validate_sample({"t": 0, "source": "bogus", "mag_uT": [1, 2]})
    assert validate_sample({"source": "sim", "mag_uT": [1, 2, 3]}) == ["missing required 't'"]
    with pytest.raises(ValueError):
        SampleBuilder("live")


# ---- accel sign / body frame (ARCHITECTURE.md: level at rest = (0,0,-1) g, FRD) -----------------
import math
import struct


def _imu(acc, mag=(0, 0, 0), gyro=(0, 0, 0)):
    return scaling.decode_raw_imu(struct.pack("<9h", *acc, *gyro, *mag))


def test_level_at_rest_is_minus_one_g_z():
    s = SampleBuilder("hardware", "inav-msp-mag").from_raw_imu(0.0, _imu((0, 0, 512)))
    assert s["accel_g"] == [0.0, 0.0, -1.0]
    schema_ok(s)


def test_roll_right_and_nose_up_signs():
    b = SampleBuilder("hardware", "inav-msp-mag")
    phi = math.radians(30)
    # INAV FLU: right side down -> +ay (imuResetOrientationQuaternion q1 = ay, roll = +)
    s = b.from_raw_imu(0, _imu((0, round(512 * math.sin(phi)), round(512 * math.cos(phi)))))
    # FRD specific force for roll phi: (0, -sin phi, -cos phi)
    assert s["accel_g"][1] == pytest.approx(-math.sin(phi), abs=2e-3)
    assert s["accel_g"][2] == pytest.approx(-math.cos(phi), abs=2e-3)
    th = math.radians(20)
    # nose up -> +ax in INAV; FRD specific force (sin th, 0, -cos th)
    s = b.from_raw_imu(0, _imu((round(512 * math.sin(th)), 0, round(512 * math.cos(th)))))
    assert s["accel_g"][0] == pytest.approx(math.sin(th), abs=2e-3)
    assert s["accel_g"][2] == pytest.approx(-math.cos(th), abs=2e-3)


def test_heading_from_converted_mag_level():
    b = SampleBuilder("hardware", "inav-msp-mag")
    for psi in (0, 45, 90, 180, 271):
        r = math.radians(psi)
        # FRD body field (h cos, -h sin, z) mG; INAV FLU representation is (x, -y, -z)
        frd = (200 * math.cos(r), -200 * math.sin(r), 400)
        s = b.from_raw_imu(0, _imu((0, 0, 512), mag=(round(frd[0]), round(-frd[1]), round(-frd[2]))))
        m = s["mag_uT"]
        assert math.degrees(math.atan2(-m[1], m[0])) % 360 == pytest.approx(psi, abs=0.5)
        assert m[2] > 0   # northern-hemisphere field points down in FRD


def test_frd_override_and_ardupilot_pitch_sign():
    b = SampleBuilder("hardware", "inav-msp-mag", body_frame="frd")
    assert b.from_raw_imu(0, _imu((0, 0, -512)))["accel_g"] == [0.0, 0.0, -1.0]
    b.fc_variant = "ARDU"
    assert b.attitude_aero({"roll": 1.0, "pitch": 5.0, "yaw": 3.0})["pitch"] == 5.0
    b.fc_variant = "INAV"
    assert b.attitude_aero({"roll": 1.0, "pitch": 5.0, "yaw": 3.0})["pitch"] == -5.0
    with pytest.raises(ValueError):
        SampleBuilder("hardware", body_frame="xyz")


def test_sensor_compass_is_not_axis_converted():
    s = SampleBuilder("hardware").from_sensor_compass(0, {"instance": 0, "time_ms": 1, "mag_mgauss": [1, 2, 3]})
    assert s["mag_uT"] == [0.1, 0.2, 0.3] and s["meta"]["body_frame_in"] == "frd"
