"""Orchestrator, Blue, Critic, Forensics and Red agents (Phase-1: deterministic reasoning, optional LLM narration)."""
import threading
import time

from . import llm, sim
from .evidence import MITRE, THRESHOLD, EvidenceBook, signal_for_event
from .gateway import Gateway

PACE = dict(phase=0.15, evidence=0.35, hypothesis=0.5, graph=0.6, timeline=0.4)
ZONE_RANK = {"DMZ": 0, "IT": 1, "OT": 2, "Control": 3, "Process": 4}
PRIORITY = {
    "auth": ["auth", "privilege", "process", "network", "config", "firmware", "file", "scan", "comms", "reset", "process_state"],
    "config": ["config", "auth", "privilege", "process", "network", "firmware", "comms", "process_state", "file", "scan", "reset"],
    "comms": ["comms", "firmware", "network", "auth", "config", "file", "scan", "reset", "process", "privilege", "process_state"],
}


class Run:
    def __init__(self, run_id, scn, critic=True, delay=0.8):
        self.id, self.scn, self.critic, self.delay = run_id, scn, critic, delay
        self.steps, self.lock = [], threading.Lock()
        self.status, self.paused = "running", False
        self.gw, self.book = Gateway(scn), EvidenceBook()
        self.tool_calls = 0
        self.report, self.verdict, self.review = None, None, None
        self.prelim_incident = None

    def emit(self, agent, kind, text, why=None, **data):
        with self.lock:
            step = dict(n=len(self.steps) + 1, agent=agent, kind=kind, text=text, why=why, data=data)
            self.steps.append(step)
        while self.paused:
            time.sleep(0.1)
        if self.delay:
            time.sleep(self.delay * PACE.get(kind, 1.0))
        return step

    def phase(self, name):
        self.emit("System", "phase", name, phase=name)

    def get_steps(self, since=0):
        with self.lock:
            return list(self.steps[since:])

    def call(self, agent, tool, **args):
        result, entry = self.gw.call(agent, tool, **args)
        self.tool_calls += 1
        argtxt = ", ".join(f"{k}={v}" for k, v in args.items())
        evs = [e["id"] for e in result] if tool == "query_events" and result else []
        assets = sorted({e["asset"] for e in result}) if tool == "query_events" and result else \
            ([args["asset"]] if "asset" in args and args["asset"] in sim.ASSETS else [])
        self.emit(agent, "tool", f"{tool}({argtxt})  →  {entry['summary']}", audit=entry, events=evs, assets=assets)
        return result

    def add_evidence(self, agent, code, weight, text, events=(), source="observation", detail=None):
        item = self.book.add(code, weight, text, events, source, detail)
        self.emit(agent, "evidence", text, evidence=item)
        return item

    def hypothesis(self, agent, text):
        b = self.book
        self.emit(agent, "hypothesis", text, confidence=round(b.confidence, 3), threshold=THRESHOLD, score=round(b.score, 2))


# ───────────────────────────────── Blue: single-pass analyst
def blue_investigate(run):
    scn = run.scn
    alert = scn["alert"]
    run.phase("investigate")
    summary = run.call("Blue", "get_log_summary")
    kinds = [k for k in PRIORITY[alert["kind"]] if k in summary]
    run.emit("Blue", "message",
             f"Starting from the alert, I will read the {len(kinds)} log sources that contain events and score anything unusual.",
             why="Blue behaves like a single-pass analyst: it hunts for signs of an attack and does not ask whether the activity could be legitimate.")
    for kind in kinds:
        events = run.call("Blue", "query_events", kind=kind)
        found = False
        for e in events:
            sig = signal_for_event(e)
            if sig:
                found = True
                code, weight, label = sig
                run.add_evidence("Blue", code, weight, f"{e['detail']}", events=[e["id"]], detail=label)
        if found:
            run.hypothesis("Blue", f"Confidence of a malicious incident is now {run.book.confidence:.2f}")
    run.prelim_incident = run.book.incident
    word = "malicious activity is likely" if run.prelim_incident else "no incident is indicated"
    fallback = (f"Preliminary assessment: {word} (confidence {run.book.confidence:.2f}). "
                f"I collected {len(run.book.items)} pieces of evidence, all of them signs of an attack.")
    text = llm.say("Blue Agent", f"Facts: {[i['text'] for i in run.book.items]}. Confidence {run.book.confidence:.2f}. "
                                  "Write the preliminary assessment.", fallback)
    run.emit("Blue", "message", text, prelim=round(run.book.confidence, 3),
             why="Without a challenger the analysis would stop here, and the verdict would stand.")


