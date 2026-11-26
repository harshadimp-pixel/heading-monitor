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
    uncalibrated_quality_factor: float = 0.5     # quality multiplier when NOT_CALIBRATED
    no_accel_quality_factor: float = 0.7         # quality multiplier when no tilt source
