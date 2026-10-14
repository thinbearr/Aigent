const $ = (s, r = document) => r.querySelector(s);
const NS = "http://www.w3.org/2000/svg";
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const J = (url, opt) => fetch(url, opt).then((r) => r.json());
const POST = (url, body) => J(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });

const VIEWS = ["home", "investigate", "report", "compare", "red", "gateway", "eval"];
const PHASES = [["alert", "Alert"], ["investigate", "Investigate"], ["challenge", "Challenge"], ["verify", "Verify"], ["reconstruct", "Reconstruct"], ["report", "Report"], ["review", "Review"]];
const PHASE_TITLE = { alert: "Alert received", investigate: "Blue Agent investigates", challenge: "Critic challenges the verdict", verify: "Checks requested by the Critic",
  reconstruct: "Forensics reconstructs the incident", report: "Verdict and report", review: "Human review" };
const KIND_LABEL = { tool: "tool call", evidence: "evidence", hypothesis: "confidence", challenge: "challenge", graph: "evidence graph", timeline: "timeline", verdict: "verdict", alert: "alert", report: "report", error: "error" };
const ROSTER = [["Orchestrator", "O", "#5b6470"], ["Blue", "B", "#1e66c1"], ["Critic", "C", "#d9730d"], ["Forensics", "F", "#6b4c9a"], ["Red", "R", "#c8102e"]];
const COLOR = Object.fromEntries(ROSTER.map((r) => [r[0].toUpperCase(), r[2]]));

// 24x24 line icons per asset type
const ICON = {
  gateway: "M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z M9 12l2 2 4-4",
  workstation: "M3 4h18v12H3z M8 20h8 M12 16v4",
  server: "M4 4h16v6H4z M4 14h16v6H4z M7 7h.01 M7 17h.01",
  hmi: "M3 5h18v11H3z M9 20h6 M12 16v4 M7 9h10 M7 12h6",
  plc: "M7 7h10v10H7z M9 3v4 M15 3v4 M9 17v4 M15 17v4 M3 9h4 M3 15h4 M17 9h4 M17 15h4",
  rtu: "M5 18h14v3H5z M12 18V9 M8 12a5.7 5.7 0 0 1 8 0 M5.5 9.5a9.5 9.5 0 0 1 13 0",
  process: "M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0-8z M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M19 5l-2 2 M7 17l-2 2",
  internet: "M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18z M3 12h18 M12 3c3 3 3 15 0 18 M12 3c-3 3-3 15 0 18",
};

let cfg, topo, state, selectedCase = "S2";
function fresh() { state = { runId: null, next: 0, timer: null, critic: true, evidence: [], timeline: [], report: null, prelim: null, overturned: false, revealHTML: "", statusText: "", audit: state ? state.audit : [] }; }
fresh();

// ───────────────────────── routing
const go = (v) => { location.hash = "#/" + v; };
function route() {
  const v = location.hash.replace("#/", "") || "home", view = VIEWS.includes(v) ? v : "home";
  document.querySelectorAll(".view").forEach((x) => x.classList.toggle("on", x.id === "v-" + view));
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.v === view));
  if (view === "report") renderReport();
  if (view === "gateway") renderGateway();
  $("#main").scrollTop = 0; document.querySelectorAll(".view.on").forEach((x) => (x.scrollTop = 0));
}

