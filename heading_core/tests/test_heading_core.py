"""Unit tests for heading_core using synthetic vectors only ([SIMULATED] inputs)."""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from heading_core import (Calibration, CoreConfig, HeadingEstimator, angle_diff_deg,
                          roll_pitch_from_accel, tilt_compensated_heading, wrap360,
                          WARN_FIELD_MAGNITUDE, WARN_NOT_CALIBRATED, WARN_TILT_TOO_LARGE,
                          WARN_NO_ACCEL, WARN_DIP_ANOMALY, WARN_HIGH_NOISE)
from heading_core.config import ACCEL_GRAVITY
from heading_core.heading import dip_deg
from heading_core.synth import (body_accel, body_field, distort, random_orientations,
                                random_soft_iron)

REPO = Path(__file__).resolve().parents[2]
jsonschema = pytest.importorskip("jsonschema")
SCHEMA = json.loads((REPO / "contracts" / "heading_estimate.schema.json").read_text())
SAMPLE_SCHEMA = json.loads((REPO / "contracts" / "sample.schema.json").read_text())


def validate(est):
    jsonschema.validate(est, SCHEMA)


def sample(t, yaw, pitch=0.0, roll=0.0, dip=40.0, field=50.0, gyro=None, **kw):
    s = {"t": t, "source": "sim", "mag_uT": body_field(yaw, pitch, roll, field, dip).tolist(),
         "accel_g": body_accel(pitch, roll).tolist()}
    if gyro is not None:
        s["gyro_dps"] = list(gyro)
    s.update(kw)
    jsonschema.validate(s, SAMPLE_SCHEMA)
    return s


# ---------------------------------------------------------------- wrap helpers
@pytest.mark.parametrize("a,exp", [(0, 0), (360, 0), (-1, 359), (721, 1), (-360, 0), (-1e-15, 0.0)])
def test_wrap360(a, exp):
    w = wrap360(a)
    assert 0 <= w < 360 and w == pytest.approx(exp, abs=1e-9)


@pytest.mark.parametrize("a,b,exp", [(1, 359, 2), (359, 1, -2), (180, 0, 180), (90, 270, 180), (10, 10, 0)])
def test_angle_diff(a, b, exp):
    assert angle_diff_deg(a, b) == pytest.approx(exp)


# ---------------------------------------------------------- heading geometry
@pytest.mark.parametrize("yaw", [0, 90, 180, 270, 45, 359.5])
def test_cardinal_level(yaw):
    h = tilt_compensated_heading(body_field(yaw, 0, 0), [0, 0, -1])
    assert abs(angle_diff_deg(h, yaw)) < 1e-9


def test_level_known_vectors():
    # level, field north+down: x forward = north
    assert tilt_compensated_heading([30, 0, 40], [0, 0, -1]) == pytest.approx(0)
    # nose east: north lies to the left -> my < 0
    assert tilt_compensated_heading([0, -30, 40], [0, 0, -1]) == pytest.approx(90)
    assert tilt_compensated_heading([-30, 0, 40], [0, 0, -1]) == pytest.approx(180)
    assert tilt_compensated_heading([0, 30, 40], [0, 0, -1]) == pytest.approx(270)


@pytest.mark.parametrize("yaw,pitch,roll", [(30, 20, 0), (120, 0, -25), (250, -35, 40), (359, 10, 10),
                                            (0, 60, 0), (200, -5, 70)])
def test_tilted(yaw, pitch, roll):
    m, a = body_field(yaw, pitch, roll, dip_deg=60), body_accel(pitch, roll)
    r, p = roll_pitch_from_accel(a)
    assert r == pytest.approx(roll, abs=1e-9) and p == pytest.approx(pitch, abs=1e-9)
    assert abs(angle_diff_deg(tilt_compensated_heading(m, a), yaw)) < 1e-9
    assert dip_deg(m, r, p) == pytest.approx(60, abs=1e-9)


def test_tilt_uncompensated_error_is_large():
    # without tilt compensation a 30 deg roll at dip 60 gives a big error -> compensation matters
    m = body_field(45, 0, 30, dip_deg=60)  # level-assumed error ~ -65 deg
    assert abs(angle_diff_deg(tilt_compensated_heading(m, None), 45)) > 20
    assert abs(angle_diff_deg(tilt_compensated_heading(m, body_accel(0, 30)), 45)) < 1e-9


def test_gravity_convention():
    a = body_accel(15, -20, convention=ACCEL_GRAVITY)
    r, p = roll_pitch_from_accel(a, ACCEL_GRAVITY)
    assert (r, p) == pytest.approx((-20, 15))
    h = tilt_compensated_heading(body_field(77, 15, -20), a, accel_convention=ACCEL_GRAVITY)
    assert h == pytest.approx(77)


