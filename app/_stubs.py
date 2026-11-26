"""LOCAL STUBS -- NOT the team's real implementations.

These exist only so the T5 app can run end-to-end while heading_core (T2), sim (T3)
and firmware_bridge (T4) are being built in parallel. They implement the SAME public
interfaces as ARCHITECTURE.md, with deliberately simple maths:

  * StubCalibration.fit  -> hard-iron offset = centre of min/max box, diagonal soft-iron
                            scale (NOT the ellipsoid fit T2 will provide).
  * stub_tilt_compensated_heading -> textbook tilt compensation, NED body frame
                            (x fwd, y right, z down); accel = specific force, level = [0,0,-1] g.
  * StubHeadingEstimator -> no smoothing, no gyro fusion; quality is a crude heuristic.
  * StubSim               -> Sample generator with source="sim" (NOT the T3 simulator).

core_adapter.py / sources.py use the real modules automatically when they are importable
and implemented (i.e. do not raise NotImplementedError). Nothing here ever emits
source="hardware".
"""
from __future__ import annotations

import math
import random
import time

NOMINAL_FIELD_UT = 50.0
STUB_LABEL = "app._stubs (LOCAL STUB)"


# ---------------------------------------------------------------- angle helpers
def wrap360(deg: float) -> float:
    d = math.fmod(deg, 360.0)
    if d < 0:
        d += 360.0
    if d >= 360.0:  # guards -1e-17 + 360 rounding to 360.0
        d = 0.0
    return d


def angle_diff_deg(a: float, b: float) -> float:
    """Signed shortest difference a - b in (-180, 180]."""
    d = wrap360(a - b)
    return d - 360.0 if d > 180.0 else d


def level_heading_deg(mag_uT) -> float:
    """Heading of a level sensor, NED body frame: atan2(-By, Bx)."""
    return wrap360(math.degrees(math.atan2(-mag_uT[1], mag_uT[0])))


def roll_pitch_from_accel(accel_g):
    ax, ay, az = accel_g
    roll = math.degrees(math.atan2(-ay, -az))
    pitch = math.degrees(math.atan2(ax, math.hypot(ay, az)))
    return roll, pitch


def stub_tilt_compensated_heading(mag_uT, accel_g, declination_deg=0.0) -> float:
    if accel_g is None:
        return wrap360(level_heading_deg(mag_uT) + declination_deg)
    roll, pitch = (math.radians(v) for v in roll_pitch_from_accel(accel_g))
    mx, my, mz = mag_uT
    xh = mx * math.cos(pitch) + (my * math.sin(roll) + mz * math.cos(roll)) * math.sin(pitch)
    yh = my * math.cos(roll) - mz * math.sin(roll)
    return wrap360(math.degrees(math.atan2(-yh, xh)) + declination_deg)


