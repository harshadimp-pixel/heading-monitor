"""Configurable constants. Hardware numbers will be updated from docs/hardware/ (T1)."""
from dataclasses import dataclass
from typing import Optional

NOMINAL_FIELD_UT = 50.0  # placeholder nominal Earth field magnitude until T1 lands


@dataclass
class CoreConfig:
    expected_field_uT: float = NOMINAL_FIELD_UT
    field_tolerance_frac: float = 0.15       # warn if | |B|/B0 - 1 | > this
    expected_dip_deg: Optional[float] = None  # inclination (+ down); None = learn/skip
    dip_tolerance_deg: float = 5.0
    max_tilt_deg: float = 45.0               # warn above this
    smoothing: str = "complementary"         # "complementary" | "circular_mean" | "none"
    alpha: float = 0.1                       # complementary-filter mag weight per sample
    window: int = 10                         # circular-mean window (samples)
    use_gyro: bool = True                    # fuse gyro for prediction if available
    noise_window: int = 20                   # samples for noise (circular std) estimate
    noise_warn_deg: float = 3.0              # circular std above which HIGH_NOISE