# ───────────────────────────────── Critic
def pick_target(scn):
    evs = scn["events"]
    for kind in ("config", "firmware"):
        c = [e for e in evs if e["kind"] == kind and e["asset"] != "VPN-GW"]
        if c:
            e = c[-1]
            return (e["dst"] if kind == "config" else e["asset"]), e["user"], e["t"]
    auths = [e for e in evs if e["kind"] == "auth"]
    e = max(auths, key=lambda x: (ZONE_RANK[sim.ASSETS[x["asset"]]["zone"]], x["t"]))
    return e["asset"], e["user"], e["t"]


def critic_alternatives(codes):
    alts = []
    if codes & {"plc_config_change", "privilege_escalation", "gateway_config_change", "process_deviation", "process_deviation_minor"}:
        alts.append(dict(id="ALT-1", name="Planned maintenance or an authorised change", checks=["maintenance", "authorization"]))
    if codes & {"firmware_upload", "comms_loss"}:
        alts.append(dict(id="ALT-2", name="A planned firmware update", checks=["firmware", "maintenance"]))
    if "comms_loss" in codes:
        alts.append(dict(id="ALT-3", name="A network or equipment fault", checks=[]))
    if codes & {"login_external_anomalous", "login_anomalous", "suspicious_process", "new_network_path"}:
        alts.append(dict(id="ALT-4", name="Legitimate remote or after-hours work by an authorised user", checks=["authorization", "maintenance"]))
    return alts


