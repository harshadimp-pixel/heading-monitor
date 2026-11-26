"""'Delivered' output modes: what the flight controller actually receives from a Matek CAN-L4-3100
(RM3100 behind ArduPilot AP_Periph), rather than raw RM3100 counts.

Behaviour modelled from source code [SOURCE-CODE], ArduPilot commit 6034266b5abffd36fb4b89f0bf61fb6db8aed85d
(the same pin T1 used in docs/hardware/SOURCES.md):
  * libraries/AP_Compass/AP_Compass_RM3100.cpp: cycle count forced to 200 (CCP0 0xC8), scaler = 1/75 uT/LSB
    converted to milligauss, TMRC 0x94 (CMM ~150 Hz), driver timer polled at 80 Hz, reading only when DRDY is set,
    and each reading passed to accumulate_sample().
  * libraries/AP_Compass/AP_Compass_Backend.cpp: accumulate_sample() sums samples, and drain_accumulated_samples(),
    called from Compass::read(), publishes their MEAN. So each delivered value is the average of the RM3100
    readings since the previous read.
  * Tools/AP_Periph/compass.cpp: can_mag_update() returns early if less than 1000/AP_PERIPH_MAG_MAX_RATE ms
    (AP_PERIPH_MAG_MAX_RATE = 25) have passed, then calls compass.read(), sends only when there is new data, and
    sends uavcan.equipment.ahrs.MagneticFieldStrength with magnetic_field_ga[i] = get_field() * 0.001
    (mG -> Gauss), float16.
  * Tools/AP_Periph/msp.cpp + libraries/AP_MSP/msp_sensors.h: MSP2_SENSOR_COMPASS, int16 magX/Y/Z in mGauss,
    assigned straight from the float field (C float->int conversion truncates toward zero). It is sent only when
    compass.last_update_ms() changes. In AP_Periph, compass.read() is called only from can_mag_update(), so we
    INFER (not verified on hardware) that MSP is limited to the same <=25 Hz update.
  * DroneCAN DSDL uavcan/equipment/ahrs/1001.MagneticFieldStrength.uavcan (dronecan/DSDL b4653c7):
    float16[3] magnetic_field_ga ("in Gauss ... SI units are avoided because of float16 range limitations"),
    marked deprecated in favour of 1002.MagneticFieldStrength2, which AP_Periph does not use for this.
  * float16 encoding: libcanard canardConvertNativeFloatToFloat16 at the submodule pin used by that ArduPilot commit
    (DroneCAN/libcanard 601ed35). It is emulated bit-exactly below.
"""
from __future__ import annotations
import numpy as np

OUTPUT_MODES = ("raw", "dronecan", "msp")

AP_RM3100_POLL_HZ = 80.0          # [SOURCE-CODE] AP_Compass_RM3100 register_periodic_callback(1000000U/80U)
AP_RM3100_CYCLE_COUNT = 200       # [SOURCE-CODE] CCP0 0xC8 / CCP1 0x00
AP_RM3100_GAIN = 75.0             # [SOURCE-CODE] GAIN_CC200, scaler = 1/75 uT per LSB
AP_PERIPH_MAG_MAX_RATE_HZ = 25.0  # [SOURCE-CODE] AP_PERIPH_MAG_MAX_RATE 25U
UT_TO_MGAUSS = np.float32(10.0)
MSP_INT16_MAX = 32767


def _f32_bits(x) -> np.ndarray:
    return np.asarray(x, dtype=np.float32).view(np.uint32)


def _bits_f32(u) -> np.ndarray:
    return np.asarray(u, dtype=np.uint32).view(np.float32)


def canard_float_to_float16(value) -> np.ndarray:
    """Bit-exact port of libcanard canardConvertNativeFloatToFloat16 (DroneCAN/libcanard 601ed35).

    Returns the uint16 encodings. All arithmetic is done in float32/uint32, as on the STM32."""
    v = np.atleast_1d(np.asarray(value, dtype=np.float32))
    u = _f32_bits(v).copy()
    sign = u & np.uint32(0x80000000)
    u ^= sign
    f32inf = np.uint32(255 << 23)
    f16inf = np.uint32(31 << 23)
    magic = _bits_f32(np.uint32(15 << 23))
    round_mask = np.uint32(0xFFFFF000)
    out = np.zeros(u.shape, dtype=np.uint32)
    special = u >= f32inf
    out[special] = np.where(u[special] > f32inf, 0x7FFF, 0x7C00)
    n = ~special
    w = u[n] & round_mask
    with np.errstate(over="ignore"):
        wf = (_bits_f32(w) * magic).astype(np.float32)
    w = _f32_bits(wf) - round_mask
    w = np.minimum(w, f16inf)
    out[n] = w >> np.uint32(13)
    out |= sign >> np.uint32(16)
    return out.astype(np.uint16)


