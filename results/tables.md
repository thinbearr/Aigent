# Benchmark results

160 cases = 16 attack and 16 benign scenario families x 5 seeds (1, 2, 3, 4, 5). Positive class = attack. Cases come from the simulated Kaveri range, not from a real plant.

## Main table (all cases)

| System | n | Accuracy (95% CI) | Recall (95% CI) | False-alarm rate (95% CI) | Precision | F1 | Unparsed |
|---|---|---|---|---|---|---|---|
| A Rule-based detector | 160 | 66% (58%-73%) | 100% (95%-100%) | 69% (58%-78%) | 59% | 0.74 | 0 |
| C Agents without Critic | 160 | 78% (71%-84%) | 94% (86%-97%) | 38% (28%-48%) | 71% | 0.81 | 0 |
| D Agents with Critic | 160 | 96% (91%-98%) | 99% (93%-100%) | 8% (3%-15%) | 93% | 0.96 | 0 |

## Hard cases only

(approved change that looks like an attack, ticket abuse, borrowed ticket, change beyond the approved value, expired ticket, wrong-asset ticket)

| System | n | Accuracy (95% CI) | Recall (95% CI) | False-alarm rate (95% CI) | Precision | F1 | Unparsed |
|---|---|---|---|---|---|---|---|
| A Rule-based detector | 80 | 44% (33%-55%) | 100% (90%-100%) | 100% (92%-100%) | 44% | 0.61 | 0 |
| C Agents without Critic | 80 | 56% (45%-67%) | 86% (71%-94%) | 67% (52%-79%) | 50% | 0.63 | 0 |
| D Agents with Critic | 80 | 91% (83%-96%) | 97% (85%-99%) | 13% (6%-26%) | 85% | 0.91 | 0 |

## Easy cases only

| System | n | Accuracy (95% CI) | Recall (95% CI) | False-alarm rate (95% CI) | Precision | F1 | Unparsed |
|---|---|---|---|---|---|---|---|
| A Rule-based detector | 80 | 88% (78%-93%) | 100% (92%-100%) | 29% (16%-45%) | 82% | 0.90 | 0 |
| C Agents without Critic | 80 | 100% (95%-100%) | 100% (92%-100%) | 0% (0%-10%) | 100% | 1.00 | 0 |
| D Agents with Critic | 80 | 100% (95%-100%) | 100% (92%-100%) | 0% (0%-10%) | 100% | 1.00 | 0 |

## Accuracy per seed

| System | seed 1 | seed 2 | seed 3 | seed 4 | seed 5 | mean | bootstrap 95% CI of mean |
|---|---|---|---|---|---|---|---|
| A | 66% | 66% | 66% | 66% | 66% | 65.6% | 66%-66% |
| C | 78% | 78% | 78% | 78% | 78% | 78.1% | 78%-78% |
| D | 97% | 97% | 97% | 94% | 94% | 95.6% | 94%-97% |

## Ablation of the Critic

| System | n | Accuracy (95% CI) | Recall (95% CI) | False-alarm rate (95% CI) | Precision | F1 | Unparsed |
|---|---|---|---|---|---|---|---|
| C Agents without Critic | 160 | 78% (71%-84%) | 94% (86%-97%) | 38% (28%-48%) | 71% | 0.81 | 0 |
| D-maint D without maintenance-window check | 160 | 79% (72%-84%) | 57% (47%-68%) | 0% (0%-5%) | 100% | 0.73 | 0 |
| D-auth D without authorisation check | 160 | 90% (84%-94%) | 100% (95%-100%) | 20% (13%-30%) | 83% | 0.91 | 0 |
| D-scope D without change-scope check | 160 | 95% (90%-97%) | 90% (81%-95%) | 0% (0%-5%) | 100% | 0.95 | 0 |
| D Agents with Critic | 160 | 96% (91%-98%) | 99% (93%-100%) | 8% (3%-15%) | 93% | 0.96 | 0 |

## Significance (exact McNemar, Holm-adjusted)

Pooled = every (family, seed) case is one pair; cases of the same family are correlated, so the family-level columns (majority outcome per family) are the conservative reading.