def critic_stage(run):
    scn, book = run.scn, run.book
    codes = {i["code"] for i in book.items}
    alts = critic_alternatives(codes)
    checks = []
    for a in alts:
        for c in a["checks"]:
            if c not in checks:
                checks.append(c)
    run.phase("challenge")
    names = "; ".join(f"{a['id']}: {a['name']}" for a in alts)
    fallback = (f"I do not accept the preliminary verdict yet. The same evidence could be explained by: {names}. "
                f"Required checks before concluding: {', '.join(checks) or 'none available'}.")
    text = llm.say("Critic Agent", f"Preliminary verdict: malicious={run.prelim_incident}. Alternatives: {names}. "
                                    "Challenge the verdict and say what must be checked.", fallback)
    run.emit("Critic", "challenge", text, alternatives=alts,
             why="The Critic argues the other side. It cannot touch the plant; it can only demand evidence.")
    run.emit("Orchestrator", "message",
             f"Critic requested {len(checks)} additional check(s). Sending them to Blue and keeping the case open.",
             why="Because the Critic can re-open the case, the investigation continues until alternatives are tested.")
    run.phase("verify")
    asset, user, at = pick_target(scn)
    res = {}
    if "maintenance" in checks:
        r = run.call("Blue", "check_maintenance_schedule", asset=asset, at=at)
        res["maintenance"] = r
        if r["found"]:
            run.add_evidence("Blue", "maintenance_match", -3.0, f"Maintenance window for {asset}: {r['ticket']} ({r['start']}-{r['end']}) {r['note']}", source="check")
        else:
            run.add_evidence("Blue", "maintenance_none", 1.2, f"No maintenance window or change ticket for {asset} at {at}", source="check")
        run.hypothesis("Blue", f"Confidence of a malicious incident is now {book.confidence:.2f}")
    if "authorization" in checks:
        r = run.call("Blue", "check_user_authorization", user=user, asset=asset)
        res["authorization"] = r
        if r["authorized"] and r["ticket"]:
            run.add_evidence("Blue", "user_authorized_ticket", -3.0, f"{user} ({r['role']}) is authorised for {asset} and holds ticket {r['ticket']}", source="check")
        elif r["authorized"]:
            run.add_evidence("Blue", "user_authorized", -1.0, f"{user} ({r['role']}) is authorised for {asset}", source="check")
        else:
            run.add_evidence("Blue", "user_unauthorized", 1.5, f"{user} ({r['role']}) is NOT authorised for {asset}", source="check")
        run.hypothesis("Blue", f"Confidence of a malicious incident is now {book.confidence:.2f}")
    if "firmware" in checks:
        r = run.call("Blue", "verify_firmware_signature", asset=asset)
        res["firmware"] = r
        if r.get("valid"):
            run.add_evidence("Blue", "firmware_valid", -2.5, f"Firmware on {asset} carries a valid vendor signature (version {r['version']})", source="check")
        else:
            run.add_evidence("Blue", "firmware_unsigned", 2.5, f"Firmware on {asset} has an INVALID signature / hash mismatch", source="check")
        run.hypothesis("Blue", f"Confidence of a malicious incident is now {book.confidence:.2f}")
    # judge each alternative
    outcomes = []
    for a in alts:
        m, u, f = res.get("maintenance"), res.get("authorization"), res.get("firmware")
        if a["id"] in ("ALT-1", "ALT-4"):
            good = bool(m and m["found"]) + bool(u and u["authorized"])
            out = "supported" if good == 2 else ("rejected" if good == 0 else "inconclusive")
        elif a["id"] == "ALT-2":
            out = "supported" if (f and f.get("valid") and m and m["found"]) else ("rejected" if f and not f.get("valid") else "inconclusive")
        else:
            out = "not testable in Phase 1 (no fault-diagnosis tool)"
        outcomes.append(dict(a, outcome=out))
    run.alt_outcomes = outcomes
    final_incident = book.incident
    lines = "; ".join(f"{o['id']} {o['outcome']}" for o in outcomes)
    if run.prelim_incident and not final_incident:
        head = "Preliminary verdict OVERTURNED."
        why = "This is the Critic's value: a confident but wrong 'attack' call became a correct 'authorised activity' call."
    elif run.prelim_incident and final_incident:
        head = "Verdict upheld."
        why = "The Critic could not explain the activity innocently, so confidence in the attack rose."
    else:
        head = "Verdict revised."
        why = "The Critic's checks changed the outcome."
    run.emit("Critic", "challenge", f"{head} Alternatives: {lines}. Final confidence of an incident: {book.confidence:.2f}.", why=why,
             overturned=bool(run.prelim_incident and not final_incident))


# ───────────────────────────────── Forensics
def forensics_stage(run):
    scn, book = run.scn, run.book
    incident = book.incident
    run.phase("reconstruct")
    allev = run.call("Forensics", "query_events")
    byid = {e["id"]: e for e in allev}
    ev_to_e = {}
    for i in book.items:
        for ev in i["events"]:
            ev_to_e.setdefault(ev, []).append(i["id"])
    used = sorted({ev for i in book.items for ev in i["events"]}, key=lambda x: byid[x]["t"])
    timeline = [dict(id=x, t=byid[x]["t"], asset=byid[x]["asset"], kind=byid[x]["kind"], text=byid[x]["detail"], evidence=ev_to_e[x]) for x in used]
    run.emit("Forensics", "timeline", f"Reconstructed a timeline of {len(timeline)} evidence-backed events.", timeline=timeline,
             why="Every line in the timeline links back to evidence. Nothing is added that the evidence store cannot support.")
    edges, tags = [], {}
    for x in used:
        e = byid[x]
        refs = ev_to_e[x] + [x]
        k, a = e["kind"], e["attrs"]
        if k == "auth" and e["src"]:
            edges.append(dict(src=e["src"], dst=e["asset"], label=f"{e['user']} login", refs=refs))
        elif k == "network":
            edges.append(dict(src=e["src"], dst=e["dst"], label=f"{a.get('port')}", refs=refs))
        elif k == "config" and e["src"] != e["dst"]:
            edges.append(dict(src=e["src"], dst=e["dst"], label=f"{a.get('param')}", refs=refs))
        elif k == "scan":
            edges.append(dict(src="EXTERNAL", dst=e["asset"], label="scan", refs=refs))
        tags.setdefault(e["asset"], []).append(k)
    if any(e["kind"] == "config" and e["dst"] == "PLC-02" for e in allev) and "PROCESS-01" in tags:
        edges.append(dict(src="PLC-02", dst="PROCESS-01", label="effect", refs=[]))
    path = []
    for ed in edges:
        for n in (ed["src"], ed["dst"]):
            if n not in path:
                path.append(n)
    run.emit("Forensics", "graph",
             "Evidence graph built: " + (f"attack path {' → '.join(path)}" if incident else "activity trail is consistent with authorised work"),
             edges=edges, tags=tags, incident=incident, path=path,
             why="The graph is the explanation. Each edge cites evidence, so an analyst can verify it.")
    run.graph = dict(edges=edges, tags=tags, path=path)
    run.timeline = timeline
    run.byid = byid