// ───────────────────────── init
async function init() {
  cfg = await J("/api/config"); topo = cfg.topology;
  buildCases(cfg.scenarios); buildMap(); buildStepper(); buildRoster(); bootFeed(); renderReport(); renderGateway();
  document.querySelectorAll("[data-go]").forEach((b) => (b.onclick = () => go(b.dataset.go)));
  $("#heroCompare").onclick = () => { selectCase("S2"); go("compare"); runCompare(); };
  $("#run").onclick = startRun; $("#pause").onclick = togglePause; $("#reset").onclick = () => resetUI();
  $("#notes").onchange = () => document.body.classList.toggle("nonotes", !$("#notes").checked);
  $("#critic").onchange = syncCritic; syncCritic();
  $("#themeBtn").onclick = toggleTheme;
  $("#cmpRun").onclick = runCompare; $("#redRun").onclick = runRed; $("#probeRun").onclick = runProbe; $("#evalRun").onclick = runEval;
  $("#cmpCase").onchange = () => selectCase($("#cmpCase").value);
  window.addEventListener("hashchange", route); route();
  tick(); setInterval(tick, 1000);
  const q = new URLSearchParams(location.search);   // handy for demos: ?case=S2&critic=0&speed=fast  |  ?compare=S2  |  ?eval=1  |  ?view=gateway
  if (q.get("case")) { selectCase(q.get("case")); $("#critic").checked = q.get("critic") !== "0"; syncCritic(); if (q.get("speed")) $("#speed").value = q.get("speed"); go("investigate"); startRun(); }
  else if (q.get("compare")) { selectCase(q.get("compare")); go("compare"); runCompare(); }
  else if (q.get("eval")) { go("eval"); runEval(); }
  else if (q.get("view")) go(q.get("view"));
}
function toggleTheme() {
  const dark = document.documentElement.getAttribute("data-theme") !== "dark";
  if (dark) document.documentElement.setAttribute("data-theme", "dark"); else document.documentElement.removeAttribute("data-theme");
  try { localStorage.setItem("ica_theme", dark ? "dark" : "light"); } catch (e) { /* storage may be blocked */ }
}
const tick = () => ($("#clock").textContent = new Date().toISOString().slice(11, 19) + " UTC");
function syncCritic() {
  const on = $("#critic").checked;
  $("#criticLabel").textContent = on ? "Critic Agent on (System D)" : "Critic Agent off (System C)";
  const r = document.querySelectorAll(".rrow")[2]; if (r) { r.classList.toggle("off", !on); r.querySelector("em").textContent = on ? "idle" : "disabled"; }
}
function buildCases(list) {
  const box = $("#scnCards"), sel = $("#cmpCase");
  list.forEach((s, i) => {
    const title = s.name.split("·")[1].trim();
    const el = document.createElement("div"); el.className = "cb"; el.dataset.id = s.id; el.dataset.sum = s.summary;
    el.innerHTML = `<i>0${i + 1}</i><span>${esc(title)}</span>`; el.onclick = () => selectCase(s.id); box.appendChild(el);
    const o = document.createElement("option"); o.value = s.id; o.textContent = `0${i + 1} · ${title}`; sel.appendChild(o);
  });
  selectCase(selectedCase);
}
function selectCase(id) {
  selectedCase = id;
  document.querySelectorAll(".cb").forEach((c) => c.classList.toggle("sel", c.dataset.id === id));
  const c = document.querySelector(`.cb[data-id="${id}"]`); if (c) $("#alertLine").innerHTML = `<b>Case alert:</b> ${esc(c.dataset.sum.replace(/^Alert:\s*/, ""))}`;
  $("#cmpCase").value = id;
}
function setRunState(txt, cls) { $("#runState").innerHTML = `<i class="sq ${cls || ""}"></i>Run: <b>${txt}</b>`; }

