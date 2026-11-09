"""Optional LLM access.

* ``say`` rewrites narration (Blue's reasoning, the Critic's challenge, the report summary). Templates are used when no LLM is configured.
* ``complete`` is used by System B (single LLM baseline). It raises LLMUnavailable when no LLM is configured.

Configure ONE of these with environment variables (keys are read from the environment, never stored in files):

  GROQ_API_KEY (+ optional GROQ_MODEL, default openai/gpt-oss-120b)       Groq, via its OpenAI-compatible API
  ANTHROPIC_API_KEY (+ optional ANTHROPIC_MODEL)                              Anthropic
  LLM_BASE_URL + LLM_API_KEY + LLM_MODEL                                      any OpenAI-compatible endpoint
  OLLAMA_MODEL                                                                local Ollama at http://localhost:11434

Scenario text (alert and events) is sent to the provider you choose. Use only synthetic data.
Integrators and tests can inject any callable with ``set_backend(fn)`` where ``fn(system, prompt) -> str``.
"""
import json
import os
import time
import urllib.error
import urllib.request

SYSTEM = ("You are part of an industrial-control-system security investigation team. Answer in at most two short "
          "sentences of plain English. Use only the facts given. Do not invent evidence.")

_BACKEND = None
USAGE = dict(calls=0, prompt_tokens=0, completion_tokens=0, seconds=0.0)


def usage():
    return dict(USAGE)


def reset_usage():
    for k in USAGE:
        USAGE[k] = 0 if k != "seconds" else 0.0


class LLMUnavailable(RuntimeError):
    pass


def set_backend(fn):
    """Inject a callable fn(system, prompt) -> str, or None to remove it."""
    global _BACKEND
    _BACKEND = fn


GROQ_BASE = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"


def mode():
    if _BACKEND:
        return "custom"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_API_KEY") and os.environ.get("LLM_MODEL"):
        return "openai-compatible"
    if os.environ.get("OLLAMA_MODEL"):
        return "ollama"
    return "off"


RETRIES = 6
RETRY_CODES = (429, 500, 502, 503, 504)


def _retry_wait(exc, attempt):
    """Seconds to wait before retrying: the server's Retry-After if given, else exponential backoff (capped)."""
    try:
        return min(float(exc.headers.get("retry-after")), 60.0)
    except (TypeError, ValueError, AttributeError):
        return min(2.0 * 2 ** attempt, 30.0)


def _post(url, body, headers):
    headers = {"User-Agent": "ics-arena/0.2", **headers}   # some providers reject urllib's default agent
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=int(os.environ.get("LLM_TIMEOUT", "600"))) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as exc:      # rate limits and transient server errors are retried
            if exc.code in RETRY_CODES and attempt < RETRIES - 1:
                time.sleep(_retry_wait(exc, attempt))
                continue
            raise


def _chat(base, key, model, system, prompt, max_tokens):
    """OpenAI-compatible chat completion (Groq and others)."""
    out = _post(base.rstrip("/") + "/chat/completions",
                dict(model=model, max_tokens=max_tokens, temperature=0,
                     messages=[dict(role="system", content=system), dict(role="user", content=prompt)]),
                {"Authorization": f"Bearer {key}", "content-type": "application/json"})
    u = out.get("usage") or {}
    USAGE["prompt_tokens"] += u.get("prompt_tokens", 0)
    USAGE["completion_tokens"] += u.get("completion_tokens", 0)
    return out["choices"][0]["message"]["content"].strip()


def complete(prompt, system=SYSTEM, max_tokens=300, use_custom=True):
    t0 = time.time()
    try:
        return _complete(prompt, system, max_tokens, use_custom)
    finally:
        USAGE["seconds"] += time.time() - t0


def _complete(prompt, system=SYSTEM, max_tokens=300, use_custom=True):
    m = mode()
    if m == "off" or (m == "custom" and not use_custom):
        raise LLMUnavailable("no LLM configured (set GROQ_API_KEY, ANTHROPIC_API_KEY, LLM_* or OLLAMA_MODEL)")
    USAGE["calls"] += 1
    try:
        if m == "custom":
            return str(_BACKEND(system, prompt)).strip()
        if m == "groq":
            return _chat(GROQ_BASE, os.environ["GROQ_API_KEY"], os.environ.get("GROQ_MODEL", GROQ_DEFAULT_MODEL), system, prompt, max_tokens)
        if m == "openai-compatible":
            return _chat(os.environ["LLM_BASE_URL"], os.environ["LLM_API_KEY"], os.environ["LLM_MODEL"], system, prompt, max_tokens)
        if m == "anthropic":
            out = _post("https://api.anthropic.com/v1/messages",
                        dict(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"), max_tokens=max_tokens, system=system,
                             messages=[dict(role="user", content=prompt)]),
                        {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
            u = out.get("usage") or {}
            USAGE["prompt_tokens"] += u.get("input_tokens", 0)
            USAGE["completion_tokens"] += u.get("output_tokens", 0)
            return out["content"][0]["text"].strip()
        out = _post(os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/") + "/api/generate",
                    dict(model=os.environ["OLLAMA_MODEL"], prompt=f"{system}\n{prompt}", stream=False,
                         options=dict(temperature=0, seed=0, num_predict=max_tokens)), {"content-type": "application/json"})
        USAGE["prompt_tokens"] += out.get("prompt_eval_count", 0)
        USAGE["completion_tokens"] += out.get("eval_count", 0)
        return out["response"].strip()
    except LLMUnavailable:
        raise
    except Exception as exc:  # network, auth, parsing: surface as one error type
        raise LLMUnavailable(f"LLM call failed: {exc}") from exc


NARRATE = True      # the benchmark switches this off: narration never changes a verdict and would only add cost


def set_narration(on: bool):
    global NARRATE
    NARRATE = bool(on)


def say(role, prompt, fallback):
    """Narration only. Never used for verdicts. Falls back to the template text."""
    if not NARRATE or mode() not in ("groq", "anthropic", "openai-compatible", "ollama"):
        return fallback
    try:
        return complete(f"Role: {role}\n{prompt}", use_custom=False, max_tokens=160)
    except LLMUnavailable:
        return fallback
