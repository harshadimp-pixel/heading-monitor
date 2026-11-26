"""PNI RM3100 magnetometer output model (counts <-> uT, gain/noise vs cycle count, saturation).

Device constants are the datasheet TYPICAL values [DATASHEET], taken from:
  - PNI "RM3100 & RM2100 Sensor Suite User Manual" (V16.0, rev. Dec 2022), Table 3-1 and Sec. 5.1
    https://www.pnisensor.com/wp-content/uploads/RM3100-RM2100-Sensor-Suite-User-Manual-V11.0.pdf
  - PNI "RM3100 Geomagnetic Sensor" sales sheet (3/11/2020)
    https://www.pnisensor.com/wp-content/uploads/PNI-Sensor-RM3100-Sales-Sheet.pdf

Cross-checked against T1's docs/hardware/FACTSHEET.md (commit bccda22, status DRAFT): the 50/100/200
table values, +/-800 uT range, default CC 200 and 24-bit two's-complement output all match.
Values at other cycle counts are NOT published by PNI; they are labelled [DERIVED-APPROX] (T1's label)
and flagged provisional in the output. Conditions: 3.0 V supply, 121 ohm Rb, 33 kohm R_EXT, room temp.

Model assumptions (see sim/README.md):
  * gain and noise piecewise-linearly interpolated between the 50/100/200 cycle-count table points;
    outside [50, 200] gain is extrapolated proportionally to cycle count (least-squares slope through
    origin of the table, ~0.3755 LSB/uT per cycle) and noise as 1/sqrt(cycle count) from the 200-cc point.
    These extrapolations are ASSUMED, not datasheet values.
  * "Noise" from the table is used as the per-axis 1-sigma white Gaussian noise (the datasheet does not
    state RMS vs peak); no 1/f noise, no temperature drift, no hysteresis/repeatability/linearity error.
  * Output is the 24-bit two's-complement result register; we clip at the monotonic field range
    (+/-800 uT per the user manual; the 2020 sales sheet lists +/-1100 uT) and at the 24-bit limits.
    Real sensors become non-monotonic beyond the range; we model it as hard clipping.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

DATASHEET_SOURCE = ("PNI RM3100/RM2100 User Manual V16.0 Table 3-1 (typical @3.0V, Rb=121ohm, Rext=33kohm); "
                    "matches docs/hardware/FACTSHEET.md (T1, DRAFT, commit bccda22)")

# [DATASHEET] typical values
CC_TABLE = np.array([50.0, 100.0, 200.0])
GAIN_TABLE_LSB_PER_UT = np.array([20.0, 38.0, 75.0])
NOISE_TABLE_NT = np.array([30.0, 20.0, 15.0])
MAX_SINGLE_AXIS_RATE_HZ = np.array([1600.0, 850.0, 440.0])  # divide by 3 for 3-axis
FIELD_RANGE_UT = 800.0          # monotonic range, user manual (sales sheet 2020 says 1100)
DEFAULT_CYCLE_COUNT = 200       # register default 0x00C8 (user manual Sec. 5.1)
RECOMMENDED_CC_RANGE = (30, 400)  # user manual Sec. 5.1: quantisation below ~30, noise-limited above ~400

COUNTS_MAX = 2 ** 23 - 1
COUNTS_MIN = -(2 ** 23)

# ASSUMED extrapolation constants derived from the table
_GAIN_SLOPE = float(np.dot(CC_TABLE, GAIN_TABLE_LSB_PER_UT) / np.dot(CC_TABLE, CC_TABLE))


def _check_cc(cc: int) -> None:
    if int(cc) != cc or cc < 1 or cc > 65535:
        raise ValueError(f"cycle count must be an integer in 1..65535, got {cc!r}")


def is_datasheet_point(cycle_count: int) -> bool:
    """True if gain/noise at this cycle count are published [DATASHEET] values (50, 100, 200)."""
    return float(cycle_count) in set(CC_TABLE.tolist())


def gain_label(cycle_count: int) -> str:
    """Evidence label: datasheet table point, or interpolated/extrapolated [DERIVED-APPROX]."""
    return "[DATASHEET]" if is_datasheet_point(cycle_count) else "[DERIVED-APPROX]"


def gain_lsb_per_uT(cycle_count: int) -> float:
    """Gain in LSB/uT. Table points exact; interpolated inside, extrapolated (ASSUMED) outside."""
    _check_cc(cycle_count)
    cc = float(cycle_count)
    if CC_TABLE[0] <= cc <= CC_TABLE[-1]:
        return float(np.interp(cc, CC_TABLE, GAIN_TABLE_LSB_PER_UT))
    return _GAIN_SLOPE * cc


def noise_nT(cycle_count: int) -> float:
    """Per-axis 1-sigma noise in nT (table interpolation; 1/sqrt(cc) extrapolation is ASSUMED)."""
    _check_cc(cycle_count)
    cc = float(cycle_count)
    if CC_TABLE[0] <= cc <= CC_TABLE[-1]:
        return float(np.interp(cc, CC_TABLE, NOISE_TABLE_NT))
    if cc < CC_TABLE[0]:
        return float(NOISE_TABLE_NT[0] * np.sqrt(CC_TABLE[0] / cc))
    return float(NOISE_TABLE_NT[-1] * np.sqrt(CC_TABLE[-1] / cc))


def max_3axis_rate_hz(cycle_count: int) -> float:
    """Approximate max 3-axis sample rate (single-axis table / 3). Outside table: ~ 1/cc (ASSUMED)."""
    _check_cc(cycle_count)
    cc = float(cycle_count)
    if CC_TABLE[0] <= cc <= CC_TABLE[-1]:
        single = float(np.interp(cc, CC_TABLE, MAX_SINGLE_AXIS_RATE_HZ))
    else:
        k = float(np.mean(CC_TABLE * MAX_SINGLE_AXIS_RATE_HZ))
        single = k / cc
    return single / 3.0


@dataclass
class RM3100Model:
    cycle_count: int = DEFAULT_CYCLE_COUNT
    field_range_uT: float = FIELD_RANGE_UT
    noise_scale: float = 1.0  # multiplier on datasheet noise (1.0 = datasheet typical)

    def __post_init__(self):
        _check_cc(self.cycle_count)
        self.gain = gain_lsb_per_uT(self.cycle_count)
        self.noise_uT = noise_nT(self.cycle_count) * 1e-3 * self.noise_scale

    def measure(self, field_uT, rng: np.random.Generator):
        """Field at the sensor (uT, body frame) -> (counts[int x3], mag_uT[x3], saturated[bool]).

        Adds sensor white noise, quantises to integer counts, clips to range/24-bit.
        mag_uT is counts / gain, i.e. exactly what a driver would report.
        """
        f = np.asarray(field_uT, dtype=float) + rng.normal(0.0, self.noise_uT, 3)
        counts = np.rint(f * self.gain)
        lim = min(np.floor(self.field_range_uT * self.gain), COUNTS_MAX)
        saturated = bool(np.any(np.abs(counts) > lim))
        counts = np.clip(counts, -lim, lim)
        counts = np.clip(counts, COUNTS_MIN, COUNTS_MAX).astype(np.int64)
        return [int(c) for c in counts], counts / self.gain, saturated

    def counts_to_uT(self, counts):
        return np.asarray(counts, dtype=float) / self.gain