// ───────────────────────── plant map
const pos = (id) => (id === "EXTERNAL" ? topo.external : topo.assets[id]);
const svgEl = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
const adjacent = (a, b) => topo.edges.some(([x, y]) => (x === a && y === b) || (x === b && y === a)) || (a === "EXTERNAL" && b === "VPN-GW");
function buildMap() {
  const svg = $("#map"); svg.innerHTML = "";
  const defs = svgEl("defs", {}, svg);
  [["arrBad", "#c8102e"], ["arrOk", "#2e7d4f"]].forEach(([id, c]) => {
    const m = svgEl("marker", { id, viewBox: "0 0 10 10", refX: 8, refY: 5, markerWidth: 5, markerHeight: 5, orient: "auto-start-reverse" }, defs);
    svgEl("path", { d: "M0 0L10 5L0 10z", class: id === "arrBad" ? "arr bad" : "arr ok" }, m);
  });
  [[62, "DMZ · IT"], [177, "OT"], [292, "CONTROL"]].forEach(([y, l]) => {
    svgEl("rect", { class: "lane", x: 6, y, width: 508, height: 76, rx: 2 }, svg);
    svgEl("rect", { class: "lanetab", x: 6, y, width: 16, height: 76, rx: 2 }, svg);
    svgEl("text", { class: "lanelabel", x: 14, y: y + 38, transform: `rotate(-90 14 ${y + 38})` }, svg).textContent = l;
  });
  [...topo.edges, ["EXTERNAL", "VPN-GW"]].forEach(([a, b]) => {
    const p = pos(a), q = pos(b);
    svgEl("line", { class: "base", x1: p.x, y1: p.y, x2: q.x, y2: q.y, "stroke-dasharray": a === "EXTERNAL" ? "2 7" : "" }, svg);
    if (a !== "EXTERNAL") svgEl("line", { class: "basein", x1: p.x, y1: p.y, x2: q.x, y2: q.y }, svg);
  });
  svgEl("g", { id: "overlay" }, svg);
  const mk = (id, p, label, sub, icon) => {
    const g = svgEl("g", { class: "node", id: "n-" + id }, svg);
    svgEl("rect", { x: p.x - 62, y: p.y - 23, width: 124, height: 46, rx: 3 }, g);
    svgEl("path", { class: "ico", d: ICON[icon], transform: `translate(${p.x - 54} ${p.y - 12}) scale(.95)` }, g);
    svgEl("text", { class: "id", x: p.x - 24, y: p.y - 3 }, g).textContent = label;
    svgEl("text", { class: "lb", x: p.x - 24, y: p.y + 12 }, g).textContent = sub;
  };
  mk("EXTERNAL", topo.external, "INTERNET", "untrusted", "internet");
  Object.entries(topo.assets).forEach(([id, a]) => mk(id, a, id, a.label, a.type));
}
const flash = (id) => { const n = $("#n-" + id); if (n) n.classList.add("touched"); };
const flashAlert = (a) => { const n = $("#n-" + a); if (n) n.classList.add("alert", "touched"); };
function drawGraph(edges, incident) {
  const ov = $("#overlay"); ov.innerHTML = "";
  const groups = {};
  edges.forEach((e) => { const k = e.src + ">" + e.dst; (groups[k] = groups[k] || { src: e.src, dst: e.dst, labels: [], refs: [] }); groups[k].labels.push(e.label); groups[k].refs.push(...e.refs.filter((r) => r.startsWith("E-"))); });
  const cls = incident ? "bad" : "ok", col = incident ? "#c8102e" : "#2e7d4f";
  Object.values(groups).forEach((g) => {
    const p1 = pos(g.src), p2 = pos(g.dst); if (!p1 || !p2) return;
    const dx = p2.x - p1.x, dy = p2.y - p1.y, len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len, horiz = Math.abs(dx) > Math.abs(dy);
    const x1 = p1.x + ux * (horiz ? 64 : 26), y1 = p1.y + uy * (horiz ? 0 : 26), x2 = p2.x - ux * (horiz ? 64 : 26), y2 = p2.y - uy * (horiz ? 0 : 26);
    const off = adjacent(g.src, g.dst) ? 0 : 55, mx = (x1 + x2) / 2 - uy * off, my = (y1 + y2) / 2 + ux * off;
    svgEl("path", { class: "ov " + cls, d: `M${x1} ${y1} Q${mx} ${my} ${x2} ${y2}`, "marker-end": `url(#${incident ? "arrBad" : "arrOk"})` }, ov);
    const lab = [...new Set(g.labels)].slice(0, 2).join(", ") + (g.refs.length ? " [" + [...new Set(g.refs)].slice(0, 2).join(",") + "]" : "");
    const cx = 0.25 * x1 + 0.5 * mx + 0.25 * x2, cy = 0.25 * y1 + 0.5 * my + 0.25 * y2, w = lab.length * 5.1 + 12;
    svgEl("rect", { class: "chipbg " + cls, x: cx - w / 2, y: cy - 8, width: w, height: 15, rx: 7 }, ov);
    svgEl("text", { class: "chiptx", x: cx, y: cy + 3 }, ov).textContent = lab;
  });
}

