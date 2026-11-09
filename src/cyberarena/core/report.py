"""Render a finished investigation as Markdown (for the human reviewer) or JSON."""
from __future__ import annotations


def to_markdown(run) -> str:
    r = run.report
    L = [f"# Triage report {r['incident_id']}", "",
         f"**Verdict:** {r['classification']}  ·  **confidence of incident:** {r['confidence']:.2f}  ·  **status:** {r['status']}", "",
         f"**Alert:** {run.alert['text']} (`{run.alert['asset']}` at {run.alert['t']})", "", "## Summary", r["summary"], "",
         "## Evidence (every conclusion cites these)", "", "| id | weight | kind | evidence | events |", "|---|---|---|---|---|"]
    for i in r["evidence"]:
        L.append(f"| {i['id']} | {i['weight']:+.1f} | {i['source']} | {i['text']} | {', '.join(i['events']) or '-'} |")
    if r["alternatives"]:
        L += ["", "## Alternatives the Critic tested", ""] + [f"- **{a['id']}** {a['name']}: {a['outcome']}" for a in r["alternatives"]]
    if r["timeline"]:
        L += ["", "## Timeline", ""] + [f"- {t['t']} `{t['asset']}` {t['text']}  _(evidence {', '.join(t['evidence'])})_" for t in r["timeline"]]
    if r["attack_path"]:
        L += ["", "## Path", "", " → ".join(r["attack_path"])]
    if r["mitre"]:
        L += ["", "## MITRE ATT&CK for ICS (indicative)", ""] + [f"- {m['id']} {m['name']} (evidence {', '.join(m['evidence'])})" for m in r["mitre"]]
    L += ["", "## Impact", r["impact"], "", "## Suggested actions (for a human to decide)"] + [f"- {a}" for a in r["actions"]]
    L += ["", "## Tool-call audit (all read-only)", "", "| # | agent | tool | status | result |", "|---|---|---|---|---|"]
    for a in run.gw.audit:
        L.append(f"| {a['n']} | {a['agent']} | {a['tool']} | {a['status']} | {a['summary']} |")
    L += ["", "_This assistant never changes anything in the plant. A human must approve or reopen this case._"]
    return "\n".join(L)
