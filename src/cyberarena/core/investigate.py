"""Orchestrator, Blue, Critic, Forensics (and the read-only Red assessment) over live plant evidence.

Reasoning is deterministic and auditable: evidence items carry weights, the confidence is a logistic function of
them, and every verdict cites the evidence behind it. An LLM, when configured, only rewrites the narration.
"""
import threading
import time

from . import llm
from .evidence import MITRE, THRESHOLD, EvidenceBook, signal_for_event
from .gateway import Gateway

import os as _os
import pathlib as _pathlib

def _load_playbooks_yaml(yaml_path: str | None = None) -> dict:
    """Load playbooks from YAML; return empty dict on any failure."""
    path_str = yaml_path or _os.environ.get("PLAYBOOKS_YAML", "config/playbooks.yaml")
    p = _pathlib.Path(path_str)
    if not p.exists():
        return {}
    try:
        import re as _re
        raw = p.read_text(encoding="utf-8")
        result: dict[str, list[str]] = {}
        current: list[str] | None = None
        for line in raw.splitlines():
            # Match asset key line: "  plc-01:"
            key_m = _re.match(r"^  ([\w\-]+):$", line)
            if key_m:
                current = []
                result[key_m.group(1)] = current
                continue
            # Match step line:  '    - "some text"'
            step_m = _re.match(r'^    - "(.+)"$', line)
            if step_m and current is not None:
                current.append(step_m.group(1).replace('\\"', '"'))
        return {k: v for k, v in result.items() if v}
    except Exception:
        return {}


PACE = dict(phase=0.15, evidence=0.35, hypothesis=0.5, graph=0.6, timeline=0.4)
GENERIC_PRIORITY = ["auth", "network", "process", "file", "config", "scan", "process_state", "erp", "hmi", "other"]
PRIORITY = {
    "auth": ["auth", "network", "process", "file", "config", "scan", "process_state", "erp", "hmi", "other"],
    "config": ["config", "auth", "network", "process", "file", "scan", "process_state", "erp", "hmi", "other"],
}


class Run:
    def __init__(self, run_id, events, alert, site, tickets, critic=True, delay=0.0, disable=()):
        self.id, self.events, self.alert, self.critic, self.delay = run_id, events, alert, critic, delay
        self.site, self.tickets = site, tickets
        self.disable = set(disable)      # Critic checks switched off, for ablations only
        self.steps, self.lock = [], threading.Lock()
        self.status, self.paused = "running", False
        self.gw, self.book = Gateway(site, tickets, events), EvidenceBook()
        self.tool_calls = 0
        self.report = self.verdict = None
        self.prelim_incident = None
        self.alt_outcomes, self.graph, self.timeline = [], {}, []

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
        assets = sorted({e["asset"] for e in result}) if tool == "query_events" and result else ([args["asset"]] if "asset" in args else [])
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
    alert = run.alert
    run.phase("investigate")
    summary = run.call("Blue", "get_log_summary")
    order = PRIORITY.get(alert["kind"], GENERIC_PRIORITY)
    kinds = [k for k in order if k in summary]
    run.emit("Blue", "message",
             f"Starting from the alert, I will read the {len(kinds)} log sources that contain events and score anything unusual.",
             why="Blue behaves like a single-pass analyst: it hunts for signs of an attack and does not ask whether the activity could be legitimate.")
    for kind in kinds:
        events = run.call("Blue", "query_events", kind=kind)
        found = False
        for e in events:
            sig = signal_for_event(e, run.site)
            if sig:
                found = True
                code, weight, label = sig
                run.add_evidence("Blue", code, weight, e["detail"], events=[e["id"]], detail=label)
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
def pick_target(run):
    """The asset, user and time the Critic's checks should be asked about."""
    evs = run.events
    cfg = [e for e in evs if e["kind"] == "config" and not e["attrs"].get("baseline")]
    if cfg:
        e = cfg[-1]
        return e["dst"] or e["asset"], e["user"], e["t"]
    auths = [e for e in evs if e["kind"] == "auth" and not e["attrs"].get("failure")]
    if auths:
        e = max(auths, key=lambda x: (run.site.zone_rank(x["asset"]), x["t"]))
        return e["asset"], e["user"], e["t"]
    for e in evs:
        if e["kind"] in ("file", "process") and e["user"]:
            return e["asset"], e["user"], e["t"]
    return run.alert["asset"], None, run.alert["t"]


