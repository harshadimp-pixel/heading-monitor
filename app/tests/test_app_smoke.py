"""Headless smoke tests of the running app over HTTP + WebSocket (no browser needed)."""
import csv
import io
import math
import os
import tempfile
import time
import json
import urllib.request

from ._helpers import WSClient, get_json, post_json, run_app, sample, wait_until

BADGE = {"sim": "SIMULATED", "replay": "REPLAY", "hardware": "HARDWARE"}


def test_sim_source_serves_ui_and_streams():
    with run_app("--source", "sim", wait_for=lambda st: st["counts"]["accepted"] > 5) as (base, port):
        health = get_json(base + "/api/health")
        assert health["ok"] is True and health["source_spec"] == "sim"
        html = urllib.request.urlopen(base + "/").read().decode()
        assert "DATA SOURCE" in html and "sourceBadge" in html
        for asset in ("/app.js", "/headingmath.js", "/style.css"):
            assert urllib.request.urlopen(base + asset).status == 200
        st = get_json(base + "/api/status")
        assert st["latest_sample_source"] == "sim"
        assert st["sensor_status"] in ("OK", "DEGRADED")
        assert st["gps"]["status"] == "unknown"
        ws = WSClient(port)
        assert " 101 " in ws.handshake.splitlines()[0]
        hello = ws.recv_json()
        assert hello["type"] == "hello" and hello["records"]
        n = 0
        for _ in range(10):
            m = ws.recv_json()
            for r in m["records"]:
                assert r["source"] in BADGE           # badge input comes from each sample
                h = r["heading_deg"]
                assert h is None or 0 <= h < 360
                n += 1
        ws.close()
        assert n > 0


def test_ingest_unknown_until_data_then_stale_and_badge_from_sample():
    with run_app("--source", "ingest") as (base, port):
        st = get_json(base + "/api/status")
        assert st["sensor_status"] == "NO DATA" and st["latest_sample_source"] is None
        code, j = post_json(base + "/api/sample", {"t": 0, "source": "sim"})       # missing mag_uT
        assert code == 422
        code, j = post_json(base + "/api/sample", {"t": 0, "source": "bogus", "mag_uT": [1, 2, 3]})
        assert code == 422
        # source "replay" pushed over HTTP ingest: badge must follow the sample, not the transport
        code, j = post_json(base + "/api/sample", sample(0.0, 90.0, source="replay"))
        assert code == 200, j
        st = get_json(base + "/api/status")
        assert st["latest_sample_source"] == "replay"
        rec = get_json(base + "/api/history")["records"][-1]
        assert abs(((rec["heading_deg"] - 90 + 180) % 360) - 180) < 0.5
        post_json(base + "/api/reference", {"deg": 100})
        post_json(base + "/api/sample", sample(0.1, 90.0, source="hardware"))
        rec = get_json(base + "/api/history")["records"][-1]
        assert rec["source"] == "hardware"
        assert abs(rec["deviation_deg"] - (-10)) < 0.5
        time.sleep(2.4)
        st = get_json(base + "/api/status")
        assert st["sensor_status"] == "STALE"


def test_ingest_rejected_for_other_sources():
    with run_app("--source", "sim") as (base, port):
        code, _ = post_json(base + "/api/sample", sample(0, 0))
        assert code == 409


def test_replay_file_and_csv_export():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        for i in range(30):
            f.write(json.dumps(sample(i * 0.02, (i * 3) % 360, source="replay")) + "\n")
        f.write("not json\n")
    try:
        with run_app("--source", f"replay:{path}",
                     wait_for=lambda st: st["source_status"].get("state") == "ended") as (base, port):
            st = get_json(base + "/api/status")
            assert st["counts"]["accepted"] == 30 and st["counts"]["invalid"] == 1
            assert st["latest_sample_source"] == "replay"
            text = urllib.request.urlopen(base + "/api/export.csv").read().decode()
            rows = list(csv.DictReader(io.StringIO(text)))
            assert len(rows) == 30
            for col in ("recv_time_iso", "heading_deg", "reference_deg", "deviation_deg", "bx_uT", "by_uT",
                        "bz_uT", "field_raw_uT", "quality", "sensor_status", "gps_status"):
                assert col in rows[0]
            for banned in ("lat", "lon", "speed", "course", "distance", "position"):   # heading-only app
                assert not any(banned in c for c in rows[0]), banned
            assert rows[0]["gps_status"] == "unknown" and rows[0]["mag_raw_x"] == ""
            assert rows[0]["reference_deg"] == ""          # unknown -> empty, never 0
    finally:
        os.unlink(path)


