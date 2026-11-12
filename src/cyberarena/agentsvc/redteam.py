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

PLANT_URL = os.getenv("PLANT_URL", "http://localhost:8000").rstrip("/")
ATTACK_TOKEN = os.getenv("ATTACK_TOKEN", "arena-red-token")

ORDER = ["recon", "initial-access", "credential-access", "lateral-movement", "defense-evasion", "impact"]


def _req(path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(PLANT_URL + path, data=data, method="POST" if body is not None else "GET",
                                 headers={"content-type": "application/json", "x-attack-token": ATTACK_TOKEN})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def run_pentest() -> dict:
    from .plant_client import PlantUnavailable
    try:
        techniques = _req("/attack/techniques")["techniques"]
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
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
        "summary": _summary(breached, blocked),
    }


def _summary(breached, blocked):
    if not breached:
        return "The factory held: every exploit the Red agent tried was refused."
    flaws = ", ".join(sorted({a["flaw"] for a in breached}))
    worst = next((a for a in breached if a["tactic"] == "impact"), None)
    tail = f" It reached process impact: {worst['title'].lower()}." if worst else ""
    return f"The Red agent broke in through {len(breached)} open flaw(s) ({flaws}).{tail}"
