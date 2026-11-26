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
    with run_app("--source", "ingest", "--stale", "30") as (base, port):
        with HeadlessPage(base + "/") as page:
            page.wait_for("window.__hmProbe && window.__hmProbe().connected")
            post_json(base + "/api/sample", dict(sample(0.0, 200.0, source="hardware"),
                                                 gps={"fix": "3d", "num_sat": 9, "hdop": 0.9}))
            page.wait_for(_rendered(get_json(base + "/api/history")["records"][-1]["seq"]))
            with_gps = page.texts(ids)
            post_json(base + "/api/sample", sample(0.1, 200.0, source="hardware"))       # gps absent
            page.wait_for(_rendered(get_json(base + "/api/history")["records"][-1]["seq"]))
            without_gps = page.texts(ids)
    assert with_gps == {"sourceBadge": "HARDWARE", "gpsStatus": "Available", "gpsFix": "3D",
                        "gpsSats": "9", "gpsHdop": "0.9"}
    assert without_gps == {"sourceBadge": "HARDWARE", "gpsStatus": "Unknown", "gpsFix": "Unknown",
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
