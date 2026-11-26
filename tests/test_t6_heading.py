"""H1-H7: heading math vs T6 independent reference model. [SIMULATED]"""
import math, numpy as np, pytest
from conftest import load, call
from refmodel import body_vectors, wrapdiff

@pytest.fixture(scope="module")
def hc(): return load("heading_core")

def H(hc, m, a, d=0.0): return call(hc.tilt_compensated_heading, list(m), list(a), declination_deg=d)

def test_H1_level_sweep(hc):
    errs = []
    for yaw in range(360):
        m, a = body_vectors(yaw)
        errs.append(wrapdiff(H(hc, m, a), yaw))
    assert np.max(np.abs(errs)) <= 0.01

@pytest.mark.parametrize("yaw", [0, 90, 180, 270])
def test_H2_cardinals(hc, yaw):
    m, a = body_vectors(yaw)
    assert abs(wrapdiff(H(hc, m, a), yaw)) <= 0.01

def test_H2_east_is_90_clockwise(hc):
    # Body x pointing East: Earth north appears on body -y (left) -> heading 90
    assert abs(wrapdiff(H(hc, [0, -20, 40], [0, 0, -1]), 90)) <= 0.01

def test_H3_range(hc):
    rng = np.random.default_rng(1)
    for _ in range(10000):
        yaw = rng.uniform(0, 360); p, r = rng.uniform(-30, 30, 2)
        m, a = body_vectors(yaw, p, r)
        h = H(hc, m, a)
        assert 0.0 <= h < 360.0 and math.isfinite(h)
    for yaw in (359.9, 359.999, 0.0, 0.001):
        h = H(hc, *body_vectors(yaw)); assert 0.0 <= h < 360.0

def test_H4_tilt_noise_free(hc):
    worst = 0
    for incl in (20, 40, 60, 70):
        for yaw in range(0, 360, 15):
            for p in range(-30, 31, 5):
                for r in range(-30, 31, 5):
                    m, a = body_vectors(yaw, p, r, incl_deg=incl)
                    worst = max(worst, abs(wrapdiff(H(hc, m, a), yaw)))
    assert worst <= 0.1, f"max tilt err {worst}"

def test_H5_tilt_noisy(hc):
    rng = np.random.default_rng(42); e = []
    for yaw in range(0, 360, 15):
        for p in range(-30, 31, 10):
            for r in range(-30, 31, 10):
                m, a = body_vectors(yaw, p, r)
                e.append(wrapdiff(H(hc, m + rng.normal(0, .15, 3), a + rng.normal(0, .005, 3)), yaw))
    e = np.array(e); rmse = float(np.sqrt(np.mean(e**2)))
    print(f"H5 RMSE={rmse:.3f} max={np.max(np.abs(e)):.3f}")
    assert rmse <= 1.0 and np.max(np.abs(e)) <= 3.0

@pytest.mark.parametrize("d", [-30, -1.5, 0, 0.5, 15, 180])
def test_H6_declination(hc, d):
    for yaw in (0, 10, 359, 200):
        m, a = body_vectors(yaw)
        assert abs(wrapdiff(H(hc, m, a, d), yaw + d)) <= 0.01

def test_H6_decl_wrap(hc):
    h = H(hc, *body_vectors(359), d=2.0)
    assert abs(h - 1.0) <= 0.01

@pytest.mark.parametrize("m,a", [([0, 0, 50], [0, 0, -1]), ([0.0, 0.0, 0.0], [0, 0, -1]), ([20, 0, 40], [1, 0, 0])])
def test_H7_degenerate_no_crash(hc, m, a):
    try:
        h = call(hc.tilt_compensated_heading, m, a)
    except (ValueError, ZeroDivisionError, FloatingPointError, ArithmeticError):
        return  # documented explicit error acceptable
    assert h is None or (isinstance(h, float) and (math.isnan(h) or 0 <= h < 360)), h
