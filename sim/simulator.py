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
from . import delivery as dl

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
    attitude_deg: Optional[list] = None      # [roll, pitch, yaw_true] constant override of the scenario attitude
    misalignment_deg: Optional[list] = None  # [rx, ry, rz] small axis-misalignment rotation M (spec SPEC.md 5.1)
    mag_bias_gm: Optional[list] = None       # [sigma_ss_uT, tau_s] first-order Gauss-Markov mag bias (spec 5.1)
    imu_bias_scale: float = 1.0              # 0 -> no accel/gyro bias (draws are unchanged, only scaled)
    output_mode: str = "raw"                 # raw | dronecan | msp  (see sim/delivery.py)
    periph_poll_hz: float = dl.AP_RM3100_POLL_HZ
    delivered_rate_hz: float = dl.AP_PERIPH_MAG_MAX_RATE_HZ


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
        # spawn(7): children are keyed by index, so the first six streams are identical to earlier versions
        r_bias, self.r_mag, self.r_env, self.r_acc, self.r_gyr, self.r_fc, self.r_gm = [
            np.random.default_rng(s) for s in ss.spawn(7)]
        self.M = np.eye(3)
        if cfg.misalignment_deg is not None:
            rx, ry, rz = np.radians(cfg.misalignment_deg)
            Rx = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
            Ry = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
            Rz = np.array([[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]])
            self.M = Rz @ Ry @ Rx
        self.SM = self.soft @ self.M
        self._gm = None  # (t_last, bias) state of the Gauss-Markov bias
        self.acc_bias = r_bias.normal(0, ACCEL_BIAS_SIGMA_G, 3) * cfg.imu_bias_scale
        self.gyr_bias = r_bias.normal(0, GYRO_BIAS_SIGMA_DPS, 3) * cfg.imu_bias_scale
        self.n = int(round(cfg.duration_s * cfg.rate_hz))
        if cfg.output_mode not in dl.OUTPUT_MODES:
            raise ValueError(f"output_mode must be one of {dl.OUTPUT_MODES}, got {cfg.output_mode!r}")
        self.delivered = cfg.output_mode != "raw"
        if self.delivered:
            if cfg.cycle_count != dl.AP_RM3100_CYCLE_COUNT:
                raise ValueError("delivered modes model ArduPilot AP_Compass_RM3100, which forces cycle count 200; "
                                 "--cycle-count must be 200")
            self.rate_ok = cfg.periph_poll_hz <= max_3axis_rate_hz(cfg.cycle_count)
            self.held_values = cfg.rate_hz > cfg.delivered_rate_hz
        else:
            self.rate_ok = cfg.rate_hz <= max_3axis_rate_hz(cfg.cycle_count)
            self.held_values = False
        self._reset_publisher()

    def _reset_publisher(self):
        self.pub = None
        self._last_seq = None
        if self.delivered:
            self.pub = dl.PeriphPublisher(self.cfg.output_mode, self._periph_measure,
                                          self.cfg.periph_poll_hz, self.cfg.delivered_rate_hz)

    def _field(self, t):
        """(b_body, b_sensor_noiseless, current) at time t."""
        roll, pitch, yaw = self._attitude(t)
        b_body = dcm_body_to_ned(roll, pitch, yaw).T @ self.b_ned
        current = float(self.scn.current(t, self.cfg.duration_s))
        return b_body, self.SM @ b_body + self.hard + self.motor_k * current, current

    def _gm_bias(self, t):
        """First-order Gauss-Markov magnetometer bias, advanced to time t (sequential calls only)."""
        if not self.cfg.mag_bias_gm:
            return 0.0
        sig, tau = self.cfg.mag_bias_gm
        if self._gm is None or t < self._gm[0]:
            self._gm = (t, self.r_gm.normal(0.0, sig, 3))      # start in steady state
        else:
            dt = t - self._gm[0]
            a = np.exp(-dt / tau)
            self._gm = (t, a * self._gm[1] + sig * np.sqrt(1 - a * a) * self.r_gm.normal(0.0, 1.0, 3))
        return self._gm[1]

    def attitude_truth(self, t):
        """(roll, pitch, yaw_true) in degrees at time t, unrounded."""
        return self._attitude(t)

    def field_truth(self, t):
        """Unrounded (earth_field_body_uT, field_at_sensor_noiseless_uT, motor_current_A) at time t."""
        return self._field(t)

    def specific_force_truth(self, t):
        """Unrounded noise- and bias-free accelerometer specific force (g) at time t."""
        roll, pitch, yaw = self._attitude(t)
        return dcm_body_to_ned(roll, pitch, yaw).T @ np.array([0.0, 0.0, -1.0])

    def _periph_measure(self, t):
        """One RM3100 reading inside the simulated CAN-L4-3100 (poll tick at time t)."""
        _, b, _ = self._field(t)
        b = b + self._gm_bias(t)
        if self.env_noise > 0:
            b = b + self.r_env.normal(0, self.env_noise, 3)
        counts, _, sat = self.mag.measure(b, self.r_mag)
        return counts, sat

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
        for k in ("output_mode", "periph_poll_hz", "delivered_rate_hz", "attitude_deg", "imu_bias_scale",
                  "misalignment_deg", "mag_bias_gm"):
            d.pop(k, None)  # raw mode: keep first-line config byte-identical to pre-delivery-mode logs
        if self.cfg.attitude_deg is not None:
            d["attitude_deg"] = list(self.cfg.attitude_deg)
        if self.cfg.misalignment_deg is not None:
            d["misalignment_deg"] = list(self.cfg.misalignment_deg)
            d["misalignment_matrix"] = self.M.tolist()
        if self.cfg.mag_bias_gm:
            d["mag_bias_gm"] = list(self.cfg.mag_bias_gm)
        if self.cfg.imu_bias_scale != 1.0:
            d["imu_bias_scale"] = self.cfg.imu_bias_scale
        if self.delivered:
            d["output_mode"] = self.cfg.output_mode
            d["delivery"] = {
                "model": "Matek CAN-L4-3100 / ArduPilot AP_Periph (see sim/delivery.py for sources)",
                "periph_poll_hz": self.cfg.periph_poll_hz, "publish_rate_hz": self.cfg.delivered_rate_hz,
                "averaging": "mean of RM3100 polls since previous publish (AP_Compass accumulate/drain)",
                "encoding": ("DroneCAN uavcan.equipment.ahrs.MagneticFieldStrength float16 Gauss (libcanard rounding)"
                             if self.cfg.output_mode == "dronecan" else
                             "MSP2_SENSOR_COMPASS int16 milligauss (truncation toward zero)"),
                "msp_rate_note": "MSP rate <=25 Hz is INFERRED from AP_Periph source, not verified" if self.cfg.output_mode == "msp" else None,
                "sample_and_hold": self.held_values,
            }
        return d

    def _attitude(self, t):
        if self.cfg.attitude_deg is not None:
            r, p, y = self.cfg.attitude_deg
            return (float(r), float(p), float(y))
        return self.scn.attitude(t, self.cfg.duration_s)

    def _body_rates_dps(self, t):
        h = 1e-4
        a0 = np.array(self._attitude(t - h)); a1 = np.array(self._attitude(t + h))
        roll, pitch, _ = self._attitude(t)
        dr, dp, dy = (a1 - a0) / (2 * h)
        return euler_rates_to_body_rates(roll, pitch, dr, dp, dy)

    def sample(self, i: int) -> dict:
        """Sample i. Delivered modes are stateful: call with i = 0, 1, 2, ... in order (as __iter__ does)."""
        cfg = self.cfg
        t = i / cfg.rate_hz
        roll, pitch, yaw = self._attitude(t)
        R = dcm_body_to_ned(roll, pitch, yaw)
        b_body = R.T @ self.b_ned
        current = float(self.scn.current(t, cfg.duration_s))
        b_sensor = self.SM @ b_body + self.hard + self.motor_k * current
        held = None
        if i == 0:
            self._gm = None
        if not self.delivered:
            if self.cfg.mag_bias_gm:
                b_sensor = b_sensor + self._gm_bias(t)
            if self.env_noise > 0:
                b_sensor = b_sensor + self.r_env.normal(0, self.env_noise, 3)
            counts, mag_uT, saturated = self.mag.measure(b_sensor, self.r_mag)
        else:
            if i == 0:
                self._reset_publisher()
            held = self.pub.at(i * 1e6 / cfg.rate_hz)
            counts, mag_uT, saturated = None, held["mag_uT"], held["saturated"]

        acc = R.T @ np.array([0.0, 0.0, -1.0]) + self.acc_bias + self.r_acc.normal(0, ACCEL_NOISE_G * self.imu_scale, 3)
        gyr = self._body_rates_dps(t) + self.gyr_bias + self.r_gyr.normal(0, GYRO_NOISE_DPS * self.imu_scale, 3)

        yaw_w = wrap360(yaw)
        s = {
            "t": round(t, 6),
            "source": "sim",
            "mag_uT": _r(mag_uT, 6) if not self.delivered else [float(v) for v in mag_uT],
        }
        if not self.delivered:
            s["mag_raw"] = counts
            s["rm3100_cycle_count"] = int(cfg.cycle_count)
        s["accel_g"] = _r(acc, 6)
        s["gyro_dps"] = _r(gyr, 5)
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
        if self.delivered:
            meta["output_mode"] = cfg.output_mode
            meta["mag_seq"] = held["seq"]
            meta["mag_age_s"] = round((i * 1e6 / cfg.rate_hz - held["t_us"]) / 1e6, 6)
            meta["mag_fresh"] = held["seq"] != self._last_seq
            meta["mag_n_avg"] = held["n_avg"]
            meta["mag_sample_mid_s"] = round(held["t_mid_us"] / 1e6, 6)  # mean time of the averaged polls
            self._last_seq = held["seq"]
            # quantisation step of the delivered value (PM decision 2026-11-27: meta.mag_quant_uT)
            if cfg.output_mode == "msp":
                meta["mag_quant_uT"] = 0.1
            else:
                g = np.abs(np.asarray(mag_uT, np.float64)) / 100.0
                meta["mag_quant_uT"] = round(float(np.max(np.spacing(g.astype(np.float16)).astype(np.float64))) * 100.0, 9)
            if cfg.output_mode == "msp":
                meta["msp_mag_mG"] = [int(v) for v in held["wire"]]
                if held["overflow"]:
                    meta["msp_int16_overflow"] = True
            else:
                meta["dronecan_float16_bits"] = [int(v) for v in held["wire"]]
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
