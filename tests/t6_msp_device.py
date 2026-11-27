"""T6 independent MSP device emulator served on a virtual pty (no product code used).

It answers MSP requests (v1 '$M<' and v2 '$X<') written by firmware_bridge to the slave side of a pty.
Identity replies are configurable so the D8 provenance paths can be exercised black-box:
  variant   4-char MSP_FC_VARIANT (e.g. 'INAV', 'SIML'); None -> error reply ('!')
  board     4-char board id in MSP_BOARD_INFO; None -> error reply
  uid       bytes for MSP_UID (cmd 160); None -> error reply (UID unsupported / missing)
  identity  False -> every identity query (API/VARIANT/VERSION/BOARD/UID) gets an error reply
Telemetry imitates INAV layouts (MSP_RAW_IMU int16 acc 512 LSB/g, gyro, mag in 0.1 uT steps; MSP_ATTITUDE),
level vehicle rotating at 30 deg/s in a 50 uT, 60 deg inclination field. Everything is [SIMULATED].
"""
import math, os, struct, threading, time, tty

from msp_frames import v1, v2

API_VERSION, FC_VARIANT, FC_VERSION, BOARD_INFO = 1, 2, 3, 4
CALIBRATION_DATA, RAW_IMU, RAW_GPS, ATTITUDE, UID = 14, 102, 106, 108, 160
IDENTITY = {API_VERSION, FC_VARIANT, FC_VERSION, BOARD_INFO, UID}


class _ReqParser:
    """Minimal request parser for '$M<' (v1) and '$X<' (v2) frames. Bad checksums are dropped."""
    def __init__(self): self.buf = b""

    def feed(self, data):
        self.buf += data
        out = []
        while True:
            i = min([j for j in (self.buf.find(b"$M"), self.buf.find(b"$X")) if j >= 0], default=-1)
            if i < 0: self.buf = self.buf[-1:]; return out
            self.buf = self.buf[i:]
            if len(self.buf) < 3: return out
            if self.buf[1:2] == b"M":
                if len(self.buf) < 6: return out
                n, cmd = self.buf[3], self.buf[4]
                if len(self.buf) < 6 + n: return out
                pl = self.buf[5:5 + n]; self.buf = self.buf[6 + n:]
                if cmd == 255 and n >= 5:   # v2 over v1: unwrap (flag, cmd16, len16, payload, crc)
                    cmd = struct.unpack("<H", pl[1:3])[0]; out.append((1, cmd, pl[5:-1])); continue
                out.append((1, cmd, pl))
            else:
                if len(self.buf) < 9: return out
                cmd, n = struct.unpack("<HH", self.buf[4:8])
                if len(self.buf) < 9 + n: return out
                pl = self.buf[8:8 + n]; self.buf = self.buf[9 + n:]
                out.append((2, cmd, pl))


class MSPDevice:
    def __init__(self, variant="INAV", board="MKH7", uid=bytes(range(0x10, 0x1C)), identity=True,
                 yaw_rate_dps=30.0):
        self.variant, self.board, self.uid, self.identity = variant, board, uid, identity
        self.yaw_rate, self.t0 = yaw_rate_dps, time.time()
        self.requests = []
        self.master, self.slave = os.openpty()
        tty.setraw(self.slave)
        self.port = os.ttyname(self.slave)
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._serve, daemon=True)
        self._th.start()

    def _reply(self, ver, cmd, payload, err=False):
        d = b"!" if err else b">"
        return v1(cmd, payload, d) if ver == 1 else v2(cmd, payload, d)

    def _payload(self, cmd):
        """Return payload bytes, or None for an error ('!') reply."""
        if cmd in IDENTITY and not self.identity: return None
        if cmd == API_VERSION: return bytes([0, 2, 5])
        if cmd == FC_VARIANT: return None if self.variant is None else self.variant.encode()[:4].ljust(4, b" ")
        if cmd == FC_VERSION: return bytes([8, 0, 0])
        if cmd == BOARD_INFO:
            if self.board is None: return None
            name = b"T6_EMULATED_DEVICE"
            return self.board.encode()[:4].ljust(4, b" ") + struct.pack("<HBB", 0, 0, 0) + bytes([len(name)]) + name
        if cmd == UID: return None if self.uid is None else bytes(self.uid)
        if cmd == CALIBRATION_DATA:
            return struct.pack("<B3h3h3hH3h", 0, 0, 0, 0, 4096, 4096, 4096, 0, 0, 0, 0, 1024, 1024, 1024)
        yaw = math.radians((self.yaw_rate * (time.time() - self.t0)) % 360)
        if cmd == RAW_IMU:
            h, z = 50 * math.cos(math.radians(60)), 50 * math.sin(math.radians(60))
            mag = [round(h * math.cos(yaw) * 10), round(h * math.sin(yaw) * 10), round(-z * 10)]
            return struct.pack("<9h", 0, 0, 512, 0, 0, -round(self.yaw_rate), *mag)
        if cmd == ATTITUDE: return struct.pack("<3h", 0, 0, int(math.degrees(yaw)))
        return None   # RAW_GPS and anything else: not supported

    def _serve(self):
        p = _ReqParser()
        while not self._stop.is_set():
            try: data = os.read(self.master, 1024)
            except OSError: return
            for ver, cmd, _ in p.feed(data):
                self.requests.append(cmd)
                pl = self._payload(cmd)
                try: os.write(self.master, self._reply(ver, cmd, b"" if pl is None else pl, err=pl is None))
                except OSError: return

    def close(self):
        self._stop.set()
        for fd in (self.slave, self.master):
            try: os.close(fd)
            except OSError: pass


class ProductFakeFCOnPty:
    """The product's own firmware_bridge.fake_fc.FakeFC (default constructor) served on a pty: the exact path
    that A10c showed as live HARDWARE before D8."""
    def __init__(self):
        from firmware_bridge.fake_fc import FakeFC
        self.fc = FakeFC()
        self.master, self.slave = os.openpty(); tty.setraw(self.slave)
        self.port = os.ttyname(self.slave)
        self._stop = threading.Event()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        t0 = time.time()
        while not self._stop.is_set():
            try: data = os.read(self.master, 1024)
            except OSError: return
            self.fc.t = time.time() - t0
            for fr in self.fc.parser.feed(data):
                rep = self.fc.handle(fr)
                if not rep: continue
                try: os.write(self.master, rep)
                except OSError: return

    def close(self):
        self._stop.set()
        for fd in (self.slave, self.master):
            try: os.close(fd)
            except OSError: pass
