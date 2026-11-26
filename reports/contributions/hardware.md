# Contribution report — Hardware Research Engineer (T1)

**Status:** T1 at REVIEW, waiting for the Auditor's sign-off.
**Evidence level:** this is all desk research plus virtual checks. **Nothing is `[HARDWARE-VERIFIED]`.** No physical RM3100, Matek CAN-L4-3100 or Matek FC was connected, and no hardware log exists.
Labels used: `[DATASHEET]` (PNI documents), `[OFFICIAL-DOC]` (mateksys.com, ardupilot.org, INAV/Betaflight docs), `[SOURCE-CODE]` (firmware at pinned commits), `[DERIVED]` (arithmetic on tagged values), `[RESELLER]` (lower-confidence copies), UNKNOWN for anything not established. Nothing is currently tagged `[UNVERIFIED]`: every `[DATASHEET]` value passed re-verification (see §2).

## 1. Deliverables
| Path | Content |
|---|---|
| `docs/hardware/FACTSHEET.md` | Fact sheet: key numbers; RM3100 interface, registers, cycle-count table, TMRC rates, DRDY (§1); Matek CAN-L4-3100 module and its DroneCAN/MSP outputs (§2); likely Matek FC models with I2C/CAN pins (§3); RM3100/module support in ArduPilot, INAV and Betaflight (§4); wiring and orientation (§5); interference (§6); open questions (§7); LIMITATIONS L1–L17 (§8) |
| `docs/hardware/key_numbers.json` | Machine-readable key numbers for the Math, Sim and Firmware teams |
| `docs/hardware/SOURCES.md` | All source URLs, pinned firmware commit SHAs, sha256 of the verified PDFs, and the audit note on the captcha download |
| `docs/hardware/verify_datasheet.py` | Script that checks every `[DATASHEET]` value with a regex against the `pdftotext` output of the PNI PDFs |
| `docs/hardware/VERIFICATION.md` | Output of the 2026-11-27 verification run |
| `TEAM_TRACKER.md` (T1 row + "Limitations — T1 Hardware") | Status and limitations mirror |
| Outside the repo (not cited as evidence): `/workspace/hwsrc/refetch/` | Verified PDF copies (not committed, for copyright reasons). Failed downloads renamed `INVALID-*` in `/workspace/hwsrc/` (see `README-INVALID.txt`) |

Commits: `0534c1e`, `bccda22` (early key numbers), `189aa77` (full fact sheet → REVIEW), `e95f524` (audit follow-up). Most of the fact-sheet body first landed in PM commit `7313846`, which picked up my uncommitted working-tree draft.

## 2. Tests actually executed (re-run 2026-11-27 ~00:25 IST)

### 2.1 Source integrity
Command (in `/workspace/hwsrc/refetch`):
```
sha256sum RM3100-RM2100-Sensor-Suite-User-Manual-V11.0.pdf PNI-Sensor-RM3100-Sales-Sheet.pdf RM3100-User-Manual.pdf
pdfinfo RM3100-RM2100-Sensor-Suite-User-Manual-V11.0.pdf | grep Pages
```
Actual output:
```
2a09457337a6882632681a48e6c62a6dd842287e18f8311b88d748e9b92f1cbf  RM3100-RM2100-Sensor-Suite-User-Manual-V11.0.pdf
ea9c5aa72f58282be052d53abf406cc3a37122c0780fb65b2a0af644d82af52c  PNI-Sensor-RM3100-Sales-Sheet.pdf
164eae6275cf129e71e6b90f86eb22b7cd976d03d83ca6f45959d87895616ceb  RM3100-User-Manual.pdf
Pages:           45
```
Result: the hashes match `SOURCES.md`, and the manual is a real 45-page PDF.

