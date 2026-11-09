# Handoff for the next Claude session

You are continuing a student project (RVCE, 5th-sem EL). Read `README.md`, `docs/LIMITATIONS.md`, `docs/BENCHMARK.md`, `paper/scenario_freeze.txt` first.

## Goal (set by the user)

A tool real people can use on real industrial plants **and** paper-grade benchmarks. Read-only alert triage: Blue gathers evidence, Critic challenges it by checking tickets /
authorisation / change scope, Forensics builds timeline and graph, a human approves. It must never change anything in the plant. Engine (`core/`), real-data adapters
(`adapters/`), simulator (`range/`, the Kaveri plant), benchmark (`bench/`).

## Honesty rules the user set (keep them)

* No claim agents beat a strong single LLM given the same records unless data shows it (earlier runs showed a tie).
* No claim of live-plant validation. Status: validated on a simulated range and a public dataset, ready for a pilot.
* Report failures and unflattering numbers as they come out. Weights are hand-tuned; scenarios were written by the authors.
* HAI: sensor time series only; it cannot test the Critic. One file only was approved and used.
* Licence and IP are open: remind the user to pick a licence and check IP rules with their mentor before publishing.
* The user's machine has no Docker: never claim the Docker/OpenPLC parts work.
* Commits are made as the user (Mayur), not as Claude. Do not add co-author trailers unless the user asks.

## State at handoff (all verified by running)

* `pytest` -> 25 passed. `cyberarena triage` works on `examples/`. `cyberarena range generate|list|serve` work. `cyberarena bench` reproduces `results/` in seconds.
* Final results: systems A, C, D + three Critic ablations on 160 cases (see docs/BENCHMARK.md). HAI experiment done (poor precision, reported).
* **Not run: systems B and E** (single LLM). Ollama with `llama3.2:3b` is installed on the user's laptop but is slow and weak. Needs a better model/key.
  Run: `OLLAMA_MODEL=<model> cyberarena bench --systems A B E C D --llm-seeds 1` (narration is off during scoring, on purpose).
* Docker, docker-compose and `plc/MixTankControl.st`: written, **never built or run**.

## Known defects (found AFTER the frozen run; deliberately not fixed so results match the freeze)

1. `core/tickets.py` `covering()` returns the first ticket covering asset+time, not the acting user's ticket. Causes B07 (second ticket is valid) to fail 5/5. Fix: prefer the ticket assigned to the acting user.
2. `core/gateway.py` `_t_check_change_scope` judges every config event on the asset, including routine operator nudges by other users. Fix: only judge events by the user under investigation.
3. Blocked attempts are weak evidence (A15). Decide a policy and document it.

If you fix them: make it a **new version**, keep the old results, report before/after, and append an addendum to `paper/scenario_freeze.txt`. Do not quietly overwrite results.

## Suggested next steps (in order)

1. Run B and E with a stronger model on at least one seed; add to the tables; say plainly if the agents do not beat E.
2. Fix defects 1-2 as "v1", re-run, report both.
3. Add scenarios written by someone else (blind), because the authors wrote these and know what the Critic checks. More structurally different families matter more than more seeds (seeds barely vary results).
4. Real-data pilot: export a month of historical alerts + tickets from a friendly plant/lab, map them with `docs/ADAPTERS.md`, compare with analyst decisions.
5. Zeek/Modbus capture adapter; Wazuh/Splunk/Elastic exports.
6. Test Docker + OpenPLC if a machine with Docker is available (docs/OPENPLC.md checklist).
7. Fill `docs/PAPER_OUTLINE.md` further; the paper must state the threats in LIMITATIONS.md.

## Practical notes

* Windows + Git Bash. Create a venv and `pip install -e ".[all]"`. Native Python cannot read git-bash `/tmp` paths; use Windows paths for files Python opens.
* `results/cases/` holds the generated cases (events, tickets, truth). `external/` (HAI data) is git-ignored: re-download `hai-21.03/test1.csv.gz` from github.com/icsdataset/hai if needed (6,149,549 bytes).
* Earlier prototypes (not in this repo): `CyberArena-Final` (demo integration with a React UI) and ICS-Arena phases 1-3 on the user's Desktop.
