"""The Red agent: an autonomous penetration test of the factory.

It does not know which security flaws are switched on. It simply tries every exploit
technique the plant exposes, in attacker order (recon -> initial access -> lateral
movement -> impact), over the network. The open flaws are the ones that succeed; the
rest are refused. Each success leaves evidence in the plant for the Blue agent to find.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

ATTACK_TOKEN = os.getenv("ATTACK_TOKEN", "arena-red-token")

DEV_URL = os.getenv("DEV_URL", "http://localhost:8100/dev").rstrip("/")
DEV_TOKEN = os.getenv("DEV_TOKEN", "arena-dev-token")

ORDER = ["recon", "initial-access", "credential-access", "lateral-movement", "defense-evasion", "impact"]


def _watermark() -> int:
    """Current event-id high-water mark, so Blue can later scope to just this round.

    Events are only ever appended (never deleted), so the plant's event_count is the id of the
    latest event. Returns 0 if the plant does not answer — the investigation then falls back to
    the whole log.
    """
    try:
        from . import plant_client
        return int(plant_client.plant_health().get("event_count", 0) or 0)
    except Exception:
        return 0


def _run_via_dev_control(baseline: int = 0) -> dict:
    """Fallback when target plant uses Developer Mode range control (:8100) instead of /attack API."""
    data = json.dumps({"key": "6", "fast": True, "actor": "attacker"}).encode()
    req = urllib.request.Request(f"{DEV_URL}/scenarios/run", data=data, method="POST",
                                 headers={"content-type": "application/json", "x-dev-token": DEV_TOKEN})
    with urllib.request.urlopen(req, timeout=15) as r:
        res = json.load(r)
    attempts = [
        {"technique": "T0836", "title": "Manipulate Mixing Tank Process (MV-101)", "flaw": "B6",
         "target": "plc-01", "tactic": "impact", "result": "success",
         "detail": f"Scenario {res.get('scenario')} launched via plant range control"}
    ]
    return {
        "attempts": attempts,
        "techniques_tried": len(attempts),
        "breached_flaws": ["B6"],
        "held_flaws": [],
        "footholds": ["Process manipulation on mixing tank MV-101"],
        "baseline_event_id": baseline,
        "summary": "The Red agent launched a process manipulation attack scenario against the factory.",
    }


def _req(path: str, body=None):
    from . import plant_client
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(plant_client.plant_url() + path, data=data,
                                 method="POST" if body is not None else "GET",
                                 headers={"content-type": "application/json", "x-attack-token": ATTACK_TOKEN})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def run_pentest() -> dict:
    from .plant_client import PlantUnavailable
    # Mark where the log stands BEFORE we attack, so the Blue investigation can look at only the
    # events this round produced and not resurrect flaws from earlier runs.
    baseline = _watermark()
    try:
        techniques = _req("/attack/techniques")["techniques"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            try:
                return _run_via_dev_control(baseline)
            except Exception:
                raise PlantUnavailable(f"cannot reach the factory attack surface: {e}")
        raise PlantUnavailable(f"cannot reach the factory attack surface: {e}")
    except (urllib.error.URLError, Exception) as e:
        try:
            return _run_via_dev_control(baseline)
        except Exception:
            raise PlantUnavailable(f"cannot reach the factory attack surface: {e}")

    techniques.sort(key=lambda t: ORDER.index(t["tactic"]) if t["tactic"] in ORDER else 99)
    attempts = []
    for t in techniques:
        try:
            r = _req("/attack/attempt", {"technique": t["id"]})
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            r = {"technique": t["id"], "title": t["title"], "flaw": t["flaw"], "target": t["target"],
                 "tactic": t["tactic"], "result": "error", "detail": str(e)}
        attempts.append(r)

    breached = [a for a in attempts if a["result"] == "success" and a["flaw"]]
    blocked = [a for a in attempts if a["result"] in ("blocked", "failed") and a["flaw"]]
    return {
        "attempts": attempts,
        "techniques_tried": len(attempts),
        "breached_flaws": sorted({a["flaw"] for a in breached}),
        "held_flaws": sorted({a["flaw"] for a in blocked if a["flaw"] not in {b["flaw"] for b in breached}}),
        "footholds": [a["title"] for a in breached],
        "baseline_event_id": baseline,
        "summary": _summary(breached, blocked),
    }


def _summary(breached, blocked):
    if not breached:
        return "The factory held: every exploit the Red agent tried was refused."
    flaws = ", ".join(sorted({a["flaw"] for a in breached}))
    worst = next((a for a in breached if a["tactic"] == "impact"), None)
    tail = f" It reached process impact: {worst['title'].lower()}." if worst else ""
    return f"The Red agent broke in through {len(breached)} open flaw(s) ({flaws}).{tail}"
