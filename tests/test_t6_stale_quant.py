"""E3b false-positive check (PM request 2026-11-27): stationary data quantised like MSP must NOT be called stale.

Inputs:
  * RM3100 noise 15 nT rms @ CC200 [DATASHEET] PNI RM3100 User Manual Table 3-1 (re-read by T6).
  * 0.05 uT rms variant [ASSUMED] (environment/electronics noise floor on a bench; no source).
  * MSP mag quantisation 0.1 uT (int16 mGauss) [SOURCE-CODE] per docs/firmware/FC_SETUP.md / firmware_bridge/scaling.py.
  * INAV MSP accel quantisation 1/512 g [SOURCE-CODE] (same), accel noise 0.002 g rms [ASSUMED] generic MEMS.
  * 20 Hz bridge poll rate (firmware_bridge default), 30 s stationary.
Frozen case (exactly identical samples) is covered by test_t6_estimator.py::test_E3_frozen_sensor and must keep failing-to-pass.
"""
import numpy as np, pytest
from conftest import load, call
from refmodel import body_vectors

STALE = {"SENSOR_STALE", "MAG_STALE"}

@pytest.fixture(scope="module")
def hc(): return load("heading_core")

def stream(sig_uT, with_meta, seed=11, rate=20.0, dur=30.0, yaw=37.0):
    rng = np.random.default_rng(seed); m, a = body_vectors(yaw, 3.0, -2.0)
    for i in range(int(rate * dur)):
        mm = np.round((m + rng.normal(0, sig_uT, 3)) / 0.1) * 0.1
        aa = np.round((a + rng.normal(0, 0.002, 3)) * 512) / 512
        s = {"t": i / rate, "source": "replay", "mag_uT": [round(float(x), 6) for x in mm], "accel_g": aa.tolist()}
        if with_meta: s["meta"] = {"mag_quant_uT": 0.1}
        yield s

@pytest.mark.parametrize("sig", [0.015, 0.05])
@pytest.mark.parametrize("with_meta", [True, False])
def test_E3b_quantised_stationary_not_stale(hc, sig, with_meta):
    est = hc.HeadingEstimator(calibration=hc.Calibration())
    outs = [call(est.update, s) for s in stream(sig, with_meta)]
    flagged = [i for i, o in enumerate(outs) if STALE & set(o.get("warnings") or [])]
    frac = len(flagged) / len(outs)
    qmin = min(o["quality"] for o in outs)
    print(f"E3b sigma={sig} meta={with_meta}: stale-flagged {len(flagged)}/{len(outs)} ({frac:.1%}), first at "
          f"{flagged[0]/20 if flagged else None} s, min quality {qmin:.3f}")
    assert not flagged, "stationary quantised sensor falsely reported stale"

def test_E3b_frozen_still_detected_with_quant_meta(hc):
    """Exactly identical samples must still raise a stale warning even when the source declares quantisation."""
    s0 = next(stream(0.015, True)); est = hc.HeadingEstimator(calibration=hc.Calibration())
    outs = [call(est.update, dict(s0, t=i / 20)) for i in range(600)]
    w = set(outs[-1].get("warnings") or [])
    print("E3b frozen+meta last warnings", w, "quality", outs[-1]["quality"])
    assert w & STALE

def test_E3b_stress_20_sessions_60s(hc):
    """20 independent stationary sessions (random yaw), 60 s @ 20 Hz, 15 nT [DATASHEET], 0.1 uT quantisation, meta set.
    A healthy stationary sensor must never be called stale."""
    bad = []
    for seed in range(20):
        rng = np.random.default_rng(seed); yaw = rng.uniform(0, 360); m, a = body_vectors(yaw, 3, -2)
        est = hc.HeadingEstimator(calibration=hc.Calibration()); n = 0
        for i in range(1200):
            mm = np.round((m + rng.normal(0, 0.015, 3)) / 0.1) * 0.1
            aa = np.round((a + rng.normal(0, 0.002, 3)) * 512) / 512
            o = call(est.update, {"t": i / 20, "source": "replay", "mag_uT": [round(float(x), 6) for x in mm],
                                  "accel_g": aa.tolist(), "meta": {"mag_quant_uT": 0.1}})
            n += bool(STALE & set(o.get("warnings") or []))
        if n: bad.append((seed, round(yaw, 1), n))
    print(f"E3b stress: {len(bad)}/20 sessions falsely stale (seed, yaw, flagged samples of 1200): {bad}")
    assert not bad

