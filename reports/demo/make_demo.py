#!/usr/bin/env python3
"""Reproducible demo video of the REAL running T5 app (free tools only: headless Chrome + ffmpeg).

    cd /workspace/heading-monitor && python3 reports/demo/make_demo.py

Each scene starts its own `python -m app` on an OS-assigned port (--port 0; the 8080 instance is never touched),
drives headless Chrome over the DevTools protocol (app/tests/_cdp.py, stdlib only), captures viewport frames
in real time, and encodes them with ffmpeg (libx264). A caption overlay is injected into the page on every frame.
Outputs: reports/demo/demo.mp4, reports/demo/*.png, reports/demo/demo_tilted_spin_recording.jsonl,
reports/demo/demo_metrics.json (numbers quoted in captions, all [SIMULATED]).
"""
import base64
import json
import math
import atexit
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from app.tests._cdp import HeadlessPage          # noqa: E402  (stdlib DevTools driver)
from app.tests._helpers import run_app, get_json, post_json  # noqa: E402  (starts app on --port 0)

W, H = 1440, 900
DISCLAIMER = "Simulated data — not hardware-verified. Compass heading only; no position or navigation."
FRAMES = tempfile.mkdtemp(prefix="hm-demo-frames-")
atexit.register(shutil.rmtree, FRAMES, True)   # D10: frames dir removed even if the run fails (Chrome dirs: see _cdp)
frames = []   # (path, output_duration_s)
metrics = {}


def overlay(page, scene):
    js = """(() => {
      let o = document.getElementById('demoOverlay');
      if (!o) {
        o = document.createElement('div'); o.id = 'demoOverlay';
        o.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:99999;background:rgba(5,8,12,.92);' +
          'padding:10px 20px 12px;border-top:3px solid #f59e0b;font-family:system-ui,sans-serif';
        o.innerHTML = '<div id="demoScene" style="color:#e3eaf2;font-size:21px;font-weight:600;margin-bottom:4px"></div>' +
          '<div style="color:#fcd34d;font-size:19px;font-weight:700">' + %s + '</div>';
        document.body.appendChild(o);
      }
      document.getElementById('demoScene').textContent = %s;
      return true; })()""" % (json.dumps(DISCLAIMER), json.dumps(scene))
    page.eval(js)


def goto(page, url, scene):
    page.ws.call("Page.navigate", url=url)
    time.sleep(0.3)
    page.wait_for("window.__hmProbe && window.__hmProbe().records > 0 && window.__hmProbe().renderedSeq > 0 || null")
    overlay(page, scene)


def capture(page, seconds, fps=5.0, speed=1.0):
    """Capture viewport frames for `seconds` of real time; each frame lasts (real gap / speed) in the video."""
    t_end = time.time() + seconds
    last = None
    while time.time() < t_end:
        t = time.time()
        data = page.ws.call("Page.captureScreenshot", format="jpeg", quality=82)["data"]
        p = os.path.join(FRAMES, f"f{len(frames):05d}.jpg")
        with open(p, "wb") as f:
            f.write(base64.b64decode(data))
        if last is not None:
            frames[-1] = (frames[-1][0], (t - last) / speed)
        frames.append((p, 1.0 / fps / speed))
        last = t
        time.sleep(max(0.0, 1.0 / fps - (time.time() - t)))


def png(page, name):
    data = page.ws.call("Page.captureScreenshot", format="png")["data"]
    with open(os.path.join(HERE, name), "wb") as f:
        f.write(base64.b64decode(data))


def mean_abs_sim_error(base, since_seq):
    recs = [r for r in get_json(base + "/api/history")["records"] if r["seq"] > since_seq]
    errs = [abs(r["sim_error_deg"]) for r in recs if r.get("sim_error_deg") is not None]
    return (sum(errs) / len(errs) if errs else None), len(errs)


def last_seq(base):
    r = get_json(base + "/api/history")["records"]
    return r[-1]["seq"] if r else 0


def click(page, el_id):
    page.eval(f"document.getElementById('{el_id}').click(); true")


def scroll(page, el_id=None):
    page.eval("window.scrollTo(0,0); true" if el_id is None else
              f"document.getElementById('{el_id}').scrollIntoView({{block:'center'}}); true")


