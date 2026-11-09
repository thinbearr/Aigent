"""Engine entry points: alerts from rules, one investigation, a whole file."""
from __future__ import annotations

import itertools
from datetime import timedelta

from . import investigate
from .normalise import Normaliser
from .schema import RawEvent, Ticket, parse_ts
from .site import Site
from .tickets import TicketStore

_ids = itertools.count(1)


def normalise(site: Site, raws: list[RawEvent]) -> list[dict]:
    return [e for e in Normaliser(site).run(raws) if not e["attrs"].get("noise")]


def build_alert(events: list[dict]) -> dict:
    hit = investigate.rule_based(events)
    e = hit or (events[0] if events else None)
    if e is None:
        return dict(t="", asset="", kind="other", text="No events", triggered=False)
    return dict(t=e["t"], asset=e["asset"], kind=e["kind"], text=e["detail"], triggered=bool(hit), event=e["id"])


def alert_windows(events: list[dict], gap_s: int = 300, lookback_s: int = 300, tail_s: int = 60) -> list[dict]:
    """Cluster rule hits in time; each cluster is one alert with the events around it as its evidence window."""
    hits = [e for e in events if investigate.rule_based([e])]
    clusters: list[list[dict]] = []
    for h in hits:
        if clusters and (parse_ts(h["t"]) - parse_ts(clusters[-1][-1]["t"])).total_seconds() <= gap_s:
            clusters[-1].append(h)
        else:
            clusters.append([h])
    out = []
    for c in clusters:
        t0, t1 = parse_ts(c[0]["t"]) - timedelta(seconds=lookback_s), parse_ts(c[-1]["t"]) + timedelta(seconds=tail_s)
        win = [e for e in events if t0 <= parse_ts(e["t"]) <= t1]
        out.append(dict(alert=build_alert(win), events=win, hits=len(c)))
    return out


def investigate_case(site: Site, tickets: TicketStore, events: list[dict], critic: bool = True, alert: dict | None = None,
                     delay: float = 0.0, run_id: str | None = None) -> investigate.Run:
    run = investigate.Run(run_id or f"{next(_ids):04d}", events, alert or build_alert(events), site, tickets, critic=critic, delay=delay)
    investigate.run_investigation(run)
    return run
