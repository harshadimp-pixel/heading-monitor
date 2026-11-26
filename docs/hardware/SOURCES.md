# T1 sources (retrieved 2026-11-26/27 IST; datasheet re-verified 2026-11-27 ~00:15 IST)

## Audit note (2026-11-27)
The Auditor found `/workspace/hwsrc/RM3100-RM2100-Sensor-Suite-User-Manual.pdf` (233 bytes, sha256 `5fa13ee64ac0d26d…`) is a
SiteGround **captcha redirect page** from a failed `www.pnicorp.com` download, not the manual. Findings:
- That file was **never** used or cited. The checksum previously listed here for PNI-UM (`2a0945…`) is the real 45-page PDF from
  **pnisensor.com**, not the captcha file. Re-downloaded today from the same URL: identical sha256, `pdfinfo` = 45 pages, real text.
- Two more failed downloads were found and renamed as well: a captcha page for `pnicorp.com/rm3100/`, and a Google redirect
  instead of the Matek CAN-L4-3100 page. The Matek page was read through a separate web fetch, which worked.
  New names: `/workspace/hwsrc/INVALID-captcha-page-NOT-RM3100-manual.html`,
  `INVALID-pnicorp-rm3100-page-blocked.html`, `INVALID-google-redirect-NOT-matek-page.html` (see `README-INVALID.txt`).
- Every `[DATASHEET]` value in FACTSHEET.md / key_numbers.json was cross-checked with `docs/hardware/verify_datasheet.py`
  against `pdftotext -layout` output of the fresh downloads: **66/66 checks PASS** (output in `VERIFICATION.md`).

## Verified PNI documents (fresh copies in /workspace/hwsrc/refetch/)

| Abbrev | URL (HTTP 200, real PDF) | sha256 | pdfinfo |
|---|---|---|---|
| PNI-UM | https://www.pnisensor.com/wp-content/uploads/RM3100-RM2100-Sensor-Suite-User-Manual-V11.0.pdf | `2a09457337a6882632681a48e6c62a6dd842287e18f8311b88d748e9b92f1cbf` | 45 pages, PDF 1.7, 2,465,891 B; content footer "Doc 1017252 V16.0", revision block to R16 (2026-08-28); metadata Subject says "V15.0" and the URL says "V11.0" (naming mismatch, content is V16.0) |
| PNI-SALES | https://www.pnisensor.com/wp-content/uploads/PNI-Sensor-RM3100-Sales-Sheet.pdf | `ea9c5aa72f58282be052d53abf406cc3a37122c0780fb65b2a0af644d82af52c` | 2 pages, PDF 1.6 (gives ±1100 µT, 534/284/147 Hz 3-axis) |
| PNI-BB | https://www.pnicorp.com/wp-content/uploads/RM3100-Breakout-Board-Sales-Sheet-2018-1.pdf | `c47ac0674cc181d4fc7837f32e197b508251faf48e230f0ea2b76aff0902e716` | 2 pages (corroborates ±800 µT and 534/284/147 Hz) |
| PNI-UM-r06 | https://www.tri-m.com/products/pni/RM3100-User-Manual.pdf (distributor mirror, 2014 r06) | `164eae6275cf129e71e6b90f86eb22b7cd976d03d83ca6f45959d87895616ceb` | 41 pages, PDF 1.5; used only to note revision differences |
| PNI-WEB | https://www.pnisensor.com/rm3100/ | HTML, re-fetched 2026-11-27, contains "1100 uT" | – |

Not tried: Digi-Key, Mouser and SparkFun mirrors. They weren't needed, because the manufacturer URL works.

## Other sources

| Abbrev | Source | Pin |
|---|---|---|
| MATEK-3100 | https://www.mateksys.com/?portfolio=can-l4-3100 (read via web fetch 2026-11-26; curl copy was a Google redirect → INVALID) | – |
| MATEK-WLITE | https://www.mateksys.com/?portfolio=h743-wlite , http://www.mateksys.com/downloads/Manual/H743-WLITE_Manual.pdf (read as search extracts only) | – |
| MATEK-F765WSE | https://www.mateksys.com/?portfolio=f765-wse (web fetch) | – |
| MATEK-F405WTE | https://www.mateksys.com/?portfolio=f405-wte (web fetch) | – |
| RESELLER | risingsunfpv.com (H743-WING V3, H743-SLIM V3), lumenier.com (H743-SLIM V3), phaserfpv.com.au (CAN-L4-3100) — search extracts, lower confidence | – |
| AP | ArduPilot master `6034266b5abffd36fb4b89f0bf61fb6db8aed85d`: AP_Compass_RM3100.{cpp,h}, AP_Compass.cpp, AP_Compass_config.h, AP_CANManager/*Params.cpp, Tools/AP_Periph/{compass,msp}.cpp, AP_MSP/msp_sensors.h, hwdef/{MatekL431-GPS,MatekL431-Periph,MatekH743,MatekF405*,MatekF765*} | commit SHA |
| AP-DOC | https://ardupilot.org/copter/docs/common-magnetic-interference.html , https://ardupilot.org/copter/docs/common-compass-setup-advanced.html | – |
| INAV | `maintenance-10.x` @ `fce6c94b38f05ec6a563a2c6e80d99ac5cb2d638` (also master @ 940b9281bb): compass_rm3100.c, common_hardware.c, target/MATEKH743|MATEKF405SE|MATEKF405TE/target.h, fc/settings.yaml, msp_protocol_v2_sensor_msg.h, docs/DroneCAN.md; release notes 10.0.0-rc2 | commit SHA |
| BF | betaflight master @ `f511ed9e82cfb77fe9e84247bceccd1946272c94` and tag 2026.6.2: sensors/compass.h, io/dronecan/dronecan_mag.c, cli/settings.c; commit bd697eba28 (#15430, 2026-07-17) | commit SHA |

PDFs are not committed (copyright). To re-verify: download the URLs above, compare sha256, run
`pdftotext -layout <pdf> <txt>` and `python docs/hardware/verify_datasheet.py um.txt sales.txt r06.txt`.
