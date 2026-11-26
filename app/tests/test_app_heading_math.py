"""Heading maths used by the app's stub and UI display layer (not heading_core, which T2 tests)."""
import json
import math
import random
import shutil
import subprocess

import pytest

from app import _stubs as S
from ._helpers import ROOT


@pytest.mark.parametrize("deg,exp", [(0, 0), (360, 0), (-1, 359), (725, 5), (-360.5, 359.5), (359.999, 359.999)])
def test_wrap360(deg, exp):
    assert S.wrap360(deg) == pytest.approx(exp)
    assert 0 <= S.wrap360(deg) < 360


@pytest.mark.parametrize("a,b,exp", [(10, 350, 20), (350, 10, -20), (180, 0, 180), (0, 180, 180),
                                     (90, 90, 0), (1, 359, 2), (359, 1, -2), (270, 90, 180)])
def test_signed_deviation_wraps_to_pm180(a, b, exp):
    assert S.angle_diff_deg(a, b) == pytest.approx(exp)
    assert -180 < S.angle_diff_deg(a, b) <= 180


@pytest.mark.parametrize("h", [0, 30, 90, 135, 180, 225, 270, 359.5])
def test_level_heading_atan2(h):
    a = math.radians(h)
    bx, by = 30 * math.cos(a), -30 * math.sin(a)   # NED: By negative when pointing east
    assert S.angle_diff_deg(S.level_heading_deg([bx, by, 40]), h) == pytest.approx(0, abs=1e-9)


def test_cardinal_axes():
    assert S.level_heading_deg([30, 0, 40]) == pytest.approx(0)     # x along north
    assert S.level_heading_deg([0, -30, 40]) == pytest.approx(90)   # field toward -y -> pointing east
    assert S.level_heading_deg([-30, 0, 40]) == pytest.approx(180)
    assert S.level_heading_deg([0, 30, 40]) == pytest.approx(270)


def test_stub_tilt_compensation_matches_truth():
    sim = S.StubSim("tilted_spin", seed=1)
    sim.noise = 0.0
    sim.accel_noise = 0.0
    for t in [0.5 * i for i in range(60)]:
        s = sim.sample(t)
        s["mag_uT"] = [m - o for m, o in zip(s["mag_uT"], sim.hard_iron)]
        h = S.stub_tilt_compensated_heading(s["mag_uT"], s["accel_g"])
        assert abs(S.angle_diff_deg(h, s["truth"]["heading_deg"])) < 0.01  # only output rounding (4-5 decimals) remains


def test_stub_calibration_removes_hard_iron():
    rng = random.Random(3)
    off = [8, -5, 3]
    pts = []
    for _ in range(500):
        v = [rng.gauss(0, 1) for _ in range(3)]
        n = math.sqrt(sum(x * x for x in v))
        pts.append([50 * x / n + o for x, o in zip(v, off)])
    cal = S.StubCalibration.fit(pts)
    assert cal.offset == pytest.approx(off, abs=1.0)
    back = S.StubCalibration.from_dict(json.loads(json.dumps(cal.to_dict())))
    assert back.apply(pts[0]) == pytest.approx(cal.apply(pts[0]))


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_ui_display_math_in_js():
    js = f"""
    const m = require({json.dumps(ROOT + '/app/static/headingmath.js')});
    const out = {{
      wrap: [m.wrap360(-1), m.wrap360(360), m.wrap360(725)],
      diff: [m.angleDiff(10, 350), m.angleDiff(350, 10), m.angleDiff(180, 0), m.angleDiff(1, 359)],
      round: [m.roundHeading(359.96), m.roundHeading(359.94), m.roundHeading(-0.04)],
      level: [m.levelHeading(30, 0), m.levelHeading(0, -30), m.levelHeading(-30, 0), m.levelHeading(0, 30)],
      card: [m.cardinal(0), m.cardinal(359.9), m.cardinal(44), m.cardinal(91), m.cardinal(null)],
      badge: ["sim", "replay", "hardware", "x", undefined].map(m.badgeLabel)
    }};
    console.log(JSON.stringify(out));
    """
    r = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    assert r["wrap"] == [359, 0, 5]
    assert r["diff"] == [20, -20, 180, 2]
    assert r["round"] == [0, 359.9, 0]          # never displays 360.0
    assert [round(v, 9) for v in r["level"]] == [0, 90, 180, 270]
    assert r["card"] == ["N", "N", "NE", "E", ""]
    assert r["badge"] == ["SIMULATED", "REPLAY", "HARDWARE", None, None]