def test_calibration_wizard_fit_apply_save_load():
    with run_app("--source", "ingest") as (base, port):
        assert post_json(base + "/api/calib/start", {"target": 200})[0] == 200
        off = [6.0, -4.0, 2.5]
        batch, t = [], 0.0
        for i in range(400):                       # golden-spiral sphere of directions + hard iron
            z = 1 - 2 * (i + 0.5) / 400
            r = math.sqrt(1 - z * z)
            phi = i * math.pi * (3 - math.sqrt(5))
            v = [50 * r * math.cos(phi) + off[0], 50 * r * math.sin(phi) + off[1], 50 * z + off[2]]
            batch.append({"t": t, "source": "sim", "mag_uT": v})
            t += 0.01
        code, j = post_json(base + "/api/sample", batch)
        assert code == 200, j
        w = get_json(base + "/api/status")["wizard"]
        assert w["n"] == 400 and w["octants_covered"] == 8
        code, j = post_json(base + "/api/calib/fit", {})
        assert code == 200, j
        cal = j["calibration"]
        got = cal.get("offset_uT", cal.get("offset"))     # heading_core key, or stub key
        assert all(abs(a - b) < 0.5 for a, b in zip(got, off)), (got, j["backend"])
        assert post_json(base + "/api/calib/apply", {})[0] == 200
        st = get_json(base + "/api/status")
        assert st["calibration"]["active"]
        code, j = post_json(base + "/api/calib/save", {"name": "pytest_tmp_cal"})
        assert code == 200 and j["file"] == "pytest_tmp_cal.json"
        try:
            assert post_json(base + "/api/calib/clear", {})[0] == 200
            assert not get_json(base + "/api/status")["calibration"]["active"]
            assert post_json(base + "/api/calib/load", {"name": "pytest_tmp_cal"})[0] == 200
            assert get_json(base + "/api/status")["calibration"]["active"]
            params = get_json(base + "/api/status")["calibration"]["params"]
            from app.hub import CALIBRATIONS_DIR as CD
            with open(os.path.join(CD, "pytest_tmp_cal.json")) as f:
                saved = json.load(f)
            assert saved["calibration"] == params                       # JSON round-trip exact
            assert get_json(base + "/api/calib/current")["calibration"] == params
            assert post_json(base + "/api/calib/clear", {})[0] == 200
            assert post_json(base + "/api/calib/load", {"doc": saved})[0] == 200   # upload path
            assert get_json(base + "/api/status")["calibration"]["params"] == params
            assert post_json(base + "/api/calib/load", {"doc": {"nope": 1}})[0] == 400
            assert get_json(base + "/api/status")["calibration"]["active"]   # bad file keeps previous
        finally:
            from app.hub import CALIBRATIONS_DIR
            os.unlink(os.path.join(CALIBRATIONS_DIR, "pytest_tmp_cal.json"))


def test_recording_jsonl_is_replayable_contract():
    with run_app("--source", "ingest") as (base, port):
        code, j = post_json(base + "/api/record/start", {"format": "jsonl"})
        name = j["file"]
        post_json(base + "/api/sample", [sample(i * 0.1, 10 * i) for i in range(5)])
        code, j = post_json(base + "/api/record/stop", {})
        assert j["file"] == name
        body = urllib.request.urlopen(f"{base}/recordings/{name}").read().decode().splitlines()
        from app.hub import RECORDINGS_DIR
        os.unlink(os.path.join(RECORDINGS_DIR, name))
        assert len(body) == 5 and json.loads(body[0])["source"] == "sim"


def test_serial_without_bridge_reports_fault_not_fake_data():
    with run_app("--source", "serial:/dev/does-not-exist",
                 wait_for=lambda st: st["source_status"].get("state") in ("fault", "ended")) as (base, port):
        st = get_json(base + "/api/status")
        assert st["latest_sample_source"] is None      # never fabricates hardware samples
        assert st["sensor_status"] in ("FAULT", "NO DATA")


