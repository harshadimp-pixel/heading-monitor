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
WARN_SENSOR_STALE = "SENSOR_STALE"              # mag (and accel, if present) frozen for >= stale_window_s: data not live (D1)
WARN_MAG_STALE = "MAG_STALE"                    # mag frozen for >= stale_window_s while accel still changes
WARN_TIMESTAMP_STALE = "TIMESTAMP_STALE"        # sample time did not advance (t <= previous t); sample not used
WARN_INVALID_MAG = "INVALID_MAG"                # non-finite or zero field / zero horizontal field: sample ignored

ALL_WARNINGS = (WARN_NOT_CALIBRATED, WARN_FIELD_MAGNITUDE, WARN_TILT_TOO_LARGE,
                WARN_NO_ACCEL, WARN_DIP_ANOMALY, WARN_HIGH_NOISE, WARN_INVALID_MAG, WARN_SENSOR_STALE, WARN_MAG_STALE, WARN_TIMESTAMP_STALE)
