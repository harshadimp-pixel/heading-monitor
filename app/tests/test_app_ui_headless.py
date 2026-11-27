"""Headless-browser checks: page renders, badge follows sample.source, GPS indicator, heading-only layout.

Deterministic by construction: each test runs its own app on an OS-assigned port (--port 0), drives headless
Chrome over the DevTools protocol on the real clock (no virtual-time fast-forward), waits (bounded) until the
page has rendered a specific sample seq via window.__hmProbe(), then reads the DOM once and asserts."""
import re

import pytest

from ._cdp import CHROME, HeadlessPage
from ._helpers import get_json, post_json, run_app, sample

pytestmark = pytest.mark.skipif(CHROME is None, reason="no headless Chrome/Chromium available")
REMOVED = ("latValue", "lonValue", "cogValue", "speedValue")


def _rendered(seq):
    return f"(() => {{ const p = window.__hmProbe && window.__hmProbe(); return p && p.renderedSeq >= {seq} ? p : null; }})()"


def test_dashboard_renders_in_headless_chrome():
    with run_app("--source", "sim", wait_for=lambda st: st["counts"]["accepted"] > 10) as (base, port):
        with HeadlessPage(base + "/") as page:
            seq = get_json(base + "/api/history")["records"][-1]["seq"]
            page.wait_for(_rendered(seq))                     # readiness only
            t = page.texts(["sourceBadge", "headingValue", "gpsStatus", "magRaw", *REMOVED])
    assert t["sourceBadge"] == "SIMULATED"
    assert re.match(r"^\d{1,3}\.\d° [NESW]{1,3}$", t["headingValue"] or ""), t["headingValue"]
    assert t["gpsStatus"] == "Unknown"                        # T3 sim emits no gps
    for removed in REMOVED:                                   # heading-only app
        assert t[removed] is None
    assert t["magRaw"] == "Unknown" or re.match(r"^-?\d+, -?\d+, -?\d+", t["magRaw"])


def test_gps_indicator_renders_fix_sats_hdop():
    ids = ["sourceBadge", "gpsStatus", "gpsFix", "gpsSats", "gpsHdop"]
    # source "hardware" via ingest is not a live serial source -> UNVERIFIED SOURCE (D6), never HARDWARE
    with run_app("--source", "ingest", "--stale", "30") as (base, port):
        with HeadlessPage(base + "/") as page:
            page.wait_for("window.__hmProbe && window.__hmProbe().connected")
            post_json(base + "/api/sample", dict(sample(0.0, 200.0, source="hardware"),
                                                 gps={"fix": "3d", "num_sat": 9, "hdop": 0.9}))
            page.wait_for(_rendered(get_json(base + "/api/history")["records"][-1]["seq"]))
            with_gps = page.texts(ids)
            banner = page.texts(["evidenceBanner"])["evidenceBanner"]
            post_json(base + "/api/sample", sample(0.1, 200.0, source="hardware"))       # gps absent
            page.wait_for(_rendered(get_json(base + "/api/history")["records"][-1]["seq"]))
            without_gps = page.texts(ids)
    assert "Live" not in banner and "not a live serial source" in banner
    assert with_gps == {"sourceBadge": "UNVERIFIED SOURCE", "gpsStatus": "Available", "gpsFix": "3D",
                        "gpsSats": "9", "gpsHdop": "0.9"}
    assert without_gps == {"sourceBadge": "UNVERIFIED SOURCE", "gpsStatus": "Unknown", "gpsFix": "Unknown",
                           "gpsSats": "Unknown", "gpsHdop": "Unknown"}


