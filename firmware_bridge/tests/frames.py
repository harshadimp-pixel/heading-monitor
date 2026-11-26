"""Hand-built MSP byte streams, written byte-by-byte from the protocol description
independently of firmware_bridge.msp (so encoder bugs cannot hide parser bugs)."""
import struct


def xor(bs):
    c = 0
    for b in bs:
        c ^= b
    return c


def crc8(bs):
    crc = 0
    for b in bs:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0xD5) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def v1(cmd, payload=b"", d=b">"):
    return b"$M" + d + bytes([len(payload), cmd]) + payload + bytes([xor(bytes([len(payload), cmd]) + payload)])


def v2(cmd, payload=b"", d=b">", flag=0):
    body = bytes([flag]) + struct.pack("<HH", cmd, len(payload)) + payload
    return b"$X" + d + body + bytes([crc8(body)])


RAW_IMU = struct.pack("<9h", 10, -20, 512, 1, -2, 30, 250, -123, 433)
ATT = struct.pack("<3h", 152, -205, 271)  # roll 15.2, pitch -20.5, yaw 271
COMPASS = struct.pack("<BIhhh", 0, 123456, 215, -100, 400)
