"""D8 (Codex audit via PM, ARCHITECTURE.md 2026-11-27): a serial connection is not proof of hardware.

Paths covered:
  serial + uid in a (temp) allowlist      -> HARDWARE (live_hardware true)
  serial + uid not in the allowlist       -> UNVERIFIED SOURCE
  serial + no device identity / no uid    -> UNVERIFIED SOURCE (board/variant 'reported by device')
  serial + variant SIML or board SIMF     -> SIMULATED (source mapped to "sim")
  shipped/missing/malformed allowlist     -> empty -> never HARDWARE
  replay (hardware + sim) and ingest      -> unchanged (D6)
"Virtual serial": an in-process Hub whose transport is serial (samples injected exactly as the serial source
would emit them), plus an end-to-end run through the real firmware_bridge on a pty driven by its FakeFC
(skipped when pyserial is missing). No physical hardware."""
import csv
import io
import json
import os
import threading
import time

import pytest

from app import provenance
from app.hub import Hub
from app.provenance import apply_serial_provenance, load_verified_devices
from app.server import serve

from ._helpers import ROOT, get_json, post_json, run_app, sample

UID_OK = "0123456789abcdef01234567"   # 24 hex = 12 MSP_UID bytes (firmware_bridge format)


def _hw(uid=None, variant=None, board=None, identity=True, t=0.0, heading=100.0, provenance=None):
    s = sample(t, heading, source="hardware")
    if identity:
        ident = {}
        if uid is not None:
            ident["uid"] = uid
        if variant is not None:
            ident["fc_variant"] = variant
        if board is not None:
            ident["board_id"] = board
        s["meta"] = {"device_identity": ident}
    if provenance is not None:
        s.setdefault("meta", {})["provenance"] = provenance
    return s


@pytest.fixture
def allowlist(tmp_path):
    p = tmp_path / "verified_devices.json"
    p.write_text(json.dumps({"devices": [{"uid": UID_OK, "label": "pytest temp allowlist"}]}))
    return str(p)


# ---------------------------------------------------------------- allowlist loader (fail closed)
def test_shipped_allowlist_is_empty_or_absent():
    uids, info = load_verified_devices()
    assert info["path"] == os.path.join(ROOT, "config", "verified_devices.json")
    assert uids == set()                          # ships empty (or not yet created by Firmware) -> nothing is HARDWARE


@pytest.mark.parametrize("content,expect", [
    (json.dumps({"devices": [{"uid": UID_OK}]}), {UID_OK}),
    (json.dumps({"devices": [{"uid": UID_OK.upper(), "label": "x"}]}), {UID_OK}),       # normalised
    (json.dumps({"devices": [{"uid": "01:23:45:67:89:ab:cd:ef:01:23:45:67"}]}), {UID_OK}),
    (json.dumps({"devices": []}), set()),
    (json.dumps([UID_OK]), set()),                    # bare list is not the schema -> fail closed
    (json.dumps({"devices": [{"uid": "1234"}]}), set()),   # not 24 hex
    (json.dumps({"devices": [{"name": "no uid"}]}), set()),
    ("not json", set()),
])
def test_allowlist_formats_fail_closed(tmp_path, content, expect):
    p = tmp_path / "v.json"
    p.write_text(content)
    uids, info = load_verified_devices(str(p))
    assert uids == expect
    valid_empty = content == json.dumps({"devices": []})
    assert (info["error"] is None) == (bool(expect) or valid_empty), info


def test_missing_allowlist_is_empty(tmp_path):
    uids, info = load_verified_devices(str(tmp_path / "nope.json"))
    assert uids == set() and not info["exists"] and "not found" in info["error"]


