"""Turn benchmark rows into tables, figures, failure analysis and a reproducibility log."""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys
from datetime import datetime
from pathlib import Path

from ..core import llm, systems
from . import stats
from .stats import ci_text, pct

ORDER = ["A", "B", "E", "C", "D", "D-maint", "D-auth", "D-scope"]


def _sys_keys(rows):
    present = {k for r in rows for k in r["results"]}
    return [k for k in ORDER if k in present]


def _valid(rows, sk):
    return [r for r in rows if sk in r["results"]]


def metrics_for(rows, sk, hard=None):
    rs = [r for r in _valid(rows, sk) if hard is None or r["hard"] == hard]
    m = stats.metrics((r["attack"], r["results"][sk]["incident"]) for r in rs)
    m["errors"] = sum(1 for r in rs if "error" in r["results"][sk])
    m["tool_calls"] = sum(r["results"][sk].get("tool_calls", 0) for r in rs) / max(1, len(rs))
    m["seconds"] = sum(r["results"][sk].get("seconds", 0) for r in rs) / max(1, len(rs))
    m["tokens"] = sum(r["results"][sk].get("tokens", 0) for r in rs) / max(1, len(rs))
    m["llm_calls"] = sum(r["results"][sk].get("llm_calls", 0) for r in rs) / max(1, len(rs))
    return m


def correct(r, sk):
    return r["results"][sk]["incident"] == r["attack"]


def main_table(rows, keys, hard=None):
    L = ["| System | n | Accuracy (95% CI) | Recall (95% CI) | False-alarm rate (95% CI) | Precision | F1 | Unparsed |", "|---|---|---|---|---|---|---|---|"]
    for k in keys:
        m = metrics_for(rows, k, hard)
        if m["n"] == 0:
            continue
        L.append(f"| {k} {systems.SYSTEMS[k]['name']} | {m['n']} | {ci_text(m['accuracy'], m['accuracy_ci'])} | {ci_text(m['recall'], m['recall_ci'])} | "
                 f"{ci_text(m['fpr'], m['fpr_ci'])} | {pct(m['precision'])} | {'-' if m['f1'] is None else format(m['f1'], '.2f')} | {m['errors']} |")
    return "\n".join(L)


def per_seed_table(rows, keys):
    seeds = sorted({r["seed"] for r in rows})
    L = ["| System | " + " | ".join(f"seed {s}" for s in seeds) + " | mean | bootstrap 95% CI of mean |", "|---|" + "---|" * (len(seeds) + 2)]
    for k in keys:
        accs = []
        cells = []
        for s in seeds:
            rs = [r for r in rows if r["seed"] == s and k in r["results"]]
            if not rs:
                cells.append("-")
                continue
            a = sum(correct(r, k) for r in rs) / len(rs)
            accs.append(a)
            cells.append(pct(a))
        if accs:
            ci = stats.bootstrap_ci(accs)
            L.append(f"| {k} | " + " | ".join(cells) + f" | {pct(sum(accs) / len(accs), 1)} | {pct(ci[0])}-{pct(ci[1])} |")
    return "\n".join(L)