def test_declination():
    # true heading 100 with declination +5 E -> magnetic heading 95
    m = body_field(100, 0, 0, declination_deg=5.0)
    assert tilt_compensated_heading(m, [0, 0, -1]) == pytest.approx(95)
    assert tilt_compensated_heading(m, [0, 0, -1], declination_deg=5.0) == pytest.approx(100)
    assert tilt_compensated_heading(body_field(358, 0, 0, declination_deg=-3), [0, 0, -1],
                                    declination_deg=-3) == pytest.approx(358)


def test_zero_horizontal_raises():
    with pytest.raises(ValueError):
        tilt_compensated_heading([0, 0, 50], [0, 0, -1])


# ---------------------------------------------------------------- calibration
def _cal_dataset(seed=1, n=600, noise=0.015, hard=(12.0, -25.0, 8.0), sym=0.2):
    rng = np.random.default_rng(seed)
    yaw, pitch, roll = random_orientations(n, rng)
    B = np.array([body_field(y, p, r) for y, p, r in zip(yaw, pitch, roll)])
    A = random_soft_iron(rng, sym_amp=sym)
    M = distort(B, hard, A) + rng.normal(0, noise, B.shape)
    return B, M, np.array(hard), A


def test_ellipsoid_recovers_hard_and_soft_iron():
    B, M, o, A = _cal_dataset()
    cal = Calibration.fit(M.tolist())
    assert np.allclose(cal.offset, o, atol=0.05)
    W = np.array(cal.soft_iron)
    assert np.allclose(W, W.T) and np.linalg.det(W) == pytest.approx(1, abs=1e-9)
    # W A must be a scaled rotation (orthogonal up to the global scale det(A)^(1/3))
    WA = W @ A / np.cbrt(np.linalg.det(A))
    assert np.allclose(WA @ WA.T, np.eye(3), atol=2e-3)
    # A symmetric -> W A = s I exactly (no residual rotation)
    assert np.allclose(WA, np.eye(3), atol=2e-3)
    assert cal.field_uT == pytest.approx(50 * np.cbrt(np.linalg.det(A)), rel=1e-3)
    assert cal.residual_rms < 0.05
    assert cal.coverage > 0.9
    mags = np.linalg.norm(cal.apply_many(M), axis=1)
    assert np.std(mags) < 0.05


def test_calibrated_heading_error_small():
    rng = np.random.default_rng(7)
    _, M, o, A = _cal_dataset(seed=3)
    cal = Calibration.fit(M)
    errs_raw, errs_cal = [], []
    for _ in range(200):
        y, p, r = rng.uniform(0, 360), rng.uniform(-30, 30), rng.uniform(-30, 30)
        m = distort(body_field(y, p, r), o, A)
        a = body_accel(p, r)
        errs_raw.append(angle_diff_deg(tilt_compensated_heading(m, a), y))
        errs_cal.append(angle_diff_deg(tilt_compensated_heading(cal.apply(m), a), y))
    assert np.max(np.abs(errs_cal)) < 0.2
    assert np.max(np.abs(errs_raw)) > 10


def test_sphere_fit_hard_iron_only():
    rng = np.random.default_rng(5)
    yaw, pitch, roll = random_orientations(300, rng)
    B = np.array([body_field(y, p, r) for y, p, r in zip(yaw, pitch, roll)])
    cal = Calibration.fit(B + [5, 6, -7], method="sphere")
    assert np.allclose(cal.offset, [5, 6, -7], atol=1e-6)
    assert np.allclose(cal.soft_iron, np.eye(3))
    assert cal.field_uT == pytest.approx(50, rel=1e-6)


def test_fit_rejects_bad_input():
    with pytest.raises(ValueError):
        Calibration.fit([[1, 2, 3]] * 5)
    # yaw-only, level spin: points lie on a circle -> no ellipsoid
    M = [body_field(y, 0, 0).tolist() for y in range(0, 360, 5)]
    with pytest.raises(ValueError):
        Calibration.fit(M)
    with pytest.raises(ValueError):
        Calibration.fit(M, method="bogus")


def test_to_from_dict_roundtrip():
    _, M, _, _ = _cal_dataset(seed=11)
    cal = Calibration.fit(M)
    d = json.loads(json.dumps(cal.to_dict()))
    cal2 = Calibration.from_dict(d)
    assert cal2.to_dict() == cal.to_dict()
    v = [10.0, -3.0, 44.0]
    assert np.allclose(cal2.apply(v), cal.apply(v))
    with pytest.raises(ValueError):
        Calibration.from_dict({"version": 99})


