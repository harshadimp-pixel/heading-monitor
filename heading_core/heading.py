"""Tilt-compensated heading (STUB - implementation in progress)."""
from __future__ import annotations


def wrap360(deg: float) -> float:
    """Wrap angle to [0, 360)."""
    raise NotImplementedError


def angle_diff_deg(a: float, b: float) -> float:
    """Signed shortest difference a - b in (-180, 180]."""
    raise NotImplementedError


def roll_pitch_from_accel(accel_g) -> tuple[float, float]:
    """(roll_deg, pitch_deg) from a static accelerometer reading in g (NED body frame)."""
    raise NotImplementedError


def tilt_compensated_heading(mag_uT, accel_g, declination_deg=0.0) -> float:
    """Heading in degrees [0,360), clockwise from magnetic north (true north if declination given)."""
    raise NotImplementedError