def _node_badges(sources):
    """Run the FRONTEND badge mapping (static/headingmath.js) in Node for the given source values."""
    import shutil
    import subprocess
    if shutil.which("node") is None:
        return None
    from ._helpers import ROOT
    js = ("const m=require(%s);console.log(JSON.stringify(%s.map(s=>m.badgeLabel(s))))"
          % (json.dumps(ROOT + "/app/static/headingmath.js"), json.dumps(sources)))
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)


def test_badge_always_equals_sample_source_for_every_pushed_record():
    """(c) Push a mixed sequence of sources; every WebSocket record carries its sample's own source,
    and the frontend mapping turns exactly that value into the badge text."""
    seq = ["sim", "replay", "hardware", "hardware", "sim", "replay", "sim"] * 5
    with run_app("--source", "ingest") as (base, port):
        ws = WSClient(port)
        assert ws.recv_json()["type"] == "hello"
        sent = []
        for i, src in enumerate(seq):
            s = sample(i * 0.05, (i * 11) % 360, source=src)
            s["meta"] = {"i": i}
            assert post_json(base + "/api/sample", s)[0] == 200
            sent.append(src)
            st = get_json(base + "/api/status")
            assert st["latest_sample_source"] == src            # status follows the latest sample only
        got = []
        t0 = time.time()
        while len(got) < len(seq) and time.time() - t0 < 5:
            got.extend(ws.recv_json()["records"])
        ws.close()
    assert [r["source"] for r in got] == sent                   # 100% of pushed frames, in order
    frontend = _node_badges([r["source"] for r in got] + ["", None, "SIM", "gps"])
    if frontend is not None:
        assert frontend[:len(got)] == [BADGE[s] for s in sent]
        assert frontend[len(got):] == [None, None, None, None]  # never guessed for unknown values


def test_badge_matches_sim_source_over_websocket():
    """(b)+(c) with the real sim source: every received sample is source='sim' -> SIMULATED."""
    with run_app("--source", "sim", wait_for=lambda st: st["counts"]["accepted"] > 3) as (base, port):
        ws = WSClient(port)
        recs = ws.recv_json()["records"]
        for _ in range(8):
            recs += ws.recv_json()["records"]
        ws.close()
    assert len(recs) > 10
    frontend = _node_badges(sorted({r["source"] for r in recs}))
    assert {r["source"] for r in recs} == {"sim"}
    if frontend is not None:
        assert frontend == ["SIMULATED"]


def test_mag_raw_is_optional():
    """CAN-L4-3100 / DroneCAN streams carry no raw counts: samples without mag_raw must work;
    samples with valid mag_raw are passed through; malformed mag_raw is rejected, not crashed on."""
    with run_app("--source", "ingest") as (base, port):
        s = sample(0.0, 10.0, source="hardware")
        assert "mag_raw" not in s
        assert post_json(base + "/api/sample", s)[0] == 200
        rec = get_json(base + "/api/history")["records"][-1]
        assert rec["mag_raw"] is None and rec["heading_deg"] is not None
        s2 = dict(sample(0.1, 20.0), mag_raw=[1950, -1125, 3000], rm3100_cycle_count=200)
        assert post_json(base + "/api/sample", s2)[0] == 200
        assert get_json(base + "/api/history")["records"][-1]["mag_raw"] == [1950, -1125, 3000]
        assert post_json(base + "/api/sample", dict(sample(0.2, 0), mag_raw=[1.5, 2, 3]))[0] == 422
        rows = list(csv.DictReader(io.StringIO(urllib.request.urlopen(base + "/api/export.csv").read().decode())))
        assert rows[0]["mag_raw_x"] == "" and rows[1]["mag_raw_x"] == "1950"