def test_identity_calibration_apply():
    assert Calibration().apply([1, 2, 3]) == [1, 2, 3]
    assert Calibration(offset=[1, 1, 1]).apply([1, 2, 3]) == [0, 1, 2]


# ------------------------------------------------------------------ estimator
def test_estimate_schema_and_fields():
    est = HeadingEstimator(Calibration(field_uT=50.0)).update(sample(0.0, 123, 5, -5))
    validate(est)
    assert est["heading_deg"] == pytest.approx(123)
    assert est["calibrated"] is True and est["warnings"] == []
    assert est["field_uT"] == pytest.approx(50)
    assert est["quality"] > 0.95
    assert (est["roll_deg"], est["pitch_deg"]) == pytest.approx((-5, 5))


def test_not_calibrated_warning():
    est = HeadingEstimator().update(sample(0.0, 10))
    validate(est)
    assert WARN_NOT_CALIBRATED in est["warnings"] and est["calibrated"] is False
    assert est["quality"] <= 0.5


def test_field_magnitude_warning():
    est = HeadingEstimator(Calibration(field_uT=50.0)).update(sample(0.0, 10, field=70))
    validate(est)
    assert WARN_FIELD_MAGNITUDE in est["warnings"] and est["quality"] < 0.5
    # default expected field from config when calibration has no radius
    est2 = HeadingEstimator(Calibration(), config=CoreConfig(expected_field_uT=30)).update(sample(0, 10))
    assert WARN_FIELD_MAGNITUDE in est2["warnings"]


def test_tilt_warning():
    est = HeadingEstimator(Calibration(field_uT=50.0)).update(sample(0.0, 10, pitch=50))
    validate(est)
    assert WARN_TILT_TOO_LARGE in est["warnings"]
    assert est["heading_deg"] == pytest.approx(10)


def test_dip_warning():
    cfg = CoreConfig(expected_dip_deg=40.0)
    e = HeadingEstimator(Calibration(field_uT=50.0), config=cfg)
    assert WARN_DIP_ANOMALY not in e.update(sample(0.0, 10, dip=41))["warnings"]
    assert WARN_DIP_ANOMALY in e.update(sample(0.02, 10, dip=55))["warnings"]


def test_no_accel_uses_fc_attitude_or_level():
    s = sample(0.0, 200, 10, 20)
    del s["accel_g"]
    est = HeadingEstimator(Calibration(field_uT=50.0)).update(s)
    assert WARN_NO_ACCEL in est["warnings"]
    s["fc_attitude_deg"] = {"roll": 20.0, "pitch": 10.0, "yaw": 0.0}
    est = HeadingEstimator(Calibration(field_uT=50.0)).update(s)
    validate(est)
    assert WARN_NO_ACCEL not in est["warnings"] and est["heading_deg"] == pytest.approx(200)


@pytest.mark.parametrize("mode", ["complementary", "circular_mean"])
def test_wraparound_smoothing(mode):
    """Alternating 358/2 deg (and slowly drifting across north) must smooth to ~0, never ~180."""
    e = HeadingEstimator(Calibration(field_uT=50.0), config=CoreConfig(smoothing=mode, alpha=0.2))
    out = []
    for k in range(100):
        y = 358.0 if k % 2 else 2.0
        est = e.update(sample(k * 0.02, y))
        validate(est)
        out.append(est["heading_deg"])
    assert all(abs(angle_diff_deg(h, 0.0)) < 2.5 for h in out)
    assert abs(angle_diff_deg(out[-1], 0.0)) < 0.5


def test_smoothing_reduces_noise_and_tracks_rotation_with_gyro():
    rng = np.random.default_rng(2)
    rate, dt = 30.0, 0.02  # 30 deg/s yaw spin through north
    cal = Calibration(field_uT=50.0)
    ef = HeadingEstimator(cal, config=CoreConfig(alpha=0.05))
    raw_err, f_err = [], []
    for k in range(500):
        y = wrap360(300 + rate * k * dt)
        s = sample(k * dt, y, gyro=[0, 0, rate])
        s["mag_uT"] = (np.array(s["mag_uT"]) + rng.normal(0, 1.0, 3)).tolist()
        est = ef.update(s)
        if k > 100:
            raw_err.append(angle_diff_deg(est["heading_raw_deg"], y))
            f_err.append(angle_diff_deg(est["heading_deg"], y))
    rms = lambda x: float(np.sqrt(np.mean(np.square(x))))
    assert rms(f_err) < 0.5 * rms(raw_err)
    assert abs(np.mean(f_err)) < 0.3  # no lag bias thanks to gyro propagation


