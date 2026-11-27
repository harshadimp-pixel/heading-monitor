"""T6 black-box regression tests for D8 (ARCHITECTURE.md, PM decision 1bef73e): a serial connection is NOT proof
of hardware. Written from the ARCHITECTURE D8 text only; no product code is called except the CLIs
(`python -m app`, `python -m firmware_bridge`) and the product FakeFC class used as a device on a pty.

Expected outcomes (T6 reading of D8 items 1-5):
  fake FC / simulator identity (variant SIML, board SIMF) over serial  -> SIMULATED (sample.source "sim")
  unknown / unidentified device or failed identity query over serial    -> UNVERIFIED SOURCE, never live
  UID listed in config/verified_devices.json                            -> HARDWARE (the ONLY path to HARDWARE)
  UID not listed, missing, truncated, extended, zero                    -> UNVERIFIED SOURCE
  replay of hardware data (even with an allowlisted UID in its meta)    -> REPLAY (recorded hardware), not live
  ingest of hardware data (even with an allowlisted UID in its meta)    -> UNVERIFIED SOURCE, not live
  config/verified_devices.json as shipped                               -> has no entries

The badge is read from the rendered dashboard (headless Chrome --dump-dom, element #sourceBadge) of a fresh app
instance started here on an ephemeral port whose listening PID is verified with `ss`. Each test also checks the
API record field live_hardware. Spec ambiguities are listed in reports/audit/d8_spec_review.md.
All data here is [SIMULATED]; no physical device is involved.
"""
import json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time, urllib.request, urllib.error
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
PY = sys.executable
CHROME = os.environ.get("CHROME") or next((shutil.which(c) for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if shutil.which(c)), None)

try:
    import serial  # noqa: F401
except Exception:
    pytest.skip("NOT RUN: pyserial missing, the serial path cannot be exercised", allow_module_level=True)
if not hasattr(os, "openpty") or not shutil.which("ss"):
    pytest.skip("NOT RUN: openpty or ss unavailable", allow_module_level=True)
if not CHROME:
    pytest.skip("NOT RUN: no headless Chrome for the badge check", allow_module_level=True)

from t6_msp_device import MSPDevice, ProductFakeFCOnPty  # noqa: E402

ALLOWED_UID = bytes([0x36, 0x54, 0x00, 0x2B, 0x11, 0x47, 0x33, 0x30, 0x39, 0x38, 0x31, 0x01])
OTHER_UID = bytes([0x99] * 12)


# ---------------------------------------------------------------- helpers
def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _listener_pid(port):
    o = subprocess.run(["ss", "-ltnpH", f"sport = :{port}"], capture_output=True, text=True).stdout
    m = re.search(r"pid=(\d+)", o); return int(m.group(1)) if m else None


def _http(port, path, obj=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 data=None if obj is None else json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if obj is None else "POST")
    try: b = urllib.request.urlopen(req, timeout=5).read()
    except urllib.error.HTTPError as e: b = e.read()
    try: return json.loads(b or b"{}")
    except ValueError: return {"_raw": b.decode(errors="replace")}


class App:
    def __init__(self, root, *args):
        self.port = _free_port()
        self.cmd = [PY, "-m", "app", "--host", "127.0.0.1", "--port", str(self.port), "--stale", "60", *args]
        self.p = subprocess.Popen(self.cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for _ in range(75):
            time.sleep(0.2)
            if self.p.poll() is not None or _listener_pid(self.port): break
        self.pid_ok = _listener_pid(self.port) == self.p.pid

    def hist(self): return _http(self.port, "/api/history?since=0").get("records", [])

    def wait_records(self, n=8, t=25):
        end = time.time() + t
        while time.time() < end:
            try:
                if len(self.hist()) >= n: return True
            except Exception: pass
            time.sleep(0.3)
        return False

    def close(self):
        self.p.terminate()
        try: out = self.p.communicate(timeout=5)[0]
        except subprocess.TimeoutExpired: self.p.kill(); out = self.p.communicate()[0]
        return out or ""


def _dom(port):
    d = ""
    for _ in range(4):
        prof = tempfile.mkdtemp(prefix="t6-chrome-")   # fresh profile per launch, removed afterwards
        try:
            d = subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-first-run", "--incognito",
                                f"--user-data-dir={prof}", "--virtual-time-budget=5000",
                                "--dump-dom", f"http://127.0.0.1:{port}/"], capture_output=True, text=True, timeout=90).stdout
        finally:
            shutil.rmtree(prof, ignore_errors=True)
        b = _text(d, "sourceBadge")
        if b and b not in ("NO DATA",): break
    return d


