"""HeadingEstimator: Sample dict -> HeadingEstimate dict (contracts/heading_estimate.schema.json).

Pipeline (HEADING_MATH.md sections 6-8): calibrate -> roll/pitch -> tilt-comp heading (+declination)
-> wrap-safe smoothing (complementary filter with optional gyro propagation, or circular mean)
-> field / dip / tilt / noise checks -> quality in [0,1] + warnings.
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np

from .calibration import Calibration
from .config import CoreConfig
from .heading import (angle_diff_deg, heading_from_level, level_frame_field,
                      roll_pitch_from_accel, tilt_deg, wrap360)
from .warnings_codes import (WARN_DIP_ANOMALY, WARN_FIELD_MAGNITUDE, WARN_HIGH_NOISE,
                             WARN_NO_ACCEL, WARN_NOT_CALIBRATED, WARN_TILT_TOO_LARGE,
                             WARN_INVALID_MAG, WARN_MAG_STALE, WARN_SENSOR_STALE,
                             WARN_TIMESTAMP_STALE)


def _lin_quality(dev: float, tol: float) -> float:
    """Soft penalty 1 / (1 + (dev/tol)^2): 1 at dev=0, 0.5 at dev=tol, 0.2 at 2*tol."""
    if tol <= 0:
        return 1.0
    return float(1.0 / (1.0 + (dev / tol) ** 2))


class _FrozenTracker:
    """Tracks how long a vector channel has stayed within tol (per axis) of the run's first value."""

    def __init__(self):
        self.ref = None
        self.t0 = None
        self.n = 0

    def update(self, t: float, v: np.ndarray, tol: float, cfg, window_s: float | None = None) -> bool:
        if not np.all(np.isfinite(v)):
            self.ref, self.t0, self.n = None, None, 0
            return False
        if self.ref is None or np.max(np.abs(v - self.ref)) > tol:
            self.ref, self.t0, self.n = v.copy(), t, 1  # data changed -> recover immediately
            return False
        self.n += 1
        w = cfg.stale_window_s if window_s is None else window_s
        return (t - self.t0) >= w and self.n >= cfg.stale_min_samples


class _QuantMotion:
    """Motion evidence while a quantised mag reading stays bit-identical (D3)."""

    def __init__(self):
        self.ref = None
        self.t0 = None
        self.w_lp = None          # low-passed gyro vector, deg/s
        self.rp_lp = None         # low-passed accel (roll, pitch), deg
        self.rp_ref = None
        self.theta = 0.0

    def update(self, t, dt, m, gyro, rp, cfg):
        if dt is not None and dt > 0:
            if gyro is not None:
                a = dt / (cfg.quant_gyro_lp_tau_s + dt)
                self.w_lp = gyro.copy() if self.w_lp is None else self.w_lp + a * (gyro - self.w_lp)
            if rp is not None:
                a = dt / (cfg.quant_accel_lp_tau_s + dt)
                if self.rp_lp is None:
                    self.rp_lp = np.array(rp, dtype=float)
                else:
                    d = np.array([angle_diff_deg(rp[0], self.rp_lp[0]), rp[1] - self.rp_lp[1]])
                    self.rp_lp = self.rp_lp + a * d
        else:
            if gyro is not None and self.w_lp is None:
                self.w_lp = gyro.copy()
            if rp is not None and self.rp_lp is None:
                self.rp_lp = np.array(rp, dtype=float)
        if not np.all(np.isfinite(m)) or self.ref is None or not np.array_equal(m, self.ref):
            self.ref, self.t0, self.theta = m.copy(), t, 0.0       # mag changed: restart evidence
            self.rp_ref = None if self.rp_lp is None else self.rp_lp.copy()
            return 0.0, 0.0, 0.0
        if self.rp_ref is None and self.rp_lp is not None:
            self.rp_ref = self.rp_lp.copy()
        if gyro is not None and self.w_lp is not None and dt is not None and dt > 0:
            self.theta += max(0.0, float(np.linalg.norm(self.w_lp)) - cfg.quant_gyro_deadband_dps) * dt
        att = 0.0
        if self.rp_lp is not None and self.rp_ref is not None:
            att = max(abs(angle_diff_deg(self.rp_lp[0], self.rp_ref[0])), abs(self.rp_lp[1] - self.rp_ref[1]))
        return t - self.t0, self.theta, att


