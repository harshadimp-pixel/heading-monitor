"""T6 independent reference model (NOT product code). NED body frame: x fwd, y right, z down.
ZYX Euler (yaw psi, pitch theta, roll phi). World frame NED: N, E, Down."""
import numpy as np

def earth_field(total_uT=50.0, incl_deg=60.0, decl_deg=0.0):
    """Field in NED *magnetic* frame rotated by declination into true-north NED."""
    i, d = np.radians(incl_deg), np.radians(decl_deg)
    h = total_uT * np.cos(i)
    return np.array([h * np.cos(d), h * np.sin(d), total_uT * np.sin(i)])

def R_body_from_world(yaw, pitch, roll):
    y, p, r = np.radians([yaw, pitch, roll])
    cy, sy, cp, sp, cr, sr = np.cos(y), np.sin(y), np.cos(p), np.sin(p), np.cos(r), np.sin(r)
    Rz = np.array([[cy, sy, 0], [-sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, -sp], [0, 1, 0], [sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, sr], [0, -sr, cr]])
    return Rx @ Ry @ Rz

def body_vectors(yaw, pitch=0.0, roll=0.0, total_uT=50.0, incl_deg=60.0):
    """Return (mag_uT body, accel_g body) for a stationary body. Magnetic north frame (decl 0).
    Accelerometer measures specific force = -gravity -> reads (0,0,-1) g when level in NED."""
    R = R_body_from_world(yaw, pitch, roll)
    m = R @ earth_field(total_uT, incl_deg)
    a = R @ np.array([0.0, 0.0, -1.0])
    return m, a

def wrapdiff(a, b):
    return (np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0
