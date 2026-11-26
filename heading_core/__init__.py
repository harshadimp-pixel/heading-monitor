"""heading_core: heading maths, calibration and filtering for the virtual heading monitor.

Public interface (see ARCHITECTURE.md):
    Calibration, tilt_compensated_heading, HeadingEstimator
Frames: body NED-style, x forward, y right, z down. Field in uT, accel in g, gyro in deg/s.
Heading: degrees clockwise from magnetic north (true north if declination given), range [0, 360).
"""
from .config import CoreConfig, NOMINAL_FIELD_UT
from .calibration import Calibration
from .heading import tilt_compensated_heading, roll_pitch_from_accel, wrap360, angle_diff_deg
from .estimator import HeadingEstimator
from .warnings_codes import (
    WARN_NOT_CALIBRATED, WARN_FIELD_MAGNITUDE, WARN_TILT_TOO_LARGE, WARN_NO_ACCEL,
    WARN_DIP_ANOMALY, WARN_HIGH_NOISE, ALL_WARNINGS,
)

__all__ = [
    "Calibration", "tilt_compensated_heading", "HeadingEstimator", "CoreConfig",
    "NOMINAL_FIELD_UT", "roll_pitch_from_accel", "wrap360", "angle_diff_deg",
    "WARN_NOT_CALIBRATED", "WARN_FIELD_MAGNITUDE", "WARN_TILT_TOO_LARGE", "WARN_NO_ACCEL",
    "WARN_DIP_ANOMALY", "WARN_HIGH_NOISE", "ALL_WARNINGS",
]
__version__ = "0.1.0"
