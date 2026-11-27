#!/usr/bin/env python3
"""T6 integrated end-to-end audit harness (black-box). Usage: python integration_run.py <repo_root> <out_dir>
Every app instance is started fresh by this script on an ephemeral port; the listening PID is verified with `ss`
to be the PID launched here, and the instance is shut down afterwards. All data is [SIMULATED] or [REPLAYED]."""
import json, os, re, shutil, socket, subprocess, sys, time, urllib.request, urllib.error

ROOT, OUT = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.makedirs(OUT, exist_ok=True)
PY = sys.executable
RESULTS = []
MAP = {"sim": "SIMULATED", "replay": "REPLAY", "hardware": "HARDWARE"}

def rec(step, cmd, ok, summary, raw):
    RESULTS.append({"step": step, "cmd": cmd, "pass": bool(ok), "summary": summary, "raw": raw[-3000:]})
    print(("PASS " if ok else "FAIL ") + step + " :: " + summary, flush=True)

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

def listener_pid(port):
    o = subprocess.run(["ss", "-ltnpH", f"sport = :{port}"], capture_output=True, text=True).stdout
    m = re.search(r"pid=(\d+)", o); return int(m.group(1)) if m else None

def http(port, path, obj=None, raw=False):
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, data=None if obj is None else json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if obj is None else "POST")
    try:
        b = urllib.request.urlopen(req, timeout=5).read()
    except urllib.error.HTTPError as e:
        b = e.read()
    return b.decode() if raw else json.loads(b or b"{}")

