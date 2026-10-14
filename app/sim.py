"""Simulated industrial plant: assets, topology and scripted scenarios with hidden ground truth.

Everything here is synthetic. No real network traffic is generated or sent anywhere.
"""

ASSETS = {
    "VPN-GW":     dict(label="VPN Gateway",   zone="DMZ",     type="gateway",     x=90, y=100,
                       config=dict(internet_exposed=True, mfa_enabled=False, shared_credentials=True)),
    "WS-ENG-01":  dict(label="Engineering WS", zone="IT",      type="workstation", x=260, y=100,
                       config=dict(mfa_enabled=True)),
    "SERVER-02":  dict(label="App Server",    zone="IT",      type="server",      x=430, y=100,
                       config=dict(mfa_enabled=False)),
    "HMI-01":     dict(label="HMI",           zone="OT",      type="hmi",         x=260, y=215,
                       config=dict(default_admin_password=True)),
    "OT-SERVER":  dict(label="OT Server",     zone="OT",      type="server",      x=430, y=215,
                       config=dict()),
    "PROCESS-01": dict(label="Process",       zone="Process", type="process",     x=90, y=330,
                       config=dict()),
    "PLC-02":     dict(label="PLC-02",        zone="Control", type="plc",         x=260, y=330,
                       config=dict(remote_programming_enabled=True)),
    "RTU-01":     dict(label="RTU-01",        zone="Control", type="rtu",         x=430, y=330,
                       config=dict(default_credentials=True, firmware_signing_enforced=False)),
}
EXTERNAL = dict(label="Internet", x=90, y=34)

EDGES = [("VPN-GW", "WS-ENG-01"), ("WS-ENG-01", "SERVER-02"), ("SERVER-02", "OT-SERVER"),
         ("OT-SERVER", "HMI-01"), ("HMI-01", "PLC-02"), ("OT-SERVER", "RTU-01"), ("PLC-02", "PROCESS-01")]

SANDBOX_ASSETS = set(ASSETS) | {"EXTERNAL"}


def topology():
    return dict(
        assets={k: {kk: vv for kk, vv in v.items() if kk != "config"} for k, v in ASSETS.items()},
        external=EXTERNAL, edges=EDGES)


def _mk(events):
    events = sorted(events, key=lambda e: e["t"])
    for i, e in enumerate(events, 1):
        e["id"] = f"EV-{i:02d}"
        e.setdefault("attrs", {})
        e.setdefault("user", None)
        e.setdefault("src", None)
        e.setdefault("dst", None)
    return events


def E(t, kind, asset, detail, user=None, src=None, dst=None, **attrs):
    return dict(t=t, kind=kind, asset=asset, detail=detail, user=user, src=src, dst=dst, attrs=attrs)


def _s1():
    return dict(
        id="S1", name="Scenario 1 · Anomalous login → PLC parameter change",
        summary="Alert: unusual login on the application server, followed by activity towards the control network.",
        alert=dict(t="14:02:13", asset="SERVER-02", kind="auth",
                   text="Anomalous login: USER-17 from 203.0.113.50 (outside baseline)"),
        events=_mk([
            E("14:02:13", "auth", "SERVER-02", "Login USER-17 from 203.0.113.50: external address, no MFA, outside normal hours",
              user="USER-17", src="EXTERNAL", external=True, mfa=False, baseline=False),
            E("14:02:18", "privilege", "SERVER-02", "USER-17 elevated from standard user to administrator", user="USER-17"),
            E("14:02:40", "process", "SERVER-02", "psexec.exe launched by USER-17 (remote execution tool)",
              user="USER-17", name="psexec.exe", suspicious=True),
            E("14:03:02", "network", "SERVER-02", "SERVER-02 opened SMB (445) session to OT-SERVER; first time on this path",
              src="SERVER-02", dst="OT-SERVER", port=445, baseline=False),
            E("14:03:31", "auth", "HMI-01", "Login USER-17 on HMI-01 via OT-SERVER; account never used in OT before",
              user="USER-17", src="OT-SERVER", external=False, mfa=False, baseline=False),
            E("14:04:17", "config", "PLC-02", "PLC-02 parameter motor_speed_limit changed 1200 → 2400 by USER-17",
              user="USER-17", src="HMI-01", dst="PLC-02", param="motor_speed_limit", old=1200, new=2400),
            E("14:04:21", "process_state", "PROCESS-01", "Motor speed 2300 rpm, above configured limit (1200)",
              param="motor_speed", value=2300, limit=1200, beyond=True),
        ]),
        context=dict(
            maintenance=[],
            users={"USER-17": dict(role="Accounts clerk", authorized=["SERVER-02"], admin=False)},
            firmware={}),
        truth=dict(incident=True, summary="Compromised account used to reach the control network and change a PLC parameter.",
                   path=["EXTERNAL", "SERVER-02", "OT-SERVER", "HMI-01", "PLC-02", "PROCESS-01"]),
    )


