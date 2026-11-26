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
                 inclination_deg: float = 60.0, support_raw_imu: bool = True, clock=None):
        self.variant = variant.encode()[:4].ljust(4, b" ")
        self.yaw_rate = yaw_rate_dps
        self.field = field_uT
        self.incl = math.radians(inclination_deg)
        self.support_raw_imu = support_raw_imu
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
        # level vehicle, body x forward/y right/z down; heading psi -> body field (h cos psi, -h sin psi, z)
        mag_mg = [round(h * math.cos(yaw) * 10), round(-h * math.sin(yaw) * 10), round(z * 10)]
        acc = [0, 0, 512]
        gyro = [0, 0, round(self.yaw_rate)]
        return struct.pack("<9h", *acc, *gyro, *mag_mg)

    def attitude_payload(self) -> bytes:
        return struct.pack("<3h", 0, 0, int(self.yaw_deg()))

    def handle(self, frame: msp.MSPFrame) -> bytes:
        version = frame.version
        if frame.cmd == msp.MSP_FC_VARIANT:
            return msp.encode(frame.cmd, self.variant, version, ">")
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