// ───────────────────────── process track, roster, meter
function buildStepper() { $("#stepper").innerHTML = PHASES.map(([k, l], i) => `<span data-p="${k}"><i>${i + 1}</i>${l}</span>`).join(""); }
function setPhase(name) {
  const idx = PHASES.findIndex((p) => p[0] === name);
  document.querySelectorAll("#stepper span").forEach((el, i) => {
    el.classList.remove("now", "done"); if (i < idx) el.classList.add("done"); if (i === idx) el.classList.add("now");
    el.querySelector("i").textContent = i < idx && !el.classList.contains("skip") ? "✓" : i + 1;
  });
}
function buildRoster() { $("#roster").innerHTML = ROSTER.map(([n, l, c]) => `<div class="rrow" data-a="${n.toUpperCase()}" style="--c:${c}"><div class="sq">${l}</div><div><b>${n}</b><em>idle</em></div></div>`).join(""); }
let activeTimer;
function setActive(agent) {
  const a = agent.toUpperCase(), off = !$("#critic").checked;
  const idle = (r) => (r.dataset.a === "CRITIC" && off ? "disabled" : "idle");
  document.querySelectorAll(".rrow").forEach((r) => { const on = r.dataset.a === a; r.classList.toggle("on", on); r.querySelector("em").textContent = on ? "working" : idle(r); });
  clearTimeout(activeTimer);
  activeTimer = setTimeout(() => document.querySelectorAll(".rrow").forEach((r) => { r.classList.remove("on"); r.querySelector("em").textContent = idle(r); }), 2200);
}
function setGauge(conf, final, incident) {
  $("#confNum").textContent = conf.toFixed(2); $("#confNum").style.color = final ? (incident ? "var(--red)" : "var(--green)") : "";
  const f = $("#confFill"); f.style.width = conf * 100 + "%"; f.className = "fill" + (final ? (incident ? " inc" : " ok") : "");
}
function setPrelim(p) { const m = $("#confPrelim"); m.style.display = "block"; m.style.left = p * 100 + "%"; }

// ───────────────────────── event journal
function bootFeed() {
  $("#feed").innerHTML = `<div class="boot"><div>Sandbox network isolated.</div><div>Tool gateway online, allow-lists loaded.</div><div>5 agents ready: Orchestrator, Blue, Critic, Forensics, Red.</div><div>Pick a case above, then press <b>Run investigation</b>.</div></div>`;
}
function addFeed(s) {
  const d = s.data || {}, c = COLOR[s.agent.toUpperCase()] || "#c8102e";
  const el = document.createElement("div");
  el.className = `row k-${s.kind}` + (s.kind === "verdict" && d.incident ? " inc" : ""); el.style.setProperty("--c", c);
  let body = esc(s.text);
  if (s.kind === "evidence") { const w = d.evidence.weight; body = `<span class="chip ${w > 0 ? "pos" : "neg"}">${w > 0 ? "+" : ""}${w.toFixed(1)}</span> ${esc(s.text)} <span class="mono" style="color:var(--muted)">${d.evidence.id}</span>`; }
  const label = KIND_LABEL[s.kind];
  el.innerHTML = `<div class="n">${s.n}</div><div class="ag"><span class="tag" style="--c:${c}">${esc(s.agent)}</span></div><div class="tx">${label ? `<span class="k">${label}</span>` : ""}${body}${s.why ? `<div class="why">${esc(s.why)}</div>` : ""}</div>`;
  $("#feed").appendChild(el); $("#feed").scrollTop = $("#feed").scrollHeight;
}