class HeadingEstimator:
    """Stateful heading estimator. One instance per data stream.

    Parameters
    ----------
    calibration : Calibration | None   None -> raw field used, NOT_CALIBRATED warning.
    declination_deg : float            east-positive; output heading is true if non-zero.
    config : CoreConfig | None         thresholds and filter settings (defaults if None).
    """

    def __init__(self, calibration: Calibration | None = None, declination_deg: float = 0.0,
                 config: CoreConfig | None = None):
        self.calibration = calibration
        self.declination_deg = float(declination_deg)
        self.config = config or CoreConfig()
        self.last_debug: dict = {}
        self._meta_quant_uT: float | None = None     # sticky per stream (meta may be on first line only)
        self._fc_mag_calibrated = None               # True / False / "unknown" / None (never reported)
        self._grid_ok = {q: True for q in self.config.infer_quant_candidates_uT}  # lattice inference state
        self._grid_n = 0
        self.reset()

    def reset(self) -> None:
        """Clear filter state (heading, window, noise history)."""
        self._psi: float | None = None
        self._t: float | None = None
        self._win: deque = deque(maxlen=max(1, self.config.window))
        self._innov: deque = deque(maxlen=max(2, self.config.noise_window))
        self._frozen = {"mag": _FrozenTracker(), "accel": _FrozenTracker(), "mag_exact": _FrozenTracker()}
        self._qmotion = _QuantMotion()
        self._t_last_seen: float | None = None

    def set_calibration(self, calibration: Calibration | None) -> None:
        self.calibration = calibration
        self.reset()

    def _infer_quant(self, m: np.ndarray):
        """Largest candidate step q such that every mag component seen so far is a multiple of q (within
        1e-6 uT). Sticky per estimator: once a reading falls off a grid, that grid is ruled out for good."""
        if not np.all(np.isfinite(m)):
            return None
        for q in self._grid_ok:
            if self._grid_ok[q]:
                r = m / q
                if np.max(np.abs(r - np.round(r))) * q > 1e-6:
                    self._grid_ok[q] = False
        self._grid_n += 1
        if self._grid_n < self.config.infer_quant_min_samples:
            return None
        ok = [q for q, v in self._grid_ok.items() if v]
        return max(ok) if ok else None

    # ------------------------------------------------------------------ main
    def update(self, sample: dict) -> dict:
        """Consume a Sample dict, return a HeadingEstimate dict.

        Keys used: t, source, mag_uT (required); accel_g, gyro_dps, fc_attitude_deg (optional).
        Tilt source priority: accel_g, else fc_attitude_deg roll/pitch, else level (+NO_ACCEL).
        """
        cfg = self.config
        warnings: list[str] = []
        t = float(sample["t"])
        m = np.asarray(sample["mag_uT"], dtype=float).reshape(3)

        meta = sample.get("meta") or {}
        if isinstance(meta, dict):
            mq = meta.get("mag_quant_uT")
            if isinstance(mq, (int, float)) and not isinstance(mq, bool) and math.isfinite(mq) and mq >= 0:
                self._meta_quant_uT = float(mq)
            if "fc_mag_calibrated" in meta:
                self._fc_mag_calibrated = meta["fc_mag_calibrated"]
        inferred = self._infer_quant(m) if cfg.infer_mag_quant else None
        quant = cfg.mag_quant_uT if cfg.mag_quant_uT is not None else (
            self._meta_quant_uT if self._meta_quant_uT is not None else inferred)
        quantised = quant is not None and quant >= cfg.quant_noise_ratio * cfg.expected_mag_noise_uT

        # 0. stale / frozen data (D1)
        if self._t_last_seen is not None and t < self._t_last_seen - cfg.max_dt_s:
            self.reset()  # large backward jump = new stream / replay restart, not staleness
        ts_stale = self._t_last_seen is not None and not (t > self._t_last_seen)
        dt_seen = None if (self._t_last_seen is None or ts_stale) else min(t - self._t_last_seen, cfg.max_dt_s)
        if not ts_stale:
            self._t_last_seen = t
        stale_q = 1.0
        if ts_stale:
            warnings.append(WARN_TIMESTAMP_STALE)
            stale_q *= cfg.timestamp_stale_quality_factor
        if cfg.stale_detection and not ts_stale:
            mag_frozen = self._frozen["mag"].update(t, m, cfg.stale_mag_tol_uT, cfg)
            acc_raw = sample.get("accel_g")
            if acc_raw is not None:
                acc_frozen = self._frozen["accel"].update(t, np.asarray(acc_raw, dtype=float).reshape(3),
                                                          cfg.stale_accel_tol_g, cfg)
            else:
                acc_frozen = True  # absent channel cannot contradict a frozen mag
            mag_exact = self._frozen["mag_exact"].update(t, m, 0.0, cfg, cfg.stale_quant_window_s)
            g_raw = sample.get("gyro_dps")
            gyro_v = None
            if g_raw is not None:
                try:
                    gyro_v = np.asarray(g_raw, dtype=float).reshape(3)
                    if not np.all(np.isfinite(gyro_v)):
                        gyro_v = None
                except (TypeError, ValueError):
                    gyro_v = None
            have_gyro = gyro_v is not None
            rp_acc = None
            if acc_raw is not None:
                try:
                    av = np.asarray(acc_raw, dtype=float).reshape(3)
                    if np.all(np.isfinite(av)) and abs(np.linalg.norm(av) - 1.0) <= cfg.quant_accel_1g_tol_g:
                        rp_acc = roll_pitch_from_accel(av, cfg.accel_convention)
                except (TypeError, ValueError):
                    rp_acc = None
            q_dur, q_theta, q_att = self._qmotion.update(t, dt_seen, m, gyro_v, rp_acc, cfg)
            quant_motion = quantised and (q_theta > cfg.quant_motion_threshold_deg
                                          or q_att > cfg.quant_motion_threshold_deg)
            self._qdebug = {"frozen_s": q_dur, "gyro_rot_deg": q_theta, "accel_att_change_deg": q_att,
                            "have_gyro": have_gyro}
            if mag_frozen and acc_frozen:
                warnings.append(WARN_SENSOR_STALE)
                stale_q *= cfg.sensor_stale_quality_factor
            elif quantised:
                # D3: a still sensor on a coarse grid repeats readings legitimately -> need motion evidence
                if quant_motion:
                    warnings.append(WARN_MAG_STALE)
                    stale_q *= max(cfg.mag_stale_quality_factor, cfg.quant_mag_stale_min_factor)
                elif not have_gyro and cfg.quant_nogyro_time_rule and mag_exact:
                    warnings.append(WARN_MAG_STALE)   # no-gyro fallback: warning only, quality not cut
            elif mag_frozen:
                warnings.append(WARN_MAG_STALE)
                stale_q *= cfg.mag_stale_quality_factor
        mag_finite = bool(np.all(np.isfinite(m)))
        if not mag_finite:
            m = np.zeros(3)
        # 1. calibration
        if self.calibration is not None:
            b = np.asarray(self.calibration.apply(m))
            calibrated = True
        else:
            b = m
            calibrated = False
            warnings.append(WARN_NOT_CALIBRATED)

        # 2. attitude (roll/pitch)
        have_tilt = True
        roll = pitch = 0.0
        accel = sample.get("accel_g")
        att = sample.get("fc_attitude_deg") or {}
        try:
            if accel is not None and np.all(np.isfinite(np.asarray(accel, dtype=float))):
                roll, pitch = roll_pitch_from_accel(accel, cfg.accel_convention)
            elif "roll" in att and "pitch" in att:
                roll, pitch = float(att["roll"]), float(att["pitch"])
            else:
                have_tilt = False
        except (ValueError, TypeError):
            have_tilt = False
        if not (math.isfinite(roll) and math.isfinite(pitch)):
            have_tilt = False
        if not have_tilt:
            roll = pitch = 0.0
            warnings.append(WARN_NO_ACCEL)
        tilt = tilt_deg(roll, pitch)
        if tilt > cfg.max_tilt_deg:
            warnings.append(WARN_TILT_TOO_LARGE)

        # 3. raw (unsmoothed) heading, field and dip
        xh, yh, zv = level_frame_field(b, roll, pitch)
        field = float(np.linalg.norm(b))
        b0 = cfg.expected_field_uT
        if (calibrated and cfg.prefer_calibration_field and self.calibration.field_uT):
            b0 = self.calibration.field_uT
        field_dev = abs(field / b0 - 1.0) if b0 > 0 else 0.0
        if field_dev > cfg.field_tolerance_frac:
            warnings.append(WARN_FIELD_MAGNITUDE)
        horiz = math.hypot(xh, yh)
        heading_valid = mag_finite and horiz > 1e-9
        if not heading_valid:
            warnings.append(WARN_INVALID_MAG)
            if WARN_FIELD_MAGNITUDE not in warnings:
                warnings.append(WARN_FIELD_MAGNITUDE)
        if heading_valid:
            psi_raw = heading_from_level(xh, yh, self.declination_deg)
        else:
            psi_raw = self._psi if self._psi is not None else 0.0
        dip = math.degrees(math.atan2(zv, horiz)) if field > 0 else 0.0
        q_dip = 1.0
        if cfg.expected_dip_deg is not None:
            ddip = abs(dip - cfg.expected_dip_deg)
            if ddip > cfg.dip_tolerance_deg:
                warnings.append(WARN_DIP_ANOMALY)
            q_dip = _lin_quality(ddip, cfg.dip_tolerance_deg)

        # 4. smoothing (wrap-safe). Invalid samples leave the filter state untouched.
        if not heading_valid:
            q_out = 0.0
            psi_hold = self._psi if self._psi is not None else 0.0
            self.last_debug = {"raw_mag_uT": np.asarray(sample["mag_uT"], dtype=float).tolist(),
                               "invalid": True}
            return {"t": t, "source": sample["source"], "heading_deg": wrap360(psi_hold),
                    "heading_raw_deg": wrap360(psi_hold), "roll_deg": float(roll),
                    "pitch_deg": float(pitch), "field_uT": field if math.isfinite(field) else 0.0,
                    "calibrated": calibrated, "quality": q_out, "warnings": warnings}
        q_field = _lin_quality(field_dev, cfg.field_tolerance_frac)
        if ts_stale and self._psi is not None:
            # repeated / out-of-order timestamp: report held heading, leave filter state untouched
            self.last_debug = {"timestamp_stale": True}
            return {"t": t, "source": sample["source"], "heading_deg": wrap360(self._psi),
                    "heading_raw_deg": wrap360(psi_raw), "roll_deg": float(roll), "pitch_deg": float(pitch),
                    "field_uT": field, "calibrated": calibrated,
                    "quality": float(min(1.0, max(0.0, q_field * stale_q))), "warnings": warnings}
        dt = None if self._t is None else t - self._t
        if dt is not None and (dt <= 0 or dt > cfg.max_dt_s):
            self.reset()
            dt = None
        psi_pred = self._psi
        if psi_pred is not None and dt is not None and cfg.use_gyro and sample.get("gyro_dps") is not None:
            p, q, r = (float(v) for v in sample["gyro_dps"])
            ph, th = math.radians(roll), math.radians(pitch)
            ct = math.cos(th)
            if abs(ct) > 1e-3:
                psi_dot = (q * math.sin(ph) + r * math.cos(ph)) / ct  # ZYX Euler yaw rate, deg/s
                psi_pred = wrap360(psi_pred + psi_dot * dt)
        innov = 0.0 if psi_pred is None else angle_diff_deg(psi_raw, psi_pred)
        mode = cfg.smoothing
        if mode == "none" or psi_pred is None:
            psi = psi_raw
        elif mode == "complementary":
            psi = wrap360(psi_pred + cfg.alpha * q_field * innov)  # de-weight disturbed field
        elif mode == "circular_mean":
            psi = psi_raw  # replaced below
        else:
            raise ValueError(f"unknown smoothing mode {mode!r}")
        if mode == "circular_mean":
            self._win.append(math.radians(psi_raw))
            s = sum(math.sin(a) for a in self._win)
            c = sum(math.cos(a) for a in self._win)
            psi = wrap360(math.degrees(math.atan2(s, c))) if (s or c) else psi_raw
            innov = angle_diff_deg(psi_raw, psi)
        if psi_pred is not None or mode == "circular_mean":
            self._innov.append(innov)
        self._psi, self._t = psi, t

        # 5. noise estimate (RMS innovation)
        noise = float(np.sqrt(np.mean(np.square(self._innov)))) if len(self._innov) >= 2 else 0.0
        if noise > cfg.noise_warn_deg:
            warnings.append(WARN_HIGH_NOISE)

        # 6. quality
        q = q_field
        q *= _lin_quality(tilt, cfg.max_tilt_deg)
        q *= q_dip
        q *= _lin_quality(noise, cfg.noise_warn_deg)
        if not calibrated:
            q *= cfg.uncalibrated_quality_factor
        if not have_tilt:
            q *= cfg.no_accel_quality_factor
        q *= stale_q
        if self._fc_mag_calibrated is True:
            q *= cfg.fc_mag_calibrated_quality_factor
        q = float(min(1.0, max(0.0, q)))

        self.last_debug = {"field_vec_uT": b.tolist(), "raw_mag_uT": m.tolist(), "dip_deg": dip,
                           "tilt_deg": tilt, "noise_deg": noise, "innovation_deg": innov,
                           "field_ref_uT": b0, "horizontal_uT": horiz,
                           "mag_quant_uT": quant, "quantised_mode": quantised,
                           "quant_motion": dict(getattr(self, "_qdebug", {})), "mag_quant_inferred_uT": inferred,
                           "fc_mag_calibrated": self._fc_mag_calibrated}
        return {
            "t": t,
            "source": sample["source"],
            "heading_deg": wrap360(psi),
            "heading_raw_deg": wrap360(psi_raw),
            "roll_deg": float(roll),
            "pitch_deg": float(pitch),
            "field_uT": field,
            "calibrated": calibrated,
            "quality": q,
            "warnings": warnings,
        }
