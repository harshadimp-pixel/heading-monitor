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
                             WARN_INVALID_MAG)


def _lin_quality(dev: float, tol: float) -> float:
    """Soft penalty 1 / (1 + (dev/tol)^2): 1 at dev=0, 0.5 at dev=tol, 0.2 at 2*tol."""
    if tol <= 0:
        return 1.0
    return float(1.0 / (1.0 + (dev / tol) ** 2))


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
        self.reset()

    def reset(self) -> None:
        """Clear filter state (heading, window, noise history)."""
        self._psi: float | None = None
        self._t: float | None = None
        self._win: deque = deque(maxlen=max(1, self.config.window))
        self._innov: deque = deque(maxlen=max(2, self.config.noise_window))

    def set_calibration(self, calibration: Calibration | None) -> None:
        self.calibration = calibration
        self.reset()

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
        q = float(min(1.0, max(0.0, q)))

        self.last_debug = {"field_vec_uT": b.tolist(), "raw_mag_uT": m.tolist(), "dip_deg": dip,
                           "tilt_deg": tilt, "noise_deg": noise, "innovation_deg": innov,
                           "field_ref_uT": b0, "horizontal_uT": horiz}
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
