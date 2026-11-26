"""python -m app --source sim[:scenario] | replay:<file> | serial:<port> | ingest"""
from __future__ import annotations

import argparse
import logging
import signal
import sys

from .hub import Hub
from .server import serve
from .sources import make_source


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m app", description="Virtual heading monitor web UI (T5)")
    ap.add_argument("--source", default="sim",
                    help="sim[:scenario] | replay:<file.jsonl> | serial:<port> | ingest (default: sim)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--rate", type=float, default=20.0, help="sim sample rate in Hz (default 20)")
    ap.add_argument("--seed", type=int, default=None, help="sim seed")
    ap.add_argument("--baud", type=int, default=115200, help="serial baud for firmware_bridge")
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed factor")
    ap.add_argument("--loop", action="store_true", help="loop replay file")
    ap.add_argument("--declination", type=float, default=0.0,
                    help="magnetic declination in deg (east +). 0 = headings are MAGNETIC")
    ap.add_argument("--stale", type=float, default=2.0,
                    help="seconds without samples before values show Unknown/STALE (default 2)")
    ap.add_argument("--calibration", default=None, help="calibration JSON file to load at start")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    hub = Hub(a.source, declination_deg=a.declination, stale_after_s=a.stale)
    if a.calibration:
        import json
        with open(a.calibration) as f:
            hub.load_calibration(doc=json.load(f))
    try:
        src = make_source(a.source, hub.emit, hub.on_source_status, rate=a.rate, seed=a.seed,
                          baud=a.baud, speed=a.speed, loop=a.loop)
    except ValueError as e:
        ap.error(str(e))
    httpd = serve(hub, a.host, a.port)
    src.start()
    logging.info("Heading monitor UI on http://%s:%d  (source %s)", a.host, a.port, a.source)
    signal.signal(signal.SIGTERM, lambda *_: (src.stop(), sys.exit(0)))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        src.stop()
        httpd.server_close()
        if hub.recorder:
            hub.stop_recording()


if __name__ == "__main__":
    main()