def _s2():
    return dict(
        id="S2", name="Scenario 2 · Privilege change → PLC parameter change",
        summary="Alert: a PLC parameter was changed after a privilege change on the engineering workstation.",
        alert=dict(t="14:04:17", asset="PLC-02", kind="config",
                   text="PLC-02 configuration changed: motor_speed_limit 1200 → 1300"),
        events=_mk([
            E("14:02:10", "auth", "WS-ENG-01", "Login USER-23 on WS-ENG-01 (internal, MFA passed, normal hours)",
              user="USER-23", src="SERVER-02", external=False, mfa=True, baseline=True),
            E("14:02:18", "privilege", "WS-ENG-01", "USER-23 elevated from standard user to administrator", user="USER-23"),
            E("14:02:55", "process", "WS-ENG-01", "engineering_suite.exe started by USER-23",
              user="USER-23", name="engineering_suite.exe", suspicious=False),
            E("14:03:20", "network", "WS-ENG-01", "WS-ENG-01 connected to OT-SERVER (engineering protocol); usual path",
              src="WS-ENG-01", dst="OT-SERVER", port=4840, baseline=True),
            E("14:03:50", "auth", "HMI-01", "Login USER-23 on HMI-01 (MFA passed, normal hours)",
              user="USER-23", src="OT-SERVER", external=False, mfa=True, baseline=True),
            E("14:04:17", "config", "PLC-02", "PLC-02 parameter motor_speed_limit changed 1200 → 1300 by USER-23",
              user="USER-23", src="HMI-01", dst="PLC-02", param="motor_speed_limit", old=1200, new=1300),
            E("14:04:21", "process_state", "PROCESS-01", "Motor speed 1290 rpm, within new limit (1300)",
              param="motor_speed", value=1290, limit=1300, beyond=False),
        ]),
        context=dict(
            maintenance=[dict(asset="PLC-02", start="14:00", end="15:00", user="USER-23", ticket="CHG-1042",
                              note="Planned speed-limit adjustment")],
            users={"USER-23": dict(role="Control engineer", authorized=["WS-ENG-01", "OT-SERVER", "HMI-01", "PLC-02"], admin=True)},
            firmware={}),
        truth=dict(incident=False, summary="Authorised change by a control engineer under ticket CHG-1042 in a planned window.",
                   path=[]),
    )


def _s3():
    return dict(
        id="S3", name="Scenario 3 · Loss of RTU comms after VPN activity",
        summary="Alert: RTU-01 lost communication with the grid operator. Other sources show VPN-side activity.",
        alert=dict(t="14:11:40", asset="RTU-01", kind="comms",
                   text="RTU-01 lost communication with DSO (grid operator)"),
        inspired_by="Poland energy-sector attacks, 29 Dec 2025 (CERT Polska, 2026): exposed VPN without MFA, default credentials, corrupted RTU firmware, wiped HMI.",
        events=_mk([
            E("14:05:02", "scan", "VPN-GW", "Port scan from 198.51.100.77 against VPN-GW (312 probes: 443, 22)",
              src="EXTERNAL", count=312),
            E("14:07:30", "auth", "VPN-GW", "VPN login svc-vpn after 14 failed attempts: external, no MFA; same credentials used at other sites",
              user="svc-vpn", src="EXTERNAL", external=True, mfa=False, baseline=False, prior_failures=14),
            E("14:08:10", "config", "VPN-GW", "VPN-GW configuration changed: new administrator account added",
              user="svc-vpn", src="VPN-GW", dst="VPN-GW", param="admin_account", old="-", new="added"),
            E("14:09:45", "network", "VPN-GW", "VPN-GW opened SSH (22) session to RTU-01; first time on this path",
              src="VPN-GW", dst="RTU-01", port=22, baseline=False),
            E("14:10:02", "auth", "RTU-01", "SSH login to RTU-01 as root using the factory default credentials",
              user="root", src="VPN-GW", external=False, mfa=False, baseline=False, default_credentials=True),
            E("14:10:40", "firmware", "RTU-01", "Firmware image uploaded to RTU-01 by root",
              user="root", signed=False, hash_match=False),
            E("14:11:30", "file", "HMI-01", "Unknown binary dynowiper.exe executed on HMI-01; disk contents wiped",
              user="svc-vpn", name="dynowiper.exe", action="wipe"),
            E("14:11:40", "comms", "RTU-01", "RTU-01 lost communication with DSO (ongoing)", peer="DSO", duration="ongoing"),
            E("14:12:05", "reset", "VPN-GW", "VPN-GW factory reset; local logs lost", logs_lost=True),
        ]),
        context=dict(
            maintenance=[],
            users={"svc-vpn": dict(role="Service account (VPN)", authorized=["VPN-GW"], admin=False),
                   "root": dict(role="Device default account", authorized=[], admin=True)},
            firmware={"RTU-01": dict(signed=False, hash_match=False, version="unknown")}),
        truth=dict(incident=True, summary="Destructive attack via exposed VPN and default credentials, with corrupted RTU firmware.",
                   path=["EXTERNAL", "VPN-GW", "RTU-01", "HMI-01"]),
    )


