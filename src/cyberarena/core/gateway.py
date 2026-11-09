"""Tool Gateway: the ONLY way an agent can look at anything. It is strictly read-only.

* Every tool is a read over the captured evidence, the ticket store or the site config. There is no write tool
  anywhere in the code base, and the allow-list below is checked before any tool runs.
* A sandbox scope rejects targets that are not assets of the site.
* Every call, allowed or denied, is appended to an audit log that ends up in the report.
"""
from __future__ import annotations

from datetime import timedelta

from .schema import parse_ts
from .site import Site
from .tickets import TicketStore

ALLOWED = {
    "Blue": {"get_log_summary", "query_events", "check_maintenance_schedule", "check_user_authorization",
             "check_change_scope", "get_asset_info"},
    "Forensics": {"get_log_summary", "query_events", "get_asset_info"},
    "Critic": set(),         # reviews evidence, has no tools
    "Orchestrator": set(),   # delegates, has no tools
}


class Gateway:
    def __init__(self, site: Site, tickets: TicketStore, events: list[dict]):
        self.site, self.tickets, self.events = site, tickets, events
        self.audit: list[dict] = []

    def _log(self, agent, tool, args, status, summary):
        entry = dict(n=len(self.audit) + 1, agent=agent, tool=tool, args=args, status=status, summary=summary)
        self.audit.append(entry)
        return entry

    def call(self, agent, tool, **args):
        """Returns (result, audit_entry). result is None when denied."""
        allowed = ALLOWED.get(agent, set())
        if tool not in allowed:
            reason = f"{agent} has no tool access" if not allowed else f"'{tool}' is not in the {agent} allow-list"
            return None, self._log(agent, tool, args, "DENIED", reason)
        target = args.get("target") or args.get("asset")
        if target and not self.site.known_asset(target):
            return None, self._log(agent, tool, args, "DENIED", f"target '{target}' is outside the sandbox scope")
        result, summary = getattr(self, "_t_" + tool)(**args)
        return result, self._log(agent, tool, args, "ALLOWED", summary)

    # ───────────── evidence reads
    def _t_get_log_summary(self):
        counts = {}
        for e in self.events:
            counts[e["kind"]] = counts.get(e["kind"], 0) + 1
        return counts, "log sources: " + ", ".join(f"{k}×{v}" for k, v in counts.items())

    def _t_query_events(self, kind=None, asset=None):
        evs = [e for e in self.events if (kind is None or e["kind"] == kind) and (asset is None or e["asset"] == asset)]
        return evs, f"{len(evs)} event(s)" + (f" of kind '{kind}'" if kind else "")

    def _t_get_asset_info(self, asset):
        a = self.site.assets.get(asset)
        return (dict(id=a.id, zone=a.zone, role=a.role) if a else None), (f"{asset}: {a.role} ({a.zone})" if a else "unknown asset")

    # ───────────── ticket and account reads
    def _names(self, asset):
        return self.site.asset_aliases.get(asset, [asset])

    def _t_check_maintenance_schedule(self, asset, at):
        t = self.tickets.covering(self._names(asset), parse_ts(at))
        if t:
            w = dict(found=True, ticket=t.id, asset=t.asset, user=t.assigned_to, requested_by=t.requested_by, approved_by=t.approved_by,
                     start=t.start.strftime("%H:%M"), end=t.end.strftime("%H:%M"), note=t.description, approved=dict(t.approved),
                     change_type=t.change_type)
            return w, f"window found for {asset}: ticket {t.id} ({w['start']}-{w['end']}, held by {t.assigned_to})"
        return dict(found=False), f"no approved maintenance window for {asset} at {at}"

    def _t_check_change_scope(self, asset, at):
        """Compare each value written to `asset` with what the covering ticket approves (only parameters it lists are judged)."""
        t = self.tickets.covering(self._names(asset), parse_ts(at))
        if not t or not t.approved:
            return dict(judged=False), "no ticket with approved values to compare against"
        over = []
        for e in self.events:
            a = e["attrs"]
            if e["kind"] != "config" or e["asset"] != asset or a.get("blocked"):
                continue
            if a.get("param") == "logic":
                for p, new in (a.get("changed") or {}).items():
                    if p in t.approved and isinstance(new, (int, float)) and new > t.approved[p] + 1e-9:
                        over.append(dict(param=p, new=new, approved=t.approved[p]))
            elif a.get("param") in t.approved and isinstance(a.get("new"), (int, float)) and a["new"] > t.approved[a["param"]] + 1e-9:
                over.append(dict(param=a["param"], new=a["new"], approved=t.approved[a["param"]]))
        if over:
            return (dict(judged=True, within=False, over=over, ticket=t.id),
                    "; ".join(f"{o['param']} written {o['new']} > approved {o['approved']}" for o in over))
        return dict(judged=True, within=True, ticket=t.id), "every listed parameter is within the ticket's approved value"

    def _t_check_user_authorization(self, user, asset, at=None):
        acct = self.site.accounts.get(user)
        if not acct:
            return dict(authorized=False, role="unknown"), f"{user}: unknown account"
        role = acct.get("role", "")
        when = parse_ts(at) if at else None
        held = self.tickets.held_by(user, self._names(asset), when)
        anywhere = self.tickets.held_by(user, None, when)
        if role in self.site.ticket_roles:
            ok = bool(anywhere)                       # an outside contractor is authorised only while holding a ticket
            ticket = (held or anywhere or [None])[0]
        else:
            ok = asset in self.site.roles.get(role, set())
            ticket = held[0] if (ok and held) else None
        ok = ok and acct.get("enabled", True)
        return (dict(authorized=ok, role=role, ticket=getattr(ticket, "id", None) if ok else None),
                f"{user} ({role}) " + (f"authorised for {asset}" + (f", ticket {ticket.id}" if ticket else "") if ok
                                       else f"NOT authorised for {asset}" + (" (no ticket)" if role in self.site.ticket_roles else "")))
