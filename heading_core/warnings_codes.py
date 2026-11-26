"""Warning codes emitted in HeadingEstimate["warnings"].

The contract only says warnings is an array of strings; these codes are proposed by T2
(pending PM confirmation in TRACKER.md). They are stable, upper-snake-case identifiers.
"""
WARN_NOT_CALIBRATED = "NOT_CALIBRATED"          # no calibration applied (raw field used)
WARN_FIELD_MAGNITUDE = "FIELD_MAGNITUDE_OUT_OF_RANGE"  # |B| deviates from expected -> interference
WARN_TILT_TOO_LARGE = "TILT_TOO_LARGE"          # tilt beyond max_tilt_deg -> heading unreliable
WARN_NO_ACCEL = "NO_ACCEL"                      # no accel in sample -> heading assumes level
WARN_DIP_ANOMALY = "DIP_ANGLE_ANOMALY"          # inclination deviates from expected -> interference
WARN_HIGH_NOISE = "HIGH_NOISE"                  # short-term heading scatter above threshold
WARN_INVALID_MAG = "INVALID_MAG"                # non-finite or zero field / zero horizontal field: sample ignored

ALL_WARNINGS = (WARN_NOT_CALIBRATED, WARN_FIELD_MAGNITUDE, WARN_TILT_TOO_LARGE,
                WARN_NO_ACCEL, WARN_DIP_ANOMALY, WARN_HIGH_NOISE, WARN_INVALID_MAG)
