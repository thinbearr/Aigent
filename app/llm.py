"""Optional LLM hook for narrative text only.

The investigation logic (which tool to call, how evidence is weighted, the verdict) is deterministic so the demo is
repeatable. If an LLM is configured it only rewrites explanations: Blue's reasoning, the Critic's challenge and the
report summary. With no configuration, built-in templates are used and nothing leaves the machine.

  Anthropic API : set ANTHROPIC_API_KEY (optional ANTHROPIC_MODEL, default claude-sonnet-5-5)
  Local Ollama  : set OLLAMA_MODEL, e.g. llama3.1 (server at http://localhost:11434)
"""
import json
import os
import urllib.request

SYSTEM = ("You are part of an industrial-control-system security investigation team. Answer in at most two short "
          "sentences of plain English. Use only the facts given. Do not invent evidence.")


def mode():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OLLAMA_MODEL"):
        return "ollama"
    return "off"


def _post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def say(role, prompt, fallback):
    m = mode()
    try:
        if m == "anthropic":
            out = _post("https://api.anthropic.com/v1/messages",
                        dict(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"), max_tokens=160, system=SYSTEM,
                             messages=[dict(role="user", content=f"Role: {role}\n{prompt}")]),
                        {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                         "content-type": "application/json"})
            return out["content"][0]["text"].strip()
        if m == "ollama":
            out = _post("http://localhost:11434/api/generate",
                        dict(model=os.environ["OLLAMA_MODEL"], prompt=f"{SYSTEM}\nRole: {role}\n{prompt}", stream=False),
                        {"content-type": "application/json"})
            return out["response"].strip()
    except Exception:
        pass
    return fallback