# ---------------------------------------------------------------- provenance rules
def test_provenance_rules():
    allow = {UID_OK}
    s, d = apply_serial_provenance(_hw(uid=UID_OK, variant="INAV", board="MKF4", provenance="verified"), allow)
    assert (s["source"], d["status"], d["verified"]) == ("hardware", "verified", True)
    s, d = apply_serial_provenance(_hw(uid=UID_OK, variant="INAV", board="MKF4"), allow)   # no meta.provenance
    assert (d["status"], d["verified"]) == ("bridge_unverified", False)
    s, d = apply_serial_provenance(_hw(uid=UID_OK.upper(), variant="INAV", provenance="verified"), allow)
    assert (d["status"], d["verified"]) == ("verified", True)
    s, d = apply_serial_provenance(_hw(uid=UID_OK, variant="INAV", provenance="unverified"), allow)
    assert (d["status"], d["verified"]) == ("bridge_unverified", False)     # app and bridge must agree
    s, d = apply_serial_provenance(_hw(uid="ffffffffffffffffffffffff", variant="INAV"), allow)
    assert (s["source"], d["status"], d["verified"]) == ("hardware", "uid_not_listed", False)
    s, d = apply_serial_provenance(_hw(uid="garbage", variant="INAV"), allow)
    assert (d["status"], d["verified"]) == ("no_uid", False)
    s, d = apply_serial_provenance(_hw(variant="INAV"), allow)
    assert (d["status"], d["verified"]) == ("no_uid", False)
    s, d = apply_serial_provenance(_hw(identity=False), allow)
    assert (s["source"], d["status"], d["verified"]) == ("hardware", "no_identity", False)
    bare = sample(0.0, 1.0, source="hardware")
    bare["meta"] = {"fc_variant": "INAV"}                       # what firmware_bridge emits today
    s, d = apply_serial_provenance(bare, allow)
    assert (d["status"], d["variant"], d["verified"]) == ("no_identity", "INAV", False)
    for kw in ({"variant": "SIML"}, {"board": "SIMF"}, {"variant": "SIML", "uid": UID_OK}):
        src = _hw(**kw)
        s, d = apply_serial_provenance(src, allow)
        assert (s["source"], d["status"], d["verified"]) == ("sim", "simulator", False)
        assert s["meta"]["source_mapped_from"] == "hardware" and src["source"] == "hardware"   # input untouched
    s, d = apply_serial_provenance(dict(sample(0.0, 1.0, source="sim"), meta={"fc_variant": "SIML"}), allow)
    assert s["source"] == "sim" and d["status"] == "simulator"
    s, d = apply_serial_provenance(_hw(uid=UID_OK, variant="INAV"), set())       # empty allowlist
    assert d["verified"] is False and d["status"] == "uid_not_listed"