def test_stale_data_renders_unknown_not_last_value():
    """After the stale timeout the UI must show Unknown + NO DATA badge, never the last value as current."""
    with run_app("--source", "ingest", "--stale", "1") as (base, port):
        with HeadlessPage(base + "/") as page:
            page.wait_for("window.__hmProbe && window.__hmProbe().connected")
            post_json(base + "/api/sample", sample(0.0, 123.0))
            page.wait_for(_rendered(get_json(base + "/api/history")["records"][-1]["seq"]))
            fresh = page.texts(["sourceBadge", "headingValue"])
            page.wait_for("document.getElementById('sourceBadge').textContent === 'NO DATA' || null", timeout=6)
            stale = page.texts(["sourceBadge", "headingValue", "headingHint", "sensorStatus"])
    assert fresh["sourceBadge"] == "SIMULATED" and fresh["headingValue"].startswith("123.0°")
    assert stale["sourceBadge"] == "NO DATA" and stale["headingValue"] == "Unknown"
    assert "STALE" in stale["headingHint"] and stale["sensorStatus"] == "STALE"


def _replay_page(tmpdir, source, ids):
    import json, os
    path = os.path.join(tmpdir, f"{source}.jsonl")
    with open(path, "w") as f:
        for i in range(400):                                  # 20 s of samples at 20 Hz: still streaming when read
            f.write(json.dumps(sample(i * 0.05, (i * 3) % 360, source=source)) + "\n")
    with run_app("--source", f"replay:{path}", "--stale", "30",
                 wait_for=lambda st: st["counts"]["accepted"] > 2) as (base, port):
        with HeadlessPage(base + "/") as page:
            page.wait_for(_rendered(get_json(base + "/api/history")["records"][-1]["seq"]))
            return page.texts(ids)


def test_d6_replayed_hardware_log_shows_replay_badge_not_live(tmp_path):
    t = _replay_page(str(tmp_path), "hardware", ["sourceBadge", "evidenceBanner", "sourceSub"])
    assert t["sourceBadge"] == "REPLAY (recorded hardware)"
    assert "Live" not in t["evidenceBanner"] and "recorded" in t["evidenceBanner"]
    assert "not a live sensor stream" in t["evidenceBanner"]
    assert 'sample.source = "replay"' in t["sourceSub"] and 'original_source = "hardware"' in t["sourceSub"]


def test_d6_replayed_sim_log_still_simulated(tmp_path):
    t = _replay_page(str(tmp_path), "sim", ["sourceBadge", "evidenceBanner"])
    assert t["sourceBadge"] == "SIMULATED" and "Live" not in t["evidenceBanner"]


