"""Turn evidence pulled from the plant into a finished investigation.

The agent knows its own site inventory (packaged site.yaml) and reads the plant's
evidence + change tickets over HTTP. It never sees the breach-point flags or any
ground truth. It runs the same engine as the CLI `triage`.
"""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from . import plant_client

# The analyst's own knowledge of their plant (asset inventory, roles, normal patterns).
SITE_YAML = Path(__file__).resolve().parents[1] / "range" / "kaveri" / "site.yaml"


def _write_inputs(tmp: Path, events: list[dict], tickets: list[dict]) -> int:
    with open(tmp / "events.jsonl", "w", encoding="utf8") as f:
        for e in events:
            f.write(json.dumps(dict(
                uid=f"EV-{e['id']}", ts=e["ts"], host=e["host"], source=e["source"],
                event_type=e["event_type"], actor=e.get("actor"), src_ip=e.get("src_ip"),
                dst_ip=e.get("dst_ip"), protocol=e.get("protocol"), outcome=e.get("outcome"),
                severity=e.get("severity"), detail=e.get("detail") or {},
            )) + "\n")
    cols = ["ticket", "asset", "assigned_to", "requested_by", "approved_by", "start", "end",
            "change_type", "status", "description", "approved_values"]
    with open(tmp / "tickets.csv", "w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for t in tickets:
            w.writerow([t.get(c, "") or "" for c in cols])
    return len(events)


def investigate(since_id: int = 0, critic: bool = True) -> dict:
    from cyberarena import adapters
    from cyberarena.core import engine, site as sitemod
    from cyberarena.core.tickets import TicketStore

    from . import flaw_finder

    events = plant_client.fetch_events(since_id)
    try:
        tickets_raw = plant_client.fetch_tickets()
    except Exception:
        tickets_raw = []
    flaws = flaw_finder.identify(events)

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        total = _write_inputs(tmp, events, tickets_raw)
        site = sitemod.load(str(SITE_YAML))
        raws = adapters.load_events(str(tmp / "events.jsonl"))
        tickets: TicketStore = adapters.load_tickets(str(tmp / "tickets.csv"))
        norm = engine.normalise(site, raws)
        windows = engine.alert_windows(norm)
        alerts = []
        for i, w in enumerate(windows, 1):
            run = engine.investigate_case(site, tickets, w["events"], critic=critic,
                                          alert=w["alert"], run_id=f"L{i:02d}")
            r = run.report
            alerts.append(dict(
                alert=w["alert"]["text"], asset=w["alert"]["asset"], t=w["alert"]["t"],
                classification=r["classification"], incident=r["incident"], confidence=r["confidence"],
                summary=r["summary"], tool_calls=r["tool_calls"], critic_enabled=r["critic_enabled"],
                affected_assets=r["affected_assets"], attack_path=r["attack_path"],
                evidence=[dict(id=e["id"], weight=e["weight"], kind=e["source"], text=e["text"], events=e["events"]) for e in r["evidence"]],
                alternatives=[dict(id=a["id"], label=a["name"], outcome=a["outcome"]) for a in r["alternatives"]],
                timeline=[dict(t=tl["t"], asset=tl["asset"], text=tl["text"], evidence=tl["evidence"]) for tl in r["timeline"]],
                mitre=[dict(id=m["id"], name=m["name"], evidence=m.get("evidence", [])) for m in r["mitre"]],
                impact=r["impact"], actions=r["actions"], checklist=r.get("checklist", []),
                steps=[dict(n=st["n"], agent=st["agent"], kind=st["kind"], text=st["text"], why=st.get("why")) for st in run.steps],
                audit=[dict(n=a["n"], agent=a["agent"], tool=a["tool"], status=a["status"], summary=a["summary"]) for a in run.gw.audit],
            ))
        return dict(evidence_examined=total, tickets_available=len(tickets_raw),
                    triggered=len(windows), flaws=flaws, alerts=alerts)