def test_noise_warning():
    rng = np.random.default_rng(4)
    e = HeadingEstimator(Calibration(field_uT=50.0))
    for k in range(40):
        s = sample(k * 0.02, 90)
        s["mag_uT"] = (np.array(s["mag_uT"]) + rng.normal(0, 8.0, 3)).tolist()
        est = e.update(s)
    assert WARN_HIGH_NOISE in est["warnings"]


def test_time_gap_resets_filter():
    e = HeadingEstimator(Calibration(field_uT=50.0), config=CoreConfig(alpha=0.01))
    e.update(sample(0.0, 0))
    est = e.update(sample(10.0, 180))  # gap > max_dt_s -> reset, take raw
    assert est["heading_deg"] == pytest.approx(180)


def test_zero_field_handled():
    e = HeadingEstimator(Calibration(field_uT=50.0))
    s = sample(0.0, 0)
    s["mag_uT"] = [0.0, 0.0, 0.0]
    est = e.update(s)
    validate(est)
    assert est["quality"] == 0 and WARN_FIELD_MAGNITUDE in est["warnings"]


def test_random_estimates_always_valid():
    rng = np.random.default_rng(9)
    e = HeadingEstimator()
    for k in range(300):
        s = {"t": k * 0.02, "source": "replay", "mag_uT": rng.normal(0, 60, 3).tolist(),
             "accel_g": rng.normal(0, 1, 3).tolist(), "gyro_dps": rng.normal(0, 100, 3).tolist()}
        validate(e.update(s))


@pytest.mark.parametrize("bad", [[float("nan"), 0, 40], [float("inf"), 1, 2], [0, 0, 0], [0, 0, 50]])
def test_invalid_mag_ignored_and_filter_not_corrupted(bad):
    from heading_core import WARN_INVALID_MAG
    e = HeadingEstimator(Calibration(field_uT=50.0))
    for k in range(20):
        e.update(sample(k * 0.02, 45))
    s = sample(0.4, 45)
    s["mag_uT"] = bad
    est = e.update(s)
    validate(est)
    assert WARN_INVALID_MAG in est["warnings"] and est["quality"] == 0
    assert est["heading_deg"] == pytest.approx(45)
    est = e.update(sample(0.42, 45))
    assert est["heading_deg"] == pytest.approx(45) and WARN_INVALID_MAG not in est["warnings"]


def test_nan_accel_falls_back():
    s = sample(0.0, 45)
    s["accel_g"] = [float("nan"), 0, -1]
    est = HeadingEstimator(Calibration(field_uT=50.0)).update(s)
    validate(est)
    assert WARN_NO_ACCEL in est["warnings"] and math.isfinite(est["heading_deg"])


def test_fit_drops_nonfinite_rows():
    _, M, o, _ = _cal_dataset(seed=21)
    M = M.copy()
    M[3, 1] = np.nan
    cal = Calibration.fit(M)
    assert cal.n_samples == len(M) - 1 and np.allclose(cal.offset, o, atol=0.05)


def test_filter_is_wrap_invariant():
    def run(start):
        e = HeadingEstimator(Calibration(field_uT=50.0))
        return [angle_diff_deg(e.update(sample(k * 0.02, wrap360(start + 0.5 * k)))["heading_deg"],
                               wrap360(start + 0.5 * k)) for k in range(80)]
    assert np.allclose(run(350), run(170), atol=1e-6)


def test_d1_frozen_sensor_3s_flagged_and_recovers():
    """D1: 3 s of bit-identical samples (mag + accel) at 50 Hz must warn and drop quality; then recover."""
    from heading_core import WARN_SENSOR_STALE
    e = HeadingEstimator(Calibration(field_uT=50.0))
    s0 = sample(0.0, 45)
    outs = [e.update(dict(s0, t=k * 0.02)) for k in range(150)]   # 3 s frozen
    for o in outs:
        validate(o)
    assert WARN_SENSOR_STALE not in outs[10]["warnings"] and outs[10]["quality"] > 0.9  # < 0.5 s: not yet
    first = next(k for k, o in enumerate(outs) if WARN_SENSOR_STALE in o["warnings"])
    assert first * 0.02 == pytest.approx(0.5, abs=0.021)          # flagged at stale_window_s
    assert all(WARN_SENSOR_STALE in o["warnings"] and o["quality"] <= 0.05 for o in outs[first:])
    # live data again (tiny noise, like a real RM3100) -> warning clears and quality recovers at once
    rng = np.random.default_rng(0)
    rec = []
    for k in range(150, 200):
        s = sample(k * 0.02, 45)
        s["mag_uT"] = (np.array(s["mag_uT"]) + rng.normal(0, 0.015, 3)).tolist()
        s["accel_g"] = (np.array(s["accel_g"]) + rng.normal(0, 0.003, 3)).tolist()
        rec.append(e.update(s))
    assert WARN_SENSOR_STALE not in rec[0]["warnings"] and rec[0]["quality"] > 0.9
    assert all(WARN_SENSOR_STALE not in o["warnings"] for o in rec)
    assert abs(angle_diff_deg(rec[-1]["heading_deg"], 45)) < 0.5


