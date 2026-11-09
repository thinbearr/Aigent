# Paper outline (numbers are the real measured ones, see docs/BENCHMARK.md)

Working title: *Ticket-aware critique for alert triage in industrial control networks: a read-only multi-agent assistant and a reproducible range benchmark*

1. **Introduction.** Alert fatigue in OT; many alerts are approved maintenance that looks like an attack. Claim (range only): a Critic that *checks* tickets, authorisation and
   change scope removes false alarms that a rule detector and a Critic-less agent raise. Contributions: (i) a read-only triage engine with an audited gateway; (ii) a 32-family range
   benchmark with hard cases; (iii) an honest negative/limits section.
2. **Related work.** ICS datasets (HAI), SOC triage assistants, LLM agents for security, ATT&CK for ICS. (To be filled; cite only verified sources.)
3. **System.** Canonical schema; site config; normaliser; evidence model (logistic of weighted evidence, hand-set weights); Blue / Critic / Forensics; gateway (no write tool,
   allow-lists, audit). The LLM is optional and never decides.
4. **Range and scenarios.** Kaveri plant (Purdue L4-L0, 11 breach points); 32 families; how hard cases were built; export to files; freeze hash (`paper/scenario_freeze.txt`).
5. **Experimental setup.** Systems A, C, D (+ ablations); B, E **not yet run**; metrics; Wilson CIs; exact McNemar with Holm; pooled vs family level; seeds.
6. **Results.** Main table (A 66 %, C 78 %, D 96 % accuracy; false alarms 69 / 38 / 8 %); hard cases (44 / 56 / 91 %); ablation (maintenance check is the largest contributor); cost (5.3 vs 7.3 tool calls, ~1 ms, no LLM tokens);
   significance (D vs C significant pooled, **not** at family level after Holm).
7. **Failure analysis.** B07 and B01 engine defects; A15 blocked attempts; rule detector false alarms; seeds barely vary results.
8. **HAI process-anomaly experiment.** Limited, one file, does not test the Critic; all 5 segments detected, 1-2 % point precision.
9. **Threats to validity.** Copy from `docs/LIMITATIONS.md` (authors wrote scenarios and tuned weights; range logs the exact fields; correlated seeds; clean tickets assumed; label policy; no live data).
10. **Discussion and pilot plan.** What a plant pilot needs (tickets with approved values, accounts, roles); next: B/E with a strong LLM, blind scenarios, Zeek/Modbus adapter.
11. **Conclusion.** Mechanism shown on a simulated range; not validated on a live plant.

Before submission: choose a licence and check IP / publication rules with the mentor.
