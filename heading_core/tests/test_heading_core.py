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