def main():
    page = HeadlessPage("about:blank", width=W, height=H)
    try:
        # ---- 1. start-up on calibration_dance (uncalibrated)
        with run_app("--source", "sim:calibration_dance", "--seed", "1",
                     wait_for=lambda st: st["counts"]["accepted"] > 5) as (base, _):
            goto(page, base + "/", "1/6  Start-up: python -m app --source sim:calibration_dance  (not yet calibrated)")
            s0 = last_seq(base)
            capture(page, 8)
            png(page, "01_startup_uncalibrated.png")
            before, n_before = mean_abs_sim_error(base, s0)
            metrics["before_cal_mean_abs_err_deg"], metrics["before_cal_n"] = before, n_before

            # ---- 2. calibration wizard
            scroll(page, "panelCalib")
            overlay(page, "2/6  Calibration wizard: collecting samples while the simulated sensor tumbles (time-lapse 4x)")
            click(page, "calStart")
            capture(page, 34, fps=2, speed=4)
            click(page, "calFit")
            t0 = time.time()
            while not get_json(base + "/api/status")["wizard"]["result"] and time.time() - t0 < 10:
                time.sleep(0.2)
            w = get_json(base + "/api/status")["wizard"]
            metrics["fit_backend"], metrics["fit_n_samples"] = w["result_backend"], w["n"]
            metrics["fit_residual_rms_uT"] = w["result"].get("residual_rms_uT") if w["result"] else None
            overlay(page, f"2/6  Fit by heading_core.Calibration.fit ({w['result'].get('method')}), "
                          f"{w['n']} samples. Review, then Apply")
            capture(page, 4)
            png(page, "02_calibration_fit.png")
            click(page, "calApply")
            capture(page, 2)

            # ---- 3. heading after calibration
            scroll(page)
            s1 = last_seq(base)
            overlay(page, "3/6  Calibration applied: heading now uses hard/soft-iron corrected field")
            capture(page, 6)
            after, n_after = mean_abs_sim_error(base, s1)
            metrics["after_cal_mean_abs_err_deg"], metrics["after_cal_n"] = after, n_after
            overlay(page, f"3/6  Mean |heading error| vs sim truth: before {before:.1f}°  →  after {after:.2f}°  "
                          f"(simulated, {n_before}/{n_after} samples)")
            capture(page, 6)
            png(page, "03_after_calibration.png")

        # ---- 4. tilted_spin (+ record JSONL for the replay scene)
        rec_path = os.path.join(HERE, "demo_tilted_spin_recording.jsonl")
        with run_app("--source", "sim:tilted_spin", "--seed", "2",
                     wait_for=lambda st: st["counts"]["accepted"] > 5) as (base, _):
            goto(page, base + "/", "4/6  sim:tilted_spin: roll 20°, pitch −15°, yaw spin; tilt-compensated heading")
            post_json(base + "/api/reference", {"deg": 90})
            name = post_json(base + "/api/record/start", {"format": "jsonl"})[1]["file"]
            capture(page, 12)
            png(page, "04_tilted_spin.png")
            post_json(base + "/api/record/stop", {})
            with urllib.request.urlopen(f"{base}/recordings/{name}") as r, open(rec_path, "wb") as f:
                f.write(r.read())
            os.unlink(os.path.join(ROOT, "app", "recordings", name))
        metrics["recording_lines"] = sum(1 for _ in open(rec_path))

        # ---- 5. motor interference
        with run_app("--source", "sim:motor_interference", "--seed", "3", "--sim-duration", "40",
                     wait_for=lambda st: st["counts"]["accepted"] > 3) as (base, _):
            goto(page, base + "/", "5/6  sim:motor_interference: idle → 8 A → 20 A → pulsing (time-lapse 1.5x)")
            capture(page, 9, speed=1.5)
            overlay(page, "5/6  Simulated motor current distorts the field: FIELD_MAGNITUDE warning, status DEGRADED")
            capture(page, 13, speed=1.5)
            png(page, "05_motor_interference.png")
            st = get_json(base + "/api/status")
            metrics["motor_status"], metrics["motor_reason"] = st["sensor_status"], st["sensor_status_reason"]

        # ---- 6. replay of the recording made in scene 4
        rel = os.path.relpath(rec_path, ROOT)
        with run_app("--source", f"replay:{rel}", wait_for=lambda st: st["counts"]["accepted"] > 3) as (base, _):
            goto(page, base + "/", f"6/6  Replay: --source replay:{rel}  (badge follows sample.source; transport = replay)")
            capture(page, 10)
            png(page, "06_replay.png")
    finally:
        page.close()

    # ---- encode
    lst = os.path.join(FRAMES, "list.txt")
    with open(lst, "w") as f:
        for p, d in frames:
            f.write(f"file '{p}'\nduration {d:.4f}\n")
        f.write(f"file '{frames[-1][0]}'\n")
    out = os.path.join(HERE, "demo.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-vf", f"fps=25,scale={W}:{H},format=yuv420p", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "26", "-movflags", "+faststart", out], check=True)
    metrics["frames_captured"] = len(frames)
    with open(os.path.join(HERE, "demo_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    shutil.rmtree(FRAMES, ignore_errors=True)
    print(json.dumps(metrics, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    main()
