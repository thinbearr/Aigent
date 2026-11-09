"""Canonical data model.

RawEvent   what an adapter produces: one log record in the canonical vocabulary (see docs/ADAPTERS.md).
Ticket     a change ticket / work order / maintenance window.
The engine turns RawEvents into *normalised events* (plain dicts, see normalise.py) that carry a `kind` and
analysis attributes. Ground truth is never part of any of these types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# Canonical event_type vocabulary understood by the normaliser. Adapters map their own log vocabulary onto it.
EVENT_TYPES = (
    "login_success", "login_failure", "mfa_challenge", "mfa_failure", "remote_session_start",
    "file_read", "process_exec", "port_scan", "network_enumeration", "network_connection", "tcp_session_open",
    "modbus_read", "modbus_write", "setpoint_change", "program_download", "program_upload", "sis_bypass_change",
    "sis_trip", "range_exceeded", "range_restored", "alarm_raised", "alarm_ack",
    "work_order_approved", "work_order_created", "work_order_closed",
)


def parse_ts(value) -> datetime:
    """Parse ISO-8601 / 'YYYY-MM-DD HH:MM:SS' / epoch seconds. Naive times are taken as UTC."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
    else:
        s = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            dt = datetime.fromtimestamp(float(s), tz=timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class RawEvent:
    ts: datetime
    host: str                       # asset id that logged / was the target of the event
    event_type: str                 # one of EVENT_TYPES (or anything else: it becomes kind "other")
    source: str = ""                # auth | network | host | plc | process | hmi | erp | historian ...
    actor: str | None = None
    src_ip: str | None = None
    dst_ip: str | None = None
    protocol: str | None = None
    outcome: str = "success"        # success | failure | blocked | info
    severity: str = "info"
    detail: dict[str, Any] = field(default_factory=dict)
    uid: str | None = None          # id in the original system, if any


@dataclass
class Ticket:
    id: str
    asset: str
    assigned_to: str
    start: datetime
    end: datetime
    requested_by: str = ""
    approved_by: str = ""
    change_type: str = "none"       # none | parameter | logic | safety_interlock
    status: str = "approved"        # approved | in_progress | closed | created | rejected
    description: str = ""
    approved: dict[str, float] = field(default_factory=dict)   # parameter -> maximum approved value

    VALID = ("approved", "in_progress", "closed")

    @property
    def valid(self) -> bool:
        return self.status in self.VALID
