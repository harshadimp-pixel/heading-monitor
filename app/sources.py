"""Sample sources. Every source yields contract Samples (contracts/sample.schema.json).

  sim[:scenario]   -> `python -m sim --rate R --duration D --scenario S` (T3) if implemented,
                      otherwise app._stubs.StubSim (clearly labelled, source="sim").
  replay:<file>    -> reads a Sample JSONL file, paced by sample `t`.
  serial:<port>    -> `python -m firmware_bridge --port P --baud B` (T4). Never stubbed:
                      if the bridge is unavailable the app shows NO DATA / fault.
  ingest           -> samples POSTed to /api/sample (for external tools / tests).

The data-source badge is taken from each sample's own `source` field, never from here.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import math
import os
import subprocess
import sys
import threading
import time

from . import _stubs

log = logging.getLogger("app.sources")
VALID_SOURCES = ("sim", "replay", "hardware")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def validate_sample(s) -> str | None:
    """Minimal check of the Sample contract's required fields. Returns error text or None."""
    if not isinstance(s, dict):
        return "sample is not a JSON object"
    for k in ("t", "source", "mag_uT"):
        if k not in s:
            return f"missing required field {k!r}"
    if s["source"] not in VALID_SOURCES:
        return f"source must be one of {VALID_SOURCES}"
    if not isinstance(s["t"], (int, float)) or isinstance(s["t"], bool):
        return "t must be a number"
    for k in ("mag_uT", "accel_g", "gyro_dps"):
        if k in s:
            v = s[k]
            if (not isinstance(v, list) or len(v) != 3
                    or not all(isinstance(x, (int, float)) and not isinstance(x, bool)
                               and math.isfinite(x) for x in v)):
                return f"{k} must be 3 finite numbers"
    if "mag_raw" in s and s["mag_raw"] is not None:   # OPTIONAL: absent on CAN-L4-3100 / DroneCAN streams
        v = s["mag_raw"]
        if not isinstance(v, list) or len(v) != 3 or not all(isinstance(x, int) and not isinstance(x, bool) for x in v):
            return "mag_raw, when present, must be 3 integers"
    return None


GPS_FIX_VALUES = ("none", "2d", "3d", "unknown")


def parse_gps(g):
    """Optional `gps` object {fix, num_sat, hdop} (availability only, no coordinates).
    Returns (gps_dict_or_None, error_or_None). An invalid gps object never invalidates the
    heading sample: the caller treats GPS as Unknown and reports the error."""
    if g is None:
        return None, None
    if not isinstance(g, dict):
        return None, "gps must be an object"
    out = {}
    fix = g.get("fix")
    if fix is not None:
        if fix not in GPS_FIX_VALUES:
            return None, f"gps.fix must be one of {GPS_FIX_VALUES}"
        out["fix"] = fix
    ns = g.get("num_sat")
    if ns is not None:
        if not isinstance(ns, int) or isinstance(ns, bool) or ns < 0:
            return None, "gps.num_sat must be a non-negative integer"
        out["num_sat"] = ns
    hd = g.get("hdop")
    if hd is not None:
        if not isinstance(hd, (int, float)) or isinstance(hd, bool) or not math.isfinite(hd) or hd < 0:
            return None, "gps.hdop must be a finite non-negative number"
        out["hdop"] = float(hd)
    return out, None


def gps_status(gps):
    """available (2d/3d fix) / unavailable (fix none) / unknown (absent, invalid or fix unknown)."""
    fix = (gps or {}).get("fix")
    return "available" if fix in ("2d", "3d") else "unavailable" if fix == "none" else "unknown"


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name + ".__main__") is not None
    except (ImportError, ValueError):
        return False


