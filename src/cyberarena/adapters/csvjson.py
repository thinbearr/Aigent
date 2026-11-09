"""CSV / JSON / JSON-lines adapter.

Expected columns (aliases accepted, case-insensitive): ts|timestamp|time, host|asset|device, event_type|event|action,
source, actor|user|username, src_ip|src, dst_ip|dst, protocol|proto, outcome|result|status, severity, uid|id.
Every other column goes into `detail` (so `tag`, `old`, `new`, `path`, `method`, `mfa`, ... are all available to the
engine). A column named `detail` may hold a JSON object. Values like "true"/"12.5" are typed automatically.
Use a mapping YAML for other column names (`columns:`) and other vocabularies (`event_type_map:`).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from ..core.schema import RawEvent, parse_ts

ALIASES = {
    "ts": ("ts", "timestamp", "time", "datetime", "@timestamp"),
    "host": ("host", "asset", "device", "hostname"),
    "event_type": ("event_type", "event", "action", "type"),
    "source": ("source", "log_source", "category"),
    "actor": ("actor", "user", "username", "account"),
    "src_ip": ("src_ip", "src", "source_ip", "client_ip"),
    "dst_ip": ("dst_ip", "dst", "dest_ip", "destination_ip"),
    "protocol": ("protocol", "proto"),
    "outcome": ("outcome", "result", "status"),
    "severity": ("severity", "level"),
    "uid": ("uid", "id", "event_id"),
}
OUTCOMES = {"success": "success", "ok": "success", "allowed": "success", "allow": "success", "accepted": "success",
            "failure": "failure", "fail": "failure", "failed": "failure", "error": "failure", "denied": "blocked",
            "blocked": "blocked", "drop": "blocked", "deny": "blocked", "refused": "blocked", "info": "info"}


def _typed(v):
    if isinstance(v, str):
        s = v.strip()
        if s.lower() in ("true", "false"):
            return s.lower() == "true"
        if s == "":
            return None
        try:
            return int(s) if s.lstrip("-").isdigit() else float(s)
        except ValueError:
            return s
    return v


def to_event(row: dict, m: dict | None = None) -> RawEvent:
    m = m or {}
    cols = {k.lower(): k for k in row}
    custom = {c.lower(): src.lower() for c, src in (m.get("columns") or {}).items()}      # canonical -> source column

    def pick(name):
        for cand in ([custom[name]] if name in custom else []) + list(ALIASES[name]):
            if cand in cols and row[cols[cand]] not in (None, ""):
                return cols[cand], row[cols[cand]]
        return None, None

    used = set()
    vals = {}
    for name in ALIASES:
        k, v = pick(name)
        if k is not None:
            used.add(k)
            vals[name] = v
    if "ts" not in vals or "host" not in vals or "event_type" not in vals:
        raise ValueError(f"row needs ts, host and event_type columns (found {sorted(row)})")
    et = str(vals["event_type"]).strip()
    et = (m.get("event_type_map") or {}).get(et, et)
    detail = {}
    if isinstance(row.get(cols.get("detail", "detail")), (dict, str)) and "detail" in cols:
        d = row[cols["detail"]]
        try:
            detail.update(d if isinstance(d, dict) else json.loads(d))
        except (ValueError, TypeError):
            detail["note"] = d
        used.add(cols["detail"])
    for k, v in row.items():
        if k not in used and v not in (None, ""):
            detail[k.lower()] = _typed(v)
    outcome = OUTCOMES.get(str(vals.get("outcome", "success")).strip().lower(), "success")
    return RawEvent(ts=parse_ts(vals["ts"]), host=str(vals["host"]), event_type=et, source=str(vals.get("source", "")),
                    actor=(str(vals["actor"]) if "actor" in vals else None), src_ip=(str(vals["src_ip"]) if "src_ip" in vals else None),
                    dst_ip=(str(vals["dst_ip"]) if "dst_ip" in vals else None), protocol=(str(vals["protocol"]) if "protocol" in vals else None),
                    outcome=outcome, severity=str(vals.get("severity", "info")), detail=detail, uid=(str(vals["uid"]) if "uid" in vals else None))


def read(path: Path, fmt: str, m: dict) -> list[RawEvent]:
    if fmt == "csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    elif fmt == "jsonl":
        rows = [json.loads(line) for line in open(path, encoding="utf8") if line.strip()]
    else:
        data = json.loads(Path(path).read_text(encoding="utf8"))
        rows = data["events"] if isinstance(data, dict) else data
    return [to_event(r, m) for r in rows]
