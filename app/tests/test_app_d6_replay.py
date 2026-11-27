"""D6 (Auditor, CRITICAL): a replayed log whose samples say source "hardware" must never be shown as live hardware.

Decision (ARCHITECTURE.md, PM 2026-11-27): app replay relabels hardware -> source "replay" with
meta.original_source "hardware" (as firmware_bridge --replay does); badge "REPLAY (recorded hardware)", banner says
recorded / not live; a replayed sim log stays SIMULATED; HARDWARE only for a live serial source."""
import csv
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request

import pytest

from ._helpers import ROOT, get_json, post_json, run_app, sample


def _write_log(path, source, n=120, dt=0.05, meta=None):
    with open(path, "w") as f:
        for i in range(n):
            s = sample(i * dt, (i * 3) % 360, source=source)
            if meta:
                s["meta"] = dict(meta)
            f.write(json.dumps(s) + "\n")


def test_unit_relabel_matches_firmware_bridge_fields():
    from app.sources import relabel_replayed_sample
    hw = {"t": 1.0, "source": "hardware", "mag_uT": [1, 2, 3], "meta": {"x": 1}}
    out = relabel_replayed_sample(hw, "/tmp/f.jsonl")
    assert out["source"] == "replay"
    assert out["meta"] == {"x": 1, "original_source": "hardware", "replayed_from": "/tmp/f.jsonl"}
    assert hw["source"] == "hardware" and hw["meta"] == {"x": 1}          # input not mutated
    sim = {"t": 1.0, "source": "sim", "mag_uT": [1, 2, 3]}
    assert relabel_replayed_sample(sim, "/tmp/f.jsonl") is sim             # sim untouched
    rep = {"t": 1.0, "source": "replay", "mag_uT": [1, 2, 3], "meta": {"original_source": "hardware"}}
    assert relabel_replayed_sample(rep, "/tmp/f.jsonl") is rep             # already relabelled (bridge output)
    # same three fields as firmware_bridge --replay produces for a hardware line
    fb = pytest.importorskip("firmware_bridge.bridge")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "in.jsonl")
        with open(p, "w") as f:
            f.write(json.dumps({"t": 1.0, "source": "hardware", "mag_uT": [1, 2, 3]}) + "\n")
        try:
            b = next(iter(fb.replay(p, {})))
        except Exception as e:  # pragma: no cover - bridge signature changed
            pytest.skip(f"firmware_bridge.replay not callable here: {e}")
        mine = relabel_replayed_sample({"t": 1.0, "source": "hardware", "mag_uT": [1, 2, 3]}, p)
    assert b["source"] == mine["source"] == "replay"
    assert b["meta"]["original_source"] == mine["meta"]["original_source"] == "hardware"
    assert b["meta"]["replayed_from"] == mine["meta"]["replayed_from"] == p


def test_replay_of_hardware_log_is_relabelled_and_recorded():
    from app.hub import RECORDINGS_DIR
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "hw.jsonl")
        _write_log(path, "hardware", n=200, meta={"fw": "x"})
        with run_app("--source", f"replay:{path}", "--stale", "30",
                     wait_for=lambda st: st["counts"]["accepted"] > 2) as (base, port):
            names = []
            for fmt in ("csv", "jsonl"):
                names.append(post_json(base + "/api/record/start", {"format": fmt})[1]["file"])
                time.sleep(1.2)                    # let replayed samples reach the recording (names are unique)
                post_json(base + "/api/record/stop", {})
            st = get_json(base + "/api/status")
            recs = get_json(base + "/api/history")["records"]
            csv_txt = urllib.request.urlopen(f"{base}/recordings/{names[0]}").read().decode()
            jsonl = urllib.request.urlopen(f"{base}/recordings/{names[1]}").read().decode().splitlines()
            for n in names:
                os.unlink(os.path.join(RECORDINGS_DIR, n))
    assert st["latest_sample_source"] == "replay"
    assert recs and all(r["source"] == "replay" for r in recs)
    assert all(r["original_source"] == "hardware" and r["transport"] == "replay" for r in recs)
    assert not any(r["live_hardware"] for r in recs)
    rows = list(csv.DictReader(io.StringIO(csv_txt)))
    assert rows and all((r["source"], r["original_source"], r["transport"]) == ("replay", "hardware", "replay")
                        for r in rows)
    lines = [json.loads(x) for x in jsonl]
    assert lines and all(x["source"] == "replay" and x["meta"]["original_source"] == "hardware"
                         and x["meta"]["fw"] == "x" and x["meta"]["replayed_from"] == path for x in lines)


def test_replay_of_sim_log_unchanged():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "sim.jsonl")
        _write_log(path, "sim", n=60)
        with run_app("--source", f"replay:{path}", "--stale", "30",
                     wait_for=lambda st: st["counts"]["accepted"] > 5) as (base, port):
            recs = get_json(base + "/api/history")["records"]
    assert recs and all(r["source"] == "sim" and r["original_source"] is None for r in recs)
    assert all(r["transport"] == "replay" and r["live_hardware"] is False for r in recs)


def test_ingest_hardware_label_is_kept_but_not_live():
    """Ingest keeps sample.source as sent (contract), but only a serial transport is live hardware."""
    with run_app("--source", "ingest") as (base, port):
        assert post_json(base + "/api/sample", sample(0.0, 10.0, source="hardware"))[1].get("accepted") == 1
        r = get_json(base + "/api/history")["records"][-1]
    assert (r["source"], r["transport"], r["live_hardware"]) == ("hardware", "ingest", False)


def _node_badge_info(cases):
    if shutil.which("node") is None:
        pytest.skip("node not available")
    js = ("const m=require(%s);console.log(JSON.stringify(%s.map(c=>m.badgeInfo(c[0],c[1],c[2],c[3]))))"
          % (json.dumps(ROOT + "/app/static/headingmath.js"), json.dumps(cases)))
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)


def test_frontend_badge_info_mapping():
    """D6 + D8: the allowlisted-device badge (formerly HARDWARE) only for source hardware via serial with a verified
    device (uid on the allowlist)."""
    cases = [["sim", None, "sim", False], ["sim", None, "replay", False], ["replay", "hardware", "replay", False],
             ["replay", "sim", "replay", False], ["replay", None, "ingest", False], ["hardware", None, "serial", True],
             ["hardware", None, "ingest", True], ["hardware", None, "replay", True], ["hardware", None, None, True],
             ["SIM", None, "sim", True], [None, None, "sim", True], ["gps", "hardware", "serial", True],
             ["hardware", None, "serial", False], ["hardware", None, "serial", None], ["hardware", None, "serial", "true"],
             ["sim", None, "serial", False]]
    got = _node_badge_info(cases)
    text = [g and g["text"] for g in got]
    live = [g and g["live"] for g in got]
    assert text == ["SIMULATED", "SIMULATED", "REPLAY (recorded hardware)", "REPLAY (recorded simulator)", "REPLAY",
                    "ALLOWLISTED DEVICE (identity not authenticated)", "UNVERIFIED SOURCE", "UNVERIFIED SOURCE", "UNVERIFIED SOURCE", None, None, None,
                    "UNVERIFIED SOURCE", "UNVERIFIED SOURCE", "UNVERIFIED SOURCE", "SIMULATED"]
    assert [i for i, v in enumerate(live) if v] == [5]          # live hardware only: serial + verified device
    assert all(t is None or ("HARDWARE" not in t and "ALLOWLISTED" not in t) for i, t in enumerate(text) if i != 5)
