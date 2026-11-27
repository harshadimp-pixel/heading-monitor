"""U1-U5 dashboard checks against T6's OWN app instance (ephemeral port, PID-verified listener). [SIMULATED]

Method: start `python -m app --source ingest --port <free>`; confirm with `ss -ltnp` that the PID T6 launched owns the
listening socket; POST hand-made Samples (T6 reference model) to /api/sample; read /api/history; compare with a fresh
heading_core.HeadingEstimator fed the same samples (black-box equality) and with the T6 reference truth; check the
UI's own display maths (app/static/headingmath.js) in Node for rounding / 0-360 wrap / badge mapping.
"""
import json, math, os, re, shutil, socket, subprocess, sys, time, urllib.request, pytest
from conftest import ROOT, load
from refmodel import body_vectors, wrapdiff

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

def listener_pid(port):
    out = subprocess.run(["ss", "-ltnpH", f"sport = :{port}"], capture_output=True, text=True).stdout
    m = re.search(r"pid=(\d+)", out); return int(m.group(1)) if m else None

def get(port, path):
    return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3).read())

def post(port, path, obj):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        return json.loads(urllib.request.urlopen(req, timeout=3).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}") | {"_http": e.code}

def start(args):
    if not os.path.isfile(os.path.join(ROOT, "app", "__main__.py")):
        pytest.skip("NOT RUN (missing deliverable): app/__main__.py")
    port = free_port()
    p = subprocess.Popen([sys.executable, "-m", "app", "--host", "127.0.0.1", "--port", str(port), *args], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for _ in range(60):
        time.sleep(0.2)
        if p.poll() is not None: pytest.fail("app exited: " + p.stdout.read().decode()[-1500:])
        if listener_pid(port): break
    return p, port

@pytest.fixture
def app_ingest():
    p, port = start(["--source", "ingest", "--stale", "1.5"])
    yield p, port
    p.terminate(); p.wait(5)
    assert listener_pid(port) is None, "port still bound after shutdown"

def test_U1_own_instance_sim():
    p, port = start(["--source", "sim"])
    try:
        assert listener_pid(port) == p.pid, f"listener pid {listener_pid(port)} != launched pid {p.pid}"
        h = get(port, "/api/health"); assert h["ok"] and h["source_spec"].startswith("sim")
        html = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3).read().decode()
        assert "sourceBadge" in html
        time.sleep(1.5); recs = get(port, "/api/history?since=0")["records"]
        assert recs and all(r["source"] == "sim" for r in recs)
        print(f"U1 own instance pid={p.pid} port={port}: {len(recs)} sim records in 1.5 s")
    finally:
        p.terminate(); p.wait(5)
    assert listener_pid(port) is None

def S(t, yaw, src, p=0, r=0):
    m, a = body_vectors(yaw, p, r); return {"t": t, "source": src, "mag_uT": m.tolist(), "accel_g": a.tolist()}

def test_U2_U3_values_badges_wrap(app_ingest):
    p, port = app_ingest
    assert listener_pid(port) == p.pid
    hc = load("heading_core")
    yaws = [359.96, 359.6, 0.04, 0.0, 90, 180, 270, 359.94, 0.06, 123.45]
    srcs = ["sim", "replay", "hardware"]
    samples = [S(i * 0.05, y, srcs[i % 3], p=10 if i % 2 else 0, r=-8) for i, y in enumerate(yaws)]
    for s in samples:
        assert post(port, "/api/sample", s).get("accepted") == 1
    recs = get(port, "/api/history?since=0")["records"]
    assert len(recs) == len(samples)
    est = hc.HeadingEstimator()  # app runs without calibration -> same default path
    ref = [est.update(dict(s)) for s in samples]
    worst_core = max(abs(wrapdiff(r["heading_deg"], q["heading_deg"])) for r, q in zip(recs, ref))
    worst_truth = max(abs(wrapdiff(r["heading_deg"], y)) for r, y in zip(recs, yaws))
    for r, s in zip(recs, samples):
        assert r["source"] == s["source"]
        assert 0 <= r["heading_deg"] < 360
    # UI display maths in Node (the functions app.js uses)
    js = os.path.join(ROOT, "app", "static", "headingmath.js")
    if not shutil.which("node"): pytest.skip("node not available")
    code = ("const H=require(process.argv[1]);const recs=JSON.parse(require('fs').readFileSync(0,'utf8'));"
            "console.log(JSON.stringify(recs.map(r=>[H.roundHeading(r.heading_deg).toFixed(1),H.badgeLabel(r.source),H.cardinal(r.heading_deg)])))")
    out = json.loads(subprocess.run(["node", "-e", code, js], input=json.dumps(recs), capture_output=True, text=True, check=True).stdout)
    # badgeLabel is the internal source->text mapping; it is not a pass criterion for "hardware" (D8: plain hardware is
    # never displayed by that text). What the page DISPLAYS comes from badgeInfo and is asserted below.
    mapping = {"sim": ("SIMULATED",), "replay": ("REPLAY",)}
    for (disp, badge, card), r in zip(out, recs):
        if r["source"] in mapping:
            assert badge in mapping[r["source"]], (badge, r["source"])
        else:
            assert badge, (badge, r["source"])   # contract source -> some (internal) label, never null
        assert disp != "360.0"
        assert abs(wrapdiff(float(disp), r["heading_deg"])) <= 0.05 + 1e-9, (disp, r["heading_deg"])
    print(f"U2/U3 app vs heading_core max diff {worst_core:.2e} deg; app vs truth max {worst_truth:.3f} deg; displayed: {[o[0] for o in out]}; badges {[o[1] for o in out]}")
    assert worst_core <= 1e-6
    for bad in ("SIMULATED", "sensor", "", None, "HARDWARE"):
        o = json.loads(subprocess.run(["node", "-e", "const H=require(process.argv[1]);console.log(JSON.stringify(H.badgeLabel(JSON.parse(process.argv[2]))))", js, json.dumps(bad)],
                                      capture_output=True, text=True, check=True).stdout)
        assert o is None, f"badge inferred from non-contract source {bad!r}"
    # D8 label decision (d5374a1): the DISPLAYED badge (badgeInfo) for source "hardware" is never the bare word HARDWARE.
    # Every transport / verification combination -> UNVERIFIED SOURCE, except app-own serial + verified -> the decided label.
    combos = [[t, v] for t in ("serial", "ingest", "replay", "sim", None, "SERIAL") for v in (True, False, None, "true", 1)]
    code = ("const H=require(process.argv[1]);const c=JSON.parse(process.argv[2]);"
            "console.log(JSON.stringify(c.map(([t,v])=>H.badgeInfo('hardware',null,t,v))))")
    infos = json.loads(subprocess.run(["node", "-e", code, js, json.dumps(combos)], capture_output=True, text=True, check=True).stdout)
    label = "ALLOWLISTED DEVICE (identity not authenticated)"
    for (t, v), bi in zip(combos, infos):
        assert bi and bi["text"] != "HARDWARE", (t, v, bi)
        if t == "serial" and v is True:
            assert bi["text"] == label and bi["live"] is True, (t, v, bi)
        else:
            assert bi["text"] == "UNVERIFIED SOURCE" and bi["live"] is False, (t, v, bi)

