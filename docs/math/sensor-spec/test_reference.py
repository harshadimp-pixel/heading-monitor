"""Reference test cases for the magnetic-heading spec.

Expected values are analytic (closed form, hand-checkable) or from a published
source (Ed Williams, Aviation Formulary, LAX->JFK example). The code in
reference_model.py must reproduce them.  `python test_reference.py --dump`
writes test_cases.json from the CASES table below (single source of truth).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

import reference_model as rm

D2R = math.pi / 180.0
LAX = (33 + 57 / 60, -(118 + 24 / 60))
JFK = (40 + 38 / 60, -(73 + 47 / 60))
R_NM = 180 * 60 / math.pi  # Earth radius in nm such that 1 arcmin = 1 nm (Williams)

# Each case: id, title, inputs, expected (dict), tolerance (dict, absolute), units, compute(inputs)->dict
CASES = []


def case(cid, title, inputs, expected, tol, units, source="analytic"):
    def deco(fn):
        CASES.append(dict(id=cid, title=title, inputs=inputs, expected=expected,
                          tolerance=tol, units=units, source=source, fn=fn))
        return fn
    return deco


EARTH = {"F_uT": 50.0, "I_deg": 60.0}   # => H = 25 uT, Z = 43.30127 uT (assumed test field)


def _b(inp):
    return rm.earth_field_ned(inp["F_uT"], inp["I_deg"], inp.get("D_deg", 0.0))


@case("TC01", "Level heading at cardinal points and 30 deg",
      {**EARTH, "yaw_deg": [0, 90, 180, 270, 30], "roll_deg": 0, "pitch_deg": 0},
      {"heading_deg": [0.0, 90.0, 180.0, 270.0, 30.0], "m_body_at_30_uT": [21.650635, -12.5, 43.301270]},
      {"heading_deg": 1e-9, "m_body_at_30_uT": 1e-6}, {"heading_deg": "deg", "m_body_at_30_uT": "uT"})
def tc01(inp):
    b = _b(inp)
    hs = [rm.heading_level(rm.sensor_model(b, y, 0, 0)[0]) for y in inp["yaw_deg"]]
    return {"heading_deg": hs, "m_body_at_30_uT": rm.sensor_model(b, 30, 0, 0)[0].tolist()}


@case("TC02", "Magnetic -> true via declination (east +), wrap-around, declination error passes through",
      {"pairs_psi_m_D": [[10.0, -1.5], [359.0, 2.0], [0.5, -1.0], [180.0, 180.0]], "D_error_deg": 0.5, "psi_m_deg": 45.0},
      {"true_deg": [8.5, 1.0, 359.5, 0.0], "true_heading_error_deg": 0.5},
      {"true_deg": 1e-9, "true_heading_error_deg": 1e-9}, {"true_deg": "deg", "true_heading_error_deg": "deg"})
def tc02(inp):
    t = [rm.magnetic_to_true(p, d) for p, d in inp["pairs_psi_m_D"]]
    e = rm.angle_diff(rm.magnetic_to_true(inp["psi_m_deg"], 3.0 + inp["D_error_deg"]),
                      rm.magnetic_to_true(inp["psi_m_deg"], 3.0))
    return {"true_deg": t, "true_heading_error_deg": e}


@case("TC03", "Wrap conventions and circular statistics",
      {"angles_deg": [359.0, 1.0], "diff_a_b": [[1.0, 359.0], [359.0, 1.0], [0.0, 180.0], [180.0, 0.0]],
       "spread_deg": [350.0, 10.0, 0.0]},
      {"arith_mean_deg": 180.0, "circ_mean_deg": 0.0, "angle_diff_deg": [2.0, -2.0, 180.0, 180.0],
       "circ_mean_spread_deg": 0.0, "circ_std_spread_deg": 8.175368},
      {"arith_mean_deg": 1e-9, "circ_mean_deg": 1e-9, "angle_diff_deg": 1e-9, "circ_mean_spread_deg": 1e-9,
       "circ_std_spread_deg": 1e-5},
      {"*": "deg"})
def tc03(inp):
    cm = rm.circular_mean_deg(inp["angles_deg"])
    cm = rm.wrap180(cm)  # 0 may come out as ~360-eps
    cs = rm.wrap180(rm.circular_mean_deg(inp["spread_deg"]))
    return {"arith_mean_deg": float(np.mean(inp["angles_deg"])), "circ_mean_deg": cm,
            "angle_diff_deg": [rm.angle_diff(a, b) for a, b in inp["diff_a_b"]],
            "circ_mean_spread_deg": cs, "circ_std_spread_deg": rm.circular_std_deg(inp["spread_deg"])}


@case("TC04", "Tilt-compensated heading from mag + accel (specific-force convention)",
      {**EARTH, "cases_yaw_pitch_roll_deg": [[135, 20, -30], [45, 30, 0], [300, -15, 25]]},
      {"tilt_comp_heading_deg": [135.0, 45.0, 300.0], "uncompensated_level_formula_deg": [133.918030, 109.733898, 302.940805],
       "recovered_roll_pitch_case1_deg": [-30.0, 20.0], "measured_dip_deg": [60.0, 60.0, 60.0]},
      {"tilt_comp_heading_deg": 1e-9, "uncompensated_level_formula_deg": 1e-5, "recovered_roll_pitch_case1_deg": 1e-9,
       "measured_dip_deg": 1e-9},
      {"*": "deg"})
def tc04(inp):
    b = _b(inp)
    tc, lv, dip = [], [], []
    for y, p, r in inp["cases_yaw_pitch_roll_deg"]:
        m = rm.sensor_model(b, y, p, r)[0]
        a = rm.accel_from_attitude(p, r)
        tc.append(rm.heading_from_mag_accel(m, a))
        lv.append(rm.heading_level(m))
        rr, pp = rm.roll_pitch_from_accel(a)
        dip.append(rm.measured_dip_deg(m, rr, pp))
    y, p, r = inp["cases_yaw_pitch_roll_deg"][0]
    return {"tilt_comp_heading_deg": tc, "uncompensated_level_formula_deg": lv,
            "recovered_roll_pitch_case1_deg": list(rm.roll_pitch_from_accel(rm.accel_from_attitude(p, r))),
            "measured_dip_deg": dip}


@case("TC05", "Hard-iron one-cycle error (b_x = 5 uT, H = 25 uT, level)",
      {**EARTH, "h_hard_uT": [5.0, 0.0, 0.0], "yaw_deg": 90.0},
      {"error_exact_deg": -11.309932, "error_first_order_deg": -11.459156, "max_error_over_heading_deg": 11.536959,
       "error_at_0_and_180_deg": [0.0, 0.0]},
      {"error_exact_deg": 1e-5, "error_first_order_deg": 1e-5, "max_error_over_heading_deg": 1e-4,
       "error_at_0_and_180_deg": 1e-9},
      {"*": "deg"})
def tc05(inp):
    b = _b(inp)
    def err(y):
        return rm.angle_diff(rm.heading_level(rm.sensor_model(b, y, 0, 0, h_hard=inp["h_hard_uT"])[0]), y)
    grid = np.arange(0, 360, 0.01)
    bx, by = inp["h_hard_uT"][:2]
    return {"error_exact_deg": err(inp["yaw_deg"]),
            "error_first_order_deg": float(rm.hard_iron_error_approx_deg(inp["yaw_deg"], bx, by, 25.0)),
            "max_error_over_heading_deg": float(np.max(np.abs(rm.hard_iron_error_exact_deg(grid, bx, by, 25.0)))),
            "error_at_0_and_180_deg": [err(0.0), err(180.0)]}


@case("TC06", "Soft-iron two-cycle error (scale x 1.05, y 0.95, level)",
      {**EARTH, "S_diag": [1.05, 0.95, 1.0], "yaw_deg": [45.0, 0.0, 90.0, 135.0]},
      {"error_deg": [-2.862405, 0.0, 0.0, 2.862405], "first_order_at_45_deg": -2.864789},
      {"error_deg": 1e-5, "first_order_at_45_deg": 1e-5}, {"*": "deg"})
def tc06(inp):
    b = _b(inp)
    S = np.diag(inp["S_diag"])
    e = [rm.angle_diff(rm.heading_level(rm.sensor_model(b, y, 0, 0, S=S)[0]), y) for y in inp["yaw_deg"]]
    E = np.diag(inp["S_diag"][:2]) - np.eye(2)
    return {"error_deg": e, "first_order_at_45_deg": float(rm.soft_iron_error_approx_deg(45.0, E))}


@case("TC07", "White-noise heading std, Monte Carlo (sigma_m = 0.1 uT/axis, H = 25 uT, N = 20000, seed 0)",
      {**EARTH, "yaw_deg": 30.0, "sigma_m_uT": 0.1, "N": 20000, "seed": 0},
      {"sigma_psi_predicted_deg": 0.229183, "sigma_psi_mc_deg": 0.229183, "mean_error_deg": 0.0},
      {"sigma_psi_predicted_deg": 1e-5, "sigma_psi_mc_deg": 0.0069, "mean_error_deg": 0.01},
      {"*": "deg"}, source="analytic; MC tolerance = 3% (sampling std of std ~ 1/sqrt(2N) = 0.5%)")
def tc07(inp):
    s = rm.heading_noise_monte_carlo(inp["yaw_deg"], inp["F_uT"], inp["I_deg"], inp["sigma_m_uT"], inp["N"], inp["seed"])
    return {"sigma_psi_predicted_deg": rm.heading_noise_sigma_deg(inp["sigma_m_uT"], 25.0),
            "sigma_psi_mc_deg": s["circ_std"], "mean_error_deg": s["circ_mean"]}


@case("TC08", "Interference: dipole (1 A m^2 at 0.3 m) and straight wire (10 A at 0.1 m)",
      {**EARTH, "dipole_moment_Am2": [1.0, 0.0, 0.0], "r_axial_m": [0.3, 0.0, 0.0], "r_equatorial_m": [0.0, 0.3, 0.0],
       "wire_I_A": 10.0, "wire_r_m": [0.1, 1.0], "disturbance_on_body_y_uT": 7.407407407, "yaw_deg": 0.0},
      {"B_axial_uT": 7.407407, "B_equatorial_uT": -3.703704, "B_wire_uT": [20.0, 2.0], "dipole_at_0.6m_axial_uT": 0.925926,
       "heading_with_disturbance_deg": 343.495639, "field_norm_uT": 50.545719, "dip_deg": 58.945314,
       "magnitude_check_5pct_pass": True, "dip_check_1deg_pass": False},
      {"B_axial_uT": 1e-5, "B_equatorial_uT": 1e-5, "B_wire_uT": 1e-6, "dipole_at_0.6m_axial_uT": 1e-6,
       "heading_with_disturbance_deg": 1e-5, "field_norm_uT": 1e-5, "dip_deg": 1e-5,
       "magnitude_check_5pct_pass": 0, "dip_check_1deg_pass": 0},
      {"*": "uT / deg / bool"})
def tc08(inp):
    m = np.array(inp["dipole_moment_Am2"])
    ax = rm.dipole_field(m, inp["r_axial_m"])[0] * 1e6
    eq = rm.dipole_field(m, inp["r_equatorial_m"])[0] * 1e6
    far = rm.dipole_field(m, [0.6, 0, 0])[0] * 1e6
    b = _b(inp)
    meas = rm.sensor_model(b, 0, 0, 0, b_interf_body=[0, inp["disturbance_on_body_y_uT"], 0])[0]
    return {"B_axial_uT": ax, "B_equatorial_uT": eq,
            "B_wire_uT": [rm.wire_field_magnitude(inp["wire_I_A"], r) * 1e6 for r in inp["wire_r_m"]],
            "dipole_at_0.6m_axial_uT": far,
            "heading_with_disturbance_deg": rm.heading_level(meas), "field_norm_uT": float(np.linalg.norm(meas)),
            "dip_deg": rm.measured_dip_deg(meas, 0, 0),
            "magnitude_check_5pct_pass": bool(rm.magnitude_check(meas, 50.0, 0.05)),
            "dip_check_1deg_pass": bool(rm.dip_check(meas, 0, 0, 60.0, 1.0))}


@case("TC09", "Heading vs track: crosswind crab angle",
      {"heading_deg": 0.0, "airspeed_mps": 50.0, "wind_toward_deg": 90.0, "wind_mps": 10.0},
      {"track_deg": 11.309932, "ground_speed_mps": 50.990195, "crab_angle_deg": 11.309932},
      {"track_deg": 1e-5, "ground_speed_mps": 1e-5, "crab_angle_deg": 1e-5},
      {"track_deg": "deg", "ground_speed_mps": "m/s", "crab_angle_deg": "deg"})
def tc09(inp):
    v = rm.ground_velocity(inp["heading_deg"], inp["airspeed_mps"], inp["wind_toward_deg"], inp["wind_mps"])
    t, gs = rm.track_and_speed(v)
    return {"track_deg": t, "ground_speed_mps": gs, "crab_angle_deg": rm.crab_angle(inp["heading_deg"], t)}


@case("TC10", "Distance travelled vs displacement (U-path and semicircle)",
      {"u_path_NE_m": [[0, 0], [100, 0], [100, 100], [0, 100]], "semicircle_radius_m": 100.0, "semicircle_segments": 100000},
      {"u_distance_m": 300.0, "u_displacement_m": 100.0, "u_displacement_bearing_deg": 90.0,
       "semi_distance_m": 314.159265, "semi_displacement_m": 200.0},
      {"u_distance_m": 1e-9, "u_displacement_m": 1e-9, "u_displacement_bearing_deg": 1e-9,
       "semi_distance_m": 1e-3, "semi_displacement_m": 1e-9},
      {"*": "m / deg"})
def tc10(inp):
    d = rm.path_length(inp["u_path_NE_m"])
    s, brg = rm.displacement(inp["u_path_NE_m"])
    R = inp["semicircle_radius_m"]
    th = np.linspace(0, np.pi, inp["semicircle_segments"] + 1)
    pts = np.column_stack([R * np.sin(th), R - R * np.cos(th)])  # start (0,0), end (0,2R)
    return {"u_distance_m": d, "u_displacement_m": s, "u_displacement_bearing_deg": brg,
            "semi_distance_m": rm.path_length(pts), "semi_displacement_m": rm.displacement(pts)[0]}


@case("TC11", "Great circle LAX->JFK (haversine, initial bearing) and rhumb line, spherical Earth",
      {"LAX_deg": list(LAX), "JFK_deg": list(JFK), "R_nm": "180*60/pi (1 arcmin = 1 nm)", "R_mean_m": rm.R_MEAN},
      {"gc_angle_rad": 0.623585, "gc_distance_nm": 2143.7, "initial_course_deg": 65.892, "rhumb_course_deg": 79.32,
       "rhumb_distance_nm": 2164.6, "gc_distance_km_Rmean": 3972.863},
      {"gc_angle_rad": 1e-6, "gc_distance_nm": 0.1, "initial_course_deg": 1e-3, "rhumb_course_deg": 0.01,
       "rhumb_distance_nm": 0.1, "gc_distance_km_Rmean": 1e-3},
      {"*": "rad / nm / deg / km"},
      source="Ed Williams, Aviation Formulary (LAX-JFK worked example: d=0.623585 rad=2144 nm, tc=1.150035 rad, rhumb 79.3 deg / 2164.6 nm)")
def tc11(inp):
    d_m, c = rm.haversine(*LAX, *JFK)
    rd, rc = rm.rhumb_line(*LAX, *JFK, R=R_NM)
    return {"gc_angle_rad": c, "gc_distance_nm": c * R_NM, "initial_course_deg": rm.initial_bearing(*LAX, *JFK),
            "rhumb_course_deg": rc, "rhumb_distance_nm": rd, "gc_distance_km_Rmean": d_m / 1000}


@case("TC12", "Dead-reckoning cross-track error from a 2 deg heading bias over 1 km",
      {"leg_m": 1000.0, "heading_bias_deg": 2.0},
      {"cross_track_m": 34.899497, "along_track_m": 999.390827, "total_position_error_m": 34.904813,
       "small_angle_cross_track_m": 34.906585},
      {"cross_track_m": 1e-5, "along_track_m": 1e-5, "total_position_error_m": 1e-5, "small_angle_cross_track_m": 1e-5},
      {"*": "m"})
def tc12(inp):
    x, a, t = rm.cross_track_from_heading_bias(inp["leg_m"], inp["heading_bias_deg"])
    # independent check through the DR integrator: 100 steps of 10 m on track 2 deg vs 0 deg
    p = rm.dead_reckon_flat([0, 0], 10.0, [inp["heading_bias_deg"]] * 100, 1.0)[-1]
    assert abs(p[1] - x) < 1e-9 and abs(p[0] - a) < 1e-9
    return {"cross_track_m": x, "along_track_m": a, "total_position_error_m": t,
            "small_angle_cross_track_m": inp["leg_m"] * math.radians(inp["heading_bias_deg"])}


@case("TC13", "Near magnetic pole: heading noise and WMM declination uncertainty grow as 1/H",
      {"sigma_m_uT": 0.1, "H_uT": [25.0, 2.0], "H_nT_for_WMM": [25000.0, 2000.0]},
      {"sigma_psi_deg": [0.229183, 2.864789], "amplification": 12.5, "wmm2025_sigma_D_deg": [0.338453, 2.720951]},
      {"sigma_psi_deg": 1e-5, "amplification": 1e-9, "wmm2025_sigma_D_deg": 1e-5},
      {"*": "deg"}, source="sigma_D formula: NCEI WMM2025 error model")
def tc13(inp):
    s = [rm.heading_noise_sigma_deg(inp["sigma_m_uT"], H) for H in inp["H_uT"]]
    return {"sigma_psi_deg": s, "amplification": s[1] / s[0],
            "wmm2025_sigma_D_deg": [rm.wmm2025_decl_uncertainty_deg(h) for h in inp["H_nT_for_WMM"]]}


@case("TC14", "Tilt-estimate error couples into heading via dip: 1 deg roll error, I = 60 deg, heading 0",
      {**EARTH, "yaw_deg": 0.0, "roll_error_deg": 1.0, "pitch_error_deg": 0.0},
      {"heading_error_deg": 1.731436, "first_order_tanI_deg": 1.732051},
      {"heading_error_deg": 1e-5, "first_order_tanI_deg": 1e-5}, {"*": "deg"})
def tc14(inp):
    b = _b(inp)
    m = rm.sensor_model(b, inp["yaw_deg"], 0, 0)[0]
    h = rm.heading_tilt_compensated(m, inp["roll_error_deg"], inp["pitch_error_deg"])
    return {"heading_error_deg": rm.angle_diff(h, inp["yaw_deg"]),
            "first_order_tanI_deg": float(rm.tilt_error_approx_deg(inp["yaw_deg"], inp["I_deg"], inp["roll_error_deg"], inp["pitch_error_deg"]))}


S_TRUE = [[1.08, 0.03, -0.02], [0.03, 0.95, 0.01], [-0.02, 0.01, 1.02]]
H_TRUE = [12.0, -7.0, 4.0]


@case("TC15", "Ellipsoid fit recovers hard/soft iron (500 random attitudes, symmetric S)",
      {**EARTH, "S_true": S_TRUE, "h_hard_true_uT": H_TRUE, "n_attitudes": 500, "seed": 1, "noise_sigma_uT": [0.0, 0.1]},
      {"offset_error_noisefree_uT": 0.0, "W_S_offdiag_noisefree": 0.0, "heading_rms_after_cal_noisefree_deg": 0.0,
       "offset_error_noisy_uT": 0.0, "heading_max_after_cal_noisy_deg": 0.0, "heading_max_before_cal_deg": 34.679191},
      {"offset_error_noisefree_uT": 1e-8, "W_S_offdiag_noisefree": 1e-8, "heading_rms_after_cal_noisefree_deg": 1e-8,
       "offset_error_noisy_uT": 0.05, "heading_max_after_cal_noisy_deg": 0.1, "heading_max_before_cal_deg": 1e-5},
      {"*": "uT / deg"})
def tc15(inp):
    rng = np.random.default_rng(inp["seed"])
    b = _b(inp)
    S, h = np.array(inp["S_true"]), np.array(inp["h_hard_true_uT"])
    att = [(rng.uniform(0, 360), rng.uniform(-80, 80), rng.uniform(-180, 180)) for _ in range(inp["n_attitudes"])]
    out = {}
    for sig in inp["noise_sigma_uT"]:
        X = np.vstack([rm.sensor_model(b, y, p, r, S=S, h_hard=h, noise_sigma=sig, rng=rng)[0] for y, p, r in att])
        c, W, _ = rm.fit_ellipsoid(X)
        WS = W @ S
        errs, raw = [], []
        for y in range(0, 360, 5):
            m = rm.sensor_model(b, y, 0, 0, S=S, h_hard=h)[0]
            errs.append(rm.angle_diff(rm.heading_level(rm.apply_calibration(m, c, W)), y))
            raw.append(rm.angle_diff(rm.heading_level(m), y))
        errs = np.array(errs)
        if sig == 0:
            out["offset_error_noisefree_uT"] = float(np.linalg.norm(c - h))
            out["W_S_offdiag_noisefree"] = float(np.max(np.abs(WS - np.diag(np.diag(WS)))))
            out["heading_rms_after_cal_noisefree_deg"] = float(np.sqrt(np.mean(errs ** 2)))
            out["heading_max_before_cal_deg"] = float(np.max(np.abs(raw)))
        else:
            out["offset_error_noisy_uT"] = float(np.linalg.norm(c - h))
            out["heading_max_after_cal_noisy_deg"] = float(np.max(np.abs(errs)))
    return out


@case("TC16", "Compass swing: deviation curve coefficients from hard + soft iron (36 headings, level)",
      {**EARTH, "h_hard_uT": [1.0, 0.5, 0.0], "E_soft_2x2": [[0.04, 0.02], [-0.01, -0.03]]},
      {"hard_B_deg": -2.291831, "hard_C_deg": -1.145916, "soft_A_deg": 0.859437, "soft_D_deg": -2.005352, "soft_E_deg": -0.286479,
       "residual_rms_after_curve_soft_deg": 0.0},
      {"hard_B_deg": 1e-6, "hard_C_deg": 1e-6, "soft_A_deg": 0.01, "soft_D_deg": 0.02, "soft_E_deg": 0.03,
       "residual_rms_after_curve_soft_deg": 0.05},
      {"*": "deg"}, source="first-order theory: B=-b_x/H, C=-b_y/H, A=(e12-e21)/2, D=(e22-e11)/2, E=-(e12+e21)/2 (rad)")
def tc16(inp):
    b = _b(inp)
    ps = np.arange(0, 360, 10.0)
    dev = [rm.angle_diff(rm.heading_level(rm.sensor_model(b, p, 0, 0, h_hard=inp["h_hard_uT"])[0]), p) for p in ps]
    ch = rm.fit_deviation_curve(ps, dev)
    S = np.eye(3)
    S[:2, :2] += np.array(inp["E_soft_2x2"])
    dev2 = np.array([rm.angle_diff(rm.heading_level(rm.sensor_model(b, p, 0, 0, S=S)[0]), p) for p in ps])
    cs = rm.fit_deviation_curve(ps, dev2)
    res = dev2 - rm.eval_deviation_curve(cs, ps)
    return {"hard_B_deg": ch[1], "hard_C_deg": ch[2], "soft_A_deg": cs[0], "soft_D_deg": cs[3], "soft_E_deg": cs[4],
            "residual_rms_after_curve_soft_deg": float(np.sqrt(np.mean(res ** 2)))}


@case("TC17", "WGS84 radii and dead reckoning in lat/lon",
      {"lat_deg": [0.0, 45.0], "dr_equator_north_m": 1000.0, "dr_45N_east_m": 1000.0},
      {"M_equator_m": 6335439.327, "N_equator_m": 6378137.0, "M_45_m": 6367381.816, "N_45_m": 6388838.290,
       "dlat_equator_1km_north_deg": 0.00904369, "dlon_45N_1km_east_deg": 0.01268282},
      {"M_equator_m": 1e-3, "N_equator_m": 1e-6, "M_45_m": 1e-3, "N_45_m": 1e-3,
       "dlat_equator_1km_north_deg": 1e-8, "dlon_45N_1km_east_deg": 1e-8},
      {"*": "m / deg"}, source="WGS84 a=6378137, 1/f=298.257223563")
def tc17(inp):
    M0, N0 = rm.radii_wgs84(0.0)
    M45, N45 = rm.radii_wgs84(45.0)
    lat1, _ = rm.dead_reckon_wgs84(0, 0, 0, [10.0], [0.0], 100.0)
    _, lon2 = rm.dead_reckon_wgs84(45, 0, 0, [10.0], [90.0], 100.0)
    return {"M_equator_m": M0, "N_equator_m": N0, "M_45_m": M45, "N_45_m": N45,
            "dlat_equator_1km_north_deg": lat1, "dlon_45N_1km_east_deg": lon2}


@case("TC18", "DR cross-track growth: constant bias (linear) vs white heading noise (sqrt N), Monte Carlo",
      {"v_mps": 10.0, "dt_s": 1.0, "n_steps": 100, "bias_deg": 1.0, "sigma_psi_deg": 2.0, "n_runs": 4000, "seed": 2},
      {"bias_crosstrack_m": 17.452406, "white_rms_crosstrack_theory_m": 3.490659, "white_rms_crosstrack_mc_m": 3.490659},
      {"bias_crosstrack_m": 1e-5, "white_rms_crosstrack_theory_m": 1e-5, "white_rms_crosstrack_mc_m": 0.14},
      {"*": "m"}, source="analytic; MC tolerance 4% (~3.5 sigma of sampling error for 4000 runs)")
def tc18(inp):
    rng = np.random.default_rng(inp["seed"])
    v, dt, n = inp["v_mps"], inp["dt_s"], inp["n_steps"]
    pb = rm.dead_reckon_flat([0, 0], v, [inp["bias_deg"]] * n, dt)[-1]
    e = rng.normal(0, inp["sigma_psi_deg"], size=(inp["n_runs"], n))
    xt = np.sum(v * dt * np.sin(np.radians(e)), axis=1)
    return {"bias_crosstrack_m": float(pb[1]),
            "white_rms_crosstrack_theory_m": rm.dr_crosstrack_rms_white(v, dt, n, inp["sigma_psi_deg"]),
            "white_rms_crosstrack_mc_m": float(np.sqrt(np.mean(xt ** 2)))}


@case("TC19", "Quantisation noise and RM3100-class noise mapped to heading (H = 25 uT)",
      {"lsb_uT": [0.013, 0.15], "rm3100_noise_cc200_uT": 0.015, "H_uT": 25.0},
      {"quant_sigma_uT": [0.0037528, 0.0433013], "rm3100_sigma_psi_deg": 0.0343775},
      {"quant_sigma_uT": 1e-6, "rm3100_sigma_psi_deg": 1e-6}, {"*": "uT / deg"},
      source="RM3100 15 nT @ CC200 and 13 nT resolution: docs/hardware/FACTSHEET.md [DATASHEET PNI-UM Table 3-1]; 0.15 uT LSB = assumed generic consumer part")
def tc19(inp):
    return {"quant_sigma_uT": [float(rm.quantisation_sigma(q)) for q in inp["lsb_uT"]],
            "rm3100_sigma_psi_deg": rm.heading_noise_sigma_deg(inp["rm3100_noise_cc200_uT"], inp["H_uT"])}


@case("TC20", "Grid convergence (TM first order) and true -> grid heading",
      {"lat_deg": 19.0, "lon_deg": 73.0, "central_meridian_deg": 75.0, "true_heading_deg": 10.0},
      {"convergence_deg": -0.651373, "grid_heading_deg": 10.651373},
      {"convergence_deg": 1e-5, "grid_heading_deg": 1e-5}, {"*": "deg"},
      source="spherical TM: tan(gamma) = tan(dlon) sin(lat); ellipsoidal terms neglected (<~0.01 deg here)")
def tc20(inp):
    g = rm.tm_grid_convergence_deg(inp["lat_deg"], inp["lon_deg"], inp["central_meridian_deg"])
    return {"convergence_deg": g, "grid_heading_deg": rm.true_to_grid(inp["true_heading_deg"], g)}


# ------------------------------------------------------------------ test runner

def _compare(got, exp, tol, key):
    if isinstance(exp, bool):
        assert bool(got) == exp, key
    elif isinstance(exp, list):
        assert len(got) == len(exp), key
        for g, e in zip(got, exp):
            _compare(g, e, tol, key)
    else:
        assert abs(float(got) - float(exp)) <= tol, f"{key}: got {got}, expected {exp} +/- {tol}"


@pytest.mark.parametrize("c", CASES, ids=[c["id"] for c in CASES])
def test_case(c):
    got = c["fn"](c["inputs"])
    for k, e in c["expected"].items():
        _compare(got[k], e, c["tolerance"][k], f'{c["id"]}.{k}')


def test_wrap_edges():
    assert rm.wrap360(360.0) == 0.0 and rm.wrap360(-0.0) == 0.0 and rm.wrap360(-1.0) == 359.0
    assert rm.wrap180(-180.0) == 180.0 and rm.wrap180(180.0) == 180.0 and rm.wrap180(540.0) == 180.0


def test_gravity_convention_equivalent():
    a = rm.accel_from_attitude(20, -30)
    assert np.allclose(rm.roll_pitch_from_accel(a), rm.roll_pitch_from_accel(-a, "gravity"))


def test_heading_needs_no_speed_position_nullspace():
    """Same heading history, different wind -> different positions: a compass alone cannot fix position."""
    pa = rm.dead_reckon_flat([0, 0], 50.0, [0.0] * 60, 1.0)[-1]
    t, gs = rm.track_and_speed(rm.ground_velocity(0.0, 50.0, 90.0, 10.0))
    pb = rm.dead_reckon_flat([0, 0], gs, [t] * 60, 1.0)[-1]
    assert np.linalg.norm(pb - pa) > 500.0   # 600 m apart after 60 s with identical compass readings


def dump(path="test_cases.json"):
    out = []
    for c in CASES:
        got = c["fn"](c["inputs"])
        out.append({k: c[k] for k in ("id", "title", "inputs", "expected", "tolerance", "units", "source")}
                   | {"computed_by_reference_model": got})
    Path(path).write_text(json.dumps({"spec": "SPEC.md", "generator": "test_reference.py --dump",
                                      "tolerance_semantics": "absolute, |computed - expected| <= tolerance, per key, elementwise for lists; bools must match",
                                      "cases": out}, indent=2, default=float))
    print(f"wrote {len(out)} cases to {path}")


if __name__ == "__main__" and "--dump" in sys.argv:
    dump()