class App:
    def __init__(self, *args, root=None):
        self.port = free_port()
        self.cmd = [PY, "-m", "app", "--host", "127.0.0.1", "--port", str(self.port), *args]
        self.p = subprocess.Popen(self.cmd, cwd=root or ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for _ in range(75):
            time.sleep(0.2)
            if self.p.poll() is not None: break
            if listener_pid(self.port): break
        self.pid_ok = listener_pid(self.port) == self.p.pid
    def cmdline(self): return " ".join(self.cmd[1:]).replace(PY, "python")
    def close(self):
        self.p.terminate()
        try: out = self.p.communicate(timeout=5)[0]
        except subprocess.TimeoutExpired: self.p.kill(); out = self.p.communicate()[0]
        self.released = listener_pid(self.port) is None
        return out or ""
    def hist(self): return http(self.port, "/api/history?since=0")["records"]
    def status(self): return http(self.port, "/api/status")

def wdiff(a, b): return (a - b + 180) % 360 - 180

def wait(pred, t=15):
    end = time.time() + t
    while time.time() < end:
        try:
            if pred(): return True
        except Exception: pass
        time.sleep(0.25)
    return False

# ---------- A1: sim -> heading_core -> app for every scenario
scen = subprocess.run([PY, "-m", "sim", "--list-scenarios"], cwd=ROOT, capture_output=True, text=True).stdout
names = re.findall(r"^\s*([a-z_]+)\b", scen, re.M)
names = [n for n in names if n not in ("scenarios", "name")] or ["static"]
for n in names:
    a = App("--source", f"sim:{n}", "--rate", "50", "--seed", "3")
    try:
        wait(lambda: len(a.hist()) >= 150, 20)
        r = a.hist(); st = a.status()
        srcs = {x["source"] for x in r}
        back = {x.get("estimator_backend") for x in r}
        errs = [wdiff(x["heading_deg"], x["truth_heading_deg"]) for x in r[50:] if x.get("truth_heading_deg") is not None and x.get("heading_deg") is not None]
        rmse = (sum(e * e for e in errs) / len(errs)) ** 0.5 if errs else float("nan")
        warns = sorted({w for x in r for w in (x.get("warnings") or [])})
        inrange = all(x.get("heading_deg") is not None and 0 <= x["heading_deg"] < 360 for x in r)
        ok = a.pid_ok and len(r) >= 150 and srcs == {"sim"} and back == {"heading_core"} and inrange
        summ = (f"pid_ok={a.pid_ok} records={len(r)} sources={sorted(srcs)} badge={MAP.get(next(iter(srcs)), None) if len(srcs)==1 else srcs} "
                f"backend={sorted(back)} RMSE_vs_truth(after 1 s, uncalibrated app)={rmse:.2f} deg warnings={warns} sim_status={st['source_status'].get('backend')}")
    finally:
        out = a.close()
    rec(f"A1 sim:{n} -> heading_core -> app", a.cmdline(), ok and a.released, summ + f" port_released={a.released}", out)

# ---------- A1b: motor_interference with a short sim duration so the current profile actually plays out in the app
if "--sim-duration" in subprocess.run([PY, "-m", "app", "--help"], cwd=ROOT, capture_output=True, text=True).stdout:
    a = App("--source", "sim:motor_interference", "--rate", "20", "--seed", "3", "--sim-duration", "10", "--stale", "60")
    try:
        wait(lambda: len(a.hist()) >= 195, 25)
        r = a.hist()
        extra = sorted({w for x in r for w in (x.get("warnings") or [])} - {"NOT_CALIBRATED"})
        errs = [abs(wdiff(x["heading_deg"], x["truth_heading_deg"])) for x in r if x.get("truth_heading_deg") is not None and x.get("heading_deg") is not None]
        flagged_bad = [x for x in r if x.get("truth_heading_deg") is not None and abs(wdiff(x["heading_deg"], x["truth_heading_deg"])) > 5]
        unflagged_bad = [x for x in flagged_bad if not (set(x.get("warnings") or []) - {"NOT_CALIBRATED"})]
        ok = a.pid_ok and len(r) >= 150 and bool(extra)
        summ = (f"pid_ok={a.pid_ok} records={len(r)} warnings_seen={extra} max|err|={max(errs):.1f} deg "
                f"samples err>5deg={len(flagged_bad)} of which without any warning={len(unflagged_bad)}")
    finally:
        out = a.close()
    rec("A1b sim:motor_interference (--sim-duration 10) -> app: interference must be warned", a.cmdline(), ok, summ, out)

# ---------- A2: replay of every sim example log
for f in sorted(os.listdir(os.path.join(ROOT, "sim", "examples"))):
    if not f.endswith(".jsonl"): continue
    path = os.path.join(ROOT, "sim", "examples", f)
    nlines = sum(1 for l in open(path) if l.strip())
    a = App("--source", f"replay:{path}", "--speed", "20")
    try:
        wait(lambda: a.status()["source_status"]["state"] == "ended", 30)
        r = a.hist(); st = a.status()
        srcs = sorted({x["source"] for x in r})
        ok = a.pid_ok and len(r) == min(nlines, 2000) - 0 and all(x.get("heading_deg") is not None for x in r)
        summ = (f"pid_ok={a.pid_ok} file_lines={nlines} records={len(r)} invalid={st['counts'].get('invalid')} sample.source={srcs} "
                f"badge={[MAP[s] for s in srcs if s in MAP]} state={st['source_status']['state']}")
    finally:
        out = a.close()
    rec(f"A2 replay sim/examples/{f}", a.cmdline().replace(ROOT + "/", ""), ok, summ, out)

# ---------- A3: firmware --capture of fake-FC, replayed via firmware_bridge --replay, then into the app
cap, fake_out, rep_out = (os.path.join(OUT, x) for x in ("fake_capture.jsonl", "fake_samples.jsonl", "capture_replayed.jsonl"))
c1 = [PY, "-m", "firmware_bridge", "--fake-fc", "--count", "60", "--capture", cap, "--out", fake_out]
p1 = subprocess.run(c1, cwd=ROOT, capture_output=True, text=True)
c2 = [PY, "-m", "firmware_bridge", "--replay", cap, "--out", rep_out]
p2 = subprocess.run(c2, cwd=ROOT, capture_output=True, text=True)
fs = [json.loads(l) for l in open(fake_out)] if os.path.exists(fake_out) else []
rs = [json.loads(l) for l in open(rep_out)] if os.path.exists(rep_out) else []
same = len(fs) == len(rs) and all(a_["mag_uT"] == b_["mag_uT"] for a_, b_ in zip(fs, rs))
hdr = json.loads(open(cap).readline()) if os.path.exists(cap) else {}
ok = p1.returncode == 0 and p2.returncode == 0 and len(fs) == 60 and same and {s["source"] for s in fs} == {"sim"} and {s["source"] for s in rs} == {"replay"} and hdr.get("source") == "sim"
rec("A3a fake-FC --capture -> firmware_bridge --replay", "python -m firmware_bridge --fake-fc --count 60 --capture fake_capture.jsonl --out fake_samples.jsonl ; python -m firmware_bridge --replay fake_capture.jsonl --out capture_replayed.jsonl",
    ok, f"rc={p1.returncode}/{p2.returncode} capture_header_source={hdr.get('source')} live={len(fs)} (source {sorted({s['source'] for s in fs})}) replayed={len(rs)} (source {sorted({s['source'] for s in rs})}) mag bit-identical={same}",
    p1.stderr + p2.stderr)
a = App("--source", f"replay:{rep_out}", "--speed", "20")
try:
    wait(lambda: a.status()["source_status"]["state"] == "ended", 20)
    r = a.hist(); srcs = sorted({x["source"] for x in r})
    ok = a.pid_ok and len(r) == len(rs) and srcs == ["replay"]
    summ = f"pid_ok={a.pid_ok} records={len(r)} sample.source={srcs} badge={[MAP[s] for s in srcs]} heading[0..3]={[round(x['heading_deg'],1) for x in r[:3]]}"
finally:
    out = a.close()
rec("A3b capture replay -> app", a.cmdline().replace(OUT + "/", "<out>/"), ok, summ, out)

# ---------- A4: fake-FC MSP stream through firmware_bridge into the app (ingest); badge must be SIMULATED, never HARDWARE
a = App("--source", "ingest", "--stale", "30")
try:
    bridge = subprocess.Popen([PY, "-m", "firmware_bridge", "--fake-fc", "--count", "100"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    acc = 0; rej = []
    for line in bridge.stdout:
        resp = http(a.port, "/api/sample", json.loads(line)); acc += resp.get("accepted", 0)
        if resp.get("errors"): rej += resp["errors"]
    bridge.wait()
    r = a.hist(); srcs = sorted({x["source"] for x in r}); st = a.status()
    ok = a.pid_ok and acc == 100 and srcs == ["sim"] and "hardware" not in srcs and st["latest_sample_source"] == "sim"
    summ = f"pid_ok={a.pid_ok} posted=100 accepted={acc} rejected={rej[:3]} sources={srcs} badge={[MAP[s] for s in srcs]} heading range={min(x['heading_deg'] for x in r):.1f}..{max(x['heading_deg'] for x in r):.1f}"
finally:
    out = a.close()
rec("A4 firmware_bridge --fake-fc | POST -> app (ingest)", "python -m firmware_bridge --fake-fc --count 100 | POST each line to /api/sample ; " + a.cmdline(), ok, summ, out)

# ---------- A5: calibration wizard flow
a = App("--source", "sim:calibration_dance", "--rate", "50", "--seed", "5")
log = []
try:
    log.append(("start", http(a.port, "/api/calib/start", {})))
    done = wait(lambda: a.status()["wizard"]["n"] >= a.status()["wizard"]["target"], 40)
    log.append(("stop", http(a.port, "/api/calib/stop", {})))
    wz = a.status()["wizard"]
    fit = http(a.port, "/api/calib/fit", {}); log.append(("fit", {k: fit.get(k) for k in ("ok", "backend", "error")}))
    ap = http(a.port, "/api/calib/apply", {}); log.append(("apply", ap))
    time.sleep(1.5)
    r = a.hist()[-50:]
    cal_flag = all(x.get("calibrated") for x in r)
    errs = [wdiff(x["heading_deg"], x["truth_heading_deg"]) for x in r if x.get("truth_heading_deg") is not None]
    rmse = (sum(e * e for e in errs) / len(errs)) ** 0.5 if errs else float("nan")
    sv = http(a.port, "/api/calib/save", {"name": "t6_audit_cal"}); log.append(("save", sv))
    lst = http(a.port, "/api/calib/list"); log.append(("list", lst))
    http(a.port, "/api/calib/clear", {}); time.sleep(0.6)
    cleared = a.status()["calibration"]["active"]
    ld = http(a.port, "/api/calib/load", {"name": "t6_audit_cal"}); log.append(("load", ld)); time.sleep(0.6)
    reloaded = a.status()["calibration"]["active"]
    params = (fit.get("calibration") or {})
    off = params.get("offset_uT")
    ok = a.pid_ok and done and fit.get("ok") and cal_flag and rmse <= 3.0 and cleared is False and reloaded is True
    summ = (f"pid_ok={a.pid_ok} collected n={wz['n']}/{wz['target']} bins={wz['heading_bins_covered']}/{wz['heading_bins_total']} octants={wz['octants_covered']}/{wz['octants_total']} "
            f"fit ok={fit.get('ok')} backend={fit.get('backend')} offset_uT={off} (sim truth hard-iron [12,-8,5]) | after apply: calibrated={cal_flag}, RMSE vs truth last 50={rmse:.2f} deg | "
            f"clear -> active={cleared}; load -> active={reloaded}")
finally:
    out = a.close()
    try: os.remove(os.path.join(ROOT, "app", "calibrations", "t6_audit_cal.json"))
    except OSError: pass
rec("A5 calibration wizard start/stop/fit/apply/save/clear/load", a.cmdline(), ok, summ, json.dumps(log, default=str)[:2500] + "\n" + out)

# ---------- A6: frozen data and stale (no data) via ingest
a = App("--source", "ingest", "--stale", "1.5")
try:
    s0 = {"t": 0, "source": "sim", "mag_uT": [25.0, -3.0, 43.0], "accel_g": [0.0, 0.0, -1.0]}
    for i in range(60): http(a.port, "/api/sample", dict(s0, t=i * 0.05))
    r = a.hist(); last = r[-1]; st = a.status()
    frozen_ok = any(w in (last.get("warnings") or []) for w in ("SENSOR_STALE", "MAG_STALE")) and last["quality"] < 0.2
    time.sleep(2.2); st2 = a.status()
    stale_ok = st2["sensor_status"] != "OK"
    ok = a.pid_ok and frozen_ok and stale_ok
    summ = (f"pid_ok={a.pid_ok} 3 s identical samples -> warnings={last.get('warnings')} quality={last['quality']:.3f} sensor_status={st['sensor_status']}; "
            f"then 2.2 s silence (stale 1.5 s) -> sensor_status={st2['sensor_status']} reason={st2.get('sensor_status_reason')!r}")
finally:
    out = a.close()
rec("A6 frozen + stale data", a.cmdline() + " ; POST 60 identical samples, then silence", ok, summ, out)

# ---------- A7: serial to a missing port
a = App("--source", "serial:/dev/ttyT6_DOES_NOT_EXIST")
try:
    time.sleep(3)
    alive = a.p.poll() is None
    st = a.status() if alive else {}
    r = a.hist() if alive else []
    ok = a.pid_ok and alive and st.get("source_status", {}).get("state") in ("fault", "ended", "error") and not r and st.get("sensor_status") != "OK"
    summ = (f"pid_ok={a.pid_ok} app alive={alive} source_status={st.get('source_status')} sensor_status={st.get('sensor_status')} "
            f"records={len(r)} (no HARDWARE samples fabricated)")
finally:
    out = a.close()
pb = subprocess.run([PY, "-m", "firmware_bridge", "--port", "/dev/ttyT6_DOES_NOT_EXIST"], cwd=ROOT, capture_output=True, text=True, timeout=30)
ok2 = pb.returncode != 0 and not pb.stdout.strip()
rec("A7 serial to missing port (app)", a.cmdline(), ok, summ, out)
rec("A7b firmware_bridge --port missing", "python -m firmware_bridge --port /dev/ttyT6_DOES_NOT_EXIST", ok2,
    f"rc={pb.returncode} stdout_lines={len(pb.stdout.splitlines())} stderr={pb.stderr.strip()[:300]!r}", pb.stderr)


def node_badges(records):
    """Evaluate the app's own headingmath.js badgeInfo(source, original_source, transport, device_verified) in Node for each record."""
    node = shutil.which("node")
    if not node: return [None] * len(records)
    js = ("const H=require(process.argv[1]);let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{"
          "const rs=JSON.parse(d);console.log(JSON.stringify(rs.map(r=>H.badgeInfo?H.badgeInfo(r.source,r.original_source,r.transport,r.device_verified):{text:H.badgeLabel(r.source)})));});")
    inp = json.dumps([{k: x.get(k) for k in ("source", "original_source", "transport", "device_verified")} for x in records])
    o = subprocess.run([node, "-e", js, os.path.join(ROOT, "app/static/headingmath.js")], input=inp, capture_output=True, text=True, timeout=30)
    return json.loads(o.stdout)

# ---------- A8: hardware-labelled log replayed through the app (badge semantics)
hw = os.path.join(OUT, "hw_labelled.jsonl")
with open(hw, "w") as f:
    for i in range(20): f.write(json.dumps({"t": i * 0.05, "source": "hardware", "mag_uT": [25.0, -3.0 + 0.01 * i, 43.0], "accel_g": [0, 0, -1]}) + "\n")
a = App("--source", f"replay:{hw}", "--speed", "20")
try:
    wait(lambda: a.status()["source_status"]["state"] == "ended", 15)
    r = a.hist(); srcs = sorted({x["source"] for x in r})
    origs = sorted({str(x.get("original_source")) for x in r}); lives = [x for x in r if x.get("live_hardware")]
    badges = sorted({b["text"] for b in node_badges(r) if b})
    ok = a.pid_ok and len(r) == 20 and srcs == ["replay"] and origs == ["hardware"] and not lives and badges == ["REPLAY (recorded hardware)"]
    summ = (f"pid_ok={a.pid_ok} file sample.source=hardware -> app records={len(r)} source={srcs} original_source={origs} "
            f"transport={sorted({str(x.get('transport')) for x in r})} live_hardware_true={len(lives)} -> badgeInfo (app's headingmath.js in Node)={badges}")
finally:
    out = a.close()
rec("A8 app replay of a hardware-labelled log: badge must not read HARDWARE", a.cmdline().replace(OUT + "/", "<out>/"), ok, summ, out)

# ---------- A9: UI render check in headless Chrome (sim and ingest-with-warning)
chrome = os.environ.get("CHROME") or next((shutil.which(c) for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if shutil.which(c)), None)
def dom(url, want):
    """Headless --dump-dom with a FRESH temporary profile (--user-data-dir) per call, removed afterwards, so a clean
    machine / sandbox where the default profile dir cannot be created still works (Codex finding). --incognito is
    needed: on Chrome 156 a fresh non-incognito profile did not exit after --dump-dom (30-60 s hang, no output, T6 test)."""
    import tempfile
    d = ""
    for _ in range(5):
        prof = tempfile.mkdtemp(prefix="t6-chrome-")
        try:
            d = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--incognito",
                                f"--user-data-dir={prof}", "--virtual-time-budget=5000", "--dump-dom", url],
                               capture_output=True, text=True, timeout=90).stdout
        finally:
            shutil.rmtree(prof, ignore_errors=True)
        if want(d): break
    return d
def text(d, id_):
    if id_ == "warnings":  # <ul id="warnings"> holds several <li>; take the whole list, not just the first item
        m = re.search(r'id="warnings"[^>]*>(.*?)</ul>', d, re.S)
        return " | ".join(x.strip() for x in re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), re.S)) if m else None
    m = re.search(r'id="%s"[^>]*>(.*?)</' % id_, d, re.S); return re.sub(r"<[^>]+>", " ", m.group(1)).strip() if m else None
