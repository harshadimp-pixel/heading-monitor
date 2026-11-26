"""Live MSP polling, raw capture and replay -> Sample dicts.

Source labelling rule (README ground rule 1, TEAM_TRACKER T4):
  * 'hardware' only from SerialTransport (a real pyserial port),
  * 'sim' only from FakeFCTransport,
  * 'replay' for every --replay input, whatever the recorded file claimed.
The label is taken from the transport's class-level `kind`, never from a CLI flag.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from typing import Iterator

from . import msp
from .sample import SampleBuilder, validate_sample
from .scaling import (FC_VARIANT_DEFAULT_PROFILE, decode_attitude, decode_calibration_data, decode_raw_imu,
                      decode_raw_gps_availability, decode_sensor_compass, redact_raw_gps_payload)


class BridgeError(RuntimeError):
    pass


def _log(msg: str) -> None:
    print(f"[firmware_bridge] {msg}", file=sys.stderr, flush=True)


class SerialTransport:
    """Real serial port via pyserial (optional dependency). kind is fixed to 'hardware'."""

    kind = "hardware"

    def __init__(self, port: str, baud: int = 115200):
        try:
            import serial  # type: ignore
        except ImportError as e:  # pragma: no cover - depends on environment
            raise BridgeError("pyserial is not installed; live --port mode needs it: "
                              "pip install pyserial  (replay and --fake-fc work without it)") from e
        # read-only telemetry polling: we only ever send MSP *read* requests (no MSP_SET_*, no reboot, no flashing)
        self.ser = serial.Serial(port, baudrate=baud, timeout=0.01)

    def write(self, data: bytes) -> None:
        self.ser.write(data)

    def read(self, n: int = 4096, timeout: float = 0.01) -> bytes:
        self.ser.timeout = timeout
        waiting = max(1, getattr(self.ser, "in_waiting", 0) or 1)
        return self.ser.read(min(n, waiting))

    def tick(self) -> None:
        pass

    def close(self) -> None:
        self.ser.close()


class CaptureWriter:
    """Timestamped MSP log (JSONL) for replay. tx = raw request bytes; rx = each parsed frame re-encoded
    (MSP_RAW_GPS coordinates zeroed), so it is frame-exact, not byte-exact (garbage/bad-CRC bytes dropped)."""

    def __init__(self, path: str, header: dict):
        self.f = open(path, "w", encoding="utf-8")
        hdr = {"capture": "firmware_bridge/msp", "format_version": 1,
               "started_utc": datetime.now(timezone.utc).isoformat(), **header}
        self.f.write(json.dumps(hdr) + "\n")

    def write(self, t: float, direction: str, data: bytes) -> None:
        if data:
            self.f.write(json.dumps({"t": round(t, 6), direction: data.hex()}) + "\n")
            self.f.flush()

    def write_frame(self, t: float, frame: msp.MSPFrame) -> None:
        """rx is logged frame by frame (re-encoded, checksum recomputed) so MSP_RAW_GPS coordinates can be
        zeroed before anything touches disk. Garbage / bad-checksum bytes are therefore not kept."""
        payload = frame.payload
        if frame.cmd == msp.MSP_RAW_GPS:
            payload = redact_raw_gps_payload(payload)
        self.write(t, "rx", encode_frame(frame, payload))


    def close(self) -> None:
        self.f.close()


def encode_frame(frame: msp.MSPFrame, payload: bytes) -> bytes:
    if frame.version == 2:
        return msp.encode_v2(frame.cmd, payload, frame.direction, frame.flag)
    if frame.version == 21:
        return msp.encode_v2_over_v1(frame.cmd, payload, frame.direction, frame.flag)
    return msp.encode_v1(frame.cmd, payload, frame.direction)


# Read-only MSP requests this bridge is allowed to send. Anything else is refused.
# MSP_CALIBRATION_DATA (14) is an "out" (read) message in INAV mspFcProcessOutCommand; the write
# counterpart MSP_SET_CALIBRATION_DATA (15) and MSP_MAG_CALIBRATION (206) are deliberately NOT allowed.
ALLOWED_REQUESTS = frozenset({msp.MSP_API_VERSION, msp.MSP_FC_VARIANT, msp.MSP_FC_VERSION,
                              msp.MSP_RAW_IMU, msp.MSP_ATTITUDE, msp.MSP_CALIBRATION_DATA,
                              msp.MSP_RAW_GPS})


class Poller:
    def __init__(self, transport, builder_kwargs: dict, msp_version: int = 1, rate_hz: float = 20.0,
                 response_timeout: float = 0.25, capture: CaptureWriter | None = None,
                 passive: bool = False, auto_profile: bool = False, clock=time.monotonic,
                 sleep=time.sleep, cal_refresh_s: float = 10.0, gps_period_s: float = 1.0,
                 gps: bool = True):
        self.tr = transport
        self.version = msp_version
        self.period = 1.0 / rate_hz if rate_hz > 0 else 0.0
        self.timeout = response_timeout
        self.capture = capture
        self.passive = passive
        self.parser = msp.MSPParser()
        self.clock, self.sleep = clock, sleep
        self.t0 = clock()
        self.builder_kwargs = dict(builder_kwargs)
        self.auto_profile = auto_profile
        self.builder = SampleBuilder(source=transport.kind, msp_version=msp_version, **self.builder_kwargs)
        self.attitude: dict | None = None
        self.raw_imu_errors = 0
        self.cal_refresh_s = cal_refresh_s
        self._last_cal_req: float | None = None
        self.gps_enabled = gps
        self.gps_period_s = gps_period_s
        self._last_gps_req: float | None = None
        self._gps_misses = 0

    def now(self) -> float:
        return self.clock() - self.t0

    def send(self, cmd: int) -> None:
        if cmd not in ALLOWED_REQUESTS:
            raise BridgeError(f"refusing to send non-read-only MSP command {cmd}")
        frame = msp.encode(cmd, b"", self.version, "<")
        if self.capture:
            self.capture.write(self.now(), "tx", frame)
        self.tr.write(frame)

    def _pump(self, want: set[int], deadline: float) -> list[msp.MSPFrame]:
        got: list[msp.MSPFrame] = []
        while True:
            data = self.tr.read(4096, timeout=0.005)
            if data:
                for f in self.parser.feed(data):
                    if self.capture:
                        self.capture.write_frame(self.now(), f)
                    got.append(f)
                    want.discard(f.cmd)
            if not want or self.clock() >= deadline:
                return got

    def identify(self) -> str | None:
        self.send(msp.MSP_FC_VARIANT)
        for f in self._pump({msp.MSP_FC_VARIANT}, self.clock() + max(self.timeout, 0.5)):
            if f.cmd == msp.MSP_FC_VARIANT and not f.is_error and len(f.payload) >= 4:
                v = f.payload[:4].decode("ascii", "replace")
                self.builder.fc_variant = v
                _log(f"FC variant: {v}")
                if self.auto_profile and v in FC_VARIANT_DEFAULT_PROFILE:
                    self.builder_kwargs["profile"] = FC_VARIANT_DEFAULT_PROFILE[v]
                    self.builder = SampleBuilder(source=self.tr.kind, msp_version=self.version,
                                                 **self.builder_kwargs)
                    self.builder.fc_variant = v
                self.request_calibration()
                if v == "ARDU":
                    _log("WARNING: ArduPilot's AP_MSP does not implement MSP_RAW_IMU; no mag over MSP. "
                         "Use MAVLink (see docs/firmware/FC_SETUP.md).")
                return v
        _log("no MSP_FC_VARIANT reply (continuing)")
        return None

    def request_calibration(self) -> None:
        """Read-only MSP_CALIBRATION_DATA for meta.fc_mag_calibrated (INAV only)."""
        if self.builder.fc_variant != "INAV":
            return
        self._last_cal_req = self.clock()
        self.send(msp.MSP_CALIBRATION_DATA)
        frames = self._pump({msp.MSP_CALIBRATION_DATA}, self.clock() + max(self.timeout, 0.5))
        self.frames_to_samples(frames, self.now())
        _log(f"FC mag calibration: fc_mag_calibrated={self.builder.fc_mag_calibrated!r}")
    def frames_to_samples(self, frames, t: float) -> list[dict]:
        return frames_to_samples(frames, t, self.builder, self)

    def run(self, max_samples: int | None = None, duration: float | None = None) -> Iterator[dict]:
        if not self.passive:
            self.identify()
        n = 0
        while True:
            if duration is not None and self.now() >= duration:
                return
            cycle_start = self.clock()
            if self.passive:
                frames = self._pump(set(), cycle_start + max(self.period, 0.01))
            else:
                if (self.builder.fc_variant == "INAV" and self._last_cal_req is not None
                        and cycle_start - self._last_cal_req >= self.cal_refresh_s):
                    self._last_cal_req = cycle_start
                    self.send(msp.MSP_CALIBRATION_DATA)   # reply handled in frames_to_samples
                want = {msp.MSP_ATTITUDE, msp.MSP_RAW_IMU}
                gps_asked = (self.gps_enabled and self.builder.fc_variant == "INAV"
                             and (self._last_gps_req is None
                                  or cycle_start - self._last_gps_req >= self.gps_period_s))
                if gps_asked:
                    self._last_gps_req = cycle_start
                    self.send(msp.MSP_RAW_GPS)
                    want.add(msp.MSP_RAW_GPS)
                self.send(msp.MSP_ATTITUDE)
                self.send(msp.MSP_RAW_IMU)
                frames = self._pump(want, cycle_start + self.timeout)
                if gps_asked:
                    if any(f.cmd == msp.MSP_RAW_GPS for f in frames):
                        self._gps_misses = 0
                    else:   # no reply at all: gps goes absent now; stop asking after 3 silent tries
                        self.builder.set_gps(None)
                        self._gps_misses += 1
                        if self._gps_misses >= 3:
                            self.gps_enabled = False
                            _log("no MSP_RAW_GPS reply 3x in a row; gps availability disabled (gps omitted)")
            for s in self.frames_to_samples(frames, self.now()):
                yield s
                n += 1
                if max_samples is not None and n >= max_samples:
                    return
            if self.raw_imu_errors >= 5:
                raise BridgeError("FC answered MSP_RAW_IMU with error frames 5x in a row "
                                  "(ArduPilot does not implement it); stopping")
            self.tr.tick()
            rest = self.period - (self.clock() - cycle_start)
            if rest > 0:
                self.sleep(rest)


def frames_to_samples(frames, t: float, builder: SampleBuilder, state) -> list[dict]:
    """Shared by live polling and replay. `state` holds .attitude and .raw_imu_errors."""
    out = []
    for f in frames:
        try:
            if f.cmd == msp.MSP_ATTITUDE and f.direction == ">":
                state.attitude = decode_attitude(f.payload)
            elif f.cmd == msp.MSP_RAW_IMU and f.direction == ">":
                raw = decode_raw_imu(f.payload)
                state.raw_imu_errors = 0
                out.append(builder.from_raw_imu(t, raw, state.attitude))
            elif f.cmd == msp.MSP_RAW_IMU and f.is_error:
                state.raw_imu_errors += 1
            elif f.cmd == msp.MSP_CALIBRATION_DATA and f.direction == ">":
                builder.set_fc_calibration(decode_calibration_data(f.payload))
            elif f.cmd == msp.MSP_CALIBRATION_DATA and f.is_error:
                builder.set_fc_calibration(None)
            elif f.cmd == msp.MSP_RAW_GPS and f.direction == ">":
                builder.set_gps(decode_raw_gps_availability(f.payload), t)
            elif f.cmd == msp.MSP_RAW_GPS and f.is_error:
                builder.set_gps(None)
            elif f.cmd == msp.MSP_FC_VARIANT and f.direction == ">" and len(f.payload) >= 4:
                builder.fc_variant = f.payload[:4].decode("ascii", "replace")
            elif f.cmd == msp.MSP2_SENSOR_COMPASS and not f.is_error:
                out.append(builder.from_sensor_compass(t, decode_sensor_compass(f.payload), state.attitude))
        except ValueError as e:  # short payload etc. - skip frame, keep going
            if f.cmd == msp.MSP_CALIBRATION_DATA:
                builder.set_fc_calibration(None)   # unreadable -> 'unknown'
            elif f.cmd == msp.MSP_RAW_GPS:
                builder.set_gps(None)              # unreadable -> gps omitted
            _log(f"skipping frame cmd={f.cmd}: {e}")
    return out


# Position/motion keys that must never leave the bridge (ARCHITECTURE.md 2026-11-27: GPS availability only).
POSITION_KEYS = frozenset({"lat", "lon", "lng", "latitude", "longitude", "alt", "altitude", "alt_m", "llh",
                           "position", "pos", "coords", "coordinates", "speed", "ground_speed", "groundspeed",
                           "course", "ground_course", "groundcourse", "heading_gps", "velocity", "vel"})
GPS_ALLOWED_KEYS = ("fix", "num_sat", "hdop")


def scrub_position_fields(s: dict) -> dict:
    """In place: drop position-like keys at top level and in meta; keep only contract keys in gps."""
    for k in list(s):
        if k.lower() in POSITION_KEYS:
            del s[k]
    if isinstance(s.get("meta"), dict):
        for k in list(s["meta"]):
            if k.lower() in POSITION_KEYS:
                del s["meta"][k]
    if "gps" in s:
        if isinstance(s["gps"], dict):
            s["gps"] = {k: s["gps"][k] for k in GPS_ALLOWED_KEYS if k in s["gps"]}
        else:
            del s["gps"]
    return s


class _ReplayState:
    def __init__(self):
        self.attitude = None
        self.raw_imu_errors = 0


def replay(path: str, builder_kwargs: dict, rate_hz: float = 50.0, realtime: bool = False,
           sleep=time.sleep) -> Iterator[dict]:
    """Replay a file and yield Samples with source='replay'.

    Formats (auto-detected):
      1. Sample JSONL (e.g. a previous bridge/sim output): each line re-emitted with source='replay',
         original label kept in meta.original_source.
      2. Capture JSONL written by --capture (first line {"capture": "firmware_bridge/msp", ...},
         then {"t":..,"rx":"<hex>"} / {"t":..,"tx":"<hex>"}); rx bytes are re-parsed, t is preserved.
      3. Anything else: a raw binary MSP byte stream (e.g. a logic-analyser / serial-sniffer dump);
         t is synthesised as sample_index / rate_hz.
    """
    with open(path, "rb") as fh:
        head = fh.read(1).lstrip()
    if head == b"{":
        yield from _replay_jsonl(path, builder_kwargs, realtime, sleep)
    else:
        yield from _replay_binary(path, builder_kwargs, rate_hz, realtime, sleep)


def _pace(realtime, sleep, t, wall0, t0):
    if realtime:
        delay = (t - t0) - (time.monotonic() - wall0)
        if delay > 0:
            sleep(delay)


def _replay_jsonl(path, builder_kwargs, realtime, sleep):
    builder = None
    parser = msp.MSPParser()
    st = _ReplayState()
    wall0, t0 = time.monotonic(), None
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                _log(f"{path}:{lineno}: not JSON, skipped")
                continue
            if "capture" in rec:
                kw = dict(builder_kwargs)
                if not kw.pop("_profile_explicit", False) and rec.get("mag_profile"):
                    kw["profile"] = rec["mag_profile"]
                else:
                    kw.pop("_profile_explicit", None)
                builder = SampleBuilder(source="replay", msp_version=rec.get("msp_version"), **kw)
                builder.fc_variant = rec.get("fc_variant")
                continue
            if "mag_uT" in rec:  # format 1: Sample JSONL
                s = dict(rec)
                meta = dict(s.get("meta") or {})
                meta["original_source"] = s.get("source")
                meta["replayed_from"] = path
                s["meta"] = meta
                scrub_position_fields(s)
                s["source"] = "replay"
                errs = validate_sample(s)
                if errs:  # never forward contract-violating samples (T6 M3)
                    _log(f"{path}:{lineno}: invalid Sample skipped: {'; '.join(errs)}")
                    continue
                t0 = s["t"] if t0 is None else t0
                _pace(realtime, sleep, s["t"], wall0, t0)
                yield s
                continue
            if "rx" in rec:  # format 2: capture
                if builder is None:
                    kw = {k: v for k, v in builder_kwargs.items() if k != "_profile_explicit"}
                    builder = SampleBuilder(source="replay", **kw)
                t = float(rec.get("t", 0.0))
                t0 = t if t0 is None else t0
                for s in frames_to_samples(parser.feed(bytes.fromhex(rec["rx"])), t, builder, st):
                    s["meta"]["replayed_from"] = path
                    _pace(realtime, sleep, t, wall0, t0)
                    yield s
    if parser.stats.bad_checksum:
        _log(f"replay: {parser.stats.bad_checksum} frames with bad checksum dropped")


def _replay_binary(path, builder_kwargs, rate_hz, realtime, sleep):
    kw = {k: v for k, v in builder_kwargs.items() if k != "_profile_explicit"}
    builder = SampleBuilder(source="replay", **kw)
    parser = msp.MSPParser()
    st = _ReplayState()
    n = 0
    wall0 = time.monotonic()
    with open(path, "rb") as fh:
        while chunk := fh.read(4096):
            for f in parser.feed(chunk):
                t = n / rate_hz
                for s in frames_to_samples([f], t, builder, st):
                    s["meta"]["replayed_from"] = path
                    s["meta"]["t_synthesised_hz"] = rate_hz
                    _pace(realtime, sleep, t, wall0, 0.0)
                    yield s
                    n += 1
    if parser.stats.bad_checksum or parser.stats.garbage_bytes:
        _log(f"replay: dropped {parser.stats.bad_checksum} bad-checksum frames, "
             f"{parser.stats.garbage_bytes} garbage bytes")
