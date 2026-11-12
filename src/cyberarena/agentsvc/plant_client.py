"""HTTP client to the plant's read-only evidence API. No database coupling."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

PLANT_URL = os.getenv("PLANT_URL", "http://localhost:8000").rstrip("/")
EVIDENCE_TOKEN = os.getenv("EVIDENCE_TOKEN", "arena-evidence-token")


class PlantUnavailable(RuntimeError):
    pass


def _get(path: str) -> dict:
    req = urllib.request.Request(PLANT_URL + path, headers={"x-evidence-token": EVIDENCE_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise PlantUnavailable(f"plant returned {e.code} for {path}")
    except urllib.error.URLError as e:
        raise PlantUnavailable(f"cannot reach plant at {PLANT_URL}: {e.reason}")


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
    return _get("/evidence/tickets").get("tickets", [])


def fetch_sources() -> dict:
    return _get("/evidence/sources").get("sources", {})


def plant_health() -> dict:
    return _get("/evidence/health")
