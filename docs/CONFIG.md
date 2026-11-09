# Site configuration (`site.yaml`)

Everything about *your* plant lives here, not in the engine. `config/site.example.yaml` is the simulated Kaveri range written in this format.

| key | what it is | used for |
|---|---|---|
| `assets[]` | `id`, `ip` (+ `extra_ips`), `zone`, `role` | mapping IP addresses to assets; how deep an asset is |
| `zones` | ordered outside -> process (default DMZ, IT, OT, Control, Process) | ranking assets; "deep" = OT or deeper |
| `internal_cidrs` | your private ranges | an address outside them is `external` |
| `remote_gateways` | hosts whose logins are remote access | expecting MFA on those logins |
| `trusted_sources` | hosts that normally talk to controllers (e.g. the HMI) | which connections / reads are baseline |
| `accounts` | `user: {role, default, shared, enabled}` | `default: true` marks factory-default logins |
| `roles` | role -> assets that role may operate | the Critic's authorisation check |
| `ticket_roles` | roles authorised only while holding a ticket (vendors) | same |
| `asset_aliases` | a ticket for any listed asset also covers the key asset | e.g. a vendor-portal session lands on the engineering workstation |
| `limits` | parameter -> [min, max] engineering limits | "beyond limits" signal |
| `routine` | `sources`, `operators`, `max_delta` | an operator nudge of at most `max_delta` from those sources is baseline |
| `sensitive_files` | substrings of file paths | credential-file access signal |

What it deliberately does **not** contain: ground truth, verdict thresholds or weights. The weights are in `core/evidence.py`; they are
hand-set and documented as such (docs/LIMITATIONS.md). Changing them is a code change, and changes after a benchmark freeze must be logged.

## Tuning checklist for a pilot

1. List your real accounts; mark default and shared ones. Unknown accounts are treated as unauthorised.
2. Fill `roles` from your access-control policy, not from what people currently do.
3. Set `limits` from your engineering documents.
4. Export tickets with the approved value in `approved_values`; without it, "change beyond the approved value" cannot be detected.
5. Run on a month of **historical** alerts and compare with analyst decisions before anyone relies on it.
