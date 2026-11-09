"""Run systems over generated cases. Cases are read back through the SAME adapters a real deployment uses."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .. import adapters
from ..core import engine, llm, site as sitemod, systems

KAVERI_SITE = Path(__file__).resolve().parent.parent / "range" / "kaveri" / "site.yaml"


def load_case(case_dir: Path, site):
    raws = adapters.load_events(case_dir / "events.jsonl")
    tickets = adapters.load_tickets(case_dir / "tickets.csv")
    events = engine.normalise(site, raws)
    return events, tickets


def run(cases_dir: str | Path, system_keys: list[str], seeds: list[int], llm_seeds: list[int] | None = None, progress=print) -> list[dict]:
    cases_dir = Path(cases_dir)
    llm.set_narration(False)      # agents are scored on the evidence model only; narration would add LLM calls but cannot change a verdict
    site = sitemod.load(KAVERI_SITE)
    rows = []
    for sd in seeds:
        for case_dir in sorted((cases_dir / f"seed-{sd}").iterdir()):
            if not (case_dir / "truth.json").exists():
                continue
            truth = json.loads((case_dir / "truth.json").read_text(encoding="utf8"))        # read only here, after the systems have run
            events, tickets = load_case(case_dir, site)
            alert = engine.build_alert(events)
            row = dict(seed=sd, family=truth["family"], name=truth["name"], attack=truth["attack"], hard=truth["hard"], events=len(events),
                       alert=alert["text"], alert_triggered=alert["triggered"], results={})
            for sk in system_keys:
                s = systems.SYSTEMS[sk]
                if s["llm"] and llm_seeds is not None and sd not in llm_seeds:
                    continue
                if s["llm"] and not systems.available(sk):
                    continue
                try:
                    row["results"][sk] = s["fn"](site, tickets, events, alert)
                except Exception as exc:       # an LLM reply that cannot be parsed counts as "no valid answer"
                    row["results"][sk] = dict(error=f"{type(exc).__name__}: {exc}"[:200], incident=False, tool_calls=0, seconds=0.0, tokens=0, llm_calls=0)
            rows.append(row)
        progress(f"seed {sd}: {len([r for r in rows if r['seed'] == sd])} cases done")
    return rows
