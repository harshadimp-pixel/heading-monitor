"""Re-checks every [DATASHEET] value in FACTSHEET.md against text extracted (pdftotext -layout) from the PNI PDFs.
Usage: python verify_datasheet.py <v16_manual.txt> <sales_sheet.txt> <r06_manual.txt>
Each check is a regex that must match in the named document; prints PASS/FAIL. Exit code 1 on any FAIL."""
import re, sys

def norm(t):
    return re.sub(r"[ \t]+", " ", t)

CHECKS = [  # (id, claim, doc, regex)
 ("D1","Gain 20/38/75 LSB/uT @CC50/100/200","um",r"Gain 20 38 75 LSB/μT"),
 ("D2","Sensitivity 50/26/13 nT","um",r"Sensitivity 50 26 13 nT"),
 ("D3","Noise 30/20/15 nT","um",r"Noise 30 20 15 nT"),
 ("D4","Noise density 1.2 nT/sqrtHz","um",r"Noise Density @ Max\. Single-Axis Sample Rate 1\.2 nT/√Hz"),
 ("D5","Repeatability 15/8/8 nT over ±200 uT","um",r"Repeatability over ±200 μT 15 8 8 nT"),
 ("D6","Hysteresis 15 nT","um",r"Hysteresis over ±200 μT 15 nT"),
 ("D7","Linearity 0.5 %","um",r"Linearity over ±200 μT 0\.5 %"),
 ("D8","Max single-axis rate 1600/850/440 Hz","um",r"1600 850 440 Hz"),
 ("D9","Single-axis avg current 70/135/260 uA","um",r"70 135 260 µA"),
 ("D10","Range -800..+800 uT (manual)","um",r"-800 to \+800 μT"),
 ("D11","Rb 121 ohm","um",r"Bias Resistor, R ?b 121 Ω"),
 ("D12","REXT 33 kohm","um",r"33 kΩ"),
 ("D13","Oscillation 180 kHz","um",r"Circuit Oscillation Frequency 180 kHz"),
 ("D14","Operating temp -40..+85 C","um",r"Operating Temperature -40 to \+85"),
 ("D15","Supply 2.0/3.0/3.6 V","um",r"2\.0 3\.0 3\.6"),
 ("D16","Abs max supply +3.7 V","um",r"\+3\.7"),
 ("D17","Ripple 0.05 Vpp","um",r"0\.05"),
 ("D18","Idle current 1 uA","um",r"Idle Mode Current 1 µA"),
 ("D19","I2C upper bits 0b01000","um",r"0b01000"),
 ("D20","SCLK <= 1 MHz","um",r"1 MHz or less"),
 ("D21","SPI CPOL=CPHA=0 or 1","um",r"(?s)\(CPOL=CPHA=0\) or\s+HIGH \(CPOL=CPHA=1\)"),
 ("D22","I2CEN HIGH=I2C LOW=SPI","um",r"(?s)I2CEN.{0,200}?(HIGH|LOW)"),
 ("D23","Register map POLL 00","um",r"POLL 00 RW 00"),
 ("D24","CMM 01","um",r"CMM 01 RW 00"),
 ("D25","CCX 04-05 default 00C8","um",r"CCX 04 ?– ?05 RW 00C8"),
 ("D26","TMRC 0B default 96","um",r"TMRC 0B RW 96"),
 ("D27","MX 24-26","um",r"MX 24 ?– ?26"),
 ("D28","BIST 33","um",r"BIST 33 RW 00"),
 ("D29","STATUS 34","um",r"STATUS 34 R 00"),
 ("D30","HSHAKE 35 default 1B","um",r"HSHAKE 35 RW 1B"),
 ("D31","REVID 36","um",r"REVID 36 R"),
 ("D32","CC useful ~30..~400","um",r"(?s)~30.{0,80}~400"),
 ("D33","TMRC 0x92 ~600 Hz","um",r"92 ~1\.7 ms ~600 Hz"),
 ("D34","TMRC 0x94 ~150 Hz","um",r"94 ~7 ms ~150 Hz"),
 ("D35","TMRC 0x96 ~37 Hz (default)","um",r"96 ~27 ms ~37 Hz"),
 ("D36","TMRC 0x9E ~0.15 Hz","um",r"9E ~6\.7 s ~0\.15 Hz"),
 ("D37","TMRC 0x9F ~0.075 Hz","um",r"9F ~13 s ~0\.075 Hz"),
 ("D38","TMRC tolerance ~7%","um",r"~7%"),
 ("D39","'~430 Hz' note","um",r"~430 Hz"),
 ("D40","24-bit two's complement range","um",r"-8388608\s+to 8388607"),
 ("D41","POLL all axes 0x70","um",r"0x70"),
 ("D42","SPI CMM example 0x79","um",r"0x79"),
 ("D43","STATUS bit7 DRDY","um",r"Bit 7 will be HIGH"),
 ("D44","SSN timing 100 ns / setup 50 ns","um",r"(?s)SSN LOW to Command Byte 100.*?Setup data before active edge 50"),
 ("D45","Rev R13 SA0/SA1 fix","um",r"R13 Updated Section 4\.3\.3 to fix error with SA0 and SA1"),
 ("D46","Doc version V16.0","um",r"Doc 1017252 V16\.0"),
 ("D47","TMRC 93/95/97 rows","um",r"(?s)93 ~3 ms ~300 Hz.*95 ~13 ms ~75 Hz.*97 ~55 ms ~18 Hz"),
 ("D48","TMRC 98-9D rows","um",r"(?s)98 ~110.*~9 Hz.*99 ~220.*~4\.5 Hz.*9A ~440.*~2\.3 Hz.*9B ~0\.8 s ~1\.2 Hz.*9C ~1\.6 s ~0\.6 Hz.*9D ~3\.3 s ~0\.3 Hz"),
 ("D49","BIST wait 30/60/120 us","um",r"(?s)\(30 µs\).*\(60 µs\).*\(120 µs\)"),
 ("D50","BIST LR periods 1/2/4","um",r"(?s)1 LR Period.*2 LR Periods.*4 LR Periods"),
 ("D51","CC register max stated as 65,536","um",r"65,536"),
 ("D52","I2CEN pin 22, DRDY pin 23","um",r"(?s)22 I2CEN.*23 DRDY"),
 ("D53","I2C modes per NXP UM10204 rev 03","um",r"(?s)UM10204.*revision 03"),
 ("D54","Default CC 200 (0xC8)","um",r"200D"),
 ("D55","DRDM: Table 5-3 two conditions","um",r"(?s)DRDY to HIGH after a full measurement.*DRDY to HIGH after the completion of a"),
 ("D56","NED sensor layout figure","um",r"North-East-Down \(NED\)"),
 ("D57","Mode 3: MISO indicates data ready","um",r"CPHA=CPOL=1, the MISO line also indicates"),
 ("D58","VIH >=0.7*DVDD, VIL <=0.3*DVDD","um",r"(?s)0\.7\*DVDD.*0\.3\*DVDD"),
 ("D59","DVDD-AVDD during operation -0.1..+0.1 V","um",r"-0\.1 0 \+0\.1"),
 ("D60","tSSW SSN high between transactions 100 ns","um",r"(?s)SSN HIGH to LOW.{0,80}100"),
 ("D61","Pin 3/pin 28 I2C address bits text (V16)","um",r"(?s)SA0 \(pin 3\).*second-least significant bit.*SA1 \(pin 28\).*least significant bit"),
 ("R1","r06 printed 9E as ~0.015 Hz","r06",r"9E ~6\.7 s ~0\.015 Hz"),
 ("R2","r06: SA0 = pin 28 (bit 0)","r06",r"SA0 \(pin 28\)"),
 ("S1","Sales: range ±1100 uT","sales",r"±1100 µT"),
 ("S2","Sales: 3-axis rate 534/284/147 Hz","sales",r"534 Hz 284 Hz 147 Hz"),
 ("S3","Sales: gain 20/38/75","sales",r"20 µT 38 µT 75 µT"),
]

def main():
    docs = {"um": norm(open(sys.argv[1], encoding="utf-8").read()),
            "sales": norm(open(sys.argv[2], encoding="utf-8").read()),
            "r06": norm(open(sys.argv[3], encoding="utf-8").read())}
    fails = 0
    for cid, claim, d, rx in CHECKS:
        ok = re.search(rx, docs[d]) is not None
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'} {cid:4} [{d}] {claim}")
    print(f"{len(CHECKS)-fails}/{len(CHECKS)} passed")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
