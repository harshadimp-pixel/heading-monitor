# Hardware Fact Sheet — PNI RM3100 + Matek FC (T1)

Owner: Hardware Research Engineer. Status: REVIEW (v1.0, 2026-11-27 IST). Research only — nothing here was measured on our hardware.
Evidence tags: `[DATASHEET]` = PNI manufacturer document; `[OFFICIAL-DOC]` = vendor/project documentation
(mateksys.com, ardupilot.org, INAV/Betaflight docs); `[SOURCE-CODE]` = firmware source at a pinned commit;
`[DERIVED]` = arithmetic on tagged numbers (formula shown). Nothing here is `[HARDWARE-VERIFIED]`.

Primary source (abbrev. **PNI-UM**): PNI Sensor, *RM3100 & RM2100 Magneto-Inductive Magnetometer User Manual*,
Doc 1017252 V16.0 (rev. block to R16, 2026-08-28),
https://www.pnisensor.com/wp-content/uploads/RM3100-RM2100-Sensor-Suite-User-Manual-V11.0.pdf
(file downloaded 2026-11-26, sha256 `2a09457337a6882632681a48e6c62a6dd842287e18f8311b88d748e9b92f1cbf`; the URL
says V11.0 but the file content is V16.0).

## Key numbers (for Math / Sim / Firmware)
Machine-readable copy: `docs/hardware/key_numbers.json`. Derived values (µT/LSB, float16 steps, full scale) were computed and checked with Python on 2026-11-27.

| Quantity | Value | Tag / source |
|---|---|---|
| Gain @ cycle count (CC) 50 / 100 / 200 | **20 / 38 / 75 LSB/µT** | [DATASHEET] PNI-UM Table 3-1 |
| Resolution ("sensitivity") @ CC 50/100/200 | 50 / 26 / 13 nT | [DATASHEET] PNI-UM Table 3-1 |
| Noise @ CC 50/100/200 | 30 / 20 / 15 nT | [DATASHEET] PNI-UM Table 3-1 |
| Max single-axis sample rate @ CC 50/100/200 | 1600 / 850 / 440 Hz ("divide by 3 for 3-axis") | [DATASHEET] PNI-UM Table 3-1 |
| Max 3-axis rate @ CC 50/100/200 | 534 / 284 / 147 Hz | [DATASHEET] PNI sales sheet https://www.pnisensor.com/wp-content/uploads/PNI-Sensor-RM3100-Sales-Sheet.pdf |
| Field measurement range | **±800 µT** (user manual, 121 Ω bias resistor); sales sheet/product page say ±1100 µT | [DATASHEET] PNI-UM Table 3-1; product page https://www.pnisensor.com/rm3100/ |
| Default cycle count | 200 (0x00C8) per axis | [DATASHEET] PNI-UM Table 5-2 |
| Raw output format | 24-bit two's complement per axis, range −8388608…8388607, big-endian MX2,MX1,MX0 | [DATASHEET] PNI-UM §5.5, Table 5-5 |
| Counts → µT | `B_uT = counts / gain(CC)`; e.g. CC=200: `counts/75` | [DATASHEET] gain from Table 3-1 |
| Other CCs | **UNKNOWN** — PNI publishes gain only for CC 50/100/200. Gain is *approximately* proportional to CC (20→38→75), but PNI gives no formula; do not extrapolate without labelling it [DERIVED-APPROX]. Usable CC range "above ~30" to "~400" | [DATASHEET] PNI-UM §5.1 |
| I2C 7-bit address | **0x20–0x23** (upper 5 bits 0b01000 fixed; lower 2 bits from pins 3 and 28) | [DATASHEET] PNI-UM §4.5; ArduPilot probes all four [SOURCE-CODE] |
| I2C / SPI clock | ≤ 1 MHz (SCL / SCLK) | [DATASHEET] PNI-UM §4.3, §4.4 |
| SPI mode | Mode 0 (CPOL=CPHA=0) or Mode 3 (CPOL=CPHA=1); read = reg \| 0x80 | [DATASHEET] PNI-UM §4.4, §5 |
| Interface select | I2CEN pin 22: HIGH = I2C, LOW = SPI | [DATASHEET] PNI-UM Table 4-1 |
| REVID (reg 0x36) | PNI does **not** publish the value. INAV detects RM3100 by REVID == **0x22** | [SOURCE-CODE] INAV `compass_rm3100.c` |
| Supply | 2.0–3.6 V (typ 3.0 V) for the bare MagI2C ASIC; idle 1 µA | [DATASHEET] PNI-UM Table 3-5 |
| Firmware defaults (ArduPilot & INAV drivers) | CC=200, TMRC=0x94 (~150 Hz), CMM=0x71 | [SOURCE-CODE] (links in §4) |
| **What our FC actually receives from the Matek CAN module** | DroneCAN `uavcan.equipment.ahrs.MagneticFieldStrength`, **float16 Gauss** (1 G = 100 µT), **≤ 25 Hz**; or MSP2_SENSOR_COMPASS **int16 milligauss** (1 mG = 0.1 µT) over UART2 @115200 | [SOURCE-CODE] AP_Periph `compass.cpp`, `msp.cpp`, `msp_sensors.h` (see §2) |