| Comparison (A vs B) | paired cases | A right / B wrong | A wrong / B right | p (exact McNemar) | p (Holm) | families | A right / B wrong | A wrong / B right | p (family level) | p (Holm) |
|---|---|---|---|---|---|---|---|---|---|---|
| D vs C | 160 | 28 | 0 | 0.0000 | 0.0000 | 32 | 6 | 0 | 0.0312 | 0.1562 |
| D vs A | 160 | 49 | 1 | 0.0000 | 0.0000 | 32 | 10 | 0 | 0.0020 | 0.0117 |
| C vs A | 160 | 25 | 5 | 0.0003 | 0.0010 | 32 | 5 | 1 | 0.2188 | 0.6562 |
| D vs D-maint | 160 | 33 | 6 | 0.0000 | 0.0001 | 32 | 6 | 1 | 0.1250 | 0.5000 |
| D vs D-auth | 160 | 10 | 1 | 0.0117 | 0.0234 | 32 | 2 | 0 | 0.5000 | 1.0000 |
| D vs D-scope | 160 | 7 | 6 | 1.0000 | 1.0000 | 32 | 1 | 1 | 1.0000 | 1.0000 |

## Cost per alert

| System | tool calls / alert | seconds / alert (CPU) | LLM calls / alert | LLM tokens / alert |
|---|---|---|---|---|
| A | 0.0 | 0.000 | 0.0 | 0 |
| C | 5.3 | 0.000 | 0.0 | 0 |
| D | 7.3 | 0.000 | 0.0 | 0 |
| D-maint | 6.1 | 0.000 | 0.0 | 0 |
| D-auth | 6.5 | 0.000 | 0.0 | 0 |
| D-scope | 7.0 | 0.000 | 0.0 | 0 |

## Per family (correct / cases)

| Family | Truth | Hard | Name | A | C | D |
|---|---|---|---|---|---|---|
| A01 | attack |  | Vendor login without MFA | 5/5 | 5/5 | 5/5 |
| A02 | attack |  | Credentials file then script | 5/5 | 5/5 | 5/5 |
| A03 | attack |  | Historian pivot | 5/5 | 5/5 | 5/5 |
| A04 | attack |  | Unapproved logic download | 5/5 | 5/5 | 5/5 |
| A05 | attack |  | Lateral movement chain | 5/5 | 5/5 | 5/5 |
| A06 | attack |  | Direct setpoint manipulation | 5/5 | 5/5 | 5/5 |
| A07 | attack |  | SIS bypass over the network | 5/5 | 5/5 | 5/5 |
| A08 | attack | yes | Change beyond the approved value | 5/5 | 5/5 | 5/5 |
| A09 | attack | yes | Borrowed ticket | 5/5 | 5/5 | 5/5 |
| A10 | attack | yes | Logic change beyond the ticket | 5/5 | 5/5 | 5/5 |
| A11 | attack | yes | Expired ticket | 5/5 | 5/5 | 5/5 |
| A12 | attack | yes | Ticket for the wrong asset | 5/5 | 5/5 | 5/5 |
| A13 | attack | yes | MFA login without a ticket | 5/5 | 5/5 | 5/5 |
| A14 | attack |  | Recon and credential guessing | 5/5 | 5/5 | 5/5 |
| A15 | attack | yes | Blocked logic download (hardened) | 5/5 | 0/5 | 4/5 |
| A16 | attack |  | External Modbus client | 5/5 | 5/5 | 5/5 |
| B01 | benign | yes | Approved setpoint change | 0/5 | 0/5 | 4/5 |
| B02 | benign | yes | Vendor support under a ticket | 0/5 | 5/5 | 5/5 |
| B03 | benign | yes | Approved logic change | 0/5 | 0/5 | 5/5 |
| B04 | benign |  | Routine operator nudge | 5/5 | 5/5 | 5/5 |
| B05 | benign | yes | Authorised safety bypass | 0/5 | 5/5 | 5/5 |
| B06 | benign | yes | Change at the ticket limit | 0/5 | 0/5 | 5/5 |
| B07 | benign | yes | Second ticket is the valid one | 0/5 | 0/5 | 0/5 |
| B08 | benign |  | Engineer program backup | 0/5 | 5/5 | 5/5 |
| B09 | benign |  | Scheduled network scan | 0/5 | 5/5 | 5/5 |
| B10 | benign |  | Quiet shift | 5/5 | 5/5 | 5/5 |
| B11 | benign |  | Operator typo then login | 5/5 | 5/5 | 5/5 |
| B12 | benign | yes | Vendor logic change under a ticket | 0/5 | 0/5 | 5/5 |
| B13 | benign |  | Work-order approvals only | 5/5 | 5/5 | 5/5 |
| B14 | benign | yes | Approved conveyor change | 0/5 | 5/5 | 5/5 |
| B15 | benign | yes | Approved change then revert | 0/5 | 0/5 | 5/5 |
| B16 | benign |  | Planner order release | 5/5 | 5/5 | 5/5 |
