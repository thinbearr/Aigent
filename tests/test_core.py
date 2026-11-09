from pathlib import Path

from cyberarena import adapters
from cyberarena.core import engine, gateway, report, site as sitemod
from cyberarena.core.tickets import TicketStore

ROOT = Path(__file__).resolve().parent.parent
SITE = sitemod.load(ROOT / "config" / "site.example.yaml")


def _triage(events_file, tickets_file=None, critic=True):
    raws = adapters.load_events(ROOT / "examples" / events_file)
    tickets = adapters.load_tickets(ROOT / "examples" / tickets_file) if tickets_file else TicketStore()
    wins = engine.alert_windows(engine.normalise(SITE, raws))
    return [engine.investigate_case(SITE, tickets, w["events"], critic=critic, alert=w["alert"]) for w in wins]


def test_example_triage_clears_ticketed_change_and_flags_the_vendor_chain():
    runs = _triage("events.csv", "tickets.csv")
    assert [r.verdict for r in runs] == [False, True]


def test_without_the_ticket_the_same_change_looks_worse():
    with_t = _triage("events.csv", "tickets.csv")[0].report
    without = _triage("events.csv", None)[0].report
    assert any(i["code"] == "maintenance_none" for i in without["evidence"])
    assert without["confidence"] > with_t["confidence"] + 0.3


def test_every_conclusion_links_to_evidence_and_report_renders():
    run = _triage("events.csv", "tickets.csv")[1]
    assert run.report["evidence"] and all(i["text"] for i in run.report["evidence"])
    assert all(t["evidence"] for t in run.report["timeline"])
    assert "Tool-call audit" in report.to_markdown(run)


def test_gateway_is_read_only_and_enforces_allow_list_and_scope():
    g = gateway.Gateway(SITE, TicketStore(), [])
    tools = {n[3:] for n in dir(g) if n.startswith("_t_")}
    assert tools and all(t.startswith(("get_", "query_", "check_")) for t in tools)      # no write-style tool exists
    for allowed in gateway.ALLOWED.values():
        assert allowed <= tools
    assert g.call("Critic", "query_events")[1]["status"] == "DENIED"
    assert g.call("Blue", "write_plc_config", asset="plc-01")[1]["status"] == "DENIED"
    assert g.call("Blue", "get_asset_info", asset="8.8.8.8")[1]["status"] == "DENIED"
    assert g.call("Blue", "get_asset_info", asset="plc-01")[1]["status"] == "ALLOWED"
    assert len(g.audit) == 4                                                              # denied calls are audited too


def test_normaliser_mfa_and_external_logic():
    raws = adapters.load_events(ROOT / "examples" / "events.csv")
    ev = {e["id"]: e for e in engine.normalise(SITE, raws)}
    login = next(e for e in ev.values() if e["kind"] == "auth" and e["user"] == "vendor.svc")
    assert login["attrs"]["external"] and not login["attrs"]["mfa"] and not login["attrs"]["baseline"]
    routine = next(e for e in ev.values() if e["user"] == "a.kulkarni")
    assert routine["attrs"]["baseline"] is True


def test_events_never_carry_ground_truth_fields():
    bad = {"truth", "is_attack", "ground_truth", "label"}
    for e in engine.normalise(SITE, adapters.load_events(ROOT / "examples" / "events.csv")):
        assert not bad & (set(e) | set(e["attrs"]))


def test_site_roles_and_zones():
    assert SITE.is_external("203.0.113.47") and not SITE.is_external("10.30.0.21")
    assert SITE.host_of_ip("10.10.0.11") == "plc-01"
    assert SITE.deep("plc-01") and not SITE.deep("erp-01")
    assert SITE.within_limits("temp_sp", 93) is False