if chrome:
    ver = subprocess.run([chrome, "--version"], capture_output=True, text=True).stdout.strip()
    a = App("--source", "sim:yaw_spin", "--stale", "60")
    try:
        wait(lambda: len(a.hist()) > 20, 10)
        d = dom(f"http://127.0.0.1:{a.port}/", lambda d: 'class="source-badge sim"' in d)
        badge, head, gps, warn = text(d, "sourceBadge"), text(d, "headingValue"), text(d, "gpsStatus"), text(d, "warnings")
        ok = a.pid_ok and badge == "SIMULATED" and bool(re.match(r"^\d{1,3}\.\d° [NESW]{1,3}$", head or "")) and gps == "Unknown" and warn is not None
        summ = f"{ver}; pid_ok={a.pid_ok} sourceBadge={badge!r} headingValue={head!r} gpsStatus={gps!r} warnings={warn!r}"
        open(os.path.join(OUT, "ui_dom_sim.html"), "w").write(d)
    finally:
        out = a.close()
    rec("A9a UI render (headless Chrome, sim)", f"{a.cmdline()} ; google-chrome --headless=new --dump-dom http://127.0.0.1:<port>/", ok, summ, out)
    a = App("--source", "ingest", "--stale", "600")
    try:
        import threading
        stop = threading.Event()
        def feed():  # keep data fresh while the headless browser renders (ingest has no own clock)
            i = 0
            while not stop.is_set():
                try:
                    http(a.port, "/api/sample", {"t": i * 0.05, "source": "replay", "mag_uT": [75.0, -9.0 + 0.1 * (i % 3), 129.0], "accel_g": [0, 0, -1]})
                    fed[0] += 1
                except Exception as e:
                    feed_err.append(repr(e))
                i += 1; time.sleep(0.05)
        fed, feed_err = [0], []
        th = threading.Thread(target=feed, daemon=True); th.start()
        wait(lambda: any("FIELD_MAGNITUDE" in w for w in (a.hist()[-1].get("warnings") or [])) if a.hist() else False, 15)
        d = dom(f"http://127.0.0.1:{a.port}/", lambda d: "FIELD_MAGNITUDE" in d)
        stop.set(); th.join(2)
        exp = a.hist()[-1]
        badge, head, warn = text(d, "sourceBadge"), text(d, "headingValue"), text(d, "warnings")
        shown = float(re.match(r"([\d.]+)", head).group(1)) if head and re.match(r"[\d.]+", head) else None
        ok = a.pid_ok and badge == "REPLAY" and "FIELD_MAGNITUDE_OUT_OF_RANGE" in (warn or "") and shown is not None and abs(wdiff(shown, exp["heading_deg"])) <= 0.5
        summ = f"pid_ok={a.pid_ok} fed={fed[0]} feed_errors={feed_err[:2]} sourceBadge={badge!r} headingValue={head!r} (api heading_deg={exp['heading_deg']:.3f}) warnings={warn!r}"
        open(os.path.join(OUT, "ui_dom_warning.html"), "w").write(d)
    finally:
        out = a.close()
    rec("A9b UI render (headless Chrome, 3x field -> warning)", a.cmdline() + " ; POST |B|~150 uT samples at 20 Hz continuously during render ; dump-dom", ok, summ, out)
    # A8b: what the browser shows for a replayed hardware-labelled file (badge + evidence banner)
    a = App("--source", f"replay:{hw}", "--speed", "1", "--loop", "--stale", "60")
    try:
        wait(lambda: len(a.hist()) > 5, 10)
        d = dom(f"http://127.0.0.1:{a.port}/", lambda d: "source-badge replay" in d)
        badge, banner, transport = text(d, "sourceBadge"), text(d, "evidenceBanner"), text(d, "transportText")
        ok = (a.pid_ok and badge == "REPLAY (recorded hardware)" and banner is not None and "not a live" in banner
              and not banner.lower().startswith("live"))
        summ = f"pid_ok={a.pid_ok} sourceBadge={badge!r} evidenceBanner={banner!r} transportText={transport!r}"
        open(os.path.join(OUT, "ui_dom_hw_replay.html"), "w").write(d)
    finally:
        out = a.close()
    rec("A8b UI render of a replayed hardware-labelled log (headless Chrome)", a.cmdline().replace(OUT + "/", "<out>/") + " ; dump-dom", ok, summ, out)