def test_E3c_frozen_mag_during_turn_detected_quantised(hc):
    """D3 fix check (PM decision 1befc7b): with meta.mag_quant_uT set, a mag that stays bit-identical while the gyro
    reports a 20 deg/s yaw turn for 3 s (60 deg, far above the 3 deg motion-evidence threshold) must raise MAG_STALE.
    [SIMULATED] T6 construction; gyro/accel channels keep changing (only the mag is frozen)."""
    rng = np.random.default_rng(3); m, a = body_vectors(37.0, 3, -2)
    m0 = (np.round(m / 0.1) * 0.1).tolist()
    est = hc.HeadingEstimator(calibration=hc.Calibration()); outs = []
    for i in range(80):  # 4 s @ 20 Hz
        aa = np.round((a + rng.normal(0, 0.002, 3)) * 512) / 512
        g = [float(rng.normal(0, 0.05)), float(rng.normal(0, 0.05)), 20.0 + float(rng.normal(0, 0.05))]
        outs.append(call(est.update, {"t": i / 20, "source": "replay", "mag_uT": m0, "accel_g": aa.tolist(),
                                      "gyro_dps": g, "meta": {"mag_quant_uT": 0.1}}))
    first = next((i for i, o in enumerate(outs) if "MAG_STALE" in (o.get("warnings") or [])), None)
    print("E3c frozen mag during 20 deg/s turn: first MAG_STALE at", None if first is None else first / 20, "s;",
          "last warnings", outs[-1].get("warnings"), "quality", round(outs[-1]["quality"], 3))
    assert first is not None and first / 20 <= 1.0

def test_E3d_residual_stationary_mag_freeze_is_documented_limitation(hc):
    """Observation (not a pass criterion on the product): bit-identical mag on a stationary platform with quantisation
    meta and live accel. After D3 this is NOT flagged by design (ARCHITECTURE.md 2026-11-27 PM D3, LIMITATIONS 14a).
    The test records the behaviour and only asserts the documented limitation text exists."""
    import pathlib
    rng = np.random.default_rng(4); m, a = body_vectors(37.0, 3, -2); m0 = (np.round(m / 0.1) * 0.1).tolist()
    est = hc.HeadingEstimator(calibration=hc.Calibration()); n = 0
    for i in range(1200):
        aa = np.round((a + rng.normal(0, 0.002, 3)) * 512) / 512
        o = call(est.update, {"t": i / 20, "source": "replay", "mag_uT": m0, "accel_g": aa.tolist(), "meta": {"mag_quant_uT": 0.1}})
        n += "MAG_STALE" in (o.get("warnings") or [])
    print(f"E3d stationary mag-only freeze 60 s, quantised meta: MAG_STALE on {n}/1200 samples (documented residual limitation)")
    root = pathlib.Path(__file__).resolve().parents[1]
    assert "14a" in (root / "docs/math/HEADING_MATH.md").read_text()

# ---- D3 regression guard (re-test of f31784a): frozen-sensor detection must not be lost (D1 must stay closed)
def _frozen(hc, gen, n=200):
    est = hc.HeadingEstimator(calibration=hc.Calibration()); outs = [call(est.update, gen(i)) for i in range(n)]
    first = next((i / 20 for i, o in enumerate(outs) if STALE & set(o.get("warnings") or [])), None)
    return first, outs[-1]

@pytest.mark.parametrize("meta", [True, False])
def test_E3e_mag_only_frozen_no_gyro_no_accel_flagged(hc, meta):
    m, _ = body_vectors(37.0, 3, -2); mq = (np.round(m / 0.1) * 0.1).tolist()
    first, last = _frozen(hc, lambda i: dict({"t": i / 20, "source": "replay", "mag_uT": mq}, **({"meta": {"mag_quant_uT": 0.1}} if meta else {})))
    print(f"E3e mag-only frozen (meta={meta}): first flag {first} s, warnings {last.get('warnings')}, quality {last['quality']:.3f}")
    assert first is not None and first <= 1.0 and last["quality"] < 0.2

def test_E3f_frozen_offgrid_mag_live_accel_no_gyro_flagged(hc):
    rng = np.random.default_rng(2); m, a = body_vectors(37.0, 3, -2); mf = [round(float(x) + 0.0123457, 7) for x in m]
    first, last = _frozen(hc, lambda i: {"t": i / 20, "source": "replay", "mag_uT": mf, "accel_g": (np.round((a + rng.normal(0, 0.002, 3)) * 512) / 512).tolist()})
    print(f"E3f frozen off-grid mag, live accel, no gyro: first flag {first} s, warnings {last.get('warnings')}")
    assert first is not None and first <= 1.0

def test_E3g_frozen_quantised_mag_tilt_change_no_gyro_flagged(hc):
    rng = np.random.default_rng(5); m, _ = body_vectors(37.0, 3, -2); mq = (np.round(m / 0.1) * 0.1).tolist()
    def g(i):
        _, aa = body_vectors(37.0, 3 + (10 * i / 100 if i < 100 else 10), -2)
        return {"t": i / 20, "source": "replay", "mag_uT": mq, "accel_g": (np.round((aa + rng.normal(0, 0.002, 3)) * 512) / 512).tolist(), "meta": {"mag_quant_uT": 0.1}}
    first, last = _frozen(hc, g)
    print(f"E3g frozen quantised mag, +10 deg pitch over 5 s, no gyro: first flag {first} s, warnings {last.get('warnings')}")
    assert first is not None and first <= 3.0
