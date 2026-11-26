"""Cross-check heading_core against the T3 simulator output (sim/). Results are [SIMULATED].

Run: python -m heading_core.experiments.sim_check
Calibrates on the sim 'calibration_dance' scenario and evaluates on other scenarios that share the same
hard/soft iron (passed explicitly on the sim CLI). Error is vs truth.heading_deg (magnetic heading).
"""
from __future__ import annotations

import json
import subprocess
import sys

import numpy as np

from heading_core import Calibration, HeadingEstimator, angle_diff_deg

HARD = ["18", "-12", "25"]
SOFT = ["1.08", "0.04", "-0.02", "0.04", "0.95", "0.03", "-0.02", "0.03", "1.02"]


def sim(scenario, duration, seed):
    cmd = [sys.executable, "-m", "sim", "--scenario", scenario, "--rate", "50", "--duration", str(duration),
           "--seed", str(seed), "--hard-iron", *HARD, "--soft-iron", *SOFT]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [json.loads(l) for l in out.splitlines() if l.strip()]


def main():
    cal = Calibration.fit([s["mag_uT"] for s in sim("calibration_dance", 60, 1)])
    print("calibration:", cal)
    rows = []
    for scen in ["static", "yaw_spin", "tilted_spin"]:
        S = sim(scen, 30, 2)
        for label, c in (("raw", None), ("calibrated", cal)):
            est = HeadingEstimator(c)
            e_raw, e_f = [], []
            for k, s in enumerate(S):
                o = est.update(s)
                if k < 100 or "truth" not in s:
                    continue
                e_raw.append(angle_diff_deg(o["heading_raw_deg"], s["truth"]["heading_deg"]))
                e_f.append(angle_diff_deg(o["heading_deg"], s["truth"]["heading_deg"]))
            rms = lambda x: float(np.sqrt(np.mean(np.square(x))))
            rows.append((scen, label, rms(e_raw), float(np.max(np.abs(e_raw))), rms(e_f), float(np.max(np.abs(e_f)))))
    print("| Scenario | Calibration | per-sample RMS | per-sample max | filtered RMS | filtered max |  [SIMULATED]")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r[0]} | {r[1]} | {r[2]:.3f} | {r[3]:.3f} | {r[4]:.3f} | {r[5]:.3f} |")


if __name__ == "__main__":
    main()
