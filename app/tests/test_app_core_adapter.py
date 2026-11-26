"""Adapter switches between heading_core (T2) and the local stub only on NotImplementedError."""
import pytest

from app import core_adapter as CA
from ._helpers import sample


class _NotYet:
    def __init__(self, *a, **k):
        pass

    def update(self, s):
        raise NotImplementedError

    @staticmethod
    def fit(x):
        raise NotImplementedError

    @staticmethod
    def from_dict(d):
        raise NotImplementedError


class _Broken(_NotYet):
    def update(self, s):
        raise ZeroDivisionError("bug")


def test_falls_back_to_stub_when_not_implemented(monkeypatch):
    monkeypatch.setattr(CA, "_REAL_EST", _NotYet)
    monkeypatch.setattr(CA, "_REAL_CAL", _NotYet)
    a = CA.CoreAdapter()
    est, backend, err = a.update(sample(0, 45))
    assert backend == CA.STUB and err is None and abs(est["heading_deg"] - 45) < 1e-6
    d, b = a.fit([sample(i, i * 7)["mag_uT"] for i in range(60)])
    assert b == CA.STUB and "offset" in d


def test_real_module_errors_are_surfaced_not_masked(monkeypatch):
    monkeypatch.setattr(CA, "_REAL_EST", _Broken)
    a = CA.CoreAdapter()
    est, backend, err = a.update(sample(0, 45))
    assert est is None and backend == CA.REAL and "ZeroDivisionError" in err


@pytest.mark.skipif(CA._REAL_EST is None, reason="heading_core not importable")
def test_uses_real_heading_core_when_implemented():
    a = CA.CoreAdapter()
    est, backend, err = a.update(sample(0, 123))
    if backend == CA.STUB:
        pytest.skip("heading_core.HeadingEstimator.update not implemented yet")
    assert err is None and abs(((est["heading_deg"] - 123 + 180) % 360) - 180) < 1.0