// ───────────────────────── run control
async function startRun() {
  resetUI(); state.critic = $("#critic").checked; $("#feed").innerHTML = "";
  const r = await POST("/api/run", { scenario: selectedCase, critic: state.critic, speed: $("#speed").value });
  state.runId = r.run_id; $("#run").disabled = true; $("#pause").disabled = false; setRunState("investigating", "run");
  if (!state.critic) document.querySelectorAll('#stepper [data-p="challenge"],#stepper [data-p="verify"]').forEach((e) => e.classList.add("skip"));
  state.timer = setInterval(poll, 250);
}
function resetUI() {
  clearInterval(state.timer); fresh();
  buildMap(); buildStepper(); bootFeed(); renderReport();
  $("#banner").className = "banner"; $("#confNum").textContent = "–"; $("#confNum").style.color = ""; $("#confFill").style.width = "0"; $("#confFill").className = "fill"; $("#confPrelim").style.display = "none";
  $("#confNote").textContent = "Setpoint 0.60. At or above it, the system declares an incident.";
  $("#run").disabled = false; $("#pause").disabled = true; $("#pause").textContent = "Pause"; setRunState("idle", ""); syncCritic();
}
async function togglePause() {
  if (!state.runId) return;
  const r = await POST(`/api/run/${state.runId}/pause`); $("#pause").textContent = r.paused ? "Resume" : "Pause"; setRunState(r.paused ? "paused" : "investigating", r.paused ? "wait" : "run");
}
async function poll() {
  if (!state.runId) return;
  const r = await J(`/api/run/${state.runId}?since=${state.next}`);
  r.steps.forEach(handle); state.next = r.next;
  if (["awaiting_review", "reviewed", "error"].includes(r.status) && !r.steps.length) { clearInterval(state.timer); $("#run").disabled = false; $("#pause").disabled = true; }
}

// ───────────────────────── step handling
function handle(s) {
  const d = s.data || {};
  if (s.kind === "phase") {
    setPhase(d.phase);
    const sep = document.createElement("div"); sep.className = "sep"; sep.textContent = PHASE_TITLE[d.phase] || d.phase;
    $("#feed").appendChild(sep); $("#feed").scrollTop = $("#feed").scrollHeight; return;
  }
  setActive(s.agent);
  if (s.kind === "alert") flashAlert(d.asset);
  if (s.kind === "tool") { (d.assets || []).forEach(flash); state.audit.push(d.audit); }
  if (s.kind === "evidence") state.evidence.push(d.evidence);
  if (s.kind === "hypothesis") setGauge(d.confidence, false);
  if (s.kind === "message" && d.prelim !== undefined) { state.prelim = d.prelim; setPrelim(d.prelim); $("#confNote").innerHTML = `Orange marker: Blue Agent alone (<b>${d.prelim.toFixed(2)}</b>).`; }
  if (s.kind === "challenge" && d.overturned) { state.overturned = true; $("#confNote").innerHTML += " <b>The Critic overturned it.</b>"; }
  if (s.kind === "timeline") state.timeline = d.timeline;
  if (s.kind === "graph") drawGraph(d.edges, d.incident);
  if (s.kind === "verdict") {
    setGauge(d.confidence, true, d.incident);
    d.assets.forEach((a) => { const n = $("#n-" + a); if (n) { n.classList.remove("alert", "touched"); n.classList.add(d.incident ? "compromised" : "benign"); } });
    showVerdict(d.incident, d.confidence, state.overturned);
  }
  if (s.kind === "report") { state.report = d.report; state.statusText = d.report.status; setRunState("awaiting review", "wait"); renderReport(); }
  if (s.kind === "report" && new URLSearchParams(location.search).get("then")) setTimeout(() => go(new URLSearchParams(location.search).get("then")), 600);
  addFeed(s);
}
function showVerdict(incident, conf, overturned) {
  const b = $("#banner"); b.className = "banner show " + (incident ? "inc" : "ok");
  b.innerHTML = `<b>${incident ? "Incident confirmed" : "False alarm cleared"}</b><span>Confidence ${conf.toFixed(2)} · ${incident ? "escalate to an analyst" : "the activity was authorised"}</span>${overturned ? "<em>Critic overturned the first verdict</em>" : ""}<button id="openRep">Open full report →</button>`;
  $("#openRep").onclick = () => go("report");
}

