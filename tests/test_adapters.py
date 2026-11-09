import json

import pytest

from cyberarena import adapters
from cyberarena.adapters import tickets as tk


def test_csv_aliases_and_typing(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("timestamp,device,action,user,src,result,tag,new\n2026-01-01 10:00:00,plc-01,setpoint_change,a,10.1.1.1,ok,temp_sp,74\n")
    (e,) = adapters.load_events(p)
    assert e.host == "plc-01" and e.actor == "a" and e.src_ip == "10.1.1.1" and e.outcome == "success"
    assert e.detail == {"tag": "temp_sp", "new": 74}


def test_event_type_map_and_columns(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("when,box,what\n2026-01-01T10:00:00Z,plc-01,WRITE_REG\n")
    (e,) = adapters.load_events(p, mapping={"columns": {"ts": "when", "host": "box", "event_type": "what"}, "event_type_map": {"WRITE_REG": "modbus_write"}})
    assert e.event_type == "modbus_write"


def test_jsonl_and_json(tmp_path):
    row = dict(ts="2026-01-01T10:00:00+00:00", host="h", event_type="login_failure", actor="x", detail={"reason": "bad"})
    (tmp_path / "a.jsonl").write_text(json.dumps(row) + "\n")
    (tmp_path / "a.json").write_text(json.dumps({"events": [row]}))
    assert adapters.load_events(tmp_path / "a.jsonl")[0].detail["reason"] == "bad"
    assert adapters.load_events(tmp_path / "a.json")[0].actor == "x"


def test_syslog_default_and_custom_rules(tmp_path):
    p = tmp_path / "s.log"
    p.write_text("Mar  2 09:00:01 eng-ws-01 sshd[123]: Accepted password for s.iyer from 10.30.0.5 port 22\n"
                 "Mar  2 09:01:00 eng-ws-01 sshd[123]: Failed password for root from 203.0.113.9 port 22\n"
                 "<14>1 2026-03-02T09:05:00Z plc-01 ctl - - - Setpoint temp_sp changed from 72 to 74 by s.iyer\n"
                 "garbage line\n")
    m = {"syslog_rules": [{"match": r"Setpoint (?P<tag>\w+) changed from (?P<old>[\d.]+) to (?P<new>[\d.]+) by (?P<actor>\S+)",
                           "event_type": "setpoint_change", "source": "plc"}], "year": 2026}
    ev = adapters.load_events(p, mapping=m)
    assert [e.event_type for e in ev] == ["login_success", "login_failure", "setpoint_change"]
    assert ev[1].outcome == "failure" and ev[2].detail["new"] == "74"


def test_tickets_csv_and_xlsx_and_value_parsing(tmp_path):
    assert tk.parse_values("temp_sp<=74; HEATER_GAIN=0.07") == {"temp_sp": 74.0, "HEATER_GAIN": 0.07}
    assert tk.parse_values('{"a": 1}') == {"a": 1.0}
    csvp = tmp_path / "t.csv"
    csvp.write_text("ticket,asset,engineer,start,end,approved_values\nWO1,plc-01,s.iyer,2026-03-02 09:00,2026-03-02 10:00,temp_sp=74\n")
    t = adapters.load_tickets(csvp).tickets[0]
    assert t.id == "WO1" and t.approved == {"temp_sp": 74.0} and t.valid
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Ticket", "Asset", "Assigned_To", "Start", "End", "Status"])
    ws.append(["WO2", "plc-01", "k.desai", "2026-03-02 09:00:00", "2026-03-02 10:00:00", "closed"])
    xp = tmp_path / "t.xlsx"
    wb.save(xp)
    assert adapters.load_tickets(xp).tickets[0].assigned_to == "k.desai"


def test_ticket_row_missing_column_is_an_error(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("ticket,asset\nWO1,plc-01\n")
    with pytest.raises(ValueError):
        adapters.load_tickets(p)
