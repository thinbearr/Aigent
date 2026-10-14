import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import gateway, sim  # noqa: E402
from app.evaluate import evaluate  # noqa: E402
from app.investigate import Run, red_assessment, run_investigation  # noqa: E402


def run(sid, critic):
    r = Run("t", sim.SCENARIOS[sid], critic=critic, delay=0)
    run_investigation(r)
    return r


def test_full_system_gets_every_scenario_right():
    for sid, scn in sim.SCENARIOS.items():
        assert run(sid, True).verdict == scn["truth"]["incident"], sid


def test_without_critic_benign_lookalikes_are_false_positives():
    # The point of the Critic: single-pass analysis flags both benign scenarios.
    assert run("S2", False).verdict is True
    assert run("S4", False).verdict is True
    assert run("S2", True).verdict is False
    assert run("S4", True).verdict is False


def test_attacks_detected_with_and_without_critic():
    for sid in ("S1", "S3", "S5"):
        assert run(sid, False).verdict is True
        assert run(sid, True).verdict is True


def test_critic_overturns_wrong_verdict_and_says_so():
    r = run("S2", True)
    assert any(s["data"].get("overturned") for s in r.steps if s["kind"] == "challenge")


def test_report_cites_evidence_for_every_timeline_row():
    r = run("S1", True)
    assert r.report["timeline"] and all(t["evidence"] for t in r.report["timeline"])
    assert r.report["mitre"], "attack should map to ATT&CK for ICS techniques"
    assert run("S2", True).report["mitre"] == []


def test_gateway_denies_out_of_scope_actions():
    audit = gateway.probe()
    assert [a["status"] for a in audit] == ["DENIED"] * 4


def test_critic_and_orchestrator_have_no_tool_access():
    r = run("S1", True)
    tool_agents = {s["agent"] for s in r.steps if s["kind"] == "tool"}
    assert tool_agents <= {"Blue", "Forensics"}


def test_red_assessment_is_read_only_and_finds_poland_style_weaknesses():
    out = red_assessment()
    assert {f["setting"] for f in out["findings"]} >= {"mfa_enabled", "default_credentials", "firmware_signing_enforced"}
    assert all(a["status"] == "ALLOWED" for a in out["audit"])


def test_evaluation_table():
    ev = evaluate()
    assert ev["summary"]["D"]["accuracy"] == "5/5"
    assert ev["summary"]["C"]["false_positives"] == "2/2"
    assert ev["summary"]["D"]["false_positives"] == "0/2"