def pairwise(rows, keys, pairs):
    """McNemar exact on pooled cases and on family-level majority outcomes, Holm-adjusted across the listed pairs."""
    out, praw_pool, praw_fam = [], {}, {}
    for a, b in pairs:
        if a not in keys or b not in keys:
            continue
        shared = [r for r in rows if a in r["results"] and b in r["results"]]
        if not shared:
            continue
        pool = stats.mcnemar_exact([correct(r, a) for r in shared], [correct(r, b) for r in shared])
        fams = {}
        for r in shared:
            fams.setdefault(r["family"], []).append(r)
        fa = [sum(correct(r, a) for r in v) * 2 > len(v) for v in fams.values()]
        fb = [sum(correct(r, b) for r in v) * 2 > len(v) for v in fams.values()]
        fam = stats.mcnemar_exact(fa, fb)
        out.append((a, b, len(shared), pool, len(fams), fam))
        praw_pool[f"{a}-{b}"], praw_fam[f"{a}-{b}"] = pool["p"], fam["p"]
    hp, hf = stats.holm(praw_pool), stats.holm(praw_fam)
    L = ["| Comparison (A vs B) | paired cases | A right / B wrong | A wrong / B right | p (exact McNemar) | p (Holm) | families | A right / B wrong | A wrong / B right | p (family level) | p (Holm) |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for a, b, n, pool, nf, fam in out:
        key = f"{a}-{b}"
        L.append(f"| {a} vs {b} | {n} | {pool['a_only']} | {pool['b_only']} | {pool['p']:.4f} | {hp[key]:.4f} | {nf} | {fam['a_only']} | {fam['b_only']} | {fam['p']:.4f} | {hf[key]:.4f} |")
    return "\n".join(L)


def cost_table(rows, keys):
    L = ["| System | tool calls / alert | seconds / alert (CPU) | LLM calls / alert | LLM tokens / alert |", "|---|---|---|---|---|"]
    for k in keys:
        m = metrics_for(rows, k)
        if m["n"]:
            L.append(f"| {k} | {m['tool_calls']:.1f} | {m['seconds']:.3f} | {m['llm_calls']:.1f} | {m['tokens']:.0f} |")
    return "\n".join(L)


def family_table(rows, keys):
    fams = sorted({r["family"] for r in rows})
    L = ["| Family | Truth | Hard | Name | " + " | ".join(keys) + " |", "|---|---|---|---|" + "---|" * len(keys)]
    for f in fams:
        rs = [r for r in rows if r["family"] == f]
        cells = []
        for k in keys:
            v = [r for r in rs if k in r["results"]]
            cells.append(f"{sum(correct(r, k) for r in v)}/{len(v)}" if v else "-")
        L.append(f"| {f} | {'attack' if rs[0]['attack'] else 'benign'} | {'yes' if rs[0]['hard'] else ''} | {rs[0]['name']} | " + " | ".join(cells) + " |")
    return "\n".join(L)


def failures(rows, keys, focus=("A", "C", "D", "B", "E")):
    L = ["# Where each system fails", "", "Every misclassified case, by system. 'FN' = missed attack, 'FP' = false alarm.", ""]
    for k in focus:
        if k not in keys:
            continue
        bad = [r for r in rows if k in r["results"] and not correct(r, k)]
        L += [f"## {k} {systems.SYSTEMS[k]['name']}: {len(bad)} of {len([r for r in rows if k in r['results']])} cases wrong", ""]
        by = {}
        for r in bad:
            by.setdefault(r["family"], []).append(r)
        for f, rs in sorted(by.items()):
            r0 = rs[0]
            res = r0["results"][k]
            conf = res.get("confidence")
            ev = ", ".join(f"{e['code']}({e['weight']:+.1f})" for e in (res.get("evidence") or [])[:8])
            L.append(f"- **{f} {r0['name']}** ({'FN' if r0['attack'] else 'FP'}, seeds {', '.join(str(r['seed']) for r in rs)}; {len(rs)} wrong)"
                     + (f" - confidence {conf:.2f}" if conf is not None else "") + (f" - evidence: {ev}" if ev else "")
                     + (f" - {res['error']}" if "error" in res else ""))
        if not bad:
            L.append("- none")
        L.append("")
    return "\n".join(L)


def figures(rows, keys, out: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    main = [k for k in keys if k in ("A", "B", "E", "C", "D")]
    colors = {"A": "#8a8a8a", "B": "#c9a227", "E": "#e0802d", "C": "#4a78b5", "D": "#1f7a5c"}
    # 1. metrics with Wilson CIs
    fig, ax = plt.subplots(figsize=(8, 4))
    names = [("accuracy", "Accuracy"), ("recall", "Recall"), ("fpr", "False-alarm rate")]
    w = 0.8 / max(1, len(main))
    for i, k in enumerate(main):
        m = metrics_for(rows, k)
        xs, ys, lo, hi = [], [], [], []
        for j, (mk, _) in enumerate(names):
            v, ci = m[mk], m[mk + "_ci"]
            xs.append(j + i * w - 0.4 + w / 2)
            ys.append(100 * v)
            lo.append(100 * (v - ci[0]))
            hi.append(100 * (ci[1] - v))
        ax.bar(xs, ys, w * 0.92, yerr=[lo, hi], capsize=2, color=colors.get(k), label=f"{k} {systems.SYSTEMS[k]['name']}")
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([n for _, n in names])
    ax.set_ylabel("%  (95% Wilson CI)")
    ax.set_ylim(0, 105)
    ax.legend(fontsize=7, loc="upper center", ncol=2, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "fig_metrics.png", dpi=170)
    plt.close(fig)
    # 2. per-family heat map
    fams = sorted({r["family"] for r in rows})
    ks = [k for k in keys if k in ("A", "B", "E", "C", "D")]
    grid = []
    for f in fams:
        row = []
        for k in ks:
            v = [r for r in rows if r["family"] == f and k in r["results"]]
            row.append(sum(correct(r, k) for r in v) / len(v) if v else float("nan"))
        grid.append(row)
    fig, ax = plt.subplots(figsize=(1.2 + 0.9 * len(ks), 0.28 * len(fams) + 1.2))
    im = ax.imshow(grid, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(len(ks)))
    ax.set_xticklabels(ks)
    ax.set_yticks(range(len(fams)))
    ax.set_yticklabels([f"{f} {next(r['name'] for r in rows if r['family'] == f)[:30]}" for f in fams], fontsize=6)
    ax.set_title("Fraction of seeds classified correctly", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.04)
    fig.tight_layout()
    fig.savefig(out / "fig_family_heatmap.png", dpi=170)
    plt.close(fig)
    # 3. ablation
    ab = [k for k in ("C", "D-maint", "D-auth", "D-scope", "D") if k in keys]
    if len(ab) >= 2:
        fig, ax = plt.subplots(figsize=(7, 3.6))
        for i, (mk, label) in enumerate([("accuracy", "Accuracy"), ("recall", "Recall"), ("fpr", "False-alarm rate")]):
            ys = [100 * metrics_for(rows, k)[mk] for k in ab]
            ax.bar([j + i * 0.27 - 0.27 for j in range(len(ab))], ys, 0.25, label=label)
        ax.set_xticks(range(len(ab)))
        ax.set_xticklabels(["C\n(no Critic)", "D − maint.", "D − auth.", "D − scope", "D\n(full)"][-len(ab):] if len(ab) == 5 else ab, fontsize=8)
        ax.set_ylabel("%")
        ax.legend(frameon=False, fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(out / "fig_ablation.png", dpi=170)
        plt.close(fig)
    # 4. confidence distribution of D
    if "D" in keys:
        fig, ax = plt.subplots(figsize=(6, 3))
        for truth, col, lab in ((True, "#b3402a", "attack"), (False, "#1f7a5c", "benign")):
            ax.hist([r["results"]["D"]["confidence"] for r in rows if "D" in r["results"] and r["attack"] == truth and r["results"]["D"].get("confidence") is not None],
                    bins=[i / 10 for i in range(11)], alpha=0.7, color=col, label=lab)
        ax.axvline(0.6, ls="--", c="k", lw=0.8)
        ax.set_xlabel("System D confidence of incident (threshold 0.6)")
        ax.set_ylabel("cases")
        ax.legend(frameon=False)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(out / "fig_confidence.png", dpi=170)
        plt.close(fig)


def run_info(cmd, seeds, system_keys, out: Path, extra=None):
    import importlib.metadata as md
    root = Path(__file__).resolve().parent.parent
    files = ["range/families.py", "core/evidence.py", "core/investigate.py", "core/gateway.py", "core/normalise.py", "core/systems.py"]
    pk = {}
    for p in ("pyyaml", "matplotlib", "openpyxl", "fastapi", "sqlalchemy", "uvicorn"):
        try:
            pk[p] = md.version(p)
        except Exception:
            pass
    info = dict(when=datetime.now().astimezone().isoformat(timespec="seconds"), command=cmd, python=sys.version.split()[0], platform=platform.platform(),
                packages=pk, cyberarena="0.1.0", seeds=seeds, systems=system_keys,
                llm=dict(mode=llm.mode(), model=(__import__("os").environ.get("OLLAMA_MODEL") or __import__("os").environ.get("GROQ_MODEL") or __import__("os").environ.get("LLM_MODEL") or None)),
                file_sha256={f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in files}, **(extra or {}))
    (out / "run_info.json").write_text(json.dumps(info, indent=1), encoding="utf8")
    return info


def write_all(rows, out: Path, cmd, seeds, system_keys, extra=None):
    out.mkdir(parents=True, exist_ok=True)
    keys = _sys_keys(rows)
    (out / "cases.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf8")
    with open(out / "cases.csv", "w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(["seed", "family", "name", "truth_attack", "hard", "events", "system", "predicted_incident", "correct", "confidence", "tool_calls", "seconds", "tokens", "error"])
        for r in rows:
            for k, v in r["results"].items():
                w.writerow([r["seed"], r["family"], r["name"], r["attack"], r["hard"], r["events"], k, v["incident"], correct(r, k), v.get("confidence"),
                            v.get("tool_calls"), round(v.get("seconds", 0), 4), v.get("tokens"), v.get("error", "")])
    n_att = len({r["family"] for r in rows if r["attack"]})
    n_ben = len({r["family"] for r in rows if not r["attack"]})
    base = [k for k in keys if k in ("A", "B", "E", "C", "D")]
    md = [f"# Benchmark results", "", f"{len(rows)} cases = {n_att} attack and {n_ben} benign scenario families x {len(seeds)} seeds ({', '.join(map(str, seeds))}). "
          "Positive class = attack. Cases come from the simulated Kaveri range, not from a real plant.", "",
          "## Main table (all cases)", "", main_table(rows, base), "", "## Hard cases only", "",
          "(approved change that looks like an attack, ticket abuse, borrowed ticket, change beyond the approved value, expired ticket, wrong-asset ticket)", "",
          main_table(rows, base, hard=True), "", "## Easy cases only", "", main_table(rows, base, hard=False), "", "## Accuracy per seed", "", per_seed_table(rows, base), "",
          "## Ablation of the Critic", "", main_table(rows, [k for k in ("C", "D-maint", "D-auth", "D-scope", "D") if k in keys]), "",
          "## Significance (exact McNemar, Holm-adjusted)", "",
          "Pooled = every (family, seed) case is one pair; cases of the same family are correlated, so the family-level columns (majority outcome per family) are the conservative reading.", "",
          pairwise(rows, keys, [("D", "C"), ("D", "A"), ("C", "A"), ("D", "B"), ("D", "E"), ("E", "B"), ("E", "C"), ("D", "D-maint"), ("D", "D-auth"), ("D", "D-scope")]), "",
          "## Cost per alert", "", cost_table(rows, keys), "", "## Per family (correct / cases)", "", family_table(rows, base), ""]
    (out / "tables.md").write_text("\n".join(md), encoding="utf8")
    (out / "failures.md").write_text(failures(rows, keys), encoding="utf8")
    figures(rows, keys, out)
    return run_info(cmd, seeds, system_keys, out, extra)
