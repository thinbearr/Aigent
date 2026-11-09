"""The systems under comparison. Each takes (site, tickets, events, alert) and returns a verdict dict.

A  rule-based detector                     no reasoning, no checks
B  single LLM, events only                 one prompt, one answer            (needs an LLM)
E  single LLM + the same records           B plus the tickets/accounts the agents can query (needs an LLM)
C  agents without the Critic               Blue's first verdict is final
D  agents with the Critic                  Critic challenges via ticket / authorisation / scope checks

The verdict of C and D comes from the weighted evidence model, never from free text. An LLM only narrates there.
"""
from __future__ import annotations

import re
import time

from . import investigate, llm

PROMPT = """You are a security analyst for an industrial plant. A detection tool raised this alert:

ALERT [{t}] on {asset}: {text}

These are all the log events available:
{events}
{context}
Decide whether this is a real security incident (malicious activity) or benign activity.
Reply with ONLY a JSON object: {{"incident": true or false, "probability_malicious": a number from 0 to 1, "reason": "one sentence"}}"""


def _timed(fn):
    def wrap(site, tickets, events, alert):
        u0, t0 = llm.usage(), time.perf_counter()
        v = fn(site, tickets, events, alert)
        u1 = llm.usage()
        v["seconds"] = time.perf_counter() - t0
        v["llm_calls"] = u1["calls"] - u0["calls"]
        v["tokens"] = (u1["prompt_tokens"] - u0["prompt_tokens"]) + (u1["completion_tokens"] - u0["completion_tokens"])
        return v
    return wrap


@_timed
def system_A(site, tickets, events, alert):
    return dict(incident=investigate.rule_based(events) is not None, confidence=None, tool_calls=0)


def _agents(site, tickets, events, alert, critic, disable=()):
    run = investigate.Run("bench", events, alert, site, tickets, critic=critic, delay=0, disable=disable)
    investigate.run_investigation(run)
    prelim = next((s["data"]["prelim"] for s in run.steps if s["data"].get("prelim") is not None), None)
    return dict(incident=bool(run.verdict), confidence=run.report["confidence"], tool_calls=run.tool_calls, prelim=prelim,
                overturned=any(s["data"].get("overturned") for s in run.steps if s["kind"] == "challenge"),
                mitre=[m["id"] for m in run.report["mitre"]], evidence=[dict(code=i["code"], weight=i["weight"]) for i in run.book.items])


@_timed
def system_C(site, tickets, events, alert):
    return _agents(site, tickets, events, alert, False)


@_timed
def system_D(site, tickets, events, alert):
    return _agents(site, tickets, events, alert, True)


def _ablate(check):
    @_timed
    def fn(site, tickets, events, alert):
        return _agents(site, tickets, events, alert, True, disable=(check,))
    return fn


def parse_llm(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in the model reply")
    inc = re.search(r'"incident"\s*:\s*"?(true|false)"?', m.group(0), re.I)
    if not inc:
        raise ValueError("no 'incident' in the model reply")
    prob = re.search(r'"(?:probability_malicious|confidence)"\s*:\s*([0-9.]+)', m.group(0))
    return dict(incident=inc.group(1).lower() == "true", confidence=float(prob.group(1)) if prob else None, tool_calls=1)


def context_text(site, tickets):
    lines = [f"- Change ticket {t.id} on {t.asset} ({t.change_type}), status {t.status}, assigned to {t.assigned_to}, "
             f"window {t.start:%Y-%m-%d %H:%M}-{t.end:%H:%M}, approved values {t.approved or 'not stated'}: {t.description}"
             for t in tickets.tickets] or ["- No change tickets."]
    lines += [f"- Account {u}: role {a.get('role')}, authorised for {', '.join(sorted(site.roles.get(a.get('role', ''), []))) or 'nothing'}"
              + (" (outside contractor: authorised only while holding a ticket)" if a.get("role") in site.ticket_roles else "")
              for u, a in site.accounts.items()]
    return "\nReference records an investigator could look up:\n" + "\n".join(lines) + "\n"


def _llm_system(site, tickets, events, alert, with_context):
    txt = "\n".join(f"- {e['t']} {e['kind']} on {e['asset']}: {e['detail']}" for e in events)
    prompt = PROMPT.format(t=alert["t"], asset=alert["asset"], text=alert["text"], events=txt,
                           context=context_text(site, tickets) if with_context else "")
    reply = llm.complete(prompt, system="You are a careful ICS security analyst. Follow the output format exactly.", max_tokens=400)
    return parse_llm(reply)


@_timed
def system_B(site, tickets, events, alert):
    return _llm_system(site, tickets, events, alert, False)


@_timed
def system_E(site, tickets, events, alert):
    return _llm_system(site, tickets, events, alert, True)


SYSTEMS = {
    "A": dict(name="Rule-based detector", fn=system_A, llm=False),
    "B": dict(name="Single LLM (events only)", fn=system_B, llm=True),
    "E": dict(name="Single LLM + same records", fn=system_E, llm=True),
    "C": dict(name="Agents without Critic", fn=system_C, llm=False),
    "D": dict(name="Agents with Critic", fn=system_D, llm=False),
    # ablations of the Critic: D with one check switched off
    "D-maint": dict(name="D without maintenance-window check", fn=_ablate("maintenance"), llm=False),
    "D-auth": dict(name="D without authorisation check", fn=_ablate("authorization"), llm=False),
    "D-scope": dict(name="D without change-scope check", fn=_ablate("scope"), llm=False),
}


def available(key):
    return (not SYSTEMS[key]["llm"]) or llm.mode() != "off"