# ---------------------------------------------------------------- in-process app with a serial transport
class _InProc:
    def __init__(self, allow_path):
        self.hub = Hub("serial:/dev/virtual-test", stale_after_s=30, verified_devices_path=allow_path)
        self.httpd = serve(self.hub, "127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.th = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.th.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def serial_app(allowlist):
    a = _InProc(allowlist)
    yield a
    a.close()


def test_serial_paths_records_status_and_csv(serial_app):
    hub = serial_app.hub
    feeds = [_hw(uid=UID_OK, variant="INAV", board="MKF4", t=0.0, provenance="verified"),
             _hw(uid="ffffffffffffffffffffffff", variant="INAV", t=0.1),
             _hw(identity=False, t=0.2), _hw(variant="SIML", board="SIMF", t=0.3), _hw(variant="INAV", t=0.4)]
    for s in feeds:
        assert hub.emit(s) is None
    recs = get_json(serial_app.base + "/api/history")["records"]
    got = [(r["source"], r["device_status"], r["device_verified"], r["live_hardware"]) for r in recs]
    assert got == [("hardware", "verified", True, True), ("hardware", "uid_not_listed", False, False),
                   ("hardware", "no_identity", False, False), ("sim", "simulator", False, False),
                   ("hardware", "no_uid", False, False)]
    st = get_json(serial_app.base + "/api/status")
    assert st["verified_devices"]["count"] == 1
    import urllib.request
    rows = list(csv.DictReader(io.StringIO(urllib.request.urlopen(serial_app.base + "/api/export.csv").read().decode())))
    assert [(r["source"], r["device_status"], r["device_verified"], r["device_board_reported"]) for r in rows[:2]] == \
        [("hardware", "verified", "true", "MKF4"), ("hardware", "uid_not_listed", "false", "")]


def test_serial_default_allowlist_never_hardware():
    a = _InProc(None)                                   # default path: shipped empty / absent
    try:
        a.hub.emit(_hw(uid=UID_OK, variant="INAV", board="MKF4", provenance="verified"))
        r = get_json(a.base + "/api/history")["records"][-1]
    finally:
        a.close()
    assert r["source"] == "hardware" and r["device_verified"] is False and r["live_hardware"] is False


def test_non_serial_transports_unchanged(tmp_path, allowlist):
    """D6 behaviour kept: replay relabels hardware; sim replay stays sim; ingest keeps hardware, never live/verified."""
    path = tmp_path / "hw.jsonl"
    with open(path, "w") as f:
        for i in range(100):
            f.write(json.dumps(_hw(uid=UID_OK, variant="INAV", t=i * 0.05)) + "\n")
    with run_app("--source", f"replay:{path}", "--stale", "30", "--verified-devices", allowlist,
                 wait_for=lambda st: st["counts"]["accepted"] > 2) as (base, _):
        r = get_json(base + "/api/history")["records"][-1]
    assert (r["source"], r["original_source"], r["device_status"], r["live_hardware"]) == \
        ("replay", "hardware", None, False)
    with run_app("--source", "ingest", "--verified-devices", allowlist) as (base, _):
        post_json(base + "/api/sample", _hw(uid=UID_OK, variant="INAV"))
        r = get_json(base + "/api/history")["records"][-1]
    assert (r["source"], r["transport"], r["device_status"], r["device_verified"], r["live_hardware"]) == \
        ("hardware", "ingest", None, False, False)


# ---------------------------------------------------------------- end-to-end: real firmware_bridge over a pty
def _fake_fc_on_pty(fc_kwargs, stop):
    import pty
    import tty
    from firmware_bridge.fake_fc import FakeFC
    master, slave = pty.openpty()
    tty.setraw(slave)
    t0 = time.monotonic()
    fc = FakeFC(clock=lambda: time.monotonic() - t0, **fc_kwargs)

    def loop():
        import select
        while not stop.is_set():
            r, _, _ = select.select([master], [], [], 0.05)
            if master in r:
                try:
                    data = os.read(master, 4096)
                except OSError:
                    break
                for f in fc.parser.feed(data):
                    if f.direction == "<":
                        os.write(master, fc.handle(f))
    th = threading.Thread(target=loop, daemon=True)
    th.start()
    return os.ttyname(slave), (master, slave, th)


def _fake_fc_kwargs(variant, board, uid_hex):
    import inspect
    from firmware_bridge.fake_fc import FakeFC
    params = inspect.signature(FakeFC.__init__).parameters
    kw = {"variant": variant}
    d8 = "board_id" in params          # D8 FakeFC (reports board id + MSP_UID)
    if d8:
        kw["board_id"] = board
        kw["uid"] = bytes.fromhex(uid_hex)
    return kw, d8


@pytest.mark.parametrize("variant,board,uid_hex", [("INAV", "MKF4", UID_OK),
                                                   ("INAV", "MKF4", "ffffffffffffffffffffffff"),
                                                   ("SIML", "SIMF", UID_OK)])
def test_e2e_bridge_over_pty(variant, board, uid_hex, allowlist):
    """Real firmware_bridge --port on a pty driven by FakeFC (virtual serial, no hardware); the app passes its temp
    allowlist to the bridge. Expected with the D8 bridge: listed uid -> HARDWARE; unlisted -> UNVERIFIED;
    SIML/SIMF -> SIMULATED even though its uid is listed. With a pre-D8 bridge (no identity): never HARDWARE."""
    pytest.importorskip("serial", reason="pyserial not installed (optional; needed for the bridge's --port mode)")
    kw, d8 = _fake_fc_kwargs(variant, board, uid_hex)
    stop = threading.Event()
    name, (master, slave, th) = _fake_fc_on_pty(kw, stop)
    try:
        with run_app("--source", f"serial:{name}", "--stale", "30", "--verified-devices", allowlist,
                     wait_for=lambda st: st["counts"]["accepted"] > 3, timeout=20) as (base, _):
            recs = get_json(base + "/api/history")["records"]
    finally:
        stop.set()
        th.join(2)
        os.close(master)
        os.close(slave)
    assert recs and all(r["transport"] == "serial" for r in recs)
    r = recs[-1]
    if variant == "SIML":
        assert (r["source"], r["device_status"], r["live_hardware"]) == ("sim", "simulator", False)
    elif not d8:
        assert (r["source"], r["device_status"], r["live_hardware"]) == ("hardware", "no_identity", False)
    elif uid_hex == UID_OK:
        assert (r["source"], r["device_status"], r["live_hardware"]) == ("hardware", "verified", True)
        assert (r["device_board"], r["device_variant"], r["device_uid"]) == ("MKF4", "INAV", UID_OK)
    else:
        assert (r["source"], r["device_status"], r["live_hardware"]) == ("hardware", "uid_not_listed", False)


# ---------------------------------------------------------------- app and bridge use the SAME allowlist file
def test_bridge_command_gets_same_allowlist(allowlist):
    from app.sources import make_source
    from app.provenance import DEFAULT_ALLOWLIST, _fw
    if _fw is None:
        pytest.skip("pre-D8 firmware_bridge (no --verified-devices flag)")
    noop = lambda *a, **k: None   # noqa: E731
    src = make_source("serial:/dev/x", noop, noop, verified_devices=allowlist)
    i = src.cmd.index("--verified-devices")
    assert src.cmd[i + 1] == os.path.abspath(allowlist)
    dflt = make_source("serial:/dev/x", noop, noop)
    assert dflt.cmd[dflt.cmd.index("--verified-devices") + 1] == os.path.abspath(DEFAULT_ALLOWLIST)


def test_running_app_passes_allowlist_to_bridge(allowlist):
    """The real `python -m app --source serial:... --verified-devices F` launches the bridge with the same F
    (read back from the source status, which shows the bridge command line)."""
    from app.provenance import _fw
    if _fw is None:
        pytest.skip("pre-D8 firmware_bridge (no --verified-devices flag)")
    with run_app("--source", "serial:/dev/does-not-exist-d8", "--verified-devices", allowlist,
                 wait_for=lambda st: st["source_status"].get("state") in ("running", "fault", "ended")) as (base, _):
        st = get_json(base + "/api/status")
    assert f"--verified-devices {os.path.abspath(allowlist)}" in st["source_status"]["command"]
    assert st["verified_devices"]["path"] == allowlist
