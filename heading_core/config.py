"""Configurable constants for heading_core.

Hardware numbers will be refined from docs/hardware/ (T1). Values here marked as placeholders
are NOT measured; see docs/math/HEADING_MATH.md section LIMITATIONS.
"""
from dataclasses import dataclass
from typing import Optional

NOMINAL_FIELD_UT = 50.0  # placeholder nominal Earth field magnitude (uT) until T1 / site value

# Accelerometer sign conventions accepted in Sample.accel_g (see HEADING_MATH.md section 2):
#   "specific_force": proper acceleration (what a physical accelerometer measures, ArduPilot style);
#                     level and at rest reads (0, 0, -1) g in the NED body frame.
#   "gravity":        gravity vector in body frame; level and at rest reads (0, 0, +1) g.
ACCEL_SPECIFIC_FORCE = "specific_force"
ACCEL_GRAVITY = "gravity"


@dataclass
class CoreConfig:
    """Estimator thresholds and filter settings.

    PROVISIONAL (until a hardware replay log exists, ARCHITECTURE.md 2026-11-27): all stale_* / quant_*
    thresholds, expected_mag_noise_uT and fc_mag_calibrated_quality_factor. They were chosen on synthetic
    data only and must be re-tuned on replayed RM3100 / Matek FC logs.
    """
    expected_field_uT: float = NOMINAL_FIELD_UT  # used when calibration has no fitted field radius
    prefer_calibration_field: bool = True        # use Calibration.field_uT as |B| reference if present
    field_tolerance_frac: float = 0.15           # warn if | |B|/B0 - 1 | > this
    expected_dip_deg: Optional[float] = None     # inclination, + = field points down (N hemisphere)
    dip_tolerance_deg: float = 5.0
    max_tilt_deg: float = 45.0                   # warn above this
    accel_convention: str = ACCEL_SPECIFIC_FORCE
    smoothing: str = "complementary"             # "complementary" | "circular_mean" | "none"
    alpha: float = 0.1                           # complementary filter: weight of mag per sample
    window: int = 10                             # circular-mean window (samples)
    use_gyro: bool = True                        # propagate with gyro (complementary mode) if present
    max_dt_s: float = 1.0                        # gaps longer than this reset the filter
    noise_window: int = 20                       # samples used for innovation RMS (noise) estimate
    noise_warn_deg: float = 3.0                  # innovation RMS above which HIGH_NOISE is raised
    # Frozen / stale data detection (D1). A channel is "frozen" while every axis of each new reading stays
    # within tol of the reading that started the frozen run. Flag after stale_window_s AND stale_min_samples.
    stale_detection: bool = True
    stale_window_s: float = 0.5
    stale_min_samples: int = 10
    stale_mag_tol_uT: float = 1e-6               # "near-identical": far below RM3100 noise (15 nT)
    stale_accel_tol_g: float = 1e-7
    sensor_stale_quality_factor: float = 0.05    # all present channels frozen (sharp drop)
    mag_stale_quality_factor: float = 0.3        # mag frozen, accel live (could be coarse mG quantisation)
    timestamp_stale_quality_factor: float = 0.05
    # Quantised sources (PM decision 2026-11-27). PROVISIONAL. Sample meta.mag_quant_uT (MSP: 0.1 uT) is
    # remembered per stream; mag_quant_uT here overrides it. If quant >= quant_noise_ratio * expected noise,
    # MAG_STALE requires bit-identical mag plus motion evidence (D3, see quant_motion_* below); its quality
    # factor is never below quant_mag_stale_min_factor. SENSOR_STALE / TIMESTAMP_STALE are unchanged.
    expected_mag_noise_uT: float = 0.015         # [DATASHEET] RM3100 noise @ CC=200 (15 nT); PROVISIONAL use
    mag_quant_uT: Optional[float] = None
    quant_noise_ratio: float = 3.0
    stale_quant_window_s: float = 5.0            # PROVISIONAL; used only by the no-gyro fallback (D3)
    # D3 (PM decision 2026-11-27), all PROVISIONAL: in quantised mode MAG_STALE needs *motion evidence* while the
    # mag stays bit-identical. Gyro evidence: theta = integral of max(0, |LP(omega)| - quant_gyro_deadband_dps) dt
    # since the mag last changed (LP = first-order low-pass, time constant quant_gyro_lp_tau_s). Accel evidence:
    # change of low-passed accel roll/pitch since the mag last changed, only while | |a| - 1 g | <= quant_accel_1g_tol_g.
    quant_motion_threshold_deg: float = 3.0
    quant_gyro_deadband_dps: float = 1.0         # > plausible residual gyro bias magnitude (e.g. 0.2 deg/s/axis)
    quant_gyro_lp_tau_s: float = 0.5
    quant_accel_lp_tau_s: float = 0.2
    quant_accel_1g_tol_g: float = 0.05
    # Opt-in (PM D3 decision 2026-11-27, default False): with no gyro, also raise MAG_STALE (warning only,
    # quality not cut) after stale_quant_window_s bit-identical. Default: no gyro -> accel-tilt evidence only.
    quant_nogyro_time_rule: bool = False
    infer_mag_quant: bool = True                 # PM-approved 2026-11-27. fallback when meta.mag_quant_uT is absent: detect a decimal
    infer_quant_candidates_uT: tuple = (1.0, 0.5, 0.1, 0.05, 0.01)  # grid (e.g. MSP mG) from the data. PROVISIONAL
    infer_quant_min_samples: int = 5
    quant_mag_stale_min_factor: float = 0.3      # PROVISIONAL
    # Single-calibration rule (ARCHITECTURE.md 2026-11-27): FC mag calibration must be neutral. If a sample
    # says meta.fc_mag_calibrated is True, our calibration is still applied (it is the only intended one) but
    # quality is multiplied by this factor, because the FC correction may change after our fit. PROVISIONAL.
    fc_mag_calibrated_quality_factor: float = 0.7
    uncalibrated_quality_factor: float = 0.5     # quality multiplier when NOT_CALIBRATED
    no_accel_quality_factor: float = 0.7         # quality multiplier when no tilt source