def critic_alternatives(codes):
    alts = []
    if codes & {"plc_config_change", "plc_logic_change", "safety_bypass", "process_deviation", "blocked_attempt"}:
        alts.append(dict(id="ALT-1", name="Planned maintenance or an authorised change", checks=["maintenance", "authorization", "scope"]))
    if codes & {"login_external_anomalous", "login_anomalous", "default_credentials_login", "suspicious_process", "new_network_path",
                "credential_file_access", "program_upload"}:
        alts.append(dict(id="ALT-4", name="Legitimate remote or engineering work by an authorised user", checks=["authorization", "maintenance"]))
    if codes & {"scan_activity", "internal_enumeration"}:
        alts.append(dict(id="ALT-5", name="A scheduled security scan or inventory run by an authorised tool", checks=["maintenance"]))
    return alts


def critic_stage(run):
    book = run.book
    codes = {i["code"] for i in book.items}
    alts = critic_alternatives(codes)
    checks = []
    for a in alts:
        for c in a["checks"]:
            if c not in checks:
                checks.append(c)
    checks = [c for c in checks if c not in run.disable]
    run.phase("challenge")
    names = "; ".join(f"{a['id']}: {a['name']}" for a in alts)
    fallback = (f"I do not accept the preliminary verdict yet. The same evidence could be explained by: {names or 'nothing I can test'}. "
                f"Required checks before concluding: {', '.join(checks) or 'none available'}.")
    text = llm.say("Critic Agent", f"Preliminary verdict: malicious={run.prelim_incident}. Alternatives: {names}. "
                                    "Challenge the verdict and say what must be checked.", fallback)
    run.emit("Critic", "challenge", text, alternatives=alts,
             why="The Critic argues the other side. It cannot touch the plant; it can only demand evidence.")
    run.emit("Orchestrator", "message",
             f"Critic requested {len(checks)} additional check(s). Sending them to Blue and keeping the case open.",
             why="Because the Critic can re-open the case, the investigation continues until alternatives are tested.")
    run.phase("verify")
    asset, user, at = pick_target(run)
    res = {}
    if "maintenance" in checks:
        r = run.call("Blue", "check_maintenance_schedule", asset=asset, at=at)
        res["maintenance"] = r
        made_change = any(e["kind"] == "config" and (e["dst"] or e["asset"]) == asset for e in run.events)
        if r["found"] and user and made_change and r["user"] != user:
            run.add_evidence("Blue", "ticket_not_holder", 0.5, f"Window for {asset} ({r['ticket']}) belongs to {r['user']}, not {user}", source="check")
        elif r["found"]:
            run.add_evidence("Blue", "maintenance_match", -3.0, f"Maintenance window for {asset}: {r['ticket']} ({r['start']}-{r['end']}) {r['note']}", source="check")
        else:
            run.add_evidence("Blue", "maintenance_none", 1.2, f"No approved maintenance window or change ticket for {asset} at {at}", source="check")
        run.hypothesis("Blue", f"Confidence of a malicious incident is now {book.confidence:.2f}")
    if "authorization" in checks and user:
        r = run.call("Blue", "check_user_authorization", user=user, asset=asset, at=at)
        res["authorization"] = r
        if r["authorized"] and r["ticket"]:
            run.add_evidence("Blue", "user_authorized_ticket", -3.0, f"{user} ({r['role']}) is authorised for {asset} and holds ticket {r['ticket']}", source="check")
        elif r["authorized"]:
            run.add_evidence("Blue", "user_authorized", -1.0, f"{user} ({r['role']}) is authorised for {asset}", source="check")
        else:
            run.add_evidence("Blue", "user_unauthorized", 1.5, f"{user} ({r['role']}) is NOT authorised for {asset}", source="check")
        run.hypothesis("Blue", f"Confidence of a malicious incident is now {book.confidence:.2f}")
    if "scope" in checks and res.get("maintenance", {}).get("found"):
        r = run.call("Blue", "check_change_scope", asset=asset, at=at)
        res["scope"] = r
        if r.get("judged") and not r["within"]:
            vals = ", ".join(f"{o['param']}={o['new']} (approved {o['approved']})" for o in r["over"])
            voided = -sum(i["weight"] for i in book.items if i["code"] in ("maintenance_match", "user_authorized_ticket"))
            run.add_evidence("Blue", "scope_exceeded", voided + 1.0,
                             f"The change goes beyond what ticket {r['ticket']} approved: {vals}. The ticket no longer vouches for it."
                             + (" (values read from the ticket text by a language model)" if "language model" in r.get("source", "") else ""), source="check")
        elif r.get("judged"):
            run.add_evidence("Blue", "scope_within", -0.5, f"Every parameter the ticket lists is within its approved value ({r['ticket']})", source="check")
        run.hypothesis("Blue", f"Confidence of a malicious incident is now {book.confidence:.2f}")
    outcomes = []
    for a in alts:
        m, u, sc = res.get("maintenance"), res.get("authorization"), res.get("scope")
        if a["id"] in ("ALT-1", "ALT-4"):
            parts = [bool(m["found"]) and (not user or m.get("user") == user)] if m else []
            if sc and sc.get("judged"):
                parts.append(bool(sc["within"]))
            if u is not None:
                parts.append(bool(u["authorized"]))
            good = sum(parts)
            out = "supported" if parts and good == len(parts) else ("rejected" if good == 0 else "inconclusive")
        else:
            out = "supported" if (m and m["found"]) else "rejected"
        outcomes.append(dict(a, outcome=out))
    run.alt_outcomes = outcomes
    final_incident = book.incident
    lines = "; ".join(f"{o['id']} {o['outcome']}" for o in outcomes)
    if run.prelim_incident and not final_incident:
        head, why = "Preliminary verdict OVERTURNED.", "This is the Critic's value: a confident but wrong 'attack' call became a correct 'authorised activity' call."
    elif run.prelim_incident and final_incident:
        head, why = "Verdict upheld.", "The Critic could not explain the activity innocently, so confidence in the attack held or rose."
    elif final_incident:
        head, why = "Verdict raised to INCIDENT.", "Blue's first read was below threshold; the checks (no ticket, unauthorised user) pushed it over."
    else:
        head, why = "Verdict upheld (no incident).", "The checks agree with the preliminary read."
    run.emit("Critic", "challenge", f"{head} Alternatives: {lines or 'none'}. Final confidence of an incident: {book.confidence:.2f}.", why=why,
             overturned=bool(run.prelim_incident and not final_incident))


