"""CLI entry point for the redaction pipeline.

Usage:
    python -m services.redaction process <path> --source-doc-id ID [--llm-model phi4]

Environment variables (all required for DB connection):
    DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

import asyncpg

from .pipeline import process_document


async def _run(path: str, source_doc_id: str, llm_model: str) -> None:
    conn = await asyncpg.connect(
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ["DB_NAME"],
    )
    try:
        result = await process_document(
            conn,
            path=path,
            source_doc_id=source_doc_id,
            llm_model=llm_model,
        )
        print(
            f"source_doc_id={result.source_doc_id} "
            f"spans_detected={result.spans_detected}"
        )
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m services.redaction",
        description="Redaction pipeline CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    proc = sub.add_parser("process", help="Process a document through the redaction pipeline")
    proc.add_argument("path", help="Path to the document file")
    proc.add_argument("--source-doc-id", required=True, help="Unique source document ID")
    proc.add_argument("--llm-model", default="phi4", help="Ollama model name (default: phi4)")

    args = parser.parse_args(argv)

    if args.command == "process":
        asyncio.run(_run(args.path, args.source_doc_id, args.llm_model))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
