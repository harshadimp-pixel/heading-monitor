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
