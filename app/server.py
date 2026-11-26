"""Standard-library HTTP server + minimal RFC 6455 WebSocket (server->client push).

Routes (JSON unless noted):
  GET  /                      UI (static/)
  GET  /ws                    WebSocket: {"type":"hello"|"update", "status":..., "records":[...]}
  GET  /api/status            current status
  GET  /api/history?since=N   recent records (max 2000)
  GET  /api/export.csv        history ring buffer as CSV (text/csv)
  POST /api/sample            ingest one contract Sample (only with --source ingest)
  POST /api/reference         {"deg": number|null}
  POST /api/control           {"paused": bool} | {"dropout_s": number}   (TEST controls)
  POST /api/calib/start|stop|fit|apply|clear|save|load ; GET /api/calib/list, /api/calib/current
  POST /api/record/start {"format":"csv"|"jsonl"}, /api/record/stop ; GET /api/recordings
  GET  /recordings/<name>     download a recording
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import mimetypes
import os
import queue
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .hub import Hub, RECORDINGS_DIR, safe_name

log = logging.getLogger("app.server")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"  # RFC 6455 section 1.3


def ws_frame(payload: bytes, opcode=0x1) -> bytes:
    n = len(payload)
    if n < 126:
        hdr = struct.pack("!BB", 0x80 | opcode, n)
    elif n < 65536:
        hdr = struct.pack("!BBH", 0x80 | opcode, 126, n)
    else:
        hdr = struct.pack("!BBQ", 0x80 | opcode, 127, n)
    return hdr + payload


class Broadcaster:
    """Pushes batched new records + status to every WebSocket client at ~10 Hz."""

    def __init__(self, hub: Hub, period=0.1):
        self.hub, self.period = hub, period
        self.clients: set[queue.Queue] = set()
        self.lock = threading.Lock()
        self.pending = []
        hub.listeners.append(self._on_record)
        threading.Thread(target=self._loop, daemon=True, name="broadcaster").start()

    def _on_record(self, rec):
        self.pending.append(rec)

    def add(self):
        q = queue.Queue(maxsize=100)
        with self.lock:
            self.clients.add(q)
        return q

    def remove(self, q):
        with self.lock:
            self.clients.discard(q)

    def _loop(self):
        while True:
            time.sleep(self.period)
            with self.hub.lock:
                recs, self.pending = self.pending, []
                status = self.hub.status()
            msg = json.dumps({"type": "update", "status": status, "records": recs},
                             separators=(",", ":"), allow_nan=False, default=str).encode()
            with self.lock:
                for q in list(self.clients):
                    try:
                        q.put_nowait(msg)
                    except queue.Full:  # slow client: drop it
                        self.clients.discard(q)


def make_handler(hub: Hub, bc: Broadcaster):
    class Handler(BaseHTTPRequestHandler):
        server_version = "HeadingMonitor/0.1"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            log.debug("%s %s", self.address_string(), fmt % args)

        # ------------------------------------------------ helpers
        def _send(self, code, body: bytes, ctype="application/json", extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, allow_nan=False, default=str).encode())

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > 2_000_000:
                raise ValueError("body too large")
            raw = self.rfile.read(n) if n else b"{}"
            return json.loads(raw or b"{}")

        # ------------------------------------------------ GET
        def do_GET(self):
            u = urlparse(self.path)
            p = u.path
            try:
                if p == "/ws":
                    return self._websocket()
                if p == "/api/status":
                    return self._json(hub.status())
                if p == "/api/history":
                    since = int(parse_qs(u.query).get("since", ["0"])[0])
                    return self._json({"records": hub.history_since(since)})
                if p == "/api/export.csv":
                    fn = time.strftime("heading-history-%Y%m%d-%H%M%S.csv")
                    return self._send(200, hub.history_csv().encode(), "text/csv; charset=utf-8",
                                      {"Content-Disposition": f'attachment; filename="{fn}"'})
                if p == "/api/calib/list":
                    return self._json({"files": hub.list_calibrations()})
                if p == "/api/calib/current":
                    if hub.core.cal_dict is None:
                        return self._json({"error": "no calibration active"}, 404)
                    body = json.dumps({"calibration": hub.core.cal_dict,
                                       "fit_backend": hub.core.cal_backend}, indent=2).encode()
                    return self._send(200, body, "application/json",
                                      {"Content-Disposition": 'attachment; filename="calibration.json"'})
                if p == "/api/recordings":
                    return self._json({"files": hub.list_recordings()})
                if p.startswith("/recordings/"):
                    name = os.path.basename(p)
                    path = os.path.join(RECORDINGS_DIR, name)
                    if name and os.path.isfile(path):
                        with open(path, "rb") as f:
                            return self._send(200, f.read(), "text/plain; charset=utf-8",
                                              {"Content-Disposition": f'attachment; filename="{name}"'})
                    return self._json({"error": "not found"}, 404)
                return self._static(p)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _static(self, p):
            rel = "index.html" if p in ("/", "") else p.lstrip("/")
            path = os.path.realpath(os.path.join(STATIC_DIR, rel))
            if not path.startswith(os.path.realpath(STATIC_DIR) + os.sep) or not os.path.isfile(path):
                return self._json({"error": "not found"}, 404)
            ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            with open(path, "rb") as f:
                self._send(200, f.read(), ctype)

        # ------------------------------------------------ POST
        def do_POST(self):
            p = urlparse(self.path).path
            try:
                body = self._body()
            except (ValueError, json.JSONDecodeError) as e:
                return self._json({"ok": False, "error": f"bad JSON: {e}"}, 400)
            try:
                return self._post(p, body)
            except (ValueError, KeyError, TypeError, FileNotFoundError) as e:
                return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 400)

        def _post(self, p, b):
            if p == "/api/sample":
                if not hub.source_spec.startswith("ingest"):
                    return self._json({"ok": False, "error": "POST /api/sample is only accepted when "
                                       "the app runs with --source ingest"}, 409)
                items = b if isinstance(b, list) else [b]
                errs = [e for e in (hub.emit(s) for s in items) if e]
                return self._json({"ok": not errs, "accepted": len(items) - len(errs), "errors": errs},
                                  200 if not errs else 422)
            if p == "/api/reference":
                deg = b.get("deg")
                if deg is not None and not isinstance(deg, (int, float)):
                    raise ValueError("deg must be a number or null")
                hub.set_reference(deg)
                return self._json({"ok": True, "reference_deg": hub.reference_deg})
            if p == "/api/control":
                if "paused" in b:
                    hub.set_paused(b["paused"])
                if "dropout_s" in b:
                    hub.inject_dropout(b["dropout_s"])
                return self._json({"ok": True})
            if p == "/api/calib/start":
                hub.wizard_start(int(b.get("target", 300)))
                return self._json({"ok": True})
            if p == "/api/calib/stop":
                hub.wizard_stop()
                return self._json({"ok": True})
            if p == "/api/calib/fit":
                d, backend, err = hub.wizard_fit()
                return self._json({"ok": err is None, "calibration": d, "backend": backend, "error": err},
                                  200 if err is None else 422)
            if p == "/api/calib/apply":
                w = hub.wizard
                if not w["result"]:
                    raise ValueError("no fitted calibration to apply")
                hub.apply_calibration(w["result"], w["result_backend"])
                return self._json({"ok": True})
            if p == "/api/calib/clear":
                hub.apply_calibration(None, None)
                return self._json({"ok": True})
            if p == "/api/calib/save":
                return self._json({"ok": True, "file": hub.save_calibration(b.get("name", "calibration"))})
            if p == "/api/calib/load":
                hub.load_calibration(name=b.get("name"), doc=b.get("doc"))
                return self._json({"ok": True})
            if p == "/api/record/start":
                return self._json({"ok": True, "file": hub.start_recording(b.get("format", "csv"))})
            if p == "/api/record/stop":
                return self._json({"ok": True, "file": hub.stop_recording()})
            return self._json({"error": "not found"}, 404)

        # ------------------------------------------------ WebSocket
        def _websocket(self):
            key = self.headers.get("Sec-WebSocket-Key")
            if not key or "websocket" not in (self.headers.get("Upgrade") or "").lower():
                return self._json({"error": "expected WebSocket upgrade"}, 400)
            accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            self.close_connection = True
            q = bc.add()
            sock = self.connection
            closed = threading.Event()
            threading.Thread(target=self._ws_reader, args=(sock, closed), daemon=True).start()
            try:
                hello = {"type": "hello", "status": hub.status(), "records": hub.history_since(0, 1500)}
                sock.sendall(ws_frame(json.dumps(hello, allow_nan=False, default=str).encode()))
                while not closed.is_set():
                    try:
                        msg = q.get(timeout=1.0)
                    except queue.Empty:
                        if q not in bc.clients:
                            break
                        continue
                    sock.sendall(ws_frame(msg))
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                bc.remove(q)

        @staticmethod
        def _ws_reader(sock, closed):
            """Consume client frames; we only care about close (0x8)."""
            try:
                while True:
                    hdr = sock.recv(2)
                    if len(hdr) < 2:
                        break
                    op, ln = hdr[0] & 0x0F, hdr[1] & 0x7F
                    if ln == 126:
                        ln = struct.unpack("!H", sock.recv(2))[0]
                    elif ln == 127:
                        ln = struct.unpack("!Q", sock.recv(8))[0]
                    if hdr[1] & 0x80:
                        sock.recv(4)
                    remaining = ln
                    while remaining:
                        chunk = sock.recv(min(remaining, 65536))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                    if op == 0x8:
                        break
            except OSError:
                pass
            closed.set()

    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(hub: Hub, host="127.0.0.1", port=8080):
    bc = Broadcaster(hub)
    httpd = Server((host, port), make_handler(hub, bc))
    return httpd
