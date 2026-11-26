"""M1-M3 MSP framing/robustness and source labelling. API discovered at Phase 2; skips until firmware_bridge lands."""
import random, pytest
from conftest import load
from msp_frames import v1, v2, raw_imu, attitude, crc8_dvb_s2

def test_frame_builder_selfcheck():
    # known vector: MSP_ATTITUDE v1 request "$M<" 0 108 -> checksum 108
    assert v1(108, direction=b"<") == b"$M<\x00\x6c\x6c"
    assert crc8_dvb_s2(b"") == 0

def _parser():
    fb = load("firmware_bridge")
    for name in ("MSPParser", "MspParser", "MSPDecoder", "Parser"):
        for mod in (fb, getattr(fb, "msp", None)):
            if mod is not None and hasattr(mod, name): return getattr(mod, name)
    pytest.skip("NOT RUN: firmware_bridge parser API not yet identified (adapt in Phase 2)")

def test_M1_M2_placeholder():
    _parser()  # Phase 2: decode v1/v2 RAW_IMU+ATTITUDE exactly; 10k fuzzed streams, 0 bad-checksum accepted
    pytest.skip("Phase 2: implement once parser API is known")
