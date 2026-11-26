"""Simulated flight controller speaking MSP, for loopback testing without hardware.

Everything produced through this module is labelled source='sim' by the CLI/bridge
(FakeFCTransport.kind == 'sim'); it can never yield source='hardware'.
The synthetic data imitates INAV's MSP_RAW_IMU / MSP_ATTITUDE encodings for the
'inav-msp-mag' profile (mag in mGauss, accel 512 LSB/g, attitude decideg/deg).
It is NOT a model of the RM3100 noise/interference (that is the sim/ package, T3).
"""
from __future__ import annotations

import math
import struct

from . import msp


class FakeFC:
    def __init__(self, variant: str = "INAV", yaw_rate_dps: float = 30.0, field_uT: float = 50.0,
                 inclination_deg: float = 60.0, support_raw_imu: bool = True, clock=None,
                 mag_zero=(0, 0, 0), mag_gain=(1024, 1024, 1024), support_calibration_data: bool = True):
        self.variant = variant.encode()[:4].ljust(4, b" ")
        self.yaw_rate = yaw_rate_dps
        self.field = field_uT
        self.incl = math.radians(inclination_deg)
        self.support_raw_imu = support_raw_imu
        self.mag_zero, self.mag_gain = tuple(mag_zero), tuple(mag_gain)
        self.support_calibration_data = support_calibration_data
        self.parser = msp.MSPParser()
        self.t = 0.0
        self._clock = clock

    def now(self) -> float:
        return self._clock() if self._clock else self.t

    def yaw_deg(self) -> float:
        return (self.yaw_rate * self.now()) % 360.0

    def raw_imu_payload(self) -> bytes:
        yaw = math.radians(self.yaw_deg())
        h = self.field * math.cos(self.incl)
        z = self.field * math.sin(self.incl)
        # level vehicle. In FRD the body field is (h cos psi, -h sin psi, +z) and specific force (0,0,-1 g).
        # INAV reports forward-LEFT-UP (see scaling.py), so emit (x, -y, -z) of the FRD values:
        mag_mg = [round(h * math.cos(yaw) * 10), round(h * math.sin(yaw) * 10), round(-z * 10)]
        acc = [0, 0, 512]                      # INAV: level -> +512 on z (imu.c L367)
        gyro = [0, 0, -round(self.yaw_rate)]   # clockwise yaw (FRD +z) is -z in FLU
        return struct.pack("<9h", *acc, *gyro, *mag_mg)

    def attitude_payload(self) -> bytes:
        return struct.pack("<3h", 0, 0, int(self.yaw_deg()))

    def handle(self, frame: msp.MSPFrame) -> bytes:
        version = frame.version
        if frame.cmd == msp.MSP_FC_VARIANT:
            return msp.encode(frame.cmd, self.variant, version, ">")
        if frame.cmd == msp.MSP_CALIBRATION_DATA and self.support_calibration_data:
            # INAV layout (scaling.decode_calibration_data); acc values arbitrary
            p = struct.pack("<B3h3h3hH3h", 0, 0, 0, 0, 4096, 4096, 4096, *self.mag_zero, 0, *self.mag_gain)
            return msp.encode(frame.cmd, p, version, ">")
        if frame.cmd == msp.MSP_ATTITUDE:
            return msp.encode(frame.cmd, self.attitude_payload(), version, ">")
        if frame.cmd == msp.MSP_RAW_IMU and self.support_raw_imu:
            return msp.encode(frame.cmd, self.raw_imu_payload(), version, ">")
        return msp.encode(frame.cmd, b"", version, "!")


class FakeFCTransport:
    """In-memory loopback transport. kind is fixed to 'sim'."""

    kind = "sim"

    def __init__(self, fc: FakeFC | None = None, dt: float = 0.02):
        self.fc = fc or FakeFC()
        self.dt = dt
        self.rx = bytearray()

    def write(self, data: bytes) -> None:
        for f in self.fc.parser.feed(data):
            if f.direction == "<":
                self.rx.extend(self.fc.handle(f))

    def read(self, n: int = 4096, timeout: float = 0.0) -> bytes:
        out = bytes(self.rx[:n])
        del self.rx[:n]
        return out

    def tick(self) -> None:
        self.fc.t += self.dt

    def close(self) -> None:
        pass