**Matek CAN module note:** our part (MATEKSYS CAN-L4-3100) puts the RM3100 on the SPI bus of an STM32L431
running ArduPilot AP_Periph and talks **DroneCAN** (or optionally MSP over UART) to the FC — the FC never sees
the RM3100 registers, I2C address or cycle count; it receives field values already scaled to Gauss/milligauss.
For Sim/Math: model the *delivered* quantisation & rate (float16 G @ ≤25 Hz, or int16 mG), not raw RM3100 counts. See §2.

---

## 1. PNI RM3100 sensor (chip level)

All §1 values: [DATASHEET] PNI-UM (URL above) unless tagged otherwise. Section/table numbers refer to PNI-UM V16.0.

### 1.1 Architecture
- Three magneto-inductive coils (2× Sen-XY-f, 1× Sen-Z-f) driven by the **MagI2C** ASIC; each coil is the inductor of an
  LR relaxation oscillator and the ASIC counts its internal clock over N sensor cycles ("cycle count", CC) — so
  resolution/noise/rate are set by CC (PNI-UM §2/§4.1). [DATASHEET]
- Circuit oscillation frequency 180 kHz; bias resistor Rb 121 Ω; REXT 33 kΩ (Table 3-1). [DATASHEET]
- Output is a signed count, not an analogue level; no offset-drift claim is quantified by PNI in the manual
  (Matek's product page says "inherently free from offset drift" [OFFICIAL-DOC] — marketing wording, no number).

### 1.2 Performance vs cycle count (Table 3-1, typical, 3.0 V, 121 Ω, 33 kΩ, room temp) [DATASHEET]

| CC | Gain (LSB/µT) | µT per LSB [DERIVED = 1/gain] | Sensitivity (nT) | Noise (nT) | Repeatability over ±200 µT (nT) | Max single-axis rate (Hz) | Max 3-axis rate (Hz) [DATASHEET sales sheet] | Single-axis avg current @24 Hz (µA) |
|---|---|---|---|---|---|---|---|---|
| 50  | 20 | 0.0500 | 50 | 30 | 15 | 1600 | 534 | 70 |
| 100 | 38 | 0.0263 | 26 | 20 | 8  | 850  | 284 | 135 |
| 200 | 75 | 0.0133 | 13 | 15 | 8  | 440  | 147 | 260 |
| 300, 400, others | **UNKNOWN** (not published) | – | – | – | – | – | – | – |

Common to all CC: range −800…+800 µT; noise density @ max single-axis rate 1.2 nT/√Hz; hysteresis over ±200 µT 15 nT;
linearity over ±200 µT 0.5 %; operating temperature −40…+85 °C. [DATASHEET]
- Range footnote: "monotonic region of the output characteristic curve … can be extended using different bias resistors".
  PNI's product page/sales sheet state **±1100 µT** — conflicting with the manual's ±800 µT. Use ±800 µT as the
  conservative figure. [DATASHEET] / [OFFICIAL-DOC] https://www.pnisensor.com/rm3100/
- Useful CC range: quantisation "generally dictate[s] working above ~30", noise limits the useful upper range to "~400"; register
  allows 0…65,535 (manual says "65,536") (§5.1). [DATASHEET]
- 24-bit result full scale is ±8,388,607 counts → at CC=200 that would be ±111,848 µT [DERIVED = 8388607/75], i.e. the
  register never saturates within the ±800 µT sensor range; range is limited by the sensor, not the register.
- Earth's field (25–65 µT) is far inside range; 50 µT at CC=200 ≈ 3,750 counts [DERIVED = 50×75].

### 1.3 Power (MagI2C, Table 3-5) [DATASHEET]
| Parameter | Min | Typ | Max |
|---|---|---|---|
| AVDD/DVDD | 2.0 V | 3.0 V | 3.6 V (abs max 3.7 V) |
| DVDD−AVDD during operation | −0.1 V | 0 | +0.1 V |
| Supply ripple | – | – | 0.05 Vpp |
| Idle current | – | 1 µA | – |
| VIH / VIL | ≥0.7·DVDD | – | ≤0.3·DVDD |
Not relevant to us directly: our Matek module regulates its own 3.3 V from 5 V (see §2).

### 1.4 Interfaces (§4.3–4.5) [DATASHEET]
- **I2CEN (pin 22)**: HIGH = I2C, LOW = SPI.
- **SPI**: SCLK ≤ 1 MHz; Mode 0 (CPOL=CPHA=0) or Mode 3 (CPOL=CPHA=1); first byte = R/W bit (write = 0, read = 1 i.e.
  `reg | 0x80`) + 7-bit address; device returns STATUS while the address byte is clocked; auto-increment while SSN low;
  timing: SSN-low→command ≥100 ns, setup/hold ≥50 ns, SSN high between transactions ≥100 ns (Table 4-2).
  In Mode 3, MISO also indicates data-ready while SSN is low.
- **I2C**: 7-bit address `0b01000 A1 A0` → **0x20, 0x21, 0x22, 0x23**; A0/A1 from pins 3 (SSN/SA*) and 28 (MISO/SA*).
  Standard, Fast, Fast-plus and High-speed modes per NXP UM10204 rev 03; SCL ≤ 1 MHz per pin description;
  register pointer auto-increments; NACK on invalid write (see HSHAKE).
  - ⚠ The pin-3 vs pin-28 → address-bit mapping is **contradictory** across PNI revisions (r06 says pin 28 = bit 0;
    V16.0 text calls pin 3 "SA0" but also "bit 0"/"second-least significant"). Revision R13 (2024-06-05) says it fixed
    an SA0/SA1 error, but the V16 wording is still self-inconsistent → treat mapping as **UNKNOWN**; irrelevant to our
    CAN module (it uses SPI internally — §2).
- **DRDY (pin 23)**: goes HIGH when a measurement completes; cleared by reading the result registers or by a register write
  (configurable via HSHAKE DRC0/DRC1). Optional — STATUS bit 7 gives the same information.

### 1.5 Register map (Table 5-1) [DATASHEET]
Write address = reg; read address = reg | 0x80.

| Name | Addr | R/W | Default | Format / meaning |
|---|---|---|---|---|
| POLL | 0x00 | RW | 0x00 | single measurement: bit6 PMZ, bit5 PMY, bit4 PMX (all axes = **0x70**) |
| CMM | 0x01 | RW | 0x00 | continuous mode: bit6 CMZ, bit5 CMY, bit4 CMX, bit2 DRDM, bit0 START |
| CCX | 0x04–0x05 | RW | 0x00C8 (=200) | uint16 cycle count X (MSB first) |
| CCY | 0x06–0x07 | RW | 0x00C8 | uint16 cycle count Y |
| CCZ | 0x08–0x09 | RW | 0x00C8 | uint16 cycle count Z |
| TMRC | 0x0B | RW | 0x96 | CMM update rate (upper nibble must be 0x9) |
| MX | 0x24–0x26 | R | 0 | int24 two's complement, MSB first |
| MY | 0x27–0x29 | R | 0 | int24 |
| MZ | 0x2A–0x2C | R | 0 | int24 (read 9 bytes from 0x24 / 0xA4 for all axes) |
| BIST | 0x33 | RW | 0x00 | bit7 STE, bit6 ZOK, bit5 YOK, bit4 XOK, bits3:2 BW (timeout 30/60/120 µs), bits1:0 BP (1/2/4 LR periods) |
| STATUS | 0x34 | R | 0x00 | bit7 = DRDY; bits 6:0 indeterminate |
| HSHAKE | 0x35 | RW | 0x1B | bit6 NACK2 (read before ready), bit5 NACK1 (POLL/CMM conflict), bit4 NACK0 (undefined reg), bit1 DRC1, bit0 DRC0 |
| REVID | 0x36 | R | **not published by PNI** | INAV's driver expects **0x22** [SOURCE-CODE]; ArduPilot instead uses the CC default 0x00C8 as a "whoami" [SOURCE-CODE] |

Notes / inconsistencies in the manual (flagged, not resolved):
- CMM: §5.2 text says DRDM is "two bits" with "4 possible conditions", but the bit map and Table 5-3 show one bit
  (0 = DRDY after full CMX/CMY/CMZ sequence, 1 = after any axis). The SPI example uses **0x79** (sets bit 3, which the bit map
  says must be 0); ArduPilot and INAV both write **0x71** (CMX|CMY|CMZ|START). [DATASHEET]/[SOURCE-CODE]
- Reading CMM or writing TMRC terminates continuous mode; POLL during CMM is ignored (NACK1). [DATASHEET]
- ArduPilot's source defines `RM3100_HSHAKE_REG 0x34` (same as STATUS; the datasheet says 0x35) — unused macro, harmless. [SOURCE-CODE]

### 1.6 Sample rate: single (POLL) vs continuous (CMM + TMRC)
- POLL: one measurement of the selected axes then idle; rate limited by CC (Table 3-1 single-axis max ÷ 3 for 3 axes). [DATASHEET]
- CMM: rate set by TMRC (Table 5-4, approx., 1σ tolerance ~7 %), **capped by the CC-limited maximum**. [DATASHEET]

| TMRC | Interval | Rate |  | TMRC | Interval | Rate |
|---|---|---|---|---|---|---|
| 0x92 | ~1.7 ms | ~600 Hz | | 0x99 | ~220 ms | ~4.5 Hz |
| 0x93 | ~3 ms | ~300 Hz | | 0x9A | ~440 ms | ~2.3 Hz |
| 0x94 | ~7 ms | ~150 Hz | | 0x9B | ~0.8 s | ~1.2 Hz |
| 0x95 | ~13 ms | ~75 Hz | | 0x9C | ~1.6 s | ~0.6 Hz |
| 0x96 (default) | ~27 ms | ~37 Hz | | 0x9D | ~3.3 s | ~0.3 Hz |
| 0x97 | ~55 ms | ~18 Hz | | 0x9E | ~6.7 s | ~0.15 Hz (older r06 misprinted 0.015) |
| 0x98 | ~110 ms | ~9 Hz | | 0x9F | ~13 s | ~0.075 Hz |

- ⚠ Inconsistency: the TMRC note says "if CC = 200 … maximum 3-axis update rate is ~430 Hz", while Table 3-1 gives
  440 Hz single-axis (÷3 ≈ 147 Hz 3-axis [DERIVED]) and the sales sheet says 147 Hz 3-axis. Treat **147 Hz** as the 3-axis
  limit at CC=200; "~430 Hz" looks like a single-axis figure. [DATASHEET]
- ArduPilot/INAV drivers: TMRC 0x94 (~150 Hz) and CC=200 → effective ~147 Hz [DERIVED]; ArduPilot polls STATUS at 80 Hz. [SOURCE-CODE]

### 1.7 Conversion recipe (for Math/Sim)
```
raw24 = (b2<<16)|(b1<<8)|b0 ; if raw24 & 0x800000: raw24 -= 1<<24     # [DATASHEET] §5.5 two's complement
B_uT  = raw24 / gain(CC)       # gain: 50→20, 100→38, 200→75 LSB/µT   [DATASHEET] Table 3-1
```
- Body axes: PNI-UM Figure 4-4 defines the sensor layout for a **North-East-Down** frame (x fwd, y right, z down), which
  matches ARCHITECTURE.md — but on any real board the PCB mounting rotation must be applied (see §2.4, §5). [DATASHEET]
- Noise model suggestion for Sim (not a measurement): Gaussian, σ = noise figure per axis (15 nT at CC=200) — PNI does
  not state whether "Noise" is RMS or p-p → **UNKNOWN**; label any sim choice `[SIMULATED]`.

---

## 2. MATEKSYS CAN-L4-3100 ("AP_Periph CAN Magnetometer RM3100") — the module we own

Source **MATEK-3100**: https://www.mateksys.com/?portfolio=can-l4-3100 (fetched 2026-11-26) [OFFICIAL-DOC]

| Item | Value | Tag |
|---|---|---|
| Product name / SKU | AP_Periph CAN Magnetometer RM3100, **CAN-L4-3100** (name verified) | [OFFICIAL-DOC] MATEK-3100 |
| Sensor | PNI RM3100 | [OFFICIAL-DOC] |
| MCU | STM32L431xC, 256 KB flash | [OFFICIAL-DOC] |
| RM3100 link inside module | **SPI1, mode 0, 1 MHz**, chip-select MAG_CS; rotation `ROTATION_PITCH_180` applied in firmware | [SOURCE-CODE] ArduPilot hwdef `MatekL431-GPS` / `MatekL431-Periph` @6034266 |
| Alternate compass on some variants | QMC5883L at I2C 0x0D, `ROTATION_PITCH_180_YAW_90` ("for different board variants") | [SOURCE-CODE] same hwdef |
| Interfaces | CAN (DroneCAN); UART2 = MSP output (MatekL431-Periph fw); UART3 = external GNSS; SWD (SWCLK/SWDIO) | [OFFICIAL-DOC] |
| Power | **4.5–5.5 V** at 5V pad/pin; **22 mA**; −40…85 °C | [OFFICIAL-DOC] |
| Physical | 36 × 25 × 10 mm, 6 g; JST-GH-4P to JST-GH-4P 20 cm cable included | [OFFICIAL-DOC] |
| CAN termination | "If the CAN wires are too long, bridge the 120R jumper" | [OFFICIAL-DOC] |
| LEDs | Blue fast = booting, blue slow = working, red = 3.3 V | [OFFICIAL-DOC] |
| Firmware | ArduPilot AP_Periph **MatekL431-GPS** (pre-installed) or **MatekL431-Periph**; update via DroneCAN GUI Tool / Mission Planner (`AP_Periph.bin`) or ST-Link (`AP_Periph_with_bl.hex`) | [OFFICIAL-DOC] |
| Matek-recommended mounting | ≥ 10 cm from power lines / ESC / motors / iron | [OFFICIAL-DOC] |
| Counterfeits | Matek warns fake CAN-L4-3100 exist; offers photo check via service@mateksys.com | [OFFICIAL-DOC] |

### 2.1 What it outputs (this is what our app will ultimately see)
- **DroneCAN**: `uavcan.equipment.ahrs.MagneticFieldStrength`, `magnetic_field_ga[3]` as **float16, Gauss**, broadcast
  at most **25 Hz** (`AP_PERIPH_MAG_MAX_RATE 25U`), only when the compass is healthy and has new data. A hi-res variant
  (`dronecan.sensors.magnetometer.MagneticFieldStrengthHiRes`) exists only when built with `AP_PERIPH_MAG_HIRES`
  (ArduPilot has a separate `MatekL431-MagHiRes` hwdef; whether it suits our board/our needs is **UNKNOWN**). [SOURCE-CODE]
  https://github.com/ArduPilot/ardupilot/blob/6034266b5abffd36fb4b89f0bf61fb6db8aed85d/Tools/AP_Periph/compass.cpp
  - float16 quantisation at Earth-field magnitudes: for |B| in 0.25–0.5 G (25–50 µT) step = 2⁻¹² G ≈ 0.024 µT (24 nT);
    for 0.5–1 G step ≈ 49 nT [DERIVED from IEEE-754 half precision, 10-bit mantissa]. Comparable to / slightly above RM3100 noise.
- **MSP** (UART2, MSPv2 native, 115200 baud): `MSP2_SENSOR_COMPASS` with `int16 magX/magY/magZ` in **milligauss**
  (front/right/down) + `uint32 time_ms` + `uint8 instance`. Resolution 1 mG = **0.1 µT** [DERIVED] — ~7× coarser than the
  RM3100's 13 nT at CC=200. Rate: sent whenever a new compass sample exists; exact rate **UNKNOWN** (not rate-limited in
  `msp.cpp`; depends on AP_Periph loop). [SOURCE-CODE] `Tools/AP_Periph/msp.cpp`, `libraries/AP_MSP/msp_sensors.h`;
  INAV defines the same struct (`mspSensorCompassDataMessage_t`) [SOURCE-CODE].
