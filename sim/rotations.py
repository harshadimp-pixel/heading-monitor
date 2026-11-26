"""Rotation helpers. Frames: NED navigation frame (x north, y east, z down) and
body frame (x forward, y right, z down). Euler order ZYX (yaw, pitch, roll), aerospace convention."""
from __future__ import annotations
import numpy as np


def dcm_body_to_ned(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    """R such that v_ned = R @ v_body (ZYX Euler)."""
    phi, th, psi = np.radians([roll_deg, pitch_deg, yaw_deg])
    cphi, sphi = np.cos(phi), np.sin(phi)
    cth, sth = np.cos(th), np.sin(th)
    cpsi, spsi = np.cos(psi), np.sin(psi)
    return np.array([
        [cth * cpsi, sphi * sth * cpsi - cphi * spsi, cphi * sth * cpsi + sphi * spsi],
        [cth * spsi, sphi * sth * spsi + cphi * cpsi, cphi * sth * spsi - sphi * cpsi],
        [-sth, sphi * cth, cphi * cth],
    ])


def euler_rates_to_body_rates(roll_deg, pitch_deg, droll, dpitch, dyaw) -> np.ndarray:
    """Body angular rates (p, q, r) from Euler angles and their time derivatives (same angular unit)."""
    phi, th = np.radians(roll_deg), np.radians(pitch_deg)
    p = droll - dyaw * np.sin(th)
    q = dpitch * np.cos(phi) + dyaw * np.sin(phi) * np.cos(th)
    r = -dpitch * np.sin(phi) + dyaw * np.cos(phi) * np.cos(th)
    return np.array([p, q, r])


def wrap360(deg: float) -> float:
    d = float(deg) % 360.0
    return 0.0 if d >= 360.0 else d


def wrap180(deg: float) -> float:
    d = (float(deg) + 180.0) % 360.0 - 180.0
    return 180.0 if d == -180.0 else d
