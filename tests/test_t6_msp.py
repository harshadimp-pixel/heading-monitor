"""M1-M4 MSP framing, robustness, resync, source labelling, schema conformance of firmware_bridge output. [SIMULATED]
Frames are built by T6's own encoder (tests/msp_frames.py, from the public MSP v1/v2 description), not the bridge's."""
import json, os, random, struct, subprocess, sys, tempfile, pytest, jsonschema
from conftest import load, ROOT
from msp_frames import v1, v2, raw_imu, attitude, crc8_dvb_s2

SCHEMA = json.load(open(os.path.join(ROOT, "contracts", "sample.schema.json")))

@pytest.fixture(scope="module")
def fb(): return load("firmware_bridge")

def frames(fb, chunks):
    p = fb.MSPParser(); out = []
    for c in chunks: out += p.feed(c)
    return out, p

def test_frame_builder_selfcheck():
    assert v1(108, direction=b"<") == b"$M<\x00\x6c\x6c"
    # CRC-8/DVB-S2 check value for "123456789" is 0xBC (CRC catalogue)
    assert crc8_dvb_s2(b"123456789") == 0xBC

def test_M1_decode_exact(fb):
    imu = raw_imu((10, -20, 512), (1, 2, 3), (1234, -567, 3000)); att = attitude(-125, 300, 271)
    for enc in (v1, v2):
        fr, _ = frames(fb, [enc(102, imu) + enc(108, att)])
        assert [f.cmd for f in fr] == [102, 108] and fr[0].payload == imu and fr[1].payload == att
    d = fb.scaling.decode_raw_imu(imu); a = fb.scaling.decode_attitude(att)
    assert d == {"acc": [10, -20, 512], "gyro": [1, 2, 3], "mag": [1234, -567, 3000]}
    assert a == {"roll": -12.5, "pitch": 30.0, "yaw": 271.0}

def test_M1_bridge_encoder_matches_t6(fb):
    imu = raw_imu()
    assert fb.encode_v1(102, imu, ">") == v1(102, imu)
    assert fb.encode_v2(102, imu, ">") == v2(102, imu)

def test_M2_byte_by_byte_and_split(fb):
    s = (v1(102, raw_imu()) + v2(108, attitude())) * 5
    fr, _ = frames(fb, [bytes([b]) for b in s]); assert len(fr) == 10
    rnd = random.Random(1); chunks, i = [], 0
    while i < len(s):
        n = rnd.randint(1, 17); chunks.append(s[i:i + n]); i += n
    assert len(frames(fb, chunks)[0]) == 10

@pytest.mark.parametrize("kind", ["v1_bad_xor", "v2_bad_crc"])
def test_M2_checksum_rejected(fb, kind):
    f = bytearray(v1(102, raw_imu()) if kind == "v1_bad_xor" else v2(102, raw_imu())); f[-1] ^= 0x5A
    fr, p = frames(fb, [bytes(f) + v1(108, attitude())])
    assert [x.cmd for x in fr] == [108] and p.stats.bad_checksum >= 1

def test_M2_payload_bitflip_rejected(fb):
    good = v1(102, raw_imu()); rejected = 0
    for i in range(5, len(good) - 1):
        for bit in range(8):
            f = bytearray(good); f[i] ^= 1 << bit
            fr, _ = frames(fb, [bytes(f)])
            ok = [x for x in fr if x.cmd == 102 and x.payload == raw_imu()]
            assert not ok or bytes(f) == good
            rejected += not fr
    assert rejected >= 1

def test_M2_truncated_then_valid(fb):
    a = v1(102, raw_imu()); b = v2(108, attitude())
    fr, _ = frames(fb, [a[:10] + b + v1(108, attitude())])
    print("M2 truncated-then-valid recovered cmds:", [x.cmd for x in fr])
    assert [x.cmd for x in fr][-1:] == [108] and len(fr) >= 1

def test_M2_length_mismatch_short(fb):
    """Header claims fewer bytes than present -> checksum lands on payload byte -> rejected, next frame recovered."""
    imu = raw_imu(); f = bytearray(v1(102, imu)); f[3] = 10
    fr, _ = frames(fb, [bytes(f) + v1(108, attitude())])
    assert all(x.cmd != 102 or x.payload != imu[:10] for x in fr) and fr[-1].cmd == 108

def test_M2_length_mismatch_long_resync_latency(fb):
    """Corrupted length byte claims MORE bytes than sent (e.g. 200). Valid frames that follow are buffered;
    measure how many extra bytes must arrive before they are emitted (live: delay; end of replay: loss)."""
    f = bytearray(v1(102, raw_imu())); f[3] = 200
    valid = v1(108, attitude())
    p = fb.MSPParser(); got = p.feed(bytes(f) + valid * 3)
    emitted_immediately = len(got)
    extra = 0
    while len(got) < 3 and extra < 5000:
        got += p.feed(valid); extra += len(valid)
    print(f"M2 long-length: {emitted_immediately}/3 valid frames emitted immediately; needed {extra} more bytes to resync")
    assert len(got) >= 3