def test_U4_errors_and_staleness_surfaced(app_ingest):
    p, port = app_ingest
    base = S(0, 45, "sim")
    post(port, "/api/sample", base)
    big = dict(base, t=0.05, mag_uT=[v * 3 for v in base["mag_uT"]])
    post(port, "/api/sample", big)
    bad = post(port, "/api/sample", dict(base, t=0.1, mag_uT=[float("nan"), 1, 2]) if False else dict(base, t=0.1, mag_uT=[1, 2]))
    recs = get(port, "/api/history?since=0")["records"]
    st = get(port, "/api/status")
    print("U4 big-field warnings:", recs[-1]["warnings"], "quality", round(recs[-1]["quality"], 3), "| malformed ->", bad, "| counts", st["counts"])
    assert "FIELD_MAGNITUDE_OUT_OF_RANGE" in recs[-1]["warnings"] and recs[-1]["quality"] < recs[0]["quality"]
    assert bad.get("accepted", 0) == 0 and st["counts"]["invalid"] >= 1
    time.sleep(2.2)
    st2 = get(port, "/api/status")
    print("U4 after 2.2 s silence: sensor_status", st2["sensor_status"])
    assert st2["sensor_status"] != "OK"

def test_U5_csv_export_roundtrip(app_ingest):
    p, port = app_ingest
    for i, y in enumerate((10, 200, 359.9)):
        post(port, "/api/sample", S(i * .05, y, "replay"))
    csv = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/export.csv", timeout=3).read().decode().splitlines()
    hdr = csv[0].split(","); i = hdr.index("heading_deg")
    recs = get(port, "/api/history?since=0")["records"]
    vals = [float(l.split(",")[i]) for l in csv[1:]]
    assert len(vals) == 3 and max(abs(a - r["heading_deg"]) for a, r in zip(vals, recs)) <= 1e-6

@pytest.mark.parametrize("yaw,expect", [(359.96, "0.0"), (359.94, "359.9"), (0.04, "0.0"), (0.06, "0.1"), (180.0, "180.0"), (89.95, "90.0")])
def test_U3_steady_display_and_wrap(app_ingest, yaw, expect):
    """Hold a heading steady (filter settled) and check the value the dashboard would print."""
    p, port = app_ingest
    for i in range(80):
        post(port, "/api/sample", S(i * 0.05, yaw, "sim"))
    r = get(port, "/api/history?since=0")["records"][-1]
    js = os.path.join(ROOT, "app", "static", "headingmath.js")
    disp = subprocess.run(["node", "-e", "const H=require(process.argv[1]);console.log(H.roundHeading(+process.argv[2]).toFixed(1))", js, repr(r["heading_deg"])],
                          capture_output=True, text=True, check=True).stdout.strip()
    print(f"U3 truth {yaw} -> heading_deg {r['heading_deg']:.4f} -> displayed {disp}")
    assert abs(wrapdiff(r["heading_deg"], yaw)) <= 0.01 and disp == expect