// ───────────────────────── report page
function renderReport() {
  const box = $("#reportBody"), r = state.report;
  if (!r) { box.innerHTML = `<div class="emptybox"><b>No report yet.</b><div>Run an investigation first. The report appears here when it finishes.</div><button class="primary" data-go="investigate" id="goInv">Go to Investigate</button></div>`; $("#goInv").onclick = () => go("investigate"); return; }
  const mitre = r.mitre.length ? `<table><tr><th>Technique</th><th>Name</th><th>Evidence</th></tr>${r.mitre.map((m) => `<tr><td class="mono">${m.id}</td><td>${m.name}</td><td class="mono">${m.evidence.join(", ")}</td></tr>`).join("")}</table><div class="note">Indicative mapping to MITRE ATT&amp;CK for ICS.</div>` : '<div class="kv">None: no malicious technique identified.</div>';
  const alts = r.alternatives.length ? `<table><tr><th>Alternative the Critic raised</th><th>Outcome</th></tr>${r.alternatives.map((a) => `<tr><td>${a.id}: ${esc(a.name)}</td><td>${esc(a.outcome)}</td></tr>`).join("")}</table>` : '<div class="kv">None: the Critic was off, so no alternative explanation was tested.</div>';
  const ev = `<table><tr><th>ID</th><th>Evidence</th><th>Source</th><th>Weight</th><th>Linked events</th></tr>` + state.evidence.map((e) => `<tr><td class="mono">${e.id}</td><td>${esc(e.text)}</td><td>${e.source === "check" ? "verification check" : "log observation"}</td><td><span class="chip ${e.weight > 0 ? "pos" : "neg"}">${e.weight > 0 ? "+" : ""}${e.weight.toFixed(1)}</span></td><td class="mono">${e.events.join(", ") || "-"}</td></tr>`).join("") + `</table><div class="note">Red (+) supports a malicious incident; green (−) supports a benign explanation. Weights are hand-set in Phase 1.</div>`;
  const tl = `<table><tr><th>Time</th><th>Asset</th><th>Event</th><th>Evidence</th></tr>` + state.timeline.map((t) => `<tr><td class="mono">${t.t}</td><td class="mono">${t.asset}</td><td>${esc(t.text)}</td><td class="mono">${t.evidence.join(", ")}</td></tr>`).join("") + "</table>";
  box.innerHTML = `<div class="report">
    <div class="rep-head"><span class="cls ${r.incident ? "inc" : "ok"}">${esc(r.classification)}</span><span class="kv">Incident <b>${r.incident_id}</b></span><span class="kv">Status <b id="repStatus">${esc(state.statusText || r.status)}</b></span></div>
    <p style="font-size:15px">${esc(r.summary)}</p>
    <div class="stats">
      <div class="stat d"><div class="sn" style="color:var(${r.incident ? "--red" : "--green"})">${r.confidence.toFixed(2)}</div><div class="sl">Final confidence of a malicious incident</div></div>
      <div class="stat"><div class="sn">${state.prelim !== null && r.critic_enabled ? state.prelim.toFixed(2) : "–"}</div><div class="sl">${r.critic_enabled ? "Blue Agent alone, before the Critic" : "Critic was off for this run"}</div></div>
      <div class="stat"><div class="sn">${r.evidence.length}<span style="font-size:16px;color:var(--muted)"> evidence · ${r.tool_calls} tool calls</span></div><div class="sl">Critic ${r.critic_enabled ? "on (System D)" : "off (System C)"}</div></div>
    </div>
    <div class="reviewbar"><b>Analyst decision:</b><button class="primary" id="approve">Approve finding</button><button id="more">Request more investigation</button></div><div id="reveal">${state.revealHTML}</div>
    <div class="twocol"><div><h4>Affected assets</h4>${r.affected_assets.map((a) => `<span class="assetchip">${a}</span>`).join("")}
      <h4>Attack path</h4>${r.attack_path.length ? r.attack_path.map((a) => `<span class="assetchip">${a}</span>`).join(" → ") : '<span class="kv">n/a</span>'}
      <h4>Impact</h4><div>${esc(r.impact)}</div><h4>Alternative hypotheses</h4>${alts}</div>
      <div><h4>MITRE ATT&amp;CK for ICS</h4>${mitre}<h4>Recommended actions</h4><ul>${r.actions.map((a) => `<li>${esc(a)}</li>`).join("")}</ul></div></div>
    <h4>Evidence</h4>${ev}<h4>Timeline</h4>${tl}</div>`;
  $("#approve").onclick = () => review("approve"); $("#more").onclick = () => review("request_more");
}
async function review(decision) {
  const r = await POST(`/api/run/${state.runId}/review`, { decision });
  state.statusText = decision === "approve" ? "Approved by analyst" : "Sent back for more investigation";
  state.revealHTML = `<div class="reveal"><b>Ground truth revealed:</b> ${esc(r.truth_summary)}<br>System verdict was <b class="${r.correct ? "good" : "bad"}">${r.correct ? "CORRECT" : "WRONG"}</b> (Critic ${state.critic ? "on" : "off"}).
    ${r.inspired_by ? `<br><span class="kv">Inspired by: ${esc(r.inspired_by)}</span>` : ""}<br><span class="kv">${esc(r.note)}</span></div>`;
  setPhase("review"); setRunState("reviewed", "done"); renderReport();
}

