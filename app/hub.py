"""Central state: receives Samples, runs heading_core (via adapter), keeps history,
calibration wizard, recordings and reference heading. Thread-safe."""
from __future__ import annotations

import collections
import functools
import csv
import datetime as dt
import io
import json
import math
import os
import re
import statistics
import threading
import time

from .core_adapter import CoreAdapter
from .provenance import apply_serial_provenance, load_verified_devices
from .sources import gps_status, parse_gps, validate_sample
from ._stubs import angle_diff_deg, wrap360

APP_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDINGS_DIR = os.path.join(APP_DIR, "recordings")
CALIBRATIONS_DIR = os.path.join(APP_DIR, "calibrations")
STALE_AFTER_S = 2.0
HISTORY_LEN = 6000
DEGRADING_WARNINGS = {"FIELD_MAGNITUDE_OUT_OF_RANGE", "TILT_TOO_LARGE", "DIP_ANGLE_ANOMALY",
                      "HIGH_NOISE"}
GPS_NOTE = ("GPS availability comes only from the optional sample.gps object (fix, satellites, HDOP). "
            "Absent or unknown fix is shown as Unknown. No coordinates are used, and nothing is inferred from heading.")

CSV_COLUMNS = ["recv_time_iso", "t", "source", "heading_deg", "heading_raw_deg", "reference_deg",
               "deviation_deg", "roll_deg", "pitch_deg", "bx_uT", "by_uT", "bz_uT",
               "field_raw_uT", "field_cal_uT", "calibrated", "quality", "noise_1sigma_deg",
               "warnings", "sensor_status", "estimator_backend", "truth_heading_deg_sim_only",
               "gps_status", "gps_fix", "gps_num_sat", "gps_hdop", "mag_raw_x", "mag_raw_y", "mag_raw_z",
               "original_source", "transport", "device_status", "device_verified",
               "device_board_reported", "device_variant_reported", "device_uid_reported"]


def _iso(ms: float) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).isoformat(timespec="milliseconds")


def _num(v, nd=3):
    return "" if v is None else (round(v, nd) if isinstance(v, float) else v)


def record_to_row(r: dict) -> list:
    """CSV row. Empty cell = unknown / not reported. gps_status is available|unavailable|unknown."""
    mag = r.get("mag_uT") or [None] * 3
    raw = r.get("mag_raw") if isinstance(r.get("mag_raw"), list) else ["", "", ""]   # optional
    return [r["recv_time_iso"], r.get("t"), r.get("source"), _num(r.get("heading_deg")),
            _num(r.get("heading_raw_deg")), _num(r.get("reference_deg")),
            _num(r.get("deviation_deg")), _num(r.get("roll_deg")), _num(r.get("pitch_deg")),
            _num(mag[0], 4), _num(mag[1], 4), _num(mag[2], 4), _num(r.get("field_raw_uT")),
            _num(r.get("field_uT")), "" if r.get("calibrated") is None else str(r["calibrated"]).lower(),
            _num(r.get("quality")), _num(r.get("noise_1sigma_deg")),
            ";".join(r.get("warnings") or []), r.get("sensor_status", ""), r.get("estimator_backend", ""),
            _num(r.get("truth_heading_deg")), r.get("gps_status", "unknown"),
            r.get("gps_fix") or "", _num(r.get("gps_num_sat")), _num(r.get("gps_hdop")), *raw,
            r.get("original_source") or "", r.get("transport") or "", r.get("device_status") or "",
            "" if r.get("device_status") is None else str(bool(r.get("device_verified"))).lower(),
            r.get("device_board") or "", r.get("device_variant") or "", r.get("device_uid") or ""]


def safe_name(name: str, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_.-]", "_", (name or "").strip())[:60].strip(".") or "unnamed"
    return base if base.endswith(ext) else base + ext


