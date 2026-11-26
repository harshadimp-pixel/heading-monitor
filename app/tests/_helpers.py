"""Shared helpers for app tests: start the app on a free port, talk WebSocket with raw sockets."""
import base64
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


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def run_app(*args, wait_for=None, timeout=10.0):
    port = free_port()
    p = subprocess.Popen([sys.executable, "-m", "app", "--port", str(port), *args], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base = f"http://127.0.0.1:{port}"
    try:
        t0 = time.time()
        while True:
            try:
                urllib.request.urlopen(base + "/api/status", timeout=1).read()
                break
            except Exception:
                if p.poll() is not None or time.time() - t0 > timeout:
                    raise RuntimeError("app did not start:\n" + (p.stdout.read() if p.poll() is not None else ""))
                time.sleep(0.2)
        if wait_for:
            wait_until(lambda: wait_for(get_json(base + "/api/status")), timeout)
        yield base, port
    finally:
        p.terminate()
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()


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
