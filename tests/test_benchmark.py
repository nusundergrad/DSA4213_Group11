import copy
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest
from pydantic import ValidationError

from src.benchmark import prepare as p
from src.benchmark.schemas import Packet, Report


@pytest.fixture
def dataset(tmp_path):
    shutil.copytree(p.ROOT / "private", tmp_path / "private",
                    ignore=shutil.ignore_patterns("attempts", "__pycache__"))
    packet = p.prepare(tmp_path, tmp_path / "private/packets/EP_0001.json")
    return tmp_path, packet


@pytest.fixture
def report(dataset):
    packet = dataset[1]
    return Report.model_validate({"report_id": "R_test", "recommendation": "HOLD", "claims": [
        {"claim_id": "C1", "text": "Net sales were 416161 million USD in FY2025.",
         "evidence_ids": ["EP_0001_E01"], "check_spec": {"kind": "numeric", "metric": "net_sales",
          "period": packet.facts[0].period.model_dump(mode="json"), "value": "416161", "unit": "USD_million"}},
        {"claim_id": "C2", "text": "Services sales increased.", "evidence_ids": ["EP_0001_E01"], "check_spec": None},
        {"claim_id": "C3", "text": "Economic conditions can affect demand.", "evidence_ids": ["EP_0001_E03"], "check_spec": None}],
        "rationale": "Sales growth is balanced against demand risk in this limited evidence.",
        "confidence_statement": "The supplied evidence supports this assessment with limitations."})


def test_masking_and_source_traceability(dataset):
    root, packet = dataset
    aliases = p.read(root / "private/aliases.json")
    assert p.mask("APPLE apple iPad Air pineapple 416161 2025-09-27", aliases) == (
        "COMPANY_01 COMPANY_01 PRODUCT_02 pineapple 416161 2025-09-27")
    original = p.read(root / "private/packets/EP_0001.json")
    assert [f.value for f in packet.facts] == [f["value"] for f in original["facts"]]
    assert packet.facts[0].period.model_dump(mode="json") == original["facts"][0]["period"]
    assert "source_url" not in packet.model_dump_json() and "locator" not in packet.model_dump_json()
    p.assert_masked(packet.model_dump(mode="json"), aliases)
    p.prepare(root, root / "private/packets/EP_0002.json")
    original["evidence"][0]["text"] += " invented"
    p.save(root / "private/packets/EP_0001.json", original)
    with pytest.raises(ValueError, match="excerpt mismatch"):
        p.prepare(root, root / "private/packets/EP_0001.json")


def test_checks_and_structural_boundary(dataset, report):
    packet = dataset[1]
    assert not p.check_report(packet, report)["errors"]
    report.claims[0].check_spec.value = "416162"
    assert p.check_report(packet, report)["errors"]
    report.claims[0].evidence_ids = ["EP_9999_E01"]
    assert Report.model_validate_json(report.model_dump_json())  # representable future flawed case
    assert "citation" in p.check_report(packet, report)["errors"][0]
    data = report.model_dump(mode="json")
    data["company"] = "private identity"
    with pytest.raises(ValidationError):
        Report.model_validate(data)
    del data["company"]
    data["claims"][1]["claim_id"] = "C1"
    with pytest.raises(ValidationError):
        Report.model_validate(data)


def test_source_text_integrity_needs_only_txt_and_json(dataset):
    root, packet = dataset
    assert {path.suffix for path in (root / "private/sources").iterdir()} == {".txt", ".json"}
    source = root / "private/sources/SRC_01.txt"
    source.write_bytes(source.read_bytes() + b" changed")
    with pytest.raises(ValueError, match="recorded hash"):
        p.prepare(root, root / "private/packets/EP_0001.json")