### 2.2 Datasheet value verification
Command (in `/workspace/hwsrc/refetch`):
```
pdftotext -layout RM3100-RM2100-Sensor-Suite-User-Manual-V11.0.pdf v16.txt
pdftotext -layout PNI-Sensor-RM3100-Sales-Sheet.pdf sales.txt
pdftotext -layout RM3100-User-Manual.pdf r06.txt
python3 /workspace/heading-monitor/docs/hardware/verify_datasheet.py v16.txt sales.txt r06.txt
```
Actual output (exit code 0):
```
PASS D1   [um] Gain 20/38/75 LSB/uT @CC50/100/200
PASS D2   [um] Sensitivity 50/26/13 nT
PASS D3   [um] Noise 30/20/15 nT
PASS D4   [um] Noise density 1.2 nT/sqrtHz
PASS D5   [um] Repeatability 15/8/8 nT over ±200 uT
PASS D6   [um] Hysteresis 15 nT
PASS D7   [um] Linearity 0.5 %
PASS D8   [um] Max single-axis rate 1600/850/440 Hz
PASS D9   [um] Single-axis avg current 70/135/260 uA
PASS D10  [um] Range -800..+800 uT (manual)
PASS D11  [um] Rb 121 ohm
PASS D12  [um] REXT 33 kohm
PASS D13  [um] Oscillation 180 kHz
PASS D14  [um] Operating temp -40..+85 C
PASS D15  [um] Supply 2.0/3.0/3.6 V
PASS D16  [um] Abs max supply +3.7 V
PASS D17  [um] Ripple 0.05 Vpp
PASS D18  [um] Idle current 1 uA
PASS D19  [um] I2C upper bits 0b01000
PASS D20  [um] SCLK <= 1 MHz
PASS D21  [um] SPI CPOL=CPHA=0 or 1
PASS D22  [um] I2CEN HIGH=I2C LOW=SPI
PASS D23  [um] Register map POLL 00
PASS D24  [um] CMM 01
PASS D25  [um] CCX 04-05 default 00C8
PASS D26  [um] TMRC 0B default 96
PASS D27  [um] MX 24-26
PASS D28  [um] BIST 33
PASS D29  [um] STATUS 34
PASS D30  [um] HSHAKE 35 default 1B
PASS D31  [um] REVID 36
PASS D32  [um] CC useful ~30..~400
PASS D33  [um] TMRC 0x92 ~600 Hz
PASS D34  [um] TMRC 0x94 ~150 Hz
PASS D35  [um] TMRC 0x96 ~37 Hz (default)
PASS D36  [um] TMRC 0x9E ~0.15 Hz
PASS D37  [um] TMRC 0x9F ~0.075 Hz
PASS D38  [um] TMRC tolerance ~7%
PASS D39  [um] '~430 Hz' note
PASS D40  [um] 24-bit two's complement range
PASS D41  [um] POLL all axes 0x70
PASS D42  [um] SPI CMM example 0x79
PASS D43  [um] STATUS bit7 DRDY
PASS D44  [um] SSN timing 100 ns / setup 50 ns
PASS D45  [um] Rev R13 SA0/SA1 fix
PASS D46  [um] Doc version V16.0
PASS D47  [um] TMRC 93/95/97 rows
PASS D48  [um] TMRC 98-9D rows
PASS D49  [um] BIST wait 30/60/120 us
PASS D50  [um] BIST LR periods 1/2/4
PASS D51  [um] CC register max stated as 65,536
PASS D52  [um] I2CEN pin 22, DRDY pin 23
PASS D53  [um] I2C modes per NXP UM10204 rev 03
PASS D54  [um] Default CC 200 (0xC8)
PASS D55  [um] DRDM: Table 5-3 two conditions
PASS D56  [um] NED sensor layout figure
PASS D57  [um] Mode 3: MISO indicates data ready
PASS D58  [um] VIH >=0.7*DVDD, VIL <=0.3*DVDD
PASS D59  [um] DVDD-AVDD during operation -0.1..+0.1 V
PASS D60  [um] tSSW SSN high between transactions 100 ns
PASS D61  [um] Pin 3/pin 28 I2C address bits text (V16)
PASS R1   [r06] r06 printed 9E as ~0.015 Hz
PASS R2   [r06] r06: SA0 = pin 28 (bit 0)
PASS S1   [sales] Sales: range ±1100 uT
PASS S2   [sales] Sales: 3-axis rate 534/284/147 Hz
PASS S3   [sales] Sales: gain 20/38/75
66/66 passed
```
Result: **66/66 PASS**, so nothing was downgraded to `[UNVERIFIED]`. This only proves the values appear in the PNI documents. It is not a measurement.

