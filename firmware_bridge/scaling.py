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


def decode_calibration_data(payload: bytes) -> dict:
    """MSP_CALIBRATION_DATA (14), INAV layout (identical in 9.1.0, master @940b928 and
    maintenance-10.x @fce6c94; fc_msp.c L1574-1603 at fce6c94):
      u8 accCalibAxisFlags, accZero[3], accGain[3], magZero[3], u16 opflow_scale*256, magGain[3]
    All axis values are int16 written with sbufWriteU16 -> decoded signed.  27 bytes.
    Betaflight/ArduPilot layouts are NOT assumed (caller only interprets this for fc_variant INAV).
    """
    if len(payload) < 27:
        raise ValueError(f"MSP_CALIBRATION_DATA payload too short: {len(payload)} < 27")
    v = struct.unpack_from("<B3h3h3hH3h", payload, 0)
    return {"acc_calib_axis_flags": v[0], "acc_zero": list(v[1:4]), "acc_gain": list(v[4:7]),
            "mag_zero": list(v[7:10]), "opflow_scale_x256": v[10], "mag_gain": list(v[11:14])}


# ---- GPS availability (contract `gps` object; ARCHITECTURE.md 2026-11-27) ----------------------
# INAV MSP_RAW_GPS (106), fc_msp.c L1044-1053 at fce6c94 (byte-identical case at 9.1.0 and master),
# inside #ifdef USE_GPS:
#   u8 fixType, u8 numSat, u32 lat, u32 lon, u16 alt(m), u16 groundSpeed, u16 groundCourse, u16 hdop  = 18 bytes
# fixType = gpsFixType_e {GPS_NO_FIX=0, GPS_FIX_2D, GPS_FIX_3D} (io/gps.h L90-92).
# PRIVACY RULE: only bytes 0-1 are ever read. lat/lon/alt/speed/course (and hdop, which the schema does not
# require) are never unpacked, never emitted, never put in meta, and are zeroed in --capture logs.
INAV_RAW_GPS_LEN = 18
INAV_FIX_MAP = {0: "none", 1: "2d", 2: "3d"}


def decode_raw_gps_availability(payload: bytes) -> dict:
    """-> {'fix': 'none'|'2d'|'3d'|'unknown', 'num_sat': int}. Raises ValueError on a short payload."""
    if len(payload) < INAV_RAW_GPS_LEN:
        raise ValueError(f"MSP_RAW_GPS payload too short: {len(payload)} < {INAV_RAW_GPS_LEN}")
    return {"fix": INAV_FIX_MAP.get(payload[0], "unknown"), "num_sat": int(payload[1])}


def redact_raw_gps_payload(payload: bytes) -> bytes:
    """Keep fixType/numSat, zero everything else (coordinates, alt, speed, course, hdop)."""
    return bytes(payload[:2]) + bytes(max(0, len(payload) - 2))


INAV_NEUTRAL_MAGZERO = (0, 0, 0)
INAV_NEUTRAL_MAGGAIN = (1024, 1024, 1024)   # settings.yaml maggain_* default; compass.c L389-390 "not calibrated" test


def fc_mag_calibration_state(cal: dict | None, fc_variant: str | None):
    """-> False (confirmed neutral), True (confirmed non-neutral) or 'unknown'.

    False only when the FC is INAV AND magZero == (0,0,0) AND magGain == (1024,1024,1024) were read back.
    'unknown' when: no reply / error reply / short payload (cal is None), FC is not INAV (layout not
    verified), or magZero and magGain are all 0 (INAV build without USE_MAG writes zeros).
    """
    if cal is None or fc_variant != "INAV":
        return "unknown"
    zero, gain = tuple(cal["mag_zero"]), tuple(cal["mag_gain"])
    if zero == (0, 0, 0) and gain == (0, 0, 0):
        return "unknown"
    return not (zero == INAV_NEUTRAL_MAGZERO and gain == INAV_NEUTRAL_MAGGAIN)