- Internally AP_Periph runs the ArduPilot `AP_Compass_RM3100` driver (CC=200, TMRC 0x94, scale 1/75 µT per LSB) [SOURCE-CODE].
- ⚠ MSP availability on the pre-installed MatekL431-GPS image: current ArduPilot master hwdef for MatekL431-GPS **does**
  enable MSP (`AP_PERIPH_MSP_ENABLED 1`, port 1) [SOURCE-CODE], while a reseller page says "MSP feature is disabled in
  MatekL431-GPS … reflash with MatekL431-Periph" [RESELLER, https://phaserfpv.com.au/products/matek-can-l4-3100-dronecan-magnetometer].
  Likely version-dependent; for **our unit's firmware version: UNKNOWN**.

### 2.2 FC-side connection options (per Matek)
- **CAN/DroneCAN (ArduPilot)**: `CAN_P1_DRIVER = 1` (or `CAN_P2_DRIVER = 1` for CAN2), `COMPASS_AUTODEC = 1`
  [OFFICIAL-DOC MATEK-3100]; Matek FC pages also list `CAN_D1_PROTOCOL = 1` (DroneCAN) and `COMPASS_TYPEMASK = 0`
  for a CAN compass [OFFICIAL-DOC H743-WLITE / F765-WSE pages].
