"""Delivered output modes (Matek CAN-L4-3100 / AP_Periph): DroneCAN float16 Gauss and MSP int16 mG."""
import json
import subprocess
import sys

import numpy as np
import pytest

from sim import generate
from sim.delivery import (canard_float_to_float16, canard_float16_to_float, msp_encode_mG, dronecan_encode)
from .conftest import REPO
from .helpers import tilt_comp_heading, angdiff, arr

SCHEMA = json.loads((REPO / "contracts" / "sample.schema.json").read_text())


def test_float16_port_matches_ieee_except_ties():
    """libcanard's converter = IEEE round-to-nearest except exact ties (rounded away from zero)."""
    x = np.random.default_rng(0).uniform(-2, 2, 100000).astype(np.float32)
    mine = canard_float16_to_float(canard_float_to_float16(x))
    ref = x.astype(np.float16).astype(np.float32)
    d = mine != ref
    assert d.mean() < 1e-3
    # every disagreement is an exact tie, and libcanard picked the larger magnitude
    lo, hi = np.minimum(np.abs(mine[d]), np.abs(ref[d])), np.maximum(np.abs(mine[d]), np.abs(ref[d]))
    assert np.allclose(np.abs(x[d]), (lo + hi) / 2, rtol=0, atol=0)
    assert np.all(np.abs(mine[d]) == hi)


def test_float16_specials():
    bits = canard_float_to_float16(np.float32([0.0, -0.0, 65504.0, 1e6, np.inf, -np.inf, 0.25]))
    assert list(bits) == [0x0000, 0x8000, 0x7BFF, 0x7C00, 0x7C00, 0xFC00, 0x3400]


@pytest.mark.parametrize("gauss,step_uT", [(0.3, 2 ** -12 * 100), (0.15, 2 ** -13 * 100), (0.6, 2 ** -11 * 100)])
def test_float16_step_sizes(gauss, step_uT):
    """Earth-field magnitudes 0.25-0.5 G: 2^-12 G = 0.0244 uT step (T1 FACTSHEET: ~24 nT)."""
    x = np.float32(gauss)
    v = canard_float16_to_float(canard_float_to_float16(x))[0]
    nxt = canard_float16_to_float(canard_float_to_float16(np.float32(v) + np.float32(step_uT / 100 * 0.51)))[0]
    assert (nxt - v) * 100 == pytest.approx(step_uT)


def test_msp_truncates_toward_zero():
    w, ov = msp_encode_mG(np.float32([249.97, -249.97, 0.4, -0.4]))
    assert list(w) == [249, -249, 0, 0] and not ov
    w, ov = msp_encode_mG(np.float32([40000.0, 0, 0]))
    assert ov and w[0] == 32767


@pytest.mark.parametrize("mode", ["dronecan", "msp"])
def test_delivered_schema_and_fields(mode):
    jsonschema = pytest.importorskip("jsonschema")
    s = generate(scenario="motor_interference", duration_s=2, rate_hz=50, output_mode=mode)
    for x in s:
        jsonschema.validate(json.loads(json.dumps(x)), SCHEMA)
        assert "mag_raw" not in x and "rm3100_cycle_count" not in x
        assert x["meta"]["output_mode"] == mode
    m = arr(s, "mag_uT")
    if mode == "msp":
        assert np.allclose(m * 10, np.round(m * 10), atol=1e-9)
        assert all(np.allclose(np.array(x["meta"]["msp_mag_mG"]) / 10, x["mag_uT"]) for x in s)
    else:
        g = m / 100.0
        assert np.all(g.astype(np.float16).astype(np.float64) == g)        # exactly float16-representable
        for x in s:
            dec = canard_float16_to_float(np.array(x["meta"]["dronecan_float16_bits"], np.uint16)) * 100.0
            assert np.allclose(dec, x["mag_uT"], rtol=0, atol=1e-12)
    assert s[0]["meta"]["sim_config"]["delivery"]["publish_rate_hz"] == 25.0


@pytest.mark.parametrize("rate,fresh_frac", [(10, 1.0), (25, 1.0), (50, 0.5), (100, 0.25)])
def test_rate_limit_and_sample_and_hold(rate, fresh_frac):
    s = generate(scenario="yaw_spin", duration_s=10, rate_hz=rate, output_mode="dronecan")
    seq = [x["meta"]["mag_seq"] for x in s]
    assert all(b >= a for a, b in zip(seq, seq[1:]))
    assert len(set(seq)) == pytest.approx(min(rate, 25) * 10, abs=1)    # <= 25 distinct messages per second
    fresh = np.mean([x["meta"]["mag_fresh"] for x in s])
    assert fresh == pytest.approx(fresh_frac, abs=0.01)
    ages = arr(s, "meta", "mag_age_s")
    assert ages.min() >= 0 and ages.max() < 0.04 + 1e-9
    # held samples repeat the value exactly
    for a, b in zip(s, s[1:]):
        if not b["meta"]["mag_fresh"]:
            assert a["mag_uT"] == b["mag_uT"]


