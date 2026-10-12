"""Extract a PDF from private/pdfs into source TXT and JSON. No network access."""
import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import platform
import re
import shutil

from pypdf import PdfReader, __version__ as pypdf_version
from pypdf.errors import PyPdfError

ROOT = Path(__file__).resolve().parents[2] / "data/benchmark"


def extract_pdf(body):
    if not body.startswith(b"%PDF-"):
        raise ValueError("The local file is not a PDF")
    reader = PdfReader(BytesIO(body))
    chunks, pages, offset = [], [], 0
    for number, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        chunks.append(text)
        pages.append({"page_number": number, "source_span": [offset, offset + len(text)]})
        offset += len(text) + 2
    if not any(chunks):
        raise ValueError("PDF has no extractable text; it needs OCR before use")
    return "\n\n".join(chunks), pages


def extract_source(pdf_name, source_id, root=ROOT):
    if Path(pdf_name).name != pdf_name or Path(pdf_name).suffix.lower() != ".pdf":
        raise ValueError("Put the PDF in private/pdfs and pass only its filename")
    if not re.fullmatch(r"SRC_\d+", source_id):
        raise ValueError("Use a source ID such as SRC_04")
    root = Path(root)
    folder = root / "private/sources"
    text_path, details_path = folder / f"{source_id}.txt", folder / f"{source_id}.json"
    pdf_path = root / "private/pdfs" / pdf_name
    body = pdf_path.read_bytes()
    text, pages = extract_pdf(body)
    encoded = text.encode("utf-8")
    details = {
        "source_id": source_id, "input_origin": "user_supplied_pdf", "original_filename": pdf_name,
        "input_file": f"private/pdfs/{pdf_name}", "input_sha256": hashlib.sha256(body).hexdigest(),
        "extracted_at": datetime.now(timezone.utc).isoformat(), "extraction_method": "pypdf-pages-v1",
        "python_version": platform.python_version(), "pypdf_version": pypdf_version,
        "text_sha256": hashlib.sha256(encoded).hexdigest(), "text_encoding": "utf-8", "newlines": "LF",
        "pdf_page_count": len(pages), "pdf_pages": pages,
        "pages_without_text": [p["page_number"] for p in pages if p["source_span"][0] == p["source_span"][1]],
    }
    folder.mkdir(parents=True, exist_ok=True)
    existing = [path for path in (text_path, details_path) if path.exists()]
    if existing:
        backup = root / "private/archive" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ_") + source_id)
        backup.mkdir(parents=True, exist_ok=False)
        for path in existing:
            shutil.copy2(path, backup / path.name)
    with text_path.open("wb") as output:
        output.write(encoded)
    with details_path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(details, output, indent=2)
        output.write("\n")
    return text_path, details_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", help="Filename inside data/benchmark/private/pdfs, e.g. aapl-20250927.pdf")
    parser.add_argument("--source-id", required=True, help="Source ID, e.g. SRC_01; replaces existing TXT/JSON after backing them up")
    parser.add_argument("--root", type=Path, default=ROOT, help="Dataset folder; defaults to data/benchmark")
    args = parser.parse_args()
    try:
        paths = extract_source(args.pdf, args.source_id, args.root)
    except (ValueError, OSError, PyPdfError) as error:
        parser.exit(1, f"Extraction failed: {error}\n")
    for path in paths:
        print(path)
    print("Recheck linked evidence packets after replacing a source; their spans are not updated automatically.")


if __name__ == "__main__":
    main()
