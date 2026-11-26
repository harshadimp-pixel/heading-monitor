"""Build and validate Sample dicts (contracts/sample.schema.json)."""
from __future__ import annotations

import math
from numbers import Real

from .scaling import MAG_PROFILES, UT_PER_MGAUSS, MagProfile

SOURCES = ("sim", "replay", "hardware")


class SampleBuilder:
    def __init__(self, source: str, profile: str = "inav-msp-mag",
                 mag_ut_per_lsb: float | None = None, accel_lsb_per_g: float | None = None,
                 msp_version: int | None = None):
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

    def _meta(self, **extra) -> dict:
        m = {
            "bridge": "firmware_bridge",
            "mag_profile": self.profile.name,
            "mag_ut_per_lsb": self.mag_scale,
            "scaling_uncertain": list(self.profile.uncertain),
        }
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
            "mag_uT": [v * self.mag_scale for v in raw["mag"]],
            "gyro_dps": [float(v) for v in raw["gyro"]],
        }
        if self.accel_scale:
            s["accel_g"] = [v / self.accel_scale for v in raw["acc"]]
        if attitude is not None:
            s["fc_attitude_deg"] = dict(attitude)
        s["meta"] = self._meta(msg="MSP_RAW_IMU", msp_raw_imu=raw, **meta)
        return s

    def from_sensor_compass(self, t: float, msg: dict, attitude: dict | None = None, **meta) -> dict:
        s = {
            "t": float(t),
            "source": self.source,
            "mag_uT": [v * UT_PER_MGAUSS for v in msg["mag_mgauss"]],
        }
        if attitude is not None:
            s["fc_attitude_deg"] = dict(attitude)
        m = self._meta(msg="MSP2_SENSOR_COMPASS", msp_sensor_compass=msg, **meta)
        m["mag_ut_per_lsb"] = UT_PER_MGAUSS  # message is defined in mGauss regardless of profile
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
