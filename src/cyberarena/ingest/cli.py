"""
CLI entry point: cyberarena ingest-docs

Usage:
    cyberarena ingest-docs [--docs PATH] [--out PATH]

Reads PDFs from --docs directory, extracts mitigation steps,
and writes them to --out YAML file.
"""
import argparse
import pathlib
import sys

from cyberarena.ingest.pdf_reader import ingest_docs, write_playbooks_yaml

DEFAULT_DOCS = pathlib.Path("config/site-docs")
DEFAULT_OUT = pathlib.Path("config/playbooks.yaml")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="cyberarena ingest-docs",
        description="Ingest SOP PDFs and generate config/playbooks.yaml",
    )
    parser.add_argument(
        "--docs",
        type=pathlib.Path,
        default=DEFAULT_DOCS,
        help=f"Directory containing SOP PDFs (default: {DEFAULT_DOCS})",
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=DEFAULT_OUT,
        help=f"Output YAML path (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args(argv)

    docs_dir: pathlib.Path = args.docs
    out_path: pathlib.Path = args.out

    if not docs_dir.exists():
        print(f"[ERROR] Docs directory not found: {docs_dir}", file=sys.stderr)
        sys.exit(1)

    pdf_files = list(docs_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"[ERROR] No PDF files found in {docs_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[ingest-docs] Reading {len(pdf_files)} PDF(s) from {docs_dir} ...")
    playbooks = ingest_docs(docs_dir)

    total_steps = sum(len(v) for v in playbooks.values())
    for asset, steps in playbooks.items():
        if steps:
            print(f"  {asset}: {len(steps)} step(s)")

    print(f"[ingest-docs] Total steps extracted: {total_steps}")
    print(f"[ingest-docs] Writing playbooks to {out_path} ...")

    source_docs = [p.name for p in sorted(pdf_files)]
    write_playbooks_yaml(playbooks, out_path, source_docs=source_docs)

    print(f"[ingest-docs] Done. Run 'cyberarena agent serve' to load new playbooks.")


if __name__ == "__main__":
    main()