# ───────────────────────────────── Forensics
def forensics_stage(run):
    book = run.book
    incident = book.incident
    run.phase("reconstruct")
    allev = run.call("Forensics", "query_events")
    byid = {e["id"]: e for e in allev}
    ev_to_e = {}
    for i in book.items:
        for ev in i["events"]:
            ev_to_e.setdefault(ev, []).append(i["id"])
    used = sorted({ev for i in book.items for ev in i["events"]}, key=lambda x: byid[x]["t"] + x)
    timeline = [dict(id=x, t=byid[x]["t"], asset=byid[x]["asset"], kind=byid[x]["kind"], text=byid[x]["detail"], evidence=ev_to_e[x]) for x in used]
    run.emit("Forensics", "timeline", f"Reconstructed a timeline of {len(timeline)} evidence-backed events.", timeline=timeline,
             why="Every line in the timeline links back to evidence. Nothing is added that the evidence store cannot support.")
    edges, tags = [], {}
    for x in used:
        e = byid[x]
        refs = ev_to_e[x] + [x]
        k, a = e["kind"], e["attrs"]
        if k == "auth" and e["src"] and e["src"] != e["asset"]:
            edges.append(dict(src=e["src"], dst=e["asset"], label=f"{e['user']} login", refs=refs))
        elif k in ("network", "config") and e["src"] and e["dst"] and e["src"] != e["dst"]:
            edges.append(dict(src=e["src"], dst=e["dst"], label=str(a.get("param") or a.get("port") or ""), refs=refs))
        elif k == "scan":
            edges.append(dict(src=e["src"] if e["src"] not in (None, e["asset"]) else "external", dst=e["asset"], label="scan", refs=refs))
        tags.setdefault(e["asset"], []).append(k)
    if any(e["kind"] == "process_state" for e in allev) and any(e["kind"] == "config" and e["dst"] == "plc-01" for e in allev):
        edges.append(dict(src="plc-01", dst="process", label="effect", refs=[]))
    path = []
    for ed in edges:
        for n in (ed["src"], ed["dst"]):
            if n not in path:
                path.append(n)
    run.emit("Forensics", "graph",
             "Evidence graph built: " + (f"attack path {' → '.join(path)}" if incident and path else "activity trail is consistent with authorised work"),
             edges=edges, tags=tags, incident=incident, path=path,
             why="The graph is the explanation. Each edge cites evidence, so an analyst can verify it.")
    run.graph = dict(edges=edges, tags=tags, path=path)
    run.timeline = timeline


