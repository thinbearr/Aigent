# Adapters

Adapters read files and produce **canonical records** (`RawEvent`) and **tickets**. They never connect to anything and never write.

## Events: CSV / JSON / JSONL

Required columns (aliases in brackets, case-insensitive): `ts` [timestamp, time], `host` [asset, device, hostname],
`event_type` [event, action, type]. Optional: `source`, `actor` [user, username], `src_ip` [src], `dst_ip` [dst], `protocol`, `outcome`
[result, status], `severity`, `uid` [id]. **Every other column goes into `detail`**, typed automatically, so `tag`, `old`, `new`, `path`,
`method`, `mfa`, `process`, `changed_parameters`... are all available to the engine. A `detail` column may hold a JSON object.
Naive timestamps are read as UTC. Outcomes `ok/allowed/accepted` become `success`; `denied/drop/refused` become `blocked`.

### The canonical `event_type` vocabulary

The engine reasons about these. Map your own names onto them with `event_type_map` (below).

| event_type | meaning | useful detail fields |
|---|---|---|
| login_success / login_failure | an authentication result | `method` (`remote` for a remote-access gateway, `historian-local`), `mfa`, `reason` |
| mfa_challenge / mfa_failure | MFA step; a challenge shortly before a success marks that login as MFA-protected | |
| remote_session_start | remote desktop session opened on a host | |
| file_read | a file was read | `path` (matched against `sensitive_files` in the site config) |
| process_exec | a process ran | `process`, `suspicious`, `note` |
| port_scan / network_enumeration | scanning | `ports` |
| network_connection / tcp_session_open | a connection across a boundary | `src_host`, `dst_host`, `dst_port`, `rule` |
| modbus_read / modbus_write | controller register access | `tag`, `old`, `new`, `count`, `address` |
| setpoint_change | a controller parameter changed | `tag`, `old`, `new` (or `requested` when refused) |
| program_download / program_upload | controller logic written / read | `changed_parameters` = `{NAME: {old, new}}` |
| sis_bypass_change | safety bypass changed | `old`, `new`, `via` (`network` or `key switch`) |
| sis_trip, range_exceeded, range_restored, alarm_raised, alarm_ack | process state and HMI | `tag`, `value`, `state`, `level` |
| work_order_* | ticket lifecycle noted in the logs (informational) | `number` |

Unknown event types are kept and ignored (they show up as kind `other`).

### Mapping file

```yaml
columns:                 # canonical name -> your column name
  ts: EventTime
  host: Device
  event_type: Action
event_type_map:          # your vocabulary -> canonical
  WRITE_SINGLE_REG: modbus_write
  USER_LOGON_OK: login_success
```
`cyberarena triage --events x.csv --mapping mapping.yaml ...`

## Syslog

RFC 3164, RFC 5424 and `ISO-timestamp host program: message` lines. The message is matched against rules (first match wins) that give
the canonical `event_type`; named groups (`actor`, `src_ip`, `tag`, `old`, `new`...) become fields. `key=value` pairs in the message
are also captured. Defaults cover sshd logins; add your own under `syslog_rules` in the mapping YAML (see `tests/test_adapters.py`).
Lines no rule matches are kept as `syslog` events and ignored by the engine. RFC 3164 lines have no year: set `year:` in the mapping.

## Tickets: CSV / XLSX

Columns: `ticket`, `asset`, `assigned_to`, `start`, `end` (required); `requested_by`, `approved_by`, `change_type`
(`none|parameter|logic|safety_interlock`), `status` (`approved|in_progress|closed` count; `created|rejected` do not),
`description`, `approved_values`. `approved_values` is the **maximum approved value per parameter**, as `temp_sp=74;HEATER_GAIN=0.07`
or a JSON object. Without it the Critic can still check the window and the person, but cannot judge the size of the change.
XLSX needs `pip install cyberarena[xlsx]`; the first sheet is read.

## Not implemented yet (planned)

Zeek / Modbus packet captures, Wazuh, Splunk and Elasticsearch exports. They would be new modules that emit the same `RawEvent`; the engine does not change.