def relabel_replayed_sample(sample, path):
    """D6 (ARCHITECTURE.md, PM 2026-11-27): a replayed sample labelled source "hardware" is never presented as live.
    Same field semantics as firmware_bridge --replay (bridge._replay_jsonl): source -> "replay",
    meta.original_source = the original label, meta.replayed_from = the file. Unlike the bridge, only "hardware"
    is relabelled here: a replayed sim log keeps source "sim" (SIMULATED is the more conservative label, per the
    same decision). The bridge's Python helper is not part of the ARCHITECTURE interfaces (CLI only), so the
    three field assignments are mirrored rather than imported."""
    if not isinstance(sample, dict) or sample.get("source") != "hardware":
        return sample
    s = dict(sample)
    meta = dict(s.get("meta") or {}) if isinstance(s.get("meta"), dict) else {}
    meta["original_source"] = "hardware"
    meta["replayed_from"] = path
    s["meta"] = meta
    s["source"] = "replay"
    return s


class Source:
    kind = "?"

    def __init__(self, emit, on_status):
        self.emit = emit            # emit(sample_dict) or emit(None, error=str)
        self.on_status = on_status  # on_status(dict) -> merged into source status
        self.stop_event = threading.Event()
        self.thread = None
        self.status = {"transport": self.kind, "state": "starting", "backend": None, "detail": ""}

    def set_status(self, **kw):
        self.status.update(kw)
        self.on_status(dict(self.status))

    def start(self):
        self.thread = threading.Thread(target=self._run_safe, daemon=True, name=f"source-{self.kind}")
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _run_safe(self):
        try:
            self.run()
        except Exception as e:  # pragma: no cover
            log.exception("source crashed")
            self.set_status(state="fault", detail=f"{type(e).__name__}: {e}")

    def run(self):
        raise NotImplementedError

    # ---- shared JSONL reader with pacing by sample t
    def _pump_lines(self, lines, pace=True, speed=1.0, transform=None):
        t_first = wall_first = None
        n = 0
        for line in lines:
            if self.stop_event.is_set():
                break
            line = line.strip()
            if not line:
                continue
            try:
                s = json.loads(line)
            except json.JSONDecodeError as e:
                self.emit(None, error=f"invalid JSON line: {e}")
                continue
            if pace and isinstance(s, dict) and isinstance(s.get("t"), (int, float)):
                if t_first is None:
                    t_first, wall_first = s["t"], time.monotonic()
                delay = wall_first + (s["t"] - t_first) / speed - time.monotonic()
                if delay > 0:
                    if self.stop_event.wait(min(delay, 5.0)):
                        break
            self.emit(transform(s) if transform else s)
            n += 1
        return n


class StubSimSource(Source):
    kind = "sim"

    def __init__(self, emit, on_status, scenario, rate, seed, reason=""):
        super().__init__(emit, on_status)
        self.sim = _stubs.StubSim(scenario=scenario, rate=rate, seed=seed)
        self.reason = reason

    def run(self):
        self.set_status(state="running", backend="STUB (app._stubs.StubSim)",
                        detail=f"scenario={self.sim.scenario}. {self.reason}".strip())
        for s in self.sim.run(self.stop_event):
            self.emit(s)
        self.set_status(state="stopped")