def test_frozen_mag_only_and_mag_without_accel():
    from heading_core import WARN_MAG_STALE, WARN_SENSOR_STALE
    rng = np.random.default_rng(1)
    e = HeadingEstimator(Calibration(field_uT=50.0))
    s0 = sample(0.0, 45)
    for k in range(60):  # mag frozen, accel live -> MAG_STALE (milder drop)
        s = dict(s0, t=k * 0.02, accel_g=(np.array(s0["accel_g"]) + rng.normal(0, 0.003, 3)).tolist())
        o = e.update(s)
    assert WARN_MAG_STALE in o["warnings"] and WARN_SENSOR_STALE not in o["warnings"] and o["quality"] <= 0.3
    e2 = HeadingEstimator(Calibration(field_uT=50.0))
    s1 = {k: v for k, v in s0.items() if k != "accel_g"}
    for k in range(60):  # no accel channel: frozen mag alone is a frozen sensor
        o = e2.update(dict(s1, t=k * 0.02))
    assert WARN_SENSOR_STALE in o["warnings"]


def test_near_identical_tolerance_and_disable():
    from heading_core import WARN_SENSOR_STALE
    e = HeadingEstimator(Calibration(field_uT=50.0))
    s0 = sample(0.0, 45)
    for k in range(60):  # 1e-9 uT jitter is "near-identical" -> still frozen
        o = e.update(dict(s0, t=k * 0.02, mag_uT=(np.array(s0["mag_uT"]) + 1e-9 * (k % 2)).tolist()))
    assert WARN_SENSOR_STALE in o["warnings"]
    off = HeadingEstimator(Calibration(field_uT=50.0), config=CoreConfig(stale_detection=False))
    assert all(WARN_SENSOR_STALE not in off.update(dict(s0, t=k * 0.02))["warnings"] for k in range(60))


def test_timestamp_stale_and_restart():
    from heading_core import WARN_TIMESTAMP_STALE
    e = HeadingEstimator(Calibration(field_uT=50.0))
    for k in range(20):
        e.update(sample(k * 0.02, 120))
    o = e.update(sample(0.38, 300))      # repeated timestamp: not used, held heading, low quality
    validate(o)
    assert WARN_TIMESTAMP_STALE in o["warnings"] and o["quality"] <= 0.05
    assert o["heading_deg"] == pytest.approx(120)
    o = e.update(sample(0.30, 300))      # small backwards step: stale too
    assert WARN_TIMESTAMP_STALE in o["warnings"]
    o = e.update(sample(0.40, 120))      # advances again -> recovers
    assert WARN_TIMESTAMP_STALE not in o["warnings"] and o["quality"] > 0.9
    for k in range(21, 100):
        e.update(sample(k * 0.02, 120))
    o = e.update(sample(0.0, 200))       # backwards jump > max_dt_s (1 s) = new stream: reset, not stale
    assert WARN_TIMESTAMP_STALE not in o["warnings"] and o["heading_deg"] == pytest.approx(200)


def test_accel_convention_matches_architecture():
    """ARCHITECTURE.md: specific force, level & at rest reads (0, 0, -1) g in NED body frame."""
    from heading_core.config import ACCEL_SPECIFIC_FORCE
    assert CoreConfig().accel_convention == ACCEL_SPECIFIC_FORCE
    assert np.allclose(body_accel(0, 0), [0, 0, -1])
    assert roll_pitch_from_accel([0, 0, -1]) == pytest.approx((0, 0))
    r, p = roll_pitch_from_accel(body_accel(10, 0))   # nose up 10 deg: x reads +sin(10) g
    assert p == pytest.approx(10) and body_accel(10, 0)[0] == pytest.approx(math.sin(math.radians(10)))
    # wrong sign (gravity convention fed as specific force) is made visible
    o = HeadingEstimator(Calibration(field_uT=50.0)).update(sample(0, 30, accel_g=[0, 0, 1]))
    assert WARN_TILT_TOO_LARGE in o["warnings"]


