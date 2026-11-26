"""T1: consistency check of docs/hardware/key_numbers.json + recompute [DERIVED] values used in FACTSHEET.md.
Run from the repo root:  python3 docs/hardware/check_key_numbers.py   (exit 0 = pass)"""
from pathlib import Path
import json, struct
d = json.load(open(Path(__file__).resolve().parent / "key_numbers.json"))
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
