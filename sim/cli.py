"""Command line: python -m sim --rate 50 --duration 60 --scenario <name> [--seed N] [--out file.jsonl]"""
from __future__ import annotations
import argparse
import json
import sys

from .scenarios import SCENARIOS
from .simulator import SimConfig, Simulator, stream


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m sim", description=(
        "Virtual RM3100 + FC IMU simulator. Emits Sample JSONL (contracts/sample.schema.json), source='sim'. "
        "SIMULATION ONLY - not hardware characterisation."))
    p.add_argument("--scenario", default="static", choices=sorted(SCENARIOS))
    p.add_argument("--rate", type=float, default=50.0, help="sample rate, Hz (default 50)")
    p.add_argument("--duration", type=float, default=60.0, help="seconds (default 60)")
    p.add_argument("--seed", type=int, default=0, help="RNG seed; output is deterministic per seed (default 0)")
    p.add_argument("--out", help="write JSONL to this file instead of stdout")
    p.add_argument("--tee", action="store_true", help="with --out, also stream to stdout")
    p.add_argument("--realtime", action="store_true", help="pace output in wall-clock time")
    p.add_argument("--cycle-count", type=int, default=200, help="RM3100 cycle count (default 200)")
    p.add_argument("--field-total", type=float, default=50.0, help="Earth field total intensity, uT")
    p.add_argument("--inclination", type=float, default=60.0, help="deg, + = down")
    p.add_argument("--declination", type=float, default=0.0, help="deg, + = east")
    p.add_argument("--hard-iron", type=float, nargs=3, metavar=("X", "Y", "Z"), help="override, uT")
    p.add_argument("--soft-iron", type=float, nargs=9, metavar="W", help="override 3x3 row-major")
    p.add_argument("--motor-k", type=float, nargs=3, metavar=("X", "Y", "Z"), help="motor field uT per A")
    p.add_argument("--env-noise", type=float, help="extra field noise 1-sigma uT (override)")
    p.add_argument("--imu-noise-scale", type=float, help="IMU noise multiplier (override)")
    p.add_argument("--mag-noise-scale", type=float, default=1.0, help="RM3100 noise multiplier")
    p.add_argument("--output-mode", default="raw", choices=["raw", "dronecan", "msp"],
                   help="raw: RM3100 counts + uT (default). dronecan/msp: what the FC receives from a Matek "
                        "CAN-L4-3100 (AP_Periph): 80 Hz poll averaged, <=25 Hz, float16 Gauss or int16 mG; "
                        "sample-and-hold at --rate; no mag_raw")
    p.add_argument("--delivered-rate", type=float, default=25.0,
                   help="publish rate in delivered modes, Hz (AP_PERIPH_MAG_MAX_RATE = 25)")
    p.add_argument("--periph-poll", type=float, default=80.0,
                   help="RM3100 poll rate inside the module in delivered modes, Hz (ArduPilot driver: 80)")
    p.add_argument("--attitude", type=float, nargs=3, metavar=("ROLL", "PITCH", "YAW"),
                   help="hold this constant attitude (deg, yaw from true north) instead of the scenario's")
    p.add_argument("--misalignment", type=float, nargs=3, metavar=("RX", "RY", "RZ"),
                   help="mag axis misalignment rotation, deg (spec M term; default none)")
    p.add_argument("--mag-bias-gm", type=float, nargs=2, metavar=("SIGMA_UT", "TAU_S"),
                   help="first-order Gauss-Markov mag bias (spec b_rw term; default none)")
    p.add_argument("--imu-bias-scale", type=float, default=1.0, help="accel/gyro bias multiplier (0 = none)")
    p.add_argument("--no-fc-attitude", action="store_true", help="omit fc_attitude_deg")
    p.add_argument("--list-scenarios", action="store_true")
    p.add_argument("--describe", action="store_true", help="print resolved config JSON and exit")
    return p


def config_from_args(a) -> SimConfig:
    cfg = SimConfig(scenario=a.scenario, rate_hz=a.rate, duration_s=a.duration, seed=a.seed,
                    cycle_count=a.cycle_count, field_total_uT=a.field_total, inclination_deg=a.inclination,
                    declination_deg=a.declination, hard_iron_uT=a.hard_iron,
                    soft_iron=None if a.soft_iron is None else [a.soft_iron[0:3], a.soft_iron[3:6], a.soft_iron[6:9]],
                    env_noise_uT=a.env_noise, imu_noise_scale=a.imu_noise_scale,
                    mag_noise_scale=a.mag_noise_scale, emit_fc_attitude=not a.no_fc_attitude,
                    output_mode=a.output_mode, attitude_deg=a.attitude, misalignment_deg=a.misalignment, mag_bias_gm=a.mag_bias_gm, imu_bias_scale=a.imu_bias_scale, periph_poll_hz=a.periph_poll, delivered_rate_hz=a.delivered_rate)
    if a.motor_k is not None:
        cfg.motor_k_uT_per_A = list(a.motor_k)
    return cfg


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    if a.list_scenarios:
        for name, s in SCENARIOS.items():
            print(f"{name:20s} {s.description}")
        return 0
    try:
        sim = Simulator(config_from_args(a))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.describe:
        print(json.dumps(sim.config_dict(), indent=2))
        return 0
    if not sim.rate_ok:
        which = "--periph-poll" if sim.delivered else "--rate"
        print(f"warning: {which} exceeds the datasheet max 3-axis rate at cycle count "
              f"{a.cycle_count}; simulated anyway", file=sys.stderr)
    if sim.held_values:
        print(f"note: --rate {a.rate} Hz > delivered rate {a.delivered_rate} Hz; magnetometer values are "
              f"sample-and-hold (see meta.mag_fresh / meta.mag_age_s)", file=sys.stderr)
    try:
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                if a.tee:
                    class _Tee:
                        def write(self, x):
                            fh.write(x); sys.stdout.write(x)
                        def flush(self):
                            fh.flush(); sys.stdout.flush()
                    stream(sim, _Tee(), a.realtime)
                else:
                    stream(sim, fh, a.realtime)
        else:
            stream(sim, sys.stdout, a.realtime)
    except BrokenPipeError:
        try:
            sys.stdout = None
        except Exception:
            pass
        return 0
    return 0
