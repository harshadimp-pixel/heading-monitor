"""Thin adapter around heading_core (T2), used ONLY through the ARCHITECTURE.md interface.

If heading_core is missing, or a method still raises NotImplementedError, the call is
served by app._stubs instead and the backend actually used is reported to the UI.
Any OTHER exception from the real module is surfaced as an error (never hidden by a stub).
"""
from __future__ import annotations

import logging
import threading

from . import _stubs

log = logging.getLogger("app.core")

try:  # interface: Calibration, HeadingEstimator (ARCHITECTURE.md)
    import heading_core as _hc
    _REAL_CAL = getattr(_hc, "Calibration", None)
    _REAL_EST = getattr(_hc, "HeadingEstimator", None)
except Exception as e:  # pragma: no cover - depends on T2 state
    log.warning("heading_core not importable (%s); using local stubs", e)
    _hc = _REAL_CAL = _REAL_EST = None

REAL = "heading_core"
STUB = "STUB"


class CoreAdapter:
    def __init__(self, declination_deg: float = 0.0):
        self.declination_deg = declination_deg
        self.lock = threading.Lock()
        self.cal_dict: dict | None = None
        self.cal_backend: str | None = None
        self.est_backend: str = "none"
        self._real_est = None
        self._stub_est = None
        self._build_estimators()

    # ------------------------------------------------------------ calibration
    def _real_cal_from_dict(self, d):
        if d is None or _REAL_CAL is None:
            return None
        try:
            return _REAL_CAL.from_dict(d)
        except NotImplementedError:
            return None

    def _build_estimators(self):
        d = self.cal_dict
        self._real_est = None
        if _REAL_EST is not None:
            try:
                real_cal = self._real_cal_from_dict(d)
                if d is not None and real_cal is None:
                    raise NotImplementedError("Calibration.from_dict not implemented")
                self._real_est = _REAL_EST(calibration=real_cal, declination_deg=self.declination_deg)
            except NotImplementedError:
                self._real_est = None
        stub_cal = _stubs.StubCalibration.from_dict(d) if d is not None else None
        self._stub_est = _stubs.StubHeadingEstimator(calibration=stub_cal,
                                                     declination_deg=self.declination_deg)

    def fit(self, samples_uT):
        """Returns (calibration dict, backend name). Does not apply it."""
        if _REAL_CAL is not None:
            try:
                cal = _REAL_CAL.fit(samples_uT)
                return cal.to_dict(), REAL
            except NotImplementedError:
                pass
        return _stubs.StubCalibration.fit(samples_uT).to_dict(), STUB

    def set_calibration(self, d: dict | None, backend: str | None):
        with self.lock:
            old = (self.cal_dict, self.cal_backend)
            self.cal_dict = d
            self.cal_backend = backend if d is not None else None
            try:
                self._build_estimators()
            except Exception:
                self.cal_dict, self.cal_backend = old  # keep previous calibration on bad input
                self._build_estimators()
                raise

    # ------------------------------------------------------------ estimate
    def update(self, sample: dict):
        """Returns (estimate dict or None, backend, error string or None)."""
        with self.lock:
            if self._real_est is not None:
                try:
                    est = self._real_est.update(sample)
                    self.est_backend = REAL
                    return est, REAL, None
                except NotImplementedError:
                    pass
                except Exception as e:  # real module bug: report, do not mask
                    self.est_backend = REAL
                    return None, REAL, f"heading_core error: {type(e).__name__}: {e}"
            try:
                est = self._stub_est.update(sample)
                self.est_backend = STUB
                return est, STUB, None
            except Exception as e:
                self.est_backend = STUB
                return None, STUB, f"stub estimator error: {type(e).__name__}: {e}"

    def info(self):
        return {"heading_core_importable": _hc is not None,
                "estimator_backend": self.est_backend,
                "calibration_backend": self.cal_backend,
                "declination_deg": self.declination_deg}
