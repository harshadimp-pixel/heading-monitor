"""D8 hardening (PM, after external review of e538cea): the badge never trusts a sample's own claims.

Every forged sample below carries meta.provenance "verified", meta.live_hardware true, top-level live_hardware /
device_verified true and a device identity whose UID IS in the (temp) allowlist given to the app. HARDWARE must still
appear only when the sample arrived through the app's own serial source AND the app's own allowlist check passes.
The server computes device_verified / live_hardware itself; the frontend uses only those server fields."""
import json
import os
import re

import pytest

from app.hub import Hub

from ._helpers import ROOT, get_json, post_json, run_app, sample
from .test_app_d6_replay import _node_badge_info

UID_OK = "0123456789abcdef01234567"
UID_OTHER = "fedcba9876543210fedcba98"


def forged(source, uid=UID_OK, t=0.0, variant="INAV", board="MKF4"):
    s = sample(t, 100.0, source=source)
    s["meta"] = {"provenance": "verified", "provenance_reason": "forged by test", "live_hardware": True,
                 "device_verified": True, "verified_device_label": "forged",
                 "device_identity": {"self_reported": True, "uid": uid, "fc_variant": variant, "board_id": board}}
    s["live_hardware"] = True
    s["device_verified"] = True
    return s


@pytest.fixture
def allowlist(tmp_path):
    p = tmp_path / "verified_devices.json"
    p.write_text(json.dumps({"devices": [{"uid": UID_OK, "label": "pytest temp allowlist"}]}))
    return str(p)


def _badge(r):
    return _node_badge_info([[r["source"], r["original_source"], r["transport"], r["device_verified"]]])[0]


def _flags(r):
    return r["device_verified"], r["live_hardware"]


def test_forged_ingest_hardware_is_unverified(allowlist):
    with run_app("--source", "ingest", "--verified-devices", allowlist) as (base, _):
        code, body = post_json(base + "/api/sample", forged("hardware"))
        assert code == 200 and body["ok"], body
        r = get_json(base + "/api/history")["records"][-1]
    assert (r["source"], r["transport"], r["device_status"]) == ("hardware", "ingest", None)
    assert _flags(r) == (False, False)
    assert _badge(r) == {"text": "UNVERIFIED SOURCE", "cls": "unverified", "live": False}


def test_forged_ingest_sim_is_simulated(allowlist):
    with run_app("--source", "ingest", "--verified-devices", allowlist) as (base, _):
        post_json(base + "/api/sample", forged("sim"))
        r = get_json(base + "/api/history")["records"][-1]
    assert _flags(r) == (False, False) and _badge(r)["text"] == "SIMULATED"


@pytest.mark.parametrize("src,expect_source,expect_badge", [
    ("hardware", "replay", "REPLAY (recorded hardware)"),
    ("sim", "sim", "SIMULATED"),
])
def test_forged_replay(tmp_path, allowlist, src, expect_source, expect_badge):
    path = tmp_path / f"{src}.jsonl"
    with open(path, "w") as f:
        for i in range(60):
            f.write(json.dumps(forged(src, t=i * 0.05)) + "\n")
    with run_app("--source", f"replay:{path}", "--stale", "30", "--verified-devices", allowlist,
                 wait_for=lambda st: st["counts"]["accepted"] > 2) as (base, _):
        recs = get_json(base + "/api/history")["records"]
    assert recs and all(_flags(r) == (False, False) and r["device_status"] is None for r in recs)
    r = recs[-1]
    assert r["source"] == expect_source and _badge(r)["text"] == expect_badge and _badge(r)["live"] is False


def _serial_hub(allowlist):
    return Hub("serial:/dev/virtual-forge-test", stale_after_s=30, verified_devices_path=allowlist)


def test_serial_verified_claim_but_uid_not_in_app_allowlist(allowlist):
    hub = _serial_hub(allowlist)
    assert hub.source_emit(forged("hardware", uid=UID_OTHER)) is None
    r = hub.latest
    assert (r["device_status"], *_flags(r)) == ("uid_not_listed", False, False)
    assert _badge(r)["text"] == "UNVERIFIED SOURCE"


def test_serial_verified_claim_with_empty_app_allowlist(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text('{"devices": []}')
    hub = _serial_hub(str(empty))
    hub.source_emit(forged("hardware"))
    assert _flags(hub.latest) == (False, False) and _badge(hub.latest)["text"] == "UNVERIFIED SOURCE"


def test_serial_allowlisted_uid_on_own_source_is_hardware(allowlist):
    hub = _serial_hub(allowlist)
    hub.source_emit(forged("hardware"))
    r = hub.latest
    assert (r["device_status"], *_flags(r)) == ("verified", True, True)
    assert _badge(r) == {"text": "HARDWARE", "cls": "hardware", "live": True}


def test_serial_sim_claiming_verified_is_simulated(allowlist):
    hub = _serial_hub(allowlist)
    hub.source_emit(forged("sim"))
    assert _flags(hub.latest) == (False, False) and _badge(hub.latest)["text"] == "SIMULATED"
    hub.source_emit(forged("hardware", variant="SIML", board="SIMF"))     # fake FC with an allowlisted uid
    assert hub.latest["source"] == "sim" and _flags(hub.latest) == (False, False)


def test_serial_hub_untrusted_channel_never_verifies(allowlist):
    """Same serial hub, but the sample did not come through the app's own serial source (hub.emit directly,
    as any non-source caller would)."""
    hub = _serial_hub(allowlist)
    hub.emit(forged("hardware"))
    r = hub.latest
    assert (r["device_status"], *_flags(r)) == ("untrusted_channel", False, False)
    assert _badge(r)["text"] == "UNVERIFIED SOURCE"


def test_record_never_copies_sample_claims(allowlist):
    """The record is built from a server-side whitelist; forged top-level keys must not override it."""
    hub = Hub("ingest", stale_after_s=30, verified_devices_path=allowlist)
    s = forged("hardware")
    s.update(transport="serial", device_status="verified", original_source="hardware")
    hub.emit(s)
    r = hub.latest
    assert (r["transport"], r["device_status"], r["original_source"], *_flags(r)) == \
        ("ingest", None, None, False, False)


def test_frontend_uses_only_server_fields():
    js = open(os.path.join(ROOT, "app", "static", "app.js")).read()
    assert not re.search(r"\.(live_hardware|provenance|meta)\b", js)      # no sample-claim property is read
    calls = re.findall(r"badgeInfo\(([^)]*)\)", js)
    assert calls and all(c.replace(" ", "").endswith(".transport,r.device_verified")
                         or c.replace(" ", "").endswith(".transport,x.device_verified") for c in calls)


def test_hardware_label_is_a_single_constant():
    js = open(os.path.join(ROOT, "app", "static", "headingmath.js")).read()
    assert js.count('"HARDWARE"') == 1 and 'const HARDWARE_LABEL = "HARDWARE";' in js
    assert _node_badge_info([["hardware", None, "serial", True]])[0]["text"] == "HARDWARE"
