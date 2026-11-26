"""Reference model for magnetic heading measurement (numpy only).

Every formula in SPEC.md has a function here; the expected values in SPEC.md
and test_cases.json are produced by / checked against this module.

Conventions (see SPEC.md section 1):
  * Navigation frame NED: x = North, y = East, z = Down.
  * Body frame: x forward, y right, z down.
  * Euler angles ZYX (yaw psi, pitch theta, roll phi); C_nb maps NED -> body:
        v_b = R1(phi) R2(theta) R3(psi) v_n   (frame rotations)
  * Heading psi: clockwise from north looking down, reported in [0, 360) deg.
  * Signed angle differences in (-180, 180] deg.
  * Declination D: east positive.  True = magnetic + D.
  * Magnetic field in microtesla (uT) unless stated.
  * Accelerometer: SPECIFIC FORCE convention by default (at rest, level,
    reads [0, 0, -g] in NED body axes).  Pass convention="gravity" if the
    driver reports +g on z when level.
"""
from __future__ import annotations

import numpy as np

MU0 = 4e-7 * np.pi          # T*m/A (classical value; CODATA differs by ~1e-10 relative)
WGS84_A = 6378137.0         # m, semi-major axis
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)
R_MEAN = 6371008.8          # m, IUGG mean Earth radius R1
NM = 1852.0                 # m per international nautical mile

# --------------------------------------------------------------------------
# 1. Angles
# --------------------------------------------------------------------------

def wrap360(a):
    """Wrap degrees to [0, 360)."""
    r = np.mod(a, 360.0)
    # np.mod(-1e-17, 360) can return 360.0 exactly
    return np.where(r >= 360.0, 0.0, r) if np.ndim(r) else (0.0 if r >= 360.0 else float(r))


def wrap180(a):
    """Wrap degrees to (-180, 180]."""
    r = 180.0 - np.mod(180.0 - np.asarray(a, dtype=float), 360.0)
    return float(r) if np.ndim(r) == 0 else r


def angle_diff(a, b):
    """Signed shortest difference a - b in (-180, 180] deg."""
    return wrap180(np.asarray(a, dtype=float) - np.asarray(b, dtype=float))


def circular_mean_deg(angles):
    a = np.radians(np.asarray(angles, dtype=float))
    return wrap360(np.degrees(np.arctan2(np.mean(np.sin(a)), np.mean(np.cos(a)))))


def mean_resultant_length(angles):
    a = np.radians(np.asarray(angles, dtype=float))
    return float(np.hypot(np.mean(np.sin(a)), np.mean(np.cos(a))))


def circular_std_deg(angles):
    """Circular standard deviation sqrt(-2 ln R), degrees."""
    R = mean_resultant_length(angles)
    return float(np.degrees(np.sqrt(-2.0 * np.log(R))))


def error_stats(measured_deg, truth_deg):
    """Wrapped error statistics: mean, RMS, max |e|, circular mean/std of error."""
    e = angle_diff(measured_deg, truth_deg)
    e = np.atleast_1d(e)
    return {
        "mean": float(np.mean(e)),
        "rms": float(np.sqrt(np.mean(e ** 2))),
        "max_abs": float(np.max(np.abs(e))),
        "p95_abs": float(np.percentile(np.abs(e), 95)),
        "circ_mean": float(wrap180(circular_mean_deg(e))),
        "circ_std": circular_std_deg(e),
    }

# --------------------------------------------------------------------------
# 2. Rotations
# --------------------------------------------------------------------------

def R1(a):  # frame rotation about x
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, s], [0, -s, c]], dtype=float)


def R2(a):  # frame rotation about y
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]], dtype=float)


def R3(a):  # frame rotation about z
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]], dtype=float)


def dcm_nav_to_body(yaw_deg, pitch_deg, roll_deg):
    """C_nb (NED -> body), ZYX Euler. v_b = C_nb @ v_n."""
    y, p, r = np.radians([yaw_deg, pitch_deg, roll_deg])
    return R1(r) @ R2(p) @ R3(y)

# --------------------------------------------------------------------------
# 3. Earth field
# --------------------------------------------------------------------------

def earth_field_ned(F, incl_deg, decl_deg=0.0):
    """Earth field in true-north NED: [F cosI cosD, F cosI sinD, F sinI]."""
    I, D = np.radians([incl_deg, decl_deg])
    return np.array([F * np.cos(I) * np.cos(D), F * np.cos(I) * np.sin(D), F * np.sin(I)])


