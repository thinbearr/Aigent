"""Runs every scripted scenario under three systems and tabulates the outcome.

A = rule-based detector, C = multi-agent without Critic, D = full system (with Critic).
These are 5 scripted scenarios used to demonstrate the mechanism. They are not evidence of real-world performance.
"""
from . import sim
from .investigate import Run, rule_based, run_investigation


def _run(scn, critic):
    r = Run("eval", scn, critic=critic, delay=0)
    run_investigation(r)
    return r


def evaluate():
    rows = []
    for sid, scn in sim.SCENARIOS.items():
        truth = scn["truth"]["incident"]
        a = rule_based(scn)["flag"]
        rc, rd = _run(scn, False), _run(scn, True)
        rows.append(dict(
            id=sid, name=scn["name"], truth=truth, truth_text=scn["truth"]["summary"],
            A=dict(flag=a, ok=a == truth),
            C=dict(flag=rc.verdict, conf=rc.report["confidence"], ok=rc.verdict == truth, calls=rc.tool_calls),
            D=dict(flag=rd.verdict, conf=rd.report["confidence"], ok=rd.verdict == truth, calls=rd.tool_calls)))
    attacks = [r for r in rows if r["truth"]]
    benign = [r for r in rows if not r["truth"]]

    def metrics(s):
        det = sum(1 for r in attacks if r[s]["flag"])
        fp = sum(1 for r in benign if r[s]["flag"])
        acc = sum(1 for r in rows if r[s]["ok"])
        return dict(detection=f"{det}/{len(attacks)}", false_positives=f"{fp}/{len(benign)}", accuracy=f"{acc}/{len(rows)}")

    return dict(rows=rows, summary={s: metrics(s) for s in ("A", "C", "D")})
