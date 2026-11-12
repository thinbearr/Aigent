"""
Curated, validated PDF extraction and industrial SOP auditor for CyberArena.

Audits and filters raw text from site documents so that only realistic,
actionable industrial incident mitigation steps reach the operator checklist.
Rejects housekeeping, study questions, table headers, and non-containment text.
"""
import re
import pathlib
import datetime
import pdfplumber

# Forbidden phrases that belong to training, housekeeping, or metadata
DISQUALIFY_PATTERNS = [
    r"what could happen",
    r"what do you do",
    r"who is responsible",
    r"what materials and equipment",
    r"what is the purpose",
    r"reflective knowledge",
    r"dirt causes",
    r"waste bin",
    r"dirt bin",
    r"housekeeping",
    r"leave lift",
    r"switch off lights",
    r"standard operating procedure",
    r"author status",
    r"effective date",
    r"michael boblit",
    r"gemini industries",
    r"page \d+ / \d+",
    r"qid#",
    r"machine description",
    r"practical steps",
    r"scope and overview",
    r"notice the start/start station",
    r"using the picture above",
]

# Action verbs that characterize genuine industrial operator mitigation
ACTION_TRIGGERS = [
    "switch off", "turn off", "shut down", "isolate", "close valve",
    "stop button", "potentiometer", "blade submerged", "free spin",
    "emergency", "mains supply", "cooling water", "steam", "solvents",
    "bottom of the mixer", "premix tank", "blending tank", "agitator",
    "stirrer", "abnormalities", "foreman", "supervisor", "batch card"
]

# Industry-standard baseline playbooks for all Purdue assets (ISA/IEC 62443 & NIST SP 800-82)
INDUSTRY_BASELINES: dict[str, list[str]] = {
    "plc-01": [
        "Dispatch Line Operator to physical PLC cabinet at mixing vessel MV-101.",
        "Change PLC physical key-switch from REMOTE to LOCAL/STOP to lock out unauthorized network commands.",
        "Cross-reference physical process gauges (temperature < 65°C, level, pressure) against the approved Batch Record.",
        "Inspect agitator drive and turn speed potentiometer fully counterclockwise to minimum before reset.",
        "Verify emergency relief valves and bottom dump lines are unobstructed before clearing alarms.",
        "Obtain Supervisor physical sign-off in the shift log before re-enabling automated remote control."
    ],
    "sis-01": [
        "URGENT: Verify Safety Instrumented System (SIS) physical lockout key switch status.",
        "Confirm hardwired emergency safety interlock circuits (overpressure and thermal trip) are armed and active.",
        "Physically inspect pressure relief valve PRV-101 and manual dump bypass handles.",
        "Disconnect SIS network communication link to isolate from remote network overrides.",
        "Mandatory two-person sign-off (Shift Supervisor + HSE Officer) required prior to bypass reset."
    ],
    "eng-ws-01": [
        "Physically disconnect the engineering workstation Ethernet patch cable (rear panel OT-LAN drop).",
        "Terminate all active PLC programming sessions (TIA Portal / FactoryTalk Go Offline).",
        "Revoke engineering domain credentials and invalidate temporary service tokens.",
        "Inspect local USB ports for unauthorized storage or programming interfaces.",
        "Keep workstation quarantined for forensic image capture before restoring operations."
    ],
    "historian-01": [
        "Sever historian data ingest ports at the Level 3 / Level 2 boundary firewall.",
        "Compare real-time historian trend values against physical analog gauges on the plant floor.",
        "Export and cryptographically hash the transaction audit log for all tag modifications in the incident window.",
        "Reset service account credentials and force re-authentication for all collector instances."
    ],
    "portal-01": [
        "Terminate all active remote VPN and vendor maintenance sessions immediately.",
        "Revoke external user tokens and force multi-factor authentication re-verification.",
        "Apply emergency firewall block rule on inbound remote management ports at fw-02.",
        "Audit remote gateway access logs for unexpected external IP connections."
    ],
    "fw-02": [
        "Roll back boundary firewall ruleset to signed golden baseline configuration.",
        "Verify complete network isolation between Purdue Level 3 (Operations) and Level 1 (Process Control).",
        "Drop all unapproved dynamic routing and lateral pivot connections.",
        "Export firewall rule change log to USB media for incident forensic review."
    ]
}


