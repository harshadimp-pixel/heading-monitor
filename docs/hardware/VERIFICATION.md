# Datasheet verification run (T1 audit follow-up)

Run: 2026-11-27 IST on fresh downloads (sha256 in SOURCES.md). Command:
`python docs/hardware/verify_datasheet.py v16.txt sales.txt r06.txt` → exit 0

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