def field_elements(b_ned):
    """(F, H, I_deg, D_deg) from NED field vector."""
    X, Y, Z = b_ned
    H = np.hypot(X, Y)
    return float(np.linalg.norm(b_ned)), float(H), float(np.degrees(np.arctan2(Z, H))), float(np.degrees(np.arctan2(Y, X)))


def magnetic_to_true(psi_m_deg, decl_deg):
    return wrap360(psi_m_deg + decl_deg)


def true_to_magnetic(psi_t_deg, decl_deg):
    return wrap360(psi_t_deg - decl_deg)


def true_to_grid(psi_t_deg, convergence_deg):
    """Grid heading = true heading - gamma (gamma > 0 when grid north is east of true north)."""
    return wrap360(psi_t_deg - convergence_deg)


def tm_grid_convergence_deg(lat_deg, lon_deg, lon0_deg):
    """First-order Transverse Mercator / UTM convergence gamma ~ (lon-lon0) sin(lat)."""
    return float(np.degrees(np.arctan(np.tan(np.radians(lon_deg - lon0_deg)) * np.sin(np.radians(lat_deg)))))


def wmm2025_decl_uncertainty_deg(H_nT):
    """WMM2025 error model (NCEI): sigma_D = sqrt(0.26^2 + (5417/H)^2) deg, H in nT."""
    return float(np.sqrt(0.26 ** 2 + (5417.0 / H_nT) ** 2))

# --------------------------------------------------------------------------
# 4. Heading
# --------------------------------------------------------------------------

def heading_level(m_b):
    """Level heading psi = atan2(-m_y, m_x), deg [0,360). Body NED x fwd, y right."""
    return wrap360(np.degrees(np.arctan2(-m_b[1], m_b[0])))


def roll_pitch_from_accel(a_b, convention="specific_force"):
    """(roll, pitch) deg from static accelerometer.

    specific_force: level at rest reads [0,0,-g]  ->  phi = atan2(-a_y,-a_z), theta = atan2(a_x, sqrt(a_y^2+a_z^2))
    gravity:        level at rest reads [0,0,+g]  ->  sign-flip input first.
    """
    a = np.asarray(a_b, dtype=float)
    if convention == "gravity":
        a = -a
    elif convention != "specific_force":
        raise ValueError(convention)
    phi = np.arctan2(-a[1], -a[2])
    theta = np.arctan2(a[0], np.hypot(a[1], a[2]))
    return float(np.degrees(phi)), float(np.degrees(theta))


def accel_from_attitude(pitch_deg, roll_deg, g=1.0):
    """Static specific force in body axes: C_nb @ [0,0,-g]."""
    return dcm_nav_to_body(0.0, pitch_deg, roll_deg) @ np.array([0.0, 0.0, -g])


def horizontal_components(m_b, roll_deg, pitch_deg):
    """De-rotate body field to the local level frame: X_h, Y_h, Z_h."""
    phi, th = np.radians([roll_deg, pitch_deg])
    mx, my, mz = m_b
    Xh = mx * np.cos(th) + my * np.sin(phi) * np.sin(th) + mz * np.cos(phi) * np.sin(th)
    Yh = my * np.cos(phi) - mz * np.sin(phi)
    Zh = -mx * np.sin(th) + my * np.sin(phi) * np.cos(th) + mz * np.cos(phi) * np.cos(th)
    return Xh, Yh, Zh


def heading_tilt_compensated(m_b, roll_deg, pitch_deg, decl_deg=0.0):
    Xh, Yh, _ = horizontal_components(m_b, roll_deg, pitch_deg)
    return wrap360(np.degrees(np.arctan2(-Yh, Xh)) + decl_deg)


def heading_from_mag_accel(m_b, a_b, decl_deg=0.0, convention="specific_force"):
    r, p = roll_pitch_from_accel(a_b, convention)
    return heading_tilt_compensated(m_b, r, p, decl_deg)


def measured_dip_deg(m_b, roll_deg, pitch_deg):
    Xh, Yh, Zh = horizontal_components(m_b, roll_deg, pitch_deg)
    return float(np.degrees(np.arctan2(Zh, np.hypot(Xh, Yh))))

# --------------------------------------------------------------------------
# 5. Sensor error model
# --------------------------------------------------------------------------