def test_averaging_window():
    s = generate(scenario="static", duration_s=5, rate_hz=25, output_mode="msp")
    n = [x["meta"]["mag_n_avg"] for x in s]
    assert n[0] == 1 and set(n[1:]) <= {3, 4}
    assert np.mean(n[1:]) == pytest.approx(80 / 25, abs=0.05)      # 80 Hz poll averaged into 25 Hz messages


@pytest.mark.parametrize("mode,tol", [("dronecan", 0.05), ("msp", 0.14)])  # + RM3100 LSB/2, noise
def test_static_delivered_close_to_field(mode, tol):
    s = generate(scenario="static", duration_s=5, rate_hz=25, output_mode=mode)
    err = arr(s, "mag_uT") - arr(s, "truth", "field_at_sensor_uT")
    assert np.abs(err).max() < tol
    if mode == "msp":   # truncation toward zero: delivered magnitude biased low
        f = arr(s, "truth", "field_at_sensor_uT")
        assert np.mean(np.abs(arr(s, "mag_uT")) - np.abs(f)) < -0.02


@pytest.mark.parametrize("mode", ["dronecan", "msp"])
def test_latency_explained_by_age_and_window(mode):
    """yaw_spin at 18 deg/s: heading from the held, averaged value lags truth by 18 * (t - window mid)."""
    s = generate(scenario="yaw_spin", duration_s=10, rate_hz=50, output_mode=mode)
    res = []
    for x in s[5:]:
        e = angdiff(tilt_comp_heading(x["mag_uT"], 0, 0), x["truth"]["heading_deg"])
        res.append(e + 18.0 * (x["t"] - x["meta"]["mag_sample_mid_s"]))
    res = np.array(res)
    assert abs(res.mean()) < 0.02 and np.abs(res).max() < (0.12 if mode == "dronecan" else 0.35)


def test_delivered_requires_cc200_and_cli(tmp_path):
    with pytest.raises(ValueError):
        generate(scenario="static", duration_s=0.1, output_mode="msp", cycle_count=100)
    r = subprocess.run([sys.executable, "-m", "sim", "--output-mode", "dronecan", "--rate", "50", "--duration", "0.2"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0 and "sample-and-hold" in r.stderr and len(r.stdout.strip().split("\n")) == 10
    r = subprocess.run([sys.executable, "-m", "sim", "--output-mode", "msp", "--cycle-count", "50"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 2


def test_raw_default_unchanged():
    a = generate(scenario="yaw_spin", duration_s=1, seed=3)
    b = generate(scenario="yaw_spin", duration_s=1, seed=3, output_mode="raw")
    assert a == b and "mag_raw" in a[0] and "output_mode" not in a[0]["meta"]["sim_config"]


def test_delivered_deterministic():
    a = generate(scenario="high_noise", duration_s=2, rate_hz=50, output_mode="dronecan", seed=4)
    b = generate(scenario="high_noise", duration_s=2, rate_hz=50, output_mode="dronecan", seed=4)
    assert a == b


def test_mag_quant_meta():
    """meta.mag_quant_uT (PM decision 2026-11-27) = delivered quantisation step."""
    m = generate(scenario="static", duration_s=1, rate_hz=25, output_mode="msp")
    assert all(x["meta"]["mag_quant_uT"] == 0.1 for x in m)
    d = generate(scenario="static", duration_s=1, rate_hz=25, output_mode="dronecan")
    # level static: largest component z = 43.3 uT = 0.433 G in [0.25, 0.5) -> 2^-12 G
    assert all(x["meta"]["mag_quant_uT"] == pytest.approx(2 ** -12 * 100) for x in d)
    r = generate(scenario="static", duration_s=0.1)
    assert "mag_quant_uT" not in r[0]["meta"]


def test_delivered_through_heading_core_no_stale_warnings():
    hc = pytest.importorskip("heading_core")
    for mode in ("dronecan", "msp"):
        s = generate(scenario="static", duration_s=20, rate_hz=50, output_mode=mode)
        est = hc.HeadingEstimator(calibration=hc.Calibration())
        outs = [est.update(x) for x in s]
        assert not any({"SENSOR_STALE", "MAG_STALE"} & set(o.get("warnings") or []) for o in outs)
