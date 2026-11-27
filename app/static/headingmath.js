/* Heading display maths shared by the UI and the Node-based unit test (app/tests). No DOM access. */
(function (root) {
  "use strict";
  const CARD16 = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
  const SOURCE_LABEL = { sim: "SIMULATED", replay: "REPLAY", hardware: "HARDWARE" };
  /** DATA SOURCE badge text: a pure mapping of sample.source; anything else -> null (UI shows NO DATA) */
  function badgeLabel(source) { return Object.prototype.hasOwnProperty.call(SOURCE_LABEL, source) ? SOURCE_LABEL[source] : null; }
  const ORIGIN_WORD = { hardware: "hardware", sim: "simulator" };
  /** Displayed badge (D6). Derived from sample.source (+ meta.original_source, + the transport that delivered it).
   *  - sim                      -> SIMULATED
   *  - replay + original_source -> "REPLAY (recorded hardware)" / "REPLAY (recorded simulator)"; else "REPLAY"
   *  - hardware via serial AND deviceVerified === true (uid in config/verified_devices.json, D8) -> HARDWARE
   *    (the ONLY path that shows HARDWARE / live; a serial link alone is not proof of hardware)
   *  - hardware any other way (serial unverified, replay, ingest, unknown) -> "UNVERIFIED SOURCE"
   *  - anything else            -> null (UI shows NO DATA)
   *  Returns {text, cls, live} or null. */
  function badgeInfo(source, originalSource, transport, deviceVerified) {
    const base = badgeLabel(source);
    if (!base) return null;
    if (source === "replay") {
      const w = Object.prototype.hasOwnProperty.call(ORIGIN_WORD, originalSource) ? ORIGIN_WORD[originalSource] : null;
      return { text: w ? `REPLAY (recorded ${w})` : "REPLAY", cls: "replay", live: false };
    }
    if (source === "hardware") {
      return transport === "serial" && deviceVerified === true ? { text: "HARDWARE", cls: "hardware", live: true }
                                    : { text: "UNVERIFIED SOURCE", cls: "unverified", live: false };
    }
    return { text: base, cls: source, live: false };
  }
  const isNum = (v) => typeof v === "number" && isFinite(v);
  /** wrap any angle to [0, 360) */
  function wrap360(d) { let x = d % 360; if (x < 0) x += 360; return x >= 360 ? 0 : x; }
  /** signed shortest difference a - b in (-180, 180] */
  function angleDiff(a, b) { const d = wrap360(a - b); return d > 180 ? d - 360 : d; }
  /** round to 0.1 deg for display; 359.96 -> 0.0, never 360.0 */
  function roundHeading(h) { let v = Math.round(wrap360(h) * 10) / 10; if (v >= 360) v -= 360; return v; }
  /** level heading (NED body: x fwd, y right, z down) = atan2(-By, Bx) */
  function levelHeading(bx, by) { return wrap360(Math.atan2(-by, bx) * 180 / Math.PI); }
  function cardinal(h) { return isNum(h) ? CARD16[Math.round(roundHeading(h) / 22.5) % 16] : ""; }
  const api = { SOURCE_LABEL, badgeLabel, badgeInfo, wrap360, angleDiff, roundHeading, levelHeading, cardinal, isNum };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.HeadingMath = api;
})(this);
