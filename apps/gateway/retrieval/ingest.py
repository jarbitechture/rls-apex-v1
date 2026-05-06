"""Ingest pipeline: corpus/raw/* → corpus/extracted/*.txt + corpus/index/bm25.json
+ corpus/manifest.json. Run via `bin/ingest`.

Design notes:
- Dedup by sha256 — duplicate raw files are skipped silently.
- PDFs go through pypdf; CSV is read as plain text. New formats add a handler
  by registering an extractor in `_EXTRACTORS`.
- Chunks are paragraph-bounded and capped at TARGET_CHUNK_CHARS, with a 1-line
  overlap so retrieval can score across boundaries.
- Source kind + classification are inferred from filename heuristics. Override
  for sensitive matters by editing `manifest.json` after ingest.

In production, this module gets replaced by an LightRAG ingestion task that
runs on bcc-ap-infer01 against the redacted corpus. The on-disk manifest
+ index format goes away (Postgres + pgvector + AGE). The /api/retrieve
contract stays.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "corpus" / "raw"
EXTRACTED_DIR = ROOT / "corpus" / "extracted"
INDEX_DIR = ROOT / "corpus" / "index"
MANIFEST_PATH = ROOT / "corpus" / "manifest.json"
INDEX_PATH = INDEX_DIR / "bm25.json"

TARGET_CHUNK_CHARS = 900
MIN_CHUNK_CHARS = 80
OVERLAP_LINES = 1


# ─── Source-kind + classification heuristics ──────────────────────

def _classify(name: str) -> tuple[str, str]:
    """Return (source_kind, classification) from filename heuristics."""
    n = name.lower()
    if "checklist" in n: return ("checklist", "public_record")
    if "submission-form" in n or "submission form" in n: return ("form", "public_record")
    if "submission-procedure" in n or "submission procedure" in n: return ("procedure", "public_record")
    if "code-enforcement" in n: return ("checklist", "public_record")
    if "onbase" in n or "records-retention" in n or "project-plan" in n: return ("project_plan", "internal")
    if re.match(r"^\d{2}[a-z]+\d{4}", n): return ("case_file", "internal")
    return ("document", "internal")


# ─── Extraction ───────────────────────────────────────────────────

def _extract_pdf(path: Path) -> tuple[str, int]:
    """Return (full_text, page_count). pypdf for text PDFs; falls back to
    OCR (pdftoppm + tesseract) on pages where pypdf yields little/no text
    (image-only / scanned pages).
    """
    from pypdf import PdfReader  # local import — only loaded when ingesting
    reader = PdfReader(str(path))
    pages = []
    for page_num, page in enumerate(reader.pages):
        try:
            text = (page.extract_text() or "").strip()
        except Exception as e:  # noqa: BLE001
            text = f"[extraction error: {e}]"
        if len(text) < 50:
            ocr_text = _ocr_pdf_page(path, page_num)
            if ocr_text:
                text = ocr_text + "\n[[OCR]]"
        pages.append(text)
    return ("\n\n[[PAGE_BREAK]]\n\n".join(pages), len(reader.pages))


def _ocr_pdf_page(path: Path, page_num: int) -> str:
    """OCR a single page via pdftoppm + tesseract. Returns '' if either
    tool is missing OR the OCR run fails. Both tools are present on the
    Mac dev box and on bcc-ap-llm01 (RHEL package: poppler-utils, tesseract).
    """
    import shutil
    import subprocess
    import tempfile
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return ""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        prefix = td_path / "page"
        try:
            subprocess.run(
                ["pdftoppm", "-r", "200", "-png",
                 "-f", str(page_num + 1), "-l", str(page_num + 1),
                 str(path), str(prefix)],
                check=True, capture_output=True, timeout=45,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ""
        pngs = sorted(td_path.glob("page-*.png"))
        if not pngs:
            return ""
        try:
            r = subprocess.run(
                ["tesseract", str(pngs[0]), "-", "-l", "eng",
                 "--psm", "1", "--oem", "1"],
                check=True, capture_output=True, text=True, timeout=45,
            )
            return r.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ""


def _extract_csv(path: Path) -> tuple[str, int]:
    """CSV → plain text with row markers. Returns (text, row_count)."""
    out = io.StringIO()
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        rows = list(reader)
    for row in rows:
        if any(cell.strip() for cell in row):
            out.write(" | ".join(cell.strip() for cell in row))
            out.write("\n")
    return (out.getvalue(), len(rows))


_EXTRACTORS: dict[str, Callable[[Path], tuple[str, int]]] = {
    ".pdf": _extract_pdf,
    ".csv": _extract_csv,
}


# ─── Chunking ─────────────────────────────────────────────────────

@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    page: int | None
    chunk_idx: int
    text: str


def _chunk_text(doc_id: str, text: str) -> list[Chunk]:
    """Split text into paragraph-bounded chunks with line overlap."""
    chunks: list[Chunk] = []
    page = 1
    chunk_idx = 0
    for raw_block in text.split("\n\n"):
        block = raw_block.strip()
        if not block:
            continue
        if "[[PAGE_BREAK]]" in block:
            page += 1
            block = block.replace("[[PAGE_BREAK]]", "").strip()
            if not block:
                continue

        # Pack paragraphs into target-sized chunks.
        if not chunks or len(chunks[-1].text) + len(block) + 2 > TARGET_CHUNK_CHARS:
            chunk_idx += 1
            cid = f"{doc_id}:c{chunk_idx:04d}"
            # Carry the last `OVERLAP_LINES` lines from the previous chunk into this one.
            prefix = ""
            if chunks and OVERLAP_LINES > 0:
                tail = chunks[-1].text.split("\n")[-OVERLAP_LINES:]
                prefix = "\n".join(tail).strip()
                if prefix:
                    prefix += "\n"
            chunks.append(Chunk(chunk_id=cid, doc_id=doc_id, page=page, chunk_idx=chunk_idx,
                                 text=prefix + block))
        else:
            chunks[-1].text += "\n\n" + block

    return [c for c in chunks if len(c.text) >= MIN_CHUNK_CHARS]


# ─── Driver ───────────────────────────────────────────────────────

def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _doc_id_from_hash(hex_hash: str) -> str:
    return f"doc-{hex_hash[:8]}"


def _iter_raw_files() -> Iterable[Path]:
    if not RAW_DIR.exists():
        return []
    for p in sorted(RAW_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in _EXTRACTORS:
            yield p


def ingest() -> dict:
    """Walk corpus/raw/, extract+chunk+index, write manifest + bm25.json."""
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    manifest_docs: list[dict] = []
    all_chunks: list[Chunk] = []
    seen_hashes: set[str] = set()

    for raw_path in _iter_raw_files():
        h = _hash(raw_path)
        if h in seen_hashes:
            print(f"  skip (duplicate hash): {raw_path.name}")
            continue
        seen_hashes.add(h)

        doc_id = _doc_id_from_hash(h)
        ext = raw_path.suffix.lower()
        extractor = _EXTRACTORS[ext]
        try:
            text, n_pages = extractor(raw_path)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR extracting {raw_path.name}: {e}")
            continue

        # Persist extracted text for debugging / re-chunking
        extracted_path = EXTRACTED_DIR / f"{doc_id}.txt"
        extracted_path.write_text(text, encoding="utf-8")

        chunks = _chunk_text(doc_id, text)
        all_chunks.extend(chunks)

        kind, classification = _classify(raw_path.name)
        manifest_docs.append({
            "id": doc_id,
            "source": raw_path.name,
            "source_kind": kind,
            "classification": classification,
            "pages": n_pages,
            "chunks": len(chunks),
            "bytes": raw_path.stat().st_size,
            "hash": f"sha256:{h}",
        })
        print(f"  ingested {doc_id}: {raw_path.name} → {n_pages}p / {len(chunks)} chunks "
              f"[{kind}, {classification}]")

    manifest = {
        "version": 1,
        "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "documents": manifest_docs,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # ── Build BM25 index ─────────────────────────────────────────
    from rank_bm25 import BM25Okapi  # noqa: F401  # used at retrieve time

    chunk_records = []
    for c in all_chunks:
        tokens = _tokenize(c.text)
        chunk_records.append({
            **asdict(c),
            "tokens": tokens,
        })

    INDEX_PATH.write_text(json.dumps({
        "version": 1,
        "tokenizer": "simple-lc-alnum",
        "chunks": chunk_records,
    }, indent=2) + "\n", encoding="utf-8")

    print(f"\nmanifest: {MANIFEST_PATH.relative_to(ROOT.parent)} "
          f"({len(manifest_docs)} docs)")
    print(f"index:    {INDEX_PATH.relative_to(ROOT.parent)} "
          f"({len(all_chunks)} chunks)")
    return manifest


# ─── Tokenizer (shared with retrieve.py) ──────────────────────────

_TOKEN_RE = re.compile(r"[a-z0-9§]+")

def _tokenize(text: str) -> list[str]:
    """Lowercase + alphanumeric + § (statute marker). Drop tokens < 2 chars."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= 2]


if __name__ == "__main__":
    print(f"corpus/raw/ → corpus/extracted/, corpus/index/, corpus/manifest.json")
    print(f"  raw dir: {RAW_DIR}")
    if not RAW_DIR.exists() or not list(RAW_DIR.iterdir()):
        print(f"  no files in {RAW_DIR} — copy your PDFs/CSVs there and re-run")
        sys.exit(1)
    ingest()
