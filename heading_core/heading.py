"""Tilt-compensated magnetic heading (HEADING_MATH.md sections 2-4).

Conventions
-----------
Body frame NED-style: x forward, y right, z down. Euler angles ZYX (yaw psi, pitch theta, roll phi):
roll > 0 = right wing down, pitch > 0 = nose up, heading clockwise from north seen from above.
Accelerometer convention set by `accel_convention` ("specific_force": level reads (0,0,-1) g;
"gravity": level reads (0,0,+1) g).
"""
from __future__ import annotations

import math

import numpy as np

from .config import ACCEL_SPECIFIC_FORCE, ACCEL_GRAVITY


def wrap360(deg: float) -> float:
    """Wrap angle to [0, 360). Robust to float round-off giving exactly 360."""
    w = math.fmod(float(deg), 360.0)
    if w < 0:
        w += 360.0
    if w >= 360.0:  # e.g. -1e-15 + 360 rounds to 360.0
        w = 0.0
    return w


def angle_diff_deg(a: float, b: float) -> float:
    """Signed shortest difference a - b in (-180, 180]."""
    d = wrap360(a - b)
    return d - 360.0 if d > 180.0 else d


def gravity_body(accel_g, accel_convention: str = ACCEL_SPECIFIC_FORCE) -> np.ndarray:
    """Body-frame unit-free gravity direction (points down) from an accel reading."""
    a = np.asarray(accel_g, dtype=float).reshape(3)
    if accel_convention == ACCEL_SPECIFIC_FORCE:
        return -a
    if accel_convention == ACCEL_GRAVITY:
        return a
    raise ValueError(f"unknown accel_convention {accel_convention!r}")


def roll_pitch_from_accel(accel_g, accel_convention: str = ACCEL_SPECIFIC_FORCE) -> tuple[float, float]:
    """(roll_deg, pitch_deg) from a static accelerometer reading (g), NED body frame.

    g_b = (-sin th, sin ph cos th, cos ph cos th)  =>  ph = atan2(g_y, g_z), th = atan2(-g_x, hypot(g_y, g_z)).
    Roll in (-180, 180], pitch in [-90, 90]. Valid only when the vehicle is not accelerating.
    """
    gx, gy, gz = gravity_body(accel_g, accel_convention)
    if gx == 0.0 and gy == 0.0 and gz == 0.0:
        raise ValueError("zero accelerometer vector")
    roll = math.atan2(gy, gz)
    pitch = math.atan2(-gx, math.hypot(gy, gz))
    return math.degrees(roll), math.degrees(pitch)


def level_frame_field(mag_uT, roll_deg: float, pitch_deg: float) -> tuple[float, float, float]:
    """Rotate body field into the local level (heading-only) frame: returns (X_h, Y_h, Z_v).

    X_h = mx cos th + my sin ph sin th + mz cos ph sin th
    Y_h = my cos ph - mz sin ph
    Z_v = -mx sin th + my sin ph cos th + mz cos ph cos th     (vertical, + down)
    """
    mx, my, mz = np.asarray(mag_uT, dtype=float).reshape(3)
    ph, th = math.radians(roll_deg), math.radians(pitch_deg)
    sp, cp, st, ct = math.sin(ph), math.cos(ph), math.sin(th), math.cos(th)
    xh = mx * ct + my * sp * st + mz * cp * st
    yh = my * cp - mz * sp
    zv = -mx * st + my * sp * ct + mz * cp * ct
    return xh, yh, zv


def heading_from_level(xh: float, yh: float, declination_deg: float = 0.0) -> float:
    """psi = atan2(-Y_h, X_h) + declination, wrapped to [0, 360)."""
    return wrap360(math.degrees(math.atan2(-yh, xh)) + declination_deg)


def dip_deg(mag_uT, roll_deg: float, pitch_deg: float) -> float:
    """Magnetic inclination (dip) estimate, degrees, + = field points below horizon."""
    xh, yh, zv = level_frame_field(mag_uT, roll_deg, pitch_deg)
    return math.degrees(math.atan2(zv, math.hypot(xh, yh)))


def tilt_deg(roll_deg: float, pitch_deg: float) -> float:
    """Angle between body z axis and vertical: acos(cos ph cos th)."""
    c = math.cos(math.radians(roll_deg)) * math.cos(math.radians(pitch_deg))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def tilt_compensated_heading(mag_uT, accel_g, declination_deg=0.0,
                             accel_convention: str = ACCEL_SPECIFIC_FORCE) -> float:
    """Heading in degrees [0,360), clockwise from magnetic north (true north if declination given).

    mag_uT: calibrated body-frame field (uT). accel_g: accelerometer (g), or None for level assumption.
    declination_deg: east-positive magnetic declination D; true = magnetic + D.
    Raises ValueError if the horizontal field component is zero (heading undefined).
    """
    if accel_g is None:
        roll = pitch = 0.0
    else:
        roll, pitch = roll_pitch_from_accel(accel_g, accel_convention)
    xh, yh, _ = level_frame_field(mag_uT, roll, pitch)
    if xh == 0.0 and yh == 0.0:
        raise ValueError("horizontal field is zero; heading undefined")
    return heading_from_level(xh, yh, declination_deg)
