import subprocess
import sys

from sim import generate
from .conftest import REPO


def _run(*args):
    return subprocess.run([sys.executable, "-m", "sim", *args], cwd=REPO, capture_output=True,
                          check=True).stdout


def test_same_seed_identical_bytes():
    a = _run("--scenario", "high_noise", "--rate", "50", "--duration", "2", "--seed", "11")
    b = _run("--scenario", "high_noise", "--rate", "50", "--duration", "2", "--seed", "11")
    assert a == b and len(a) > 0


def test_different_seed_differs():
    a = generate(scenario="static", duration_s=1, seed=1)
    b = generate(scenario="static", duration_s=1, seed=2)
    assert [s["mag_raw"] for s in a] != [s["mag_raw"] for s in b]
    # truth does not depend on the seed
    assert [s["truth"] for s in a] == [s["truth"] for s in b]


def test_out_file_equals_stdout(tmp_path):
    out = tmp_path / "x.jsonl"
    stdout = _run("--scenario", "yaw_spin", "--duration", "1", "--seed", "5")
    _run("--scenario", "yaw_spin", "--duration", "1", "--seed", "5", "--out", str(out))
    assert out.read_bytes() == stdout


def test_prefix_stable_across_durations():
    """Samples don't depend on run length for scenarios whose trajectory is duration-independent."""
    a = generate(scenario="tilted_spin", duration_s=1, seed=9)
    b = generate(scenario="tilted_spin", duration_s=2, seed=9)
    strip = lambda s: {k: v for k, v in s.items() if k != "meta"}
    assert [strip(s) for s in a] == [strip(s) for s in b[:len(a)]]
