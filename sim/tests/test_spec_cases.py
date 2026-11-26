"""Sim vs T2 heading sensor spec (docs/math/sensor-spec, read-only): all 20 reference cases.

Every applicable key must PASS; the only allowed non-pass outcomes are the explicitly documented
N/A keys (formula/navigation quantities the sim does not model) and KNOWN_MISMATCH entries, which are
logged in TEAM_TRACKER.md (T3 row). Any new disagreement fails this test."""
import numpy as np
import pytest

from sim import spec_check
from sim import generate
from .helpers import arr

if not (spec_check.SPEC_DIR / "test_cases.json").exists():
    pytest.skip("docs/math/sensor-spec not present", allow_module_level=True)

ROWS, EXTRA = spec_check.evaluate()


def test_all_20_cases_covered():
    ids = {r[0] for r in ROWS}
    assert ids == {f"TC{i:02d}" for i in range(1, 21)}


@pytest.mark.parametrize("row", ROWS, ids=[f"{r[0]}-{r[1]}" for r in ROWS])
def test_spec_key(row):
    cid, key, status, val, exp, tol, note = row
    if status == "N/A":
        pytest.skip(f"{cid}.{key}: {note}")
    if status == "MISMATCH":
        assert f"{cid}.{key}" in spec_check.KNOWN_MISMATCH
        pytest.xfail(f"known, logged: {note}")
    assert status == "PASS", f"{cid}.{key}: sim {val} vs expected {exp} (tol {tol})"


@pytest.mark.parametrize("row", EXTRA, ids=[f"{r[0]}-{r[1][:40]}" for r in EXTRA])
def test_extra_sim_checks(row):
    assert row[2] == "PASS", row


def test_misalignment_antisymmetric_gives_constant_offset():
    """Spec 5.4/7.3: a pure rotation (antisymmetric part of M) is a constant heading offset."""
    from sim.tests.helpers import tilt_comp_heading, angdiff
    s = generate(scenario="yaw_spin", duration_s=20, rate_hz=5, misalignment_deg=[0, 0, 2.0],
                 mag_noise_scale=0, imu_noise_scale=0, imu_bias_scale=0)
    e = np.array([angdiff(tilt_comp_heading(x["mag_uT"], 0, 0), x["truth"]["heading_deg"]) for x in s])
    assert np.allclose(e, -2.0, atol=0.03)
    assert np.allclose(np.linalg.norm(arr(s, "mag_uT"), axis=1), 50.0, atol=0.02)   # magnitude unchanged


def test_gauss_markov_bias_statistics():
    s = generate(scenario="static", duration_s=4000, rate_hz=2, mag_bias_gm=[0.5, 20.0],
                 mag_noise_scale=0, seed=2)
    b = arr(s, "mag_uT") - arr(s, "truth", "earth_field_body_uT")
    assert 0.4 < b.std(axis=0).mean() < 0.6       # steady-state sigma 0.5 uT
    lag = int(20 * 2)  # one time constant
    r = np.mean([np.corrcoef(b[:-lag, k], b[lag:, k])[0, 1] for k in range(3)])
    assert 0.2 < r < 0.55   # theory exp(-1) = 0.37 (200 time constants of data)