def test_d8_serial_badges_and_reported_by_device_labels(tmp_path):
    """D8 in the browser: serial + allowlisted uid -> HARDWARE; uid not listed / no identity -> UNVERIFIED SOURCE;
    SIML/SIMF -> SIMULATED; board/variant/uid always labelled 'reported by device'. Virtual serial: an in-process hub
    whose transport is serial, on an OS-assigned port; samples injected as the serial source emits them."""
    import json
    import threading
    from app.hub import Hub
    from app.server import serve
    uid = "0123456789abcdef01234567"
    allow = tmp_path / "verified_devices.json"
    allow.write_text(json.dumps({"devices": [{"uid": uid, "label": "pytest"}]}))
    hub = Hub("serial:/dev/virtual-ui-test", stale_after_s=30, verified_devices_path=str(allow))
    httpd = serve(hub, "127.0.0.1", 0)
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def hw(t, ident, provenance=None):
        s = sample(t, 150.0, source="hardware")
        if ident is not None:
            s["meta"] = {"device_identity": ident}
        if provenance:
            s.setdefault("meta", {})["provenance"] = provenance
        return s
    cases = [
        ("verified", hw(0.0, {"fc_variant": "INAV", "board_id": "MKF4", "target_name": "MATEKF405", "uid": uid},
                        "verified")),
        ("not_listed", hw(0.1, {"fc_variant": "INAV", "board_id": "MKF4", "uid": "ffffffffffffffffffffffff"})),
        ("no_identity", hw(0.2, None)),
        ("simulator", hw(0.3, {"fc_variant": "SIML", "board_id": "SIMF", "uid": uid})),
    ]
    ids = ["sourceBadge", "evidenceBanner", "deviceBoard", "deviceVariant", "deviceTarget", "deviceUid", "deviceVerify"]
    out = {}
    try:
        with HeadlessPage(base + "/") as page:
            page.wait_for("window.__hmProbe && window.__hmProbe().connected")
            for name, s in cases:
                assert hub.source_emit(s) is None
                page.wait_for(_rendered(get_json(base + "/api/history")["records"][-1]["seq"]))
                out[name] = page.texts(ids)
                out[name]["hidden"] = page.eval("document.getElementById('deviceIdentity').hidden")
    finally:
        httpd.shutdown()
        httpd.server_close()
    v, n, x, sm = out["verified"], out["not_listed"], out["no_identity"], out["simulator"]
    assert v["sourceBadge"] == "HARDWARE" and v["hidden"] is False
    assert v["deviceBoard"] == "MKF4 (reported by device)" and v["deviceVariant"] == "INAV (reported by device)"
    assert v["deviceTarget"] == "MATEKF405 (reported by device)" and x["deviceTarget"] == "Unknown (reported by device)"
    assert v["deviceUid"] == f"{uid} (reported by device)" and "verified_devices.json" in v["deviceVerify"]
    assert n["sourceBadge"] == "UNVERIFIED SOURCE" and "not proof of hardware" in n["evidenceBanner"]
    assert "Live" not in n["evidenceBanner"] and n["deviceBoard"] == "MKF4 (reported by device)"
    assert "UID not in verified list" in n["deviceVerify"]
    assert x["sourceBadge"] == "UNVERIFIED SOURCE" and "Live" not in x["evidenceBanner"]
    assert x["deviceBoard"] == "Unknown (reported by device)" and x["deviceVariant"] == "Unknown (reported by device)"
    assert "no identity" in x["deviceVerify"]
    assert sm["sourceBadge"] == "SIMULATED" and sm["deviceVariant"] == "SIML (reported by device)"
    assert sm["deviceBoard"] == "SIMF (reported by device)" and "simulator" in sm["deviceVerify"]


def test_d8_forged_ingest_claims_show_unverified(tmp_path):
    """D8 hardening in the browser: an ingested 'hardware' sample that claims meta.provenance 'verified',
    live_hardware true and an allowlisted UID (in the app's own --verified-devices file) still shows
    UNVERIFIED SOURCE, never HARDWARE or a 'Live' banner, and no device-identity box (not a serial sample)."""
    import json
    uid = "0123456789abcdef01234567"
    allow = tmp_path / "verified_devices.json"
    allow.write_text(json.dumps({"devices": [{"uid": uid, "label": "pytest"}]}))
    s = sample(0.0, 200.0, source="hardware")
    s["meta"] = {"provenance": "verified", "live_hardware": True, "device_verified": True,
                 "device_identity": {"uid": uid, "fc_variant": "INAV", "board_id": "MKF4"}}
    s.update(live_hardware=True, device_verified=True, transport="serial")
    with run_app("--source", "ingest", "--stale", "30", "--verified-devices", str(allow)) as (base, _):
        with HeadlessPage(base + "/") as page:
            page.wait_for("window.__hmProbe && window.__hmProbe().connected")
            code, body = post_json(base + "/api/sample", s)
            assert code == 200 and body["ok"], body
            page.wait_for(_rendered(get_json(base + "/api/history")["records"][-1]["seq"]))
            t = page.texts(["sourceBadge", "evidenceBanner"])
            hidden = page.eval("document.getElementById('deviceIdentity').hidden")
    assert t["sourceBadge"] == "UNVERIFIED SOURCE"
    assert "HARDWARE" not in t["sourceBadge"].replace("UNVERIFIED SOURCE", "") and "Live" not in t["evidenceBanner"]
    assert "not treated as live" in t["evidenceBanner"] and hidden is True
