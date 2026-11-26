"""Sanity tests for rm3100_quantization_sim.py (synthetic data only)."""
import numpy as np
import rm3100_quantization_sim as s


def test_counts_scaling():
    # 1 uT at CC200 -> 75 counts -> 10 mGauss
    v = s.path_values(np.array([1.0]))
    assert v["A_raw_counts"][0] == 10.0
    assert abs(v["B_ap_mgauss_f32"][0] - 10.0) < 1e-4


def test_inav_truncation_matches_shift():
    c = s.to_counts(np.array([50.0]))  # 3750 counts
    assert int(c[0]) == 3750
    assert int(c[0] >> 8) == 14       # INAV keeps only the top 16 of 24 bits


def test_float16_step():
    assert abs(float(np.spacing(np.float16(0.25))) - 2 ** -12) < 1e-12


def test_heading_identity():
    r = s.run(20.0, 40.0, noise=False, step=1.0)
    assert r["D_dronecan_hires_f32"]["max_abs_err_deg"] < 0.05
