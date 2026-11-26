"""Headless-browser check: page renders, badge follows sample.source, GPS/position show Unknown."""
import re
import shutil
import subprocess

import pytest

from ._helpers import run_app

CHROME = next((shutil.which(c) for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)), None)


@pytest.mark.skipif(CHROME is None, reason="no headless Chrome/Chromium available")
def test_dashboard_renders_in_headless_chrome():
    # --stale 30: headless --virtual-time-budget fast-forwards Date.now(), which would otherwise mark data stale
    with run_app("--source", "sim", "--stale", "30", wait_for=lambda st: st["counts"]["accepted"] > 10) as (base, port):
        dom = subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
                              "--virtual-time-budget=4000", "--dump-dom", base + "/"],
                             capture_output=True, text=True, timeout=60).stdout

    def text(id_):
        m = re.search(r'id="%s"[^>]*>([^<]*)<' % id_, dom)
        return m.group(1) if m else None
    assert text("sourceBadge") == "SIMULATED"
    assert re.match(r"^\d{1,3}\.\d° [NESW]{1,3}$", text("headingValue") or ""), text("headingValue")
    assert text("gpsStatus") == "Unknown"
    for removed in ("latValue", "lonValue", "cogValue", "speedValue"):   # heading-only app
        assert f'id="{removed}"' not in dom
    assert text("magRaw") in ("Unknown",) or re.match(r"^-?\d+, -?\d+, -?\d+", text("magRaw") or "")
