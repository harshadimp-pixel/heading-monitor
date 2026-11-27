/* Virtual Heading Monitor UI (T5). Vanilla JS, no external dependencies.
 * Rule: anything not measured, not reported, or stale is shown as "Unknown" — never 0 or a stale value as current.
 * The DATA SOURCE badge is derived ONLY from the `source` field of received samples. */
"use strict";
const $ = (id) => document.getElementById(id);
const MAX_RECORDS = 6000;
const UNKNOWN = "Unknown";

const S = { records: [], status: null, statusAt: 0, connected: false, lastMsgAt: 0, dirty: true, lastTable: 0,
            messages: 0, renders: 0, renderedSeq: 0 };
// Read-only readiness probe for automated UI tests: how many WS messages arrived and which sample seq was last rendered.
window.__hmProbe = () => ({ connected: S.connected, messages: S.messages, records: S.records.length,
  latestSeq: S.records.length ? S.records[S.records.length - 1].seq : 0, renderedSeq: S.renderedSeq, renders: S.renders });

// ---------------------------------------------------------------- math helpers (mirrored in tests)
const { wrap360, angleDiff, roundHeading, cardinal, isNum, badgeLabel, badgeInfo } = window.HeadingMath;
function fmtHeading(h) { return isNum(h) ? roundHeading(h).toFixed(1) + "°" : UNKNOWN; }
function fmtSigned(d, nd = 1) { return isNum(d) ? (d > 0 ? "+" : d < 0 ? "−" : "±") + Math.abs(d).toFixed(nd) + "°" : UNKNOWN; }
function fmtNum(v, nd = 2, unit = "") { return isNum(v) ? v.toFixed(nd) + unit : UNKNOWN; }

function setVal(el, text, unknown) {
  el = typeof el === "string" ? $(el) : el;
  el.textContent = text;
  el.classList.toggle("unknown", !!unknown || text === UNKNOWN);
  el.classList.toggle("unk", !!unknown || text === UNKNOWN);
}

// ---------------------------------------------------------------- freshness
function sampleAge() {
  const st = S.status;
  if (!st || !isNum(st.last_sample_age_s)) return null;
  return st.last_sample_age_s + (Date.now() - S.statusAt) / 1000;
}
function staleAfter() { return (S.status && S.status.stale_after_s) || 2; }
function isFresh() {
  const age = sampleAge();
  return S.connected && (Date.now() - S.lastMsgAt) < Math.max(3000, staleAfter() * 1000 + 1000) && age !== null && age <= staleAfter();
}
function latest() { return S.records.length ? S.records[S.records.length - 1] : null; }

// ---------------------------------------------------------------- WebSocket
function connect() {
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => { S.connected = true; S.dirty = true; };
  ws.onclose = () => { S.connected = false; S.dirty = true; setTimeout(connect, 1500); };
  ws.onerror = () => ws.close();
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    S.lastMsgAt = Date.now(); S.messages++;
    if (m.status) { S.status = m.status; S.statusAt = Date.now(); }
    if (m.type === "hello") S.records = m.records || [];
    else if (m.records && m.records.length) {
      S.records.push(...m.records);
      if (S.records.length > MAX_RECORDS) S.records.splice(0, S.records.length - MAX_RECORDS);
    }
    S.dirty = true;
  };
}

