"""cyberarena command line.

    cyberarena triage --events logs.csv --site site.yaml [--tickets tickets.xlsx] [--out report.md]
    cyberarena range  generate --seed 1 --out cases/        (needs the 'range' extra)
    cyberarena bench  --out results/                        (needs the 'bench' and 'range' extras)
    cyberarena version
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_triage(a):
    from . import adapters
    from .core import engine, report, site as sitemod
    from .core.tickets import TicketStore

    site = sitemod.load(a.site)
    raws = adapters.load_events(a.events, a.format, a.mapping)
    tickets = adapters.load_tickets(a.tickets) if a.tickets else TicketStore()
    events = engine.normalise(site, raws)
    print(f"read {len(raws)} records -> {len(events)} events, {len(tickets.tickets)} tickets", file=sys.stderr)
    wins = engine.alert_windows(events, gap_s=a.gap)
    if not wins:
        print("No alert: no event matched a detection rule. Nothing to triage.")
        return 0
    out_dir = Path(a.out) if a.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    for i, w in enumerate(wins, 1):
        run = engine.investigate_case(site, tickets, w["events"], critic=not a.no_critic, alert=w["alert"], run_id=f"{i:03d}")
        r = run.report
        print(f"[alert {i}/{len(wins)}] {r['classification']}  confidence {r['confidence']:.2f}  evidence {len(r['evidence'])}  "
              f"tool calls {r['tool_calls']}  - {w['alert']['text'][:90]}")
        if out_dir:
            (out_dir / f"alert-{i:03d}.md").write_text(report.to_markdown(run), encoding="utf8")
            (out_dir / f"alert-{i:03d}.json").write_text(json.dumps(dict(report=r, audit=run.gw.audit), default=str, indent=1), encoding="utf8")
    if out_dir:
        print(f"reports written to {out_dir}/  (a human must approve each one; nothing was changed in the plant)", file=sys.stderr)
    return 0


def cmd_range(a):
    from .range import cli as rcli
    return rcli.main(a)


def cmd_bench(a):
    from .bench import cli as bcli
    return bcli.main(a)


def main(argv=None):
    p = argparse.ArgumentParser(prog="cyberarena", description="Read-only alert triage for industrial networks.")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("triage", help="triage the alerts found in a log file")
    t.add_argument("--events", required=True, help="CSV / JSON / JSONL / syslog file")
    t.add_argument("--site", required=True, help="site config YAML (assets, roles, accounts, limits)")
    t.add_argument("--tickets", help="tickets CSV or XLSX")
    t.add_argument("--mapping", help="adapter mapping YAML (column names, event_type_map, syslog_rules)")
    t.add_argument("--format", choices=["csv", "json", "jsonl", "syslog"])
    t.add_argument("--no-critic", action="store_true", help="skip the Critic (System C)")
    t.add_argument("--gap", type=int, default=300, help="seconds of quiet that separate two alerts (default 300)")
    t.add_argument("--out", help="directory for Markdown + JSON reports")
    t.set_defaults(fn=cmd_triage)

    r = sub.add_parser("range", help="the simulated Kaveri range (separate from the engine)")
    r.add_argument("action", choices=["generate", "serve", "list"])
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--out", default="cases")
    r.add_argument("--scenarios", nargs="*")
    r.add_argument("--preset", default="all_vulnerable")
    r.add_argument("--host", default="127.0.0.1", help="bind address for `range serve` (use 0.0.0.0 inside Docker)")
    r.set_defaults(fn=cmd_range)

    b = sub.add_parser("bench", help="run the benchmark and regenerate every table and figure")
    b.add_argument("--out", default="results")
    b.add_argument("--seeds", type=int, nargs="*", default=[1, 2, 3, 4, 5])
    b.add_argument("--systems", nargs="*", default=["A", "C", "D"], help="A B C D E (B and E need an LLM)")
    b.add_argument("--cases", help="use previously generated cases instead of regenerating them")
    b.add_argument("--llm-seeds", type=int, nargs="*", help="restrict LLM systems (B, E) to these seeds (they are slow)")
    b.add_argument("--hai", help="folder with the extracted HAI file for the process-anomaly experiment")
    b.set_defaults(fn=cmd_bench)

    v = sub.add_parser("version")
    v.set_defaults(fn=lambda a: print("cyberarena 0.1.0") or 0)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