def sensor_model(b_earth_ned, yaw_deg, pitch_deg, roll_deg, S=None, M=None,
                 b_interf_body=None, h_hard=None, noise_sigma=0.0, bias=None,
                 quant_lsb=None, temp_delta=0.0, temp_scale_coeff=0.0,
                 temp_offset_coeff=None, rng=None, n=1):
    """m = S M (C_nb b_earth + b_interf) * (1 + k_T dT) + h_hard + k_off dT + bias + noise, quantised.

    S: 3x3 soft-iron/scale matrix (default I). M: 3x3 misalignment / non-orthogonality (default I).
    Returns array (n,3).
    """
    C = dcm_nav_to_body(yaw_deg, pitch_deg, roll_deg)
    S = np.eye(3) if S is None else np.asarray(S, float)
    M = np.eye(3) if M is None else np.asarray(M, float)
    b_i = np.zeros(3) if b_interf_body is None else np.asarray(b_interf_body, float)
    h = np.zeros(3) if h_hard is None else np.asarray(h_hard, float)
    m = S @ M @ (C @ np.asarray(b_earth_ned, float) + b_i)
    m = m * (1.0 + temp_scale_coeff * temp_delta) + h
    if temp_offset_coeff is not None:
        m = m + np.asarray(temp_offset_coeff, float) * temp_delta
    if bias is not None:
        m = m + np.asarray(bias, float)
    out = np.tile(m, (n, 1))
    if noise_sigma > 0:
        rng = np.random.default_rng(0) if rng is None else rng
        out = out + rng.normal(0.0, noise_sigma, size=out.shape)
    if quant_lsb:
        out = np.round(out / quant_lsb) * quant_lsb
    return out


def bias_random_walk(n, dt, sigma_rw, rng):
    """Bias random walk: b_k = b_{k-1} + sigma_rw*sqrt(dt)*w_k  (sigma_rw in uT/sqrt(s))."""
    return np.cumsum(rng.normal(0.0, sigma_rw * np.sqrt(dt), size=(n, 3)), axis=0)


def gauss_markov_bias(n, dt, sigma_ss, tau, rng):
    """First-order Gauss-Markov bias (bias instability model), steady-state std sigma_ss."""
    a = np.exp(-dt / tau)
    q = sigma_ss * np.sqrt(1 - a * a)
    b = np.zeros((n, 3))
    b[0] = rng.normal(0, sigma_ss, 3)
    for k in range(1, n):
        b[k] = a * b[k - 1] + q * rng.normal(0, 1, 3)
    return b


def quantisation_sigma(lsb):
    return lsb / np.sqrt(12.0)


def heading_noise_sigma_deg(sigma_m, H):
    """Small-angle heading noise from isotropic per-axis noise sigma_m in level plane: sigma_psi = sigma_m/H rad."""
    return float(np.degrees(sigma_m / H))


def hard_iron_error_exact_deg(psi_deg, bx, by, H):
    """Exact level heading error from horizontal hard-iron (bx,by) in body axes."""
    p = np.radians(psi_deg)
    num = -(bx * np.sin(p) + by * np.cos(p))
    den = H + bx * np.cos(p) - by * np.sin(p)
    return np.degrees(np.arctan2(num, den))


def hard_iron_error_approx_deg(psi_deg, bx, by, H):
    """First order: delta psi ~ -(|b|/H) sin(psi + phi_b), phi_b = atan2(by, bx)."""
    b = np.hypot(bx, by)
    phib = np.arctan2(by, bx)
    return np.degrees(-(b / H) * np.sin(np.radians(psi_deg) + phib))


def hard_iron_max_error_deg(b, H):
    """Max |error| over all headings = asin(b/H) for b < H; 180 deg possible if b >= H."""
    return float(np.degrees(np.arcsin(b / H))) if b < H else 180.0


def soft_iron_error_approx_deg(psi_deg, E):
    """First order level heading error for horizontal m = (I+E) m_true (E 2x2 small).

    delta psi ~ (e12-e21)/2 + (e22-e11)/2 sin 2psi - (e12+e21)/2 cos 2psi  (rad)
    """
    E = np.asarray(E, float)
    p = np.radians(psi_deg)
    d = (E[0, 1] - E[1, 0]) / 2 + (E[1, 1] - E[0, 0]) / 2 * np.sin(2 * p) - (E[0, 1] + E[1, 0]) / 2 * np.cos(2 * p)
    return np.degrees(d)


def soft_iron_error_exact_deg(psi_deg, E, H=1.0):
    E = np.asarray(E, float)
    p = np.radians(psi_deg)
    m = np.array([H * np.cos(p), -H * np.sin(p)])
    mm = (np.eye(2) + E) @ m
    return angle_diff(np.degrees(np.arctan2(-mm[1], mm[0])), psi_deg)