### 2.3 key_numbers.json consistency and derived values
Command: `python3 /tmp/kn_check.py`. The script is quoted below. It loads `docs/hardware/key_numbers.json`, asserts gain, range and I2C addresses, and recomputes the `[DERIVED]` values used in the fact sheet.
```python
import json, struct
d = json.load(open("docs/hardware/key_numbers.json"))
r = d["rm3100"]; g = r["gain_lsb_per_uT"]
assert (g["50"], g["100"], g["200"]) == (20, 38, 75)
assert r["range_uT"]["min"] == -800 and r["range_uT"]["max"] == 800
assert r["i2c_addresses"] == ["0x20", "0x21", "0x22", "0x23"]
for cc in ("50", "100", "200"):
    print(f"CC={cc}: {1/g[cc]:.4f} uT/LSB")
print(f"24-bit full scale at CC=200: {8388607/75:.0f} uT")
print(f"INAV counts>>8 at CC=200: {256/75:.3f} uT/LSB")
def f16step(x):
    i = struct.unpack('<H', struct.pack('<e', x))[0]
    return struct.unpack('<e', struct.pack('<H', i+1))[0] - struct.unpack('<e', struct.pack('<H', i))[0]
print(f"float16 step @0.3 G = {f16step(0.3)*1e5:.1f} nT, @0.6 G = {f16step(0.6)*1e5:.1f} nT")
print("key_numbers.json: valid JSON, asserts OK")
```
Actual output (exit code 0):
```
CC=50: 0.0500 uT/LSB
CC=100: 0.0263 uT/LSB
CC=200: 0.0133 uT/LSB
24-bit full scale at CC=200: 111848 uT
INAV counts>>8 at CC=200: 3.413 uT/LSB
float16 step @0.3 G = 24.4 nT, @0.6 G = 48.8 nT
key_numbers.json: valid JSON, asserts OK
```
Result: the JSON is valid and the asserts pass. The derived values match the fact sheet (0.0133 µT/LSB, 111,848 µT, 3.413 µT/LSB, 24.4/48.8 nT).

### 2.4 Not executed
- No hardware tests (no hardware available; see BLOCKERS B1).
- No firmware builds or SITL runs. All firmware statements are `[SOURCE-CODE]` reading at the pinned commits.

## 3. Open limitations (same as FACTSHEET §8 and TEAM_TRACKER.md)
- L1 Exact Matek FC model and FC firmware UNKNOWN (candidate list only; BLOCKERS B2).
- L2 No hardware verification; all numbers are DATASHEET / OFFICIAL-DOC / SOURCE-CODE / DERIVED.
- L3 RM3100 gain and noise are published only for cycle counts 50/100/200.
- L4 Range conflict: ±800 µT (PNI manual) vs ±1100 µT (PNI product page and sales sheet).
- L5 PNI manual internal inconsistencies: SA0/SA1 mapping, DRDM width, CMM 0x79 example, ~430 Hz vs 147 Hz 3-axis.
- L6 REVID 0x22 is known only from INAV source, not from PNI docs.
- L7 PNI does not say whether "noise" is RMS or peak-to-peak.
- L8 Actual MSP / DroneCAN output rates of our CAN-L4-3100 are UNKNOWN (DroneCAN is capped at 25 Hz in code).
- L9 MSP output on the pre-installed MatekL431-GPS firmware is version-dependent and unverified.
- L10 The module's output frame and the reason for Matek's INAV `align_mag = CW90` are unverified (needs a physical rotation test).
- L11 Betaflight DroneCAN magnetometer support (added 2026-07, in tag 2026.6.2) is untested; whether Matek H743 builds include it is UNKNOWN.
- L12 H743-MINI, F405-HDTE/WMN/MINI-TE and H7A3 boards were not verified.
- L13 H743-WING/SLIM V3 specs come from reseller copies of Matek pages `[RESELLER]`, cross-checked against the ArduPilot hwdef.
- L14 Web sources may change; PDFs are not committed (sha256 in SOURCES.md).
- L15 ArduPilot renamed COMPASS_TYPEMASK to COMPASS_DISBLMSK; the first release containing the rename was not identified.
- L16 The PNI manual labels its version three ways (URL V11.0 / PDF metadata V15.0 / content V16.0); values are cited from the V16.0 content.
- L17 Matek H743-WLITE values were read from search extracts of the official page/manual (direct fetch returned 404); pins were cross-checked against the ArduPilot hwdef.

## 4. Money spent and paid tools/services
**None.** No purchases, sign-ups or paid services. Only free public web pages, public GitHub source, and free local tools: curl, poppler-utils (`pdftotext`/`pdfinfo`) and Python 3 standard library.