# ───────────────────────────────── Report
ACTIONS = {
    "login_external_anomalous": "Enforce MFA on all remote access and block the source address.",
    "default_credentials_login": "Rotate factory-default credentials on RTU/HMI devices and disable default accounts.",
    "firmware_unsigned": "Restore RTU-01 from a known-good image and enforce signed-firmware verification.",
    "plc_config_change": "Revert the PLC parameter to the last approved value and review the change.",
    "wiper_activity": "Rebuild the HMI from a clean backup; keep logs off-device.",
    "log_destruction": "Forward device logs to an off-device store in real time.",
    "credential_dumping_tool": "Reset exposed credentials and hunt for lateral movement.",
    "scan_activity": "Restrict internet exposure of the VPN gateway.",
    "new_network_path": "Segment IT/OT and alert on first-seen cross-zone connections.",
}


def build_report(run):
    book, scn = run.book, run.scn
    incident = book.incident
    codes = {i["code"] for i in book.items}
    assets = sorted({t["asset"] for t in run.timeline})
    mitre = []
    if incident:
        seen = set()
        for i in book.items:
            m = MITRE.get(i["code"])
            if m and m[0] not in seen:
                seen.add(m[0])
                mitre.append(dict(id=m[0], name=m[1], evidence=[x["id"] for x in book.items if MITRE.get(x["code"]) == m]))
    if incident:
        actions = [a for c, a in ACTIONS.items() if c in codes or (c == "firmware_unsigned" and book.has("firmware_unsigned"))]
        actions.insert(0, f"Isolate affected assets: {', '.join(assets)}.")
        impact = []
        if "process_deviation" in codes:
            impact.append("process driven outside its configured limit")
        if "comms_loss" in codes:
            impact.append("loss of view and control of RTU-01")
        if "wiper_activity" in codes:
            impact.append("HMI data destroyed")
        impact = ("Observed impact: " + "; ".join(impact) + ".") if impact else "No physical impact observed. Caught before any change was made."
    else:
        tick = next((i["text"] for i in book.items if i["code"] in ("maintenance_match", "user_authorized_ticket")), "")
        actions = ["Close the alert as authorised activity and link it to the change ticket.",
                   "Tune the detection rule to suppress alerts that match a ticket and a maintenance window."]
        impact = "No impact beyond the planned change."
    fallback = ((f"{'Incident confirmed' if incident else 'No incident'}: confidence {book.confidence:.2f}. "
                 f"{len(book.items)} evidence items across {len(assets)} assets; ") +
                (f"attack path {' → '.join(run.graph['path'])}." if incident else "activity matches an authorised change."))
    summary = llm.say("Report writer", f"Verdict incident={incident}, confidence {book.confidence:.2f}. "
                                       f"Evidence: {[i['text'] for i in book.items]}. Write a 2-sentence executive summary.", fallback)
    run.report = dict(
        incident_id=f"INC-{scn['id'][1:].zfill(3)}",
        scenario=scn["id"], classification="Security incident" if incident else "No incident (authorised activity)",
        incident=incident, confidence=round(book.confidence, 3), status="Awaiting human review",
        summary=summary, affected_assets=assets, attack_path=run.graph["path"] if incident else [],
        timeline=run.timeline, evidence=book.items, mitre=mitre, alternatives=getattr(run, "alt_outcomes", []),
        impact=impact, actions=actions, critic_enabled=run.critic, tool_calls=run.tool_calls)
    run.verdict = incident
    run.phase("report")
    run.emit("Orchestrator", "verdict",
             f"Investigation complete: {'INCIDENT' if incident else 'NO INCIDENT'} (confidence {book.confidence:.2f}). Report is ready for human review.",
             incident=incident, confidence=round(book.confidence, 3), assets=assets,
             why="The system never treats its own conclusion as final. A human approves or sends the case back.")
    run.emit("Orchestrator", "report", "Incident report generated.", report=run.report)
    run.phase("review")


