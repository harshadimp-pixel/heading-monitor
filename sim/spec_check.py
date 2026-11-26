"""Check the simulator against T2's heading sensor spec (docs/math/sensor-spec/, commit 912476c).

For every case in test_cases.json, the simulator produces the magnetometer / accelerometer data from the case
inputs (fixed attitude via SimConfig.attitude_deg, noise, hard/soft iron, Earth field), and the spec's own
reference_model.py maths (heading, dip, ellipsoid fit, deviation curve) turns the sim output into the quantity
being checked. The spec files are only read, never modified.

Statuses per expected key:
  PASS      sim-derived value within the spec tolerance
  FAIL      sim-derived value outside tolerance (a genuine disagreement to log)
  MISMATCH  outside tolerance for an understood, documented reason (logged in TEAM_TRACKER.md)
  N/A       the key is a pure formula or navigation/geodesy quantity that the simulator does not model

Run:  python -m sim.spec_check            (table)      python -m sim.spec_check --json
"""
from __future__ import annotations
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

from .simulator import Simulator, SimConfig, generate
from .rotations import wrap180 as sim_wrap180
from .rm3100 import RM3100Model, gain_lsb_per_uT
from .earth import EarthField

REPO = Path(__file__).resolve().parents[1]
SPEC_DIR = REPO / "docs" / "math" / "sensor-spec"

# Keys the sim does not model: (case or "case.key") -> reason
NA = {
    "TC03.arith_mean_deg": "circular statistics are analysis maths, not part of the simulator",
    "TC03.circ_mean_deg": "circular statistics are analysis maths, not part of the simulator",
    "TC03.circ_mean_spread_deg": "circular statistics are analysis maths, not part of the simulator",
    "TC03.circ_std_spread_deg": "circular statistics are analysis maths, not part of the simulator",
    "TC05.error_first_order_deg": "first-order approximation formula; the sim generates exact fields",
    "TC06.first_order_at_45_deg": "first-order approximation formula; the sim generates exact fields",
    "TC08.B_axial_uT": "sim has no dipole source model (motor field is k*I, ASSUMED)",
    "TC08.B_equatorial_uT": "sim has no dipole source model",
    "TC08.B_wire_uT": "sim has no straight-wire source model",
    "TC08.dipole_at_0.6m_axial_uT": "sim has no dipole source model",
    "TC13.sigma_psi_deg": "analytic formula; sim Monte Carlo cross-check reported as extra row",
    "TC13.amplification": "analytic ratio",
    "TC13.wmm2025_sigma_D_deg": "WMM declination error model not in sim (uniform field model)",
    "TC14.first_order_tanI_deg": "first-order approximation formula",
    "TC19.quant_sigma_uT[1]": "0.15 uT LSB is a generic consumer part, not an RM3100 setting",
    "TC09": "navigation (wind/track) - sim has no position/velocity model",
    "TC10": "navigation (path geometry) - not modelled",
    "TC11": "geodesy (great circle / rhumb) - not modelled",
    "TC12": "dead reckoning - not modelled",
    "TC17": "WGS84 radii / dead reckoning - not modelled",
    "TC18": "dead-reckoning Monte Carlo - not modelled",
    "TC20": "grid convergence - not modelled",
}

# Understood disagreements: "case.key" -> explanation (also logged in TEAM_TRACKER.md, T3 row)
KNOWN_MISMATCH = {
    # (empty) TC19 resolved by T2 in 64579d9: spec LSB now exactly 1/75 uT, matching the sim.
}