else:
    rec("A9 UI render", "-", False, "NOT RUN: no headless Chrome available", "")


# ---------- A10: D6 edge cases (re-test of 0ca6b0f)
# A10a: can a replayed file defeat the relabel? case variants, original_source tricks, injected transport/live fields
trick = os.path.join(OUT, "replay_tricks.jsonl")
variants = [
    ("upper-case HARDWARE", {"source": "HARDWARE"}),
    ("title-case Hardware", {"source": "Hardware"}),
    ("hardware + meta.original_source=sim", {"source": "hardware", "meta": {"original_source": "sim"}}),
    ("replay + original_source=hardware + top-level transport=serial, live_hardware=true", {"source": "replay", "meta": {"original_source": "hardware"}, "transport": "serial", "live_hardware": True}),
    ("hardware + top-level transport=serial, live_hardware=true", {"source": "hardware", "transport": "serial", "live_hardware": True}),
    ("replay + meta.original_source=HARDWARE", {"source": "replay", "meta": {"original_source": "HARDWARE"}}),
    ("replay + meta.original_source=object", {"source": "replay", "meta": {"original_source": {"x": "hardware"}}}),
    ("sim + meta.original_source=hardware", {"source": "sim", "meta": {"original_source": "hardware"}}),
    ("hardware + meta.replayed_from spoof", {"source": "hardware", "meta": {"replayed_from": "", "original_source": "replay"}}),
]
with open(trick, "w") as f:
    for i, (_, extra) in enumerate(variants):
        f.write(json.dumps(dict({"t": i * 0.05, "mag_uT": [25.0, -3.0, 43.0], "accel_g": [0, 0, -1]}, **extra)) + "\n")
