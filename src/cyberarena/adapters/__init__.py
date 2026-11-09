"""Adapters: real data in. Each adapter turns a source into canonical RawEvents / Tickets. They only read files."""
from __future__ import annotations

from pathlib import Path

import yaml

from ..core.schema import RawEvent
from . import csvjson, syslog, tickets  # noqa: F401
from .tickets import load_tickets  # noqa: F401


def load_events(path: str | Path, fmt: str | None = None, mapping: str | Path | dict | None = None) -> list[RawEvent]:
    """Load events from a file. fmt: csv | json | jsonl | syslog (guessed from the extension if omitted).
    mapping: optional YAML (or dict) with `columns`, `event_type_map`, `syslog_rules` — see docs/ADAPTERS.md."""
    p = Path(path)
    m = mapping if isinstance(mapping, dict) else (yaml.safe_load(Path(mapping).read_text(encoding="utf8")) if mapping else {})
    fmt = fmt or {".csv": "csv", ".json": "json", ".jsonl": "jsonl", ".ndjson": "jsonl"}.get(p.suffix.lower(), "syslog")
    if fmt in ("csv", "json", "jsonl"):
        return csvjson.read(p, fmt, m)
    if fmt == "syslog":
        return syslog.read(p, m)
    raise ValueError(f"unknown format '{fmt}'")
