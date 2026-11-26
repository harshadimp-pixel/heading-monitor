"""MSP (MultiWii Serial Protocol) v1 / v2 framing, checksums and an incremental parser.

Framing (verified against INAV src/main/msp/msp_serial.c, see docs/firmware/FC_SETUP.md §6):

MSPv1:   '$' 'M' <dir> <size:u8> <cmd:u8> <payload[size]> <xor>
         xor = size ^ cmd ^ payload[0] ^ ... ^ payload[n-1]
         JUMBO: if size == 255 the real size follows as u16 LE (after cmd) and is
         included in the XOR (INAV mspSerialEncode, JUMBO_FRAME_SIZE_LIMIT = 255).
MSPv2:   '$' 'X' <dir> <flag:u8> <cmd:u16 LE> <size:u16 LE> <payload[size]> <crc8>
         crc8 = CRC-8/DVB-S2 (poly 0xD5, init 0) over flag..payload.
MSPv2-over-v1: a v1 frame with cmd = 255 (MSP_V2_FRAME) whose v1 payload is
         <flag><cmd:u16><size:u16><payload><crc8 v2>; outer v1 XOR covers everything.
<dir> is '<' (to FC / request), '>' (from FC / response) or '!' (error response).
Note: AP_Periph pushes unsolicited sensor frames (e.g. MSP2_SENSOR_COMPASS) with '<'
(ArduPilot libraries/AP_MSP/msp.cpp msp_serial_encode(is_request=true)), so the parser
accepts every direction and reports it.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

# Command ids (INAV src/main/msp/msp_protocol.h, msp_protocol_v2_sensor.h)
MSP_API_VERSION = 1
MSP_FC_VARIANT = 2
MSP_FC_VERSION = 3
MSP_CALIBRATION_DATA = 14   # read-only 'out' message (INAV fc_msp.c mspFcProcessOutCommand); 15 = SET, never sent
MSP_RAW_IMU = 102
MSP_RAW_GPS = 106   # read-only; only fixType/numSat are ever decoded, coordinates are dropped
MSP_ATTITUDE = 108
MSP_V2_FRAME = 255
MSP2_SENSOR_COMPASS = 0x1F04

DIR_TO_FC = ord("<")
DIR_FROM_FC = ord(">")
DIR_ERROR = ord("!")
_DIRS = (DIR_TO_FC, DIR_FROM_FC, DIR_ERROR)

JUMBO_FRAME_SIZE_LIMIT = 255
MAX_PAYLOAD = 4096  # sanity limit; INAV/BF buffers are far smaller


def crc8_dvb_s2(crc: int, byte: int) -> int:
    """One step of CRC-8/DVB-S2 (poly 0xD5), identical to INAV common/crc.c crc8_dvb_s2."""
    crc ^= byte
    for _ in range(8):
        crc = ((crc << 1) ^ 0xD5) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def crc8_dvb_s2_bytes(data: bytes, crc: int = 0) -> int:
    for b in data:
        crc = crc8_dvb_s2(crc, b)
    return crc


def xor_checksum(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b
    return c


def encode_v1(cmd: int, payload: bytes = b"", direction: str = "<") -> bytes:
    if not 0 <= cmd <= 255:
        raise ValueError("MSPv1 command must fit in one byte; use MSPv2 for larger ids")
    n = len(payload)
    if n >= JUMBO_FRAME_SIZE_LIMIT:
        body = bytes([JUMBO_FRAME_SIZE_LIMIT, cmd]) + struct.pack("<H", n) + payload
    else:
        body = bytes([n, cmd]) + payload
    return b"$M" + direction.encode() + body + bytes([xor_checksum(body)])


def _v2_body(cmd: int, payload: bytes, flag: int) -> bytes:
    return struct.pack("<BHH", flag, cmd, len(payload)) + payload


def encode_v2(cmd: int, payload: bytes = b"", direction: str = "<", flag: int = 0) -> bytes:
    body = _v2_body(cmd, payload, flag)
    return b"$X" + direction.encode() + body + bytes([crc8_dvb_s2_bytes(body)])


def encode_v2_over_v1(cmd: int, payload: bytes = b"", direction: str = "<", flag: int = 0) -> bytes:
    body = _v2_body(cmd, payload, flag)
    inner = body + bytes([crc8_dvb_s2_bytes(body)])
    return encode_v1(MSP_V2_FRAME, inner, direction)


def encode(cmd: int, payload: bytes = b"", version: int = 1, direction: str = "<") -> bytes:
    """version: 1 = MSPv1, 2 = MSPv2 native ('$X'), 21 = MSPv2 tunnelled in v1."""
    if version == 1:
        return encode_v1(cmd, payload, direction)
    if version == 2:
        return encode_v2(cmd, payload, direction)
    if version == 21:
        return encode_v2_over_v1(cmd, payload, direction)
    raise ValueError(f"unknown MSP version {version!r}")


@dataclass
class MSPFrame:
    version: int          # 1, 2 (native) or 21 (v2 over v1)
    direction: str        # '<', '>' or '!'
    cmd: int
    payload: bytes
    flag: int = 0

    @property
    def is_error(self) -> bool:
        return self.direction == "!"


@dataclass
class ParserStats:
    frames: int = 0
    garbage_bytes: int = 0
    bad_checksum: int = 0
    oversize: int = 0
    error_frames: int = 0


class MSPParser:
    """Incremental, resynchronising MSP v1/v2 parser.

    feed() accepts any chunking of the byte stream (single bytes, partial frames,
    several frames at once) and returns the complete, checksum-valid frames.
    On a bad checksum or malformed header it drops only the leading '$' and rescans,
    so a valid frame hidden inside garbage is still found.
    """

    def __init__(self, max_payload: int = MAX_PAYLOAD):
        self.buf = bytearray()
        self.max_payload = max_payload
        self.stats = ParserStats()

    def feed(self, data: bytes) -> list[MSPFrame]:
        self.buf.extend(data)
        out: list[MSPFrame] = []
        while True:
            res = self._try_parse()
            if res is None:
                break
            if isinstance(res, MSPFrame):
                self.stats.frames += 1
                if res.is_error:
                    self.stats.error_frames += 1
                out.append(res)
        return out

    def _drop(self, n: int) -> bool:
        del self.buf[:n]
        return True

    def _try_parse(self):
        """Return MSPFrame, True (made progress, no frame) or None (need more data)."""
        buf = self.buf
        start = buf.find(b"$")
        if start < 0:
            self.stats.garbage_bytes += len(buf)
            buf.clear()
            return None
        if start > 0:
            self.stats.garbage_bytes += start
            del buf[:start]
        if len(buf) < 3:
            return None
        proto, direction = buf[1], buf[2]
        if proto not in (ord("M"), ord("X")) or direction not in _DIRS:
            self.stats.garbage_bytes += 1
            return self._drop(1)
        d = chr(direction)
        if proto == ord("M"):
            return self._parse_v1(d)
        return self._parse_v2(d)

    def _parse_v1(self, d: str):
        buf = self.buf
        if len(buf) < 5:
            return None
        size, cmd = buf[3], buf[4]
        hdr = 5
        if size == JUMBO_FRAME_SIZE_LIMIT:
            if len(buf) < 7:
                return None
            size = struct.unpack_from("<H", buf, 5)[0]
            hdr = 7
        if size > self.max_payload:
            self.stats.oversize += 1
            return self._drop(1)
        total = hdr + size + 1
        if len(buf) < total:
            return None
        body = bytes(buf[3:hdr + size])
        if xor_checksum(body) != buf[hdr + size]:
            self.stats.bad_checksum += 1
            return self._drop(1)
        payload = bytes(buf[hdr:hdr + size])
        del buf[:total]
        if cmd == MSP_V2_FRAME:
            inner = self._unwrap_v2(payload, d)
            if inner is None:
                self.stats.bad_checksum += 1
                return True
            return inner
        return MSPFrame(1, d, cmd, payload)

    def _unwrap_v2(self, p: bytes, d: str):
        if len(p) < 6:
            return None
        flag, cmd, size = struct.unpack_from("<BHH", p, 0)
        if len(p) != 5 + size + 1:
            return None
        if crc8_dvb_s2_bytes(p[:5 + size]) != p[5 + size]:
            return None
        return MSPFrame(21, d, cmd, bytes(p[5:5 + size]), flag)

    def _parse_v2(self, d: str):
        buf = self.buf
        if len(buf) < 8:
            return None
        flag, cmd, size = struct.unpack_from("<BHH", buf, 3)
        if size > self.max_payload:
            self.stats.oversize += 1
            return self._drop(1)
        total = 8 + size + 1
        if len(buf) < total:
            return None
        if crc8_dvb_s2_bytes(bytes(buf[3:8 + size])) != buf[8 + size]:
            self.stats.bad_checksum += 1
            return self._drop(1)
        payload = bytes(buf[8:8 + size])
        del buf[:total]
        return MSPFrame(2, d, cmd, payload, flag)