a = App("--source", f"replay:{trick}", "--speed", "20")
try:
    wait(lambda: a.status()["source_status"]["state"] == "ended", 15)
    r = a.hist(); st = a.status(); nb = node_badges(r)
    rows = [(x.get("t"), x.get("source"), x.get("original_source"), x.get("transport"), x.get("live_hardware"), (b or {}).get("text")) for x, b in zip(r, nb)]
    bad = [row for row in rows if row[1] == "hardware" or row[4] or row[5] in ("HARDWARE", "UNVERIFIED SOURCE")]
    ok = a.pid_ok and not bad and len(r) + st["counts"]["invalid"] == len(variants)
    summ = (f"pid_ok={a.pid_ok} lines={len(variants)} accepted={len(r)} invalid={st['counts']['invalid']} last_error={st.get('last_error')!r}; "
            f"records (t, source, original_source, transport, live_hardware, badge)={rows}; violations={bad}")
finally:
    out = a.close()
rec("A10a replayed file cannot defeat the D6 relabel (case variants, original_source/transport/live tricks)", a.cmdline().replace(OUT + "/", "<out>/"), ok, summ,
    "variants: " + json.dumps([v[0] for v in variants]) + "\n" + out)

# A10b: ingest of a 'hardware' sample (with injected transport/live fields) -> UNVERIFIED SOURCE, never live
a = App("--source", "ingest", "--stale", "600")
try:
    import threading
    stop = threading.Event()
    def feed2():
        i = 0
        while not stop.is_set():
            try: http(a.port, "/api/sample", {"t": i * 0.05, "source": "hardware", "mag_uT": [25.0, -3.0 + 0.01 * (i % 5), 43.0], "accel_g": [0, 0, -1], "transport": "serial", "live_hardware": True})
            except Exception: pass
            i += 1; time.sleep(0.05)
    th = threading.Thread(target=feed2, daemon=True); th.start()
    wait(lambda: len(a.hist()) > 10, 10)
    d = dom(f"http://127.0.0.1:{a.port}/", lambda d: "source-badge unverified" in d) if chrome else ""
    stop.set(); th.join(2)
    r = a.hist(); nb = node_badges(r[-5:])
    badge, banner = (text(d, "sourceBadge"), text(d, "evidenceBanner")) if chrome else (None, None)
    srcs = sorted({x["source"] for x in r}); tr = sorted({str(x.get("transport")) for x in r}); lives = sum(bool(x.get("live_hardware")) for x in r)
    ok = (a.pid_ok and srcs == ["hardware"] and tr == ["ingest"] and lives == 0 and all((b or {}).get("text") == "UNVERIFIED SOURCE" for b in nb)
          and badge == "UNVERIFIED SOURCE" and banner is not None and banner.startswith("[UNVERIFIED]"))
    summ = (f"pid_ok={a.pid_ok} records={len(r)} sample.source={srcs} transport={tr} live_hardware_true={lives} "
            f"badgeInfo(Node)={sorted({(b or {}).get('text') for b in nb})} DOM sourceBadge={badge!r} evidenceBanner={banner!r}")
    if chrome: open(os.path.join(OUT, "ui_dom_ingest_hardware.html"), "w").write(d)
