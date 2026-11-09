"""Slow: drives the real Kaveri range. Checks the benign twin is cleared and the attack twin is flagged by D."""
import json

import pytest

pytest.importorskip("fastapi")

from cyberarena.bench import runner  # noqa: E402
from cyberarena.core import engine, site as sitemod, systems  # noqa: E402
from cyberarena.range import families, generate  # noqa: E402


@pytest.fixture(scope="module")
def cases(tmp_path_factory):
    out = tmp_path_factory.mktemp("cases")
    generate.generate(out, seeds=[1], keys=["A08", "B01", "A04", "B03", "B10"], db_path=str(out / "r.db"), progress=lambda m: None)
    return out


def test_registry_has_32_families_16_each():
    reg = families.REGISTRY
    assert len(reg) == 32 and sum(f.attack for f in reg.values()) == 16


def test_cases_contain_events_tickets_and_separate_truth(cases):
    d = cases / "seed-1" / "A08"
    assert (d / "events.jsonl").exists() and (d / "tickets.csv").exists()
    assert json.loads((d / "truth.json").read_text())["attack"] is True
    assert "attack" not in (d / "events.jsonl").read_text()          # truth is not smuggled into the evidence


@pytest.mark.parametrize("fam,attack", [("A08", True), ("B01", False), ("A04", True), ("B03", False)])
def test_critic_separates_twins(cases, fam, attack):
    site = sitemod.load(runner.KAVERI_SITE)
    events, tickets = runner.load_case(cases / "seed-1" / fam, site)
    assert systems.system_D(site, tickets, events, engine.build_alert(events))["incident"] is attack


def test_rule_detector_flags_the_benign_twin(cases):
    site = sitemod.load(runner.KAVERI_SITE)
    events, tickets = runner.load_case(cases / "seed-1" / "B01", site)
    assert systems.system_A(site, tickets, events, engine.build_alert(events))["incident"] is True
