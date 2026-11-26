"""HeadingEstimator (STUB - implementation in progress)."""
from __future__ import annotations
from .calibration import Calibration


class HeadingEstimator:
    def __init__(self, calibration: Calibration | None = None, declination_deg: float = 0.0, config=None):
        self.calibration = calibration
        self.declination_deg = declination_deg
        self.config = config

    def update(self, sample: dict) -> dict:
        """Consume a Sample dict, return a HeadingEstimate dict (contracts/heading_estimate.schema.json)."""
        raise NotImplementedError