def canard_float16_to_float(h) -> np.ndarray:
    """Bit-exact port of libcanard canardConvertFloat16ToNativeFloat."""
    h = np.atleast_1d(np.asarray(h, dtype=np.uint32))
    magic = _bits_f32(np.uint32((254 - 15) << 23))
    was_inf_nan = _bits_f32(np.uint32((127 + 16) << 23))
    out = ((_bits_f32((h & np.uint32(0x7FFF)) << np.uint32(13))) * magic).astype(np.float32)
    ou = _f32_bits(out).copy()
    ou[out >= was_inf_nan] |= np.uint32(255 << 23)
    ou |= (h & np.uint32(0x8000)) << np.uint32(16)
    return _bits_f32(ou)


def dronecan_encode(field_mG_f32):
    """mG (float32) -> Gauss float32 (x0.001, as AP_Periph) -> float16 wire bits; returns (bits, decoded uT)."""
    ga = (np.asarray(field_mG_f32, dtype=np.float32) * np.float32(0.001)).astype(np.float32)
    bits = canard_float_to_float16(ga)
    return bits, canard_float16_to_float(bits).astype(np.float64) * 100.0


def dronecan_roundtrip_uT(field_mG_f32) -> np.ndarray:
    return dronecan_encode(field_mG_f32)[1]


def msp_encode_mG(field_mG_f32):
    """float mG -> int16 mG as AP_Periph assigns it (truncation toward zero). Values outside int16 are
    undefined behaviour in C; we clip and report overflow."""
    f = np.asarray(field_mG_f32, dtype=np.float32).astype(np.float64)
    t = np.trunc(f)
    overflow = bool(np.any(np.abs(t) > MSP_INT16_MAX))
    return np.clip(t, -MSP_INT16_MAX - 1, MSP_INT16_MAX).astype(np.int64), overflow


class PeriphPublisher:
    """Emulates the AP_Periph pipeline: an 80 Hz RM3100 poll, accumulate, mean at each publish tick, encode.

    Time is integer microseconds, so the grids are exact. Publishes happen at j * (1e6/publish_rate).
    A publish averages the poll ticks in (previous publish, this publish]; with no ticks there is no new data,
    so no message is sent and the FC keeps the previous one.
    """

    def __init__(self, mode, measure_fn, poll_hz=AP_RM3100_POLL_HZ, publish_hz=AP_PERIPH_MAG_MAX_RATE_HZ):
        if mode not in ("dronecan", "msp"):
            raise ValueError(mode)
        if poll_hz <= 0 or publish_hz <= 0:
            raise ValueError("poll and publish rates must be > 0")
        self.mode = mode
        self.measure_fn = measure_fn          # t_s -> (counts[3], saturated)
        self.poll_us = 1e6 / poll_hz
        self.pub_us = 1e6 / publish_hz
        self.k = 0                            # next poll tick index
        self.j = 0                            # next publish index
        self.held = None                      # dict(t_us, mag_uT, seq, saturated, overflow, n_avg)
        self.seq = -1

    def _publish(self, t_pub_us):
        acc, n, sat, tsum = np.zeros(3, np.float32), 0, False, 0.0
        while self.k * self.poll_us <= t_pub_us + 1e-6:
            counts, s = self.measure_fn(self.k * self.poll_us / 1e6)
            # driver: int counts * float32 scaler (1/75 uT -> mG), summed in float32
            scaler = np.float32(np.float32(1.0) / np.float32(AP_RM3100_GAIN)) * UT_TO_MGAUSS
            acc = (acc + np.asarray(counts, np.float32) * scaler).astype(np.float32)
            n += 1
            tsum += self.k * self.poll_us
            sat |= s
            self.k += 1
        if n == 0:
            return
        mean_mG = (acc / np.float32(n)).astype(np.float32)
        overflow = False
        if self.mode == "dronecan":
            wire, uT = dronecan_encode(mean_mG)
        else:
            wire, overflow = msp_encode_mG(mean_mG)
            uT = wire.astype(np.float64) / 10.0
        self.seq += 1
        self.held = {"t_us": t_pub_us, "mag_uT": uT, "seq": self.seq, "saturated": sat,
                     "overflow": overflow, "n_avg": n, "wire": wire,
                     "t_mid_us": tsum / n}

    def at(self, t_us: float) -> dict | None:
        """Latest message the FC holds at time t_us (sample-and-hold)."""
        while self.j * self.pub_us <= t_us + 1e-6:
            self._publish(self.j * self.pub_us)
            self.j += 1
        return self.held