class Hub:
    def __init__(self, source_spec: str, declination_deg: float = 0.0, stale_after_s: float = STALE_AFTER_S,
                 verified_devices_path: str | None = None):
        self.lock = threading.RLock()
        self.stale_after_s = float(stale_after_s)
        self.source_spec = source_spec
        self.transport = source_spec.split(":")[0]
        # D8 hardening: the ONLY trusted channel is this callable, handed to the app's own SerialSource by __main__.
        # Anything else that calls emit() (POST /api/sample, tests, other code) is untrusted and can never verify.
        self._serial_token = object()
        self.source_emit = functools.partial(self.emit, _channel=self._serial_token)
        self.verified_uids, self.verified_info = load_verified_devices(verified_devices_path)
        self.core = CoreAdapter(declination_deg)
        self.history = collections.deque(maxlen=HISTORY_LEN)
        self.seq = 0
        self.latest = None
        self.last_recv_mono = None
        self.recv_times = collections.deque(maxlen=400)
        self.headings = collections.deque(maxlen=40)
        self.counts = {"received": 0, "accepted": 0, "invalid": 0, "dropped_by_test_control": 0,
                       "gps_invalid": 0}
        self.last_error = None
        self.source_status = {"transport": source_spec.split(":")[0], "state": "starting"}
        self.reference_deg = None
        self.paused = False
        self.dropout_until = 0.0
        self.wizard = {"collecting": False, "samples": [], "target": 300, "bins": set(),
                       "octants": set(), "result": None, "result_backend": None, "error": None}
        self.recorder = None
        self.listeners = []

    # ------------------------------------------------------------ intake
    def on_source_status(self, st: dict):
        with self.lock:
            self.source_status = st

    def emit(self, sample, error=None, _channel=None):
        """Called by sources (and POST /api/sample). Returns error text or None.
        Verification (device_verified / live_hardware) is computed HERE, never read from the sample: any
        sample-supplied live_hardware, device_verified or meta.provenance claim is ignored unless the sample came
        through self.source_emit on a serial hub AND its reported UID is in this app's own allowlist."""
        with self.lock:
            self.counts["received"] += 1
            if error:
                self.counts["invalid"] += 1
                self.last_error = error
                return error
            err = validate_sample(sample)
            if err:
                self.counts["invalid"] += 1
                self.last_error = f"invalid sample: {err}"
                return err
            device = None
            if self.transport == "serial":          # D8: serial is not proof of hardware
                sample, device = apply_serial_provenance(sample, self.verified_uids)
                if _channel is not self._serial_token and device.get("verified"):
                    device = dict(device, verified=False, status="untrusted_channel")
            now = time.monotonic()
            if self.paused or now < self.dropout_until:
                self.counts["dropped_by_test_control"] += 1
                return None
            est, backend, est_err = self.core.update(sample)
            rec = self._make_record(sample, est, backend, est_err, device)
            self.counts["accepted"] += 1
            self.last_recv_mono = now
            self.recv_times.append(now)
            self.latest = rec
            self.history.append(rec)
            if self.wizard["collecting"]:
                self._wizard_add(sample["mag_uT"])
            if self.recorder:
                self.recorder.write(rec, sample)
            for fn in self.listeners:
                fn(rec)
            return None

    def _noise_estimate(self):
        """Short-term heading noise (1 sigma): std of 2nd differences / sqrt(6), which removes
        a constant rotation rate. Precision only -- NOT absolute accuracy."""
        h = list(self.headings)
        if len(h) < 10:
            return None
        un = [h[0]]
        for v in h[1:]:
            un.append(un[-1] + angle_diff_deg(v, un[-1] % 360))
        d2 = [un[i + 1] - 2 * un[i] + un[i - 1] for i in range(1, len(un) - 1)]
        return statistics.pstdev(d2) / math.sqrt(6)

    def _make_record(self, s, est, backend, est_err, device=None):
        self.seq += 1
        ms = time.time() * 1000
        mag = s["mag_uT"]
        r = {"seq": self.seq, "recv_ms": ms, "recv_time_iso": _iso(ms), "t": s["t"],
             "source": s["source"], "mag_uT": mag, "accel_g": s.get("accel_g"),
             "mag_raw": s.get("mag_raw"), "rm3100_cycle_count": s.get("rm3100_cycle_count"),
             "field_raw_uT": math.sqrt(sum(v * v for v in mag)),
             "estimator_backend": backend, "error": est_err,
             "truth_heading_deg": (s.get("truth") or {}).get("heading_deg") if s["source"] == "sim" else None,
             "gps_status": "unknown", "gps_fix": None, "gps_num_sat": None, "gps_hdop": None}
        # D6: provenance for the badge/banner. original_source is copied from meta (never inferred);
        # transport is how this process received the sample (sim | replay | serial | ingest).
        meta = s.get("meta") if isinstance(s.get("meta"), dict) else {}
        orig = meta.get("original_source")
        r["original_source"] = orig if isinstance(orig, str) else None
        r["transport"] = self.source_spec.split(":")[0]
        dev = device or {}
        r["device_status"] = dev.get("status")            # serial only: verified|uid_not_listed|no_uid|no_identity|simulator
        r["device_verified"] = bool(dev.get("verified"))
        r["device_board"], r["device_variant"], r["device_uid"] = dev.get("board"), dev.get("variant"), dev.get("uid")
        r["device_target"] = dev.get("target")
        r["live_hardware"] = s["source"] == "hardware" and r["transport"] == "serial" and r["device_verified"]
        gps, gps_err = parse_gps(s.get("gps"))
        if gps_err:
            r["gps_error"] = gps_err
            self.counts["gps_invalid"] = self.counts.get("gps_invalid", 0) + 1
            self.last_error = f"invalid gps object ignored (GPS shown as Unknown): {gps_err}"
        elif gps:
            r.update(gps_status=gps_status(gps), gps_fix=gps.get("fix"), gps_num_sat=gps.get("num_sat"),
                     gps_hdop=gps.get("hdop"))
        if est:
            for k in ("heading_deg", "heading_raw_deg", "roll_deg", "pitch_deg", "field_uT",
                      "calibrated", "quality", "warnings"):
                r[k] = est.get(k)
            if est.get("source") not in (None, s["source"]):
                r["error"] = f"estimate source {est.get('source')!r} != sample source {s['source']!r}"
            h = r.get("heading_deg")
            if isinstance(h, (int, float)) and math.isfinite(h):
                self.headings.append(wrap360(h))
                r["noise_1sigma_deg"] = self._noise_estimate()
                if self.reference_deg is not None:
                    r["reference_deg"] = self.reference_deg
                    r["deviation_deg"] = angle_diff_deg(h, self.reference_deg)
                if r["truth_heading_deg"] is not None:
                    r["sim_error_deg"] = angle_diff_deg(h, r["truth_heading_deg"])
            else:
                r["heading_deg"] = None
        if r.get("reference_deg") is None:
            r["reference_deg"] = self.reference_deg
        r["sensor_status"] = self._status_for(r)
        return r

    @staticmethod
    def _status_for(r):
        if r.get("error") or r.get("heading_deg") is None:
            return "FAULT"
        if DEGRADING_WARNINGS & set(r.get("warnings") or []):
            return "DEGRADED"
        return "OK"

    # ------------------------------------------------------------ controls
    def set_reference(self, deg):
        with self.lock:
            self.reference_deg = None if deg is None else wrap360(float(deg))

    def set_paused(self, paused: bool):
        with self.lock:
            self.paused = bool(paused)

    def inject_dropout(self, seconds: float):
        with self.lock:
            self.dropout_until = time.monotonic() + max(0.0, min(float(seconds), 60.0))

    # ------------------------------------------------------------ calibration wizard
    def _wizard_add(self, mag):
        w = self.wizard
        w["samples"].append(list(mag))
        w["bins"].add(int(wrap360(math.degrees(math.atan2(-mag[1], mag[0]))) // 30))
        w["octants"].add(tuple(v >= 0 for v in mag))
        if len(w["samples"]) >= 5000:
            w["collecting"] = False

    def wizard_start(self, target=300):
        with self.lock:
            self.wizard.update(collecting=True, samples=[], bins=set(), octants=set(),
                               result=None, result_backend=None, error=None,
                               target=int(max(20, min(target, 5000))))

    def wizard_stop(self):
        with self.lock:
            self.wizard["collecting"] = False

    def wizard_fit(self):
        with self.lock:
            samples = list(self.wizard["samples"])
            self.wizard["collecting"] = False
        try:
            d, backend = self.core.fit(samples)
            with self.lock:
                self.wizard.update(result=d, result_backend=backend, error=None)
            return d, backend, None
        except Exception as e:
            with self.lock:
                self.wizard.update(result=None, result_backend=None, error=f"{type(e).__name__}: {e}")
            return None, None, self.wizard["error"]

    def apply_calibration(self, d, backend):
        self.core.set_calibration(d, backend)

    def wizard_status(self):
        w = self.wizard
        return {"collecting": w["collecting"], "n": len(w["samples"]), "target": w["target"],
                "heading_bins_covered": len(w["bins"]), "heading_bins_total": 12,
                "octants_covered": len(w["octants"]), "octants_total": 8,
                "result": w["result"], "result_backend": w["result_backend"], "error": w["error"]}

    def save_calibration(self, name):
        if self.core.cal_dict is None:
            raise ValueError("no calibration is active")
        os.makedirs(CALIBRATIONS_DIR, exist_ok=True)
        fn = safe_name(name, ".json")
        doc = {"calibration": self.core.cal_dict, "fit_backend": self.core.cal_backend,
               "saved_at": _iso(time.time() * 1000), "app": "heading-monitor T5"}
        with open(os.path.join(CALIBRATIONS_DIR, fn), "w") as f:
            json.dump(doc, f, indent=2)
        return fn

    def load_calibration(self, name=None, doc=None):
        if name:
            with open(os.path.join(CALIBRATIONS_DIR, safe_name(name, ".json"))) as f:
                doc = json.load(f)
        if not isinstance(doc, dict):
            raise ValueError("calibration JSON must be an object")
        cal = doc.get("calibration", doc)
        if not isinstance(cal, dict) or not ({"offset", "offset_uT"} & set(cal)):
            raise ValueError("calibration JSON needs an 'offset_uT' (or 'offset') field")
        self.apply_calibration(cal, doc.get("fit_backend", "loaded-file"))

    @staticmethod
    def list_calibrations():
        if not os.path.isdir(CALIBRATIONS_DIR):
            return []
        return sorted(f for f in os.listdir(CALIBRATIONS_DIR) if f.endswith(".json"))

    # ------------------------------------------------------------ recording
    def start_recording(self, fmt):
        with self.lock:
            if self.recorder:
                self.recorder.close()
            self.recorder = Recorder(fmt)
            return self.recorder.name

    def stop_recording(self):
        with self.lock:
            if not self.recorder:
                return None
            name = self.recorder.name
            self.recorder.close()
            self.recorder = None
            return name

    @staticmethod
    def list_recordings():
        if not os.path.isdir(RECORDINGS_DIR):
            return []
        out = []
        for f in sorted(os.listdir(RECORDINGS_DIR)):
            if f.endswith((".csv", ".jsonl")):
                out.append({"name": f, "bytes": os.path.getsize(os.path.join(RECORDINGS_DIR, f))})
        return out

    # ------------------------------------------------------------ outputs
    def history_csv(self) -> str:
        with self.lock:
            rows = list(self.history)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(CSV_COLUMNS)
        for r in rows:
            w.writerow(record_to_row(r))
        return buf.getvalue()

    def history_since(self, seq=0, limit=2000):
        with self.lock:
            return [r for r in self.history if r["seq"] > seq][-limit:]

    def _gps_status(self, age):
        r = self.latest
        if r is None or age is None or age > self.stale_after_s:
            return {"status": "unknown", "fix": None, "num_sat": None, "hdop": None, "note": GPS_NOTE}
        return {"status": r["gps_status"], "fix": r.get("gps_fix"), "num_sat": r.get("gps_num_sat"),
                "hdop": r.get("gps_hdop"), "error": r.get("gps_error"), "note": GPS_NOTE}

    def status(self):
        with self.lock:
            now = time.monotonic()
            age = None if self.last_recv_mono is None else now - self.last_recv_mono
            rate = len([t for t in self.recv_times if now - t <= 2.0]) / 2.0
            src_state = self.source_status.get("state")
            if self.latest is None:
                sensor, why = "NO DATA", "no valid sample received yet"
                if src_state == "fault":
                    sensor, why = "FAULT", self.source_status.get("detail", "")
            elif age > self.stale_after_s:
                sensor, why = "STALE", f"no sample for {age:.1f} s (timeout {self.stale_after_s} s)"
                if src_state == "fault":
                    sensor, why = "FAULT", self.source_status.get("detail", "")
            else:
                sensor = self.latest["sensor_status"]
                why = self.latest.get("error") or ", ".join(
                    w for w in (self.latest.get("warnings") or []) if w in DEGRADING_WARNINGS) or ""
            return {
                "server_time_ms": time.time() * 1000,
                "source_spec": self.source_spec,
                "source_status": self.source_status,
                "verified_devices": dict(self.verified_info),
                "latest_sample_source": self.latest["source"] if self.latest else None,
                "last_sample_age_s": age,
                "stale_after_s": self.stale_after_s,
                "rate_hz": rate,
                "sensor_status": sensor,
                "sensor_status_reason": why,
                "core": self.core.info(),
                "calibration": {"active": self.core.cal_dict is not None,
                                "backend": self.core.cal_backend, "params": self.core.cal_dict},
                "wizard": self.wizard_status(),
                "recording": self.recorder.info() if self.recorder else None,
                "reference_deg": self.reference_deg,
                "paused": self.paused,
                "dropout_remaining_s": max(0.0, self.dropout_until - now),
                "counts": dict(self.counts),
                "last_error": self.last_error,
                "gps": self._gps_status(age),
            }


class Recorder:
    def __init__(self, fmt):
        if fmt not in ("csv", "jsonl"):
            raise ValueError("format must be csv or jsonl")
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.fmt = fmt
        self.name = f"rec-{stamp}.{fmt}"
        self.path = os.path.join(RECORDINGS_DIR, self.name)
        self.f = open(self.path, "w", newline="", encoding="utf-8")
        self.n = 0
        self.started = time.time()
        if fmt == "csv":
            self.w = csv.writer(self.f)
            self.w.writerow(CSV_COLUMNS)

    def write(self, rec, sample):
        if self.fmt == "csv":
            self.w.writerow(record_to_row(rec))
        else:  # JSONL of the ORIGINAL contract Samples -> directly replayable with --source replay:
            self.f.write(json.dumps(sample, separators=(",", ":")) + "\n")
        self.n += 1
        if self.n % 50 == 0:
            self.f.flush()

    def close(self):
        self.f.close()

    def info(self):
        return {"name": self.name, "format": self.fmt, "samples": self.n,
                "elapsed_s": time.time() - self.started}
