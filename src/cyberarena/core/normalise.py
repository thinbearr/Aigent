"""RawEvent -> normalised event.

A normalised event is a dict:
    {id, t, asset, kind, user, src, dst, attrs, detail, outcome, severity, source}
`kind` is one of auth | network | scan | file | process | config | process_state | erp | hmi | other.
Every attribute is a pure function of the event, the site config and the events before it (for example, "was this
remote login preceded by an MFA challenge?"). Nothing here can see ground truth or tickets.
"""
from __future__ import annotations

from datetime import timedelta

from .schema import RawEvent
from .site import Site

MFA_WINDOW = timedelta(minutes=10)


class Normaliser:
    def __init__(self, site: Site):
        self.site = site
        self.challenge: dict[str, object] = {}
        self.login_mfa: dict[str, bool] = {}
        self.n = 0

    def run(self, raws: list[RawEvent]) -> list[dict]:
        out = []
        for r in sorted(raws, key=lambda r: r.ts):
            e = self(r)
            if e is not None:
                out.append(e)
        return out

    def __call__(self, e: RawEvent) -> dict | None:
        site, d = self.site, e.detail or {}
        et, actor = e.event_type, e.actor
        self.n += 1
        src = site.host_of_ip(e.src_ip)
        acct = site.accounts.get(actor or "", {})
        base = dict(id=e.uid or f"EV-{self.n}", t=e.ts.strftime("%Y-%m-%d %H:%M:%S"), asset=e.host, kind="other", user=actor,
                    src=src, dst=None, attrs={}, outcome=e.outcome, severity=e.severity, source=e.source)

        def out(kind, detail, **attrs):
            base.update(kind=kind, detail=detail, attrs=attrs)
            return base

        if et == "mfa_challenge":
            self.challenge[actor or ""] = e.ts
            return None
        ext = site.is_external(e.src_ip)
        if et == "mfa_failure":
            return out("auth", f"MFA code rejected for {actor} from {e.src_ip}", external=ext, failure=True, baseline=False)
        if et == "login_failure":
            return out("auth", f"Failed login for {actor} on {e.host} ({d.get('reason', 'bad credentials')})", external=ext, failure=True, baseline=True)
        if et == "login_success":
            via = d.get("method") or ("remote" if e.host in site.remote_gateways else "local")
            ch = self.challenge.pop(actor or "", None)
            mfa = bool(d.get("mfa")) or (ch is not None and (e.ts - ch) < MFA_WINDOW)
            self.login_mfa[actor or ""] = mfa
            default = bool(acct.get("default"))
            if via == "remote":
                baseline = mfa
            elif via == "historian-local":
                baseline = False if src != e.host and not site.deep(src) else not default
            else:
                baseline = not default
            txt = f"{actor} logged in to {e.host} via {via} from {e.src_ip}" + (" (MFA passed)" if mfa else (" (no MFA)" if via == "remote" else ""))
            return out("auth", txt, external=ext, mfa=mfa, baseline=baseline, default_credentials=default,
                       shared_account=bool(acct.get("shared")), via=via)
        if et == "remote_session_start":
            gw = next(iter(site.remote_gateways), "gateway")
            base["src"], base["dst"] = gw, e.host
            return out("network", f"Remote desktop session for {actor} opened on {e.host} via {gw}",
                       baseline=self.login_mfa.get(actor or "", False), port=3389, remote_session=True)
        if et == "file_read":
            path = str(d.get("path", ""))
            sens = any(s in path.lower() for s in site.sensitive_files)
            return out("file", f"{actor} read {path} on {e.host}", action="read", path=path, sensitive=sens)
        if et == "process_exec":
            susp = d.get("suspicious")
            if susp is None:
                susp = "unexpected" in str(d.get("note", "")).lower()
            return out("process", f"{actor} ran '{d.get('process', '?')}' on {e.host}", name=d.get("process"), suspicious=bool(susp))
        if et == "port_scan":
            return out("scan", f"Port scan of {e.host} from {e.src_ip}", external=ext, ports=d.get("ports"))
        if et == "network_enumeration":
            base["src"], base["dst"] = src, e.host
            return out("scan", f"Network enumeration of the control subnet from {src}", external=False, internal=True)
        if et == "network_connection":
            s = d.get("src_host", src)
            dst = d.get("dst_host", e.host)
            base["src"], base["dst"] = s, dst
            return out("network", f"{s} -> {dst} {e.protocol or ''} {e.outcome} ({d.get('rule', '')})",
                       baseline=(s in site.trusted_sources) and e.outcome == "success", port=d.get("dst_port"),
                       blocked=e.outcome == "blocked", rule=d.get("rule"))
        if et == "tcp_session_open":
            if not ext:
                return None
            base["src"], base["dst"] = src, e.host
            return out("network", f"External client {e.src_ip} opened {e.protocol or 'a session'} to {e.host}", baseline=False, external=True)
        sh = d.get("src_host") or src
        if et == "modbus_read":
            base["src"], base["dst"] = sh, e.host
            return out("network", f"{sh} read {d.get('count', '?')} register(s) from {e.host}", baseline=sh in site.trusted_sources, read=True)
        if et == "setpoint_change":
            base["src"], base["dst"] = sh, e.host
            tag, old = d.get("tag"), d.get("old")
            new = d.get("new", d.get("requested"))
            blocked = e.outcome == "blocked"
            r = site.routine
            routine = (sh in r.get("sources", []) and actor in r.get("operators", []) and not blocked
                       and isinstance(old, (int, float)) and isinstance(new, (int, float)) and abs(new - old) <= r.get("max_delta", 1.0))
            wl = d.get("within_engineering_limits")
            if wl is None:
                wl = site.within_limits(tag, new)
            return out("config", f"{actor} {'attempted to set' if blocked else 'set'} {tag} {old} -> {new} on {e.host} from {sh}"
                                 + (f" (refused: {d.get('error')})" if blocked else ""),
                       param=tag, old=old, new=new, blocked=blocked, baseline=routine, within_limits=True if wl is None else wl,
                       change_type="parameter")
        if et == "modbus_write":
            base["src"], base["dst"] = sh, e.host
            tag = d.get("tag") or f"register {d.get('address')}"
            if e.outcome == "failure":
                return out("config", f"Write to {tag} on {e.host} failed ({d.get('error', 'error')})", param=tag, blocked=True,
                           baseline=sh in site.trusted_sources, trivial=True)
            return out("config", f"{actor or 'client'} wrote {tag}={d.get('new', d.get('requested'))} on {e.host} from {sh}",
                       param=tag, old=d.get("old"), new=d.get("new"), blocked=e.outcome == "blocked", baseline=sh in site.trusted_sources)
        if et == "program_download":
            base["src"], base["dst"] = sh, e.host
            ch = d.get("changed_parameters") or {}
            blocked = e.outcome == "blocked"
            txt = f"{actor} {'attempted a ' if blocked else ''}logic download to {e.host} from {sh}"
            if ch:
                txt += ": " + ", ".join(f"{k} {v.get('old')} -> {v.get('new')}" for k, v in ch.items())
            return out("config", txt, param="logic", blocked=blocked, baseline=False, changed={k: v.get("new") for k, v in ch.items()})
        if et == "program_upload":
            base["src"], base["dst"] = sh, e.host
            return out("file", f"{actor} read the controller program from {e.host}", action="read_program", sensitive=True, path=f"{e.host}/program")
        if et == "sis_bypass_change":
            base["src"], base["dst"] = sh, e.host
            via = d.get("via", "network")
            return out("config", f"Safety bypass set to {d.get('new')} on {e.host} via {via} by {actor}", param="sis_bypass",
                       old=d.get("old"), new=d.get("new"), baseline=not bool(d.get("new")), via=via)
        if et == "sis_trip":
            return out("process_state", f"Safety system tripped the process ({d.get('cause')})", beyond=True, tag="sis", state="trip")
        if et == "range_exceeded":
            state = d.get("state")
            return out("process_state", f"{d.get('tag')} reached {d.get('value')} {d.get('unit', '')} ({state})",
                       beyond=state in ("alarm", "trip"), tag=d.get("tag"), value=d.get("value"), state=state)
        if et == "range_restored":
            return out("process_state", f"{d.get('tag')} back to normal", beyond=False, restored=True, tag=d.get("tag"))
        if et == "alarm_raised":
            return out("process_state", f"Alarm: {d.get('tag')} {d.get('level')} ({d.get('value')})", beyond=True, tag=d.get("tag"), alarm=True)
        if et == "alarm_ack":
            return out("hmi", f"{actor} acknowledged an alarm on {e.host}")
        if et.startswith("work_order"):
            return out("erp", f"{et.replace('_', ' ')} {d.get('number', '')} by {actor}", number=d.get("number"))
        return out("other", f"{e.source}:{et}", noise=True)
