"""Tickets adapter: a spreadsheet (CSV or XLSX) of change tickets / work orders / maintenance windows.

Columns (aliases accepted): ticket|id|number, asset|device, assigned_to|engineer|owner, start|window_start, end|window_end,
requested_by, approved_by, change_type|type (none|parameter|logic|safety_interlock), status (approved|in_progress|closed|created|rejected),
description|note, approved_values (e.g. "temp_sp=74;HEATER_GAIN=0.07" or a JSON object: the maximum value approved per parameter).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from ..core.schema import Ticket, parse_ts
from ..core.tickets import TicketStore

ALIASES = {
    "id": ("ticket", "id", "number", "ticket_id", "wo"),
    "asset": ("asset", "device", "equipment"),
    "assigned_to": ("assigned_to", "engineer", "owner", "assignee", "performed_by"),
    "start": ("start", "window_start", "from", "planned_start"),
    "end": ("end", "window_end", "to", "planned_end"),
    "requested_by": ("requested_by", "requester", "created_by"),
    "approved_by": ("approved_by", "approver"),
    "change_type": ("change_type", "type"),
    "status": ("status", "state"),
    "description": ("description", "note", "notes", "summary"),
    "approved_values": ("approved_values", "approved", "limits"),
}


def parse_values(v) -> dict[str, float]:
    if not v:
        return {}
    if isinstance(v, dict):
        return {k: float(x) for k, x in v.items()}
    s = str(v).strip()
    if s.startswith("{"):
        return {k: float(x) for k, x in json.loads(s).items()}
    out = {}
    for part in s.replace(",", ";").split(";"):
        for op in ("<=", "="):
            if op in part:
                k, x = part.split(op, 1)
                out[k.strip()] = float(x)
                break
    return out


def _rows(path: Path) -> list[dict]:
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError as e:  # pragma: no cover
            raise ImportError("reading .xlsx needs openpyxl: pip install cyberarena[xlsx]") from e
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
        it = ws.iter_rows(values_only=True)
        head = [str(h).strip() if h is not None else "" for h in next(it)]
        return [dict(zip(head, r)) for r in it if any(c is not None for c in r)]
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_tickets(path: str | Path, mapping: dict | None = None) -> TicketStore:
    custom = {c.lower(): s.lower() for c, s in ((mapping or {}).get("ticket_columns") or {}).items()}
    out = []
    for row in _rows(Path(path)):
        cols = {str(k).lower(): k for k in row}

        def pick(name, default=None):
            for cand in ([custom[name]] if name in custom else []) + list(ALIASES[name]):
                if cand in cols and row[cols[cand]] not in (None, ""):
                    return row[cols[cand]]
            return default

        for need in ("id", "asset", "assigned_to", "start", "end"):
            if pick(need) is None:
                raise ValueError(f"ticket row is missing '{need}': {row}")
        out.append(Ticket(id=str(pick("id")), asset=str(pick("asset")), assigned_to=str(pick("assigned_to")), start=parse_ts(pick("start")),
                          end=parse_ts(pick("end")), requested_by=str(pick("requested_by", "")), approved_by=str(pick("approved_by", "")),
                          change_type=str(pick("change_type", "none")), status=str(pick("status", "approved")).lower(),
                          description=str(pick("description", "")), approved=parse_values(pick("approved_values"))))
    return TicketStore(out)
