"""Generate benchmark cases from the range.

For every (family, seed) the range is reset, background activity is seeded, the family runs, and the evidence is
exported as plain files in the formats real adapters read:

    cases/seed-1/A08/events.jsonl     canonical records (what the plant logged)
    cases/seed-1/A08/tickets.csv      the work orders that existed
    cases/seed-1/A08/truth.json       ground truth: NEVER read by the engine, only by the scorer
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import time
from pathlib import Path


def _setup_env(db_path: str):
    os.environ["CYBERARENA_RANGE_DB"] = db_path
    os.environ.setdefault("NOISE_MIN", "99999")
    os.environ.setdefault("NOISE_MAX", "99999")


def families_hash() -> str:
    p = Path(__file__).with_name("families.py")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def export_case(out: Path, fam, seed: int, flags_used: dict):
    from .kaveri.db import session_scope
    from .kaveri.models import Event, WorkOrder
    out.mkdir(parents=True, exist_ok=True)
    with session_scope() as s:
        events = s.query(Event).order_by(Event.id).all()
        wos = s.query(WorkOrder).order_by(WorkOrder.id).all()
        with open(out / "events.jsonl", "w", encoding="utf8") as f:
            for e in events:
                ts = e.ts if e.ts.tzinfo else e.ts.replace(tzinfo=__import__("datetime").timezone.utc)
                f.write(json.dumps(dict(uid=f"EV-{e.id}", ts=ts.isoformat(), host=e.host, source=e.source, event_type=e.event_type, actor=e.actor,
                                        src_ip=e.src_ip, dst_ip=e.dst_ip, protocol=e.protocol, outcome=e.outcome, severity=e.severity,
                                        detail=e.detail or {}), default=str) + "\n")
        with open(out / "tickets.csv", "w", newline="", encoding="utf8") as f:
            w = csv.writer(f)
            w.writerow(["ticket", "asset", "assigned_to", "requested_by", "approved_by", "start", "end", "change_type", "status", "description", "approved_values"])
            for t in wos:
                pc = t.planned_change or {}
                key = pc.get("tag") or pc.get("parameter")
                approved = f"{key}={pc['to']}" if key and isinstance(pc.get("to"), (int, float)) else ""
                ws, we = [(x if x.tzinfo else x.replace(tzinfo=__import__("datetime").timezone.utc)).isoformat() for x in (t.window_start, t.window_end)] \
                    if t.window_start else ("", "")
                if ws:
                    w.writerow([t.number, t.asset, t.assigned_to, t.requested_by, t.approved_by, ws, we, t.change_type, t.status, t.description, approved])
    (out / "truth.json").write_text(json.dumps(dict(family=fam.key, name=fam.name, attack=fam.attack, hard=fam.hard, description=fam.description,
                                                    techniques=list(fam.techniques), seed=seed, flags=flags_used, events=len(events)), indent=1), encoding="utf8")
    return len(events)


def generate(out_dir: str | Path, seeds=(1,), keys=None, preset="all_vulnerable", db_path: str | None = None, progress=print):
    out_dir = Path(out_dir)
    _setup_env(db_path or str(out_dir / "_range.db"))
    out_dir.mkdir(parents=True, exist_ok=True)
    from .kaveri import flags, runtime, seed as seedmod
    from .kaveri.plant.sim import plant
    from . import families

    seedmod.init_database()
    runtime.PAUSE_NOISE.set()
    base = flags.PRESETS[preset]["flags"]
    total = 0
    for sd in seeds:
        for key, fam in families.REGISTRY.items():
            if keys and key not in keys:
                continue
            rng = random.Random(f"{sd}:{key}")
            random.seed(f"{sd}:{key}:bg")            # background activity helpers use the global RNG
            seedmod.reset_database()
            cb = plant.on_bottles
            plant.reset()
            plant.on_bottles = cb
            used = {**base, **(fam.flags or {})}
            flags.set_modes(used)
            runtime.organic_burst(rng.randint(3, 7))
            time.sleep(0.02)
            fam.run(rng)
            runtime.organic_burst(rng.randint(1, 4))
            time.sleep(0.12)                          # let asynchronous plant effects land
            n = export_case(out_dir / f"seed-{sd}" / key, fam, sd, used)
            total += 1
            progress(f"seed {sd} {key} {fam.name}: {n} events")
    return total