// ───────────────────────── compare / red / gateway / eval pages
async function runCompare() {
  $("#cmpOut").innerHTML = '<div class="empty">Running the same case twice…</div>';
  const r = await J("/api/compare?scenario=" + selectedCase);
  const side = (k, title, x, cls) => {
    const col = x.incident ? "var(--red)" : "var(--green)";
    return `<div class="side2 ${cls}"><div class="ttl">${title}</div><div class="verd" style="color:${col}">${x.incident ? "INCIDENT" : "NO INCIDENT"}</div>
      <div class="bar"><div class="f" data-w="${x.confidence * 100}" style="background:${col}"></div><div class="t"></div>${x.prelim !== null && k === "D" ? `<div class="p" style="left:${x.prelim * 100}%"></div>` : ""}</div>
      <div class="kv">confidence ${x.confidence.toFixed(2)} · setpoint 0.60${x.prelim !== null && k === "D" ? ` · orange marker = Blue alone (${x.prelim.toFixed(2)})` : ""}</div>
      <div class="meta"><span>evidence <b>${x.evidence}</b></span><span>tool calls <b>${x.tool_calls}</b></span></div>
      <div class="res ${x.correct ? "good" : "bad"}">${x.correct ? "✓ CORRECT" : "✗ WRONG"} vs ground truth</div></div>`;
  };
  $("#cmpOut").innerHTML = `<h3 class="sh" style="margin-top:4px">${esc(r.name)}</h3><div class="kv" style="margin-bottom:12px">Ground truth: <b>${r.truth_incident ? "real incident" : "benign activity"}</b>. ${esc(r.truth_summary)}</div>
    <div class="h2h">${side("C", "System C · Agents without Critic", r.C, "")}${side("D", "System D · With Critic Agent", r.D, "d")}</div>
    <div class="note" style="margin-top:14px">Five scripted cases demonstrate the mechanism; they are not a measure of real-world accuracy.</div>`;
  setTimeout(() => document.querySelectorAll(".bar .f").forEach((f) => (f.style.width = f.dataset.w + "%")), 120);
}
async function runRed() {
  $("#redOut").innerHTML = '<div class="empty">Running…</div>';
  const r = await POST("/api/red"); state.audit.push(...r.audit);
  $("#redOut").innerHTML = `<div class="note" style="margin:0 0 10px">${r.findings.length} findings from ${r.audit.length} read-only tool calls, all logged by the gateway.</div>` +
    `<table><tr><th>Severity</th><th>Asset</th><th>Setting</th><th>Finding</th></tr>${r.findings.map((f) => `<tr><td><span class="chip ${f.severity}">${f.severity}</span></td><td class="mono">${f.asset}</td><td class="mono">${f.setting} = ${f.value}</td><td>${esc(f.finding)}</td></tr>`).join("")}</table>`;
}
function renderGateway() {
  if (!cfg) return;
  const allowed = cfg.allowed || {};
  const tools = (a) => ((allowed[a] || []).length ? allowed[a].map((t) => `<span class="assetchip">${t}</span>`).join("") : '<span class="kv">none: this agent cannot touch the plant</span>');
  $("#gwMatrix").innerHTML = `<table class="mx"><tr><th>Agent</th><th>Allowed tools</th></tr>${ROSTER.map(([n]) => `<tr><td><span class="tag" style="--c:${COLOR[n.toUpperCase()]}">${n}</span></td><td>${tools(n)}</td></tr>`).join("")}</table>`;
  $("#gwAudit").innerHTML = !state.audit.length ? '<div class="empty">No calls yet. Run an investigation or fire the forbidden actions.</div>' :
    `<table><tr><th>#</th><th>Agent</th><th>Tool</th><th>Arguments</th><th>Decision</th><th>Result</th></tr>` +
    state.audit.map((a, i) => `<tr><td>${i + 1}</td><td>${a.agent}</td><td class="mono">${a.tool}</td><td class="mono">${esc(JSON.stringify(a.args))}</td><td><span class="chip ${a.status === "ALLOWED" ? "allowed" : "denied"}">${a.status}</span></td><td>${esc(a.summary)}</td></tr>`).join("") + "</table>";
}
async function runProbe() { const r = await POST("/api/probe"); state.audit.push(...r.audit); renderGateway(); }
async function runEval() {
  $("#evalOut").innerHTML = '<div class="empty">Running 5 cases under 3 systems…</div>';
  const r = await J("/api/evaluate");
  const cell = (c, conf) => `<span class="${c.ok ? "good" : "bad"}">${c.flag ? "Incident" : "No incident"} ${c.ok ? "✓" : "✗"}</span>${conf !== undefined ? ` <span class="kv mono">${conf.toFixed(2)}</span>` : ""}`;
  const S = r.summary;
  $("#evalOut").innerHTML = `<div class="stats">
      <div class="stat"><b>A · Rule-based</b><div class="sn">${S.A.accuracy}</div><div class="sl">correct · false positives ${S.A.false_positives}</div></div>
      <div class="stat"><b>C · Agents, no Critic</b><div class="sn">${S.C.accuracy}</div><div class="sl">correct · false positives ${S.C.false_positives}</div></div>
      <div class="stat d"><b>D · Full system</b><div class="sn">${S.D.accuracy}</div><div class="sl">correct · false positives ${S.D.false_positives}</div></div></div>
    <h3 class="sh">Case by case</h3>
    <table><tr><th>Case</th><th>Truth</th><th>A · Rule-based</th><th>C · No Critic</th><th>D · With Critic</th></tr>` +
    r.rows.map((x) => `<tr><td>${esc(x.name)}</td><td>${x.truth ? "Incident" : "Benign"}</td><td>${cell(x.A)}</td><td>${cell(x.C, x.C.conf)}</td><td>${cell(x.D, x.D.conf)}</td></tr>`).join("") +
    ["detection", "false_positives", "accuracy"].map((m) => `<tr class="sumrow"><td>${{ detection: "Attacks detected", false_positives: "False positives (benign flagged)", accuracy: "Overall accuracy" }[m]}</td><td></td><td>${S.A[m]}</td><td>${S.C[m]}</td><td>${S.D[m]}</td></tr>`).join("") +
    `</table><div class="note"><b>Read carefully:</b> five scripted cases with hand-set evidence weights. This demonstrates the <i>mechanism</i> (a Critic that tests alternatives removes false positives). It is not a measure of real-world accuracy. System B (single LLM) is not built yet.</div>`;
}

init();
