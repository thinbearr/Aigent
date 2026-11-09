# Where each system fails

Every misclassified case, by system. 'FN' = missed attack, 'FP' = false alarm.

## A Rule-based detector: 55 of 160 cases wrong

- **B01 Approved setpoint change** (FP, seeds 1, 2, 3, 4, 5; 5 wrong)
- **B02 Vendor support under a ticket** (FP, seeds 1, 2, 3, 4, 5; 5 wrong)
- **B03 Approved logic change** (FP, seeds 1, 2, 3, 4, 5; 5 wrong)
- **B05 Authorised safety bypass** (FP, seeds 1, 2, 3, 4, 5; 5 wrong)
- **B06 Change at the ticket limit** (FP, seeds 1, 2, 3, 4, 5; 5 wrong)
- **B07 Second ticket is the valid one** (FP, seeds 1, 2, 3, 4, 5; 5 wrong)
- **B08 Engineer program backup** (FP, seeds 1, 2, 3, 4, 5; 5 wrong)
- **B09 Scheduled network scan** (FP, seeds 1, 2, 3, 4, 5; 5 wrong)
- **B12 Vendor logic change under a ticket** (FP, seeds 1, 2, 3, 4, 5; 5 wrong)
- **B14 Approved conveyor change** (FP, seeds 1, 2, 3, 4, 5; 5 wrong)
- **B15 Approved change then revert** (FP, seeds 1, 2, 3, 4, 5; 5 wrong)

## C Agents without Critic: 35 of 160 cases wrong

- **A15 Blocked logic download (hardened)** (FN, seeds 1, 2, 3, 4, 5; 5 wrong) - confidence 0.57 - evidence: new_network_path(+0.7), blocked_attempt(+1.0)
- **B01 Approved setpoint change** (FP, seeds 1, 2, 3, 4, 5; 5 wrong) - confidence 0.62 - evidence: new_network_path(+0.7), plc_config_change(+1.5)
- **B03 Approved logic change** (FP, seeds 1, 2, 3, 4, 5; 5 wrong) - confidence 0.65 - evidence: new_network_path(+0.7), plc_logic_change(+1.8)
- **B06 Change at the ticket limit** (FP, seeds 1, 2, 3, 4, 5; 5 wrong) - confidence 0.62 - evidence: new_network_path(+0.7), plc_config_change(+1.5)
- **B07 Second ticket is the valid one** (FP, seeds 1, 2, 3, 4, 5; 5 wrong) - confidence 0.62 - evidence: new_network_path(+0.7), plc_config_change(+1.5)
- **B12 Vendor logic change under a ticket** (FP, seeds 1, 2, 3, 4, 5; 5 wrong) - confidence 0.65 - evidence: new_network_path(+0.7), plc_logic_change(+1.8)
- **B15 Approved change then revert** (FP, seeds 1, 2, 3, 4, 5; 5 wrong) - confidence 0.75 - evidence: new_network_path(+0.7), plc_config_change(+1.5), plc_config_change(+1.5)

## D Agents with Critic: 7 of 160 cases wrong

- **A15 Blocked logic download (hardened)** (FN, seeds 4; 1 wrong) - confidence 0.59 - evidence: new_network_path(+0.7), blocked_attempt(+1.0), maintenance_none(+1.2), user_authorized(-1.0)
- **B01 Approved setpoint change** (FP, seeds 5; 1 wrong) - confidence 0.71 - evidence: new_network_path(+0.7), plc_config_change(+1.5), maintenance_match(-3.0), user_authorized_ticket(-3.0), scope_exceeded(+7.0)
- **B07 Second ticket is the valid one** (FP, seeds 1, 2, 3, 4, 5; 5 wrong) - confidence 0.75 - evidence: new_network_path(+0.7), plc_config_change(+1.5), ticket_not_holder(+0.5), user_authorized_ticket(-3.0), scope_exceeded(+4.0)
