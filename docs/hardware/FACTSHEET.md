# Hardware Fact Sheet — PNI RM3100 + Matek FC (T1)

Owner: Hardware Research Engineer. Status: DRAFT (key numbers first; full sheet follows below).
Evidence tags: `[DATASHEET]` = PNI manufacturer document; `[OFFICIAL-DOC]` = vendor/project documentation
(mateksys.com, ardupilot.org, INAV/Betaflight docs); `[SOURCE-CODE]` = firmware source at a pinned commit;
`[DERIVED]` = arithmetic on tagged numbers (formula shown). Nothing here is `[HARDWARE-VERIFIED]`.

Primary source (abbrev. **PNI-UM**): PNI Sensor, *RM3100 & RM2100 Magneto-Inductive Magnetometer User Manual*,
Doc 1017252 V16.0 (rev. block to R16, 2026-08-28),
https://www.pnisensor.com/wp-content/uploads/RM3100-RM2100-Sensor-Suite-User-Manual-V11.0.pdf
(file downloaded 2026-11-26, sha256 `2a09457337a6882632681a48e6c62a6dd842287e18f8311b88d748e9b92f1cbf`; the URL
says V11.0 but the file content is V16.0).

## Key numbers (for Math / Sim / Firmware)

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
| Firmware defaults (ArduPilot & INAV) | CC=200, TMRC=0x94 (~150 Hz), CMM=0x71 | [SOURCE-CODE] (links in §4) |

**Matek CAN module note:** our part (MATEKSYS "RM3100 AP_Periph CAN" magnetometer) puts the RM3100 behind an
STM32 running ArduPilot AP_Periph and talks **DroneCAN** to the FC — the FC never sees the RM3100 registers,
I2C address or cycle count; it receives calibrated-scale field values in DroneCAN messages. See §2.
