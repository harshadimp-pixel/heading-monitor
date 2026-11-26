"""Build and validate Sample dicts (contracts/sample.schema.json)."""
from __future__ import annotations

import math
from numbers import Real

from .scaling import MAG_PROFILES, fc_mag_calibration_state, PITCH_SIGN_BY_VARIANT, UT_PER_MGAUSS, MagProfile, to_body_frd

SOURCES = ("sim", "replay", "hardware")


class SampleBuilder:
    def __init__(self, source: str, profile: str = "inav-msp-mag",
                 mag_ut_per_lsb: float | None = None, accel_lsb_per_g: float | None = None,
                 msp_version: int | None = None, body_frame: str | None = None):
        if source not in SOURCES:
            raise ValueError(f"invalid source {source!r}")
        if profile not in MAG_PROFILES:
            raise ValueError(f"unknown mag profile {profile!r}; choose from {sorted(MAG_PROFILES)}")
        self.source = source
        self.profile: MagProfile = MAG_PROFILES[profile]
        self.mag_scale = mag_ut_per_lsb if mag_ut_per_lsb is not None else self.profile.ut_per_lsb
        self.accel_scale = accel_lsb_per_g if accel_lsb_per_g is not None else self.profile.accel_lsb_per_g
        if self.mag_scale is None:
            raise ValueError(f"profile {profile!r} has no known mag scale; pass --mag-ut-per-lsb")
        self.msp_version = msp_version
        self.fc_variant: str | None = None
        self.body_frame = body_frame or self.profile.body_frame
        self.fc_cal: dict | None = None          # last decoded MSP_CALIBRATION_DATA
        self.fc_cal_source: str | None = None
        to_body_frd([0, 0, 0], self.body_frame)  # validate

    def set_fc_calibration(self, cal: dict | None, source: str = "MSP_CALIBRATION_DATA") -> None:
        self.fc_cal = cal
        self.fc_cal_source = source if cal is not None else None

    @property
    def fc_mag_calibrated(self):
        return fc_mag_calibration_state(self.fc_cal, self.fc_variant)

    def attitude_aero(self, att: dict) -> dict:
        """MSP_ATTITUDE (as decoded) -> aerospace convention (pitch + nose up)."""
        sign = PITCH_SIGN_BY_VARIANT.get(self.fc_variant or "INAV", -1.0)
        return {"roll": att["roll"], "pitch": att["pitch"] * sign if att["pitch"] else 0.0, "yaw": att["yaw"]}

    def _meta(self, **extra) -> dict:
        m = {
            "bridge": "firmware_bridge",
            "mag_profile": self.profile.name,
            "body_frame_in": self.body_frame,
            "mag_ut_per_lsb": self.mag_scale,
            # ARCHITECTURE.md 2026-11-27 "Quantised sources": step of the mag value as delivered (uT)
            "mag_quant_uT": self.mag_scale,
            # ARCHITECTURE.md 2026-11-27 "Single-calibration rule": True / False / "unknown"
            "fc_mag_calibrated": self.fc_mag_calibrated,
            "scaling_uncertain": list(self.profile.uncertain),
        }
        if self.fc_cal is not None:
            m["fc_mag_cal"] = {"source": self.fc_cal_source, "mag_zero": self.fc_cal["mag_zero"],
                               "mag_gain": self.fc_cal["mag_gain"]}
        if self.msp_version is not None:
            m["msp_version"] = self.msp_version
        if self.fc_variant:
            m["fc_variant"] = self.fc_variant
        m.update(extra)
        return m

    def from_raw_imu(self, t: float, raw: dict, attitude: dict | None = None, **meta) -> dict:
        s = {
            "t": float(t),
            "source": self.source,
            "mag_uT": [round(v * self.mag_scale, 6) + 0.0 for v in to_body_frd(raw["mag"], self.body_frame)],
            "gyro_dps": [float(v) + 0.0 for v in to_body_frd(raw["gyro"], self.body_frame)],
        }
        if self.accel_scale:
            s["accel_g"] = [v / self.accel_scale + 0.0 for v in to_body_frd(raw["acc"], self.body_frame)]
        if attitude is not None:
            s["fc_attitude_deg"] = self.attitude_aero(attitude)
        s["meta"] = self._meta(msg="MSP_RAW_IMU", msp_raw_imu=raw, msp_attitude=attitude, **meta)
        return s

    def from_sensor_compass(self, t: float, msg: dict, attitude: dict | None = None, **meta) -> dict:
        s = {
            "t": float(t),
            "source": self.source,
            "mag_uT": [round(v * UT_PER_MGAUSS, 6) for v in msg["mag_mgauss"]],
        }
        if attitude is not None:
            s["fc_attitude_deg"] = self.attitude_aero(attitude)
        m = self._meta(msg="MSP2_SENSOR_COMPASS", msp_sensor_compass=msg, **meta)
        m["body_frame_in"] = "frd"  # message is defined front/right/down (msp_sensors.h)
        m["mag_ut_per_lsb"] = UT_PER_MGAUSS  # message is defined in mGauss regardless of profile
        m["mag_quant_uT"] = UT_PER_MGAUSS
        m["scaling_uncertain"] = ["AP_Periph field includes node-side orientation/offsets; not hardware-checked."]
        s["meta"] = m
        return s


def _is_num(x) -> bool:
    return isinstance(x, Real) and not isinstance(x, bool) and math.isfinite(float(x))


def _vec(x, kind=_is_num) -> bool:
    return isinstance(x, list) and len(x) == 3 and all(kind(v) for v in x)


def validate_sample(s: dict) -> list[str]:
    """Dependency-free check against contracts/sample.schema.json. Returns a list of errors."""
    errs = []
    if not isinstance(s, dict):
        return ["sample is not an object"]
    for k in ("t", "source", "mag_uT"):
        if k not in s:
            errs.append(f"missing required '{k}'")
    if "t" in s and not _is_num(s["t"]):
        errs.append("t must be a number")
    if "source" in s and s["source"] not in SOURCES:
        errs.append(f"source must be one of {SOURCES}")
    for k in ("mag_uT", "accel_g", "gyro_dps"):
        if k in s and not _vec(s[k]):
            errs.append(f"{k} must be 3 numbers")
    if "mag_raw" in s and not _vec(s["mag_raw"], lambda v: isinstance(v, int) and not isinstance(v, bool)):
        errs.append("mag_raw must be 3 integers")
    if "rm3100_cycle_count" in s and not (isinstance(s["rm3100_cycle_count"], int)
                                          and not isinstance(s["rm3100_cycle_count"], bool)):
        errs.append("rm3100_cycle_count must be integer")
    if "fc_attitude_deg" in s:
        a = s["fc_attitude_deg"]
        if not isinstance(a, dict) or any(k in a and not _is_num(a[k]) for k in ("roll", "pitch", "yaw")):
            errs.append("fc_attitude_deg must be object of numbers")
    for k in ("meta", "truth"):
        if k in s and not isinstance(s[k], dict):
            errs.append(f"{k} must be an object")
    return errs
