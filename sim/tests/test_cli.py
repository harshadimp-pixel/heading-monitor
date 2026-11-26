import json
import subprocess
import sys

from .conftest import REPO


def _run(*args):
    return subprocess.run([sys.executable, "-m", "sim", *args], cwd=REPO, capture_output=True, text=True)


def test_unknown_scenario_fails():
    r = _run("--scenario", "nope")
    assert r.returncode != 0


def test_describe_and_list():
    r = _run("--describe", "--scenario", "hard_iron", "--declination", "3.5", "--cycle-count", "100")
    d = json.loads(r.stdout)
    assert d["hard_iron_uT"] == [25.0, -15.0, 10.0] and d["declination_deg"] == 3.5
    assert d["rm3100"]["gain_lsb_per_uT"] == 38.0 and d["rm3100"]["provisional"] is False
    assert d["rm3100"]["label"] == "[DATASHEET]"
    d2 = json.loads(_run("--describe", "--cycle-count", "150").stdout)
    assert d2["rm3100"]["provisional"] is True and d2["rm3100"]["label"] == "[DERIVED-APPROX]"
    assert "calibration_dance" in _run("--list-scenarios").stdout


def test_rate_above_datasheet_max_warns():
    r = _run("--rate", "200", "--duration", "0.05", "--cycle-count", "200")
    assert r.returncode == 0 and "exceeds the datasheet max" in r.stderr
    assert len(r.stdout.strip().split("\n")) == 10


def test_overrides_reach_output():
    r = _run("--duration", "0.1", "--hard-iron", "1", "2", "3", "--soft-iron", "1", "0", "0", "0", "2", "0", "0", "0", "1",
             "--field-total", "40", "--inclination", "0", "--no-fc-attitude")
    first = json.loads(r.stdout.split("\n")[0])
    assert "fc_attitude_deg" not in first
    tr = first["truth"]
    assert abs(sum(v * v for v in tr["earth_field_body_uT"]) ** 0.5 - 40) < 1e-4
    exp = [tr["earth_field_body_uT"][0] + 1, 2 * tr["earth_field_body_uT"][1] + 2, tr["earth_field_body_uT"][2] + 3]
    assert all(abs(a - b) < 1e-5 for a, b in zip(tr["field_at_sensor_uT"], exp))