def tilt_error_approx_deg(psi_deg, incl_deg, droll_deg, dpitch_deg):
    """Level vehicle, attitude-estimate errors (droll, dpitch):
    delta psi ~ tan I (dphi cos psi - dtheta sin psi)."""
    p = np.radians(psi_deg)
    return np.tan(np.radians(incl_deg)) * (droll_deg * np.cos(p) - dpitch_deg * np.sin(p))

# --------------------------------------------------------------------------
# 6. Interference
# --------------------------------------------------------------------------

def dipole_field(m_vec, r_vec):
    """B = mu0/(4 pi r^3) [3 (m.rhat) rhat - m]  (SI: A m^2, m -> T)."""
    r_vec = np.asarray(r_vec, float)
    m_vec = np.asarray(m_vec, float)
    r = np.linalg.norm(r_vec)
    rh = r_vec / r
    return MU0 / (4 * np.pi * r ** 3) * (3 * np.dot(m_vec, rh) * rh - m_vec)


def wire_field_magnitude(I, r):
    """Infinite straight wire |B| = mu0 I / (2 pi r)  (T)."""
    return MU0 * I / (2 * np.pi * r)


def magnitude_check(m_b, F_expected, tol_frac):
    return abs(np.linalg.norm(m_b) - F_expected) <= tol_frac * F_expected


def dip_check(m_b, roll_deg, pitch_deg, I_expected_deg, tol_deg):
    return abs(measured_dip_deg(m_b, roll_deg, pitch_deg) - I_expected_deg) <= tol_deg

# --------------------------------------------------------------------------
# 7. Calibration
# --------------------------------------------------------------------------

def fit_ellipsoid(samples):
    """Algebraic least-squares ellipsoid fit.

    Model: a x^2 + b y^2 + c z^2 + 2f yz + 2g xz + 2h xy + 2p x + 2q y + 2r z = 1.
    Returns (offset h, W) with calibrated  m_cal = W (m - h), |m_cal| ~ field radius,
    W symmetric positive definite (rotation ambiguity resolved as symmetric).
    Also returns radius estimate.
    """
    X = np.asarray(samples, float)
    x, y, z = X.T
    D = np.column_stack([x * x, y * y, z * z, 2 * y * z, 2 * x * z, 2 * x * y, 2 * x, 2 * y, 2 * z])
    v, *_ = np.linalg.lstsq(D, np.ones(len(X)), rcond=None)
    A = np.array([[v[0], v[5], v[4]], [v[5], v[1], v[3]], [v[4], v[3], v[2]]])
    bv = v[6:9]
    center = -np.linalg.solve(A, bv)
    k = 1.0 + center @ A @ center
    Q = A / k                     # (m-h)^T Q (m-h) = 1
    w, V = np.linalg.eigh(Q)
    if np.any(w <= 0):
        raise ValueError("fit is not an ellipsoid (insufficient orientation coverage?)")
    sqrtQ = V @ np.diag(np.sqrt(w)) @ V.T  # unit-sphere mapping
    radius = float(np.mean(np.linalg.norm((X - center) @ sqrtQ.T, axis=1)))
    # scale so output magnitude equals geometric mean radius of ellipsoid
    r_geo = float(np.prod(1 / np.sqrt(w)) ** (1 / 3))
    W = sqrtQ * r_geo
    return center, W, r_geo


def apply_calibration(m, h, W):
    return (np.asarray(m, float) - h) @ np.asarray(W).T


def fit_deviation_curve(psi_deg, dev_deg):
    """Least squares delta(psi) = A + B sin psi + C cos psi + D sin 2psi + E cos 2psi."""
    p = np.radians(np.asarray(psi_deg, float))
    G = np.column_stack([np.ones_like(p), np.sin(p), np.cos(p), np.sin(2 * p), np.cos(2 * p)])
    coef, *_ = np.linalg.lstsq(G, np.asarray(dev_deg, float), rcond=None)
    return coef


def eval_deviation_curve(coef, psi_deg):
    p = np.radians(np.asarray(psi_deg, float))
    A, B, C, D, E = coef
    return A + B * np.sin(p) + C * np.cos(p) + D * np.sin(2 * p) + E * np.cos(2 * p)

# --------------------------------------------------------------------------
# 8. Kinematics: heading vs track, distance vs displacement, position
# --------------------------------------------------------------------------

def ground_velocity(heading_deg, airspeed, wind_to_deg, wind_speed, sideslip_deg=0.0):
    """v_ground = v_air (along heading + sideslip) + wind (direction wind blows TOWARD)."""
    h = np.radians(heading_deg + sideslip_deg)
    w = np.radians(wind_to_deg)
    return np.array([airspeed * np.cos(h) + wind_speed * np.cos(w),
                     airspeed * np.sin(h) + wind_speed * np.sin(w)])


