# T1 sources (retrieved 2026-11-26/27 IST)

| Abbrev | Source | Pin / hash |
|---|---|---|
| PNI-UM | PNI RM3100 & RM2100 User Manual Doc 1017252 V16.0 — https://www.pnisensor.com/wp-content/uploads/RM3100-RM2100-Sensor-Suite-User-Manual-V11.0.pdf | sha256 2a09457337a6882632681a48e6c62a6dd842287e18f8311b88d748e9b92f1cbf |
| PNI-UM-r06 | Older r06 (2014) mirror, used only to note revision differences — https://www.tri-m.com/products/pni/RM3100-User-Manual.pdf | sha256 164eae6275cf129e71e6b90f86eb22b7cd976d03d83ca6f45959d87895616ceb |
| PNI-SALES | https://www.pnisensor.com/wp-content/uploads/PNI-Sensor-RM3100-Sales-Sheet.pdf (3-axis rates, ±1100 µT) | (read via search extract) |
| PNI-WEB | https://www.pnisensor.com/rm3100/ | – |
| MATEK-3100 | https://www.mateksys.com/?portfolio=can-l4-3100 | fetched 2026-11-26 |
| MATEK-WLITE | https://www.mateksys.com/?portfolio=h743-wlite , manual http://www.mateksys.com/downloads/Manual/H743-WLITE_Manual.pdf | – |
| MATEK-F765WSE | https://www.mateksys.com/?portfolio=f765-wse | – |
| MATEK-F405WTE | https://www.mateksys.com/?portfolio=f405-wte | – |
| RESELLER | risingsunfpv.com (H743-WING V3, H743-SLIM V3), lumenier.com (H743-SLIM V3), phaserfpv.com.au (CAN-L4-3100) | lower confidence |
| AP | ArduPilot master `6034266b5abffd36fb4b89f0bf61fb6db8aed85d`: libraries/AP_Compass/AP_Compass_RM3100.{cpp,h}, AP_Compass.cpp, AP_Compass_config.h, AP_CANManager/*Params.cpp, Tools/AP_Periph/{compass,msp}.cpp, AP_MSP/msp_sensors.h, AP_HAL_ChibiOS/hwdef/{MatekL431-GPS,MatekL431-Periph,MatekH743,MatekF405*,MatekF765*} | commit SHA |
| AP-DOC | https://ardupilot.org/copter/docs/common-magnetic-interference.html , https://ardupilot.org/copter/docs/common-compass-setup-advanced.html | – |
| INAV | iNavFlight/inav `maintenance-10.x` @ `fce6c94b38f05ec6a563a2c6e80d99ac5cb2d638` (also master @ 940b9281bb): src/main/drivers/compass/compass_rm3100.c, target/common_hardware.c, target/MATEKH743/target.h, MATEKF405SE, MATEKF405TE, fc/settings.yaml, msp/msp_protocol_v2_sensor_msg.h, docs/DroneCAN.md; release notes 10.0.0-rc2 | commit SHA |
| BF | betaflight/betaflight master @ `f511ed9e82cfb77fe9e84247bceccd1946272c94` and tag 2026.6.2: sensors/compass.h, io/dronecan/dronecan_mag.c, cli/settings.c; commit bd697eba28 "Add DroneCAN magnetometer support (#15430)" 2026-07-17 | commit SHA |

PDFs are not committed (copyright); re-download and compare the sha256 to verify.