def test_percentage_and_ambiguous_checks(dataset, report):
    packet = dataset[1]
    data = report.model_dump(mode="json")
    data["claims"][0]["check_spec"] = {"kind": "percentage_change", "metric": "net_sales",
        "from_period": packet.facts[1].period.model_dump(mode="json"),
        "to_period": packet.facts[0].period.model_dump(mode="json"), "value": "6.43", "unit": "percent"}
    candidate = Report.model_validate(data)
    assert not p.check_report(packet, candidate)["errors"]
    candidate.claims[0].check_spec.value = "20"
    assert p.check_report(packet, candidate)["errors"]
    packet.facts[1].value = "0"
    assert "zero denominator" in p.check_report(packet, candidate)["human_review"][0]
    report.claims[0].check_spec.unit = "USD"
    assert "unit mapping" in p.check_report(packet, report)["human_review"][0]
    report.claims[0].check_spec.period.label = "FY2020"
    assert "period" in p.check_report(packet, report)["human_review"][0]


@pytest.mark.parametrize("outcome", ["valid", "malformed", "http_error", "identity_leak", "arithmetic"])
def test_generation_preserves_attempts(dataset, report, monkeypatch, outcome):
    root, packet = dataset
    monkeypatch.setattr(p, "uuid4", lambda: SimpleNamespace(hex="test"))
    payload = report.model_dump(mode="json")
    if outcome == "identity_leak":
        payload["rationale"] = "Microsoft is a good business."
    if outcome == "arithmetic":
        payload["claims"][0]["check_spec"]["value"] = "1"
    content = "not JSON" if outcome == "malformed" else json.dumps(payload)
    raw = json.dumps({"model": "provider/model", "usage": {"total_tokens": 10},
        "choices": [{"finish_reason": "stop", "message": {"content": content}}]}).encode()
    calls = []

    def response(request, timeout):
        calls.append(request)
        sent = json.loads(request.data)
        assert sent["provider"]["allow_fallbacks"] is False
        assert sent["temperature"] == 0
        p.assert_masked(sent, p.read(root / "private/aliases.json"))
        assert "source_url" not in request.data.decode()
        if outcome == "http_error":
            raise HTTPError(request.full_url, 429, "rate limited", {}, BytesIO(b'{"error":"quota"}'))
        return BytesIO(raw)

    monkeypatch.setattr(p, "urlopen", response)
    folder, status = p.generate(root, packet, "provider/model", "test-secret")
    assert len(calls) == 1
    expected = "needs_review" if outcome == "valid" else "invalid" if outcome == "arithmetic" else "failed"
    assert status == expected
    saved = p.read(folder / "attempt.json")
    assert saved["raw_response"] and "test-secret" not in json.dumps(saved)
    assert not (root / "public/reports").exists()
    if status == "needs_review":
        review = p.read(folder / "review.json")
        assert review["content_label"] is None
        assert set(review["reviewers"]) == {"reviewer_1", "reviewer_2"}
        assert all(v["status"] == "pending" for v in review["reviewers"].values())


def test_loader_separation_and_generation_gates(dataset, report, monkeypatch):
    root, packet = dataset
    monkeypatch.setattr(p, "urlopen", lambda *a, **kw: pytest.fail("unexpected model call"))
    for model in (None, "openrouter/free", "openrouter/auto"):
        with pytest.raises(ValueError, match="explicit model"):
            p.generate(root, packet, model, "key")
    with pytest.raises(ValueError, match="Identifying"):
        p.generate(root, packet, "provider/model", "key", "Use Apple financials")
    report_path = root / "public/reports/R_test.json"
    p.save(report_path, report.model_dump(mode="json"))  # simulates manual publication
    packet_path = root / "public/evidence_packets/EP_0001.json"
    result = p.load_agent_input(packet_path, report_path)
    assert set(result) == {"evidence_packet", "initial_report"}
    with pytest.raises(ValueError, match="same public dataset"):
        p.load_agent_input(root / "private/packets/EP_0001.json", report_path)


def test_imports_have_no_side_effects():
    code = ("import sys, urllib.request; urllib.request.urlopen = lambda *a, **k: sys.exit(9); "
            "import src.benchmark.prepare; assert 'src.graph' not in sys.modules; "
            "assert 'src.agent' not in sys.modules; assert 'dotenv' not in sys.modules")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0 and not result.stdout, result.stderr
