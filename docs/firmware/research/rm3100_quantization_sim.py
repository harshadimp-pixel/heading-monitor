#!/usr/bin/env python3
"""
RM3100 data-path quantization simulation (SYNTHETIC DATA ONLY).

Models, per the cited source code, how a synthetic magnetic field vector is
represented at each hop and what heading error the representation alone adds:

  A. RM3100 raw 24-bit count, CC=200, 75 LSB/uT       (PNI user manual Table 3-1)
  B. ArduPilot AP_Compass float mGauss = count/75*10  (AP_Compass_RM3100.cpp, _scaler)
  C. DroneCAN MagneticFieldStrength float16 Gauss     (Tools/AP_Periph/compass.cpp, DSDL 1001/1002)
  D. DroneCAN MagneticFieldStrengthHiRes float32 Gauss(DSDL 1043, AP_PERIPH_MAG_HIRES)
  E. int16 mGauss (MAVLink RAW_IMU/SCALED_IMU xmag, DataFlash MAG.MagX, MSP2_SENSOR_COMPASS)
     applied after path C (typical CAN node -> ArduPilot FC -> GCS)
  F. INAV native RM3100 driver: int16(count24 >> 8)  (inav compass_rm3100.c, issue #10746)

Heading is computed for a level sensor as atan2(-By, Bx) (NED body frame,
X forward, Y right). Tilt compensation, declination, calibration (offsets,
soft-iron, INAV magGain) and filtering are NOT modelled.

The field magnitude is a synthetic, illustrative value, not a location-specific
model output. Noise case uses the datasheet typical noise (15 nT @ CC200) as a
Gaussian sigma with a fixed seed. Results are deterministic.
"""
import json
import math
import sys

import numpy as np

GAIN_LSB_PER_UT = 75.0           # CC=200 (PNI manual Table 3-1; ArduPilot GAIN_CC200)
UT_TO_MGAUSS = 10.0               # 1 uT = 10 mGauss
NOISE_UT = 0.015                  # 15 nT typical noise @ CC200 (PNI manual Table 3-1)


def to_counts(b_ut):
    """uT -> signed 24-bit RM3100 count (rounded, clipped)."""
    c = np.rint(b_ut * GAIN_LSB_PER_UT)
    return np.clip(c, -(1 << 23), (1 << 23) - 1).astype(np.int64)


def path_values(b_ut):
    counts = to_counts(b_ut)
    ap_mgauss = counts.astype(np.float32) * np.float32((1.0 / GAIN_LSB_PER_UT) * UT_TO_MGAUSS)
    ga = ap_mgauss.astype(np.float32) * np.float32(0.001)
    can_f16_mg = ga.astype(np.float16).astype(np.float32) * np.float32(1000.0)
    can_f32_mg = ga.astype(np.float32) * np.float32(1000.0)
    int16_mg = np.clip(np.trunc(can_f16_mg), -32768, 32767)  # C int16 cast truncates toward zero
    # INAV: (int16)((count24 left-aligned in 32 bits) >> 16) == count >> 8 (arithmetic)
    inav_raw = (counts >> 8).astype(np.int16)
    inav_mg = inav_raw.astype(np.float64) * 256.0 / GAIN_LSB_PER_UT * UT_TO_MGAUSS
    return {
        "A_raw_counts": counts.astype(np.float64) / GAIN_LSB_PER_UT * UT_TO_MGAUSS,
        "B_ap_mgauss_f32": ap_mgauss.astype(np.float64),
        "C_dronecan_f16": can_f16_mg.astype(np.float64),
        "D_dronecan_hires_f32": can_f32_mg.astype(np.float64),
        "E_int16_mgauss_after_f16": int16_mg.astype(np.float64),
        "F_inav_native_int16": inav_mg,
    }


def heading_deg(bx, by):
    return np.degrees(np.arctan2(-by, bx)) % 360.0


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def run(h_ut, z_ut, noise=False, step=0.05, seed=1):
    psi = np.arange(0.0, 360.0, step)
    # Field in body frame for a level vehicle at true-magnetic heading psi
    bx = h_ut * np.cos(np.radians(psi))
    by = -h_ut * np.sin(np.radians(psi))
    bz = np.full_like(psi, z_ut)
    if noise:
        rng = np.random.default_rng(seed)
        bx = bx + rng.normal(0, NOISE_UT, psi.shape)
        by = by + rng.normal(0, NOISE_UT, psi.shape)
        bz = bz + rng.normal(0, NOISE_UT, psi.shape)
    px = path_values(bx)
    py = path_values(by)
    out = {}
    for k in px:
        e = wrap(heading_deg(px[k], py[k]) - psi)
        out[k] = {"max_abs_err_deg": float(np.max(np.abs(e))),
                  "rms_err_deg": float(np.sqrt(np.mean(e ** 2)))}
    return out


def step_table():
    """Representation step size (mGauss) near typical field components."""
    rows = []
    for mg in (50, 150, 250, 450, 600):
        g = np.float16(mg / 1000.0)
        f16_step = float(np.spacing(g)) * 1000.0
        rows.append({"component_mGauss": mg,
                     "rm3100_lsb_mGauss": round(UT_TO_MGAUSS / GAIN_LSB_PER_UT, 4),
                     "float16_step_mGauss": round(f16_step, 4),
                     "int16_step_mGauss": 1.0,
                     "inav_native_step_mGauss": round(256.0 / GAIN_LSB_PER_UT * UT_TO_MGAUSS, 2)})
    return rows


def main():
    cases = [
        {"name": "H=20uT Z=40uT, no noise", "h": 20.0, "z": 40.0, "noise": False},
        {"name": "H=20uT Z=40uT, 15 nT noise", "h": 20.0, "z": 40.0, "noise": True},
        {"name": "H=5uT Z=55uT (high latitude), no noise", "h": 5.0, "z": 55.0, "noise": False},
        {"name": "H=5uT Z=55uT (high latitude), 15 nT noise", "h": 5.0, "z": 55.0, "noise": True},
    ]
    results = {"step_table": step_table(), "cases": []}
    for c in cases:
        results["cases"].append({"case": c["name"], "paths": run(c["h"], c["z"], c["noise"])})
    json.dump(results, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