# ------------------------------------------------ quantised sources (PM decision 2026-11-27)
def _quant_stream(n, rate=50.0, q=0.1, mag_noise=0.0, accel_noise=0.002, seed=0, yaw=45.0, meta_first_only=True):
    rng = np.random.default_rng(seed)
    out = []
    for k in range(n):
        s = sample(k / rate, yaw)
        m = np.array(s["mag_uT"]) + rng.normal(0, mag_noise, 3)
        s["mag_uT"] = (np.round(m / q) * q).tolist()
        s["accel_g"] = (np.array(s["accel_g"]) + rng.normal(0, accel_noise, 3)).tolist()
        if k == 0 or not meta_first_only:
            s["meta"] = {"mag_quant_uT": q}
        jsonschema.validate(s, SAMPLE_SCHEMA)
        out.append(s)
    return out


def test_quantised_nogyro_fallback_5s_warning_only():
    """D3 (c): no gyro -> MAG_STALE after 5 s bit-identical, warning only (quality not cut)."""
    from heading_core import WARN_MAG_STALE, WARN_SENSOR_STALE, ALL_WARNINGS
    e = HeadingEstimator(Calibration(field_uT=50.0))
    ref = HeadingEstimator(Calibration(field_uT=50.0), config=CoreConfig(stale_detection=False))
    stream = _quant_stream(300)                                # 6 s, bit-identical mag, live accel
    outs = [e.update(s) for s in stream]
    refs = [ref.update(s) for s in stream]                     # same data, never flagged
    assert e.last_debug["quantised_mode"] is True
    for o in outs:
        validate(o)
        assert set(o["warnings"]) <= set(ALL_WARNINGS) and WARN_SENSOR_STALE not in o["warnings"]
    first = next(k for k, o in enumerate(outs) if WARN_MAG_STALE in o["warnings"])
    assert first / 50.0 == pytest.approx(5.0, abs=0.021)      # not before 5 s
    assert all(WARN_MAG_STALE not in o["warnings"] for o in outs[:first])
    assert all(o["quality"] == pytest.approx(r["quality"]) for o, r in zip(outs[:first], refs[:first]))
    assert all(o["quality"] == pytest.approx(r["quality"]) for o, r in zip(outs[first:], refs[first:]))
    assert all(WARN_MAG_STALE in o["warnings"] for o in outs[first:])
    assert abs(angle_diff_deg(outs[-1]["heading_deg"], 45)) < 0.5


def test_quantised_varying_stream_never_stale():
    from heading_core import WARN_MAG_STALE, WARN_SENSOR_STALE
    e = HeadingEstimator(Calibration(field_uT=50.0))
    outs = [e.update(s) for s in _quant_stream(600, mag_noise=0.06, seed=3)]   # 12 s, 0.1 uT steps flip
    assert not any(WARN_MAG_STALE in o["warnings"] or WARN_SENSOR_STALE in o["warnings"] for o in outs)
    # slowly turning vehicle, quantised, meta on every line
    e2 = HeadingEstimator(Calibration(field_uT=50.0))
    for k in range(500):
        s = sample(k * 0.02, wrap360(10 + 2.0 * k * 0.02), meta={"mag_quant_uT": 0.1})
        s["mag_uT"] = (np.round(np.array(s["mag_uT"]) / 0.1) * 0.1).tolist()
        o = e2.update(s)
        assert WARN_MAG_STALE not in o["warnings"]


def test_quantised_mode_threshold_override_and_sensor_stale_unchanged():
    from heading_core import WARN_MAG_STALE, WARN_SENSOR_STALE
    # quant 0.02 uT < 3 x 0.015 -> normal mode: MAG_STALE after 0.5 s as before
    e = HeadingEstimator(Calibration(field_uT=50.0))
    outs = [e.update(s) for s in _quant_stream(60, q=0.02)]
    assert e.last_debug["quantised_mode"] is False and WARN_MAG_STALE in outs[-1]["warnings"]
    # CoreConfig override without meta
    e = HeadingEstimator(Calibration(field_uT=50.0), config=CoreConfig(mag_quant_uT=0.1))
    s0 = _quant_stream(1)[0]
    s0.pop("meta")
    rng = np.random.default_rng(5)
    outs = [e.update(dict(s0, t=k * 0.02, accel_g=(np.array(s0["accel_g"]) + rng.normal(0, 0.002, 3)).tolist()))
            for k in range(100)]
    assert e.last_debug["quantised_mode"] is True and WARN_MAG_STALE not in outs[-1]["warnings"]
    # fully frozen (mag + accel) quantised data still gives SENSOR_STALE at 0.5 s with the sharp drop
    e = HeadingEstimator(Calibration(field_uT=50.0))
    s0 = _quant_stream(1)[0]
    outs = [e.update(dict(s0, t=k * 0.02)) for k in range(60)]
    assert WARN_SENSOR_STALE in outs[-1]["warnings"] and outs[-1]["quality"] <= 0.05