finally:
    out = a.close()
rec("A10b ingest of source=hardware (+ injected transport=serial) -> UNVERIFIED SOURCE, never live", a.cmdline() + " ; POST hardware samples ; dump-dom", ok, summ, out)

# A10c-A10g (D8, ARCHITECTURE 1bef73e): a serial connection is NOT proof of hardware. L-SER is withdrawn.
# A10c FAILS whenever the product fake FC on a virtual pty shows HARDWARE or any live record; it must show SIMULATED.
# A10d/e: unknown or unidentified device -> UNVERIFIED SOURCE. A10f: allowlisted UID -> HARDWARE (the only way).
# A10g: non-allowlisted UID with a non-empty allowlist -> UNVERIFIED SOURCE.
try:
    import serial  # noqa: F401
    have_serial = True
except Exception:
    have_serial = False

def serial_case(step, root, dev, want_badge, want_live, want_sources=None, extra=""):
    a = App("--source", f"serial:{dev.port}", "--stale", "60", root=root)
    try:
        wait(lambda: len(a.hist()) > 10, 25)
        d = dom(f"http://127.0.0.1:{a.port}/", lambda d: (text(d, "sourceBadge") or "NO DATA") != "NO DATA") if chrome else ""
        r = a.hist()
        badge, banner = (text(d, "sourceBadge"), text(d, "evidenceBanner")) if chrome else (None, None)
        srcs = sorted({x["source"] for x in r}); lives = sum(bool(x.get("live_hardware")) for x in r)
        ok = a.pid_ok and len(r) > 10 and badge == want_badge and (lives == len(r) if want_live else lives == 0)
        if want_sources is not None: ok = ok and srcs == want_sources
        summ = (f"pid_ok={a.pid_ok} port=<virtual pty> {extra} records={len(r)} sample.source={srcs} live_hardware_true={lives}/{len(r)} "
                f"DOM sourceBadge={badge!r} (required {want_badge!r}) evidenceBanner={banner!r}")
        safe = re.sub(r"[^a-z0-9]+", "_", step.split(" ")[0].lower())
        if chrome: open(os.path.join(OUT, f"ui_dom_{safe}.html"), "w").write(d)
    finally:
        out = a.close(); dev.close()
    rec(step, a.cmdline().replace(dev.port, "<pty>"), ok, summ, out)

