"""sim: virtual RM3100 + flight-controller IMU sensor simulator (task T3).

THIS IS A SIMULATION. Nothing produced by this package is hardware characterisation.
Every number it emits is [SIMULATED]; device constants are [DATASHEET] typicals (see rm3100.py),
[DERIVED-APPROX] between/outside table points, or explicitly ASSUMED values documented in sim/README.md.

Usage:  python -m sim --rate 50 --duration 60 --scenario yaw_spin --seed 1 [--out file.jsonl]
"""
from .rm3100 import RM3100Model, gain_lsb_per_uT, noise_nT, max_3axis_rate_hz, gain_label
from .earth import EarthField
from .scenarios import SCENARIOS, get_scenario
from .simulator import Simulator, SimConfig, generate

__all__ = [
    "RM3100Model", "gain_label", "gain_lsb_per_uT", "noise_nT", "max_3axis_rate_hz", "EarthField",
    "SCENARIOS", "get_scenario", "Simulator", "SimConfig", "generate",
]
__version__ = "0.1.0"
