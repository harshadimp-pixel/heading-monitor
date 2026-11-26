"""Payload decoders and per-firmware unit scaling for MSP telemetry.

Every scale factor below is traced to firmware source (pinned commits are listed in
docs/firmware/FC_SETUP.md §6, "Unit scaling").  Items marked UNCERTAIN have not been
validated on real hardware and must be checked before any [HARDWARE-VERIFIED] claim.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

UT_PER_MGAUSS = 0.1          # 1 G = 100 uT  ->  1 mG = 0.1 uT (exact, SI definition)
RM3100_GAIN_CC200 = 75.0     # LSB/uT at cycle count 200 [DATASHEET] PNI-UM Table 3-1; ArduPilot GAIN_CC200


def decode_raw_imu(payload: bytes) -> dict:
    """MSP_RAW_IMU (102): 9 x int16 LE = acc[3], gyro[3], mag[3].

    INAV fc_msp.c:  acc = lrintf(acc.accADCf[i] * 512)   (accADCf in g -> 512 LSB/g)
                    gyro = gyroRateDps(i)                 (deg/s, integer)
                    mag = lrintf(mag.magADC[i])           (driver/calibration dependent, see MAG_PROFILES)
    Betaflight msp.c: acc = lrintf(acc.accADC.v[i])  (raw counts, acc_1G is sensor dependent: UNCERTAIN)
                      gyro = gyroRateDps(i); mag = lrintf(mag.magADC.v[i])
    ArduPilot AP_MSP does NOT implement MSP_RAW_IMU (no case in AP_MSP_Telem_Backend.cpp).
    """
    if len(payload) < 18:
        raise ValueError(f"MSP_RAW_IMU payload too short: {len(payload)} < 18")
    v = struct.unpack_from("<9h", payload, 0)
    return {"acc": list(v[0:3]), "gyro": list(v[3:6]), "mag": list(v[6:9])}


def decode_attitude(payload: bytes) -> dict:
    """MSP_ATTITUDE (108): int16 roll [decideg], int16 pitch [decideg], int16 yaw [deg].

    INAV & Betaflight: roll/pitch = attitude.values.* (decidegrees), yaw = DECIDEGREES_TO_DEGREES(yaw).
    ArduPilot AP_MSP_Telem_Backend::msp_process_out_attitude: roll/pitch = deg*10, yaw = wrap_360(deg).
    """
    if len(payload) < 6:
        raise ValueError(f"MSP_ATTITUDE payload too short: {len(payload)} < 6")
    r, p, y = struct.unpack_from("<3h", payload, 0)
    return {"roll": r / 10.0, "pitch": p / 10.0, "yaw": float(y % 360)}


def decode_sensor_compass(payload: bytes) -> dict:
    """MSP2_SENSOR_COMPASS (0x1F04): u8 instance, u32 time_ms, int16 mag x/y/z [mGauss, FRD].

    INAV msp_protocol_v2_sensor_msg.h mspSensorCompassDataMessage_t; ArduPilot AP_MSP/msp_sensors.h
    msp_compass_data_message_t. Pushed by AP_Periph (e.g. Matek CAN-L4-3100 UART2, send_msp_compass).
    """
    if len(payload) < 11:
        raise ValueError(f"MSP2_SENSOR_COMPASS payload too short: {len(payload)} < 11")
    inst, tms, x, y, z = struct.unpack_from("<BIhhh", payload, 0)
    return {"instance": inst, "time_ms": tms, "mag_mgauss": [x, y, z]}


@dataclass(frozen=True)
class MagProfile:
    name: str
    ut_per_lsb: float | None          # None -> unknown, caller must supply --mag-ut-per-lsb
    accel_lsb_per_g: float | None     # None -> unknown, accel_g omitted
    description: str
    uncertain: tuple[str, ...] = field(default_factory=tuple)


MAG_PROFILES: dict[str, MagProfile] = {
    # Our part: Matek CAN-L4-3100 (RM3100 + AP_Periph) wired by UART2 MSP to an INAV FC with mag_hardware=MSP.
    "inav-msp-mag": MagProfile(
        "inav-msp-mag", UT_PER_MGAUSS, 512.0,
        "INAV with mag_hardware=MSP fed by AP_Periph MSP2_SENSOR_COMPASS (mGauss). "
        "INAV compass_msp.c copies mGauss into magADCRaw, so MSP_RAW_IMU mag = mGauss (0.1 uT/LSB) "
        "rotated by CW90_DEG_FLIP + align_mag, ONLY while INAV mag calibration is unset "
        "(magzero_*=0, maggain_*=1024).",
        ("Valid only with INAV magzero_x/y/z=0 and maggain_x/y/z=1024; after INAV mag calibration the "
         "values are offset-removed and normalised to ~1024 per axis peak (dimensionless).",
         "Axis order/sign after INAV CW90_DEG_FLIP + align_mag not yet checked on hardware.",
         "AP_Periph field already includes the node's own COMPASS_OFS/orientation (ROTATION_PITCH_180 in hwdef)."),
    ),
    # Bare RM3100 breakout on SPI (INAV registers RM3100 on SPI only, e.g. MATEKH743 SPI3 / MATEKF405CAN SPI2).
    "inav-rm3100-spi": MagProfile(
        "inav-rm3100-spi", 256.0 / RM3100_GAIN_CC200, 512.0,
        "INAV native RM3100 driver (compass_rm3100.c): CC=200 (75 LSB/uT) and the 24-bit sample is "
        "truncated to its top 16 bits (raw24 >> 8), so 1 LSB = 256/75 = 3.413 uT.",
        ("Very coarse (~3.4 uT/LSB): earth field is only ~7-19 LSB per axis; heading quantisation of "
         "several degrees is expected.",
         "Valid only with INAV magzero=0 / maggain=1024 (see inav-msp-mag)."),
    ),
    "betaflight": MagProfile(
        "betaflight", None, None,
        "Betaflight has no RM3100 driver (src/main/drivers/compass/ at master). magADC units are "
        "driver-specific and accel is raw counts (acc_1G sensor-specific).",
        ("No RM3100 support; mag/accel scaling unknown - supply --mag-ut-per-lsb / --accel-lsb-per-g.",),
    ),
    "custom": MagProfile("custom", None, None, "User-supplied scale factors.", ("User-supplied scaling.",)),
}

FC_VARIANT_DEFAULT_PROFILE = {"INAV": "inav-msp-mag", "BTFL": "betaflight"}