if have_serial and hasattr(os, "openpty"):
    sys.path.insert(0, os.path.join(ROOT, "tests")); sys.path.insert(0, ROOT)
    from t6_msp_device import MSPDevice, ProductFakeFCOnPty
    serial_case("A10c D8: product fake FC on a virtual pty via serial: must be SIMULATED, never HARDWARE/live", ROOT,
                ProductFakeFCOnPty(), "SIMULATED", False, ["sim"], "device=firmware_bridge.fake_fc.FakeFC() (NO hardware)")
    serial_case("A10d D8: unknown device (INAV/MKH7, UID not listed) via serial: UNVERIFIED SOURCE", ROOT,
                MSPDevice(variant="INAV", board="MKH7", uid=bytes([0x99] * 12)), "UNVERIFIED SOURCE", False, None, "device=T6 MSPDevice")
    serial_case("A10e D8: unidentified device (identity queries fail) via serial: UNVERIFIED SOURCE", ROOT,
                MSPDevice(identity=False), "UNVERIFIED SOURCE", False, None, "device=T6 MSPDevice identity=False")
    # allowlist in a TEMPORARY copy of the export (the shipped config/verified_devices.json is never modified)
    uid_b = bytes([0x36, 0x54, 0x00, 0x2B, 0x11, 0x47, 0x33, 0x30, 0x39, 0x38, 0x31, 0x01])
    dev = MSPDevice(variant="INAV", board="MKH7", uid=uid_b)
    bp = subprocess.run([PY, "-m", "firmware_bridge", "--port", dev.port, "--count", "5"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    dev.close()
    ids = [((json.loads(l).get("meta") or {}).get("device_identity") or {}) for l in bp.stdout.splitlines() if l.startswith("{")]
    uids = sorted({i.get("uid") for i in ids if i.get("uid")})
    shipped_p = os.path.join(ROOT, "config", "verified_devices.json")
    shipped = json.load(open(shipped_p)) if os.path.exists(shipped_p) else None
    shipped_entries = (shipped if isinstance(shipped, list) else [v for k, v in (shipped or {}).items() if isinstance(v, list) for v in v]) if shipped is not None else None
    rec("A10h D8: shipped config/verified_devices.json exists and is empty", f"cat config/verified_devices.json", shipped_entries == [],
        f"exists={shipped is not None} entries={shipped_entries!r}", json.dumps(shipped))
    if len(uids) == 1:
        import tempfile
        tmpd = tempfile.mkdtemp(prefix="t6_d8_int_")
        root2 = os.path.join(tmpd, "repo")
        shutil.copytree(ROOT, root2, ignore=shutil.ignore_patterns(".git", "__pycache__", "reports", "recordings"))
        doc = list(uids) if isinstance(shipped, list) else {**(shipped or {}), "devices": [{"uid": uids[0], "label": "T6 temporary"}]}
        os.makedirs(os.path.join(root2, "config"), exist_ok=True)
        json.dump(doc, open(os.path.join(root2, "config", "verified_devices.json"), "w"))
        serial_case("A10f D8: allowlisted UID (temporary allowlist copy) via serial: HARDWARE, the only path to it", root2,
                    MSPDevice(variant="INAV", board="MKH7", uid=uid_b), "HARDWARE", True, ["hardware"], f"uid={uids[0]} listed")
        serial_case("A10g D8: non-allowlisted UID with a non-empty allowlist via serial: UNVERIFIED SOURCE", root2,
                    MSPDevice(variant="INAV", board="MKH7", uid=uid_b[:-1] + bytes([uid_b[-1] ^ 1])), "UNVERIFIED SOURCE", False, None, "uid one bit off")
        shutil.rmtree(tmpd, ignore_errors=True)
    else:
        rec("A10f D8: allowlisted UID via serial: HARDWARE", "-", False, f"NOT RUN: bridge reported no single meta.device_identity.uid ({uids!r}); D8 item 1 missing", bp.stderr[-1500:])
        rec("A10g D8: non-allowlisted UID via serial: UNVERIFIED SOURCE", "-", False, "NOT RUN: depends on A10f UID discovery", "")
else:
    rec("A10c D8 serial over virtual pty", "-", False, "NOT RUN: pyserial or openpty unavailable", "")

json.dump(RESULTS, open(os.path.join(OUT, "integration_results.json"), "w"), indent=1)
print(f"TOTAL {sum(r['pass'] for r in RESULTS)}/{len(RESULTS)} passed")