# ───────────────────────────────── Report
ACTIONS = {
    "login_external_anomalous": "Enforce MFA on all remote access and rotate the vendor credentials.",
    "default_credentials_login": "Disable factory-default accounts and local logins.",
    "credential_file_access": "Move credentials out of project files and shares into a vault.",
    "suspicious_process": "Quarantine the engineering workstation and review its scheduled scripts.",
    "plc_config_change": "Revert the PLC parameter to the last approved value and require a work order for non-HMI writes.",
    "plc_logic_change": "Restore the last signed PLC program and require a logic-change work order.",
    "safety_bypass": "Remove network write access to the SIS bypass; allow it only via the physical key switch.",
    "new_network_path": "Close the temporary firewall rule and segment IT/OT.",
    "internal_enumeration": "Restrict the dual-homed historian and alert on first-seen cross-zone connections.",
    "scan_activity": "Rate-limit and alert on probes of the remote access portal.",
}

TARGETED_PLAYBOOKS = {
    "plc-01": [
        "Dispatch Line 2 Operator to physical PLC cabinet at Line 2 mixing tank.",
        "Inspect physical run key switch on PLC-1; change mode from REMOTE to STOP/PROGRAM.",
        "Cross-reference holding registers (temp setpoint target 65C max, valve state) against manual piping diagram.",
        "Reload validated factory firmware and golden ladder-logic from local offline backup media.",
        "Keep mixing tank agitator in fail-safe manual jog until supervisor signs off clearance."
    ],
    "sis-01": [
        "URGENT: Check local Safety Instrumented System (SIS) physical lockout key switch.",
        "Confirm safety interlock circuits (high temperature / overpressure trip) are active and armed.",
        "Visually verify mechanical pressure relief valve PRV-101 and cooling jacket dump bypass.",
        "Require two-person sign-off (Shift Supervisor + Safety Engineer) before clearing alarm state."
    ],
    "eng-ws-01": [
        "Disconnect network cable from engineering station (eng-ws-01) at OT switch port 4.",
        "Terminate all active engineering software sessions and background Python scripts.",
        "Check Windows event logs and project folder for modified config or credential dumps.",
        "Quarantine host from L3 operations bus until full image verification."
    ],
    "historian-01": [
        "Disconnect dual-homed secondary NIC facing IT/Office network.",
        "Terminate external diagnostic sessions and reset the local historian administrator credential.",
        "Restrict SQL and OPC-UA listener ports strictly to known MES and HMI IP addresses."
    ],
    "portal-01": [
        "Immediately terminate active external VPN tunnel and remote sessions.",
        "Invalidate all vendor service tokens and enable compulsory hardware token MFA.",
        "Verify edge firewall rules blocking unsolicited inbound connections to L4 portal."
    ],
    "fw-02": [
        "Access FW-02 console locally and disable rule 140 (temporary vendor bypass rule).",
        "Verify strict L3 to L1 boundary: no direct Modbus (TCP/502) traffic permitted outside HMI-01."
    ],
}

