"""Hard/soft-iron calibration (STUB - implementation in progress)."""
from __future__ import annotations


class Calibration:
    """Calibrated field b_cal = W @ (m - offset).

    offset: hard-iron offset (3,) in uT. soft_iron W: symmetric 3x3, normalised to preserve field radius.
    """

    def __init__(self, offset=None, soft_iron=None, field_uT=None, residual_rms=None, n_samples=0):
        self.offset = [0.0, 0.0, 0.0] if offset is None else list(offset)
        self.soft_iron = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]] if soft_iron is None else soft_iron
        self.field_uT = field_uT
        self.residual_rms = residual_rms
        self.n_samples = n_samples

    def apply(self, mag_uT) -> list[float]:
        raise NotImplementedError

    @staticmethod
    def fit(samples_uT: list[list[float]]) -> "Calibration":
        raise NotImplementedError

    def to_dict(self) -> dict:
        raise NotImplementedError

    @staticmethod
    def from_dict(d) -> "Calibration":
        raise NotImplementedError