# ───────────────────────────────── entry points
def run_investigation(run):
    try:
        scn = run.scn
        run.phase("alert")
        run.emit("System", "alert", scn["alert"]["text"], asset=scn["alert"]["asset"], t=scn["alert"]["t"],
                 why="Detection tools raise this alert. Everything after it is the investigation they do not do.")
        run.emit("Orchestrator", "message",
                 "Objective: determine whether this alert is a real compromise. Plan: Blue investigates"
                 + (", the Critic challenges, " if run.critic else ", (Critic disabled), ") + "Forensics reconstructs, a human reviews.",
                 why="The Orchestrator plans and delegates. It has no direct access to the plant.")
        blue_investigate(run)
        if run.critic:
            critic_stage(run)
        else:
            run.emit("Orchestrator", "message", "Critic disabled: accepting Blue's preliminary verdict as final.",
                     why="This is System C of the evaluation (multi-agent without a Critic).")
        forensics_stage(run)
        build_report(run)
        run.status = "awaiting_review"
    except Exception as exc:  # surface any bug to the UI instead of hanging
        run.status = "error"
        run.emit("System", "error", f"{type(exc).__name__}: {exc}")
        raise


def rule_based(scn):
    """System A: a signature-style detector. Flags sensitive event types and explains nothing."""
    flag = any(e["kind"] in ("config", "firmware", "file") or (e["kind"] == "process" and e["attrs"].get("suspicious"))
               for e in scn["events"])
    return dict(flag=flag)


def red_assessment():
    """Red Agent: read-only, authorised assessment of the simulated plant's configuration."""
    g = Gateway()
    out = []
    assets, _ = g.call("Red", "discover_assets")
    risk = {
        ("VPN-GW", "internet_exposed"): ("High", "VPN gateway is reachable from the internet."),
        ("VPN-GW", "mfa_enabled"): ("High", "No MFA on VPN: a single stolen password is enough."),
        ("VPN-GW", "shared_credentials"): ("Medium", "Same credentials reused across sites."),
        ("RTU-01", "default_credentials"): ("High", "Factory-default credentials still active."),
        ("RTU-01", "firmware_signing_enforced"): ("High", "Unsigned firmware would be accepted."),
        ("HMI-01", "default_admin_password"): ("High", "Default administrator password on the HMI."),
        ("SERVER-02", "mfa_enabled"): ("Medium", "No MFA on the application server."),
        ("PLC-02", "remote_programming_enabled"): ("Medium", "Remote programming enabled on the PLC."),
    }
    bad_when = {"internet_exposed": True, "mfa_enabled": False, "shared_credentials": True, "default_credentials": True,
                "firmware_signing_enforced": False, "default_admin_password": True, "remote_programming_enabled": True}
    for a in assets:
        cfg, entry = g.call("Red", "inspect_configuration", asset=a)
        for k, v in cfg.items():
            if k in bad_when and v == bad_when[k] and (a, k) in risk:
                sev, why = risk[(a, k)]
                out.append(dict(asset=a, setting=k, value=v, severity=sev, finding=why))
    out.sort(key=lambda f: (f["severity"] != "High", f["asset"]))
    return dict(findings=out, audit=g.audit)
