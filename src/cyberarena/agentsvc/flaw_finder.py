"""Identify WHICH security flaws were actually exploited, from evidence alone — in plain language.

The agent does not know which breach-point switches are on. A real analyst knows what each
class of weakness looks like in the logs. This module encodes those signatures and reports the
flaws it can SEE being used in the evidence it is given — with the event ids that justify each
one. It never reads the plant's flag state or any ground truth.

Two things keep it honest (so Blue does not "score everything"):
  1. It is only ever handed the events from the CURRENT round (the investigate service scopes
     the log to what happened after the Red agent started), so last round's findings do not
     linger.
  2. A few weaknesses are *standing* ones that can also look like normal work — a default
     admin login, the shared operator account. Those are marked `ambiguous=True` and are only
     reported when the surrounding evidence actually looks like an incident. A flaw that merely
     *exists* is not the same as one that was *exploited*.

Every flaw carries a plain-English name and explanation so anyone — not just a SOC analyst —
can read the report.
"""
from __future__ import annotations

# code      — matches the plant's hidden breach-point id, only so a human can compare afterwards.
# title     — the technical name.
# plain     — the same thing in everyday words.
# means     — what it let the attacker actually do, in one sentence.
# fix       — the one-line plain-language fix.
# ambiguous — True if this pattern can also appear in ordinary, authorised work (see note above).
# match     — signature predicate over one evidence event (event, detail).
FLAWS = [
    {"code": "B1", "title": "Remote access without MFA", "layer": "L4", "severity": "high",
     "plain": "Remote login needed only a password",
     "means": "Someone logged in from outside the factory with just a stolen password — there was no second check (like a code on a phone) to stop them.",
     "fix": "Turn on two-step verification for every remote login and change the shared vendor password.",
     "ambiguous": False,
     "match": lambda e, d: e["event_type"] == "login_success" and d.get("method") == "remote" and not d.get("mfa")},

    {"code": "B2", "title": "Default administrator account in use", "layer": "L4", "severity": "high",
     "plain": "The out-of-the-box 'admin' account still worked",
     "means": "The factory kept the vendor's default 'admin' login, so an attacker just guessed the obvious username and password to get in.",
     "fix": "Disable the default 'admin' account and give each person their own named login.",
     "ambiguous": True,
     "match": lambda e, d: e["event_type"] == "login_success" and e.get("actor") == "admin"},

    {"code": "B3", "title": "Credentials exposed on a file share", "layer": "L4", "severity": "medium",
     "plain": "A password was sitting in a file on a shared drive",
     "means": "An attacker opened a handover note on the office file share and found a working password written inside it.",
     "fix": "Delete passwords from files and shares; keep them in a password vault.",
     "ambiguous": False,
     "match": lambda e, d: e["event_type"] == "file_read" and "handover" in str(d.get("path", "")).lower()},

    {"code": "B4", "title": "Work-order approval without separation of duty", "layer": "L4", "severity": "medium",
     "plain": "Someone approved their own maintenance request",
     "means": "The same person asked for a change and signed it off themselves, so no second person ever checked it — a forged 'authorised' change.",
     "fix": "Require a different supervisor to approve every change request.",
     "ambiguous": False,
     "match": lambda e, d: e["event_type"] == "work_order_approved" and d.get("self_approved")},

    {"code": "B5", "title": "Dual-homed historian / default local login", "layer": "L3", "severity": "high",
     "plain": "A bridge computer let office users log straight in",
     "means": "The history-logging computer sits on both the office and factory networks and accepted a default local login, giving an attacker a foothold inside the plant network.",
     "fix": "Remove the office-side connection and require proper single sign-on, not a local default account.",
     "ambiguous": False,
     "match": lambda e, d: e["event_type"] == "login_success" and d.get("method") == "historian-local"},

    {"code": "B6", "title": "Plain-text credentials in engineering files", "layer": "L3", "severity": "medium",
     "plain": "A controller password was saved in an engineering file",
     "means": "An attacker opened a project file on an engineer's PC and read the password for the machine controller straight out of it.",
     "fix": "Never store controller passwords in project files; use a vault reference instead.",
     "ambiguous": False,
     "match": lambda e, d: e["event_type"] == "file_read" and "project_config" in str(d.get("path", "")).lower()},

    {"code": "B7", "title": "Unsigned PLC logic download", "layer": "L3→L1", "severity": "critical",
     "plain": "The machine controller accepted new, unverified program code",
     "means": "The controller that runs the mixing tank loaded a new program with no signature check — so an attacker could change how the machine behaves.",
     "fix": "Only let the controller accept signed programs, and require a work order for any logic change.",
     "ambiguous": False,
     "match": lambda e, d: e["event_type"] == "program_download" and e.get("change_type") == "logic" and e.get("outcome") == "success"},

    {"code": "B8", "title": "Over-permissive control-zone firewall rule", "layer": "L3/L4→L1", "severity": "high",
     "plain": "A leftover firewall hole reached the machine floor",
     "means": "An old 'temporary' firewall rule was still open, letting a computer outside the control zone talk directly to the machine controller.",
     "fix": "Delete the leftover vendor firewall rule and keep IT and factory networks separated.",
     "ambiguous": False,
     "match": lambda e, d: e["event_type"] in ("network_connection", "network_enumeration") and ("140" in str(d.get("rule", "")) or "vendor" in str(d.get("rule", "")).lower())},

    {"code": "B9", "title": "Unauthenticated controller write", "layer": "L1→L0", "severity": "high",
     "plain": "The controller accepted commands from the wrong computer",
     "means": "A machine setting was changed by a computer that is not the operator's station, and the controller asked for no proof of who it was.",
     "fix": "Only accept machine commands from the operator station, and require authentication for writes.",
     "ambiguous": False,
     "match": lambda e, d: e["event_type"] == "setpoint_change" and e.get("outcome") == "success" and d.get("src_host") not in (None, "hmi-01")},

    {"code": "B10", "title": "Shared operator account", "layer": "L2", "severity": "medium",
     "plain": "Everyone shares one 'operator' login",
     "means": "The control screen uses a single shared 'operator' account, so an attacker who got it blends in and no one can tell who did what.",
     "fix": "Give each operator their own login so actions can be traced to a person.",
     "ambiguous": True,
     "match": lambda e, d: e["event_type"] == "login_success" and e.get("actor") == "operator"},

    {"code": "B11", "title": "Safety-interlock (SIS) bypass over the network", "layer": "L1", "severity": "critical",
     "plain": "The safety shut-off was switched off remotely",
     "means": "The safety system that trips the machine on over-temperature/over-pressure was disabled over the network instead of with the physical key — removing the last line of protection.",
     "fix": "Allow the safety bypass only with the local physical key switch, never over the network.",
     "ambiguous": False,
     # Must have SUCCEEDED — a blocked bypass attempt still emits a modbus_write, and that is the
     # safety system doing its job, not a breach. Require outcome=success and the bit actually set.
     "match": lambda e, d: e.get("outcome") == "success" and (
         (e["event_type"] == "sis_bypass_change" and d.get("new") not in (False, 0, None))
         or (e["event_type"] == "modbus_write" and d.get("tag") == "sis_bypass"))},
]

