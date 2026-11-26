"""Scenario definitions: attitude trajectory, motor current profile and default disturbance parameters.

Attitude angles are aerospace ZYX Euler angles in degrees; yaw is relative to TRUE north
(the magnetic heading truth is yaw - declination). Yaw may be returned unwrapped (continuous);
the simulator wraps it for output. All trajectories are smooth so gyro rates are well defined.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
import numpy as np

AttitudeFn = Callable[[float, float], tuple]      # (t, duration) -> (roll, pitch, yaw) deg
CurrentFn = Callable[[float, float], float]       # (t, duration) -> motor current A

SPIN_PERIOD_S = 20.0  # one full yaw revolution every 20 s (18 deg/s)


def _zero_current(t, d):
    return 0.0


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    attitude: AttitudeFn
    current: CurrentFn = _zero_current
    hard_iron_uT: tuple = (0.0, 0.0, 0.0)
    soft_iron: tuple = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    env_noise_uT: float = 0.0       # extra white field noise per axis (environment), 1-sigma
    imu_noise_scale: float = 1.0
    params: dict = field(default_factory=dict)


def _static(t, d):
    return (0.0, 0.0, 30.0)


def _yaw_spin(t, d):
    return (0.0, 0.0, 360.0 * t / SPIN_PERIOD_S)


def _tilted_spin(t, d):
    return (20.0, -15.0, 360.0 * t / SPIN_PERIOD_S)


def _calibration_dance(t, d):
    # incommensurate periods -> body-frame field direction sweeps most of the sphere in ~30-60 s
    roll = 150.0 * np.sin(2 * np.pi * t / 17.0)
    pitch = 70.0 * np.sin(2 * np.pi * t / 11.0 + 0.7)
    yaw = 360.0 * t / 8.0
    return (float(roll), float(pitch), float(yaw))


def _motor_current(t, d):
    """Throttle-like profile as a fraction of run length: idle, 8 A, 20 A, pulsing 14+/-8 A, idle."""
    u = t / d if d > 0 else 0.0
    if u < 0.15:
        return 0.0
    if u < 0.35:
        return 8.0
    if u < 0.55:
        return 20.0
    if u < 0.80:
        return float(14.0 + 8.0 * np.sin(2 * np.pi * t / 2.0))
    return 0.0


_CAL_SOFT = ((1.10, 0.05, -0.03), (0.05, 0.92, 0.04), (-0.03, 0.04, 1.02))
_SOFT = ((1.15, 0.06, 0.00), (0.06, 0.88, 0.03), (0.00, 0.03, 1.00))

SCENARIOS: dict[str, Scenario] = {s.name: s for s in [
    Scenario("static", "level, stationary at true yaw 30 deg; sensor + IMU noise only", _static),
    Scenario("yaw_spin", "level, constant yaw spin, 1 rev / 20 s", _yaw_spin),
    Scenario("tilted_spin", "fixed tilt roll 20 deg, pitch -15 deg, yaw spin 1 rev / 20 s", _tilted_spin),
    Scenario("calibration_dance",
             "large roll/pitch/yaw sweeps (roll +/-150, pitch +/-70, yaw 1 rev / 8 s) for ellipsoid fitting; "
             "includes moderate hard- and soft-iron; use >= 30 s for good sphere coverage",
             _calibration_dance, hard_iron_uT=(12.0, -8.0, 5.0), soft_iron=_CAL_SOFT),
    Scenario("hard_iron", "yaw_spin with hard-iron offset (25, -15, 10) uT", _yaw_spin,
             hard_iron_uT=(25.0, -15.0, 10.0)),
    Scenario("soft_iron", "yaw_spin with symmetric soft-iron matrix", _yaw_spin, soft_iron=_SOFT),
    Scenario("motor_interference",
             "yaw_spin with current-proportional motor field (idle / 8 A / 20 A / pulsing / idle)",
             _yaw_spin, current=_motor_current),
    Scenario("high_noise", "yaw_spin with 1.0 uT environmental field noise and 5x IMU noise", _yaw_spin,
             env_noise_uT=1.0, imu_noise_scale=5.0),
]}


def get_scenario(name: str) -> Scenario:
    try:
        return SCENARIOS[name]
    except KeyError:
        raise ValueError(f"unknown scenario {name!r}; choose from {sorted(SCENARIOS)}") from None
