"""Core simulator: produces Sample dicts (contracts/sample.schema.json) with source='sim'.

Signal chain per sample (body frame x fwd, y right, z down; uT):
  B_earth_body = R(roll,pitch,yaw)^T @ B_ned
  B_sensor     = W_soft @ B_earth_body + h_hard + k_motor * I(t) + n_env
  RM3100       : + sensor noise -> quantise to counts (gain @ cycle count) -> clip -> counts / gain
  accel_g      = R^T @ [0, 0, -1] + b_acc + n_acc       (specific force; level & still -> z = -1 g)
  gyro_dps     = body rates from Euler-angle derivatives + b_gyro + n_gyro
Truth heading = magnetic heading = wrap360(yaw_true - declination).
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Iterator, Optional
import numpy as np

from .earth import EarthField
from .rm3100 import RM3100Model, DATASHEET_SOURCE, max_3axis_rate_hz, is_datasheet_point, gain_label
from .rotations import dcm_body_to_ned, euler_rates_to_body_rates, wrap360, wrap180
from .scenarios import get_scenario

DISCLAIMER = ("SIMULATED DATA - not hardware characterisation. RM3100 constants are datasheet typicals "
              "(not per-unit); IMU/interference/environment constants are ASSUMED.")

# ASSUMED generic MEMS IMU figures (NOT measured on any Matek FC; see README LIMITATIONS)
ACCEL_NOISE_G = 0.003
ACCEL_BIAS_SIGMA_G = 0.01
GYRO_NOISE_DPS = 0.05
GYRO_BIAS_SIGMA_DPS = 0.3
FC_ATT_NOISE_DEG = 0.3
DEFAULT_MOTOR_K_UT_PER_A = (0.8, -0.4, 1.5)  # ASSUMED; ~35 uT at 20 A


@dataclass
class SimConfig:
    scenario: str = "static"
    rate_hz: float = 50.0
    duration_s: float = 60.0
    seed: int = 0
    cycle_count: int = 200
    field_total_uT: float = 50.0
    inclination_deg: float = 60.0
    declination_deg: float = 0.0
    hard_iron_uT: Optional[list] = None      # None -> scenario default
    soft_iron: Optional[list] = None         # None -> scenario default (3x3)
    motor_k_uT_per_A: list = field(default_factory=lambda: list(DEFAULT_MOTOR_K_UT_PER_A))
    env_noise_uT: Optional[float] = None     # None -> scenario default
    imu_noise_scale: Optional[float] = None  # None -> scenario default
    mag_noise_scale: float = 1.0
    emit_fc_attitude: bool = True


def _r(x, nd):
    return [round(float(v), nd) for v in x]


class Simulator:
    def __init__(self, cfg: SimConfig):
        if cfg.rate_hz <= 0 or cfg.duration_s < 0:
            raise ValueError("rate must be > 0 and duration >= 0")
        self.cfg = cfg
        self.scn = get_scenario(cfg.scenario)
        self.earth = EarthField(cfg.field_total_uT, cfg.inclination_deg, cfg.declination_deg)
        self.b_ned = self.earth.ned()
        self.hard = np.array(cfg.hard_iron_uT if cfg.hard_iron_uT is not None else self.scn.hard_iron_uT, float)
        self.soft = np.array(cfg.soft_iron if cfg.soft_iron is not None else self.scn.soft_iron, float).reshape(3, 3)
        self.motor_k = np.array(cfg.motor_k_uT_per_A, float)
        self.env_noise = self.scn.env_noise_uT if cfg.env_noise_uT is None else cfg.env_noise_uT
        self.imu_scale = self.scn.imu_noise_scale if cfg.imu_noise_scale is None else cfg.imu_noise_scale
        self.mag = RM3100Model(cfg.cycle_count, noise_scale=cfg.mag_noise_scale)
        # independent RNG streams so changing one model does not reshuffle the others
        ss = np.random.SeedSequence(int(cfg.seed))
        r_bias, self.r_mag, self.r_env, self.r_acc, self.r_gyr, self.r_fc = [np.random.default_rng(s) for s in ss.spawn(6)]
        self.acc_bias = r_bias.normal(0, ACCEL_BIAS_SIGMA_G, 3)
        self.gyr_bias = r_bias.normal(0, GYRO_BIAS_SIGMA_DPS, 3)
        self.n = int(round(cfg.duration_s * cfg.rate_hz))
        self.rate_ok = cfg.rate_hz <= max_3axis_rate_hz(cfg.cycle_count)

    def config_dict(self) -> dict:
        d = asdict(self.cfg)
        d.update({
            "hard_iron_uT": self.hard.tolist(), "soft_iron": self.soft.tolist(),
            "env_noise_uT": self.env_noise, "imu_noise_scale": self.imu_scale,
            "scenario_description": self.scn.description,
            "earth_field_ned_uT": _r(self.b_ned, 6),
            "rm3100": {"gain_lsb_per_uT": self.mag.gain, "noise_uT_1sigma": self.mag.noise_uT,
                       "field_range_uT": self.mag.field_range_uT,
                       "provisional": not is_datasheet_point(self.cfg.cycle_count),
                       "label": gain_label(self.cfg.cycle_count),
                       "source": DATASHEET_SOURCE,
                       "max_3axis_rate_hz": round(max_3axis_rate_hz(self.cfg.cycle_count), 1),
                       "rate_within_datasheet_max": self.rate_ok},
            "imu_bias_truth": {"accel_g": _r(self.acc_bias, 6), "gyro_dps": _r(self.gyr_bias, 6)},
            "accel_convention": "specific force, NED body: level & still -> [0, 0, -1] g",
        })
        return d

    def _attitude(self, t):
        return self.scn.attitude(t, self.cfg.duration_s)

    def _body_rates_dps(self, t):
        h = 1e-4
        a0 = np.array(self._attitude(t - h)); a1 = np.array(self._attitude(t + h))
        roll, pitch, _ = self._attitude(t)
        dr, dp, dy = (a1 - a0) / (2 * h)
        return euler_rates_to_body_rates(roll, pitch, dr, dp, dy)

    def sample(self, i: int) -> dict:
        cfg = self.cfg
        t = i / cfg.rate_hz
        roll, pitch, yaw = self._attitude(t)
        R = dcm_body_to_ned(roll, pitch, yaw)
        b_body = R.T @ self.b_ned
        current = float(self.scn.current(t, cfg.duration_s))
        b_sensor = self.soft @ b_body + self.hard + self.motor_k * current
        if self.env_noise > 0:
            b_sensor = b_sensor + self.r_env.normal(0, self.env_noise, 3)
        counts, mag_uT, saturated = self.mag.measure(b_sensor, self.r_mag)

        acc = R.T @ np.array([0.0, 0.0, -1.0]) + self.acc_bias + self.r_acc.normal(0, ACCEL_NOISE_G * self.imu_scale, 3)
        gyr = self._body_rates_dps(t) + self.gyr_bias + self.r_gyr.normal(0, GYRO_NOISE_DPS * self.imu_scale, 3)

        yaw_w = wrap360(yaw)
        s = {
            "t": round(t, 6),
            "source": "sim",
            "mag_uT": _r(mag_uT, 6),
            "mag_raw": counts,
            "rm3100_cycle_count": int(cfg.cycle_count),
            "accel_g": _r(acc, 6),
            "gyro_dps": _r(gyr, 5),
        }
        if cfg.emit_fc_attitude:
            # crude FC attitude estimate: truth + noise; yaw drifts with z-gyro bias (no compass fusion)
            fn = self.r_fc.normal(0, FC_ATT_NOISE_DEG, 3)
            s["fc_attitude_deg"] = {
                "roll": round(wrap180(roll + fn[0]), 4), "pitch": round(float(pitch + fn[1]), 4),
                "yaw": round(wrap360(yaw + self.gyr_bias[2] * t + fn[2]), 4)}
        s["truth"] = {
            "heading_deg": round(wrap360(yaw - cfg.declination_deg), 6),
            "roll_deg": round(wrap180(roll), 6),
            "pitch_deg": round(float(pitch), 6),
            "true_heading_deg": round(yaw_w, 6),
            "declination_deg": cfg.declination_deg,
            "earth_field_body_uT": _r(b_body, 6),
            "field_at_sensor_uT": _r(b_sensor, 6),
            "interference_uT": _r(b_sensor - b_body, 6),
            "motor_current_A": round(current, 4),
        }
        meta = {"scenario": cfg.scenario, "seed": int(cfg.seed), "i": i}
        if saturated:
            meta["rm3100_saturated"] = True
        if i == 0:
            meta["disclaimer"] = DISCLAIMER
            meta["sim_config"] = self.config_dict()
        s["meta"] = meta
        return s

    def __iter__(self) -> Iterator[dict]:
        for i in range(self.n):
            yield self.sample(i)


def generate(**kwargs) -> list[dict]:
    """Convenience: list of samples for a config given as keyword args of SimConfig."""
    return list(Simulator(SimConfig(**kwargs)))


def stream(sim: Simulator, fh, realtime: bool = False) -> int:
    n = 0
    t0 = time.monotonic()
    for s in sim:
        if realtime:
            delay = s["t"] - (time.monotonic() - t0)
            if delay > 0:
                time.sleep(delay)
        fh.write(json.dumps(s, separators=(",", ":")) + "\n")
        if realtime:
            fh.flush()
        n += 1
    fh.flush()
    return n
