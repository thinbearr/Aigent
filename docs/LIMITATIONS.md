# Limitations (read before citing any number)

## What has and has not been shown

| claim | status |
|---|---|
| The engine triages alerts from CSV/JSON/syslog logs plus a tickets sheet, read-only | **Works** on the examples and tests in this repo (25 tests). Not run on any real plant data. |
| On a simulated range, the Critic removes false alarms that a rule detector and a Critic-less agent raise | **Measured** on 32 families we wrote (docs/BENCHMARK.md). Mechanism evidence, not generalisation. |
| Agents beat a strong single LLM given the same records | **Not shown.** The only LLM run here is a 3B local model on a subset of seeds. Earlier exploratory runs (CyberArena-Final) with a larger model showed a **tie**. |
| Works on a live plant | **Not shown. No live-plant validation exists.** Status: ready for a pilot. |
| The process-anomaly layer works on public data | **Weak**: on one HAI file it finds all 5 attack segments but with 1-2 % point precision (docs/BENCHMARK.md). HAI cannot test the Critic. |
| OpenPLC / Docker integration | **Untested.** See docs/OPENPLC.md. |

## Threats to validity (put these in the paper)

1. **We wrote the scenarios and the model.** The evidence weights (`core/evidence.py`) and the Critic's checks were hand-tuned on an earlier
   set of 14 scenarios whose results we saw (CyberArena-Final). The 32 families here were written afterwards, several are variants of those
   earlier ones, and the pipeline was trial-run on seed 1 before the final run. Hashes and a dated statement are in `paper/scenario_freeze.txt`.
   Scenario authors know what the Critic checks; an external red team writing scenarios blind would be a fairer test.
2. **The range emits exactly the fields the engine reads.** The Kaveri plant logs `old`, `new`, `changed_parameters`, `method`, etc. Real logs are
   messier. The adapters are meant to close that gap, but the benchmark does not measure how well your logs map.
3. **Seeds vary parameters, not structure.** Five seeds change actors, values, ticket limits and background noise; the same family is the same
   story every time. Pooled cases are therefore correlated; the benchmark reports family-level tests alongside pooled ones, and the family-level
   test (n = 32) is the one to trust.
4. **Ticket data is assumed clean.** If real tickets are missing, late, or lack approved values, the Critic's value shrinks. The engine
   cannot detect "change beyond the approved value" without `approved_values`.
5. **Label definitions are ours.** We label reconnaissance and blocked attempts as attacks, and an authorised engineer exceeding a ticket as an
   attack. A different policy changes the table.
6. **One background-noise model**, a few kinds of routine event, no seasonal or shift patterns.
7. **Detection is partly structural.** Some attacks are caught only because the range's firewall logs a connection from an untrusted host
   (e.g. an engineer's workstation writing to the PLC). That evidence exists in the simulator by design.
8. **Single LLM baseline is weak here**: a 3B model on a subset of seeds; do not read B/E as "LLMs cannot do this".
9. **Time and cost** of the agents are CPU seconds on one laptop for deterministic code; LLM cost is tokens only.

## Known failure modes of the engine (from the benchmark; see results/failures.md for the full list)

* A change by an authorised engineer with **no ticket but inside limits** is borderline by design (role authorisation offsets the missing ticket).
* Anything the Critic cannot check is left to Blue's first read: there are no checks for firmware signatures, process physics plausibility or
  out-of-band approvals.
* The Critic can only be as good as the tickets: a stale or bulk-approved ticket will clear a bad change.
* Verdict weights are not calibrated probabilities; "confidence 0.8" does not mean 80 % of such cases are attacks.

## Safety and responsible use

* Read-only by construction (no write tool; tested). It still reads sensitive logs: run it on a copy, in your own environment.
* If an LLM is configured, event text is sent to that provider. Use local models or cleared data.
* The range is **deliberately vulnerable**. Run it only on an isolated machine.

## Licence and IP (action for you)

The licence is a placeholder in `pyproject.toml`. **Before publishing code, data or a paper, decide a licence and check your institution's
IP and publication rules with your mentor.**
