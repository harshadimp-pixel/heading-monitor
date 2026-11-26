import numpy as np
import pytest

from sim import generate
from .helpers import arr


def test_no_interference_in_clean_scenarios():
    for sc in ("static", "yaw_spin", "tilted_spin"):
        s = generate(scenario=sc, duration_s=5)
        assert np.allclose(arr(s, "truth", "interference_uT"), 0, atol=1e-6)


def test_hard_iron_is_constant_offset_and_shifts_centre():
    s = generate(scenario="hard_iron", duration_s=20)  # exactly one yaw revolution
    assert np.allclose(arr(s, "truth", "interference_uT"), [25, -15, 10], atol=1e-5)
    centre = arr(s, "mag_uT").mean(axis=0)
    clean = arr(generate(scenario="yaw_spin", duration_s=20), "mag_uT").mean(axis=0)
    assert np.allclose(centre - clean, [25, -15, 10], atol=0.05)


def test_soft_iron_matrix_applied():
    s = generate(scenario="soft_iron", duration_s=20)
    W = np.array(s[0]["meta"]["sim_config"]["soft_iron"])
    b = arr(s, "truth", "earth_field_body_uT")
    assert np.allclose(arr(s, "truth", "field_at_sensor_uT"), b @ W.T, atol=1e-5)
    # horizontal locus becomes an ellipse: x and y radii differ
    m = arr(s, "mag_uT")
    assert np.ptp(m[:, 0]) / np.ptp(m[:, 1]) == pytest.approx(1.15 / 0.88, rel=0.05)


def test_motor_interference_proportional_to_current():
    s = generate(scenario="motor_interference", duration_s=20)
    k = np.array(s[0]["meta"]["sim_config"]["motor_k_uT_per_A"])
    I = arr(s, "truth", "motor_current_A")
    intf = arr(s, "truth", "interference_uT")
    assert np.allclose(intf, I[:, None] * k[None, :], atol=1e-5)
    assert I.min() == 0 and I.max() >= 20
    assert np.all(I[: int(0.15 * len(I))] == 0)  # idle at start
    # field-magnitude anomaly only while current flows
    dmag = np.abs(np.linalg.norm(arr(s, "mag_uT"), axis=1) - 50.0)
    assert dmag[I == 0].max() < 0.2 and dmag[I >= 20].min() > 5.0
    # override coefficient via config
    s2 = generate(scenario="motor_interference", duration_s=20, motor_k_uT_per_A=[0, 0, 0])
    assert np.allclose(arr(s2, "truth", "interference_uT"), 0, atol=1e-6)


def test_high_noise_increases_scatter():
    def resid(sc):
        s = generate(scenario=sc, duration_s=10, seed=3)
        return np.std(arr(s, "mag_uT") - arr(s, "truth", "field_at_sensor_uT"), axis=0)
    # field_at_sensor includes the env noise draw, so compare measured vs noiseless earth field
    s_hi = generate(scenario="high_noise", duration_s=10, seed=3)
    s_lo = generate(scenario="yaw_spin", duration_s=10, seed=3)
    r_hi = np.std(arr(s_hi, "mag_uT") - arr(s_hi, "truth", "earth_field_body_uT"), axis=0)
    r_lo = np.std(arr(s_lo, "mag_uT") - arr(s_lo, "truth", "earth_field_body_uT"), axis=0)
    assert np.all(r_hi > 0.8) and np.all(r_lo < 0.05)
    g_hi = np.std(arr(s_hi, "accel_g"), axis=0)
    assert np.all(g_hi[:2] > 0.01)
    assert np.all(resid("high_noise") < 0.05)  # sensor noise itself unchanged (datasheet)
