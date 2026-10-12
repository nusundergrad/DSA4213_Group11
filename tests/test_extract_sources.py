import hashlib
import json
import shutil
import socket

import pytest
from pypdf import PdfWriter

from src.benchmark import extract_sources as e


@pytest.fixture
def pdf_folder(tmp_path):
    folder = tmp_path / "private/pdfs"
    folder.mkdir(parents=True)
    shutil.copy2(e.ROOT / "private/pdfs/aapl-20250927.pdf", folder)
    return tmp_path


def test_local_pdf_without_network(pdf_folder, monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("No network allowed"))
    text_path, details_path = e.extract_source("aapl-20250927.pdf", "SRC_07", pdf_folder)
    details = json.loads(details_path.read_text())
    text = text_path.read_text(encoding="utf-8")
    assert "download_url" not in details and "retrieved_at" not in details
    assert details["input_origin"] == "user_supplied_pdf"
    assert details["pdf_page_count"] == 65 and details["pages_without_text"] == []
    page = details["pdf_pages"][26]
    start, end = page["source_span"]
    assert page["page_number"] == 27
    assert "Products and Services Performance" in text[start:end]
    assert "416,161" in text[start:end] and "391,035" in text[start:end]
    pdf = pdf_folder / details["input_file"]
    assert details["input_sha256"] == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert details["text_sha256"] == hashlib.sha256(text_path.read_bytes()).hexdigest()
    assert {p.suffix for p in text_path.parent.iterdir()} == {".txt", ".json"}
    assert text_path.read_bytes() == (e.ROOT / "private/sources/SRC_01.txt").read_bytes()
    before = details_path.read_bytes()
    text_path.write_text("old extraction", encoding="utf-8")
    e.extract_source("aapl-20250927.pdf", "SRC_07", pdf_folder)
    backups = list((pdf_folder / "private/archive").iterdir())
    assert len(backups) == 1
    assert (backups[0] / "SRC_07.json").read_bytes() == before
    assert (backups[0] / "SRC_07.txt").read_text() == "old extraction"
    assert text_path.read_bytes() == (e.ROOT / "private/sources/SRC_01.txt").read_bytes()
    before = (text_path.read_bytes(), details_path.read_bytes())
    (pdf_folder / "private/pdfs/bad.pdf").write_bytes(b"bad PDF")
    with pytest.raises(ValueError):
        e.extract_source("bad.pdf", "SRC_07", pdf_folder)
    assert (text_path.read_bytes(), details_path.read_bytes()) == before


def test_scanned_or_invalid_pdf_is_not_saved(tmp_path):
    folder = tmp_path / "private/pdfs"
    folder.mkdir(parents=True)
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(folder / "blank.pdf")
    with pytest.raises(ValueError, match="OCR"):
        e.extract_source("blank.pdf", "SRC_08", tmp_path)
    assert not (tmp_path / "private/sources").exists()
    with pytest.raises(ValueError, match="not a PDF"):
        e.extract_pdf(b"not a PDF")


@pytest.mark.parametrize("filename", ["https://www.sec.gov/filing.pdf", "../filing.pdf", "filing.html"])
def test_only_pdf_filenames_are_accepted(tmp_path, filename):
    with pytest.raises(ValueError, match="only its filename"):
        e.extract_source(filename, "SRC_04", tmp_path)
    assert not list(tmp_path.iterdir())