- **UART/MSP (ArduPilot ≥ 4.1)**: module 5V→FC 4.0–5.3 V, G→GND, TX2→spare FC UART RX; `SERIALx_PROTOCOL = 32` (MSP),
  `SERIALx_BAUD = 115`, `COMPASS_TYPEMASK = 0` (MSP bit not masked). [OFFICIAL-DOC]
- **UART/MSP (INAV ≥ 2.6)**: enable MSP on that UART only, 115200; `set mag_hardware = MSP`;
  `set align_mag = CW90` "if compass is mounted flat with arrow facing forward, and FC arrow facing forward". [OFFICIAL-DOC]
- An FC **without a CAN port** (e.g. the F405 family below) can therefore only use this module via **MSP over UART**.

### 2.3 Power for the module
- 4.5–5.5 V, 22 mA [OFFICIAL-DOC] — well within any Matek FC 5 V BEC (2 A cont. on F405-WTE/F765-WSE/H743-WLITE
  [OFFICIAL-DOC]). Whether the FC's CAN JST-GH 5V pin is powered from USB alone (bench testing without battery): **UNKNOWN per board**.

### 2.4 Orientation of the module
- Firmware already applies `ROTATION_PITCH_180` to the RM3100 (chip is mounted upside-down on the PCB) [SOURCE-CODE hwdef],
  so outputs are intended to be in the board-arrow frame; the remaining FC-side rotation is set with `COMPASS_ORIENT`
  (ArduPilot) or `align_mag` (INAV). Matek's INAV instruction (`align_mag = CW90` for arrow-forward) implies the MSP
  frame is **not** identical to INAV's expected frame — the reason is **UNKNOWN**; verify with a hardware rotation test
  (cannot be done virtually).