def _s4():
    return dict(
        id="S4", name="Scenario 4 · Loss of RTU comms during firmware activity",
        summary="Alert: RTU-01 lost communication with the grid operator. A remote session to RTU-01 is also visible.",
        alert=dict(t="14:31:20", asset="RTU-01", kind="comms",
                   text="RTU-01 lost communication with DSO (grid operator)"),
        events=_mk([
            E("14:25:00", "auth", "VPN-GW", "VPN login USER-31 (MFA passed, known device, normal hours)",
              user="USER-31", src="EXTERNAL", external=True, mfa=True, baseline=True),
            E("14:25:40", "network", "VPN-GW", "VPN-GW opened SSH (22) session to RTU-01; first time on this path",
              src="VPN-GW", dst="RTU-01", port=22, baseline=False),
            E("14:26:10", "auth", "RTU-01", "SSH login to RTU-01 by USER-31 (MFA passed)",
              user="USER-31", src="VPN-GW", external=False, mfa=True, baseline=True),
            E("14:27:30", "firmware", "RTU-01", "Firmware image 13.2.1 uploaded to RTU-01 by USER-31",
              user="USER-31", signed=True, hash_match=True, version="13.2.1"),
            E("14:31:20", "comms", "RTU-01", "RTU-01 lost communication with DSO for 3 min (device reboot)",
              peer="DSO", duration="3 min", reboot=True),
        ]),
        context=dict(
            maintenance=[dict(asset="RTU-01", start="14:20", end="14:50", user="USER-31", ticket="CHG-2210",
                              note="Vendor-signed firmware 13.2.1 rollout")],
            users={"USER-31": dict(role="Field engineer", authorized=["VPN-GW", "RTU-01"], admin=False)},
            firmware={"RTU-01": dict(signed=True, hash_match=True, version="13.2.1")}),
        truth=dict(incident=False, summary="Planned, vendor-signed firmware update under ticket CHG-2210; the reboot caused the comms loss.",
                   path=[]),
    )


def _s5():
    return dict(
        id="S5", name="Scenario 5 · Off-hours login on application server",
        summary="Alert: off-hours login on the application server from the engineering workstation.",
        alert=dict(t="02:41:10", asset="SERVER-02", kind="auth",
                   text="Anomalous login: USER-09 from WS-ENG-01 at 02:41 (outside baseline)"),
        events=_mk([
            E("02:41:10", "auth", "SERVER-02", "Login USER-09 on SERVER-02 from WS-ENG-01 at 02:41; no MFA, outside baseline",
              user="USER-09", src="WS-ENG-01", external=False, mfa=False, baseline=False),
            E("02:42:05", "process", "SERVER-02", "credential_dump.exe launched by USER-09 (credential dumping tool)",
              user="USER-09", name="credential_dump.exe", suspicious=True, tool="credential_dumping"),
            E("02:43:30", "network", "SERVER-02", "SERVER-02 opened SMB (445) session to OT-SERVER; first time on this path",
              src="SERVER-02", dst="OT-SERVER", port=445, baseline=False),
            E("02:44:12", "auth", "HMI-01", "Login USER-09 on HMI-01 via OT-SERVER; account never used in OT before",
              user="USER-09", src="OT-SERVER", external=False, mfa=False, baseline=False),
            E("02:45:00", "network", "HMI-01", "HMI-01 sent Modbus (502) read requests to PLC-02; first time on this path",
              src="HMI-01", dst="PLC-02", port=502, baseline=False),
        ]),
        context=dict(
            maintenance=[],
            users={"USER-09": dict(role="HR analyst", authorized=["SERVER-02"], admin=False)},
            firmware={}),
        truth=dict(incident=True, summary="Stolen credentials used for lateral movement towards the PLC; caught before any change was made.",
                   path=["WS-ENG-01", "SERVER-02", "OT-SERVER", "HMI-01", "PLC-02"]),
    )


SCENARIOS = {s["id"]: s for s in (_s1(), _s2(), _s3(), _s4(), _s5())}


def public_scenarios():
    """Scenario list for the UI. Ground truth is NOT included."""
    return [dict(id=s["id"], name=s["name"], summary=s["summary"]) for s in SCENARIOS.values()]
