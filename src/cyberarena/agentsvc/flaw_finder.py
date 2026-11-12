"""Identify WHICH security flaws are being violated, from evidence alone.

The agent does not know which breach-point switches are on. But a real analyst knows
what each class of weakness looks like in the logs. This module encodes those
signatures and reports the flaws it can SEE being exploited in the evidence — with the
event ids that justify each one. It never reads the plant's flag state or ground truth.
"""
from __future__ import annotations

# Each flaw: a human-readable identity plus a signature predicate over one evidence
# event. `code` matches the plant's breach-point ids only so a human can compare after
# the fact — the agent derives it purely from the evidence.
FLAWS = [
    {"code": "B1", "title": "Remote access without MFA", "layer": "L4", "severity": "high",
     "match": lambda e, d: e["event_type"] == "login_success" and d.get("method") == "remote" and not d.get("mfa"),
     "why": "A remote session was granted on a single factor — no one-time code was required."},
    {"code": "B2", "title": "Default administrator account in use", "layer": "L4", "severity": "high",
     "match": lambda e, d: e["event_type"] == "login_success" and e.get("actor") == "admin",
     "why": "The vendor-default 'admin' account authenticated — it should have been disabled."},
    {"code": "B3", "title": "Credentials exposed on a file share", "layer": "L4", "severity": "medium",
     "match": lambda e, d: e["event_type"] == "file_read" and "handover" in str(d.get("path", "")).lower(),
     "why": "A file containing reusable vendor credentials was read from the corporate share."},
    {"code": "B4", "title": "Work-order approval without separation of duty", "layer": "L4", "severity": "medium",
     "match": lambda e, d: e["event_type"] == "work_order_approved" and d.get("self_approved"),
     "why": "A maintenance work order was approved by its own requester."},
    {"code": "B5", "title": "Dual-homed historian / default local login", "layer": "L3", "severity": "high",
     "match": lambda e, d: e["event_type"] == "login_success" and d.get("method") == "historian-local",
     "why": "The historian accepted a local login reachable from the office network."},
    {"code": "B6", "title": "Plain-text credentials in engineering files", "layer": "L3", "severity": "medium",
     "match": lambda e, d: e["event_type"] == "file_read" and "project_config" in str(d.get("path", "")).lower(),
     "why": "An engineering project file holding a controller password was opened."},
    {"code": "B7", "title": "Unsigned PLC logic download", "layer": "L3→L1", "severity": "critical",
     "match": lambda e, d: e["event_type"] == "program_download" and e.get("change_type") == "logic" and e.get("outcome") == "success",
     "why": "The controller accepted a program download that changed its logic."},
    {"code": "B8", "title": "Over-permissive control-zone firewall rule", "layer": "L3/L4→L1", "severity": "high",
     "match": lambda e, d: e["event_type"] in ("network_connection", "network_enumeration") and ("140" in str(d.get("rule", "")) or "vendor" in str(d.get("rule", "")).lower()),
     "why": "A host outside the control zone reached a PLC through a leftover vendor firewall rule."},
    {"code": "B9", "title": "Unauthenticated controller write", "layer": "L1→L0", "severity": "high",
     "match": lambda e, d: e["event_type"] == "setpoint_change" and e.get("outcome") == "success" and d.get("src_host") not in (None, "hmi-01"),
     "why": "A setpoint write was accepted from a host other than the HMI — the controller required no authentication."},
    {"code": "B10", "title": "Shared operator account", "layer": "L2", "severity": "medium",
     "match": lambda e, d: e["event_type"] == "login_success" and e.get("actor") == "operator",
     "why": "The shared 'operator' console account was used — individual accountability is lost."},
    {"code": "B11", "title": "Safety-interlock (SIS) bypass over the network", "layer": "L1", "severity": "critical",
     "match": lambda e, d: e["event_type"] in ("sis_bypass_change", "modbus_write") and (d.get("tag") == "sis_bypass" or e["event_type"] == "sis_bypass_change") and d.get("new") not in (False, 0),
     "why": "The safety-trip bypass bit was set over the network rather than via the local key switch."},
]


def identify(events: list[dict]) -> list[dict]:
    """Return the flaws the evidence shows being exploited, each with its justifying events."""
    out = []
    for flaw in FLAWS:
        hits = []
        for e in events:
            d = e.get("detail") or {}
            try:
                if flaw["match"](e, d):
                    hits.append(e["id"])
            except Exception:
                continue
        if hits:
            out.append({"code": flaw["code"], "title": flaw["title"], "layer": flaw["layer"],
                        "severity": flaw["severity"], "why": flaw["why"],
                        "event_ids": [f"EV-{i}" for i in hits], "observations": len(hits)})
    sev = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    out.sort(key=lambda f: sev.get(f["severity"], 9))
    return out
