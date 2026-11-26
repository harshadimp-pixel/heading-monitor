"""E1-E6 error handling, F1-F2 filter, K1 schema, R1 repeatability for HeadingEstimator. [SIMULATED]"""
import copy, json, math, os, numpy as np, pytest, jsonschema
from conftest import load, call, ROOT
from refmodel import body_vectors, wrapdiff

SCHEMA = json.load(open(os.path.join(ROOT, "contracts", "heading_estimate.schema.json")))
@pytest.fixture(scope="module")
def hc(): return load("heading_core")

def S(t, yaw, p=0, r=0, src="sim", **kw):
    m, a = body_vectors(yaw, p, r)
    s = {"t": t, "source": src, "mag_uT": m.tolist(), "accel_g": a.tolist()}; s.update(kw); return s

def run(hc, samples, **kw):
    est = hc.HeadingEstimator(**kw)
    return [call(est.update, s) for s in samples]

def valid(o): jsonschema.validate(o, SCHEMA); return True

def test_K1_schema_and_source_passthrough(hc):
    for src in ("sim", "replay", "hardware"):
        outs = run(hc, [S(i * .02, (i * 3) % 360, src=src) for i in range(200)])
        for o in outs:
            valid(o); assert o["source"] == src

def _ramp_err(hc, start):
    yaws = [(start + 0.5 * i) % 360 for i in range(80)] + [(start + 40 - 0.5 * i) % 360 for i in range(80)]
    outs = run(hc, [S(i * .02, y) for i, y in enumerate(yaws)])
    return np.array([wrapdiff(o["heading_deg"], y) for o, y in zip(outs, yaws)])

def test_F1_wraparound_smoothing(hc):
    """Filter must be wrap-invariant: a ramp across 0/360 must behave exactly like the same ramp across 180.
    (Absolute lag on a 25 deg/s ramp is a tuning property, reported not gated.)"""
    e0, e180 = _ramp_err(hc, 350), _ramp_err(hc, 170)
    print(f"F1 max err across 0/360={np.max(np.abs(e0)):.3f}, across 180={np.max(np.abs(e180)):.3f}, max diff={np.max(np.abs(e0-e180)):.2e}")
    assert np.max(np.abs(e0)) < 10, "smoothing passes through the wrong side of the circle"
    assert np.max(np.abs(e0 - e180)) <= 1e-6, "filter behaviour depends on where the wrap is"

def test_F2_step(hc):
    yaws = [10] * 50 + [100] * 250
    outs = run(hc, [S(i * .02, y) for i, y in enumerate(yaws)])
    e = [abs(wrapdiff(o["heading_deg"], y)) for o, y in zip(outs, yaws)]
    settle = next((i for i in range(50, 300) if all(x <= 1 for x in e[i:])), None)
    print(f"F2 settle samples after step: {None if settle is None else settle-50} (@50 Hz)")
    assert settle is not None

@pytest.mark.parametrize("bad", [[float("nan"), 0, 40], [float("inf"), 1, 2], [0, 0, 0]])
def test_E1_E3_bad_mag(hc, bad):
    seq = [S(i * .02, 45) for i in range(20)] + [dict(S(0.4, 45), mag_uT=bad)] + [S(0.42 + i * .02, 45) for i in range(20)]
    outs = []
    est = hc.HeadingEstimator()
    for s in seq:
        try:
            outs.append(call(est.update, s))
        except (ValueError, TypeError) as e:
            outs.append({"rejected": str(e)})
    o = outs[20]
    if "rejected" not in o:
        assert math.isfinite(o["heading_deg"]) and 0 <= o["heading_deg"] < 360
        assert o.get("warnings") or o.get("quality", 1) <= 0.2, f"bad mag {bad} not flagged: {o}"
    after = outs[-1]
    assert math.isfinite(after["heading_deg"]) and abs(wrapdiff(after["heading_deg"], 45)) <= 1, "filter corrupted by bad sample"

def test_E1_nan_accel(hc):
    s = S(0, 45); s["accel_g"] = [float("nan"), 0, -1]
    est = hc.HeadingEstimator()
    try: o = call(est.update, s)
    except (ValueError, TypeError): return
    assert math.isfinite(o["heading_deg"]) and (o.get("warnings") or o.get("quality", 1) <= 0.2)

@pytest.mark.parametrize("scale", [0.3, 2.0, 20.0])
def test_E2_field_out_of_range(hc, scale):
    s = S(0, 45); s["mag_uT"] = (np.array(s["mag_uT"]) * scale).tolist()
    o = call(hc.HeadingEstimator().update, s)
    assert o.get("warnings"), f"|B| x{scale} not flagged"

def test_E3_frozen_sensor(hc):
    s0 = S(0, 45); outs = run(hc, [dict(s0, t=i * .02) for i in range(150)])  # 3 s identical, zero noise
    print("E3 frozen-sensor last warnings:", outs[-1].get("warnings"), "quality", outs[-1].get("quality"))
    assert outs[-1].get("warnings") or outs[-1].get("quality", 1) < 1, "stuck/identical data never flagged (stale)"

def test_E4_time_anomalies(hc):
    ts = [i * .02 for i in range(50)] + [0.98, 0.5, 0.5] + [3.0 + i * .02 for i in range(50)]
    outs = []
    est = hc.HeadingEstimator()
    for i, t in enumerate(ts):
        try: outs.append(call(est.update, S(t, 120)))
        except ValueError: outs.append(None)
    assert outs[-1] and abs(wrapdiff(outs[-1]["heading_deg"], 120)) <= 1

def test_E5_interference_step(hc):
    samples = []
    for i in range(200):
        s = S(i * .02, 30)
        if i >= 100: s["mag_uT"] = (np.array(s["mag_uT"]) + [25, 0, 0]).tolist()
        samples.append(s)
    outs = run(hc, samples)
    first = next((i for i in range(100, 200) if outs[i].get("warnings")), None)
    print("E5 interference flagged at sample", first, "err after:", round(abs(wrapdiff(outs[-1]["heading_deg"], 30)), 2))
    assert first is not None and first - 100 <= 10  # <= 0.2 s at 50 Hz

def test_E6_missing_accel(hc):
    s = S(0, 77); del s["accel_g"]
    o = call(hc.HeadingEstimator().update, s)
    assert abs(wrapdiff(o["heading_deg"], 77)) <= 0.5 and o.get("warnings")

@pytest.mark.parametrize("mut", ["short", "str", "nosource"])
def test_E6_malformed(hc, mut):
    s = S(0, 10)
    if mut == "short": s["mag_uT"] = [1, 2]
    elif mut == "str": s["mag_uT"] = ["a", "b", "c"]
    else: del s["source"]
    est = hc.HeadingEstimator()
    try: o = call(est.update, s)
    except (ValueError, TypeError, KeyError): return
    valid(o)

def test_R1_repeatability(hc):
    rng = np.random.default_rng(5); seq = []
    for i in range(500):
        s = S(i * .02, (i * 0.7) % 360, 10 * math.sin(i / 30), 5)
        s["mag_uT"] = (np.array(s["mag_uT"]) + rng.normal(0, .3, 3)).tolist(); seq.append(s)
    runs = [[o["heading_deg"] for o in run(hc, copy.deepcopy(seq))] for _ in range(5)]
    spread = np.max(np.ptp(np.array(runs), axis=0))
    print("R1 max spread across 5 runs:", spread)
    assert spread == 0.0
