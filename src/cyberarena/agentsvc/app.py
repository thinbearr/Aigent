"""The agent service's FastAPI app (its own container, port 8200)."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import gpt_report, investigate_svc, plant_client, redteam

app = FastAPI(title="CyberArena · Investigation Agent", version="1.1.0",
              description="Autonomous Blue/Critic/Forensics investigation. Separate service; pulls evidence "
                          "from the plant over HTTP and never sees ground truth.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# One round's memory, so the Blue investigation can scope itself to what the Red run just did and
# the GPT report can be written without the client re-posting everything. Single-process, per-session.
_ROUND: dict = {"baseline_event_id": 0, "red": None, "investigation": None}


class InvestigateIn(BaseModel):
    critic: bool = True
    since_id: int = 0          # 0 = use the watermark from the last Red run (this round only)
    full_log: bool = False     # True = ignore the watermark and scan the whole log


@app.get("/agent/health")
def health():
    return {"status": "ok", "service": "agent", "plant_url": plant_client.plant_url(),
            "connected": plant_client.is_connected(), "gpt_report": gpt_report.available()}


def _plant_snapshot() -> dict:
    """Reach the plant and describe what the agent can currently see (shared by /plant and /connect)."""
    try:
        h = plant_client.plant_health()
        sources = plant_client.fetch_sources()
    except plant_client.PlantUnavailable as e:
        plant_client.set_connected(False)
        return {"connected": False, "plant_url": plant_client.plant_url(), "error": str(e)}
    plant_client.set_connected(True)
    # Tickets endpoint is optional — not all plant deployments expose it yet.
    try:
        ticket_count = len(plant_client.fetch_tickets())
    except plant_client.PlantUnavailable:
        ticket_count = None
    return {"connected": True, "plant_url": plant_client.plant_url(),
            "event_count": h.get("event_count"), "by_source": sources, "tickets": ticket_count}


class ConnectIn(BaseModel):
    url: str | None = None   # omit to just (re)check the current target


@app.post("/agent/connect")
def connect(body: ConnectIn):
    """Point the agent at a plant and verify it is reachable. The agent does not touch any plant
    until this is called — on the landing page the operator connects it live."""
    if body.url:
        plant_client.set_plant_url(body.url)
    return _plant_snapshot()


@app.post("/agent/disconnect")
def disconnect():
    plant_client.set_connected(False)
    return {"connected": False, "plant_url": plant_client.plant_url()}


@app.get("/agent/plant")
def plant_link():
    """Is the target plant reachable, and what does the agent currently see?
    Returns connected:false without probing until the operator has connected."""
    if not plant_client.is_connected():
        return {"connected": False, "plant_url": plant_client.plant_url(), "idle": True}
    return _plant_snapshot()


@app.post("/agent/redteam")
def redteam_attack():
    """Red agent: autonomously probe every exploit technique; the open flaws succeed."""
    try:
        res = redteam.run_pentest()
    except plant_client.PlantUnavailable as e:
        raise HTTPException(502, str(e))
    _ROUND["baseline_event_id"] = int(res.get("baseline_event_id", 0) or 0)
    _ROUND["red"] = res
    _ROUND["investigation"] = None   # a new attack invalidates the last investigation
    return res


@app.post("/agent/investigate")
def investigate(body: InvestigateIn):
    # Default to this round only: start from the watermark captured when Red attacked, so the agent
    # does not re-score flaws left in the log by earlier rounds. full_log overrides for a deep sweep.
    since = body.since_id
    if since == 0 and not body.full_log:
        since = _ROUND["baseline_event_id"]
    try:
        res = investigate_svc.investigate(since_id=since, critic=body.critic)
    except plant_client.PlantUnavailable as e:
        raise HTTPException(502, str(e))
    _ROUND["investigation"] = res
    return res


class ReportIn(BaseModel):
    # Both optional: if omitted, the service uses the last Red run and investigation from this round.
    red: dict | None = None
    investigation: dict | None = None


@app.post("/agent/report")
def report(body: ReportIn):
    """Write a detailed, plain-language incident report with GPT from the current round's result."""
    red = body.red if body.red is not None else _ROUND["red"]
    inv = body.investigation if body.investigation is not None else _ROUND["investigation"]
    if red is None and inv is None:
        raise HTTPException(409, "No round to report on yet — run the Red agent and the investigation first.")
    out = gpt_report.generate(red or {}, inv or {})
    if not out.get("ok"):
        raise HTTPException(502, out.get("error", "report generation failed"))
    return out


def serve():
    import os
    import uvicorn
    uvicorn.run(app, host=os.getenv("AGENT_HOST", "0.0.0.0"), port=int(os.getenv("AGENT_PORT", "8200")),
                log_level="warning")