def load_reference_model():
    spec = importlib.util.spec_from_file_location("t2_reference_model", SPEC_DIR / "reference_model.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_cases():
    return json.loads((SPEC_DIR / "test_cases.json").read_text())["cases"]


# ---------------------------------------------------------------- sim helpers
def _sim(F, I, D=0.0, yaw=0.0, pitch=0.0, roll=0.0, S=None, h=None, **kw):
    cfg = SimConfig(scenario="static", rate_hz=50, duration_s=0.02, field_total_uT=F, inclination_deg=I,
                    declination_deg=D, attitude_deg=[roll, pitch, yaw], hard_iron_uT=h,
                    soft_iron=None if S is None else np.asarray(S, float).tolist(),
                    mag_noise_scale=0.0, env_noise_uT=0.0, imu_noise_scale=0.0, imu_bias_scale=0.0, **kw)
    return Simulator(cfg)


def sim_fields(F, I, D=0.0, yaw=0.0, pitch=0.0, roll=0.0, S=None, h=None):
    """Unrounded (earth field in body, field at sensor) from the sim for a fixed attitude."""
    b_body, b_sensor, _ = _sim(F, I, D, yaw, pitch, roll, S, h).field_truth(0.0)
    return b_body, b_sensor


def sim_noisy_mag(F, I, yaw, n, env_noise=0.0, mag_noise_scale=0.0, seed=0, pitch=0.0, roll=0.0):
    """n emitted mag_uT samples (RM3100 path incl. quantisation) at a fixed attitude."""
    s = generate(scenario="static", rate_hz=50, duration_s=n / 50, field_total_uT=F, inclination_deg=I,
                 attitude_deg=[roll, pitch, yaw], env_noise_uT=env_noise, mag_noise_scale=mag_noise_scale,
                 imu_noise_scale=0.0, imu_bias_scale=0.0, seed=seed)
    return np.array([x["mag_uT"] for x in s]), s


# ---------------------------------------------------------------- per-case
def run_cases(rm):
    out, extras = {}, []

    def tc01(c):
        i = c["inputs"]
        hd = []
        for y in i["yaw_deg"]:
            sm = generate(scenario="static", rate_hz=50, duration_s=0.02, field_total_uT=i["F_uT"],
                          inclination_deg=i["I_deg"], attitude_deg=[i["roll_deg"], i["pitch_deg"], y],
                          mag_noise_scale=0.0, imu_noise_scale=0.0, imu_bias_scale=0.0)[0]
            b_body, _ = sim_fields(i["F_uT"], i["I_deg"], yaw=y)
            assert abs(rm.angle_diff(rm.heading_level(b_body), sm["truth"]["heading_deg"])) < 1e-9
            hd.append(sm["truth"]["heading_deg"])
            e = rm.angle_diff(rm.heading_level(sm["mag_uT"]), y)
            extras.append(("TC01", f"heading from emitted mag_uT (quantised), yaw {y}", float(e), 0.0, 0.05))
        return {"heading_deg": hd, "m_body_at_30_uT": sim_fields(i["F_uT"], i["I_deg"], yaw=30.0)[0].tolist()}

    def tc02(c):
        i = c["inputs"]
        true = []
        for psi_m, D in i["pairs_psi_m_D"]:
            sim = _sim(50.0, 60.0, D=D, yaw=psi_m + D)
            b_body, _, _ = sim.field_truth(0.0)
            # the field itself must give the magnetic heading psi_m (checks the sim's declination sign)
            assert abs(rm.angle_diff(rm.heading_level(b_body), psi_m)) < 1e-9
            tr = sim.sample(0)["truth"]
            assert abs(rm.angle_diff(tr["heading_deg"], psi_m)) < 1e-6
            true.append(tr["true_heading_deg"])
        # declination error passes straight through: actual D = 0, user assumes D_error
        sim = _sim(50.0, 60.0, D=0.0, yaw=i["psi_m_deg"])
        psi_m = rm.heading_level(sim.field_truth(0.0)[0])
        est_true = rm.magnetic_to_true(psi_m, i["D_error_deg"])
        err = float(rm.angle_diff(est_true, sim.sample(0)["truth"]["true_heading_deg"]))
        return {"true_deg": true, "true_heading_error_deg": err}

    def tc03(c):
        return {"angle_diff_deg": [sim_wrap180(a - b) for a, b in c["inputs"]["diff_a_b"]]}

    def tc04(c):
        i = c["inputs"]
        tc, unc, dip = [], [], []
        rp1 = None
        for k, (y, p, r) in enumerate(i["cases_yaw_pitch_roll_deg"]):
            sim = _sim(i["F_uT"], i["I_deg"], yaw=y, pitch=p, roll=r)
            b_body, _, _ = sim.field_truth(0.0)
            f = sim.specific_force_truth(0.0)
            tc.append(rm.heading_from_mag_accel(b_body, f))
            unc.append(rm.heading_level(b_body))
            rr, pp = rm.roll_pitch_from_accel(f)
            dip.append(rm.measured_dip_deg(b_body, rr, pp))
            if k == 0:
                rp1 = [rr, pp]
            # emitted (rounded) accel: within output precision
            em = sim.sample(0)
            e = rm.angle_diff(rm.heading_from_mag_accel(em["truth"]["earth_field_body_uT"], em["accel_g"]), y)
            extras.append(("TC04", f"tilt-comp heading from emitted JSON (6-dp rounding), case {k + 1}", float(e), 0.0, 1e-3))
        return {"tilt_comp_heading_deg": tc, "uncompensated_level_formula_deg": unc,
                "recovered_roll_pitch_case1_deg": rp1, "measured_dip_deg": dip}

    def tc05(c):
        i = c["inputs"]
        h = i["h_hard_uT"]

        def err(y):
            return float(rm.angle_diff(rm.heading_level(sim_fields(i["F_uT"], i["I_deg"], yaw=y, h=h)[1]), y))
        sim = _sim(i["F_uT"], i["I_deg"], h=h)
        ys = np.arange(0.0, 360.0, 0.01)
        mx = 0.0
        for y in ys:
            sim.cfg.attitude_deg = [0.0, 0.0, float(y)]
            mx = max(mx, abs(float(rm.angle_diff(rm.heading_level(sim.field_truth(0.0)[1]), y))))
        return {"error_exact_deg": err(i["yaw_deg"]), "max_error_over_heading_deg": mx,
                "error_at_0_and_180_deg": [err(0.0), err(180.0)]}

    def tc06(c):
        i = c["inputs"]
        S = np.diag(i["S_diag"])
        return {"error_deg": [float(rm.angle_diff(rm.heading_level(sim_fields(i["F_uT"], i["I_deg"], yaw=y, S=S)[1]), y))
                              for y in i["yaw_deg"]]}

    def tc07(c):
        i = c["inputs"]
        m, _ = sim_noisy_mag(i["F_uT"], i["I_deg"], i["yaw_deg"], i["N"], env_noise=i["sigma_m_uT"], seed=i["seed"])
        e = np.array([rm.angle_diff(rm.heading_level(v), i["yaw_deg"]) for v in m])
        H = EarthField(i["F_uT"], i["I_deg"]).horizontal_uT()
        return {"sigma_psi_predicted_deg": math.degrees(i["sigma_m_uT"] / H),
                "sigma_psi_mc_deg": float(np.std(e)), "mean_error_deg": float(np.mean(e))}

    def tc08(c):
        i = c["inputs"]
        _, b = sim_fields(i["F_uT"], i["I_deg"], yaw=i["yaw_deg"], h=[0.0, i["disturbance_on_body_y_uT"], 0.0])
        dip = rm.measured_dip_deg(b, 0.0, 0.0)
        return {"heading_with_disturbance_deg": rm.heading_level(b), "field_norm_uT": float(np.linalg.norm(b)),
                "dip_deg": dip, "magnitude_check_5pct_pass": bool(abs(np.linalg.norm(b) / i["F_uT"] - 1) <= 0.05),
                "dip_check_1deg_pass": bool(abs(dip - i["I_deg"]) <= 1.0)}

    def tc13(c):
        i = c["inputs"]
        for H in i["H_uT"]:
            F = 50.0
            I = math.degrees(math.acos(H / F))
            m, _ = sim_noisy_mag(F, I, 0.0, 20000, env_noise=i["sigma_m_uT"], seed=3)
            e = np.array([rm.angle_diff(rm.heading_level(v), 0.0) for v in m])
            pred = math.degrees(i["sigma_m_uT"] / H)
            extras.append(("TC13", f"sim MC heading std at H={H} uT vs sigma/H (3% tol)", float(np.std(e)), pred, 0.03 * pred))
        return {}

    def tc14(c):
        i = c["inputs"]
        b_body, _ = sim_fields(i["F_uT"], i["I_deg"], yaw=i["yaw_deg"])
        est = rm.heading_tilt_compensated(b_body, i["roll_error_deg"], i["pitch_error_deg"])
        return {"heading_error_deg": float(rm.angle_diff(est, i["yaw_deg"]))}

    def tc15(c):
        i = c["inputs"]
        rng = np.random.default_rng(i["seed"])
        S, h = np.array(i["S_true"]), np.array(i["h_hard_true_uT"])
        att = [(rng.uniform(0, 360), rng.uniform(-80, 80), rng.uniform(-180, 180)) for _ in range(i["n_attitudes"])]
        sim = _sim(i["F_uT"], i["I_deg"], S=S, h=h)
        X0 = []
        for y, p, r in att:
            sim.cfg.attitude_deg = [r, p, y]
            X0.append(sim.field_truth(0.0)[1])
        X0 = np.array(X0)
        res = {}

        def level_errs(cc, W):
            errs, raw = [], []
            for y in range(0, 360, 5):
                sim.cfg.attitude_deg = [0.0, 0.0, float(y)]
                m = sim.field_truth(0.0)[1]
                errs.append(rm.angle_diff(rm.heading_level(rm.apply_calibration(m, cc, W)), y))
                raw.append(rm.angle_diff(rm.heading_level(m), y))
            return np.array(errs), np.array(raw)
        cc, W, _ = rm.fit_ellipsoid(X0)
        WS = W @ S
        errs, raw = level_errs(cc, W)
        res["offset_error_noisefree_uT"] = float(np.linalg.norm(cc - h))
        res["W_S_offdiag_noisefree"] = float(np.max(np.abs(WS - np.diag(np.diag(WS)))))
        res["heading_rms_after_cal_noisefree_deg"] = float(np.sqrt(np.mean(errs ** 2)))
        res["heading_max_before_cal_deg"] = float(np.max(np.abs(raw)))
        # noisy: the sim's own noise path (env noise 0.1 uT/axis + RM3100 quantisation), one sample per attitude
        Xn = []
        for k, (y, p, r) in enumerate(att):
            s = generate(scenario="static", rate_hz=50, duration_s=0.02, field_total_uT=i["F_uT"],
                         inclination_deg=i["I_deg"], attitude_deg=[r, p, y], soft_iron=S.tolist(), hard_iron_uT=h.tolist(),
                         env_noise_uT=i["noise_sigma_uT"][1], mag_noise_scale=0.0, imu_noise_scale=0.0,
                         imu_bias_scale=0.0, seed=1000 + k)
            Xn.append(s[0]["mag_uT"])
        cn, Wn, _ = rm.fit_ellipsoid(np.array(Xn))
        errs_n, _ = level_errs(cn, Wn)
        res["offset_error_noisy_uT"] = float(np.linalg.norm(cn - h))
        res["heading_max_after_cal_noisy_deg"] = float(np.max(np.abs(errs_n)))
        return res

    def tc16(c):
        i = c["inputs"]
        ps = np.arange(0, 360, 10.0)
        dev = [rm.angle_diff(rm.heading_level(sim_fields(i["F_uT"], i["I_deg"], yaw=p, h=i["h_hard_uT"])[1]), p) for p in ps]
        ch = rm.fit_deviation_curve(ps, dev)
        S = np.eye(3)
        S[:2, :2] += np.array(i["E_soft_2x2"])
        dev2 = np.array([rm.angle_diff(rm.heading_level(sim_fields(i["F_uT"], i["I_deg"], yaw=p, S=S)[1]), p) for p in ps])
        cs = rm.fit_deviation_curve(ps, dev2)
        r = dev2 - rm.eval_deviation_curve(cs, ps)
        return {"hard_B_deg": ch[1], "hard_C_deg": ch[2], "soft_A_deg": cs[0], "soft_D_deg": cs[3], "soft_E_deg": cs[4],
                "residual_rms_after_curve_soft_deg": float(np.sqrt(np.mean(r ** 2)))}

    def tc19(c):
        i = c["inputs"]
        # quantisation of the sim's RM3100 path: sweep a noise-free field over many LSBs, measure error std
        mdl = RM3100Model(200, noise_scale=0.0)
        rng = np.random.default_rng(0)
        # noise-free fields on a low-discrepancy (golden-ratio Weyl) grid of LSB fractions, pushed through the sim's
        # RM3100 quantiser 3 at a time; the std converges to the quantiser's true error std (deterministic)
        lsb = 1.0 / gain_lsb_per_uT(200)
        k = np.arange(90000)
        x = (20.0 + k * lsb * 0.6180339887498949).reshape(-1, 3)
        q_err = np.concatenate([np.asarray(mdl.measure(v, rng)[1]) - v for v in x])
        H = 25.0
        sim_noise = mdl.__class__(200).noise_uT
        extras.append(("TC19", "sim RM3100 LSB (uT) = 1/gain(200) vs spec lsb_uT[0]", lsb, i["lsb_uT"][0], 1e-12))
        return {"quant_sigma_uT": [float(np.std(q_err)), None],
                "rm3100_sigma_psi_deg": math.degrees(sim_noise / H)}

    fns = {"TC01": tc01, "TC02": tc02, "TC03": tc03, "TC04": tc04, "TC05": tc05, "TC06": tc06, "TC07": tc07,
           "TC08": tc08, "TC13": tc13, "TC14": tc14, "TC15": tc15, "TC16": tc16, "TC19": tc19}
    for c in load_cases():
        cid = c["id"]
        out[cid] = (c, fns[cid](c) if cid in fns else None)
    return out, extras


def _cmp(val, exp, tol):
    if isinstance(exp, bool):
        return bool(val) == exp, val
    v, e = np.atleast_1d(np.asarray(val, float)), np.atleast_1d(np.asarray(exp, float))
    return bool(v.shape == e.shape and np.all(np.abs(v - e) <= tol)), val


def evaluate():
    rm = load_reference_model()
    res, extras = run_cases(rm)
    rows = []
    for cid, (c, got) in res.items():
        for key, exp in c["expected"].items():
            tol = c["tolerance"][key]
            if cid in NA:
                rows.append((cid, key, "N/A", None, exp, tol, NA[cid])); continue
            if f"{cid}.{key}" in NA:
                rows.append((cid, key, "N/A", None, exp, tol, NA[f"{cid}.{key}"])); continue
            val = got.get(key) if got else None
            if isinstance(val, list) and any(v is None for v in val):
                # partially N/A list: compare element-wise
                for j, (v, e) in enumerate(zip(val, exp)):
                    k2 = f"{key}[{j}]"
                    if f"{cid}.{k2}" in NA:
                        rows.append((cid, k2, "N/A", None, e, tol, NA[f"{cid}.{k2}"])); continue
                    ok, _ = _cmp(v, e, tol)
                    st = "PASS" if ok else ("MISMATCH" if f"{cid}.{k2}" in KNOWN_MISMATCH else "FAIL")
                    rows.append((cid, k2, st, v, e, tol, KNOWN_MISMATCH.get(f"{cid}.{k2}", "")))
                continue
            if val is None:
                rows.append((cid, key, "FAIL", None, exp, tol, "sim produced no value")); continue
            ok, _ = _cmp(val, exp, tol)
            st = "PASS" if ok else ("MISMATCH" if f"{cid}.{key}" in KNOWN_MISMATCH else "FAIL")
            rows.append((cid, key, st, val, exp, tol, KNOWN_MISMATCH.get(f"{cid}.{key}", "")))
    extra_rows = [(cid, name, "PASS" if abs(v - e) <= t else "FAIL", v, e, t, "extra sim-side check")
                  for cid, name, v, e, t in extras]
    return rows, extra_rows


def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, (list, tuple, np.ndarray)):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    if isinstance(v, (bool, np.bool_)):
        return str(bool(v))
    return f"{float(v):.6g}"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    rows, extra = evaluate()
    if "--json" in argv:
        print(json.dumps([dict(zip(("case", "key", "status", "sim", "expected", "tol", "note"),
                                   (r[0], r[1], r[2], None if r[3] is None else np.asarray(r[3], dtype=object).tolist(),
                                    r[4], r[5], r[6]))) for r in rows + extra], default=float, indent=1))
        return 0
    print(f"{'case':5} {'key':58} {'status':8} {'sim':>28} {'expected':>28}  tol")
    for r in rows + extra:
        print(f"{r[0]:5} {r[1][:58]:58} {r[2]:8} {_fmt(r[3])[:28]:>28} {_fmt(r[4])[:28]:>28}  {r[5]:g}  {r[6][:70]}")
    per = {}
    for r in rows:
        per.setdefault(r[0], {}).setdefault(r[2], 0)
        per[r[0]][r[2]] += 1
    print("\nper case:", json.dumps(per))
    tot = {}
    for r in rows:
        tot[r[2]] = tot.get(r[2], 0) + 1
    print("spec keys:", tot, "| extra checks:", {s: sum(1 for r in extra if r[2] == s) for s in ("PASS", "FAIL")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