_SEV = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def identify(events: list[dict], incident: bool = True, scoped: bool = False) -> list[dict]:
    """Return the flaws the evidence shows being exploited, each with its justifying events.

    `scoped` means the caller already trimmed `events` to the current round (everything after the
    Red run began). Within a round, blocked exploits leave no evidence and the normal bots never
    use a default/shared login, so every signature match is a real breach and we trust all of them.

    When the log is NOT scoped (a full-history sweep), the *ambiguous* standing weaknesses (a
    default-admin or shared-operator login, which can also appear in ordinary work) are only
    reported if the investigation also concluded an incident — so the agent does not flag flaws
    that merely exist rather than having been exploited.
    """
    out = []
    for flaw in FLAWS:
        if flaw["ambiguous"] and not scoped and not incident:
            continue
        hits = []
        for e in events:
            d = e.get("detail") or {}
            try:
                if flaw["match"](e, d):
                    hits.append(e["id"])
            except Exception:
                continue
        if hits:
            out.append({
                "code": flaw["code"], "title": flaw["title"], "plain": flaw["plain"],
                "means": flaw["means"], "fix": flaw["fix"], "layer": flaw["layer"],
                "severity": flaw["severity"],
                "event_ids": [f"EV-{i}" for i in hits], "observations": len(hits),
            })
    out.sort(key=lambda f: _SEV.get(f["severity"], 9))
    return out