# --------------------------------------------------- single-calibration rule (fc_mag_calibrated)
@pytest.mark.parametrize("flag,factor", [(True, 0.7), (False, 1.0), ("unknown", 1.0), (None, 1.0)])
def test_fc_mag_calibrated_handling(flag, factor):
    from heading_core import ALL_WARNINGS
    B, M, o, A = _cal_dataset(seed=31)
    cal = Calibration.fit(M)
    ref = HeadingEstimator(cal)
    e = HeadingEstimator(cal)
    for k in range(5):
        s = sample(k * 0.02, 70, 5, -5)
        s["mag_uT"] = distort(np.array(s["mag_uT"]), o, A).tolist()
        r = ref.update(dict(s))
        if flag is not None and k == 0:
            s["meta"] = {"fc_mag_calibrated": flag}        # first line only: remembered per stream
        jsonschema.validate(s, SAMPLE_SCHEMA)
        out = e.update(s)
        validate(out)
        assert set(out["warnings"]) <= set(ALL_WARNINGS)  # no new codes
        assert out["warnings"] == r["warnings"]
        assert out["heading_deg"] == pytest.approx(r["heading_deg"])   # our calibration still applied
        assert out["quality"] == pytest.approx(factor * r["quality"])
    assert e.last_debug["fc_mag_calibrated"] == flag


def test_quant_inferred_without_meta():
    """No meta (e.g. older bridge): a 0.1 uT decimal grid is detected from the data itself."""
    from heading_core import WARN_MAG_STALE
    stream = _quant_stream(200)
    stream[0].pop("meta")
    e = HeadingEstimator(Calibration(field_uT=50.0))
    outs = [e.update(s) for s in stream]                      # 4 s bit-identical, live accel
    assert e.last_debug["mag_quant_inferred_uT"] == pytest.approx(0.1) and e.last_debug["quantised_mode"]
    assert not any(WARN_MAG_STALE in o["warnings"] for o in outs)
    # continuous (unquantised) data is never mistaken for a grid
    e2 = HeadingEstimator(Calibration(field_uT=50.0))
    rng = np.random.default_rng(8)
    for k in range(50):
        s = sample(k * 0.02, 45)
        s["mag_uT"] = (np.array(s["mag_uT"]) + rng.normal(0, 0.015, 3)).tolist()
        e2.update(s)
    assert e2.last_debug["mag_quant_inferred_uT"] is None and not e2.last_debug["quantised_mode"]


# ------------------------------------------------ D3: quantised mode needs motion evidence
def _session(seed, dur=60.0, rate=50.0, gyro_bias=0.2, gyro_noise=0.1, gyro_int=False, mag_noise=0.015,
             accel_noise=0.002, q=0.1, freeze_mag_after=None, yaw_rate=0.0, pitch=3.0, roll=-2.0):
    """Synthetic MSP-like session [SIMULATED]: mag on a q-uT grid, accel 1/512 g, gyro with per-session bias."""
    rng = np.random.default_rng(seed)
    yaw0 = rng.uniform(0, 360)
    bias = rng.uniform(-gyro_bias, gyro_bias, 3)
    frozen = None
    for k in range(int(dur * rate)):
        t = k / rate
        yaw = wrap360(yaw0 + yaw_rate * t)
        m = np.round((body_field(yaw, pitch, roll) + rng.normal(0, mag_noise, 3)) / q) * q
        if freeze_mag_after is not None and t >= freeze_mag_after:
            frozen = m if frozen is None else frozen
            m = frozen
        a = np.round((body_accel(pitch, roll) + rng.normal(0, accel_noise, 3)) * 512) / 512
        p_, r_ = math.radians(pitch), math.radians(roll)
        w = np.array([-math.sin(p_), math.sin(r_) * math.cos(p_), math.cos(r_) * math.cos(p_)]) * yaw_rate
        g = w + bias + rng.normal(0, gyro_noise, 3)
        if gyro_int:
            g = np.round(g)  # INAV MSP_RAW_IMU gyro is integer deg/s [SOURCE-CODE]
        yield {"t": t, "source": "replay", "mag_uT": [round(float(x), 6) for x in m], "accel_g": a.tolist(),
               "gyro_dps": g.tolist(), "meta": {"mag_quant_uT": q}}


