"""FastAPI server for the Industrial Cyber-Arena Phase-1 prototype.  Run:  python -m uvicorn app.main:app --port 8000"""
import itertools
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import gateway, llm, sim
from .evaluate import evaluate
from .investigate import Run, red_assessment, run_investigation

app = FastAPI(title="Industrial Cyber-Arena (Phase 1 prototype)")
STATIC = Path(__file__).resolve().parent.parent / "static"
RUNS = {}
_ids = itertools.count(1)
SPEEDS = {"slow": 1.4, "normal": 0.8, "fast": 0.2}


class RunReq(BaseModel):
    scenario: str
    critic: bool = True
    speed: str = "normal"


class ReviewReq(BaseModel):
    decision: str  # approve | request_more


@app.get("/api/config")
def config():
    return dict(llm=llm.mode(), scenarios=sim.public_scenarios(), topology=sim.topology(),
                allowed={k: sorted(v) for k, v in gateway.ALLOWED.items()})


@app.post("/api/run")
def start(req: RunReq):
    if req.scenario not in sim.SCENARIOS:
        raise HTTPException(404, "unknown scenario")
    rid = f"run{next(_ids)}"
    run = Run(rid, sim.SCENARIOS[req.scenario], critic=req.critic, delay=SPEEDS.get(req.speed, 0.8))
    RUNS[rid] = run
    threading.Thread(target=_safe, args=(run,), daemon=True).start()
    return dict(run_id=rid)


def _safe(run):
    try:
        run_investigation(run)
    except Exception:
        pass


@app.get("/api/run/{rid}")
def poll(rid: str, since: int = 0):
    run = RUNS.get(rid)
    if not run:
        raise HTTPException(404, "unknown run")
    steps = run.get_steps(since)
    return dict(status=run.status, paused=run.paused, steps=steps, next=since + len(steps))


@app.post("/api/run/{rid}/pause")
def pause(rid: str):
    run = RUNS[rid]
    run.paused = not run.paused
    return dict(paused=run.paused)


@app.post("/api/run/{rid}/review")
def review(rid: str, req: ReviewReq):
    run = RUNS[rid]
    if run.report is None:
        raise HTTPException(409, "report not ready")
    truth = run.scn["truth"]
    run.review = req.decision
    run.status = "reviewed"
    return dict(decision=req.decision, correct=run.verdict == truth["incident"], truth_incident=truth["incident"],
                truth_summary=truth["summary"], inspired_by=run.scn.get("inspired_by"),
                note=("Analyst approved the finding." if req.decision == "approve"
                      else "Analyst sent the case back. In Phase 1 this is logged only; Phase 2 re-opens the investigation."))


@app.post("/api/red")
def red():
    return red_assessment()


@app.post("/api/probe")
def probe():
    return dict(audit=gateway.probe())


@app.get("/api/compare")
def compare(scenario: str):
    """Head-to-head: the same scenario with and without the Critic (System C vs System D)."""
    if scenario not in sim.SCENARIOS:
        raise HTTPException(404, "unknown scenario")
    scn = sim.SCENARIOS[scenario]
    out = dict(name=scn["name"], truth_incident=scn["truth"]["incident"], truth_summary=scn["truth"]["summary"])
    for key, critic in (("C", False), ("D", True)):
        r = Run("cmp", scn, critic=critic, delay=0)
        run_investigation(r)
        prelim = next((s["data"]["prelim"] for s in r.steps if s["data"].get("prelim") is not None), None)
        out[key] = dict(incident=r.verdict, confidence=r.report["confidence"], prelim=prelim, evidence=len(r.book.items),
                        tool_calls=r.tool_calls, correct=r.verdict == scn["truth"]["incident"], summary=r.report["summary"])
    return out


@app.get("/api/evaluate")
def run_eval():
    return evaluate()


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
