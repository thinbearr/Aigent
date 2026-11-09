"""Evidence book, signal extraction and the confidence model.

Confidence in "this is a malicious incident" is a logistic function of weighted evidence:
    confidence = sigmoid((BIAS + sum(weights)) / TEMP)
Positive weights support the malicious hypothesis, negative weights a benign explanation.
The weights are hand-set judgement calls, not learned. They were tuned while building the scenario set,
so benchmark numbers measure the mechanism, not generalisation (see docs/LIMITATIONS.md).
"""
import math


BIAS = -1.0
TEMP = 2.5
THRESHOLD = 0.6           # confidence at or above this is declared an incident

# MITRE ATT&CK for ICS: indicative mapping (technique id, name)
MITRE = {
    "scan_activity": ("T0846", "Remote System Discovery"),
    "internal_enumeration": ("T0840", "Network Connection Enumeration"),
    "login_external_anomalous": ("T0859", "Valid Accounts"),
    "login_anomalous": ("T0859", "Valid Accounts"),
    "default_credentials_login": ("T0859", "Valid Accounts"),
    "credential_file_access": ("T0859", "Valid Accounts"),
    "suspicious_process": ("T0853", "Scripting"),
    "new_network_path": ("T0886", "Remote Services"),
    "plc_config_change": ("T0836", "Modify Parameter"),
    "plc_logic_change": ("T0889", "Modify Program"),
    "program_upload": ("T0845", "Program Upload"),
    "safety_bypass": ("T0880", "Loss of Safety"),
    "process_deviation": ("T0831", "Manipulation of Control"),
    "blocked_attempt": ("T0836", "Modify Parameter"),
}


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def signal_for_event(e, site):
    """Heuristic a single-pass analyst applies to one event. Returns (code, weight, text) or None."""
    k, a, asset = e["kind"], e["attrs"], e["asset"]
    ot = site.deep(asset)
    if k == "auth":
        if a.get("failure"):
            return ("login_anomalous", 0.5, "Failed authentication from outside") if a.get("external") else None
        if a.get("default_credentials"):
            return ("default_credentials_login", 1.0, "Login with a factory-default account")
        if not a.get("baseline", True):
            if a.get("external"):
                return ("login_external_anomalous", 1.5, "Remote login from the internet without MFA")
            return ("login_anomalous", 0.5 if ot else 1.0, "Login outside baseline" + (" in OT zone" if ot else ""))
    elif k == "process" and a.get("suspicious"):
        return ("suspicious_process", 1.5, "Unexpected script launched on an engineering host")
    elif k == "file":
        if a.get("sensitive") and a.get("action") == "read":
            return ("credential_file_access", 1.0, "File holding credentials was read")
        if a.get("action") == "read_program":
            return ("program_upload", 0.5, "Controller program was read out")
    elif k == "network" and not a.get("baseline", True) and not a.get("read"):
        if a.get("blocked"):
            return ("new_network_path", 0.5, "Blocked connection attempt across zones")
        return ("new_network_path", 0.7, "New network path between zones")
    elif k == "network" and a.get("read") and not a.get("baseline", True):
        return ("new_network_path", 0.4, "Controller read by a host that does not normally read it")
    elif k == "scan":
        if a.get("internal"):
            return ("internal_enumeration", 0.8, "Internal host enumerating the control subnet")
        return ("scan_activity", 0.6, "External port scan")
    elif k == "config" and not a.get("baseline", False) and not a.get("trivial"):
        if a.get("blocked"):
            return ("blocked_attempt", 1.0, "Controller change attempted but refused")
        p = a.get("param")
        if p == "sis_bypass":
            return ("safety_bypass", 2.0 if a.get("via") == "network" else 1.5, "Safety interlock bypass was set")
        if p == "logic":
            return ("plc_logic_change", 1.8, "Controller logic was replaced")
        w = 1.5
        if a.get("within_limits") is False:
            w += 0.6
        return ("plc_config_change", w, "Controller parameter changed" + (" beyond engineering limits" if a.get("within_limits") is False else ""))
    elif k == "process_state":
        if a.get("beyond"):
            return ("process_deviation", 0.8, "Process value beyond its alarm limit")
    return None


class EvidenceBook:
    def __init__(self):
        self.items = []

    def _next_id(self):
        return f"E-{len(self.items) + 1:02d}"

    def add(self, code, weight, text, events=(), source="observation", detail=None):
        item = dict(id=self._next_id(), code=code, weight=weight, text=text,
                    events=list(events), source=source, detail=detail or "")
        self.items.append(item)
        return item

    @property
    def score(self):
        return BIAS + sum(i["weight"] for i in self.items)

    @property
    def confidence(self):
        return sigmoid(self.score / TEMP)

    @property
    def incident(self):
        return self.confidence >= THRESHOLD

    def has(self, code):
        return any(i["code"] == code for i in self.items)