def track_and_speed(v_ne):
    return wrap360(np.degrees(np.arctan2(v_ne[1], v_ne[0]))), float(np.hypot(*v_ne))


def crab_angle(heading_deg, track_deg):
    """Drift/crab angle = track - heading, (-180,180]."""
    return angle_diff(track_deg, heading_deg)


def path_length(points):
    P = np.asarray(points, float)
    return float(np.sum(np.linalg.norm(np.diff(P, axis=0), axis=1)))


def displacement(points):
    P = np.asarray(points, float)
    d = P[-1] - P[0]
    return float(np.linalg.norm(d)), wrap360(np.degrees(np.arctan2(d[1], d[0])))


def dead_reckon_flat(p0_ne, speeds, tracks_deg, dt):
    """N_k+1 = N_k + v cos(chi) dt, E_k+1 = E_k + v sin(chi) dt (rectangle rule)."""
    chi = np.radians(np.asarray(tracks_deg, float))
    v = np.asarray(speeds, float) * np.ones_like(chi)
    dN = np.cumsum(v * np.cos(chi) * dt)
    dE = np.cumsum(v * np.sin(chi) * dt)
    return np.column_stack([p0_ne[0] + np.r_[0, dN], p0_ne[1] + np.r_[0, dE]])


def radii_wgs84(lat_deg):
    """Meridian radius M and prime-vertical radius N (m)."""
    s2 = np.sin(np.radians(lat_deg)) ** 2
    w = 1 - WGS84_E2 * s2
    return WGS84_A * (1 - WGS84_E2) / w ** 1.5, WGS84_A / np.sqrt(w)


def dead_reckon_wgs84(lat0, lon0, h, speeds, tracks_deg, dt):
    """phi' = v_N/(M+h), lambda' = v_E/((N+h) cos phi), Euler integration."""
    lat, lon = np.radians(lat0), np.radians(lon0)
    for v, chi in zip(np.atleast_1d(speeds) * np.ones(len(np.atleast_1d(tracks_deg))), np.atleast_1d(tracks_deg)):
        M, N = radii_wgs84(np.degrees(lat))
        c = np.radians(chi)
        lat_new = lat + v * np.cos(c) * dt / (M + h)
        lon = lon + v * np.sin(c) * dt / ((N + h) * np.cos(lat))
        lat = lat_new
    return float(np.degrees(lat)), float(np.degrees(lon))


def haversine(lat1, lon1, lat2, lon2, R=R_MEAN):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    return float(R * c), float(c)


def initial_bearing(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    y = np.sin(dl) * np.cos(p2)
    x = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl)
    return wrap360(np.degrees(np.arctan2(y, x)))


def rhumb_line(lat1, lon1, lat2, lon2, R=R_MEAN):
    """Spherical rhumb line: (distance, constant course deg)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(wrap180(lon2 - lon1))
    dpsi = np.log(np.tan(np.pi / 4 + p2 / 2) / np.tan(np.pi / 4 + p1 / 2))
    q = dp / dpsi if abs(dpsi) > 1e-12 else np.cos(p1)
    d = np.hypot(dp, q * dl) * R
    course = wrap360(np.degrees(np.arctan2(dl, dpsi)))
    return float(d), course


def cross_track_from_heading_bias(d, dpsi_deg):
    """Straight leg of length d flown with constant heading/track error dpsi:
    cross-track = d sin dpsi, along-track = d cos dpsi, total = 2 d sin(dpsi/2)."""
    e = np.radians(dpsi_deg)
    return float(d * np.sin(e)), float(d * np.cos(e)), float(2 * d * np.sin(e / 2))


def dr_crosstrack_rms_white(v, dt, n_steps, sigma_psi_deg):
    """RMS cross-track after n steps with independent per-step heading errors (small angle):
    sqrt(n) * v dt * sigma_psi."""
    return float(np.sqrt(n_steps) * v * dt * np.radians(sigma_psi_deg))


def heading_noise_monte_carlo(psi_deg, F, incl_deg, sigma_m, n, seed=0, roll=0.0, pitch=0.0):
    rng = np.random.default_rng(seed)
    b = earth_field_ned(F, incl_deg)
    m = sensor_model(b, psi_deg, pitch, roll, noise_sigma=sigma_m, rng=rng, n=n)
    psi = np.array([heading_tilt_compensated(mi, roll, pitch) for mi in m])
    return error_stats(psi, psi_deg)
