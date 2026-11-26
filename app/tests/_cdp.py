"""Drive headless Chrome over the DevTools protocol with stdlib only (no Playwright needed).

Real wall clock (no --virtual-time-budget), so the page's staleness logic sees true time.
Readiness is polled explicitly via window.__hmProbe() with a bounded timeout; assertions run once
afterwards on a single DOM read.
"""
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

CHROME = next((shutil.which(c) for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)), None)


class _WS:
    def __init__(self, url):
        u = urllib.parse.urlparse(url)
        self.s = socket.create_connection((u.hostname, u.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
                        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        hdr = b""
        while b"\r\n\r\n" not in hdr:
            c = self.s.recv(1)
            if not c:
                raise ConnectionError("devtools handshake failed")
            hdr += c
        if b" 101 " not in hdr.split(b"\r\n")[0]:
            raise ConnectionError(hdr.decode(errors="replace"))
        self.next_id = 0

    def _recv_exact(self, n):
        b = b""
        while len(b) < n:
            c = self.s.recv(n - len(b))
            if not c:
                raise ConnectionError("closed")
            b += c
        return b

    def send(self, obj):
        data = json.dumps(obj).encode()
        mask = os.urandom(4)
        n = len(data)
        hdr = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else
                               bytes([0x80 | 126]) + struct.pack("!H", n) if n < 65536 else
                               bytes([0x80 | 127]) + struct.pack("!Q", n))
        self.s.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        h = self._recv_exact(2)
        ln = h[1] & 0x7F
        if ln == 126:
            ln = struct.unpack("!H", self._recv_exact(2))[0]
        elif ln == 127:
            ln = struct.unpack("!Q", self._recv_exact(8))[0]
        return json.loads(self._recv_exact(ln))

    def call(self, method, **params):
        self.next_id += 1
        mid = self.next_id
        self.send({"id": mid, "method": method, "params": params})
        while True:
            m = self.recv()
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m["result"]


class HeadlessPage:
    def __init__(self, url, width=1400, height=1800, timeout=15):
        self.tmp = tempfile.mkdtemp(prefix="hm-chrome-")
        self.proc = subprocess.Popen([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-first-run",
                                      f"--user-data-dir={self.tmp}", "--remote-debugging-port=0",
                                      f"--window-size={width},{height}", url],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        port_file = os.path.join(self.tmp, "DevToolsActivePort")
        t0 = time.time()
        while not (os.path.exists(port_file) and open(port_file).read().strip()):
            if time.time() - t0 > timeout or self.proc.poll() is not None:
                self.close()
                raise RuntimeError("headless Chrome did not start DevTools")
            time.sleep(0.1)
        port = int(open(port_file).read().split()[0])
        page = None
        while page is None and time.time() - t0 < timeout:
            targets = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5).read())
            page = next((t for t in targets if t.get("type") == "page"), None)
            if page is None:
                time.sleep(0.1)
        self.ws = _WS(page["webSocketDebuggerUrl"])

    def eval(self, expr):
        r = self.ws.call("Runtime.evaluate", expression=expr, returnByValue=True)
        return r["result"].get("value")

    def wait_for(self, expr, timeout=15.0, step=0.1):
        """Bounded readiness wait: poll a JS expression until truthy. Raises TimeoutError with the last value."""
        t0, last = time.time(), None
        while time.time() - t0 < timeout:
            try:
                last = self.eval(expr)
            except Exception as e:  # page still loading
                last = repr(e)
            if last and not isinstance(last, str):
                return last
            time.sleep(step)
        raise TimeoutError(f"page not ready after {timeout}s: {expr} -> {last!r}")

    def texts(self, ids):
        return self.eval("(" + json.dumps(ids) + ").reduce((o, id) => { const e = document.getElementById(id);"
                         " o[id] = e ? e.textContent : null; return o; }, {})")

    def screenshot(self, path):
        data = self.ws.call("Page.captureScreenshot", format="png")["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(5)
        except Exception:
            self.proc.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
