# CyberArena

> **If you are an AI assistant (Claude) reading this README to continue the project: read this whole file, then `docs/HANDOFF.md`,
> `docs/LIMITATIONS.md`, `docs/BENCHMARK.md` and `paper/scenario_freeze.txt`. Everything you need to continue is in this repository.**

## Project context (for a new session)

* **Who/why:** a student project (RVCE, 5th-semester Experiential Learning, theme: industrial cybersecurity, SDG 9). The user's goal is a tool real
  people can use on real industrial plants, which also records **paper-grade benchmarks** so they can publish a paper.
* **What it is:** a read-only alert-triage assistant for OT/ICS networks. An alert comes in; agents investigate; a report goes to a human who approves it.
  It never changes anything in the plant.
* **The novelty being tested:** a **Critic** agent that *checks* change tickets, authorisation and change scope, so approved maintenance that looks like an
  attack is cleared, and abuse of a ticket is not. **This claim is shown on a simulated range only.** No live-plant validation exists.
* **History:** this repo replaces an earlier Phase-1 prototype (still in git history of this repo). Other earlier prototypes (a demo integration with a React UI, and
  "ICS-Arena" phases 2-3 with a pure-Python plant simulator and LLM baselines) live only on the user's laptop and are not needed to continue.
* **How to run:** see "Quick start" below. `pip install -e ".[all]"`, `pytest` (25 pass), `cyberarena triage ...`, `cyberarena bench ...`.
* **Rules you must keep (set by the user):** do not claim agents beat a strong single LLM given the same records unless data shows it (earlier exploratory runs
  showed a tie); do not claim live-plant validation; report failures and unflattering numbers; the evidence weights are hand-tuned and the scenarios were written by
  the authors (say so in the paper); HAI is sensor data only and cannot test the Critic; Docker/OpenPLC are untested; the licence and IP/publication rules are an open
  decision for the user and their mentor (remind them). Commit as the user, with no AI co-author trailer.
* **Most valuable next steps:** run systems B and E (single LLM) with a stronger model; fix the two documented engine defects as a versioned change with before/after
  results; add scenarios written blind by someone else; pilot on real exported logs + tickets. Full list: `docs/HANDOFF.md`.

---

A **read-only alert-triage assistant for industrial networks**. An alert comes in; a small team of agents investigates it
and hands a report to a human, who approves it or sends it back. **It never changes anything in the plant.**

* **Blue** gathers evidence from the logs and scores it.
* **Critic** challenges Blue's verdict by *checking*: is there a change ticket, was this person authorised, is the change
  within the value the ticket approved? A "scary" event with a matching ticket is cleared; an event with a ticket that does
  not cover it is not.
* **Forensics** builds the timeline and graph. Every line cites the evidence behind it.
* The verdict comes from a weighted **evidence model**, not from free text. A language model is optional and only rewrites
  narration, so the tool works fully offline.

```
adapters/   real data in      CSV / JSON / JSONL / syslog logs + a tickets spreadsheet (CSV / XLSX)
core/       the engine        canonical schema, site config (YAML), read-only gateway, agents, evidence model
range/      the simulator     the Kaveri plant: breach points, 32 scenario families, hidden ground truth
bench/      the paper         systems A-E, Wilson CIs, McNemar, ablation, figures, one command
```

## What has been executed (verified by running, 2026-11-09)

| item | status |
|---|---|
| `pytest` | **25 passed** (adapters, statistics, read-only gateway, no ground truth in evidence, range twins, PLC bridge client vs a stand-in server) |
| `cyberarena triage` on `examples/` | **ran**: cleared the ticketed change, flagged the vendor chain |
| Range: 32 scenario families x 5 seeds = 160 cases | **generated and benchmarked** |
| Systems A, C, D + 3 Critic ablations | **run**: accuracy 66 / 78 / 96 %, see [docs/BENCHMARK.md](docs/BENCHMARK.md) |
| Systems B, E (single LLM) | **NOT run in the results** (code exists; a first attempt was abandoned, see `paper/scenario_freeze.txt`) |
| HAI (one file, process anomaly only) | **ran**: finds all 5 attack segments, 1-2 % point precision. Does not test the Critic |
| Docker image, compose, OpenPLC, `plc/MixTankControl.st` | **written, never built or run** (no Docker on the dev machine) |
| Live plant / real logs | **never run** |
| Two engine defects found after the frozen run | **open, deliberately unfixed** (docs/HANDOFF.md) |