- ArduPilot can determine compass orientation automatically during calibration (`COMPASS_AUTO_ROT`; default 2 on Matek FC
  hwdefs `HAL_COMPASS_AUTO_ROT_DEFAULT 2`); detection "CAN fail" near metal/interference. [OFFICIAL-DOC]
  https://ardupilot.org/copter/docs/common-compass-setup-advanced.html , [SOURCE-CODE] Matek hwdefs.

---

## 3. Matek flight controllers — likely candidates (**our exact model is UNKNOWN**)

Pin/peripheral data from mateksys.com product pages [OFFICIAL-DOC] and ArduPilot hwdefs / INAV `target.h` [SOURCE-CODE].
"CAN" = has a CAN transceiver/port usable for the CAN-L4-3100 over DroneCAN.

| Board | MCU | I2C (compass) | CAN | FW targets | Evidence |
|---|---|---|---|---|---|
| **H743-WING V3** (V1/V2/V3 share target) | STM32H743VIT6 | I2C1 PB6/PB7, I2C2 PB10/PB11 (JST-GH, baro DPS310) | **Yes, CAN1 PD0/PD1** (JST-GH-4P) | ArduPilot `MatekH743`, INAV `MATEKH743` | [RESELLER] risingsunfpv (copy of Matek page), [SOURCE-CODE] ArduPilot hwdef MatekH743 (I2C1 PB6/PB7, I2C2 PB10/PB11, CAN1 PD0/PD1, silent pin PD3) |
| **H743-SLIM V3** | STM32H743VIH6 | 2× I2C (same target) | **Yes, 1× CAN** on JST-GH-4P (5V/CAN-H/CAN-L/G) | `MatekH743` / `MATEKH743` | [RESELLER] lumenier, risingsunfpv; [SOURCE-CODE] |
| **H743-WLITE** (EOL) | STM32H743VIH6 | I2C1 CL1/DA1 PB6/PB7 = compass; I2C2 PB10/PB11 on JST-GH-4P = DPS310 0x76 | **Yes, CAN1 PD0/PD1** JST-GH-4P | `MATEKH743` | [OFFICIAL-DOC] https://www.mateksys.com/?portfolio=h743-wlite |
| H743-MINI (V3) | STM32H743 (variant UNKNOWN) | **UNKNOWN** (not verified) | **UNKNOWN** | likely `MatekH743` — **unverified** | – |
| **F405-WTE** (EOL) | STM32F405RGT6 | **1× I2C** (I2C1; ArduPilot hwdef PB8 SCL / PB7 SDA), compass + SPL06 baro share it | **No** (none listed) | ArduPilot `MatekF405-TE`, INAV `MATEKF405TE_SD` | [OFFICIAL-DOC] https://www.mateksys.com/?portfolio=f405-wte ; [SOURCE-CODE] |
| F405-WSE / F405-WING | STM32F405 | 2× I2C (ArduPilot: I2C1 PB8/PB9, I2C2 PB10/PB11; INAV MAG_I2C_BUS = I2C2) | **No** in ArduPilot hwdef | ArduPilot `MatekF405-Wing`, INAV `MATEKF405SE` | [OFFICIAL-DOC] F405-WTE comparison table; [SOURCE-CODE] |
| F405-STD/CTR/OSD family | STM32F405 | I2C1 PB6/PB7 | **No** in hwdef | ArduPilot `MatekF405` | [SOURCE-CODE] |
| F405-HDTE, F405-WMN, F405-MINI-TE etc. | – | **UNKNOWN** (not researched/verified) | **UNKNOWN** | – | – |
| **F765-WSE** (EOL) | STM32F765VIH6 | I2C1 CL1/DA1 PB6/PB7 = compass; I2C2 PB10/PB11 = DPS310 | **Yes, CAN1 PD0/PD1** | ArduPilot/INAV `MATEKF765SE` | [OFFICIAL-DOC] https://www.mateksys.com/?portfolio=f765-wse |
| F765-WING | STM32F767 | I2C1 PB6/PB7, I2C2 PB10/PB11 | CAN pins **commented out** in hwdef → treat as **No** | ArduPilot `MatekF765-Wing` | [SOURCE-CODE] |
| H7A3-SLIM / H7A3-WING | STM32H7A3 | not researched | **UNKNOWN** | `MatekH7A3`, `MatekH7A3-Wing` | [SOURCE-CODE] (names only) |

