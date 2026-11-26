"""T6 hand-built MSP frames from the public protocol description (MSPv1 XOR checksum, MSPv2 CRC8 DVB-S2)."""
import struct

def v1(cmd, payload=b"", direction=b">"):
    cs = len(payload) ^ cmd
    for b in payload: cs ^= b
    return b"$M" + direction + bytes([len(payload), cmd]) + payload + bytes([cs])

def crc8_dvb_s2(data):
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0xD5) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc

def v2(cmd, payload=b"", direction=b">", flag=0):
    body = bytes([flag]) + struct.pack("<HH", cmd, len(payload)) + payload
    return b"$X" + direction + body + bytes([crc8_dvb_s2(body)])

def raw_imu(acc=(0, 0, 512), gyro=(0, 0, 0), mag=(100, -50, 300)):
    return struct.pack("<9h", *acc, *gyro, *mag)

def attitude(roll_ddeg=15, pitch_ddeg=-20, yaw_deg=271):
    return struct.pack("<hhh", roll_ddeg, pitch_ddeg, yaw_deg)
