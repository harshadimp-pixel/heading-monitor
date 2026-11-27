"""Drive headless Chrome over the DevTools protocol with stdlib only (no Playwright needed).

Real wall clock (no --virtual-time-budget), so the page's staleness logic sees true time.
Readiness is polled explicitly via window.__hmProbe() with a bounded timeout; assertions run once
afterwards on a single DOM read.

D10 (Chrome temp leak): Chrome 156 headless writes ~36 MB per launch into $TMPDIR (scoped_dir*,
.com.google.Chrome.*, com.google.Chrome.*) and never removes it; with TMPDIR=/tmp that filled the box's / on
27 Nov. Same approach as the Auditor's 03fc993: every launch gets ONE private directory from tempfile.mkdtemp
(prefix "hm-cdp-") holding both the profile (--user-data-dir) and Chrome's TMPDIR. close() stops the whole Chrome
process group it started (terminate, wait, kill if needed) and then removes that directory; an atexit hook
repeats the cleanup for any page that was never closed. A SIGKILLed test process cannot run either, which is
the remaining (documented) gap.
"""
import atexit
import base64
import json
import os
import signal
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

CHROME = next((shutil.which(c) for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)), None)
LAUNCH_PREFIX = "hm-cdp-"          # one private dir per Chrome launch: <dir>/profile + <dir>/tmp (Chrome's TMPDIR)
_LIVE = set()                      # pages not yet closed; cleaned by the atexit backup
DEFAULT_PARENT = None              # where launch dirs go when parent=None (None -> tempfile.gettempdir()); tests set it


def chrome_env(tmpdir):
    """Environment for a Chrome launch whose temp files must land in tmpdir (not the system /tmp)."""
    return {**os.environ, "TMPDIR": tmpdir, "TMP": tmpdir, "TEMP": tmpdir}


def _cleanup_live():
    for page in list(_LIVE):
        page.close()


atexit.register(_cleanup_live)


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
    def __init__(self, url, width=1400, height=1800, timeout=15, parent=None):
        self.box = tempfile.mkdtemp(prefix=LAUNCH_PREFIX, dir=parent or DEFAULT_PARENT)
        self.tmp = os.path.join(self.box, "profile")                    # --user-data-dir
        self.chrome_tmp = os.path.join(self.box, "tmp")                 # Chrome's TMPDIR
        os.makedirs(self.tmp)
        os.makedirs(self.chrome_tmp)
        self.proc = None
        self.ws = None
        _LIVE.add(self)
        try:
            self.proc = subprocess.Popen([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-first-run",
                                          f"--user-data-dir={self.tmp}", "--remote-debugging-port=0",
                                          f"--window-size={width},{height}", url],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                         env=chrome_env(self.chrome_tmp), start_new_session=True)
            self._connect(timeout)
        except BaseException:
            self.close()
            raise

    def _connect(self, timeout):
        port_file = os.path.join(self.tmp, "DevToolsActivePort")
        t0 = time.time()
        while not (os.path.exists(port_file) and open(port_file).read().strip()):
            if time.time() - t0 > timeout or self.proc.poll() is not None:
                raise RuntimeError("headless Chrome did not start DevTools")
            time.sleep(0.1)
        port = int(open(port_file).read().split()[0])
        page = None
        while page is None and time.time() - t0 < timeout:
            targets = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5).read())
            page = next((t for t in targets if t.get("type") == "page"), None)
            if page is None:
                time.sleep(0.1)
        if page is None:
            raise RuntimeError("headless Chrome exposed no page target")
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
        """Stop the Chrome process group this page started, then delete its private dir. Idempotent."""
        _LIVE.discard(self)
        if self.ws is not None:
            try:
                self.ws.s.close()
            except OSError:
                pass
            self.ws = None
        if self.proc is not None and self.proc.poll() is None:
            for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
                try:
                    os.killpg(self.proc.pid, sig)        # own session (start_new_session): only Chrome we started
                except ProcessLookupError:
                    break
                try:
                    self.proc.wait(wait)
                    break
                except subprocess.TimeoutExpired:
                    continue
        if self.proc is not None:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)   # stragglers (renderer/zygote) still in the group
            except (ProcessLookupError, PermissionError):
                pass
        for _ in range(20):                               # a dying child may still write for a moment
            shutil.rmtree(self.box, ignore_errors=True)
            if not os.path.exists(self.box):
                break
            time.sleep(0.1)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
