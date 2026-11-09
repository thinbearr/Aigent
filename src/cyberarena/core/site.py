"""Site configuration: everything the engine needs to know about *your* plant, loaded from YAML.

Nothing about any particular plant is hardcoded in the engine. See config/site.example.yaml and docs/CONFIG.md.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Asset:
    id: str
    zone: str = "IT"
    role: str = ""
    ips: list[str] = field(default_factory=list)


@dataclass
class Site:
    name: str
    assets: dict[str, Asset]
    zones: list[str]                              # ordered outside -> process, used to rank "how deep" an asset is
    internal_cidrs: list[ipaddress.IPv4Network]
    roles: dict[str, set[str]]                    # role -> assets that role may operate
    accounts: dict[str, dict]                     # user -> {role, default, shared, enabled}
    ticket_roles: set[str]                        # roles authorised only while holding a ticket (e.g. vendors)
    asset_aliases: dict[str, list[str]]           # a ticket for any alias also covers the asset
    remote_gateways: set[str]                     # hosts whose logins are remote access (MFA expected)
    limits: dict[str, tuple[float, float]]        # engineering limits per parameter
    routine: dict                                 # {sources, operators, max_delta}
    trusted_sources: set[str]                     # hosts that normally talk to controllers
    sensitive_files: list[str]
    process_assets: set[str]
    raw: dict = field(default_factory=dict)
    _ip: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------ lookups
    def host_of_ip(self, ip: str | None) -> str:
        """Asset id for an address, 'external' for outside addresses, 'internal' for unknown inside ones."""
        if not ip:
            return "unknown"
        if ip in self._ip:
            return self._ip[ip]
        return "external" if self.is_external(ip) else "internal"

    def is_external(self, ip: str | None) -> bool:
        if not ip or ip in self._ip:
            return False
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return True
        return not any(a in n for n in self.internal_cidrs)

    def zone_of(self, asset: str | None) -> str:
        if asset in (None, "external", "EXTERNAL"):
            return "EXTERNAL"
        a = self.assets.get(asset)
        return a.zone if a else "IT"

    def zone_rank(self, asset: str | None) -> int:
        z = self.zone_of(asset)
        return -1 if z == "EXTERNAL" else (self.zones.index(z) if z in self.zones else 1)

    def deep(self, asset: str | None) -> bool:
        """True for assets in the operational (non-office) part of the plant."""
        return self.zone_rank(asset) >= 2

    def known_asset(self, a: str | None) -> bool:
        return a in self.assets or a == "external"

    def within_limits(self, param: str | None, value) -> bool | None:
        lim = self.limits.get(param or "")
        if lim is None or not isinstance(value, (int, float)):
            return None
        return lim[0] <= value <= lim[1]


def load(path: str | Path | dict) -> Site:
    d = path if isinstance(path, dict) else yaml.safe_load(Path(path).read_text(encoding="utf8"))
    assets = {}
    ipmap = {}
    for a in d["assets"]:
        ips = [a["ip"]] if a.get("ip") else []
        ips += a.get("extra_ips", [])
        assets[a["id"]] = Asset(a["id"], a.get("zone", "IT"), a.get("role", ""), ips)
        for ip in ips:
            ipmap[ip] = a["id"]
    return Site(
        name=d.get("name", "site"),
        assets=assets,
        zones=d.get("zones", ["DMZ", "IT", "OT", "Control", "Process"]),
        internal_cidrs=[ipaddress.ip_network(c) for c in d.get("internal_cidrs", ["10.0.0.0/8", "192.168.0.0/16", "172.16.0.0/12"])],
        roles={r: set(v) for r, v in d.get("roles", {}).items()},
        accounts=d.get("accounts", {}),
        ticket_roles=set(d.get("ticket_roles", [])),
        asset_aliases=d.get("asset_aliases", {}),
        remote_gateways=set(d.get("remote_gateways", [])),
        limits={k: (float(v[0]), float(v[1])) for k, v in d.get("limits", {}).items()},
        routine=d.get("routine", {"sources": [], "operators": [], "max_delta": 1.0}),
        trusted_sources=set(d.get("trusted_sources", [])),
        sensitive_files=[s.lower() for s in d.get("sensitive_files", [])],
        process_assets=set(d.get("process_assets", ["process"])),
        raw=d,
        _ip=ipmap,
    )
