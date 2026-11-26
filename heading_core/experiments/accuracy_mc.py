"""Monte Carlo heading-accuracy experiment. ALL RESULTS ARE [SIMULATED].

Run:  python -m heading_core.experiments.accuracy_mc [--trials 200] [--seed 2026] [--out docs/math]
Writes accuracy_results.md and accuracy_results.json. Parameters (PARAMS) are documented
assumptions, not measurements; see HEADING_MATH.md section 10.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import time
from pathlib import Path

import numpy as np

from heading_core import Calibration, CoreConfig, HeadingEstimator, angle_diff_deg, tilt_compensated_heading
from heading_core.synth import body_accel, body_field, distort, random_orientations, random_soft_iron

PARAMS = {
    "field_uT": 50.0,                 # nominal (placeholder, not site-specific)
    "dip_deg": 40.0,                  # assumed inclination
    "mag_noise_sensor_uT": 0.015,     # [DATASHEET] RM3100 noise @ CC=200 = 15 nT (taken as per-axis 1-sigma)
    "mag_lsb_uT": 1 / 75,             # [DATASHEET] gain 75 LSB/uT @ CC=200 -> quantisation applied
    "mag_noise_platform_uT": 0.3,     # ASSUMED extra per-axis white noise from motors/ESC/wiring (illustrative)
    "accel_noise_g": 0.003,           # ASSUMED per-axis white noise (typical MEMS FC IMU order of magnitude)
    "accel_bias_g": 0.005,            # ASSUMED residual per-axis bias 1-sigma after accel calibration
    "hard_iron_uT": 30.0,             # ASSUMED uniform +-30 uT per axis
    "soft_iron_sym": 0.10,            # ASSUMED symmetric perturbation, uniform +-0.10
    "soft_iron_skew": 0.02,           # ASSUMED skew part (only in the 'skew' case)
    "n_cal": 300,                     # calibration samples, uniformly random orientations
    "n_test": 500,                    # test samples per trial
    "tilt_max_deg": 30.0,             # test roll/pitch uniform in +-tilt_max
    "rate_hz": 50.0,
    "gyro_noise_dps": 0.05,           # ASSUMED gyro white noise per sample
    "gyro_bias_dps": 0.2,             # ASSUMED residual gyro bias 1-sigma
    "yaw_rate_dps": 30.0,             # rotating scenario
    "filter_alpha": 0.05,
    "circ_window": 25,
}


def _quant(m, lsb):
    return np.round(np.asarray(m) / lsb) * lsb


def _stats(err):
    e = np.abs(np.asarray(err, dtype=float))
    return {"rms_deg": float(np.sqrt(np.mean(e ** 2))), "p95_deg": float(np.percentile(e, 95)),
            "max_deg": float(e.max()), "n": int(e.size)}


def run(trials: int = 200, seed: int = 2026, P: dict = PARAMS) -> dict:
    rng = np.random.default_rng(seed)
    errs = {k: [] for k in ["no_tilt_comp_cal", "uncalibrated", "hard_iron_only", "ellipsoid", "ellipsoid_true_accel",
                            "ellipsoid_platform_noise", "ellipsoid_skew_soft_iron"]}
    smooth = {k: [] for k in ["static_raw", "static_complementary", "static_circular_mean",
                              "rot_raw", "rot_complementary_gyro", "rot_complementary_nogyro",
                              "rot_circular_mean"]}
    fit_stats = {"offset_err_uT": [], "residual_rms_uT": []}
    lsb = P["mag_lsb_uT"]
    for _ in range(trials):
        o = rng.uniform(-P["hard_iron_uT"], P["hard_iron_uT"], 3)
        A = random_soft_iron(rng, P["soft_iron_sym"])
        A_skew = random_soft_iron(rng, P["soft_iron_sym"], P["soft_iron_skew"])
        abias = rng.normal(0, P["accel_bias_g"], 3)

        def meas(b, A_, plat=False):
            n = P["mag_noise_sensor_uT"] + (P["mag_noise_platform_uT"] if plat else 0.0)
            return _quant(distort(b, o, A_) + rng.normal(0, n, np.shape(b)), lsb)

        # calibration datasets (random full-sphere orientations)
        y, p, r = random_orientations(P["n_cal"], rng)
        Bc = np.array([body_field(*a, P["field_uT"], P["dip_deg"]) for a in zip(y, p, r)])
        cal_e = Calibration.fit(meas(Bc, A))
        cal_s = Calibration.fit(meas(Bc, A), method="sphere")
        cal_p = Calibration.fit(meas(Bc, A, plat=True))
        cal_k = Calibration.fit(meas(Bc, A_skew))
        fit_stats["offset_err_uT"].append(float(np.linalg.norm(np.array(cal_e.offset) - o)))
        fit_stats["residual_rms_uT"].append(cal_e.residual_rms)

        # per-sample static accuracy over random headings / tilts
        yaw = rng.uniform(0, 360, P["n_test"])
        tm = P["tilt_max_deg"]
        pit, rol = rng.uniform(-tm, tm, P["n_test"]), rng.uniform(-tm, tm, P["n_test"])
        for yy, pp, rr in zip(yaw, pit, rol):
            b = body_field(yy, pp, rr, P["field_uT"], P["dip_deg"])
            a = body_accel(pp, rr) + abias + rng.normal(0, P["accel_noise_g"], 3)
            m = meas(b, A)
            errs["uncalibrated"].append(angle_diff_deg(tilt_compensated_heading(m, a), yy))
            errs["hard_iron_only"].append(angle_diff_deg(tilt_compensated_heading(cal_s.apply(m), a), yy))
            errs["ellipsoid"].append(angle_diff_deg(tilt_compensated_heading(cal_e.apply(m), a), yy))
            errs["ellipsoid_true_accel"].append(
                angle_diff_deg(tilt_compensated_heading(cal_e.apply(m), body_accel(pp, rr)), yy))
            errs["no_tilt_comp_cal"].append(angle_diff_deg(tilt_compensated_heading(cal_e.apply(m), None), yy))
            mp = meas(b, A, plat=True)
            errs["ellipsoid_platform_noise"].append(
                angle_diff_deg(tilt_compensated_heading(cal_p.apply(mp), a), yy))
            mk = meas(b, A_skew)
            errs["ellipsoid_skew_soft_iron"].append(
                angle_diff_deg(tilt_compensated_heading(cal_k.apply(mk), a), yy))

        # smoothing: static hold (10 s) and constant-rate yaw spin (10 s), platform noise on
        dt = 1.0 / P["rate_hz"]
        n = int(10 * P["rate_hz"])
        y0, p0, r0 = rng.uniform(0, 360), rng.uniform(-15, 15), rng.uniform(-15, 15)
        gbias = rng.normal(0, P["gyro_bias_dps"], 3)
        ests = {
            "complementary": HeadingEstimator(cal_p, config=CoreConfig(alpha=P["filter_alpha"])),
            "circular_mean": HeadingEstimator(cal_p, config=CoreConfig(smoothing="circular_mean",
                                                                         window=P["circ_window"])),
            "comp_nogyro": HeadingEstimator(cal_p, config=CoreConfig(alpha=P["filter_alpha"], use_gyro=False)),
        }
        for scen in ("static", "rot"):
            for e in ests.values():
                e.reset()
            rate = 0.0 if scen == "static" else P["yaw_rate_dps"]
            for k in range(n):
                yy = (y0 + rate * k * dt) % 360.0
                b = body_field(yy, p0, r0, P["field_uT"], P["dip_deg"])
                s = {"t": k * dt, "source": "sim",
                     "mag_uT": meas(b, A, plat=True).tolist(),
                     "accel_g": (body_accel(p0, r0) + abias + rng.normal(0, P["accel_noise_g"], 3)).tolist(),
                     # body rates for a pure yaw rotation at fixed roll/pitch (inverse Euler kinematics)
                     "gyro_dps": (np.array([-math.sin(math.radians(p0)) * rate,
                                            math.sin(math.radians(r0)) * math.cos(math.radians(p0)) * rate,
                                            math.cos(math.radians(r0)) * math.cos(math.radians(p0)) * rate])
                                  + gbias + rng.normal(0, P["gyro_noise_dps"], 3)).tolist()}
                oc = ests["complementary"].update(s)
                om = ests["circular_mean"].update(s)
                on = ests["comp_nogyro"].update(s)
                if k < 2 * P["rate_hz"]:  # 2 s warm-up excluded
                    continue
                smooth[f"{scen}_raw"].append(angle_diff_deg(oc["heading_raw_deg"], yy))
                key = "static_complementary" if scen == "static" else "rot_complementary_gyro"
                smooth[key].append(angle_diff_deg(oc["heading_deg"], yy))
                smooth[f"{scen}_circular_mean"].append(angle_diff_deg(om["heading_deg"], yy))
                if scen == "rot":
                    smooth["rot_complementary_nogyro"].append(angle_diff_deg(on["heading_deg"], yy))
    return {"tag": "[SIMULATED]", "params": P, "trials": trials, "seed": seed,
            "static_per_sample": {k: _stats(v) for k, v in errs.items()},
            "smoothing": {k: _stats(v) for k, v in smooth.items()},
            "fit": {"offset_err_uT_mean": float(np.mean(fit_stats["offset_err_uT"])),
                    "offset_err_uT_max": float(np.max(fit_stats["offset_err_uT"])),
                    "residual_rms_uT_mean": float(np.mean(fit_stats["residual_rms_uT"]))},
            "env": {"python": platform.python_version(), "numpy": np.__version__}}


LABELS = {
    "uncalibrated": "Raw (no calibration), tilt-compensated",
    "hard_iron_only": "Hard-iron only (sphere fit)",
    "ellipsoid": "Ellipsoid fit (hard + soft iron)",
    "ellipsoid_true_accel": "Ellipsoid fit, error-free accel (isolates mag + fit error)",
    "no_tilt_comp_cal": "Ellipsoid fit, NO tilt compensation (level assumed)",
    "ellipsoid_platform_noise": "Ellipsoid fit, + 0.3 uT platform noise",
    "ellipsoid_skew_soft_iron": "Ellipsoid fit, true soft iron has skew part (+-0.02)",
    "static_raw": "Static hold, per-sample (no smoothing)",
    "static_complementary": "Static hold, complementary filter (alpha 0.05, gyro)",
    "static_circular_mean": "Static hold, circular mean (25 samples)",
    "rot_raw": "30 deg/s yaw spin, per-sample (no smoothing)",
    "rot_complementary_gyro": "30 deg/s yaw spin, complementary + gyro",
    "rot_complementary_nogyro": "30 deg/s yaw spin, complementary, no gyro",
    "rot_circular_mean": "30 deg/s yaw spin, circular mean (25 samples)",
}


def to_markdown(res: dict) -> str:
    P = res["params"]
    L = ["# Heading accuracy Monte Carlo results [SIMULATED]", "",
         f"Generated by `python -m heading_core.experiments.accuracy_mc --trials {res['trials']} --seed {res['seed']}` "
         f"(python {res['env']['python']}, numpy {res['env']['numpy']}). Synthetic data only; no hardware involved.", "",
         "## Assumed parameters", "", "| Parameter | Value |", "|---|---|"]
    L += [f"| {k} | {v:.6g} |" if isinstance(v, float) else f"| {k} | {v} |" for k, v in P.items()]
    L += ["", "## A. Per-sample heading error, random heading, roll/pitch uniform +-30 deg [SIMULATED]", "",
          "| Case | RMS (deg) | P95 (deg) | Max (deg) | N |", "|---|---|---|---|---|"]
    for k, s in res["static_per_sample"].items():
        L.append(f"| {LABELS[k]} | {s['rms_deg']:.3f} | {s['p95_deg']:.3f} | {s['max_deg']:.3f} | {s['n']} |")
    L += ["", "## B. Smoothing (with 0.3 uT platform noise, ellipsoid calibration), 2 s warm-up excluded [SIMULATED]", "",
          "| Case | RMS (deg) | P95 (deg) | Max (deg) | N |", "|---|---|---|---|---|"]
    for k, s in res["smoothing"].items():
        L.append(f"| {LABELS[k]} | {s['rms_deg']:.3f} | {s['p95_deg']:.3f} | {s['max_deg']:.3f} | {s['n']} |")
    f = res["fit"]
    L += ["", f"Calibration fit: mean |offset error| {f['offset_err_uT_mean']:.4f} uT (max {f['offset_err_uT_max']:.4f}), "
          f"mean residual RMS {f['residual_rms_uT_mean']:.4f} uT [SIMULATED].", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "math"))
    a = ap.parse_args(argv)
    t0 = time.time()
    res = run(a.trials, a.seed)
    res["runtime_s"] = round(time.time() - t0, 1)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "accuracy_results.json").write_text(json.dumps(res, indent=2))
    (out / "accuracy_results.md").write_text(to_markdown(res))
    print(to_markdown(res))


if __name__ == "__main__":
    main()
