"""Command line entry: python -m firmware_bridge ..."""
from __future__ import annotations

import argparse
import json
import sys

from .identity import load_allowlist
from .bridge import BridgeError, CaptureWriter, Poller, SerialTransport, replay
from .fake_fc import FakeFC, FakeFCTransport
from .scaling import MAG_PROFILES

EPILOG = """
Modes (exactly one):
  --port DEV       live MSP polling of a real FC  -> source="hardware"
  --replay FILE    Sample JSONL, --capture JSONL, or raw MSP bytes -> source="replay"
  --fake-fc        in-process simulated FC (loopback) -> source="sim"
Read-only: the bridge only sends MSP_FC_VARIANT / MSP_ATTITUDE / MSP_RAW_IMU requests.
See firmware_bridge/README.md and docs/firmware/FC_SETUP.md.
"""


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m firmware_bridge", epilog=EPILOG,
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 description="MSP telemetry bridge emitting Sample JSONL (contracts/sample.schema.json)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--port", help="serial device of the FC USB VCP, e.g. /dev/ttyACM0 or COM5")
    mode.add_argument("--replay", metavar="FILE", help="replay a recorded file")
    mode.add_argument("--fake-fc", action="store_true", help="simulated FC loopback (source='sim')")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--msp-version", type=int, choices=(1, 2, 21), default=1,
                    help="1 = MSPv1 ($M, XOR), 2 = MSPv2 native ($X, CRC8 DVB-S2), 21 = MSPv2 over v1")
    ap.add_argument("--rate", type=float, default=20.0, help="poll rate Hz (live/fake)")
    ap.add_argument("--profile", choices=sorted(MAG_PROFILES), default=None,
                    help="mag/accel unit profile (default inav-msp-mag; see README)")
    ap.add_argument("--auto-profile", action="store_true",
                    help="pick profile from MSP_FC_VARIANT (INAV->inav-msp-mag, BTFL->betaflight)")
    ap.add_argument("--body-frame", choices=("flu", "frd"), default=None,
                    help="frame of MSP_RAW_IMU vectors (default from profile: INAV=flu, converted to FRD)")
    ap.add_argument("--mag-ut-per-lsb", type=float, help="override mag scale (uT per MSP LSB)")
    ap.add_argument("--accel-lsb-per-g", type=float, help="override accel scale (LSB per g)")
    ap.add_argument("--passive", action="store_true",
                    help="live: do not poll, only listen (e.g. AP_Periph UART pushing MSP2_SENSOR_COMPASS)")
    ap.add_argument("--verified-devices", metavar="FILE",
                    help="D8 allowlist (default: config/verified_devices.json, ships empty)")
    ap.add_argument("--no-gps", action="store_true",
                    help="do not request MSP_RAW_GPS (gps availability object will be absent)")
    ap.add_argument("--capture", metavar="FILE", help="live/fake: also log raw tx/rx bytes as replayable JSONL")
    ap.add_argument("--replay-rate", type=float, default=50.0, help="t step (Hz) for raw-binary replay")
    ap.add_argument("--realtime", action="store_true", help="replay: pace output by t")
    ap.add_argument("--count", type=int, help="stop after N samples")
    ap.add_argument("--duration", type=float, help="stop after S seconds (live/fake)")
    ap.add_argument("--out", metavar="FILE", help="write JSONL here instead of stdout")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    bk = {"profile": args.profile or "inav-msp-mag", "mag_ut_per_lsb": args.mag_ut_per_lsb,
          "accel_lsb_per_g": args.accel_lsb_per_g, "body_frame": args.body_frame}
    out = open(args.out, "w", encoding="utf-8") if args.out else sys.stdout
    capture = None
    n = 0
    try:
        if args.replay:
            it = replay(args.replay, {**bk, "_profile_explicit": args.profile is not None},
                        rate_hz=args.replay_rate, realtime=args.realtime)
        else:
            tr = FakeFCTransport(FakeFC(), dt=1.0 / args.rate) if args.fake_fc else SerialTransport(args.port, args.baud)
            if args.capture:
                capture = CaptureWriter(args.capture, {"source": tr.kind, "port": args.port or "fake-fc",
                                                       "baud": args.baud, "msp_version": args.msp_version,
                                                       "mag_profile": bk["profile"]})
            if args.fake_fc:
                # simulated clock so fake runs are deterministic and fast
                clock_state = {"t": 0.0}
                def clock():
                    clock_state["t"] += 0.001
                    return clock_state["t"]
                def sleep(s):
                    clock_state["t"] += s
                tr.fc._clock = lambda: clock_state["t"]
                poller = Poller(tr, bk, args.msp_version, args.rate, capture=capture,
                                auto_profile=args.auto_profile, clock=clock, sleep=sleep, gps=not args.no_gps,
                                allowlist=load_allowlist(args.verified_devices))
            else:
                poller = Poller(tr, bk, args.msp_version, args.rate, capture=capture,
                                passive=args.passive, auto_profile=args.auto_profile, gps=not args.no_gps,
                                allowlist=load_allowlist(args.verified_devices))
            it = poller.run(max_samples=args.count, duration=args.duration)
        for s in it:
            out.write(json.dumps(s, separators=(",", ":")) + "\n")
            out.flush()
            n += 1
            if args.count is not None and n >= args.count:
                break
    except (BridgeError, ValueError, OSError) as e:
        print(f"[firmware_bridge] ERROR: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        pass
    finally:
        if capture:
            capture.close()
        if args.out:
            out.close()
    return 0
