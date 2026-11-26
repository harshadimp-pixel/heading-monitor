"""Hard/soft-iron magnetometer calibration by least-squares ellipsoid fit.

Model (HEADING_MATH.md section 5):  m = A b + o + n
    m  measured field (uT), b true field in body frame, o hard-iron offset, A distortion, n noise.
Correction:  b_cal = W (m - o),  W symmetric positive definite, det(W) = 1 so the geometric-mean
radius of the ellipsoid is preserved (field magnitude stays in uT and comparable to the Earth field).
"""
from __future__ import annotations

import numpy as np

_DICT_VERSION = 1


def _as_vec3(x) -> np.ndarray:
    v = np.asarray(x, dtype=float).reshape(-1)
    if v.shape != (3,):
        raise ValueError(f"expected 3-vector, got shape {np.shape(x)}")
    return v


class Calibration:
    """Calibrated field b_cal = W @ (m - offset).

    Attributes
    ----------
    offset : list[float]          hard-iron offset (3,) in uT
    soft_iron : list[list[float]] W, symmetric 3x3, det(W)=1 after fit (identity = hard-iron only)
    field_uT : float | None       fitted field radius (local |B| during calibration), uT
    residual_rms : float | None   RMS of (|b_cal| - field_uT) over the fit data, uT
    n_samples : int               number of samples used in the fit
    coverage : float | None       fraction of the 26 direction bins (cube faces/edges/corners) hit
    method : str                  "ellipsoid" | "sphere" | "identity" | "manual"
    """

    def __init__(self, offset=None, soft_iron=None, field_uT=None, residual_rms=None,
                 n_samples=0, coverage=None, method="manual"):
        self.offset = [0.0, 0.0, 0.0] if offset is None else [float(x) for x in _as_vec3(offset)]
        W = np.eye(3) if soft_iron is None else np.asarray(soft_iron, dtype=float)
        if W.shape != (3, 3):
            raise ValueError("soft_iron must be 3x3")
        self.soft_iron = W.tolist()
        self.field_uT = None if field_uT is None else float(field_uT)
        self.residual_rms = None if residual_rms is None else float(residual_rms)
        self.n_samples = int(n_samples)
        self.coverage = None if coverage is None else float(coverage)
        self.method = method

    # ------------------------------------------------------------------ apply
    def apply(self, mag_uT) -> list[float]:
        """Return calibrated field W (m - o) as a list of 3 floats (uT)."""
        m = _as_vec3(mag_uT)
        b = np.asarray(self.soft_iron) @ (m - np.asarray(self.offset))
        return [float(x) for x in b]

    def apply_many(self, mags_uT) -> np.ndarray:
        """Vectorised apply for an (N,3) array; returns (N,3) ndarray."""
        M = np.asarray(mags_uT, dtype=float).reshape(-1, 3)
        return (M - np.asarray(self.offset)) @ np.asarray(self.soft_iron).T

    # -------------------------------------------------------------------- fit
    @staticmethod
    def fit(samples_uT: list[list[float]], method: str = "ellipsoid") -> "Calibration":
        """Fit hard/soft iron from magnetometer samples covering many orientations.

        method="ellipsoid": 9-parameter general quadric (offset + symmetric soft iron).
                            Needs >= 9 well-spread samples (>= 100 recommended, all orientations).
        method="sphere":    4-parameter sphere fit (offset only, W = I). Needs >= 4 samples;
                            more robust when orientation coverage is poor (e.g. yaw-only spin).
        Raises ValueError for too few samples or a degenerate (non-ellipsoidal) fit.
        """
        X = np.asarray(samples_uT, dtype=float).reshape(-1, 3)
        X = X[np.all(np.isfinite(X), axis=1)]
        n = X.shape[0]
        # Condition the problem: centre and scale before fitting.
        mu = X.mean(axis=0) if n else np.zeros(3)
        s = float(np.sqrt(((X - mu) ** 2).sum(axis=1).mean())) if n else 0.0
        if method == "sphere":
            if n < 4 or s <= 0:
                raise ValueError("sphere fit needs >= 4 distinct samples")
            Y = (X - mu) / s
            # |y|^2 = 2 c.y + (r^2 - |c|^2)  -> linear in (c, k)
            D = np.column_stack([2 * Y, np.ones(n)])
            sol, *_ = np.linalg.lstsq(D, (Y ** 2).sum(axis=1), rcond=None)
            c_y, k = sol[:3], sol[3]
            r2 = k + c_y @ c_y
            if r2 <= 0:
                raise ValueError("degenerate sphere fit")
            offset = mu + s * c_y
            W = np.eye(3)
            R = s * np.sqrt(r2)
        elif method == "ellipsoid":
            if n < 9 or s <= 0:
                raise ValueError("ellipsoid fit needs >= 9 distinct samples (>=100 recommended)")
            Y = (X - mu) / s
            x, y, z = Y.T
            # a x^2 + b y^2 + c z^2 + 2d xy + 2e xz + 2f yz + 2g x + 2h y + 2i z = 1
            D = np.column_stack([x * x, y * y, z * z, 2 * x * y, 2 * x * z, 2 * y * z,
                                 2 * x, 2 * y, 2 * z])
            sv = np.linalg.svd(D, compute_uv=False)
            if sv[-1] < 1e-6 * sv[0]:
                raise ValueError("ellipsoid fit is rank-deficient: samples do not span 3-D "
                                 "(e.g. yaw-only spin); rotate through all orientations or use "
                                 "method='sphere'")
            p, *_ = np.linalg.lstsq(D, np.ones(n), rcond=None)
            a, b, c, d, e, f, g, h, i = p
            Mq = np.array([[a, d, e], [d, b, f], [e, f, c]])
            gv = np.array([g, h, i])
            try:
                c_y = -np.linalg.solve(Mq, gv)
            except np.linalg.LinAlgError as exc:
                raise ValueError("degenerate ellipsoid fit (singular quadric)") from exc
            k = 1.0 + c_y @ Mq @ c_y
            Q = Mq / k                       # (y - c)^T Q (y - c) = 1
            evals, evecs = np.linalg.eigh(Q)
            if k <= 0 or np.any(evals <= 0):
                raise ValueError("fit is not an ellipsoid (insufficient orientation coverage?)")
            # back to uT units: (m - o)^T (Q / s^2) (m - o) = 1
            evals_uT = evals / s ** 2
            sqrtQ = evecs @ np.diag(np.sqrt(evals_uT)) @ evecs.T
            R = float(np.prod(evals_uT) ** (-1.0 / 6.0))  # geometric-mean radius = det(sqrtQ)^(-1/3)
            W = R * sqrtQ                                  # det(W) = 1
            W = 0.5 * (W + W.T)
            offset = mu + s * c_y
        else:
            raise ValueError(f"unknown method {method!r}")

        cal = Calibration(offset=offset, soft_iron=W, field_uT=R, n_samples=n, method=method)
        B = cal.apply_many(X)
        mags = np.linalg.norm(B, axis=1)
        cal.residual_rms = float(np.sqrt(np.mean((mags - R) ** 2)))
        cal.coverage = direction_coverage(B)
        return cal

    # ---------------------------------------------------------- serialisation
    def to_dict(self) -> dict:
        """JSON-serialisable dict (plain floats/lists)."""
        return {
            "version": _DICT_VERSION,
            "method": self.method,
            "offset_uT": list(self.offset),
            "soft_iron": [list(r) for r in self.soft_iron],
            "field_uT": self.field_uT,
            "residual_rms_uT": self.residual_rms,
            "n_samples": self.n_samples,
            "coverage": self.coverage,
        }

    @staticmethod
    def from_dict(d) -> "Calibration":
        """Inverse of to_dict. Accepts also the short keys 'offset'/'soft_iron_matrix'."""
        if d is None:
            raise ValueError("calibration dict is None")
        ver = d.get("version", _DICT_VERSION)
        if ver != _DICT_VERSION:
            raise ValueError(f"unsupported calibration version {ver}")
        offset = d.get("offset_uT", d.get("offset"))
        W = d.get("soft_iron", d.get("soft_iron_matrix"))
        return Calibration(offset=offset, soft_iron=W, field_uT=d.get("field_uT"),
                           residual_rms=d.get("residual_rms_uT"), n_samples=d.get("n_samples", 0),
                           coverage=d.get("coverage"), method=d.get("method", "manual"))

    def __repr__(self) -> str:
        return (f"Calibration(method={self.method!r}, offset={np.round(self.offset, 3).tolist()}, "
                f"field_uT={self.field_uT}, residual_rms={self.residual_rms})")


def direction_coverage(vectors) -> float:
    """Fraction of 26 direction bins (sign pattern of each axis in {-,0,+}, thresh 0.38) hit.

    A crude orientation-coverage indicator for the calibration wizard: 1.0 means the sensor saw
    the field from every face, edge and corner direction of a cube.
    """
    V = np.asarray(vectors, dtype=float).reshape(-1, 3)
    norms = np.linalg.norm(V, axis=1)
    V = V[norms > 0] / norms[norms > 0, None]
    if V.size == 0:
        return 0.0
    q = np.where(V > 0.38, 1, np.where(V < -0.38, -1, 0))
    bins = {tuple(r) for r in q if any(r)}
    return len(bins) / 26.0