class SubprocessSource(Source):
    def __init__(self, emit, on_status, cmd, backend, pace):
        super().__init__(emit, on_status)
        self.cmd, self.backend, self.pace = cmd, backend, pace
        self.proc = None
        self.stderr_tail = []

    def _drain_stderr(self):
        for line in self.proc.stderr:
            self.stderr_tail = (self.stderr_tail + [line.rstrip()])[-20:]

    def run_process(self):
        self.set_status(state="running", backend=self.backend, detail=" ".join(self.cmd))
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        self.proc = subprocess.Popen(self.cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        n = self._pump_lines(self.proc.stdout, pace=self.pace)
        if self.stop_event.is_set():
            self.proc.terminate()
        rc = self.proc.wait()
        return n, rc

    def stop(self):
        super().stop()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


class RealSimSource(SubprocessSource):
    kind = "sim"

    def __init__(self, emit, on_status, scenario, rate, seed, fallback_factory, duration=86400.0):
        cmd = [sys.executable, "-m", "sim", "--rate", str(rate), "--duration", str(duration), "--realtime"]
        if scenario:
            cmd += ["--scenario", scenario]
        if seed is not None:
            cmd += ["--seed", str(seed)]
        super().__init__(emit, on_status, cmd, "sim (T3, real module)", pace=True)
        self.fallback_factory = fallback_factory

    def run(self):
        n, rc = self.run_process()
        if self.stop_event.is_set():
            return
        tail = "\n".join(self.stderr_tail)
        if n == 0 and "NotImplementedError" in tail:
            log.warning("sim module not implemented yet; falling back to stub")
            fb = self.fallback_factory("T3 sim present but raised NotImplementedError")
            fb.stop_event = self.stop_event
            fb.run()
            return
        self.set_status(state="fault" if rc else "ended",
                        detail=f"sim exited rc={rc} after {n} samples. {tail[-400:]}")


class SerialSource(SubprocessSource):
    kind = "serial"

    def __init__(self, emit, on_status, port, baud):
        cmd = [sys.executable, "-m", "firmware_bridge", "--port", port, "--baud", str(baud)]
        super().__init__(emit, on_status, cmd, "firmware_bridge (T4)", pace=False)
        self.port = port

    def run(self):
        if not _module_available("firmware_bridge"):
            self.set_status(state="fault", backend=None,
                            detail="firmware_bridge (T4) is not available yet; no hardware data. "
                                   "Hardware is never simulated by the app.")
            return
        n, rc = self.run_process()
        if not self.stop_event.is_set():
            self.set_status(state="fault" if rc else "ended",
                            detail=f"firmware_bridge exited rc={rc} after {n} samples. "
                                   + "\n".join(self.stderr_tail)[-400:])


class ReplaySource(Source):
    kind = "replay"

    def __init__(self, emit, on_status, path, speed=1.0, loop=False):
        super().__init__(emit, on_status)
        self.path, self.speed, self.loop = path, speed, loop

    def run(self):
        if not os.path.isfile(self.path):
            self.set_status(state="fault", detail=f"file not found: {self.path}")
            return
        self.set_status(state="running", backend="app file reader", detail=self.path)
        while not self.stop_event.is_set():
            with open(self.path, encoding="utf-8") as f:
                self._pump_lines(f, pace=True, speed=self.speed,
                                 transform=lambda x: relabel_replayed_sample(x, self.path))
            if not self.loop:
                break
        if not self.stop_event.is_set():
            self.set_status(state="ended", detail=f"end of file: {self.path}")


class IngestSource(Source):
    kind = "ingest"

    def run(self):
        self.set_status(state="waiting", backend="HTTP POST /api/sample",
                        detail="waiting for samples POSTed to /api/sample")


def make_source(spec: str, emit, on_status, rate=20.0, seed=None, baud=115200,
                speed=1.0, loop=False, sim_duration=86400.0) -> Source:
    kind, _, arg = spec.partition(":")
    if kind == "sim":
        scenario = arg or None

        def stub(reason):
            return StubSimSource(emit, on_status, scenario or "slow_yaw_spin", rate, seed, reason)
        if _module_available("sim"):
            return RealSimSource(emit, on_status, scenario, rate, seed, stub, duration=sim_duration)
        return stub("T3 sim module not available yet.")
    if kind == "replay":
        if not arg:
            raise ValueError("replay needs a file: replay:<file>")
        return ReplaySource(emit, on_status, arg, speed=speed, loop=loop)
    if kind == "serial":
        if not arg:
            raise ValueError("serial needs a port: serial:<port>")
        return SerialSource(emit, on_status, arg, baud)
    if kind == "ingest":
        return IngestSource(emit, on_status)
    raise ValueError(f"unknown source {spec!r}; use sim[:scenario] | replay:<file> | serial:<port> | ingest")
