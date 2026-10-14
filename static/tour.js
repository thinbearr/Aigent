/* Guided tour. Drives the real prototype (navigates, picks a case, toggles the Critic, runs simulations)
   and explains each part. Depends on the globals defined in app.js. */
(function () {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const has = (sel) => !!document.querySelector(sel);
  const rows = () => document.querySelectorAll("#feed .row").length;
  const COL = { Orchestrator: "#5b6470", Blue: "#1e66c1", Critic: "#d9730d", Forensics: "#6b4c9a", Red: "#c8102e", Gateway: "#2e7d4f", Human: "#8a6400" };

  const T = [
    { view: "home", title: "Welcome to Industrial Cyber-Arena", next: "Start the tour",
      body: "<p>This guide drives the real prototype for you and explains each part as it happens. You will watch a false alarm get raised and then corrected, meet every agent, and see exactly what each one can and cannot do.</p><p>It takes about six minutes. Use <b>Next</b>, <b>Back</b> or the arrow keys, and press <b>Esc</b> to leave at any time.</p>" },

    { view: "home", target: ".hero .casefile", place: "left", title: "The problem: alerts are not answers",
      body: "<p>Detection tools raise alerts in a plant, but a person still has to decide whether each one is real. That investigation is slow and manual, and a wrong call either misses an attack or wastes hours on a harmless event.</p><p>This card shows one case from start to finish: an alert, a first verdict, a doubt, and a corrected verdict. The rest of the tour shows how the agents produce it.</p>" },

    { view: "home", target: ".agents", place: "top", title: "Five agents, five jobs",
      body: "<p>The agents are the heart of the project. Each has one responsibility, and only some of them may touch the plant at all.</p>",
      tech: ["<b>Orchestrator</b>: plans the case and delegates. No tool access.", "<b>Blue</b>: reads logs through read-only tools and forms the first verdict.", "<b>Critic</b>: argues the other side and demands proof. No tool access.",
        "<b>Forensics</b>: rebuilds the timeline and attack path from cited evidence. Read-only tools.", "<b>Red</b>: checks the plant for weak settings. Read-only tools.",
        "Why split them? The agent that <i>judges</i> the evidence never <i>collects</i> it, so it cannot quietly bias the result."] },

    { view: "investigate", target: "#scnCards", place: "bottom", title: "Pick a case",
      action: async () => { resetUI(); state.audit = []; selectCase("S2"); },
      body: "<p>A case is a scripted alert plus a hidden ground truth that the system cannot see. <b>Case 02</b> looks like an attack: a privilege change followed by a PLC parameter change. We selected it.</p><p>Is it real? The agents do not know yet.</p>" },

    { view: "investigate", target: "#v-investigate .chk", place: "bottom", title: "First run: Critic off",
      action: async () => { $("#critic").checked = false; syncCritic(); },
      body: "<p>The Critic switch is off, so we first see what a single analyst does. This is <b>System C</b> in the evaluation. Next we will switch it on (<b>System D</b>) and run exactly the same case.</p>" },

    { view: "investigate", target: ".feedcol", place: "left", tag: "Orchestrator", title: "Orchestrator: the project manager",
      action: async () => { $("#speed").value = "normal"; await startRun(); }, until: () => rows() >= 2,
      body: "<p>The run has started. The first agent to speak is the Orchestrator. It reads the alert, sets the objective (<i>is this a real compromise?</i>) and plans the work: Blue investigates, the Critic challenges, Forensics reconstructs, a human reviews.</p>",
      tech: ["It has <b>no tool access</b>: it cannot read logs or touch the plant. It can only delegate.", "The case state (objective, evidence so far, confidence, status) lives with the run, so every agent works from the same facts.",
        "Phase 1 runs one challenge round. Later phases let it re-open a case as many times as the evidence demands."] },

    { view: "investigate", target: ".feedcol", place: "left", tag: "Blue", title: "Blue: the analyst", until: () => state.prelim !== null,
      body: "<p>Blue now reads the logs. It never touches the plant directly: every read is a <b>tool call through the gateway</b>. Watch the journal: tool calls such as <code>get_log_summary</code> and <code>query_events</code> are followed by evidence rows with a red <b>+</b> weight.</p>",
      tech: ["It starts from the alert's log source, then reads each source that has events.", "Every event goes through a signal rule, for example privilege escalation <code>+1.0</code>, PLC parameter changed <code>+1.0</code>, minor process deviation <code>+0.3</code>.",
        "Each finding gets an ID (<code>E-01</code>, <code>E-02</code>…) so later steps can cite it.", "By design Blue only collects <i>attack-looking</i> evidence. It is a single-pass analyst, like many real tools."] },

    { view: "investigate", target: ".strip .meter", place: "top", tag: "Blue", title: "How confidence is computed",
      body: "<p>Blue's findings add up to one number: the confidence that this is a malicious incident. Blue has just finished with a score above the setpoint, so its first verdict is <b>attack</b>.</p>",
      tech: ["<code>confidence = sigmoid((−1 + Σ weights) ÷ 2.5)</code>", "At or above the <b>0.60</b> setpoint the system declares an incident.", "The orange marker records Blue's confidence alone, so we can measure the Critic's effect later.",
        "Weights are hand-set in Phase 1: the numbers show the mechanism, not learned accuracy."] },

    { view: "investigate", target: ".mapwrap", place: "left", tag: "Forensics", title: "Forensics: the case-board artist", until: () => state.report !== null,
      body: "<p>Forensics now rebuilds the story and the system issues its verdict. Look at the map and the banner: with no Critic, the system declares an <b>incident</b>. But Case 02 was an authorised change, so this is a <b>false positive</b>.</p>",
      tech: ["It uses read-only tools and only the events that Blue's evidence cites.", "It builds a timeline and an <b>evidence graph</b>; every arrow on the map carries the evidence IDs behind it.", "It maps findings to <b>MITRE ATT&amp;CK for ICS</b> techniques, only when the verdict is an incident."] },

    { view: "investigate", target: "#v-investigate .chk", place: "bottom", tag: "Critic", title: "Now add the Critic", until: () => has("#feed .k-challenge"),
      action: async () => { $("#critic").checked = true; syncCritic(); await startRun(); },
      body: "<p>We switched the Critic on and restarted the same case. Same events, same Blue, same first verdict. Only one thing changed: the Critic is now allowed to speak before the verdict is final (<b>System D</b>).</p>" },

    { view: "investigate", target: ".feedcol", place: "left", tag: "Critic", title: "Critic: the sceptic",
      body: "<p>The amber row is the Critic. It does not look at the plant. It looks at Blue's evidence and asks: <i>what else could explain this?</i></p>",
      tech: ["From the evidence types it proposes <b>alternatives</b>: planned maintenance or an authorised change (ALT-1), a planned firmware update (ALT-2), an equipment fault (ALT-3), legitimate remote work (ALT-4).",
        "For each it lists the <b>checks</b> that would test it: maintenance schedule, user authorisation, firmware signature.", "It has no tool access, so Blue runs those checks through the gateway and the results become new evidence.",
        "Independence is the point: the judge never collects the evidence."] },

    { view: "investigate", target: ".mapwrap", place: "left", tag: "Critic", title: "Evidence flips the verdict", until: () => state.report !== null,
      body: "<p>The checks came back: a maintenance window exists for PLC-02 (ticket CHG-1042) and the engineer is authorised. Each is green, negative-weight evidence (<code>−3.0</code>), so confidence falls from <b>0.63 to 0.13</b>. The banner says the Critic overturned the first verdict.</p>",
      tech: ["Each alternative is judged <i>supported</i>, <i>rejected</i> or <i>inconclusive</i>. ALT-3 (equipment fault) is marked not testable in Phase 1.",
        "If the checks had failed (no ticket, unauthorised user, invalid firmware) the same loop would have <b>raised</b> confidence, as in the attack cases."] },

    { view: "report", target: ".stats", place: "bottom", title: "The report",
      body: "<p>Everything is written up for a human. The three numbers tell the story: final confidence, Blue alone before the Critic, and the effort in evidence items and tool calls.</p>",
      tech: ["Every timeline row and graph edge cites evidence IDs, so an analyst can verify them.", "The list of alternatives shows what the Critic tested and the outcome.", "Recommended actions are derived from the evidence types found."] },

    { view: "report", target: "#reveal", place: "top", tag: "Human", title: "A human has the last word",
      action: async () => { try { await review("approve"); } catch (e) { /* no run to review */ } }, until: () => ($("#reveal") || {}).innerText && $("#reveal").innerText.length > 5,
      body: "<p>The system never finalises its own conclusion. We pressed <b>Approve</b> for you, which reveals the hidden ground truth and grades the system's verdict.</p><p>Here the verdict is correct: the Critic turned a false alarm into a cleared one.</p>" },

    { view: "gateway", target: "#gwMatrix", place: "bottom", tag: "Gateway", title: "The Tool Gateway: where safety is enforced",
      body: "<p>Every agent request goes through this gateway, which checks the agent's allow-list and the sandbox scope, then logs the call.</p>",
      tech: ["Blue, Forensics and Red have read-only tools. The Critic and Orchestrator have none.", "Scope is enforced <b>in code</b>, not by trusting the model's judgement.", "An agent that tried something harmful would simply be refused and logged."] },

    { view: "gateway", target: "#gwAudit", place: "top", tag: "Gateway", title: "Trying to break the rules",
      action: async () => { await runProbe(); }, until: () => document.querySelectorAll("#gwAudit .chip.denied").length >= 4,
      body: "<p>We just fired four illegal requests: change a PLC setting, scan an address outside the sandbox, delete logs, and the Critic calling a tool. All four are <b>DENIED</b> and logged.</p>" },

    { view: "red", target: "#redOut", place: "top", tag: "Red", title: "Red: the building inspector",
      action: async () => { await runRed(); }, until: () => has("#redOut table"),
      body: "<p>The Red Agent checks the plant's configuration for weak settings. It found things like no MFA on the VPN gateway, default credentials and unsigned firmware: the same kinds of weakness reported in the December 2025 Poland attacks.</p>",
      tech: ["Tools: <code>discover_assets</code>, <code>inspect_configuration</code>, <code>check_exposure</code>.", "It can look but never change anything, and every call is audited."] },

    { view: "compare", target: "#cmpOut", place: "top", title: "Side by side",
      action: async () => { selectCase("S2"); await runCompare(); }, until: () => has("#cmpOut .h2h"),
      body: "<p>The same case, run twice behind the scenes: without the Critic the verdict is wrong, with the Critic it is right. The orange marker shows how far the Critic moved the confidence.</p>" },

    { view: "eval", target: "#evalOut", place: "top", title: "The scoreboard, honestly",
      action: async () => { await runEval(); }, until: () => has("#evalOut .stats"),
      body: "<p>All five cases under three systems. The rule-based detector and the agents without the Critic both flag both harmless cases; the full system gets all five right.</p>",
      tech: ["Caveat: five scripted cases with hand-set weights demonstrate the <b>mechanism</b>, not real-world accuracy.", "A single-LLM baseline (System B) and a much larger case set come in later phases."] },

    { view: "home", title: "That is the tour", next: "Finish",
      body: "<p>You have seen the full loop: the <b>Orchestrator</b> plans, <b>Blue</b> investigates, the <b>Critic</b> challenges, <b>Forensics</b> reconstructs, the <b>Gateway</b> keeps everyone in bounds, and a <b>human</b> decides.</p><p>Replay this any time with <b>Guide me</b>. Next phases: a Docker-isolated plant with a PLC simulator, LLM-driven planning, memory, and many more cases.</p>" },
  ];

  let idx = -1, root = null, layoutTimer = null, waitTimer = null, token = 0;

  function build() {
    root = document.createElement("div"); root.id = "tour";
    root.innerHTML = `<div class="tback"></div><div class="tspot"></div>
      <div class="tcard" role="dialog" aria-modal="true"><div class="tprog"><i></i></div>
        <div class="tin"><div class="tmeta"><span class="tstep"></span><span class="tag" style="display:none"></span></div>
          <h3></h3><div class="tbody"></div><div class="ttech" style="display:none"><b>Under the hood</b><ul></ul></div><div class="twait">Watching the simulation, one moment…</div></div>
        <div class="tnav"><button class="skip">Skip tour</button><span class="grow"></span><button class="tback2">Back</button><button class="primary tnext">Next</button></div></div>`;
    document.body.appendChild(root);
    root.querySelector(".skip").onclick = close;
    root.querySelector(".tback2").onclick = () => idx > 0 && show(idx - 1, false);
    root.querySelector(".tnext").onclick = () => (idx >= T.length - 1 ? close(true) : show(idx + 1, true));
    document.addEventListener("keydown", onKey);
    layoutTimer = setInterval(layout, 250);
  }
  function onKey(e) {
    if (!root) return;
    if (e.key === "Escape") close();
    else if ((e.key === "ArrowRight" || e.key === "Enter") && !root.querySelector(".tnext").disabled) { e.preventDefault(); root.querySelector(".tnext").click(); }
    else if (e.key === "ArrowLeft") root.querySelector(".tback2").click();
  }
  function close(done) {
    clearInterval(layoutTimer); clearInterval(waitTimer); token++;
    document.removeEventListener("keydown", onKey);
    if (root) root.remove(); root = null; idx = -1;
    try { localStorage.setItem("ica_tour_seen", "1"); } catch (e) { /* ignore */ }
    if (done) go("home");
  }

  async function show(i, forward) {
    const my = ++token; idx = i; const s = T[i];
    const q = (sel) => root.querySelector(sel), next = q(".tnext"), back = q(".tback2");
    q(".tstep").textContent = `Step ${i + 1} of ${T.length}`;
    const tg = q(".tag"); if (s.tag) { tg.style.display = ""; tg.style.setProperty("--c", COL[s.tag]); tg.textContent = s.tag; } else tg.style.display = "none";
    q("h3").textContent = s.title; q(".tbody").innerHTML = s.body;
    const tech = q(".ttech"); if (s.tech) { tech.style.display = ""; tech.querySelector("ul").innerHTML = s.tech.map((t) => `<li>${t}</li>`).join(""); } else tech.style.display = "none";
    q(".tprog i").style.width = ((i + 1) / T.length) * 100 + "%";
    back.disabled = i === 0; next.textContent = s.next || "Next"; next.disabled = true; q(".twait").classList.remove("on");
    if (s.view) { go(s.view); await sleep(260); }
    if (my !== token) return;
    if (forward && s.action) { try { await s.action(); } catch (e) { /* keep the tour going */ } }
    if (my !== token) return;
    await sleep(120); scrollToTarget(s); layout();
    if (s.until && forward) {
      q(".twait").classList.add("on"); const t0 = Date.now();
      clearInterval(waitTimer);
      waitTimer = setInterval(() => {
        let ok = false; try { ok = s.until(); } catch (e) { ok = false; }
        if (ok || Date.now() - t0 > 60000 || my !== token) { clearInterval(waitTimer); if (my === token && root) { q(".twait").classList.remove("on"); next.disabled = false; layout(); } }
      }, 300);
    } else next.disabled = false;
  }
  function scrollToTarget(s) {
    const t = s.target && document.querySelector(s.target);
    if (t && t.getClientRects().length) t.scrollIntoView({ block: "center", behavior: "smooth" });
  }
  function layout() {
    if (!root || idx < 0) return;
    const s = T[idx], card = root.querySelector(".tcard"), spot = root.querySelector(".tspot");
    const t = s.target && document.querySelector(s.target), vw = innerWidth, vh = innerHeight, m = 14;
    const cw = card.offsetWidth, ch = card.offsetHeight;
    if (t && t.getClientRects().length && (t.getBoundingClientRect().height > 2)) {
      const r = t.getBoundingClientRect(), pad = 8;
      const x = Math.max(4, r.left - pad), y = Math.max(4, r.top - pad);
      const w = Math.min(vw - 4 - x, r.width + pad * 2), h = Math.min(vh - 4 - y, r.height + pad * 2);
      Object.assign(spot.style, { left: x + "px", top: y + "px", width: w + "px", height: h + "px" });
      root.classList.add("spotting");
      const box = { left: x, top: y, right: x + w, bottom: y + h };
      const opt = { right: () => [box.right + m, box.top], left: () => [box.left - cw - m, box.top], bottom: () => [box.left, box.bottom + m], top: () => [box.left, box.top - ch - m] };
      const fits = { right: (p) => p[0] + cw <= vw - m, left: (p) => p[0] >= m, bottom: (p) => p[1] + ch <= vh - m, top: (p) => p[1] >= m };
      let placed = false;
      for (const k of [s.place, "right", "left", "bottom", "top"].filter(Boolean)) {
        const p = opt[k]();
        if (fits[k](p)) { setCard(card, p[0], p[1], cw, ch, vw, vh, m); placed = true; break; }
      }
      if (!placed) setCard(card, vw - cw - m, vh - ch - m, cw, ch, vw, vh, m);
    } else {
      root.classList.remove("spotting");
      setCard(card, (vw - cw) / 2, (vh - ch) / 2, cw, ch, vw, vh, m);
    }
  }
  function setCard(card, x, y, cw, ch, vw, vh, m) {
    card.style.left = Math.max(m, Math.min(x, vw - cw - m)) + "px";
    card.style.top = Math.max(m, Math.min(y, vh - ch - m)) + "px";
  }

  function start(at) {
    if (root) return;
    const hint = document.querySelector(".thint"); if (hint) hint.remove();
    try { resetUI(); state.audit = []; } catch (e) { /* ignore */ }
    build(); show(at || 0, true);
  }
  window.startTour = start;

  document.addEventListener("DOMContentLoaded", () => {
    const b = document.getElementById("guideBtn"); if (b) b.onclick = () => start(0);
  });
  window.addEventListener("load", () => {
    const b = document.getElementById("guideBtn"); if (b) b.onclick = () => start(0);
    const q = new URLSearchParams(location.search);
    if (q.get("tour") !== null) { setTimeout(() => start(parseInt(q.get("tour"), 10) || 0), 1200); return; }
    let seen = false; try { seen = !!localStorage.getItem("ica_tour_seen"); } catch (e) { /* ignore */ }
    if (!seen && !q.get("case") && !q.get("compare") && !q.get("eval") && !q.get("view")) setTimeout(() => {
      if (root || document.querySelector(".thint")) return;
      const h = document.createElement("div"); h.className = "thint";
      h.innerHTML = `<b>New here?</b><p>Take the guided tour: it runs the prototype for you and explains each agent as it works.</p><div class="r"><button class="primary" id="hintGo">Start the guide</button><button id="hintNo">Not now</button></div>`;
      document.body.appendChild(h);
      h.querySelector("#hintGo").onclick = () => start(0);
      h.querySelector("#hintNo").onclick = () => { h.remove(); try { localStorage.setItem("ica_tour_seen", "1"); } catch (e) { /* ignore */ } };
    }, 1500);
  });
})();
