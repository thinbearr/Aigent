"""
PDF ingestion module for CyberArena.

Reads industrial SOP PDFs from a docs directory, extracts operational
steps relevant to each known asset, and writes config/playbooks.yaml.
"""
import re
import pathlib
import datetime
import pdfplumber

# ---------------------------------------------------------------------------
# Asset keyword map: asset-id -> list of keywords that signal relevance
# ---------------------------------------------------------------------------
ASSET_KEYWORDS: dict[str, list[str]] = {
    "plc-01": [
        "mixer", "mixing", "agitator", "potentiometer", "start/stop",
        "speed control", "tank", "pump", "stirrer", "mains supply",
        "control room", "valve", "blending", "premix", "cooling tower",
        "batch", "blade"
    ],
    "sis-01": [
        "safety", "emergency", "fire", "ppe", "protective", "exit",
        "hazard", "fire fighting", "shift foreman", "plant manager",
        "electrical power", "close valves", "steam", "solvents lines",
        "injuries", "abnormalities"
    ],
    "eng-ws-01": [
        "electronic devices", "headphones", "ear buds", "warehouse",
        "hazardous environment", "engineering", "programming"
    ],
}


def _clean_str(text: str) -> str:
    """Normalize internal spaces and newlines."""
    if not text:
        return ""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return " ".join(lines)


def _extract_steps_from_tables(pdf) -> list[str]:
    """Extract operational steps from tabular SOPs (like Appendix A)."""
    steps: list[str] = []
    seen: set[str] = set()

    for page in pdf.pages:
        tables = page.extract_tables() or []
        for t in tables:
            for row in t:
                clean_row = [c.strip() for c in row if c and c.strip()]
                if not clean_row:
                    continue

                # Check if first cell is a step number e.g. "1.1", "3.2", "4.2"
                num_cell = clean_row[0]
                if re.match(r"^\d+(\.\d+)?$", num_cell) and len(clean_row) > 1:
                    step_text = _clean_str(clean_row[1])
                    if step_text.isupper() and len(step_text.split()) <= 4:
                        continue
                    if len(step_text) > 10 and step_text not in seen:
                        steps.append(step_text)
                        seen.add(step_text)
                
                # Check emergency action rows (e.g. "In the event of Fire...")
                for cell in clean_row:
                    if cell.startswith("In the event of Fire") or cell.startswith("Emergency:"):
                        txt = _clean_str(cell)
                        if txt not in seen:
                            steps.append(txt)
                            seen.add(txt)

    return steps


def _extract_steps_from_text(pdf) -> list[str]:
    """Extract operational steps from standard text/section SOPs."""
    full_text = ""
    for page in pdf.pages:
        txt = page.extract_text() or ""
        full_text += "\n" + txt

    pattern = re.compile(
        r"(?:^|\n)\s*(\d+\.\d+)\s+([^\n]+(?:\n(?!\s*\d+\.\d+|\s*\d+\.0)[^\n]+)*)",
        re.MULTILINE
    )

    steps: list[str] = []
    seen: set[str] = set()

    for m in pattern.finditer(full_text):
        num_str = m.group(1)
        if num_str.endswith(".0"):
            continue
        content = _clean_str(m.group(2))
        if len(content) > 15 and content not in seen:
            steps.append(content)
            seen.add(content)

    return steps


def _extract_pdf_steps(pdf_path: pathlib.Path) -> tuple[str, list[str]]:
    """Extract full raw text (for relevance scoring) and clean list of steps."""
    with pdfplumber.open(pdf_path) as pdf:
        full_text = " ".join(page.extract_text() or "" for page in pdf.pages)
        table_steps = _extract_steps_from_tables(pdf)
        text_steps = _extract_steps_from_text(pdf)

        steps: list[str] = []
        seen: set[str] = set()
        for s in table_steps + text_steps:
            if s not in seen:
                steps.append(s)
                seen.add(s)

        return full_text, steps


def _score_relevance(text: str, keywords: list[str]) -> int:
    """Count how many keywords appear in the text (case-insensitive)."""
    lower = text.lower()
    return sum(1 for kw in keywords if kw in lower)


def ingest_docs(
    docs_dir: str | pathlib.Path,
    min_relevance: int = 1,
) -> dict[str, list[str]]:
    """
    Read all PDFs in docs_dir and return a dict:
        { asset_id: [step, step, ...], ... }
    """
    docs_dir = pathlib.Path(docs_dir)
    playbooks: dict[str, list[str]] = {aid: [] for aid in ASSET_KEYWORDS}
    playbooks["general"] = []

    pdf_files = sorted(docs_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDFs found in {docs_dir}")

    for pdf_path in pdf_files:
        text, steps = _extract_pdf_steps(pdf_path)
        if not steps:
            continue

        scores = {
            aid: _score_relevance(text, kws)
            for aid, kws in ASSET_KEYWORDS.items()
        }
        best_asset = max(scores, key=lambda a: scores[a])
        best_score = scores[best_asset]

        target = best_asset if best_score >= min_relevance else "general"

        doc_label = pdf_path.stem.replace("_", " ").replace("-", " ").title()
        for step in steps:
            entry = f"[{doc_label}] {step}"
            if entry not in playbooks[target]:
                playbooks[target].append(entry)

    return playbooks


def write_playbooks_yaml(
    playbooks: dict[str, list[str]],
    out_path: str | pathlib.Path,
    source_docs: list[str] | None = None,
) -> None:
    """Write the playbooks dict to a YAML file without external yaml dependency."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Auto-generated by: cyberarena ingest-docs",
        f"# Generated at: {datetime.datetime.now().isoformat(timespec='seconds')}",
        "",
    ]

    if source_docs:
        lines.append("source_docs:")
        for doc in source_docs:
            lines.append(f"  - {doc}")
        lines.append("")

    lines.append("playbooks:")
    for asset_id, steps in playbooks.items():
        lines.append(f"  {asset_id}:")
        if steps:
            for step in steps:
                safe = step.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'    - "{safe}"')
        else:
            lines.append("    []")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