Continuing this work (e.g. with Claude)? Start with [docs/HANDOFF.md](docs/HANDOFF.md).

## Status: read this first

* Validated on a **simulated range** (32 scenario families we wrote) and one public dataset used for process anomalies only.
* **Not validated on a live plant.** The honest status is *ready for a pilot*, not *proven in production*.
* The evidence weights are hand-tuned and the scenarios were written by the same people. See [docs/LIMITATIONS.md](docs/LIMITATIONS.md)
  and the numbers in [docs/BENCHMARK.md](docs/BENCHMARK.md).
* The OpenPLC / Docker parts are **untested** (no Docker on the development machine).
* **Licence: placeholder.** Decide a licence and check IP / publication rules with your mentor or institution before publishing anything.

## Quick start (no Docker)

```bash
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[all]"

# 1. triage real-format logs with a site config and a tickets sheet
cyberarena triage --events examples/events.csv --tickets examples/tickets.csv --site config/site.example.yaml --out out/

# 2. look at the simulated range and its 32 scenario families
cyberarena range list
cyberarena range serve            # plant UI/API :8000, developer API :8100, Modbus/TCP :5020

# 3. reproduce every benchmark table and figure from scratch (fixed seeds)
cyberarena bench --out results --seeds 1 2 3 4 5 --systems A C D          # add B E with a local LLM, see below

# 4. tests
pytest
```

`triage` prints one line per alert and writes a Markdown + JSON report per alert (evidence table, alternatives tested,
timeline, suggested actions, and an audit of every tool call). A human decides; nothing is executed.

### Using your own plant

1. Copy `config/site.example.yaml` and describe your assets, roles, accounts, engineering limits and "normal" ([docs/CONFIG.md](docs/CONFIG.md)).
2. Export logs as CSV/JSON/syslog and tickets as CSV/XLSX; map your column names and event names ([docs/ADAPTERS.md](docs/ADAPTERS.md)).
3. Run `cyberarena triage ...` on a **copy** of last month's data first, and compare with what your analysts decided.

### Optional language model (offline or cloud)

Nothing needs one. For narration, or for the single-LLM baselines B and E in the benchmark:

```bash
OLLAMA_MODEL=llama3.2:3b cyberarena bench --systems A B E C D --llm-seeds 1 2     # local, offline
# or GROQ_API_KEY / ANTHROPIC_API_KEY / LLM_BASE_URL+LLM_API_KEY+LLM_MODEL
```

Scenario text is sent to whichever provider you configure. Use only synthetic or properly cleared data with cloud models.

## Docker (untested)

`Dockerfile` and `docker-compose.yml` are provided but were never built or run. See [docs/OPENPLC.md](docs/OPENPLC.md).

## Layout

```
src/cyberarena/core      schema, site, normalise, gateway, evidence, investigate, systems, engine, report, llm
src/cyberarena/adapters  csvjson, syslog, tickets
src/cyberarena/range     families.py (the frozen scenario set), generate.py, kaveri/ (the plant)
src/cyberarena/bench     runner, stats, report (tables/figures), hai, cli
config/                  site.example.yaml     examples/  events.csv, tickets.csv
docs/                    ADAPTERS, CONFIG, BENCHMARK, LIMITATIONS, OPENPLC, PAPER_OUTLINE
paper/                   scenario_freeze.txt (hashes recorded BEFORE the benchmark was run)
```

## Safety design

* One tool gateway; every tool is a read (`get_*`, `query_*`, `check_*`); there is no write tool in the code base (a test enforces this).
* Per-agent allow-lists (the Critic and Orchestrator have no tools), a sandbox scope, and an audit log of every call, denied calls included.
* Ground truth never enters the engine: the range exports it to a separate file that only the scorer reads (a test checks it is not in the evidence).