def test_gps_availability_absent_present_invalid():
    """Optional sample.gps {fix, num_sat, hdop}: absent -> unknown; present -> passed through;
    invalid -> heading sample still accepted, GPS shown as unknown, error reported. No coordinates ever."""
    with run_app("--source", "ingest") as (base, port):
        assert get_json(base + "/api/status")["gps"]["status"] == "unknown"          # no data at all
        assert post_json(base + "/api/sample", sample(0.0, 10.0))[0] == 200            # gps absent
        g = get_json(base + "/api/status")["gps"]
        assert g["status"] == "unknown" and g["fix"] is None and g["num_sat"] is None and g["hdop"] is None
        s = dict(sample(0.1, 10.0), gps={"fix": "3d", "num_sat": 11, "hdop": 0.8})
        assert post_json(base + "/api/sample", s)[0] == 200
        g = get_json(base + "/api/status")["gps"]
        assert (g["status"], g["fix"], g["num_sat"], g["hdop"]) == ("available", "3d", 11, 0.8)
        s = dict(sample(0.2, 10.0), gps={"fix": "none", "num_sat": 0})
        post_json(base + "/api/sample", s)
        g = get_json(base + "/api/status")["gps"]
        assert (g["status"], g["fix"], g["num_sat"], g["hdop"]) == ("unavailable", "none", 0, None)
        post_json(base + "/api/sample", dict(sample(0.3, 10.0), gps={"fix": "unknown", "num_sat": 4}))
        assert get_json(base + "/api/status")["gps"]["status"] == "unknown"
        for bad in ({"fix": "rtk"}, {"num_sat": -1}, {"num_sat": 3.5}, {"hdop": "x"}, "3d", [1]):
            code, j = post_json(base + "/api/sample", dict(sample(0.4, 20.0), gps=bad))
            assert code == 200, (bad, j)                       # heading sample still accepted
            st = get_json(base + "/api/status")
            assert st["gps"]["status"] == "unknown" and st["gps"]["error"], bad
            assert "gps" in st["last_error"]
            rec = get_json(base + "/api/history")["records"][-1]
            assert rec["heading_deg"] is not None and rec["gps_status"] == "unknown"
        assert get_json(base + "/api/status")["counts"]["gps_invalid"] == 6
        rows = list(csv.DictReader(io.StringIO(urllib.request.urlopen(base + "/api/export.csv").read().decode())))
        assert [r["gps_status"] for r in rows[:4]] == ["unknown", "available", "unavailable", "unknown"]
        assert (rows[1]["gps_fix"], rows[1]["gps_num_sat"], rows[1]["gps_hdop"]) == ("3d", "11", "0.8")
        assert rows[0]["gps_fix"] == "" and rows[0]["gps_num_sat"] == "" and rows[0]["gps_hdop"] == ""
        for banned in ("lat", "lon", "speed", "course", "distance", "position"):
            assert not any(banned in c for c in rows[0])
        time.sleep(2.4)                                        # stale -> GPS also Unknown
        assert get_json(base + "/api/status")["gps"]["status"] == "unknown"


def test_gps_in_recordings():
    from app.hub import RECORDINGS_DIR
    with run_app("--source", "ingest") as (base, port):
        names = []
        for fmt in ("csv", "jsonl"):
            names.append(post_json(base + "/api/record/start", {"format": fmt})[1]["file"])
            post_json(base + "/api/sample", [dict(sample(0.1, 5), gps={"fix": "2d", "num_sat": 6, "hdop": 1.7}),
                                             sample(0.2, 6)])
            post_json(base + "/api/record/stop", {})
            time.sleep(1.1)                                    # recording names are per-second
        csv_txt = urllib.request.urlopen(f"{base}/recordings/{names[0]}").read().decode()
        jsonl = urllib.request.urlopen(f"{base}/recordings/{names[1]}").read().decode().splitlines()
        for n in names:
            os.unlink(os.path.join(RECORDINGS_DIR, n))
    rows = list(csv.DictReader(io.StringIO(csv_txt)))
    assert (rows[0]["gps_status"], rows[0]["gps_fix"], rows[0]["gps_num_sat"], rows[0]["gps_hdop"]) == \
        ("available", "2d", "6", "1.7")
    assert rows[1]["gps_status"] == "unknown" and rows[1]["gps_fix"] == ""
    assert json.loads(jsonl[0])["gps"] == {"fix": "2d", "num_sat": 6, "hdop": 1.7}
    assert "gps" not in json.loads(jsonl[1])
