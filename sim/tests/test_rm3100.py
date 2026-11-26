import numpy as np
import pytest

from sim import generate, gain_lsb_per_uT, noise_nT, max_3axis_rate_hz
from sim.rm3100 import RM3100Model, COUNTS_MAX, FIELD_RANGE_UT
from .helpers import arr


@pytest.mark.parametrize("cc,gain,noise", [(50, 20.0, 30.0), (100, 38.0, 20.0), (200, 75.0, 15.0)])
def test_datasheet_table_points(cc, gain, noise):
    assert gain_lsb_per_uT(cc) == gain
    assert noise_nT(cc) == noise


def test_matches_t1_factsheet():
    """Table values must agree with T1's docs/hardware/FACTSHEET.md (fails loudly if T1 changes them)."""
    from .conftest import REPO
    fs = REPO / "docs" / "hardware" / "FACTSHEET.md"
    if not fs.exists():
        pytest.skip("docs/hardware/FACTSHEET.md not present")
    txt = fs.read_text()
    assert "20 / 38 / 75 LSB/µT" in txt and "30 / 20 / 15 nT" in txt and "±800 µT" in txt
    assert "1600 / 850 / 440 Hz" in txt


def test_gain_monotonic_and_noise_decreasing():
    ccs = [10, 30, 50, 75, 100, 150, 200, 300, 400]
    g = [gain_lsb_per_uT(c) for c in ccs]
    n = [noise_nT(c) for c in ccs]
    assert all(b > a for a, b in zip(g, g[1:]))
    assert all(b < a for a, b in zip(n, n[1:]))
    assert max_3axis_rate_hz(200) == pytest.approx(440 / 3)
    assert max_3axis_rate_hz(50) > max_3axis_rate_hz(400)


def test_invalid_cycle_count():
    for bad in (0, -5, 70000, 1.5):
        with pytest.raises(ValueError):
            gain_lsb_per_uT(bad)


@pytest.mark.parametrize("cc", [50, 100, 200, 300])
def test_counts_consistent_with_uT(cc):
    s = generate(scenario="tilted_spin", duration_s=2, cycle_count=cc, seed=1)
    g = gain_lsb_per_uT(cc)
    raw, uT = arr(s, "mag_raw"), arr(s, "mag_uT")
    assert np.all(raw == np.round(raw))
    assert np.allclose(uT * g, raw, atol=1e-3)
    assert all(x["rm3100_cycle_count"] == cc for x in s)
    # counts scale with gain: same field, raw ratio ~ gain ratio
    s200 = generate(scenario="tilted_spin", duration_s=2, cycle_count=200, seed=1)
    ratio = np.abs(raw).sum() / np.abs(arr(s200, "mag_raw")).sum()
    assert ratio == pytest.approx(g / 75.0, rel=0.01)


@pytest.mark.parametrize("cc", [50, 100, 200])
def test_static_noise_matches_model(cc):
    s = generate(scenario="static", duration_s=60, rate_hz=50, cycle_count=cc, seed=4)
    sd = arr(s, "mag_uT").std(axis=0)
    q = 1.0 / gain_lsb_per_uT(cc)
    expected = np.sqrt((noise_nT(cc) * 1e-3) ** 2 + q * q / 12.0)  # white noise + quantisation
    assert np.allclose(sd, expected, rtol=0.25), (sd, expected)


def test_saturation_and_24bit_clip():
    rng = np.random.default_rng(0)
    m = RM3100Model(200)
    counts, uT, sat = m.measure([900.0, -2000.0, 10.0], rng)
    lim = int(np.floor(FIELD_RANGE_UT * 75))
    assert sat and counts[0] == lim and counts[1] == -lim and abs(counts[2] - 750) <= 2
    assert all(abs(c) <= COUNTS_MAX for c in counts)
    # very high cycle count: 24-bit register limit binds before the field range
    big = RM3100Model(65535)
    c2, _, sat2 = big.measure([800.0, 0, 0], rng)
    assert sat2 and c2[0] == COUNTS_MAX
    s = generate(scenario="static", duration_s=0.1, hard_iron_uT=[0, 0, 900.0])
    assert all(x["meta"].get("rm3100_saturated") for x in s)