def test_M2_jumbo_oversize_and_garbage_fuzz(fb):
    from firmware_bridge import bridge
    builder = fb.SampleBuilder(source="replay"); leaked = []
    rnd = random.Random(1234); total_valid = total_got = false_accepts = 0
    good = [v1(102, raw_imu()), v1(108, attitude()), v2(102, raw_imu()), v2(108, attitude())]
    for trial in range(2000):
        stream = bytearray(); n_valid = 0
        for _ in range(rnd.randint(1, 6)):
            r = rnd.random()
            if r < 0.4:
                stream += rnd.choice(good); n_valid += 1
            elif r < 0.6:
                stream += bytes(rnd.getrandbits(8) for _ in range(rnd.randint(1, 40)))
            elif r < 0.8:
                g = bytearray(rnd.choice(good)); g[rnd.randrange(3, len(g))] ^= 1 << rnd.randrange(8); stream += g
            else:
                stream += b"$M>" + bytes([255, 102]) + struct.pack("<H", rnd.randint(4097, 65535))  # oversize jumbo
        stream += good[1] * 0  # nothing appended
        fr, p = frames(fb, [bytes(stream)])
        for f in fr:
            if f.cmd in (102, 108) and f.payload not in (raw_imu(), attitude()):
                false_accepts += 1  # frame-level: corrupted frame passed the 8-bit checksum (inherent 1/256 collision)
                st = bridge._ReplayState(); st.attitude = None
                samples = bridge.frames_to_samples([f], 0.0, builder, st)
                if samples or (f.cmd == 108 and st.attitude is not None):
                    leaked.append((f.version, f.cmd, f.payload.hex()))
        total_valid += n_valid; total_got += sum(1 for f in fr if f.payload in (raw_imu(), attitude()))
    print(f"M2 fuzz 2000 streams: valid frames sent {total_valid}, recovered {total_got} ({total_got/total_valid:.1%}), corrupted frames passing checksum {false_accepts} (8-bit checksum collisions), of which leaked into samples/attitude {len(leaked)}: {leaked}")
    assert not leaked
    assert total_got / total_valid >= 0.95

def test_M2_error_frame(fb):
    fr, _ = frames(fb, [v1(102, b"", b"!") + v1(108, attitude())])
    assert fr[0].is_error and fr[1].cmd == 108

def test_M3_fake_fc_is_sim_and_schema_valid():
    p = subprocess.run([sys.executable, "-m", "firmware_bridge", "--fake-fc", "--count", "50"], cwd=ROOT,
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]
    lines = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
    assert len(lines) == 50
    for s in lines:
        jsonschema.validate(s, SCHEMA); assert s["source"] == "sim"
    print("M3 fake-fc: 50 samples, all source=sim, schema-valid; first mag_uT", lines[0]["mag_uT"], "accel", lines[0].get("accel_g"))

def _replay(path, *extra):
    return subprocess.run([sys.executable, "-m", "firmware_bridge", "--replay", path, *extra], cwd=ROOT,
                          capture_output=True, text=True, timeout=60)

def test_M3_replay_relabels_hardware_and_binary(tmp_path):
    j = tmp_path / "hw.jsonl"
    j.write_text("\n".join(json.dumps({"t": i * .05, "source": "hardware", "mag_uT": [20, 1, 40], "accel_g": [0, 0, -1]}) for i in range(5)))
    out = [json.loads(l) for l in _replay(str(j)).stdout.splitlines() if l.strip()]
    assert len(out) == 5 and all(s["source"] == "replay" and s["meta"]["original_source"] == "hardware" for s in out)
    b = tmp_path / "raw.bin"
    b.write_bytes(b"\x00\xffgarbage" + (v1(108, attitude()) + v1(102, raw_imu())) * 4 + b"$M>\x05")
    p = _replay(str(b)); out = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
    for s in out:
        jsonschema.validate(s, SCHEMA); assert s["source"] == "replay"
    print("M3 binary replay:", len(out), "samples; mag_uT", out[0]["mag_uT"] if out else None)
    assert len(out) == 4

def test_M3_replay_malformed_sample_lines(tmp_path):
    """Replay of Sample JSONL must not forward contract-violating samples."""
    j = tmp_path / "bad.jsonl"
    rows = [{"t": 0, "source": "sim", "mag_uT": [1, 2]}, {"t": 0.1, "source": "sim", "mag_uT": ["a", 1, 2]},
            {"t": 0.2, "source": "sim", "mag_uT": [20, 1, 40]}]
    j.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
    out = [json.loads(l) for l in _replay(str(j)).stdout.splitlines() if l.strip()]
    invalid = []
    for s in out:
        try: jsonschema.validate(s, SCHEMA)
        except jsonschema.ValidationError as e: invalid.append(e.message)
    print(f"M3 malformed replay: {len(out)} emitted, {len(invalid)} schema-invalid: {invalid}")
    assert not invalid, "bridge replay forwards schema-invalid samples"

def test_M4_inav_scaling(fb):
    b = fb.SampleBuilder(source="replay", profile="inav-msp-mag")
    s = b.from_raw_imu(0.0, {"acc": [0, 0, 512], "gyro": [0, 0, 0], "mag": [250, 0, 433]})
    # INAV FLU -> FRD: (x, -y, -z); mGauss -> 0.1 uT
    assert s["accel_g"] == [0.0, 0.0, -1.0] and s["mag_uT"] == [25.0, 0.0, -43.3]
    jsonschema.validate(s, SCHEMA)