- All Matek I2C pads above are listed as "5 V tolerant I/O" on the pages that show them [OFFICIAL-DOC].
- Matek FC 3.3 V LDO "for Baro/Compass module": 200 mA continuous (F405-WTE, F765-WSE pages) [OFFICIAL-DOC].
- INAV's `MATEKH743` target also exposes **SPI3 "SPARE for external RM3100"** (SCK PB3, MISO PB4, MOSI PB5, CS PE2 "CS2 pad")
  [SOURCE-CODE INAV target.h] — that is for a *bare* RM3100 breakout, not for our CAN module.
- Implication: the CAN-L4-3100 works over CAN only on H743/F765-SE class boards; on any F405 board it needs MSP over UART.

---

## 4. Firmware support for RM3100 / the CAN module

Pinned sources: ArduPilot `6034266b5a` (master, 2026-11-26), INAV `fce6c94b38` (`maintenance-10.x`, default branch,
2026-11-26; release 10.0.0-rc2), Betaflight `f511ed9e82` (master, 2026-11-26) and tag `2026.6.2`.

### 4.1 ArduPilot
- Direct driver **`AP_Compass_RM3100`** (I2C or SPI): probes I2C **0x20–0x23** on external buses (internal buses only if
  `AP_COMPASS_RM3100_INTERNAL_BUS_PROBING_ENABLED`); whoami = CC registers read back as 0x00C8; sets TMRC 0x94, CMM 0x71,
  CC=200; scale 1/75 µT per LSB (`GAIN_CC200 75.0f`); timer 80 Hz checks STATUS bit7 then reads 9 bytes from 0x24;
  optional `AP_RM3100_REVERSAL_MASK` for boards with wrong axis polarity. [SOURCE-CODE]
  https://github.com/ArduPilot/ardupilot/blob/6034266b5abffd36fb4b89f0bf61fb6db8aed85d/libraries/AP_Compass/AP_Compass_RM3100.cpp
