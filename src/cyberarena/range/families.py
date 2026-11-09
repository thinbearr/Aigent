"""The scenario set: 32 families (16 attack, 16 benign), each a function of a seeded RNG.

FROZEN BEFORE THE FIRST BENCHMARK RUN. The SHA-256 of this file is recorded in paper/scenario_freeze.txt before any
result was produced; the benchmark report prints the hash it ran with. Do not edit families after seeing results
without recording a new freeze (and saying so in the paper).

A family drives the Kaveri range through the same entry points an operator, engineer or attacker would use
(Modbus writes, logic downloads, logins, work orders), so the evidence has the same form as organic activity.
Each seed varies actors, values, ticket limits and the amount of background activity.
Hard cases are marked `hard=True`: an approved change that looks like an attack, ticket abuse, a borrowed ticket,
a change beyond the approved value, an expired ticket, a ticket for the wrong asset.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

from .kaveri import flags, runtime
from .kaveri.db import session_scope
from .kaveri.events import emit
from .kaveri.models import WorkOrder, utcnow
from .kaveri.plant.sim import DEFAULT_PROGRAM, plant
from .kaveri.scenarios import _ext_ip
from .kaveri.topology import ip_of


@dataclass
class Family:
    key: str
    name: str
    attack: bool
    hard: bool
    description: str
    run: Callable
    techniques: tuple = ()
    flags: dict | None = None          # breach-point overrides applied for this family


REGISTRY: dict[str, Family] = {}


def family(key, name, attack, hard, description, techniques=(), flags_=None):
    def deco(fn):
        REGISTRY[key] = Family(key, name, attack, hard, description, fn, tuple(techniques), flags_)
        return fn
    return deco


# ───────────────────────────────────────────────────────────────── helpers
def wo(asset, change_type, planned, assigned, requested, approver, desc, start_min=-5, end_min=60):
    now = utcnow()
    with session_scope() as s:
        last = s.query(WorkOrder).order_by(WorkOrder.id.desc()).first()
        num = str(int(last.number) + 1) if last else "80004420"
        s.add(WorkOrder(number=num, asset=asset, description=desc, change_type=change_type, planned_change=planned, status="approved",
                        requested_by=requested, assigned_to=assigned, approved_by=approver,
                        window_start=now + timedelta(minutes=start_min), window_end=now + timedelta(minutes=end_min)))
    emit(source="erp", host="erp-01", event_type="work_order_approved", actor=approver, src_ip="10.40.1.12", protocol="https",
         number=num, asset=asset, change_type=change_type)
    return num


def write_sp(value, src_host, actor, tag_reg=0, scale=10):
    return plant.write(1, "hr", tag_reg, [int(round(value * scale))], {"src_ip": ip_of(src_host), "actor": actor, "protocol": "modbus/tcp", "function_code": 6})


def download(gain, src_host, actor, comment=""):
    src = DEFAULT_PROGRAM.replace("HEATER_GAIN       : REAL := 0.08;", f"HEATER_GAIN       : REAL := {gain};")
    return plant.download_program(src, {"src_ip": ip_of(src_host), "actor": actor, "comment": comment})


def vendor_login(mfa):
    ip = _ext_ip("vendor.svc")
    if mfa:
        emit(source="auth", host="portal-01", event_type="mfa_challenge", actor="vendor.svc", src_ip=ip, protocol="https", outcome="info", method="remote")
    emit(source="auth", host="portal-01", event_type="login_success", actor="vendor.svc", src_ip=ip, protocol="https", outcome="success",
         method="remote", session_host="eng-ws-01")
    emit(source="host", host="eng-ws-01", event_type="remote_session_start", actor="vendor.svc", src_ip=ip_of("portal-01"), protocol="rdp",
         outcome="success", origin_ip=ip)
    return ip


# ───────────────────────────────────────────────────────────────── ATTACKS
@family("A01", "Vendor login without MFA", True, False, "Reused vendor credentials open a remote session; sometimes preceded by a probe.",
        ["T0886", "T0859"])
def a01(rng):
    ip = _ext_ip("vendor.svc")
    if rng.random() < 0.5:
        emit(source="network", host="portal-01", event_type="port_scan", src_ip=ip, protocol="tcp", outcome="info", severity="low", ports=[443])
    vendor_login(mfa=False)


@family("A02", "Credentials file then script", True, False, "A credentials file is read and an unexpected script runs on the engineering host.", ["T0853", "T0859"])
def a02(rng):
    actor = rng.choice(["eng.svc", "s.iyer"])
    emit(source="host", host="eng-ws-01", event_type="file_read", actor=actor, src_ip=ip_of("eng-ws-01"), protocol="ssh",
         path="/Projects/Line2_MixTank/project_config.ini")
    emit(source="host", host="eng-ws-01", event_type="process_exec", actor=actor, src_ip=ip_of("eng-ws-01"), process="python plc_connect.py",
         note="unexpected engineering script execution")


@family("A03", "Historian pivot", True, False, "Office-side default login on the dual-homed historian, then control-subnet enumeration.", ["T0840"])
def a03(rng):
    office = f"10.40.1.{rng.randint(60, 99)}"
    emit(source="auth", host="historian-01", event_type="login_success", actor="historian.local", src_ip=office, protocol="https", method="historian-local")
    plant.read(1, "ir", 0, 5, {"src_ip": ip_of("historian-01"), "actor": "historian.local", "protocol": "modbus/tcp", "force_fw_log": True})
    emit(source="network", host="fw-02", event_type="network_enumeration", src_ip=ip_of("historian-01"), protocol="modbus/tcp", outcome="info",
         severity="moderate")


@family("A04", "Unapproved logic download", True, False, "A logic change is pushed to the PLC with no ticket.", ["T0889"])
def a04(rng):
    download(round(rng.uniform(0.15, 0.4), 2), "eng-ws-01", rng.choice(["attacker", "eng.svc"]), "unscheduled change")


@family("A05", "Lateral movement chain", True, False, "Remote login, historian pivot, then a control-network write from the historian.", ["T0859", "T0886", "T0831"])
def a05(rng):
    a01(rng)
    a03(rng)
    plant.write(1, "hr", 0, [int(rng.uniform(86, 93) * 10)], {"src_ip": ip_of("historian-01"), "actor": "vendor.svc", "protocol": "modbus/tcp",
                "function_code": 6, "force_fw_log": True})


@family("A06", "Direct setpoint manipulation", True, False, "An unknown account drives the temperature setpoint out of limits.", ["T0836", "T0831"])
def a06(rng):
    write_sp(rng.uniform(86, 95), "eng-ws-01", rng.choice(["attacker", "eng.svc"]))


@family("A07", "SIS bypass over the network", True, False, "The safety bypass bit is set over Modbus, then the setpoint is pushed.", ["T0880", "T0831"])
def a07(rng):
    ctx = {"src_ip": ip_of("hmi-01"), "actor": "attacker", "protocol": "modbus/tcp", "function_code": 5}
    plant.write(2, "coil", 0, [1], ctx)
    write_sp(rng.uniform(88, 94), "hmi-01", "attacker")


@family("A08", "Change beyond the approved value", True, True,
        "An authorised engineer with a valid ticket for temp_sp<=T writes a value above T (sometimes still inside engineering limits).", ["T0836"])
def a08(rng):
    t = rng.choice([74, 75, 76, 78])
    wo("plc-01", "parameter", {"tag": "temp_sp", "from": 72, "to": t}, "s.iyer", "k.desai", "r.mehta", "Scheduled temperature trim")
    write_sp(rng.uniform(t + 4, 93), rng.choice(["eng-ws-01", "hmi-01"]), "s.iyer")


@family("A09", "Borrowed ticket", True, True, "A technician with no PLC rights writes a value inside another engineer's approved window.", ["T0859", "T0836"])
def a09(rng):
    t = rng.choice([74, 76, 78])
    wo("plc-01", "parameter", {"tag": "temp_sp", "from": 72, "to": t}, "s.iyer", "k.desai", "r.mehta", "Scheduled temperature trim")
    write_sp(rng.uniform(72.5, t), "eng-ws-01", rng.choice(["k.desai", "a.kulkarni"]))


@family("A10", "Logic change beyond the ticket", True, True, "A logic ticket approves HEATER_GAIN<=0.07; the engineer downloads a much larger gain.", ["T0889"])
def a10(rng):
    wo("plc-01", "logic", {"parameter": "HEATER_GAIN", "from": 0.08, "to": 0.07}, "s.iyer", "s.iyer", "r.mehta", "Retune heater gain")
    download(round(rng.uniform(0.15, 0.3), 2), "eng-ws-01", "s.iyer", "retune")


@family("A11", "Expired ticket", True, True, "The engineer's ticket window closed hours ago; the same change is made now.", ["T0836"])
def a11(rng):
    wo("plc-01", "parameter", {"tag": "temp_sp", "from": 72, "to": 78}, "s.iyer", "k.desai", "r.mehta", "Scheduled temperature trim",
       start_min=-300, end_min=-200)
    write_sp(rng.uniform(74, 78), "eng-ws-01", "s.iyer")


@family("A12", "Ticket for the wrong asset", True, True, "The engineer holds a ticket for the PLC but sets the safety bypass over the network.", ["T0880"])
def a12(rng):
    wo("plc-01", "parameter", {"tag": "temp_sp", "from": 72, "to": 74}, "s.iyer", "k.desai", "r.mehta", "Scheduled temperature trim")
    plant.write(2, "coil", 0, [1], {"src_ip": ip_of("eng-ws-01"), "actor": "s.iyer", "protocol": "modbus/tcp", "function_code": 5})


@family("A13", "MFA login without a ticket", True, True, "The vendor session passes MFA (stolen phone) but there is no work order; the program is read and replaced.", ["T0859", "T0889"])
def a13(rng):
    vendor_login(mfa=True)
    plant.upload_program({"src_ip": ip_of("eng-ws-01"), "actor": "vendor.svc"})
    download(round(rng.uniform(0.12, 0.3), 2), "eng-ws-01", "vendor.svc", "diagnostics")


@family("A14", "Recon and credential guessing", True, False, "An external scan followed by failed logins. Nothing succeeds: an attempt.", ["T0846", "T0859"])
def a14(rng):
    ip = _ext_ip("vendor.svc")
    emit(source="network", host="portal-01", event_type="port_scan", src_ip=ip, protocol="tcp", outcome="info", severity="low", ports=[443, 3389])
    for _ in range(rng.randint(3, 6)):
        emit(source="auth", host="portal-01", event_type="login_failure", actor="vendor.svc", src_ip=ip, protocol="https", outcome="failure",
             severity="low", reason="bad password", method="remote")


@family("A15", "Blocked logic download (hardened)", True, True, "The PLC refuses an unapproved download: an attempt that was stopped.", ["T0889"],
        flags_={"B7": "patched", "B8": "vulnerable"})
def a15(rng):
    download(round(rng.uniform(0.15, 0.4), 2), "eng-ws-01", rng.choice(["attacker", "eng.svc"]), "unscheduled change")


@family("A16", "External Modbus client", True, False, "A client from outside writes a coil on the PLC.", ["T0836"])
def a16(rng):
    ip = rng.choice(["203.0.113.47", "198.51.100.23", "185.220.101.9"])
    emit(source="network", host="plc-01", event_type="tcp_session_open", src_ip=ip, protocol="modbus/tcp", outcome="info", dst_port=502)
    plant.write(1, "coil", rng.choice([0, 1, 2]), [0], {"src_ip": ip, "actor": None, "protocol": "modbus/tcp", "function_code": 5, "force_fw_log": True})


# ───────────────────────────────────────────────────────────────── BENIGN
@family("B01", "Approved setpoint change", False, True, "An engineer changes temp_sp within an approved ticket (looks like A08/A09 to a rule).")
def b01(rng):
    t = rng.choice([74, 75, 76, 78])
    wo("plc-01", "parameter", {"tag": "temp_sp", "from": 72, "to": t}, "s.iyer", "k.desai", "r.mehta", "Scheduled temperature trim")
    write_sp(rng.uniform(72.5, t), rng.choice(["hmi-01", "eng-ws-01"]), "s.iyer")


@family("B02", "Vendor support under a ticket", False, True, "The integrator passes MFA under an approved work order and reads the program.")
def b02(rng):
    wo("plc-01", "none", {}, "vendor.svc", "k.desai", "r.mehta", "Warranty diagnostics on PLC-1", end_min=120)
    vendor_login(mfa=True)
    plant.upload_program({"src_ip": ip_of("eng-ws-01"), "actor": "vendor.svc"})


@family("B03", "Approved logic change", False, True, "A logic ticket approves HEATER_GAIN<=g; the engineer downloads exactly that.")
def b03(rng):
    g = rng.choice([0.06, 0.07, 0.075])
    wo("plc-01", "logic", {"parameter": "HEATER_GAIN", "from": 0.08, "to": g}, "s.iyer", "s.iyer", "r.mehta", "Retune heater gain")
    download(round(rng.uniform(g - 0.01, g), 3), "eng-ws-01", "s.iyer", "retune")


@family("B04", "Routine operator nudge", False, False, "The operator trims the setpoint by half a degree, as every shift.")
def b04(rng):
    for _ in range(rng.randint(1, 3)):
        cur = plant.snapshot()["temp_sp"]
        write_sp(min(78, max(68, cur + rng.choice([-0.5, 0.5]))), "hmi-01", "p.nair")


@family("B05", "Authorised safety bypass", False, True, "An engineer sets and clears the SIS bypass with the key switch under a safety ticket.")
def b05(rng):
    wo("sis-01", "safety_interlock", {"tag": "sis_bypass", "from": 0, "to": 1}, "s.iyer", "s.iyer", "r.mehta", "Calibrate trip transmitter", end_min=30)
    ctx = {"src_ip": ip_of("hmi-01"), "actor": "s.iyer", "protocol": "modbus/tcp", "function_code": 5, "key_switch": True}
    plant.write(2, "coil", 0, [1], ctx)
    plant.write(2, "coil", 0, [0], ctx)


@family("B06", "Change at the ticket limit", False, True, "The written value equals the approved maximum exactly.")
def b06(rng):
    t = rng.choice([74, 76, 78])
    wo("plc-01", "parameter", {"tag": "temp_sp", "from": 72, "to": t}, "s.iyer", "k.desai", "r.mehta", "Scheduled temperature trim")
    write_sp(t, "eng-ws-01", "s.iyer")


@family("B07", "Second ticket is the valid one", False, True, "Two tickets exist for the PLC; the engineer acts under the one assigned to them.")
def b07(rng):
    wo("plc-01", "parameter", {"tag": "temp_sp", "from": 72, "to": 70}, "k.desai", "r.mehta", "r.mehta", "Lower setpoint for cleaning")
    t = rng.choice([75, 77])
    wo("plc-01", "parameter", {"tag": "temp_sp", "from": 72, "to": t}, "s.iyer", "k.desai", "r.mehta", "Scheduled temperature trim")
    write_sp(rng.uniform(72.5, t), "eng-ws-01", "s.iyer")


@family("B08", "Engineer program backup", False, False, "An engineer reads the controller program for a backup. No ticket needed for a read.")
def b08(rng):
    plant.upload_program({"src_ip": ip_of("eng-ws-01"), "actor": rng.choice(["s.iyer", "eng.svc"])})


@family("B09", "Scheduled network scan", False, False, "IT runs an inventory scan of the control subnet inside a ticketed window.")
def b09(rng):
    wo("fw-02", "none", {}, "m.rao", "m.rao", "r.mehta", "Quarterly asset inventory scan", end_min=90)
    emit(source="network", host="fw-02", event_type="network_enumeration", src_ip="10.40.1.12", protocol="modbus/tcp", outcome="info", severity="moderate")


@family("B10", "Quiet shift", False, False, "Only routine background activity. A control: no alert expected.")
def b10(rng):
    runtime.organic_burst(rng.randint(4, 9))


@family("B11", "Operator typo then login", False, False, "Two failed logins from the HMI, then success.")
def b11(rng):
    for _ in range(rng.randint(1, 2)):
        emit(source="auth", host="erp-01", event_type="login_failure", actor="p.nair", src_ip=ip_of("hmi-01"), protocol="https", outcome="failure",
             severity="low", reason="bad password", method="corp")
    emit(source="auth", host="erp-01", event_type="login_success", actor="p.nair", src_ip=ip_of("hmi-01"), protocol="https", outcome="success", method="corp")


@family("B12", "Vendor logic change under a ticket", False, True, "A vendor with MFA and a logic ticket downloads a change within the approved gain.")
def b12(rng):
    g = rng.choice([0.06, 0.07])
    wo("plc-01", "logic", {"parameter": "HEATER_GAIN", "from": 0.08, "to": g}, "vendor.svc", "s.iyer", "r.mehta", "Vendor retune", end_min=120)
    vendor_login(mfa=True)
    download(g, "eng-ws-01", "vendor.svc", "vendor retune")


@family("B13", "Work-order approvals only", False, False, "A supervisor approves tickets; nothing touches the plant.")
def b13(rng):
    wo("plc-01", "parameter", {"tag": "temp_sp", "from": 72, "to": 75}, "s.iyer", "k.desai", "r.mehta", "Scheduled temperature trim", start_min=600, end_min=700)


@family("B14", "Approved conveyor change", False, True, "A ticket approves conveyor_sp<=1.2; the engineer sets 1.1 from the HMI.")
def b14(rng):
    wo("plc-01", "parameter", {"tag": "conveyor_sp", "from": 1.0, "to": 1.2}, "s.iyer", "k.desai", "r.mehta", "Raise line speed slightly")
    plant.write(1, "hr", 1, [int(rng.uniform(1.05, 1.2) * 100)], {"src_ip": ip_of("hmi-01"), "actor": "s.iyer", "protocol": "modbus/tcp", "function_code": 6})


@family("B15", "Approved change then revert", False, True, "A ticketed change followed by a revert to the old value.")
def b15(rng):
    t = rng.choice([74, 76])
    wo("plc-01", "parameter", {"tag": "temp_sp", "from": 72, "to": t}, "s.iyer", "k.desai", "r.mehta", "Trial setpoint")
    write_sp(t, "eng-ws-01", "s.iyer")
    write_sp(72, "eng-ws-01", "s.iyer")


@family("B16", "Planner order release", False, False, "Planning releases production orders and logs in from the office.")
def b16(rng):
    for _ in range(rng.randint(2, 4)):
        emit(source="erp", host="erp-01", event_type="production_order_released", actor="a.kulkarni", src_ip="10.40.1.11", protocol="https")
    emit(source="auth", host="erp-01", event_type="login_success", actor="a.kulkarni", src_ip="10.40.1.11", protocol="https", method="corp")