def _text(d, id_):
    m = re.search(r'id="%s"[^>]*>(.*?)</' % id_, d, re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip() if m else None


def _visible_text(d):
    d = re.sub(r"<script.*?</script>|<style.*?</style>", " ", d, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", d))


def _run_serial(root, dev):
    """Start a fresh app on serial:<pty of dev>; return (badge, records, visible_text, pid_ok, app_output)."""
    a = App(root, "--source", f"serial:{dev.port}")
    try:
        got = a.wait_records(8, 25)
        d = _dom(a.port) if got else ""
        r = a.hist()
    finally:
        out = a.close()
    return _text(d, "sourceBadge"), r, _visible_text(d), a.pid_ok, out


def _bridge_samples(dev, root=ROOT, n=5, extra=()):
    """Run `python -m firmware_bridge --port <pty> --count n` directly and return the emitted Sample dicts."""
    p = subprocess.run([PY, "-m", "firmware_bridge", "--port", dev.port, "--count", str(n), *extra], cwd=root,
                       capture_output=True, text=True, timeout=60)
    return [json.loads(l) for l in p.stdout.splitlines() if l.strip().startswith("{")], p


def _repo_copy_with_allowlist(tmp, uid_strings):
    """Copy the code under test to tmp and write config/verified_devices.json listing uid_strings.
    Schema: D8 does not define it (ambiguity A1). The shipped file's top-level shape is reused:
    {"devices": [...]} -> entries {"uid": U, "label": ...}; a bare list -> [U, ...]."""
    dst = os.path.join(tmp, "repo")
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", "reports", "recordings", "*.pyc"))
    cfg = os.path.join(dst, "config", "verified_devices.json")
    shipped = None
    if os.path.exists(os.path.join(ROOT, "config", "verified_devices.json")):
        shipped = json.load(open(os.path.join(ROOT, "config", "verified_devices.json")))
    os.makedirs(os.path.dirname(cfg), exist_ok=True)
    if isinstance(shipped, list):
        doc = list(uid_strings)
    else:
        doc = dict(shipped or {})
        doc["devices"] = [{"uid": u, "label": "T6 test entry (temporary copy, not the repo file)"} for u in uid_strings]
    json.dump(doc, open(cfg, "w"), indent=1)
    return dst


def _reported_uid(uid_bytes):
    """The UID string format is not defined by D8 (ambiguity A2). Discover it black-box: what the bridge itself
    reports in meta.device_identity.uid for a device with these UID bytes."""
    dev = MSPDevice(variant="INAV", board="MKH7", uid=uid_bytes)
    try:
        s, p = _bridge_samples(dev)
    finally:
        dev.close()
    ids = [(x.get("meta") or {}).get("device_identity") for x in s]
    uids = {i.get("uid") for i in ids if isinstance(i, dict) and i.get("uid")}
    if len(uids) != 1:
        return None, (f"D8 item 1: bridge must report the device UID in meta.device_identity.uid; got {uids!r} "
                      f"from {len(s)} samples; stderr tail: {p.stderr[-400:]!r}")
    return str(uids.pop()), None


def _assert_never_live(r):
    assert r, "no records reached the app"
    live = [x for x in r if x.get("live_hardware")]
    assert not live, f"{len(live)}/{len(r)} records flagged live_hardware=True"


# ---------------------------------------------------------------- shipped allowlist
def test_d8_shipped_allowlist_is_empty():
    p = os.path.join(ROOT, "config", "verified_devices.json")
    assert os.path.exists(p), "D8 item 4: config/verified_devices.json must ship (empty)"
    d = json.load(open(p))
    entries = d if isinstance(d, list) else [v for k, v in d.items() if isinstance(v, list) for v in v]
    assert entries == [], f"D8 item 4: the shipped allowlist must be empty (no HV checklist sign-off exists); got {entries!r}"


# ---------------------------------------------------------------- fake FC / simulator identity
def test_d8_product_fake_fc_over_pty_is_simulated():
    """The old A10c path: product FakeFC on a virtual pty via app serial: must show SIMULATED, never HARDWARE."""
    dev = ProductFakeFCOnPty()
    try:
        badge, r, txt, pid_ok, out = _run_serial(ROOT, dev)
    finally:
        dev.close()
    assert pid_ok
    _assert_never_live(r)
    assert {x["source"] for x in r} == {"sim"}, f"sample.source must be 'sim' for the fake FC; got {sorted({x['source'] for x in r})}"
    assert badge == "SIMULATED", f"badge {badge!r}"


def test_d8_bridge_alone_labels_fake_fc_sim():
    dev = ProductFakeFCOnPty()
    try:
        s, p = _bridge_samples(dev)
    finally:
        dev.close()
    assert s, p.stderr[-600:]
    assert {x["source"] for x in s} == {"sim"}, {x["source"] for x in s}


def test_d8_emulated_siml_simf_identity_is_simulated():
    """Independent (non-product) device announcing the D8 simulator identity."""
    dev = MSPDevice(variant="SIML", board="SIMF", uid=bytes(12))
    try:
        badge, r, txt, pid_ok, out = _run_serial(ROOT, dev)
    finally:
        dev.close()
    assert pid_ok
    _assert_never_live(r)
    assert badge == "SIMULATED", badge


# ---------------------------------------------------------------- unknown devices
@pytest.mark.parametrize("cfg", [
    dict(variant="INAV", board="MKH7", uid=OTHER_UID),            # plausible unknown INAV board
    dict(variant="BTFL", board="S7X2", uid=OTHER_UID),            # other firmware
    dict(variant="INAV", board="MKH7", uid=None),                 # UID unsupported/missing
    dict(variant=None, board=None, uid=None),                     # identity replies all errors
    dict(identity=False),                                         # failed identity query
], ids=["inav_unknown_uid", "btfl_unknown_uid", "uid_missing", "identity_errors", "identity_failed"])
def test_d8_unknown_device_is_unverified(cfg):
    dev = MSPDevice(**cfg)
    try:
        badge, r, txt, pid_ok, out = _run_serial(ROOT, dev)
    finally:
        dev.close()
    assert pid_ok
    _assert_never_live(r)
    assert badge == "UNVERIFIED SOURCE", f"badge {badge!r} for {cfg}"
    if cfg.get("board"):
        # D8 item 3: the reported board/variant are shown as "reported by device"
        assert re.search(r"reported by (the )?device", txt, re.I), "UI must say the identity is 'reported by device'"
        assert cfg["board"] in txt, f"reported board {cfg['board']!r} not shown"


@pytest.mark.parametrize("variant,board", [("siml", "simf"), ("SIM ", "SIMF"), ("SIMX", "SIMF"), ("INAV", "SIMF"),
                                           ("SIML", "MKH7"), ("S1ML", "S1MF")],
                         ids=["lowercase", "SIM_space", "SIMX", "inav_simf", "siml_realboard", "digit_spoof"])
def test_d8_identity_spelling_variants_never_hardware(variant, board):
    """Case/spelling variants of the simulator identity: may be SIMULATED or UNVERIFIED (D8 does not say which;
    ambiguity A4), but never HARDWARE and never live."""
    dev = MSPDevice(variant=variant, board=board, uid=OTHER_UID)
    try:
        badge, r, txt, pid_ok, out = _run_serial(ROOT, dev)
    finally:
        dev.close()
    assert pid_ok
    _assert_never_live(r)
    assert badge in ("SIMULATED", "UNVERIFIED SOURCE"), badge


# ---------------------------------------------------------------- allowlist
@pytest.fixture(scope="module")
def allow_repo():
    uid, err = _reported_uid(ALLOWED_UID)
    # If the bridge does not report a UID (pre-fix), fall back to plain hex so the replay/ingest paths still run;
    # the HARDWARE test then fails on `err`.
    tmp = tempfile.mkdtemp(prefix="t6_d8_")
    try:
        yield _repo_copy_with_allowlist(tmp, [uid or ALLOWED_UID.hex()]), (uid or ALLOWED_UID.hex()), err
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_d8_allowlisted_uid_is_hardware(allow_repo):
    """Only path to HARDWARE. NOTE (F11): the 'device' here is T6's emulator on a pty, i.e. a spoofer reporting an
    allowlisted UID; it is accepted because the UID is self-reported. This passing is the D8 design, and it is
    also the evidence for unresolved limitation F11."""
    root, uid, err = allow_repo
    assert err is None, err
    dev = MSPDevice(variant="INAV", board="MKH7", uid=ALLOWED_UID)
    try:
        badge, r, txt, pid_ok, out = _run_serial(root, dev)
    finally:
        dev.close()
    assert pid_ok
    assert r and all(x.get("live_hardware") for x in r[-5:]), "allowlisted device: records should be live hardware"
    assert badge == "HARDWARE", badge


@pytest.mark.parametrize("uid", [OTHER_UID, None, ALLOWED_UID[:11], ALLOWED_UID + b"\x00", bytes(12),
                                 bytes(reversed(ALLOWED_UID)), ALLOWED_UID[:-1] + bytes([ALLOWED_UID[-1] ^ 1])],
                         ids=["other", "missing", "truncated", "extended", "zero", "byte_reversed", "one_bit_off"])
def test_d8_non_allowlisted_or_spoofed_uid_is_unverified(allow_repo, uid):
    root, _, _ = allow_repo
    dev = MSPDevice(variant="INAV", board="MKH7", uid=uid)
    try:
        badge, r, txt, pid_ok, out = _run_serial(root, dev)
    finally:
        dev.close()
    assert pid_ok
    _assert_never_live(r)
    assert badge == "UNVERIFIED SOURCE", badge


def test_d8_simulator_identity_with_allowlisted_uid_is_not_hardware(allow_repo):
    """A device announcing SIML/SIMF must not become HARDWARE even if it also reports an allowlisted UID
    (ambiguity A3: precedence not stated; T6 requires the conservative label)."""
    root, _, _ = allow_repo
    dev = MSPDevice(variant="SIML", board="SIMF", uid=ALLOWED_UID)
    try:
        badge, r, txt, pid_ok, out = _run_serial(root, dev)
    finally:
        dev.close()
    assert pid_ok
    _assert_never_live(r)
    assert badge in ("SIMULATED", "UNVERIFIED SOURCE"), badge


def test_d8_replay_with_allowlisted_uid_is_replay_not_live(allow_repo, tmp_path):
    root, uid, _ = allow_repo
    f = tmp_path / "hw_with_uid.jsonl"
    with open(f, "w") as fh:
        for i in range(400):
            fh.write(json.dumps({"t": i * 0.05, "source": "hardware", "mag_uT": [25.0, -3.0 + 0.01 * i, 43.0],
                                 "accel_g": [0, 0, -1],
                                 "meta": {"device_identity": {"uid": uid, "fc_variant": "INAV", "board_id": "MKH7"},
                                          "provenance": "verified", "device_verified": True, "live_hardware": True,
                                          "transport": "serial"}}) + "\n")
    a = App(root, "--source", f"replay:{f}", "--speed", "1")
    try:
        a.wait_records(8, 20)
        d = _dom(a.port)
        r = a.hist()
    finally:
        a.close()
    assert a.pid_ok
    _assert_never_live(r)
    assert _text(d, "sourceBadge") == "REPLAY (recorded hardware)", _text(d, "sourceBadge")


@pytest.mark.parametrize("src", ["hardware", "HARDWARE", "Hardware", " hardware"])
def test_d8_ingest_with_allowlisted_uid_is_never_hardware(allow_repo, src):
    root, uid, _ = allow_repo
    a = App(root, "--source", "ingest")
    stop = threading.Event()
    def feed():
        i = 0
        while not stop.is_set():
            _http(a.port, "/api/sample", {"t": i * 0.05, "source": src, "mag_uT": [25.0, -3.0, 43.0], "accel_g": [0, 0, -1],
                                          "meta": {"device_identity": {"uid": uid}, "device_verified": True,
                                                   "provenance": "verified", "transport": "serial"}})
            i += 1; time.sleep(0.05)
    th = threading.Thread(target=feed, daemon=True)
    try:
        th.start()
        a.wait_records(5, 10) if src == "hardware" else time.sleep(2)
        d = _dom(a.port)
        r = a.hist()
    finally:
        stop.set(); th.join(2); a.close()
    assert a.pid_ok
    assert not [x for x in r if x.get("live_hardware")], "ingest must never be live"
    badge = _text(d, "sourceBadge")
    if src == "hardware":
        assert badge == "UNVERIFIED SOURCE", badge
    else:   # non-canonical spellings: rejected by the schema (NO DATA) or, if accepted, still not HARDWARE
        assert badge != "HARDWARE", badge
