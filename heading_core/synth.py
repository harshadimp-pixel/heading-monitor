"""Synthetic reference model (forward model) used by tests and the accuracy experiment.

This is the inverse of heading.py and documents the forward equations for the Simulation
Developer (HEADING_MATH.md section 3). Nothing here is measured data.
"""
from __future__ import annotations

import math

import numpy as np

from .config import ACCEL_SPECIFIC_FORCE, NOMINAL_FIELD_UT


def rot_zyx(yaw_deg: float, pitch_deg: float, roll_deg: float) -> np.ndarray:
    """C_nb: body -> NED rotation for ZYX Euler angles (v_ned = C @ v_body)."""
    y, p, r = (math.radians(a) for a in (yaw_deg, pitch_deg, roll_deg))
    cy, sy, cp, sp, cr, sr = math.cos(y), math.sin(y), math.cos(p), math.sin(p), math.cos(r), math.sin(r)
    return np.array([
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ])


def earth_field_ned(field_uT: float = NOMINAL_FIELD_UT, dip_deg: float = 40.0,
                    declination_deg: float = 0.0) -> np.ndarray:
    """Earth field in NED (true-north) frame: B (cos I cos D, cos I sin D, sin I)."""
    I, D = math.radians(dip_deg), math.radians(declination_deg)
    return field_uT * np.array([math.cos(I) * math.cos(D), math.cos(I) * math.sin(D), math.sin(I)])


def body_field(yaw_deg, pitch_deg, roll_deg, field_uT=NOMINAL_FIELD_UT, dip_deg=40.0,
               declination_deg=0.0) -> np.ndarray:
    """True body-frame field for a vehicle at true heading yaw_deg. b = C_nb^T B_ned."""
    return rot_zyx(yaw_deg, pitch_deg, roll_deg).T @ earth_field_ned(field_uT, dip_deg, declination_deg)


def body_accel(pitch_deg, roll_deg, convention=ACCEL_SPECIFIC_FORCE) -> np.ndarray:
    """Static accelerometer reading (g). specific_force: f = -g_b; gravity: g_b."""
    g_b = rot_zyx(0.0, pitch_deg, roll_deg).T @ np.array([0.0, 0.0, 1.0])
    return -g_b if convention == ACCEL_SPECIFIC_FORCE else g_b


def distort(b, hard_iron, soft_iron) -> np.ndarray:
    """m = A b + o (applied row-wise for (N,3))."""
    b = np.asarray(b, dtype=float)
    return b @ np.asarray(soft_iron).T + np.asarray(hard_iron)


def random_orientations(n: int, rng: np.random.Generator):
    """Uniformly random rotations (via random unit quaternions), returned as (yaw,pitch,roll) deg."""
    q = rng.normal(size=(n, 4))
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    w, x, y, z = q.T
    roll = np.degrees(np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)))
    pitch = np.degrees(np.arcsin(np.clip(2 * (w * y - z * x), -1, 1)))
    yaw = np.degrees(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
    return yaw, pitch, roll


def random_soft_iron(rng: np.random.Generator, sym_amp=0.15, skew_amp=0.0) -> np.ndarray:
    """I + symmetric perturbation (uniform +-sym_amp) + optional skew (rotation-like) part."""
    S = rng.uniform(-sym_amp, sym_amp, size=(3, 3))
    S = 0.5 * (S + S.T)
    K = rng.uniform(-skew_amp, skew_amp, size=(3, 3)) if skew_amp else np.zeros((3, 3))
    K = 0.5 * (K - K.T)
    return np.eye(3) + S + K