// ---------------------------------------------------------------- compass
const SVGNS = "http://www.w3.org/2000/svg";
function el(tag, attrs, parent) {
  const e = document.createElementNS(SVGNS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
const C = {};
function buildCompass() {
  const svg = $("compass");
  el("circle", { r: 150, fill: "#0f1720", stroke: "#2b3b4f", "stroke-width": 2 }, svg);
  el("circle", { r: 112, fill: "none", stroke: "#1e2a38", "stroke-width": 1 }, svg);
  for (let d = 0; d < 360; d += 10) {
    const major = d % 30 === 0, a = d * Math.PI / 180, r1 = 148, r2 = major ? 130 : 138;
    el("line", { x1: r1 * Math.sin(a), y1: -r1 * Math.cos(a), x2: r2 * Math.sin(a), y2: -r2 * Math.cos(a),
      stroke: major ? "#9fb2c8" : "#4b5d73", "stroke-width": major ? 2 : 1 }, svg);
    if (major && d % 90 !== 0) {
      const t = el("text", { x: 120 * Math.sin(a), y: -120 * Math.cos(a) + 4, "text-anchor": "middle",
        fill: "#8a9bb0", "font-size": 11 }, svg);
      t.textContent = d;
    }
  }
  [["N", 0, "#f87171"], ["E", 90, "#e3eaf2"], ["S", 180, "#e3eaf2"], ["W", 270, "#e3eaf2"]].forEach(([l, d, c]) => {
    const a = d * Math.PI / 180;
    const t = el("text", { x: 116 * Math.sin(a), y: -116 * Math.cos(a) + 7, "text-anchor": "middle",
      fill: c, "font-size": 20, "font-weight": 800 }, svg);
    t.textContent = l;
  });
  // reference: dashed line + rim triangle
  C.ref = el("g", { visibility: "hidden" }, svg);
  el("line", { x1: 0, y1: 0, x2: 0, y2: -146, stroke: "#ffb547", "stroke-width": 2.5, "stroke-dasharray": "7 5" }, C.ref);
  el("polygon", { points: "0,-150 -9,-164 9,-164", fill: "#ffb547" }, C.ref);
  // raw needle
  C.raw = el("g", { visibility: "hidden" }, svg);
  el("line", { x1: 0, y1: 0, x2: 0, y2: -100, stroke: "#7f8ea3", "stroke-width": 2 }, C.raw);
  el("circle", { cx: 0, cy: -100, r: 4, fill: "#7f8ea3" }, C.raw);
  // measured needle
  C.meas = el("g", { visibility: "hidden" }, svg);
  el("polygon", { points: "0,-108 9,0 0,14 -9,0", fill: "#38d6ff", stroke: "#0b1016", "stroke-width": 1 }, C.meas);
  el("polygon", { points: "0,14 9,0 0,40 -9,0", fill: "#25414f" }, C.meas);
  el("circle", { r: 6, fill: "#e3eaf2" }, svg);
  C.center = el("text", { y: 60, "text-anchor": "middle", fill: "#8a9bb0", "font-size": 14, "font-style": "italic" }, svg);
  svg.setAttribute("viewBox", "-170 -170 340 340");
  svg.addEventListener("click", (ev) => {
    const p = svg.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY;
    const q = p.matrixTransform(svg.getScreenCTM().inverse());
    if (Math.hypot(q.x, q.y) < 20) return;
    setReference(Math.round(wrap360(Math.atan2(q.x, -q.y) * 180 / Math.PI)));
  });
}
function setNeedle(g, deg) {
  if (isNum(deg)) { g.setAttribute("visibility", "visible"); g.setAttribute("transform", `rotate(${deg})`); }
  else g.setAttribute("visibility", "hidden");
}

// ---------------------------------------------------------------- attitude
function drawHorizon(roll, pitch) {
  const cv = $("horizon"), ctx = cv.getContext("2d"), w = cv.width, h = cv.height;
  ctx.clearRect(0, 0, w, h);
  if (!isNum(roll) || !isNum(pitch)) {
    ctx.fillStyle = "#1b2430"; ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "#8a9bb0"; ctx.font = "italic 16px system-ui"; ctx.textAlign = "center";
    ctx.fillText(UNKNOWN, w / 2, h / 2 + 5); return;
  }
  const ppd = 2.2; // pixels per degree of pitch
  ctx.save(); ctx.translate(w / 2, h / 2); ctx.rotate(-roll * Math.PI / 180); ctx.translate(0, pitch * ppd);
  ctx.fillStyle = "#1e4d7a"; ctx.fillRect(-w * 2, -h * 3, w * 4, h * 3);
  ctx.fillStyle = "#5a3d22"; ctx.fillRect(-w * 2, 0, w * 4, h * 3);
  ctx.strokeStyle = "#e3eaf2"; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(-w * 2, 0); ctx.lineTo(w * 2, 0); ctx.stroke();
  ctx.lineWidth = 1; ctx.fillStyle = "#e3eaf2"; ctx.font = "10px system-ui"; ctx.textAlign = "left";
  for (let p = -40; p <= 40; p += 10) {
    if (!p) continue;
    const y = -p * ppd, half = p % 20 === 0 ? 30 : 16;
    ctx.beginPath(); ctx.moveTo(-half, y); ctx.lineTo(half, y); ctx.stroke();
    if (p % 20 === 0) ctx.fillText(p, half + 4, y + 3);
  }
  ctx.restore();
  ctx.strokeStyle = "#fbbf24"; ctx.lineWidth = 3; ctx.beginPath();
  ctx.moveTo(w / 2 - 50, h / 2); ctx.lineTo(w / 2 - 15, h / 2); ctx.lineTo(w / 2, h / 2 + 10);
  ctx.lineTo(w / 2 + 15, h / 2); ctx.lineTo(w / 2 + 50, h / 2); ctx.stroke();
}

// ---------------------------------------------------------------- charts
function drawChart(cv, series, opts) {
  const dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
  const L = 44, R = 8, T = 8, B = 20, pw = W - L - R, ph = H - T - B;
  const now = opts.now, t0 = now - opts.windowS * 1000;
  let [ymin, ymax] = opts.y || [Infinity, -Infinity];
  if (!opts.y) {
    series.forEach((s) => s.data.forEach(([t, v]) => { if (t >= t0 && isNum(v)) { ymin = Math.min(ymin, v); ymax = Math.max(ymax, v); } }));
    if (!isFinite(ymin)) { ymin = -1; ymax = 1; }
    const pad = Math.max((ymax - ymin) * 0.1, 1); ymin -= pad; ymax += pad;
  }
  const X = (t) => L + (t - t0) / (now - t0) * pw, Y = (v) => T + (1 - (v - ymin) / (ymax - ymin)) * ph;
  ctx.strokeStyle = "#1e2a38"; ctx.fillStyle = "#6b7c90"; ctx.font = "10px system-ui"; ctx.lineWidth = 1;
  const ticks = opts.yTicks || niceTicks(ymin, ymax);
  ticks.forEach((v) => { const y = Y(v); ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(W - R, y); ctx.stroke(); ctx.textAlign = "right"; ctx.fillText(v, L - 4, y + 3); });
  ctx.textAlign = "center";
  for (let s = 0; s <= opts.windowS; s += opts.windowS / 6) { const x = X(now - s * 1000); ctx.fillText(s ? `-${Math.round(s)}s` : "now", x, H - 6); }
  series.forEach((s) => {
    ctx.strokeStyle = s.color; ctx.lineWidth = s.width || 1.5; ctx.setLineDash(s.dash || []); ctx.beginPath();
    let prev = null;
    for (const [t, v] of s.data) {
      if (t < t0) { prev = null; continue; }
      if (!isNum(v)) { prev = null; continue; }
      const gap = !prev || t - prev[0] > (opts.gapMs || 1500) || (s.wrap && Math.abs(v - prev[1]) > 180);
      if (gap) ctx.moveTo(X(t), Y(v)); else ctx.lineTo(X(t), Y(v));
      prev = [t, v];
    }
    ctx.stroke(); ctx.setLineDash([]);
  });
}
function niceTicks(a, b) {
  const span = b - a, step = Math.pow(10, Math.floor(Math.log10(span / 4))), m = span / 4 / step;
  const st = step * (m > 5 ? 10 : m > 2 ? 5 : m > 1 ? 2 : 1), out = [];
  for (let v = Math.ceil(a / st) * st; v <= b; v += st) out.push(+v.toFixed(6));
  return out;
}

// ---------------------------------------------------------------- render
function render() {
  if (!S.dirty) { requestAnimationFrame(render); return; }
  S.dirty = false;
  const st = S.status, r = latest(), fresh = isFresh() && r;
  const age = sampleAge();

  // connection
  $("connDot").className = "dot " + (S.connected ? "ok" : "bad");
  $("connText").textContent = S.connected ? "live (WebSocket)" : "disconnected — reconnecting";
  if (st) {
    const ss = st.source_status || {};
    $("transportText").textContent = `transport: ${st.source_spec} · ${ss.state || "?"}${ss.backend ? " · " + ss.backend : ""}`;
    $("backendText").textContent = `heading estimator: ${st.core.estimator_backend}` + (st.core.declination_deg ? ` · declination ${st.core.declination_deg}°` : "");
    $("staleS").textContent = st.stale_after_s;
  }

  // DATA SOURCE badge — from sample.source only
  const badge = $("sourceBadge");
  const bi = r ? badgeInfo(r.source, r.original_source, r.transport, r.device_verified) : null;
  if (fresh && bi) {
    badge.textContent = bi.text; badge.className = "source-badge " + bi.cls;
    $("sourceSub").textContent = `from sample.source = "${r.source}"` +
      (r.original_source ? ` · meta.original_source = "${r.original_source}"` : "") + ` · via ${r.transport || "?"}`;
  } else {
    badge.textContent = "NO DATA"; badge.className = "source-badge none";
    $("sourceSub").textContent = r ? `last sample.source "${r.source}" · ${isNum(age) ? age.toFixed(1) + " s ago" : "connection lost"}` : "no sample received";
  }
  let evidText = "No current data. All measurements below are Unknown.";
  if (fresh && bi) {
    if (r.source === "sim") evidText = "[SIMULATED] Values come from the simulator. They are not hardware measurements.";
    else if (r.source === "replay" && r.original_source === "hardware")
      evidText = "[REPLAYED] Recorded hardware log played back from a file. This is recorded data, not a live sensor stream. Nothing here is hardware-verified.";
    else if (r.source === "replay") evidText = "[REPLAYED] Values come from a recorded log, not a live sensor stream.";
    else if (bi.live) evidText = "Live hardware samples from a verified device (serial; uid listed in config/verified_devices.json). Accuracy is not hardware-verified until the auditor signs off a committed log.";
    else if (r.transport === "serial")
      evidText = "[UNVERIFIED] Samples arrived over a serial link, but the device is not in config/verified_devices.json (" +
                 ({ no_identity: "no device identity reported", no_uid: "no device UID reported", uid_not_listed: "UID not in the verified list", bridge_unverified: "the bridge did not report provenance verified" }[r.device_status] || "not verified") +
                 "). A serial connection is not proof of hardware. Board and variant are reported by device, not verified.";
    else evidText = `[UNVERIFIED] Samples are labelled "hardware" but arrived via ${r.transport || "an unknown transport"}, not a live serial source. They are not treated as live sensor data.`;
  }
  $("evidenceBanner").textContent = evidText;

  // D8: device identity over serial, always labelled "reported by device" (never verified by the app)
  const devBox = $("deviceIdentity");
  if (r && r.transport === "serial") {
    devBox.hidden = false;
    const rb = (v) => `${isNum(v) || (typeof v === "string" && v) ? v : "Unknown"} (reported by device)`;
    $("deviceBoard").textContent = rb(r.device_board);
    $("deviceVariant").textContent = rb(r.device_variant);
    $("deviceTarget").textContent = rb(r.device_target);
    $("deviceUid").textContent = rb(r.device_uid);
    $("deviceVerify").textContent = r.device_verified ? "UID listed in config/verified_devices.json"
      : r.device_status === "simulator" ? "device reports a simulator (SIML/SIMF)"
      : "not verified (" + ({ no_identity: "no identity", no_uid: "no UID", uid_not_listed: "UID not in verified list", bridge_unverified: "bridge provenance not verified" }[r.device_status] || "unknown") + ")";
  } else {
    devBox.hidden = true;
  }

  // heading
  const declTxt = st && st.core.declination_deg ? "true, declination applied" : "magnetic";
  $("headingLabel").textContent = `Measured heading (filtered estimate, ${declTxt})`;
  const h = fresh ? r.heading_deg : null, hr = fresh ? r.heading_raw_deg : null;
  setVal("headingValue", isNum(h) ? `${fmtHeading(h)} ${cardinal(h)}` : UNKNOWN);
  const hint = $("headingHint");
  if (!fresh && r && isNum(r.heading_deg)) {
    hint.textContent = `STALE: last value ${fmtHeading(r.heading_deg)} at ${new Date(r.recv_ms).toLocaleTimeString()} (not current)`;
    hint.className = "hint stale";
  } else {
    hint.textContent = fresh && r.calibrated === false ? "Not calibrated: heading uses the uncalibrated field (see Calibration wizard)" : "";
    hint.className = "hint";
  }
  setVal("rawHeadingValue", isNum(hr) ? `${fmtHeading(hr)} ${cardinal(hr)}` : UNKNOWN);
  const ref = st ? st.reference_deg : null;
  setVal("deviationValue", isNum(h) && isNum(ref) ? fmtSigned(angleDiff(h, ref)) : UNKNOWN);
  if (document.activeElement !== $("refNumber")) $("refNumber").value = isNum(ref) ? ref : "";
  if (isNum(ref) && document.activeElement !== $("refSlider")) $("refSlider").value = Math.round(ref) % 360;
  setNeedle(C.meas, h); setNeedle(C.raw, hr); setNeedle(C.ref, ref);
  C.center.textContent = isNum(h) ? "" : "heading unknown";

  // status
  let sensor = !S.connected ? "UNKNOWN" : (st ? st.sensor_status : "UNKNOWN");
  if (S.connected && st && r && !isFresh() && (sensor === "OK" || sensor === "DEGRADED")) sensor = "STALE";  // never show a stale OK
  const pill = $("sensorStatus");
  pill.textContent = sensor === "UNKNOWN" ? UNKNOWN : sensor;
  pill.className = "pill " + sensor.toLowerCase().replace(/\s/g, "");
  $("sensorReason").textContent = !S.connected ? "dashboard not connected to backend" : (st ? st.sensor_status_reason : "");
  setVal("lastAge", isNum(age) ? `${age.toFixed(1)} s ago` : UNKNOWN);
  setVal("rateValue", st && S.connected && st.rate_hz > 0 ? `${st.rate_hz.toFixed(1)} Hz` : UNKNOWN);
  if (st) $("countsValue").textContent = `${st.counts.accepted} / ${st.counts.invalid}`;
  const q = fresh ? r.quality : null;
  setVal("qualityValue", isNum(q) ? q.toFixed(2) : UNKNOWN);
  $("qualityBar").style.width = isNum(q) ? Math.max(0, Math.min(1, q)) * 100 + "%" : "0";
  setVal("noiseValue", fresh && isNum(r.noise_1sigma_deg) ? `±${r.noise_1sigma_deg.toFixed(2)}°` : UNKNOWN);
  const cal = st && st.calibration;
  setVal("calState", !st ? UNKNOWN : cal.active ? `applied (${cal.backend || "?"})` : "not calibrated");
  const res = cal && cal.params && (cal.params.residual_rms_uT ?? cal.params.residual_rms);
  setVal("calResidual", isNum(res) ? `${res.toFixed(3)} µT rms` : UNKNOWN);
  const simErr = fresh && r.source === "sim" ? r.sim_error_deg : null;
  $("simErrRow").style.display = fresh && r.source !== "sim" ? "none" : "";
  setVal("simErr", isNum(simErr) ? fmtSigned(simErr, 2) : UNKNOWN);
  const wl = $("warnings"); wl.innerHTML = "";
  const warns = fresh ? (r.warnings || []) : null;
  const addLi = (t, cls) => { const li = document.createElement("li"); li.textContent = t; if (cls) li.className = cls; wl.appendChild(li); };
  if (!warns) addLi(UNKNOWN, "muted");
  else if (!warns.length && !r.error) addLi("none", "muted");
  else { warns.forEach((w) => addLi(w)); if (r.error) addLi(r.error); }

  // attitude
  const roll = fresh ? r.roll_deg : null, pitch = fresh ? r.pitch_deg : null;
  drawHorizon(roll, pitch);
  setVal("rollValue", fmtNum(roll, 1, "°")); setVal("pitchValue", fmtNum(pitch, 1, "°"));

  // GPS availability: status only, from the optional sample.gps object {fix, num_sat, hdop}; never coordinates
  const g = st && S.connected && fresh ? st.gps : null;
  const gps = g ? g.status : "unknown";
  const gp = $("gpsStatus"); gp.textContent = gps === "available" ? "Available" : gps === "unavailable" ? "Unavailable" : UNKNOWN;
  gp.className = "pill " + (gps === "available" ? "ok" : gps === "unavailable" ? "fault" : "unknown");
  setVal("gpsFix", g && g.fix && g.fix !== "unknown" ? (g.fix === "none" ? "No fix" : g.fix.toUpperCase()) : UNKNOWN);
  setVal("gpsSats", g && isNum(g.num_sat) ? String(g.num_sat) : UNKNOWN);
  setVal("gpsHdop", g && isNum(g.hdop) ? g.hdop.toFixed(1) : UNKNOWN);
  if (st) $("gpsNote").textContent = "This app shows heading only. Heading is orientation, not movement or position. " +
    st.gps.note + (g && g.error ? " Last gps object was invalid: " + g.error : "");

  // field
  const mag = fresh ? r.mag_uT : null;
  ["bx", "by", "bz"].forEach((k, i) => setVal(k, mag ? mag[i].toFixed(2) + " µT" : UNKNOWN));
  const mr = fresh && Array.isArray(r.mag_raw) ? r.mag_raw : null;   // absent on CAN-L4-3100 / DroneCAN
  setVal("magRaw", mr ? mr.join(", ") + (isNum(r.rm3100_cycle_count) ? ` (CC ${r.rm3100_cycle_count})` : "") : UNKNOWN);
  setVal("bmag", fresh ? fmtNum(r.field_raw_uT, 2, " µT") : UNKNOWN);
  setVal("bmagCal", !fresh ? UNKNOWN : r.calibrated ? fmtNum(r.field_uT, 2, " µT") : "n/a (not calibrated)", !fresh || !r.calibrated);

  // charts
  const now = Date.now() + (st ? st.server_time_ms - S.statusAt : 0), win = +$("windowSel").value;
  const recs = S.records, pick = (f) => recs.map((x) => [x.recv_ms, f(x)]);
  drawChart($("fieldChart"), [
    { data: pick((x) => x.mag_uT && x.mag_uT[0]), color: "#ff6b6b" },
    { data: pick((x) => x.mag_uT && x.mag_uT[1]), color: "#4ade80" },
    { data: pick((x) => x.mag_uT && x.mag_uT[2]), color: "#60a5fa" },
    { data: pick((x) => x.field_raw_uT), color: "#e5e7eb", width: 2 }], { now, windowS: win });
  drawChart($("headingChart"), [
    { data: pick((x) => x.truth_heading_deg), color: "#b38cff", dash: [3, 3], wrap: true },
    { data: pick((x) => x.reference_deg), color: "#ffb547", dash: [7, 5], wrap: true },
    { data: pick((x) => x.heading_raw_deg), color: "#7f8ea3", wrap: true },
    { data: pick((x) => x.heading_deg), color: "#38d6ff", width: 2, wrap: true }],
    { now, windowS: win, y: [0, 360], yTicks: [0, 90, 180, 270, 360] });

  renderTable();
  renderPanels();
  S.renders++; S.renderedSeq = r ? r.seq : 0;
  requestAnimationFrame(render);
}

function cell(v, fmt) { return isNum(v) ? `<td>${fmt(v)}</td>` : `<td class="unk">${UNKNOWN}</td>`; }
function renderTable() {
  const rows = S.records.slice(-20).reverse().map((x) => {
    const m = x.mag_uT || [];
    return `<tr><td>${new Date(x.recv_ms).toLocaleTimeString([], { hour12: false })}.${String(Math.floor(x.recv_ms % 1000)).padStart(3, "0")}</td>` +
      `<td>${(badgeInfo(x.source, x.original_source, x.transport, x.device_verified) || {}).text || x.source}</td>` + cell(x.heading_deg, (v) => roundHeading(v).toFixed(1)) +
      cell(x.heading_raw_deg, (v) => roundHeading(v).toFixed(1)) + cell(x.reference_deg, (v) => v.toFixed(1)) +
      cell(x.deviation_deg, (v) => v.toFixed(1)) + cell(m[0], (v) => v.toFixed(2)) + cell(m[1], (v) => v.toFixed(2)) +
      cell(m[2], (v) => v.toFixed(2)) + cell(x.field_raw_uT, (v) => v.toFixed(2)) + cell(x.quality, (v) => v.toFixed(2)) +
      `<td>${x.sensor_status}</td>` + (x.gps_fix && x.gps_fix !== "unknown" ? `<td>${x.gps_fix}</td>` : `<td class="unk">${UNKNOWN}</td>`) + `</tr>`;
  });
  $("samplesTable").tBodies[0].innerHTML = rows.join("") || `<tr><td colspan="13" class="unk">No samples received</td></tr>`;
}

function fmtCal(c) {
  const f = (v) => isNum(v) ? v.toFixed(3) : String(v);
  return Object.entries(c).map(([k, v]) => Array.isArray(v)
    ? `${k}: ` + (Array.isArray(v[0]) ? "\n" + v.map((r) => "  [" + r.map(f).join(", ") + "]").join("\n") : "[" + v.map(f).join(", ") + "]")
    : `${k}: ${f(v)}`).join("\n");
}
function renderPanels() {
  const st = S.status; if (!st) return;
  const w = st.wizard;
  $("calN").textContent = `${w.n} / ${w.target}${w.collecting ? " (collecting…)" : ""}`;
  $("calProgress").style.width = Math.min(100, w.n / w.target * 100) + "%";
  $("calBins").textContent = `${w.heading_bins_covered}/${w.heading_bins_total}`;
  $("calOct").textContent = `${w.octants_covered}/${w.octants_total}`;
  $("calStart").classList.toggle("active", w.collecting);
  $("calApply").disabled = !w.result;
  const pre = $("calResult");
  const txt = w.error ? "Fit failed: " + w.error :
    w.result ? `Fitted by: ${w.result_backend}\n` + fmtCal(w.result) : "No fit yet.";
  if (pre.textContent !== txt) pre.textContent = txt;
  const rec = st.recording;
  $("recState").textContent = rec ? `${rec.name} · ${rec.samples} samples` : "off";
  $("recStop").disabled = !rec; $("recCsv").disabled = !!rec; $("recJsonl").disabled = !!rec;
  $("pauseBtn").textContent = st.paused ? "Resume intake" : "Pause intake";
  $("pauseBtn").classList.toggle("active", st.paused);
  $("intakeState").textContent = st.paused ? "PAUSED (test)" : st.dropout_remaining_s > 0 ? `dropout ${st.dropout_remaining_s.toFixed(1)} s (test)` : "normal";
  $("lastError").textContent = st.last_error || "none";
}

// ---------------------------------------------------------------- actions
async function post(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
const msg = (t) => { $("calMsg").textContent = t; };
function setReference(deg) { post("/api/reference", { deg }).catch((e) => alert(e.message)); }
async function refreshLists() {
  const [c, r] = await Promise.all([fetch("/api/calib/list").then((x) => x.json()), fetch("/api/recordings").then((x) => x.json())]);
  const sel = $("calFiles"), cur = sel.value;
  sel.innerHTML = `<option value="">saved files…</option>` + c.files.map((f) => `<option>${f}</option>`).join("");
  sel.value = cur;
  $("recList").innerHTML = r.files.slice(-10).reverse().map((f) => `<li><a href="/recordings/${encodeURIComponent(f.name)}" download>${f.name}</a> <span class="muted">${(f.bytes / 1024).toFixed(1)} KB</span></li>`).join("") || `<li class="muted">no recordings yet</li>`;
}

function wire() {
  $("refSet").onclick = () => { const v = parseFloat($("refNumber").value); if (isNum(v)) setReference(wrap360(v)); };
  $("refNumber").onkeydown = (e) => { if (e.key === "Enter") $("refSet").click(); };
  $("refSlider").oninput = (e) => setReference(+e.target.value);
  $("refUseCurrent").onclick = () => { const r = latest(); if (isFresh() && r && isNum(r.heading_deg)) setReference(Math.round(r.heading_deg * 10) / 10 % 360); };
  $("refClear").onclick = () => setReference(null);
  $("calStart").onclick = () => post("/api/calib/start", { target: 300 }).then(() => msg("Collecting: rotate the sensor through all orientations.")).catch((e) => msg(e.message));
  $("calStop").onclick = () => post("/api/calib/stop").catch((e) => msg(e.message));
  $("calFit").onclick = () => post("/api/calib/fit").then((j) => msg(`Fit OK (${j.backend}). Review, then Apply.`)).catch((e) => msg("Fit failed: " + e.message));
  $("calApply").onclick = () => post("/api/calib/apply").then(() => msg("Calibration applied.")).catch((e) => msg(e.message));
  $("calClear").onclick = () => post("/api/calib/clear").then(() => msg("Calibration removed; raw field in use.")).catch((e) => msg(e.message));
  $("calSave").onclick = () => post("/api/calib/save", { name: $("calName").value }).then((j) => { msg("Saved app/calibrations/" + j.file); refreshLists(); }).catch((e) => msg(e.message));
  $("calLoad").onclick = () => { const n = $("calFiles").value; if (n) post("/api/calib/load", { name: n }).then(() => msg("Loaded " + n)).catch((e) => msg(e.message)); };
  $("calUpload").onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    try { await post("/api/calib/load", { doc: JSON.parse(await f.text()) }); msg("Loaded " + f.name); } catch (err) { msg("Load failed: " + err.message); }
    e.target.value = "";
  };
  $("recCsv").onclick = () => post("/api/record/start", { format: "csv" }).then(refreshLists);
  $("recJsonl").onclick = () => post("/api/record/start", { format: "jsonl" }).then(refreshLists);
  $("recStop").onclick = () => post("/api/record/stop").then(refreshLists);
  $("pauseBtn").onclick = () => post("/api/control", { paused: !(S.status && S.status.paused) });
  $("dropoutBtn").onclick = () => post("/api/control", { dropout_s: 5 });
  setInterval(refreshLists, 5000); refreshLists();
}

buildCompass(); wire(); connect(); requestAnimationFrame(render);
setInterval(() => { S.dirty = true; }, 250); // re-evaluate staleness even with no new data