@dataclass(frozen=True)
class MagProfile:
    name: str
    ut_per_lsb: float | None          # None -> unknown, caller must supply --mag-ut-per-lsb
    accel_lsb_per_g: float | None     # None -> unknown, accel_g omitted
    description: str
    uncertain: tuple[str, ...] = field(default_factory=tuple)
    body_frame: str = "flu"           # frame of MSP_RAW_IMU vectors: 'flu' (INAV) or 'frd' (no change)


# ---- body frame -------------------------------------------------------------------------------
# ARCHITECTURE.md: body frame x forward, y right, z down (FRD/"NED-style"); accel is specific force,
# level & at rest = (0, 0, -1) g.
# INAV MSP_RAW_IMU vectors are, by source derivation, in a forward-LEFT-UP body frame:
#   * imu.c L367: wCoGAcc = (accBFNorm.z - 1) ... "z direction is verified via SITL"  -> level acc z = +1 g
#   * imu.c L287-293 imuResetOrientationQuaternion(): q = (az+|a|, ay, -ax, 0) and
#     imu.c L626-627 roll = atan2(rMat[2][1], rMat[2][2]), pitch = 90deg - acos(-rMat[2][0]):
#     +roll (right side down, see mavlink_streams.c L724) <=> +ay  -> y points LEFT
#     nose-up (negative INAV pitch, see osd.c L3085 SYM_PITCH_DOWN for pitch>0) <=> +ax -> x FORWARD
#   * Matek CAN-L4-3100 page: INAV `align_mag = CW90` for an arrow-forward module; INAV compass_msp.c
#     applies CW90_DEG_FLIP to the FRD MSP2_SENSOR_COMPASS vector, boardalignment.c L126-150:
#     FRD (f,r,d) -CW90_DEG_FLIP-> (r,f,-d) -CW90_DEG-> (f,-r,-d) = FLU.  Consistent with the above.
# FLU -> FRD is (x, -y, -z). Applied to acc, gyro and mag.  NEEDS HARDWARE VALIDATION (tilt/rotate test
# in docs/firmware/FC_SETUP.md §7); the gyro sign in particular is only inferred.
def flu_to_frd(v):
    return [v[0], -v[1], -v[2]]


def to_body_frd(v, body_frame: str):
    if body_frame == "flu":
        return flu_to_frd(v)
    if body_frame == "frd":
        return list(v)
    raise ValueError(f"unknown body frame {body_frame!r}")


# MSP_ATTITUDE pitch sign by firmware: INAV/Betaflight report +pitch = nose DOWN (INAV osd.c L3085,
# INAV MAVLink sends -pitch, mavlink_streams.c L725); ArduPilot AP_MSP sends degrees(pitch_rad)*10,
# i.e. aerospace +pitch = nose UP. The bridge outputs aerospace convention (roll + right side down,
# pitch + nose up, yaw clockwise from north, 0..360).
PITCH_SIGN_BY_VARIANT = {"INAV": -1.0, "BTFL": -1.0, "ARDU": 1.0}


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
         "Axis order/sign: INAV body frame derived as forward-left-up from source and converted to FRD; "
         "assumes align_mag=CW90 per Matek for an arrow-forward module. Not yet checked on hardware.",
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
        ("No RM3100 support; mag/accel scaling unknown - supply --mag-ut-per-lsb / --accel-lsb-per-g.",
         "Body frame assumed forward-left-up like INAV (shared Cleanflight heritage); not verified for Betaflight."),
    ),
    "custom": MagProfile("custom", None, None, "User-supplied scale factors; vectors passed through as FRD.",
                         ("User-supplied scaling; no axis conversion.",), body_frame="frd"),
}

FC_VARIANT_DEFAULT_PROFILE = {"INAV": "inav-msp-mag", "BTFL": "betaflight"}