- **For our CAN module** the FC uses the DroneCAN compass backend (not AP_Compass_RM3100):
  - `CAN_P1_DRIVER = 1` (values 0 disabled / 1 first driver …), `CAN_D1_PROTOCOL = 1` (DroneCAN), `CAN_P1_BITRATE`
    default 1,000,000. [SOURCE-CODE] `AP_CANIfaceParams.cpp`, `AP_CANManager_CANDriver_Params.cpp`
  - Driver-disable bitmask — named **`COMPASS_DISBLMSK`** on current master (Matek pages and older firmware call it
    `COMPASS_TYPEMASK`; the rename's release version is UNKNOWN): bit 11 = DroneCAN, bit 16 = RM3100, bit 17 = MSP →
    keep 0 (or at least bits 11/17 clear); default 0. [SOURCE-CODE] `AP_Compass.cpp` L532-537 @6034266
  - `COMPASS_ORIENT` (rotation), `COMPASS_EXTERNAL`, `COMPASS_AUTO_ROT`, `COMPASS_AUTODEC` (default 1), `COMPASS_DEC`,
    `COMPASS_OFFS_MAX` (default **1800**), `COMPASS_MOTCT` (0 disabled / 1 throttle / 2 current). [SOURCE-CODE]
  - Calibration warning "Compass Offsets High: one of your compass offsets exceeds 600, indicating likely magnetic
    interference" [OFFICIAL-DOC] https://ardupilot.org/copter/docs/common-compass-setup-advanced.html
- MSP compass path: `SERIALx_PROTOCOL = 32`, baud 115 (see §2.2). [OFFICIAL-DOC]

### 4.2 INAV
- Driver `src/main/drivers/compass/compass_rm3100.c`, `mag_hardware = RM3100` exists in the setting table. [SOURCE-CODE]
- **SPI only**: in `common_hardware.c` RM3100 is registered only via `BUSDEV_REGISTER_SPI(... RM3100_SPI_BUS, RM3100_CS_PIN ...)`;
  there is **no I2C registration** → an I2C RM3100 is not detected by INAV at this commit. [SOURCE-CODE]
  https://github.com/iNavFlight/inav/blob/fce6c94b38f05ec6a563a2c6e80d99ac5cb2d638/src/main/target/common_hardware.c
- Detection: REVID (0x36) == **0x22**, 5 retries; init TMRC 0x94, CMM 0x71, CC=200. [SOURCE-CODE]
- ⚠ Data path truncates the 24-bit result to int16 as `counts >> 8` [SOURCE-CODE] — i.e. 1 INAV raw LSB = 256 counts
  = 3.41 µT at CC=200 [DERIVED = 256/75]. Whether later INAV code rescales this is **UNKNOWN** (Firmware T4 to check);
  irrelevant for our CAN module, which INAV reads via MSP in mG.
- **DroneCAN in INAV 10.0 (rc)**: supports GPS, battery V/I, param get/set, DNA; on STM32H7 (FDCAN) and STM32F7 (bxCAN);
  **no magnetometer over DroneCAN** — DroneCAN.md feature table has no compass entry and the tree has no DroneCAN mag
  driver. [OFFICIAL-DOC] https://github.com/iNavFlight/inav/blob/fce6c94b38f05ec6a563a2c6e80d99ac5cb2d638/docs/DroneCAN.md
  `MATEKH743` target defines `USE_DRONECAN`, CAN1 PD0/PD1, standby PD3. [SOURCE-CODE]
- **So with INAV the CAN-L4-3100 must be used via MSP**: `set mag_hardware = MSP` (driver `compass_msp.c`), MSP on a UART
  at 115200. [OFFICIAL-DOC MATEK-3100] / [SOURCE-CODE]

### 4.3 Betaflight
- **No RM3100 driver**: `magSensor_e` = DEFAULT, NONE, HMC5883, AK8975, AK8963, QMC5883L, LIS2MDL, LIS3MDL, MPU925X_AK8963,
  IST8310, MMC560X, QMC5883P, **DRONECAN**, BMM350, AK9916; no `compass_rm3100.c` in the tree; no MSP magnetometer type.
  [SOURCE-CODE] https://github.com/betaflight/betaflight/blob/f511ed9e82cfb77fe9e84247bceccd1946272c94/src/main/sensors/compass.h
- **DroneCAN magnetometer: yes, new.** "Add DroneCAN magnetometer support (#15430)" committed 2026-07-17; present in
  release tag **2026.6.2**. `io/dronecan/dronecan_mag.c` subscribes to `MagneticFieldStrength` and `MagneticFieldStrength2`,
  converts Gauss → int16 milligauss. Requires a build with `ENABLE_DRONECAN` + `USE_MAG`; CAN platform drivers exist for
  STM32H7, G4, C5 (and X32) — **no F4/F7 CAN driver** in Betaflight. CLI: `mag_hardware` (lookup includes DroneCAN),
  `dronecan_enabled`, `dronecan_node_id`, `dronecan_device`, `dronecan_dna_enabled`, `can_bitrate_khz` (125–1000). [SOURCE-CODE]
  - Whether the Betaflight cloud build for a Matek H743 target includes DroneCAN + MAG by default: **UNKNOWN**.
  - Exact `mag_hardware` CLI string ("DRONECAN") not verified in a running build: **UNKNOWN**.
  - Hardware-untested by us; maturity of this new feature: **UNKNOWN**.
- Betaflight on an F405 board cannot use our module at all (no RM3100 driver, no CAN, no MSP mag). [SOURCE-CODE]

### 4.4 Summary matrix (our CAN-L4-3100)

| Firmware | H743 / F765-SE (has CAN) | F405 family (no CAN) |
|---|---|---|
| ArduPilot | DroneCAN ✔ (Matek-documented) or MSP ✔ | MSP over UART ✔ (Matek-documented) |
| INAV ≥ 2.6 | MSP over UART ✔ only (INAV 10 DroneCAN has no mag) | MSP over UART ✔ |
| Betaflight | DroneCAN mag only in ≥ 2026.6.x builds with ENABLE_DRONECAN on H7 — unverified | ✘ not supported |

---

## 5. Wiring & orientation notes
- CAN: JST-GH-4P cable supplied (pinout on FC side per Matek: 5V / CAN-H / CAN-L / G on H743-SLIM V3 [RESELLER copy of
  Matek spec]). Matek-to-Matek cable assumed pin-compatible — **UNVERIFIED** for our specific FC; check pin 1 before power-up.
- CAN bus termination: 120 Ω at both ends (INAV DroneCAN.md) [OFFICIAL-DOC]; module has a "120R" bridge jumper. Whether the
  FC end is terminated on-board: **UNKNOWN per board**.
- MSP: module 5V/G/TX2 → FC 4.0–5.3 V / GND / spare UART RX; 115200 baud; no other function on that UART (INAV). [OFFICIAL-DOC]
- Orientation: ArduPilot `COMPASS_ORIENT` / auto-rotation; INAV `align_mag` (Matek: CW90 for arrow-forward via MSP);
  Betaflight `align_mag` (DEFAULT, CW0…CW270FLIP, CUSTOM) [SOURCE-CODE `cli/settings.c`]. Our app must accept a
  configurable mag→body rotation; default to the FC's already-rotated output.
- Placement: ≥ 10 cm from power lines/ESC/motors/iron (Matek) [OFFICIAL-DOC]; mast-mount away from PDB (ArduPilot) [OFFICIAL-DOC].

## 6. Known interference issues
Source **AP-MAGINT**: https://ardupilot.org/copter/docs/common-magnetic-interference.html [OFFICIAL-DOC]
- DC currents in battery→PDB→ESC wiring are the primary source; motor phase wires (AC) matter less; field rises with loop
  area and current and falls ~1/distance³ for z ≫ loop radius → twist power leads, keep them short, prefer 4-in-1 ESCs;
  aluminium shielding helps only for AC, not DC. [OFFICIAL-DOC AP-MAGINT]
- Environment: minimum distances during calibration — 15 cm (keys, phones, batteries…), 50 cm (computers, radios), 2 m
  (bicycle, fire hydrant, road signs, steel pole, magnets, chain-link/barbed-wire fence), 5 m (electrical box, small car/truck,
  power line, concrete & steel building), 10 m (large truck, metal building, heavy machinery) ("not objectively tested" per ArduPilot). [OFFICIAL-DOC AP-MAGINT]
- CompassMot (ArduPilot): throttle 50–75 % for 5–10 s; result < 30 % acceptable, 31–60 % "grey zone", > 60 % move the
  compass. [OFFICIAL-DOC] https://ardupilot.org/copter/docs/common-compass-setup-advanced.html
- Offsets > 600 flagged as likely interference; `COMPASS_OFFS_MAX` default 1800. [OFFICIAL-DOC]/[SOURCE-CODE]
- Motor permanent magnets / steel screws / battery orientation (rotating the battery reverses its field contribution). [OFFICIAL-DOC AP-MAGINT]
- Suggested app warnings (design proposal, not a fact): |B| deviating from the local reference magnitude, |B| correlated with
  throttle/current, sudden heading jumps without gyro yaw rate. Thresholds: **UNKNOWN** — to be set by Math (T2) and labelled [SIMULATED].

---

## 7. Open questions (for PM → owner)
1. **Exact Matek FC model** (silkscreen name + version, e.g. "H743-WING V3", "F405-WTE"). Decides CAN vs MSP-only and the
   FC-side UART/CAN pins. Candidates in §3.
2. **Firmware on the FC** (ArduPilot / INAV / Betaflight + version) — decides the T4 bridge protocol (MAVLink vs MSP) and mag path.
3. **Firmware on the CAN-L4-3100** (MatekL431-GPS vs -Periph, version) — decides whether MSP output is available.
4. Is the module genuine Matek (counterfeit warning)?
5. How is the module mounted on the airframe (arrow direction, distance from power wiring)?
6. Do we need resolution better than float16-Gauss (DroneCAN) / 0.1 µT (MSP)? If yes, a HiRes AP_Periph build would be needed (owner decision; no purchase involved, but reflashing hardware is out of scope for the virtual phase).

## 8. LIMITATIONS (unresolved, as of 2026-11-27 IST)
- L1 Exact Matek FC model and its firmware are UNKNOWN; §3 is a candidate list only.
- L2 Nothing in this sheet is hardware-verified; all numbers are [DATASHEET]/[OFFICIAL-DOC]/[SOURCE-CODE]/[DERIVED].
- L3 PNI publishes gain/noise only for CC 50/100/200; values for other cycle counts are UNKNOWN.
- L4 PNI range conflict: ±800 µT (user manual) vs ±1100 µT (product page/sales sheet).
- L5 PNI manual inconsistencies: SA0/SA1 pin→address-bit mapping; DRDM "two bits" vs one bit; CMM example 0x79 vs bit map;
  "~430 Hz" 3-axis at CC=200 vs 147 Hz. Not resolvable without PNI or hardware.
- L6 REVID value (0x22) comes only from INAV source, not from PNI documentation.
- L7 Whether PNI "Noise" is RMS or peak-to-peak is not stated.
- L8 CAN-L4-3100 MSP output rate and DroneCAN effective rate on our unit are UNKNOWN (code caps DroneCAN at 25 Hz).
- L9 MSP availability on the pre-installed MatekL431-GPS firmware is version-dependent/unverified (reseller vs current source).
- L10 Reason for Matek's INAV `align_mag = CW90` and the module's true output frame are unverified (needs a physical rotation test).
- L11 Betaflight DroneCAN magnetometer support is new (2026-07) and untested by us; inclusion in Matek H743 builds UNKNOWN.
- L12 H743-MINI, F405-HDTE/WMN/MINI-TE, H7A3 boards were not verified (CAN/I2C pads UNKNOWN).
- L13 H743-WING V3 / H743-SLIM V3 specs were read from reseller copies of Matek's pages (mateksys.com URLs for those boards
  returned 404 to our fetcher); pins cross-checked against ArduPilot hwdef only.
- L15 `COMPASS_TYPEMASK` → `COMPASS_DISBLMSK` rename: first ArduPilot release containing it not identified.
- L14 mateksys.com pages may change; values captured 2026-11-26. Source files are not mirrored in the repo (copyright);
  URLs, commit SHAs and file hashes are in `docs/hardware/SOURCES.md`.

## Out of scope for T1
RadioMaster TX16S and the FPV camera/monitor do not measure magnetic heading; they are not covered here.
