"""Optional: turn a finished Red+Blue round into a detailed, readable incident report with GPT.

This is a *narration* layer only. Every fact it is given has already been decided by the
deterministic engine (what Red breached, what Blue concluded, the evidence, the timeline). GPT
is asked to write it up clearly for a mixed audience — it is never the thing that decides the
verdict, and it is never given any ground truth the agent itself did not derive.

The OpenAI key is read from the environment (OPENAI_API_KEY) and is never logged or returned.
Set OPENAI_MODEL to change the model (default: gpt-4o-mini). No third-party SDK is required.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM = (
    "You are the incident report writer for CyberArena, an autonomous ICS/OT security range. "
    "You write a clear, well-structured incident report in Markdown for a MIXED audience: a plant "
    "manager with no security background should understand it, while a SOC analyst should still find "
    "it precise. Explain every technical term in plain words the first time it appears. Be factual and "
    "concise; never invent evidence, flaws, timestamps or assets that are not in the data provided. If "
    "the data says no incident, say so plainly and do not manufacture alarm. Do not reveal chain-of-"
    "thought; give conclusions and the evidence behind them."
)

TEMPLATE = """Write the incident report using this data from one Red-vs-Blue round.

## What the Red agent (the attacker) did
- Techniques tried: {techniques_tried}
- Flaws it broke through (succeeded): {breached}
- Flaws that held (blocked): {held}
- Footholds gained: {footholds}
- Red's own summary: {red_summary}

## What the Blue agent (the defender) concluded — investigating blind
- Verdict: {verdict} (confidence {confidence})
- Flaws Blue independently identified from the evidence: {blue_flaws}
- Affected assets: {assets}
- Attack path reconstructed: {path}
- Recommended actions: {actions}

## Evidence Blue cited
{evidence}

## Timeline
{timeline}

## MITRE ATT&CK for ICS techniques mapped
{mitre}

Structure the report with these sections:
1. **Executive summary** (3-4 sentences, plain language a plant manager can read)
2. **What happened** (the attack narrative, in order)
3. **Which weaknesses were exploited** (one short paragraph per flaw: plain name, what it let the attacker do, and the fix)
4. **Did the defender catch it?** (compare Red's breaches with what Blue found; note agreement or any gap)
5. **Recommended actions** (prioritised, concrete)
6. **Technical appendix** (evidence ids, MITRE mapping, timeline) — compact.
"""


def _fmt_flaws(flaws: list[dict]) -> str:
    if not flaws:
        return "(none identified)"
    out = []
    for f in flaws:
        out.append(f"- {f.get('code', '?')} — {f.get('plain', f.get('title', ''))}: "
                   f"{f.get('means', '')} Fix: {f.get('fix', '')}")
    return "\n".join(out)


def _primary_alert(investigation: dict) -> dict:
    alerts = investigation.get("alerts") or []
    if not alerts:
        return {}
    # The alert with the highest confidence is the one worth narrating.
    return max(alerts, key=lambda a: a.get("confidence", 0))


def _build_prompt(red: dict, investigation: dict) -> str:
    a = _primary_alert(investigation)
    incident = investigation.get("incident")
    evidence = a.get("evidence") or []
    ev_txt = "\n".join(f"- [{e.get('id')}] {e.get('text')} (weight {e.get('weight')})"
                       for e in evidence[:20]) or "(no evidence collected)"
    tl = a.get("timeline") or []
    tl_txt = "\n".join(f"- {t.get('t')} · {t.get('asset')} · {t.get('text')}" for t in tl[:25]) or "(empty)"
    mitre = a.get("mitre") or []
    mitre_txt = "\n".join(f"- {m.get('id')} {m.get('name')}" for m in mitre) or "(none)"
    return TEMPLATE.format(
        techniques_tried=red.get("techniques_tried", "?"),
        breached=", ".join(red.get("breached_flaws") or []) or "none",
        held=", ".join(red.get("held_flaws") or []) or "none",
        footholds="; ".join(red.get("footholds") or []) or "none",
        red_summary=red.get("summary", ""),
        verdict=("INCIDENT" if incident else "No incident (authorised activity)"),
        confidence=a.get("confidence", "n/a"),
        blue_flaws=_fmt_flaws(investigation.get("flaws") or []),
        assets=", ".join(a.get("affected_assets") or []) or "none",
        path=" -> ".join(a.get("attack_path") or []) or "none",
        actions="; ".join(a.get("actions") or []) or "none",
        evidence=ev_txt, timeline=tl_txt, mitre=mitre_txt,
    )


def available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def generate(red: dict, investigation: dict) -> dict:
    """Return {ok, markdown, model} or {ok: False, error}. Never raises."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return {"ok": False, "error": "No OPENAI_API_KEY set. Add it to .env (gitignored) to enable GPT reports."}
    body = json.dumps({
        "model": DEFAULT_MODEL,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": _build_prompt(red or {}, investigation or {})},
        ],
    }).encode()
    req = urllib.request.Request(
        OPENAI_URL, data=body, method="POST",
        headers={"content-type": "application/json", "authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        md = data["choices"][0]["message"]["content"]
        return {"ok": True, "markdown": md, "model": data.get("model", DEFAULT_MODEL)}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.load(e).get("error", {}).get("message", "")
        except Exception:
            detail = e.reason
        # 401 = bad/rotated key, 429 = quota. Keep the message human.
        return {"ok": False, "error": f"OpenAI API error ({e.code}): {detail}"}
    except Exception as e:  # network, timeout, parse
        return {"ok": False, "error": f"Could not reach OpenAI: {e}"}
