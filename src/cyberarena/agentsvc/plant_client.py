"""HTTP client to the plant's read-only evidence API. No database coupling."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

EVIDENCE_TOKEN = os.getenv("EVIDENCE_TOKEN", "arena-evidence-token")

# The target plant URL is mutable at runtime: the agent starts UNconnected and the operator
# points it at a plant from the UI (POST /agent/connect). This keeps the demo honest — the agent
# only reaches the factory once someone connects it.
_STATE = {"url": os.getenv("PLANT_URL", "http://localhost:8000").rstrip("/"),
          "connected": False}

# Back-compat module attribute (read-only snapshot at import).
PLANT_URL = _STATE["url"]


def plant_url() -> str:
    return _STATE["url"]


def set_plant_url(url: str) -> str:
    _STATE["url"] = (url or "").strip().rstrip("/")
    return _STATE["url"]


def is_connected() -> bool:
    return _STATE["connected"]


def set_connected(v: bool) -> None:
    _STATE["connected"] = bool(v)


class PlantUnavailable(RuntimeError):
    pass


def _get(path: str) -> dict:
    base = _STATE["url"]
    req = urllib.request.Request(base + path, headers={"x-evidence-token": EVIDENCE_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise PlantUnavailable(f"plant returned {e.code} for {path}")
    except urllib.error.URLError as e:
        raise PlantUnavailable(f"cannot reach plant at {base}: {e.reason}")


def fetch_events(since_id: int = 0) -> list[dict]:
    """Page through the plant's evidence log."""
    out: list[dict] = []
    cursor = since_id
    while True:
        page = _get(f"/evidence/events?since_id={cursor}&limit=2000")
        evs = page.get("events", [])
        out.extend(evs)
        if len(evs) < 2000:
            break
        cursor = page["last_id"]
    return out


def fetch_tickets() -> list[dict]:
    try:
        return _get("/evidence/tickets").get("tickets", [])
    except PlantUnavailable:
        return []


def fetch_sources() -> dict:
    return _get("/evidence/sources").get("sources", {})


def plant_health() -> dict:
    return _get("/evidence/health")