@pytest.mark.parametrize("variant", [dict(), dict(gyro_bias=0.5), dict(gyro_bias=0.3, gyro_int=True),
                                     dict(rate=20.0)])
def test_d3_stationary_quantised_no_false_alarm_20x60s(variant):
    """D3 (a): 20 seeded stationary 60 s sessions, RM3100 15 nT [DATASHEET], 0.1 uT grid, gyro noise+bias."""
    from heading_core import WARN_MAG_STALE, WARN_SENSOR_STALE
    bad, max_theta, max_att, max_frozen = [], 0.0, 0.0, 0.0
    for seed in range(20):
        e = HeadingEstimator(Calibration(field_uT=50.0))
        n = 0
        for s in _session(seed, **variant):
            o = e.update(s)
            n += bool({WARN_MAG_STALE, WARN_SENSOR_STALE} & set(o["warnings"]))
            d = e.last_debug["quant_motion"]
            max_theta, max_att = max(max_theta, d["gyro_rot_deg"]), max(max_att, d["accel_att_change_deg"])
            max_frozen = max(max_frozen, d["frozen_s"])
        assert e.last_debug["quantised_mode"]
        if n:
            bad.append((seed, n))
    print(f"D3 {variant}: false-stale sessions {len(bad)}/20 {bad}; max gyro evidence {max_theta:.3f} deg, "
          f"max accel evidence {max_att:.3f} deg, longest bit-identical run {max_frozen:.1f} s")
    assert not bad


@pytest.mark.parametrize("yaw_rate", [30.0, 5.0])
def test_d3_rotating_with_frozen_mag_flags(yaw_rate):
    """D3 (b): vehicle turning (gyro + level-ish accel unchanged) while mag is stuck -> MAG_STALE, quality cut."""
    from heading_core import WARN_MAG_STALE
    e = HeadingEstimator(Calibration(field_uT=50.0))
    ref = HeadingEstimator(Calibration(field_uT=50.0), config=CoreConfig(stale_detection=False))
    first = None
    for s in _session(1, dur=10.0, yaw_rate=yaw_rate, freeze_mag_after=2.0):
        o, r = e.update(s), ref.update(dict(s))
        if s["t"] < 2.0:
            assert WARN_MAG_STALE not in o["warnings"]
        if first is None and WARN_MAG_STALE in o["warnings"]:
            first = s["t"]
            assert o["quality"] == pytest.approx(0.3 * r["quality"])
    assert first is not None
    # flags once (rate - 1 deg/s deadband) has accumulated 3 deg (+ low-pass rise)
    assert first - 2.0 < 3.0 / (yaw_rate - 1.0) + 1.5


def test_d3_tilting_without_gyro_flags_by_accel():
    """No gyro, mag stuck, vehicle pitches by 10 deg: accel attitude change is motion evidence (quality cut)."""
    from heading_core import WARN_MAG_STALE
    e = HeadingEstimator(Calibration(field_uT=50.0))
    rng = np.random.default_rng(4)
    m0 = None
    for k in range(150):
        t = k * 0.02
        pitch = 0.0 if t < 1.0 else min(10.0, (t - 1.0) * 10.0)
        s = sample(t, 45, pitch, 0)
        m0 = s["mag_uT"] if m0 is None else m0
        s["mag_uT"] = m0
        s["accel_g"] = (np.array(s["accel_g"]) + rng.normal(0, 0.002, 3)).tolist()  # live accel
        s["meta"] = {"mag_quant_uT": 0.1}
        o = e.update(s)
    assert WARN_MAG_STALE in o["warnings"] and o["quality"] < 0.5
    assert e.last_debug["quant_motion"]["accel_att_change_deg"] > 3.0


def test_d3_gyro_bias_does_not_accumulate():
    """0.2 deg/s/axis bias for 60 s would integrate to ~21 deg raw; the deadband keeps evidence at 0."""
    e = HeadingEstimator(Calibration(field_uT=50.0))
    s0 = next(_session(0, gyro_noise=0.0))
    for k in range(3000):
        o = e.update(dict(s0, t=k * 0.02, gyro_dps=[0.2, -0.2, 0.2],
                          accel_g=(np.array(s0["accel_g"]) + 0.002 * ((-1) ** k)).tolist()))
    assert e.last_debug["quant_motion"]["gyro_rot_deg"] == 0.0
    assert e.last_debug["quant_motion"]["frozen_s"] > 59 and "MAG_STALE" not in o["warnings"]
