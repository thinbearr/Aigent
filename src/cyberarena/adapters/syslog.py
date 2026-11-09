"""Syslog adapter (RFC 3164 / RFC 5424 line formats, plus key=value messages).

Each line is split into timestamp, host, program and message. The message is then matched against rules; the first
rule that matches decides the canonical event_type, and its named regex groups become fields (user, src, ...).
A small default rule set covers sshd logins. Add your own in the mapping YAML under `syslog_rules:`
    - match: 'Setpoint (?P<tag>\\w+) changed from (?P<old>[\\d.]+) to (?P<new>[\\d.]+) by (?P<actor>\\S+)'
      event_type: setpoint_change
      source: plc
Lines no rule matches are kept as event_type "syslog" (the engine ignores them) and counted in the adapter stats.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from ..core.schema import RawEvent, parse_ts

RFC5424 = re.compile(r"^<\d+>\d+ (?P<ts>\S+) (?P<host>\S+) (?P<prog>\S+) \S+ \S+ (?:\[.*?\]|-) ?(?P<msg>.*)$")
RFC3164 = re.compile(r"^(?:<\d+>)?(?P<ts>[A-Z][a-z]{2}\s+\d+ \d\d:\d\d:\d\d) (?P<host>\S+) (?P<prog>[^\s:\[]+)(?:\[\d+\])?: ?(?P<msg>.*)$")
ISO_PREFIX = re.compile(r"^(?P<ts>\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:?\d\d)?) (?P<host>\S+) (?P<prog>[^\s:\[]+)(?:\[\d+\])?: ?(?P<msg>.*)$")
KV = re.compile(r'(\w+)=("[^"]*"|\S+)')

DEFAULT_RULES = [
    dict(match=r"Accepted (?:password|publickey) for (?P<actor>\S+) from (?P<src_ip>\S+)", event_type="login_success", source="auth"),
    dict(match=r"Failed password for (?:invalid user )?(?P<actor>\S+) from (?P<src_ip>\S+)", event_type="login_failure", source="auth", outcome="failure"),
    dict(match=r"Invalid user (?P<actor>\S+) from (?P<src_ip>\S+)", event_type="login_failure", source="auth", outcome="failure"),
]


def _ts(s: str, year: int) -> datetime:
    if re.match(r"^[A-Z][a-z]{2}\s", s):
        return datetime.strptime(f"{year} {s}", "%Y %b %d %H:%M:%S").replace(tzinfo=timezone.utc)
    return parse_ts(s)


def read(path: Path, m: dict) -> list[RawEvent]:
    rules = [dict(r, rx=re.compile(r["match"])) for r in (m.get("syslog_rules") or []) + DEFAULT_RULES]
    year = int(m.get("year", datetime.now(timezone.utc).year))
    out, skipped = [], 0
    for line in Path(path).read_text(encoding="utf8", errors="replace").splitlines():
        if not line.strip():
            continue
        mt = RFC5424.match(line) or ISO_PREFIX.match(line) or RFC3164.match(line)
        if not mt:
            skipped += 1
            continue
        ts, host, prog, msg = _ts(mt["ts"], year), mt["host"], mt["prog"], mt["msg"]
        detail = {k: v.strip('"') for k, v in KV.findall(msg)}
        et, src, outcome, fields = "syslog", prog, "success", {}
        for r in rules:
            g = r["rx"].search(msg)
            if g:
                et, src, outcome = r["event_type"], r.get("source", prog), r.get("outcome", "success")
                fields = {k: v for k, v in g.groupdict().items() if v is not None}
                break
        detail.update({k: v for k, v in fields.items() if k not in ("actor", "src_ip")})
        detail["raw"] = msg[:300]
        out.append(RawEvent(ts=ts, host=host, event_type=et, source=src, actor=fields.get("actor") or detail.get("user"),
                            src_ip=fields.get("src_ip") or detail.get("src"), outcome=outcome, detail=detail))
    return out