# ---------------------------------------------------------------- calibration
class StubCalibration:
    def __init__(self, offset=None, soft_iron=None, field_uT=None, residual_rms=None, n_samples=0):
        self.offset = [0.0, 0.0, 0.0] if offset is None else [float(v) for v in offset]
        self.soft_iron = ([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
                          if soft_iron is None else [[float(v) for v in r] for r in soft_iron])
        self.field_uT = field_uT
        self.residual_rms = residual_rms
        self.n_samples = n_samples

    def apply(self, mag_uT):
        c = [mag_uT[i] - self.offset[i] for i in range(3)]
        W = self.soft_iron
        return [sum(W[r][k] * c[k] for k in range(3)) for r in range(3)]

    @staticmethod
    def fit(samples_uT):
        if len(samples_uT) < 10:
            raise ValueError("need at least 10 samples")
        mins = [min(s[i] for s in samples_uT) for i in range(3)]
        maxs = [max(s[i] for s in samples_uT) for i in range(3)]
        offset = [(mins[i] + maxs[i]) / 2 for i in range(3)]
        radii = [max((maxs[i] - mins[i]) / 2, 1e-6) for i in range(3)]
        r_mean = sum(radii) / 3
        W = [[r_mean / radii[0], 0, 0], [0, r_mean / radii[1], 0], [0, 0, r_mean / radii[2]]]
        cal = StubCalibration(offset, W, field_uT=r_mean, n_samples=len(samples_uT))
        mags = [math.sqrt(sum(v * v for v in cal.apply(s))) for s in samples_uT]
        cal.residual_rms = math.sqrt(sum((m - r_mean) ** 2 for m in mags) / len(mags))
        return cal

    def to_dict(self):
        return {"offset": self.offset, "soft_iron": self.soft_iron, "field_uT": self.field_uT,
                "residual_rms": self.residual_rms, "n_samples": self.n_samples,
                "method": "stub-minmax-diagonal"}

    @staticmethod
    def from_dict(d):
        # accepts both the stub keys and heading_core's keys (offset_uT / residual_rms_uT)
        return StubCalibration(d.get("offset", d.get("offset_uT")), d.get("soft_iron"), d.get("field_uT"),
                               d.get("residual_rms", d.get("residual_rms_uT")), d.get("n_samples", 0))


# ---------------------------------------------------------------- estimator
class StubHeadingEstimator:
    def __init__(self, calibration=None, declination_deg=0.0, config=None):
        self.calibration = calibration
        self.declination_deg = declination_deg
        self.expected_field_uT = NOMINAL_FIELD_UT

    def update(self, sample: dict) -> dict:
        mag = sample["mag_uT"]
        acc = sample.get("accel_g")
        warnings = []
        if self.calibration is not None:
            cmag = self.calibration.apply(mag)
            calibrated = True
        else:
            cmag = list(mag)
            calibrated = False
            warnings.append("NOT_CALIBRATED")
        h = stub_tilt_compensated_heading(cmag, acc, self.declination_deg)
        field = math.sqrt(sum(v * v for v in cmag))
        out = {"t": sample["t"], "source": sample["source"], "heading_deg": h,
               "heading_raw_deg": h,  # stub has no smoothing: unfiltered == filtered
               "field_uT": field, "calibrated": calibrated}
        quality = 1.0 if calibrated else 0.5
        if acc is not None:
            r, p = roll_pitch_from_accel(acc)
            out["roll_deg"], out["pitch_deg"] = r, p
            if max(abs(r), abs(p)) > 45:
                warnings.append("TILT_TOO_LARGE")
                quality *= 0.5
        else:
            warnings.append("NO_ACCEL")
            quality *= 0.8
        ref = (self.calibration.field_uT if calibrated and self.calibration.field_uT
               else self.expected_field_uT)
        if abs(field / ref - 1) > 0.15:
            warnings.append("FIELD_MAGNITUDE_OUT_OF_RANGE")
            quality *= 0.5
        out["quality"] = round(quality, 3)
        out["warnings"] = warnings
        return out


# ---------------------------------------------------------------- simulator
STUB_SCENARIOS = ("slow_yaw_spin", "static", "tilted_spin", "hard_iron", "noisy", "dropouts")


class StubSim:
    """Yields contract Samples (source="sim") at `rate` Hz in real time.

    Earth field (NED) from total field B0 and dip angle; vehicle attitude per scenario.
    Placeholder numbers: B0=50 uT, dip=60 deg, noise 0.15 uT 1-sigma -- NOT from T1 datasheet.
    """

    def __init__(self, scenario="slow_yaw_spin", rate=20.0, seed=None, b0=50.0, dip_deg=60.0):
        if scenario not in STUB_SCENARIOS:
            raise ValueError(f"unknown stub scenario {scenario!r}; choose from {STUB_SCENARIOS}")
        self.scenario, self.rate = scenario, rate
        self.rng = random.Random(seed)
        d = math.radians(dip_deg)
        self.earth = [b0 * math.cos(d), 0.0, b0 * math.sin(d)]
        self.noise = 0.15 * (6 if scenario == "noisy" else 1)
        self.accel_noise = 0.005
        self.hard_iron = [8.0, -5.0, 3.0] if scenario in ("hard_iron", "slow_yaw_spin", "tilted_spin") else [0.0, 0.0, 0.0]

    @staticmethod
    def _rot(roll, pitch, yaw):
        cr, sr, cp, sp, cy, sy = (math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch),
                                  math.cos(yaw), math.sin(yaw))
        # body->NED, R = Rz(yaw) Ry(pitch) Rx(roll)
        return [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                [-sp, cp * sr, cp * cr]]

    def attitude(self, t):
        s = self.scenario
        if s == "static":
            return 0.0, 0.0, 37.0
        if s == "tilted_spin":
            return 20 * math.sin(0.5 * t), 15 * math.cos(0.3 * t), (12 * t) % 360
        if s in ("hard_iron",):
            return 25 * math.sin(0.7 * t), 25 * math.sin(0.45 * t), (30 * t) % 360
        return 3 * math.sin(0.4 * t), 2 * math.sin(0.25 * t), (10 * t) % 360

    def sample(self, t):
        roll, pitch, yaw = self.attitude(t)
        R = self._rot(*(math.radians(v) for v in (roll, pitch, yaw)))
        Rt = [[R[j][i] for j in range(3)] for i in range(3)]
        mag = [sum(Rt[i][k] * self.earth[k] for k in range(3)) + self.hard_iron[i]
               + self.rng.gauss(0, self.noise) for i in range(3)]
        grav = [0.0, 0.0, 1.0]
        acc = [-sum(Rt[i][k] * grav[k] for k in range(3)) + self.rng.gauss(0, self.accel_noise) for i in range(3)]
        return {"t": round(t, 4), "source": "sim", "mag_uT": [round(v, 4) for v in mag],
                "accel_g": [round(v, 5) for v in acc],
                "truth": {"heading_deg": round(wrap360(yaw), 3), "roll_deg": round(roll, 3),
                          "pitch_deg": round(pitch, 3)},
                "meta": {"generator": STUB_LABEL, "scenario": self.scenario}}

    def run(self, stop_event):
        """Generator of samples, paced in real time, until stop_event is set."""
        t0 = time.monotonic()
        n = 0
        while not stop_event.is_set():
            t = n / self.rate
            delay = t0 + t - time.monotonic()
            if delay > 0:
                stop_event.wait(delay)
            n += 1
            if self.scenario == "dropouts" and int(t) % 15 in (10, 11, 12):
                continue  # 3 s of silence every 15 s
            yield self.sample(t)
