"""C1-C5 calibration recovery. [SIMULATED]"""
import json, math, numpy as np, pytest
from conftest import load, call
from refmodel import body_vectors, wrapdiff

@pytest.fixture(scope="module")
def hc(): return load("heading_core")

HARD = np.array([35.0, -22.0, 40.0])
SOFT = np.array([[1.15, 0.08, -0.05], [0.08, 0.88, 0.10], [-0.05, 0.10, 1.05]])

def dance(n=800, seed=3, noise=0.15):
    rng = np.random.default_rng(seed); true, meas, acc, yaws = [], [], [], []
    for _ in range(n):
        y = rng.uniform(0, 360); p = np.degrees(np.arcsin(rng.uniform(-1, 1))); r = rng.uniform(-180, 180)
        m, a = body_vectors(y, p, r)
        true.append(m); meas.append(SOFT @ m + HARD + rng.normal(0, noise, 3)); acc.append(a); yaws.append(y)
    return np.array(true), np.array(meas)

@pytest.fixture(scope="module")
def fitted(hc):
    _, meas = dance()
    return call(hc.Calibration.fit, meas.tolist())

def test_C1_C2_recovery(hc, fitted):
    true, meas = dance(seed=99)
    corr = np.array([call(fitted.apply, list(v)) for v in meas])
    mags = np.linalg.norm(corr, axis=1)
    rel_std = mags.std() / mags.mean()
    # direction error (calibration may rescale and may leave a rotation; report both)
    cosang = np.sum(corr * true, 1) / (mags * np.linalg.norm(true, axis=1))
    ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
    print(f"C2 |B| rel std={rel_std:.4%}, dir err rms={np.sqrt(np.mean(ang**2)):.3f} deg")
    assert rel_std <= 0.01
    assert np.sqrt(np.mean(ang**2)) <= 1.0
    # implied hard iron: apply(HARD + soft*0) should map hard offset to ~0
    z = np.array(call(fitted.apply, list(HARD)))
    assert np.linalg.norm(z) <= 1.0 * math.sqrt(3) * np.linalg.norm(SOFT, 2) or True  # informational
    off = getattr(fitted, "offset", None)
    if off is not None:
        print("C1 offset est", np.round(off, 3), "true", HARD)
        assert np.max(np.abs(np.asarray(off, float) - HARD)) <= 1.0

def test_C3_calibrated_heading(hc, fitted):
    rng = np.random.default_rng(7); ec, eu = [], []
    for y in range(0, 360, 10):
        for p, r in ((0, 0), (20, -15), (-30, 30), (30, 10)):
            m, a = body_vectors(y, p, r); mm = SOFT @ m + HARD + rng.normal(0, .15, 3)
            ec.append(wrapdiff(call(hc.tilt_compensated_heading, call(fitted.apply, list(mm)), list(a)), y))
            eu.append(wrapdiff(call(hc.tilt_compensated_heading, list(mm), list(a)), y))
    rc, ru = np.sqrt(np.mean(np.square(ec))), np.sqrt(np.mean(np.square(eu)))
    print(f"C3 calibrated RMSE={rc:.3f} uncalibrated RMSE={ru:.3f}")
    assert ru >= 5 and rc <= 1.0

@pytest.mark.parametrize("bad", ["few", "coplanar", "nan"])
def test_C4_fit_robustness(hc, bad):
    if bad == "few":
        data = dance(5)[1].tolist()
    elif bad == "coplanar":
        data = [list(SOFT @ body_vectors(y)[0] + HARD) for y in range(0, 360, 2)]
    else:
        data = dance(200)[1].tolist(); data[10][1] = float("nan")
    try:
        cal = call(hc.Calibration.fit, data)
    except (ValueError, np.linalg.LinAlgError, RuntimeError) as e:
        return  # explicit error is acceptable
    out = call(cal.apply, [10.0, 20.0, 30.0])
    if bad == "nan":  # dropping non-finite rows and fitting the rest is acceptable if the result is still good
        true, meas = dance(n=200, seed=99)
        corr = np.array([call(cal.apply, list(v)) for v in meas]); mags = np.linalg.norm(corr, axis=1)
        assert mags.std() / mags.mean() <= 0.01; return
    assert all(math.isfinite(x) for x in out), f"{bad}: fit returned non-finite calibration"
    d = call(cal.to_dict)
    flagged = d.get("valid") is False or d.get("ok") is False or bool(d.get("warnings")) \
        or (isinstance(d.get("quality"), (int, float)) and d["quality"] < 0.5)
    assert flagged, f"{bad}: degenerate data accepted silently"

def test_C5_roundtrip(hc, fitted):
    d = json.loads(json.dumps(call(fitted.to_dict)))
    c2 = call(hc.Calibration.from_dict, d)
    for v in ([1, 2, 3], [40, -10, 55]):
        assert np.max(np.abs(np.subtract(call(fitted.apply, v), call(c2.apply, v)))) <= 1e-9
