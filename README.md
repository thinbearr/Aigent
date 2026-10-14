# Industrial Cyber-Arena: Phase 1 prototype

A runnable slice of the project: a simulated industrial plant in which AI agents (Orchestrator, Red, Blue, Forensics, Critic)
investigate security alerts, behind a Tool Gateway, with an evidence graph, MITRE ATT&CK for ICS mapping, a report and human review.

## Run it

Double-click `run.bat`, or:

```
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

Open http://localhost:8000. Run the tests with `python -m pytest -q`.
No API key and no internet are needed. Optional: set `ANTHROPIC_API_KEY` or `OLLAMA_MODEL` and an LLM will narrate the agents' reasoning (it never decides the verdict).

## 6-minute demo script

1. **The problem (30 s).** Pick *Scenario 2*, switch the **Critic Agent OFF**, speed *Normal*, press **Run**. Explain: Blue Agent reads logs through the Tool Gateway and scores anything unusual. Point at the Presenter notes under each step.
2. **The false alarm (1 min).** It ends with *Security incident, confidence 0.63*. Press **Approve** and show the ground truth: it was an authorised change under ticket CHG-1042. "A single-pass analyst raised a false alarm."
3. **The Critic (2 min).** Switch the Critic **ON**, run Scenario 2 again. Show the Critic's challenge (alternative explanations), the checks it requests, the confidence dropping from 0.63 (blue tick) to 0.13, and "Preliminary verdict OVERTURNED".
4. **A real attack (1.5 min).** Run *Scenario 3* (inspired by the Dec 2025 Poland attacks). Show the evidence graph on the plant map, the MITRE techniques and recommended actions in the Report tab. Note the Critic could not explain the activity away, so confidence rose.
5. **Safety (30 s).** Press **Try forbidden actions**. Four attempts are DENIED in the Gateway audit log. The Critic and Orchestrator have no tool access at all.
6. **Evaluation (30 s).** Press **Evaluate A / C / D**: the Critic removes both false positives. Be explicit that this is 5 scripted scenarios demonstrating a mechanism, not a performance measurement.

Also try **Red assessment** (read-only findings that mirror the Poland weaknesses).

## Layout

```
app/sim.py          plant, topology, 5 scripted scenarios with hidden ground truth
app/gateway.py      Tool Gateway: per-agent allow-list, sandbox scope check, audit log
app/evidence.py     signal extraction, evidence store, confidence model, MITRE mapping
app/investigate.py  Orchestrator / Blue / Critic / Forensics / Red agents, report
app/evaluate.py     Systems A (rules), C (no Critic), D (full) across all scenarios
app/llm.py          optional LLM narration hook
app/main.py         FastAPI server
static/             dashboard (plain HTML/JS/SVG, no build step)
tests/              9 tests
```

## Honest limits (say these before your mentor asks)

- Events are scripted. Verdicts come from hand-set evidence weights, so the *mechanism* is real but the numbers are illustrative.
- Agent "reasoning" is rule-based in Phase 1. An LLM only rewrites explanations, if configured. (LLM calls are implemented but untested in this build, because no API key was available.)
- No Docker isolation, no real PLC/process simulation, no memory or RAG, no System B (single-LLM baseline) yet.
- "Request more investigation" is logged but does not re-open the case yet.

## Suggested Phase 2

Docker-isolated plant with a PLC/process simulator, LLM-driven planning and tool choice, RAG over ICS documents, memory, more scenarios with real statistics, System B baseline, re-opening cases.
