"""Evidence store, signal extraction and the confidence model.

Confidence in "this is a malicious incident" is a logistic function of weighted evidence:
    confidence = sigmoid((BIAS + sum(weights)) / TEMP)
Positive weights support the malicious hypothesis; negative weights support a benign explanation.
Phase-1 weights are hand-set and illustrative. They are not learned from data.
"""
import math

BIAS = -1.0
TEMP = 2.5
THRESHOLD = 0.6          # confidence at or above this is declared an incident

ZONE_OT = {"OT", "Control", "Process"}

# MITRE ATT&CK for ICS: indicative mapping (technique id, name)
MITRE = {
    "scan_activity": ("T0846", "Remote System Discovery"),
    "login_external_anomalous": ("T0859", "Valid Accounts"),
    "login_anomalous": ("T0859", "Valid Accounts"),
    "default_credentials_login": ("T0859", "Valid Accounts"),
    "suspicious_process": ("T0886", "Remote Services"),
    "credential_dumping_tool": ("T0859", "Valid Accounts"),
    "new_network_path": ("T0886", "Remote Services"),
    "plc_config_change": ("T0836", "Modify Parameter"),
    "process_deviation": ("T0831", "Manipulation of Control"),
    "firmware_upload": ("T0857", "System Firmware"),
    "wiper_activity": ("T0809", "Data Destruction"),
    "comms_loss": ("T0815", "Denial of View"),
    "log_destruction": ("T0872", "Indicator Removal on Host"),
}


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def signal_for_event(e):
    """Heuristic a single-pass analyst applies to one event. Returns (code, weight, text) or None."""
    k, a, asset = e["kind"], e["attrs"], e["asset"]
    zone_ot = None
    from . import sim
    zone_ot = sim.ASSETS[asset]["zone"] in ZONE_OT
    if k == "auth":
        if a.get("default_credentials"):
            return ("default_credentials_login", 1.0, "Login with factory default credentials")
        if not a.get("baseline", True):
            if a.get("external"):
                return ("login_external_anomalous", 1.0, "External login outside baseline, no MFA")
            return ("login_anomalous", 0.5 if zone_ot else 1.0, "Login outside baseline" + (" in OT zone" if zone_ot else ""))
    elif k == "privilege":
        return ("privilege_escalation", 1.0, "Privilege escalation to administrator")
    elif k == "process" and a.get("suspicious"):
        if a.get("tool") == "credential_dumping":
            return ("credential_dumping_tool", 2.0, "Credential dumping tool executed")
        return ("suspicious_process", 1.0, f"Remote execution tool ({a.get('name')}) launched")
    elif k == "network" and not a.get("baseline", True):
        return ("new_network_path", 0.7, "New network path between zones")
    elif k == "config":
        if e["asset"] == "VPN-GW":
            return ("gateway_config_change", 1.0, "Gateway configuration changed (new admin account)")
        return ("plc_config_change", 1.0, "PLC parameter changed")
    elif k == "firmware":
        return ("firmware_upload", 0.8, "Firmware image uploaded to controller")
    elif k == "comms":
        return ("comms_loss", 0.8, "Controller lost communication with grid operator")
    elif k == "process_state":
        if a.get("beyond"):
            return ("process_deviation", 0.8, "Process value beyond configured limit")
        return ("process_deviation_minor", 0.3, "Minor process deviation")
    elif k == "file" and a.get("action") == "wipe":
        return ("wiper_activity", 2.0, "Destructive wiper executed")
    elif k == "scan":
        return ("scan_activity", 0.6, "External port scan")
    elif k == "reset" and a.get("logs_lost"):
        return ("log_destruction", 1.0, "Device factory-reset, local logs destroyed")
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
