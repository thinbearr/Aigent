"""Tool Gateway: the only way an agent can touch the (simulated) plant.

Every call is checked against a per-agent allow-list and a sandbox scope, then written to an audit log.
Scope is enforced here, in code. It is not left to the model's own judgement.
"""
from . import sim

ALLOWED = {
    "Blue": {"get_log_summary", "query_events", "check_maintenance_schedule",
             "check_user_authorization", "verify_firmware_signature", "get_asset_info"},
    "Forensics": {"get_log_summary", "query_events", "get_asset_info"},
    "Red": {"discover_assets", "inspect_configuration", "check_exposure"},
    "Critic": set(),         # the Critic reviews evidence; it never touches the plant
    "Orchestrator": set(),   # the Orchestrator delegates; it never touches the plant
}


class Gateway:
    def __init__(self, scn=None, clock=lambda: ""):
        self.scn = scn
        self.audit = []
        self.clock = clock

    def _log(self, agent, tool, args, status, summary):
        entry = dict(n=len(self.audit) + 1, agent=agent, tool=tool, args=args, status=status, summary=summary)
        self.audit.append(entry)
        return entry

    def call(self, agent, tool, **args):
        """Returns (result, audit_entry). result is None when denied."""
        if tool not in ALLOWED.get(agent, set()):
            reason = (f"{agent} has no tool access" if not ALLOWED.get(agent)
                      else f"'{tool}' is not in the {agent} allow-list")
            return None, self._log(agent, tool, args, "DENIED", reason)
        target = args.get("target") or args.get("asset")
        if target and target not in sim.SANDBOX_ASSETS:
            return None, self._log(agent, tool, args, "DENIED", f"target '{target}' is outside the sandbox scope")
        fn = getattr(self, "_t_" + tool)
        result, summary = fn(**args)
        return result, self._log(agent, tool, args, "ALLOWED", summary)

    # ───────────── read tools over the scripted scenario
    def _t_get_log_summary(self):
        counts = {}
        for e in self.scn["events"]:
            counts[e["kind"]] = counts.get(e["kind"], 0) + 1
        return counts, "log sources: " + ", ".join(f"{k}×{v}" for k, v in counts.items())

    def _t_query_events(self, kind=None, asset=None):
        evs = [e for e in self.scn["events"] if (kind is None or e["kind"] == kind) and (asset is None or e["asset"] == asset)]
        return evs, f"{len(evs)} event(s)" + (f" of kind '{kind}'" if kind else "")

    def _t_get_asset_info(self, asset):
        a = sim.ASSETS.get(asset)
        return a, (f"{asset}: {a['label']} ({a['zone']})" if a else "unknown asset")

    def _t_check_maintenance_schedule(self, asset, at):
        for w in self.scn["context"]["maintenance"]:
            if w["asset"] == asset and w["start"] <= at[:5] <= w["end"]:
                return dict(found=True, **w), f"window found for {asset}: {w['ticket']} ({w['start']}-{w['end']})"
        return dict(found=False), f"no maintenance window for {asset} at {at}"

    def _t_check_user_authorization(self, user, asset):
        u = self.scn["context"]["users"].get(user)
        if not u:
            return dict(authorized=False, role="unknown"), f"{user}: unknown account"
        ok = asset in u["authorized"]
        ticket = None
        if ok:
            for w in self.scn["context"]["maintenance"]:
                if w["asset"] == asset and w["user"] == user:
                    ticket = w["ticket"]
        return dict(authorized=ok, role=u["role"], ticket=ticket), \
            f"{user} ({u['role']}) " + (f"authorised for {asset}" + (f", ticket {ticket}" if ticket else "") if ok else f"NOT authorised for {asset}")

    def _t_verify_firmware_signature(self, asset):
        f = self.scn["context"]["firmware"].get(asset)
        if not f:
            return dict(found=False), f"no firmware record for {asset}"
        valid = f["signed"] and f["hash_match"]
        return dict(found=True, valid=valid, **f), f"firmware on {asset}: " + ("valid vendor signature" if valid else "signature INVALID / hash mismatch")

    # ───────────── Red agent read-only assessment tools
    def _t_discover_assets(self):
        return list(sim.ASSETS), f"{len(sim.ASSETS)} assets discovered"

    def _t_inspect_configuration(self, asset):
        return sim.ASSETS[asset]["config"], f"{asset} config: " + ", ".join(f"{k}={v}" for k, v in sim.ASSETS[asset]["config"].items())

    def _t_check_exposure(self, asset):
        c = sim.ASSETS[asset]["config"]
        return dict(internet_exposed=c.get("internet_exposed", False)), f"{asset} internet-exposed={c.get('internet_exposed', False)}"


# Actions the demo deliberately tries to perform, to show the gateway refusing them.
PROBES = [
    ("Blue", "write_plc_config", dict(asset="PLC-02", param="motor_speed_limit", value=9999)),
    ("Red", "scan_external", dict(target="8.8.8.8")),
    ("Critic", "query_events", dict(kind="config")),
    ("Blue", "delete_logs", dict(asset="VPN-GW")),
]


def probe():
    g = Gateway()
    out = []
    for agent, tool, args in PROBES:
        _, entry = g.call(agent, tool, **args)
        out.append(entry)
    return out
