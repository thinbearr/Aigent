"""The agent service's FastAPI app (its own container, port 8200)."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import investigate_svc, plant_client, redteam

app = FastAPI(title="CyberArena · Investigation Agent", version="1.0.0",
              description="Autonomous Blue/Critic/Forensics investigation. Separate service; pulls evidence "
                          "from the plant over HTTP and never sees ground truth.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class InvestigateIn(BaseModel):
    critic: bool = True
    since_id: int = 0


@app.get("/agent/health")
def health():
    return {"status": "ok", "service": "agent", "plant_url": plant_client.PLANT_URL}


@app.get("/agent/plant")
def plant_link():
    """Is the target plant reachable, and what does the agent currently see?"""
    try:
        h = plant_client.plant_health()
        sources = plant_client.fetch_sources()
    except plant_client.PlantUnavailable as e:
        return {"connected": False, "plant_url": plant_client.PLANT_URL, "error": str(e)}
    # Tickets endpoint is optional — not all plant deployments expose it yet.
    try:
        tickets = plant_client.fetch_tickets()
        ticket_count = len(tickets)
    except plant_client.PlantUnavailable:
        ticket_count = None
    return {"connected": True, "plant_url": plant_client.PLANT_URL,
            "event_count": h.get("event_count"), "by_source": sources, "tickets": ticket_count}


@app.post("/agent/redteam")
def redteam_attack():
    """Red agent: autonomously probe every exploit technique; the open flaws succeed."""
    try:
        return redteam.run_pentest()
    except plant_client.PlantUnavailable as e:
        raise HTTPException(502, str(e))


@app.post("/agent/investigate")
def investigate(body: InvestigateIn):
    try:
        return investigate_svc.investigate(since_id=body.since_id, critic=body.critic)
    except plant_client.PlantUnavailable as e:
        raise HTTPException(502, str(e))


def serve():
    import os
    import uvicorn
    uvicorn.run(app, host=os.getenv("AGENT_HOST", "0.0.0.0"), port=int(os.getenv("AGENT_PORT", "8200")),
                log_level="warning")
