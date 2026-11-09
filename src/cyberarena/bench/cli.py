"""`cyberarena bench`: regenerate cases from fixed seeds, run every system, write every table and figure."""
from __future__ import annotations

import shlex
import sys
import time
from pathlib import Path

ABLATIONS = ["D-maint", "D-auth", "D-scope"]


def main(a):
    from ..range import generate
    from . import report, runner

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cases = Path(a.cases) if a.cases else out / "cases"
    systems = list(a.systems) + [k for k in ABLATIONS if "D" in a.systems and k not in a.systems]
    t0 = time.time()
    if not a.cases:
        print(f"generating cases for seeds {a.seeds} (fixed seeds, range reset for every case)...")
        generate.generate(cases, seeds=a.seeds, progress=lambda m: None)
    print("running systems", systems)
    rows = runner.run(cases, systems, a.seeds, llm_seeds=a.llm_seeds)
    extra = dict(range_families_sha256=generate.families_hash(), wall_seconds=round(time.time() - t0, 1))
    info = report.write_all(rows, out, "cyberarena bench " + " ".join(shlex.quote(x) for x in sys.argv[2:]), a.seeds, systems, extra)
    if a.hai:
        from . import hai
        p = Path(a.hai)
        p = next(p.glob("*.csv.gz")) if p.is_dir() else p
        r = hai.evaluate(p)
        (out / "hai.md").write_text(hai.to_markdown(r), encoding="utf8")
        import json
        (out / "hai.json").write_text(json.dumps(r, indent=1), encoding="utf8")
        print("HAI experiment written to", out / "hai.md")
    print(f"done in {time.time() - t0:.0f}s: {len(rows)} cases. See {out}/tables.md, failures.md, figures and run_info.json")
    return 0
