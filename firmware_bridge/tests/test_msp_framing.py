import random
import struct

import pytest

from firmware_bridge import msp
from . import frames as F


# ---- checksums ----------------------------------------------------------------------------
def test_v1_xor_known_vector():
    # MSP_ATTITUDE request, empty payload: checksum = 0 ^ 108 = 0x6C
    assert msp.encode_v1(108) == b"$M<\x00\x6c\x6c"
    assert msp.encode_v1(102) == b"$M<\x00\x66\x66"


def test_crc8_dvb_s2_known_vectors():
    # CRC-8/DVB-S2 catalogue check value: crc("123456789") == 0xBC
    assert msp.crc8_dvb_s2_bytes(b"123456789") == 0xBC
    assert msp.crc8_dvb_s2_bytes(b"") == 0
    # MSPv2 MSP_RAW_IMU request: flag 0, cmd 0x0066, size 0
    body = bytes([0, 0x66, 0, 0, 0])
    assert msp.encode_v2(102) == b"$X<" + body + bytes([F.crc8(body)])


def test_encoders_match_independent_builders():
    assert msp.encode_v1(102, F.RAW_IMU, ">") == F.v1(102, F.RAW_IMU)
    assert msp.encode_v2(108, F.ATT, ">") == F.v2(108, F.ATT)
    assert msp.encode_v2(0x1F04, F.COMPASS, "<") == F.v2(0x1F04, F.COMPASS, b"<")


def test_v2_over_v1_layout():
    fr = msp.encode_v2_over_v1(108, F.ATT, ">")
    assert fr[:3] == b"$M>" and fr[4] == 255 and fr[3] == 5 + len(F.ATT) + 1
    inner = fr[5:-1]
    assert inner[-1] == F.crc8(inner[:-1])
    assert fr[-1] == F.xor(fr[3:-1])


# ---- parser -------------------------------------------------------------------------------
def test_parse_v1_v2_and_tunnelled():
    p = msp.MSPParser()
    stream = F.v1(102, F.RAW_IMU) + F.v2(108, F.ATT) + msp.encode_v2_over_v1(102, F.RAW_IMU, ">")
    out = p.feed(stream)
    assert [(f.version, f.cmd, f.direction) for f in out] == [(1, 102, ">"), (2, 108, ">"), (21, 102, ">")]
    assert out[0].payload == F.RAW_IMU and out[1].payload == F.ATT and out[2].payload == F.RAW_IMU
    assert p.stats.bad_checksum == 0 and p.stats.garbage_bytes == 0


def test_byte_by_byte_partial_frames():
    p = msp.MSPParser()
    stream = F.v2(108, F.ATT) + F.v1(102, F.RAW_IMU)
    got = []
    for i in range(len(stream)):
        got += p.feed(stream[i:i + 1])
        if i < len(F.v2(108, F.ATT)) - 1:
            assert got == []
    assert [f.cmd for f in got] == [108, 102]


def test_random_chunking():
    rng = random.Random(1)
    stream = b"".join(F.v1(102, F.RAW_IMU) + F.v2(108, F.ATT) for _ in range(50))
    for _ in range(20):
        p, got, i = msp.MSPParser(), [], 0
        while i < len(stream):
            k = rng.randint(1, 37)
            got += p.feed(stream[i:i + k])
            i += k
        assert len(got) == 100


def test_garbage_and_resync():
    p = msp.MSPParser()
    stream = b"\x00\xffhello$$M$X?" + F.v1(108, F.ATT) + b"$Mz garbage" + F.v2(102, F.RAW_IMU)
    out = p.feed(stream)
    assert [f.cmd for f in out] == [108, 102]
    assert p.stats.garbage_bytes > 0


def test_bad_checksums_rejected_then_recovers():
    good = F.v1(108, F.ATT)
    bad1 = bytearray(good); bad1[-1] ^= 0x01
    good2 = F.v2(102, F.RAW_IMU)
    bad2 = bytearray(good2); bad2[10] ^= 0x40   # corrupt payload -> CRC mismatch
    p = msp.MSPParser()
    out = p.feed(bytes(bad1) + bytes(bad2) + good + good2)
    assert [f.cmd for f in out] == [108, 102]
    assert p.stats.bad_checksum == 2


def test_bad_inner_crc_in_tunnel_rejected():
    fr = bytearray(msp.encode_v2_over_v1(108, F.ATT, ">"))
    fr[-2] ^= 0xFF                                # break inner v2 crc
    fr[-1] = F.xor(fr[3:-1])                      # but keep outer xor valid
    p = msp.MSPParser()
    assert p.feed(bytes(fr)) == []
    assert p.stats.bad_checksum == 1


def test_error_frame():
    p = msp.MSPParser()
    (f,) = p.feed(F.v1(102, b"", b"!"))
    assert f.is_error and f.cmd == 102
    (g,) = p.feed(F.v2(102, b"", b"!"))
    assert g.is_error and g.version == 2
    assert p.stats.error_frames == 2


def test_jumbo_v1_frame():
    payload = bytes(range(256)) + b"xyz"
    fr = msp.encode_v1(116, payload, ">")
    assert fr[3] == 255 and struct.unpack_from("<H", fr, 5)[0] == len(payload)
    (f,) = msp.MSPParser().feed(fr)
    assert f.payload == payload


def test_oversize_length_is_dropped():
    p = msp.MSPParser(max_payload=64)
    hdr = b"$X>" + bytes([0]) + struct.pack("<HH", 102, 60000)
    out = p.feed(hdr + F.v1(108, F.ATT))
    assert [f.cmd for f in out] == [108] and p.stats.oversize == 1


def test_fuzz_never_accepts_corrupted_frames():
    rng = random.Random(7)
    good = F.v1(102, F.RAW_IMU)
    accepted_bad = 0
    for _ in range(2000):
        fr = bytearray(good)
        i = rng.randrange(3, len(fr))
        fr[i] ^= 1 << rng.randrange(8)        # single-bit error after the header magic
        for f in msp.MSPParser().feed(bytes(fr)):
            if f.payload != F.RAW_IMU or f.cmd != 102:
                accepted_bad += 1
    # XOR catches every single-bit error
    assert accepted_bad == 0


def test_unknown_version_rejected():
    with pytest.raises(ValueError):
        msp.encode(102, b"", 3)
    with pytest.raises(ValueError):
        msp.encode_v1(0x1F04)
