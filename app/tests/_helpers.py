"""Shared helpers for app tests: start the app on a free port, talk WebSocket with raw sockets."""
import base64
import re
import threading
import contextlib
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@contextlib.contextmanager
def run_app(*args, wait_for=None, timeout=10.0):
    """Start `python -m app --port 0` (OS-assigned ephemeral port, never 8080) and yield (base_url, port).
    The real port is read from the app's start-up log line."""
    p = subprocess.Popen([sys.executable, "-m", "app", "--port", "0", *args], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = []
    port_box = []
    got_port = threading.Event()

    def reader():
        for line in p.stdout:
            log.append(line)
            m = re.search(r"Heading monitor UI on http://[^:]+:(\d+)", line)
            if m and not port_box:
                port_box.append(int(m.group(1)))
                got_port.set()
        got_port.set()

    threading.Thread(target=reader, daemon=True).start()
    try:
        if not got_port.wait(timeout) or not port_box:
            raise RuntimeError("app did not report its port:\n" + "".join(log))
        port = port_box[0]
        assert port != 8080
        base = f"http://127.0.0.1:{port}"
        wait_until(lambda: _alive(base), timeout)
        if wait_for:
            wait_until(lambda: wait_for(get_json(base + "/api/status")), timeout)
        yield base, port
    finally:
        p.terminate()
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()


def _alive(base):
    try:
        urllib.request.urlopen(base + "/api/health", timeout=1).read()
        return True
    except Exception:
        return False


def wait_until(pred, timeout=10.0, step=0.2):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(step)
    raise AssertionError("condition not met within %.1f s" % timeout)


def get_json(url):
    return json.loads(urllib.request.urlopen(url, timeout=5).read())


def post_json(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


class WSClient:
    """Minimal RFC 6455 client (text frames only) for tests."""

    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=5)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
                        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        hdr = b""
        while b"\r\n\r\n" not in hdr:
            hdr += self.s.recv(1)
        self.handshake = hdr.decode()

    def _recv_exact(self, n):
        b = b""
        while len(b) < n:
            c = self.s.recv(n - len(b))
            if not c:
                raise ConnectionError("closed")
            b += c
        return b

    def recv_json(self):
        h = self._recv_exact(2)
        ln = h[1] & 0x7F
        if ln == 126:
            ln = struct.unpack("!H", self._recv_exact(2))[0]
        elif ln == 127:
            ln = struct.unpack("!Q", self._recv_exact(8))[0]
        return json.loads(self._recv_exact(ln))

    def close(self):
        self.s.close()


def sample(t, heading_deg, source="sim", b_h=30.0, b_z=40.0):
    """Level-sensor contract Sample whose true heading is heading_deg (NED body frame)."""
    import math
    a = math.radians(heading_deg)
    return {"t": t, "source": source, "mag_uT": [b_h * math.cos(a), -b_h * math.sin(a), b_z],
            "accel_g": [0.0, 0.0, -1.0]}