def _is_valid_incident_step(text: str) -> bool:
    """Validate whether an extracted line is a genuine operational mitigation step."""
    clean = text.strip()
    if len(clean) < 20 or len(clean) > 300:
        return False

    lower = clean.lower()
    for bad in DISQUALIFY_PATTERNS:
        if re.search(bad, lower):
            return False

    # Must contain at least one operational action trigger
    return any(trig in lower for trig in ACTION_TRIGGERS)


def _clean_text(text: str) -> str:
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return " ".join(line.strip() for line in text.split("\n") if line.strip())


def extract_audited_steps_from_pdf(pdf_path: pathlib.Path) -> list[str]:
    """Extract and rigorously validate mitigation steps from an SOP PDF."""
    raw_candidates: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        # Extract from tables
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for t in tables:
                for row in t:
                    cells = [_clean_text(c) for c in row if c and c.strip()]
                    if not cells:
                        continue
                    # Check first cell if number, and second cell if action
                    if len(cells) >= 2 and re.match(r"^\d+(\.\d+)?$", cells[0]):
                        raw_candidates.append(cells[1])
                    for cell in cells:
                        if "emergency action" in cell.lower() or "in the event of" in cell.lower():
                            raw_candidates.append(cell)

        # Extract from numbered sections in text
        for page in pdf.pages:
            txt = page.extract_text() or ""
            matches = re.finditer(
                r"(?:^|\n)\s*(\d+\.\d+)\s+([^\n]+(?:\n(?!\s*\d+\.\d+|\s*\d+\.0)[^\n]+)*)",
                txt, re.MULTILINE
            )
            for m in matches:
                num = m.group(1)
                if not num.endswith(".0"):
                    raw_candidates.append(_clean_text(m.group(2)))

    # Filter and audit candidates
    audited: list[str] = []
    seen: set[str] = set()
    for cand in raw_candidates:
        if _is_valid_incident_step(cand):
            # Normalise formatting
            step = cand.strip()
            if not step.endswith("."):
                step += "."
            if step not in seen:
                audited.append(step)
                seen.add(step)

    return audited


def generate_curated_playbooks(docs_dir: pathlib.Path, out_yaml: pathlib.Path) -> dict[str, list[str]]:
    """
    Build playbooks by merging audited PDF equipment procedures with
    authoritative industrial cybersecurity SOP standards.
    """
    playbooks: dict[str, list[str]] = {k: list(v) for k, v in INDUSTRY_BASELINES.items()}
    source_docs = []

    if docs_dir.exists():
        pdf_files = sorted(docs_dir.glob("*.pdf"))
        for pdf_path in pdf_files:
            source_docs.append(pdf_path.name)
            doc_label = pdf_path.stem.replace("_", " ").replace("-", " ").title()
            valid_steps = extract_audited_steps_from_pdf(pdf_path)

            for s in valid_steps:
                lower = s.lower()
                tagged = f"[{doc_label}] {s}"
                # Route verified machinery steps to plc-01 or sis-01
                if any(k in lower for k in ["mixer", "tank", "potentiometer", "blade", "valve", "steam", "cooling"]):
                    if tagged not in playbooks["plc-01"]:
                        playbooks["plc-01"].append(tagged)
                elif any(k in lower for k in ["emergency", "fire", "foreman", "supervisor", "power"]):
                    if tagged not in playbooks["sis-01"]:
                        playbooks["sis-01"].append(tagged)

    # Write out YAML
    out_yaml.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Audited industrial mitigation playbooks",
        f"# Generated at: {datetime.datetime.now().isoformat(timespec='seconds')}",
        "",
        "source_docs:",
    ]
    for d in source_docs:
        lines.append(f"  - {d}")
    lines.append("")
    lines.append("playbooks:")

    for asset_id, steps in playbooks.items():
        lines.append(f"  {asset_id}:")
        for step in steps:
            safe = step.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'    - "{safe}"')
        lines.append("")

    out_yaml.write_text("\n".join(lines), encoding="utf-8")
    return playbooks


if __name__ == "__main__":
    import sys
    docs = pathlib.Path("config/site-docs")
    out = pathlib.Path("config/playbooks.yaml")
    res = generate_curated_playbooks(docs, out)
    print(f"Generated curated playbooks for {len(res)} assets in {out}")
