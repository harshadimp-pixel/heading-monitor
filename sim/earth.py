"""Earth magnetic field model: a single constant vector set by total intensity F, inclination I
(positive = field points down, northern hemisphere) and declination D (positive = east of true north).

B_ned = F * [cos I cos D, cos I sin D, sin I]   (uT, NED, x = TRUE north)

ASSUMPTION: uniform, time-invariant field (no WMM/IGRF location model, no diurnal variation,
no local anomalies). Defaults (50 uT, 60 deg, 0 deg) are generic mid-latitude placeholders, not a site.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class EarthField:
    total_uT: float = 50.0
    inclination_deg: float = 60.0
    declination_deg: float = 0.0

    def ned(self) -> np.ndarray:
        inc, dec = np.radians(self.inclination_deg), np.radians(self.declination_deg)
        return self.total_uT * np.array([np.cos(inc) * np.cos(dec), np.cos(inc) * np.sin(dec), np.sin(inc)])

    def horizontal_uT(self) -> float:
        return float(self.total_uT * np.cos(np.radians(self.inclination_deg)))
