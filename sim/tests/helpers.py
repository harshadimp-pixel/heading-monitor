"""Test-only reference maths, written independently of the simulator internals."""
import math
import numpy as np


def tilt_comp_heading(mag, roll_deg, pitch_deg):
    """Standard tilt-compensated magnetic heading (NED body frame), degrees [0, 360)."""
    phi, th = math.radians(roll_deg), math.radians(pitch_deg)
    mx, my, mz = mag
    xh = mx * math.cos(th) + my * math.sin(phi) * math.sin(th) + mz * math.cos(phi) * math.sin(th)
    yh = my * math.cos(phi) - mz * math.sin(phi)
    return math.degrees(math.atan2(-yh, xh)) % 360.0


def roll_pitch_from_specific_force(f):
    fx, fy, fz = f
    roll = math.degrees(math.atan2(-fy, -fz))
    pitch = math.degrees(math.atan2(fx, math.hypot(fy, fz)))
    return roll, pitch


def angdiff(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def arr(samples, key, sub=None):
    if sub is None:
        return np.array([s[key] for s in samples], dtype=float)
    return np.array([s[key][sub] for s in samples], dtype=float)
