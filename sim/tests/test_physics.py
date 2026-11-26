import math

import numpy as np
import pytest

from sim import SCENARIOS, generate
from .helpers import tilt_comp_heading, roll_pitch_from_specific_force, angdiff, arr


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_earth_field_magnitude_and_dip(scenario):
    s = generate(scenario=scenario, duration_s=10, field_total_uT=47.5, inclination_deg=-30.0)
    b = arr(s, "truth", "earth_field_body_uT")
    assert np.allclose(np.linalg.norm(b, axis=1), 47.5, atol=1e-4)
    # dip = angle between field and local horizontal plane, from body field + truth attitude
    for x in s[::25]:
        from sim.rotations import dcm_body_to_ned
        R = dcm_body_to_ned(x["truth"]["roll_deg"], x["truth"]["pitch_deg"], x["truth"]["true_heading_deg"])
        n = R @ np.array(x["truth"]["earth_field_body_uT"])
        assert math.degrees(math.atan2(n[2], math.hypot(n[0], n[1]))) == pytest.approx(-30.0, abs=1e-3)


@pytest.mark.parametrize("scenario", ["static", "yaw_spin", "tilted_spin", "high_noise"])
def test_measured_magnitude_clean_scenarios(scenario):
    s = generate(scenario=scenario, duration_s=20)
    mag = np.linalg.norm(arr(s, "mag_uT"), axis=1)
    tol = 0.2 if scenario != "high_noise" else 1.0
    assert abs(mag.mean() - 50.0) < tol


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
@pytest.mark.parametrize("decl", [0.0, 12.5, -7.0])
def test_truth_heading_consistent_with_truth_field(scenario, decl):
    s = generate(scenario=scenario, duration_s=20, rate_hz=10, declination_deg=decl, seed=2)
    for x in s:
        tr = x["truth"]
        if abs(abs(tr["pitch_deg"]) - 90) < 1:  # heading undefined at gimbal lock
            continue
        h = tilt_comp_heading(tr["earth_field_body_uT"], tr["roll_deg"], tr["pitch_deg"])
        assert abs(angdiff(h, tr["heading_deg"])) < 1e-3
        assert abs(angdiff(tr["true_heading_deg"] - decl, tr["heading_deg"])) < 1e-6
        assert 0 <= tr["heading_deg"] < 360


@pytest.mark.parametrize("scenario", ["static", "yaw_spin", "tilted_spin"])
def test_measured_heading_close_to_truth_without_interference(scenario):
    """mag + accel only (no truth attitude): error limited by accel bias & noise (ASSUMED values)."""
    s = generate(scenario=scenario, duration_s=20, seed=6)
    err = []
    for x in s:
        r, p = roll_pitch_from_specific_force(x["accel_g"])
        err.append(angdiff(tilt_comp_heading(x["mag_uT"], r, p), x["truth"]["heading_deg"]))
    err = np.abs(err)
    assert err.mean() < 2.0 and err.max() < 6.0


def test_accel_is_specific_force_and_gyro_matches_rates():
    s = generate(scenario="static", duration_s=5)
    assert np.allclose(arr(s, "accel_g").mean(axis=0), [0, 0, -1], atol=0.04)
    s = generate(scenario="yaw_spin", duration_s=20, seed=8)
    bias = np.array(s[0]["meta"]["sim_config"]["imu_bias_truth"]["gyro_dps"])
    g = arr(s, "gyro_dps").mean(axis=0) - bias
    assert np.allclose(g, [0, 0, 18.0], atol=0.02)
    # tilted: |accel| ~ 1 g; roll/pitch recovered from accel
    s = generate(scenario="tilted_spin", duration_s=5)
    a = arr(s, "accel_g")
    assert np.allclose(np.linalg.norm(a, axis=1), 1.0, atol=0.05)
    r, p = roll_pitch_from_specific_force(a.mean(axis=0))
    assert r == pytest.approx(20.0, abs=1.5) and p == pytest.approx(-15.0, abs=1.5)


def test_calibration_dance_sphere_coverage():
    s = generate(scenario="calibration_dance", duration_s=60)
    v = arr(s, "truth", "earth_field_body_uT")
    v /= np.linalg.norm(v, axis=1)[:, None]
    n = 50
    i = np.arange(n) + 0.5
    phi, th = np.arccos(1 - 2 * i / n), np.pi * (1 + 5 ** 0.5) * i
    bins = np.c_[np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)]
    cov = len(set(np.argmax(v @ bins.T, axis=1))) / n
    assert cov >= 0.8
    spin = arr(generate(scenario="yaw_spin", duration_s=60), "truth", "earth_field_body_uT")
    spin /= np.linalg.norm(spin, axis=1)[:, None]
    assert len(set(np.argmax(spin @ bins.T, axis=1))) / n < 0.3  # a flat spin is NOT good coverage
