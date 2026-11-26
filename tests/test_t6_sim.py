"""S1-S3, A1, R2: simulator contract, truth, repeatability, end-to-end accuracy. [SIMULATED]"""
import hashlib, json, os, subprocess, sys, numpy as np, pytest, jsonschema
from conftest import load, call, ROOT
from refmodel import wrapdiff

SCHEMA = json.load(open(os.path.join(ROOT, "contracts", "sample.schema.json")))
SCEN = ["static", "yaw_spin", "tilted_spin", "calibration_dance", "hard_iron", "soft_iron", "motor_interference", "high_noise"]

def sim(scen, seed=1, rate=50, dur=10, extra=()):
    if not os.path.isfile(os.path.join(ROOT, "sim", "__main__.py")):
        pytest.skip("NOT RUN (missing deliverable): sim/__main__.py")
    p = subprocess.run([sys.executable, "-m", "sim", "--rate", str(rate), "--duration", str(dur), "--scenario", scen, "--seed", str(seed), *extra],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr[-2000:]
    return p.stdout

@pytest.mark.parametrize("scen", SCEN)
def test_S1_contract(scen):
    out = sim(scen); lines = [l for l in out.splitlines() if l.strip()]
    assert abs(len(lines) - 500) <= 1, len(lines)
    ts = []
    for l in lines:
        s = json.loads(l); jsonschema.validate(s, SCHEMA); assert s["source"] == "sim"; ts.append(s["t"])
        assert "truth" in s and "heading_deg" in s["truth"]
    assert all(b > a for a, b in zip(ts, ts[1:])), "t not strictly monotonic"

@pytest.mark.parametrize("scen", ["static", "yaw_spin", "high_noise"])
def test_S3_seed_repeatability(scen):
    hs = {hashlib.sha256(sim(scen, 7).encode()).hexdigest() for _ in range(5)}
    assert len(hs) == 1
    if scen == "high_noise":
        assert hashlib.sha256(sim(scen, 8).encode()).hexdigest() not in hs

TARGET = {"static": .5, "yaw_spin": 1.5, "tilted_spin": 2.0, "hard_iron": 1.5, "soft_iron": 1.5, "high_noise": 3.0}

def e2e(scen, seed, hc):
    cal = None
    samples = [json.loads(l) for l in sim(scen, seed, dur=20).splitlines() if l.strip()]
    if scen in ("hard_iron", "soft_iron"):
        # Calibrate from a separate 3D calibration_dance carrying the SAME injected distortion (black-box, via CLI flags)
        cfg = samples[0]["meta"]["sim_config"]
        extra = ["--hard-iron", *map(str, cfg["hard_iron_uT"]), "--soft-iron", *[str(x) for row in cfg["soft_iron"] for x in row]]
        dance = [json.loads(l) for l in sim("calibration_dance", seed + 100, dur=40, extra=extra).splitlines() if l.strip()]
        cal = call(hc.Calibration.fit, [d["mag_uT"] for d in dance])
    est = hc.HeadingEstimator(calibration=cal)
    outs = [call(est.update, s) for s in samples]
    e = np.array([wrapdiff(o["heading_deg"], s["truth"]["heading_deg"]) for o, s in zip(outs, samples)][100:])
    return float(np.sqrt(np.mean(e ** 2))), outs

@pytest.mark.parametrize("scen", list(TARGET))
def test_A1_R2_accuracy(scen):
    hc = load("heading_core"); r = [e2e(scen, seed, hc)[0] for seed in (1, 2, 3, 4, 5)]
    print(f"A1 {scen}: RMSE mean={np.mean(r):.3f} std={np.std(r):.3f} min={min(r):.3f} max={max(r):.3f} (5 seeds)")
    assert np.mean(r) <= TARGET[scen] and np.std(r) <= 0.3

def test_A1_motor_interference_flagged():
    hc = load("heading_core"); rmse, outs = e2e("motor_interference", 1, hc)
    print(f"A1 motor_interference RMSE={rmse:.3f}")
    assert any(o.get("warnings") for o in outs)

@pytest.mark.parametrize("scen", ["static", "yaw_spin", "tilted_spin", "calibration_dance"])
def test_S2_truth_vs_refmodel(scen):
    from refmodel import body_vectors
    for l in sim(scen, 3, dur=5).splitlines()[::10]:
        s = json.loads(l); tr = s["truth"]; cfg_line = s
        m, _ = body_vectors(tr["heading_deg"], tr["pitch_deg"], tr["roll_deg"])
        assert np.max(np.abs(m - np.array(tr["earth_field_body_uT"]))) <= 0.05, (scen, s["t"], m, tr)
