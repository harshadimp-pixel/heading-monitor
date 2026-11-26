"""firmware_bridge (T4): MSP telemetry from a Matek FC (INAV primary) -> Sample JSONL.

Public API:
    msp.MSPParser, msp.encode_v1/encode_v2/encode_v2_over_v1, msp.crc8_dvb_s2_bytes
    scaling.decode_raw_imu/decode_attitude/decode_sensor_compass, scaling.MAG_PROFILES
    sample.SampleBuilder, sample.validate_sample
    bridge.Poller, bridge.replay, fake_fc.FakeFC / FakeFCTransport
CLI: python -m firmware_bridge --port /dev/ttyACM0 --baud 115200 | --replay FILE | --fake-fc
"""
from . import msp, scaling, sample  # noqa: F401
from .msp import MSPFrame, MSPParser, crc8_dvb_s2_bytes, encode_v1, encode_v2, encode_v2_over_v1  # noqa: F401
from .sample import SampleBuilder, validate_sample  # noqa: F401

__all__ = ["msp", "scaling", "sample", "MSPParser", "MSPFrame", "SampleBuilder", "validate_sample",
           "encode_v1", "encode_v2", "encode_v2_over_v1", "crc8_dvb_s2_bytes"]
