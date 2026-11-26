import json
import subprocess
import sys
from pathlib import Path

import pytest

from sim import SCENARIOS, generate
from .conftest import REPO

SCHEMA = json.loads((REPO / "contracts" / "sample.schema.json").read_text())


def _basic_contract_check(s):
    """Dependency-free structural check (always runs, even without jsonschema)."""
    assert isinstance(s["t"], (int, float)) and s["source"] == "sim"
    for k in ("mag_uT", "accel_g", "gyro_dps"):
        assert len(s[k]) == 3 and all(isinstance(v, (int, float)) for v in s[k])
    assert len(s["mag_raw"]) == 3 and all(isinstance(v, int) for v in s["mag_raw"])
    assert isinstance(s["rm3100_cycle_count"], int)
    for k in ("heading_deg", "roll_deg", "pitch_deg"):
        assert isinstance(s["truth"][k], (int, float))
    assert isinstance(s["meta"], dict)


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_samples_validate_against_contract(scenario):
    samples = generate(scenario=scenario, duration_s=2.0, rate_hz=25, seed=3)
    assert len(samples) == 50
    for s in samples:
        _basic_contract_check(s)
    jsonschema = pytest.importorskip("jsonschema")
    v = jsonschema.Draft202012Validator(SCHEMA)
    for s in samples:
        errs = list(v.iter_errors(json.loads(json.dumps(s))))
        assert not errs, errs[0].message


def test_t_monotonic_and_rate():
    s = generate(scenario="yaw_spin", duration_s=3.0, rate_hz=50)
    t = [x["t"] for x in s]
    assert len(t) == 150 and all(b > a for a, b in zip(t, t[1:]))
    assert t[1] - t[0] == pytest.approx(0.02)


def test_cli_stdout_is_valid_jsonl():
    out = subprocess.run([sys.executable, "-m", "sim", "--rate", "50", "--duration", "1",
                          "--scenario", "tilted_spin", "--seed", "7"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    lines = out.strip().split("\n")
    assert len(lines) == 50
    jsonschema = pytest.importorskip("jsonschema")
    for ln in lines:
        jsonschema.validate(json.loads(ln), SCHEMA)


def test_example_logs_validate_and_are_reproducible(tmp_path):
    ex = sorted((REPO / "sim" / "examples").glob("*.jsonl"))
    assert ex, "sim/examples/*.jsonl missing"
    jsonschema = pytest.importorskip("jsonschema")
    for f in ex:
        lines = f.read_text().strip().split("\n")
        first = json.loads(lines[0])
        for ln in lines:
            jsonschema.validate(json.loads(ln), SCHEMA)
        cfg = first["meta"]["sim_config"]
        regen = tmp_path / f.name
        subprocess.run([sys.executable, "-m", "sim", "--scenario", cfg["scenario"], "--rate", str(cfg["rate_hz"]),
                        "--duration", str(cfg["duration_s"]), "--seed", str(cfg["seed"]),
                        "--cycle-count", str(cfg["cycle_count"]), "--output-mode", cfg.get("output_mode", "raw"),
                        "--out", str(regen)], cwd=REPO, check=True)
        assert regen.read_bytes() == f.read_bytes(), f"{f.name} not reproducible"
