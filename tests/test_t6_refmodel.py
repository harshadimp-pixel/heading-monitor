"""Self-check of T6 reference model with a textbook tilt-comp formula (Ozyagcioglu/AN4248 style)."""
import numpy as np
from refmodel import body_vectors, wrapdiff

def textbook(m, a):
    # roll/pitch from accel (NED, a = -g): level -> (0,0,-1)
    ax, ay, az = -np.asarray(a)
    roll = np.arctan2(ay, az); pitch = np.arctan2(-ax, np.hypot(ay, az))
    mx, my, mz = m
    xh = mx*np.cos(pitch) + my*np.sin(roll)*np.sin(pitch) + mz*np.cos(roll)*np.sin(pitch)
    yh = my*np.cos(roll) - mz*np.sin(roll)
    return np.degrees(np.arctan2(-yh, xh)) % 360

def test_refmodel_consistent():
    rng = np.random.default_rng(0)
    for _ in range(2000):
        y = rng.uniform(0, 360); p, r = rng.uniform(-60, 60, 2)
        m, a = body_vectors(y, p, r, incl_deg=rng.uniform(0, 80))
        assert abs(wrapdiff(textbook(m, a), y)) < 1e-6