# Merge YAML playbooks on top of hardcoded dict (YAML takes precedence)
_yaml_playbooks = _load_playbooks_yaml()
if _yaml_playbooks:
    TARGETED_PLAYBOOKS = {**TARGETED_PLAYBOOKS, **_yaml_playbooks}



def build_report(run):
    book = run.book
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
        actions = [a for c, a in ACTIONS.items() if c in codes]
        actions.insert(0, f"Isolate affected assets: {', '.join(assets)}." if assets else "Isolate the affected assets.")
        checklist = []
        for asset_id in assets:
            if asset_id in TARGETED_PLAYBOOKS:
                for step in TARGETED_PLAYBOOKS[asset_id]:
                    if step not in checklist:
                        checklist.append(step)
        if not checklist:
            for c in codes:
                if c in ACTIONS:
                    checklist.append(f"Execute mitigation: {ACTIONS[c]}")
            checklist.append("Conduct visual inspection of machinery status on local plant floor.")
            checklist.append("Obtain signed approval from shift supervisor before restoring remote automation.")
        impact = []
        if "process_deviation" in codes:
            impact.append("process driven outside its alarm limit")
        if "safety_bypass" in codes:
            impact.append("safety trip bypassed")
        if "plc_logic_change" in codes:
            impact.append("controller logic altered")
        impact = ("Observed impact: " + "; ".join(impact) + ".") if impact else "No physical impact observed yet."
    else:
        actions = ["Close the alert as authorised activity and link it to the change ticket.",
                   "Tune the detection rule to suppress alerts that match a ticket and a maintenance window."]
        checklist = ["Verify work order sign-off in maintenance logbook.", "Confirm operating telemetry returned to nominal state."]
        impact = "No impact beyond the planned change."
    fallback = (f"{'Incident confirmed' if incident else 'No incident'}: confidence {book.confidence:.2f}. "
                f"{len(book.items)} evidence items across {len(assets)} assets; "
                + (f"attack path {' → '.join(run.graph['path'])}." if incident and run.graph.get("path") else "activity matches an authorised change."))
    summary = llm.say("Report writer", f"Verdict incident={incident}, confidence {book.confidence:.2f}. "
                                       f"Evidence: {[i['text'] for i in book.items]}. Write a 2-sentence executive summary.", fallback)
    run.report = dict(
        incident_id=f"INC-{run.id}", classification="Security incident" if incident else "No incident (authorised activity)",
        incident=incident, confidence=round(book.confidence, 3), status="Awaiting human review", summary=summary,
        affected_assets=assets, attack_path=run.graph.get("path", []) if incident else [], timeline=run.timeline,
        evidence=book.items, mitre=mitre, alternatives=run.alt_outcomes, impact=impact, actions=actions,
        checklist=checklist,
        critic_enabled=run.critic, tool_calls=run.tool_calls)
    run.verdict = incident
    run.phase("report")
    run.emit("Orchestrator", "verdict",
             f"Investigation complete: {'INCIDENT' if incident else 'NO INCIDENT'} (confidence {book.confidence:.2f}). Report is ready for human review.",
             incident=incident, confidence=round(book.confidence, 3), assets=assets,
             why="The system never treats its own conclusion as final. A human approves or sends the case back.")
    run.emit("Orchestrator", "report", "Incident report generated.", report=run.report)
    run.phase("review")


def run_investigation(run):
    try:
        run.phase("alert")
        run.emit("System", "alert", run.alert["text"], asset=run.alert["asset"], t=run.alert["t"],
                 why="Detection rules raise this alert. Everything after it is the investigation they do not do.")
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


def rule_based(events):
    """System A: a signature-style detector. Flags sensitive event types and explains nothing."""
    for e in events:
        a, k = e["attrs"], e["kind"]
        hit = (
            (k == "config" and not a.get("baseline") and not a.get("trivial"))
            or (k == "process" and a.get("suspicious"))
            or (k == "file" and (a.get("sensitive") or a.get("action") == "read_program"))
            or (k == "auth" and not a.get("failure") and (a.get("default_credentials") or (a.get("external") and not a.get("baseline", True))))
            or (k == "scan")
            or (k == "network" and not a.get("baseline", True) and not a.get("read") and not a.get("remote_session"))
        )
        if hit:
            return e
    return None
