import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import httpx

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
         "evidence_ids": ["EP_0001_E01"], "check_spec": {"kind": "numeric", "metric": "net_sales", "fact_id": "EP_0001_F01",
          "period": packet.facts[0].period.model_dump(mode="json"), "value": "416161", "unit": "USD_million"}},
        {"claim_id": "C2", "text": "Services sales increased.", "evidence_ids": ["EP_0001_E01"], "check_spec": None},
        {"claim_id": "C3", "text": "Economic conditions can affect demand.", "evidence_ids": ["EP_0001_E03"], "check_spec": None}],
        "rationale": "Sales growth is balanced against demand risk in this limited evidence."})


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
    for field in ("company", "confidence_statement"):
        data[field] = "Not part of the report contract"
        with pytest.raises(ValidationError):
            Report.model_validate(data)
        del data[field]
    data["claims"][1]["claim_id"] = "C1"
    with pytest.raises(ValidationError):
        Report.model_validate(data)


def test_masking_names_split_across_lines():
    aliases = {"More Personal Computing": "SEGMENT_03"}
    original = {"text": "More Personal \nComputing 69% FY2025", "metric": "More\tPersonal Computing"}
    masked = {"text": "SEGMENT_03 69% FY2025", "metric": "SEGMENT_03"}
    assert p.mask(original, aliases) == masked
    with pytest.raises(ValueError, match="Identifying"):
        p.assert_masked(original, aliases)
    p.assert_masked(masked, aliases)


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
    assert any("zero denominator" in note for note in p.check_report(packet, candidate)["human_review"])
    report.claims[0].check_spec.fact_id = None  # old reports still use the legacy lookup
    report.claims[0].check_spec.unit = "USD"
    assert "unit mapping" in p.check_report(packet, report)["human_review"][0]
    report.claims[0].check_spec.period.label = "FY2020"
    assert "period" in p.check_report(packet, report)["human_review"][0]


@pytest.mark.parametrize("outcome", ["valid", "malformed", "http_error", "identity_leak", "arithmetic", "malformed_api", "truncated", "changed_id", "missing_fact_id"])
def test_generation_preserves_attempts(dataset, report, monkeypatch, outcome):
    root, packet = dataset
    monkeypatch.setattr(p, "uuid4", lambda: SimpleNamespace(hex="test"))
    payload = report.model_dump(mode="json")
    if outcome == "identity_leak":
        payload["rationale"] = "Microsoft is a good business."
    if outcome == "arithmetic":
        payload["claims"][0]["check_spec"]["value"] = "1"
    if outcome == "missing_fact_id":
        del payload["claims"][0]["check_spec"]["fact_id"]
    if outcome == "changed_id":
        payload["report_id"] = "R_wrong"
    content = "not JSON" if outcome == "malformed" else json.dumps(payload)
    raw = json.dumps({"id": "test", "object": "chat.completion", "created": 1, "system_fingerprint": None,
        "model": "provider/model", "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        "choices": [{"index": 0, "finish_reason": "length" if outcome == "truncated" else "stop",
                     "message": {"role": "assistant", "content": content}}]}).encode()
    if outcome == "malformed_api":
        raw = b"not JSON"
    if outcome == "http_error":
        raw = b'{"error":{"message":"quota","code":429}}'
    calls = []

    def response(self, request):
        calls.append(request)
        sent = json.loads(request.content)
        assert sent["provider"]["allow_fallbacks"] is False
        assert sent["temperature"] == 0
        p.assert_masked(sent, p.read(root / "private/aliases.json"))
        assert "source_url" not in request.content.decode()
        return httpx.Response(429 if outcome == "http_error" else 200, content=raw,
                              headers={"Content-Type": "application/json"}, request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", response)
    folder, status = p.generate(root, packet, "provider/model", "test-secret")
    assert len(calls) == 1
    expected = "needs_review" if outcome == "valid" else "invalid" if outcome in {"arithmetic", "missing_fact_id"} else "failed"
    saved = p.read(folder / "attempt.json")
    assert status == expected, saved.get("error")
    assert saved["raw_response"] == raw.decode()
    assert saved["request"] == json.loads(calls[0].content)
    assert "test-secret" not in json.dumps(saved)
    errors = {"http_error": "quota", "identity_leak": "Identifying",
              "truncated": "did not finish", "changed_id": "changed the assigned"}
    if outcome in errors:
        assert errors[outcome] in saved["error"]
    assert not (root / "public/reports").exists()
    assert not (folder / "review.json").exists()


def test_loader_separation_and_generation_gates(dataset, report, monkeypatch):
    root, packet = dataset
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", lambda *a, **kw: pytest.fail("unexpected model call"))
    for model in (None, "openrouter/free", "openrouter/auto"):
        with pytest.raises(ValueError, match="explicit model"):
            p.generate(root, packet, model, "key")
    with pytest.raises(ValueError, match="Identifying"):
        p.generate(root, packet, "provider/model", "key", "Use Apple financials")
    report_path = root / "public/reports/EP_0001/clean.json"
    p.save(report_path, report.model_dump(mode="json"))  # simulates manual publication
    packet_path = root / "public/evidence_packets/EP_0001.json"
    result = p.load_agent_input(packet_path, report_path)
    assert set(result) == {"evidence_packet", "initial_report"}
    with pytest.raises(ValueError, match="same public dataset"):
        p.load_agent_input(root / "private/packets/EP_0001.json", report_path)


def test_imports_have_no_side_effects():
    code = ("import sys, urllib.request; urllib.request.urlopen = lambda *a, **k: sys.exit(9); "
            "import src.benchmark.prepare, src.benchmark.create_flawed_reports; assert 'src.graph' not in sys.modules; "
            "assert 'src.agent' not in sys.modules; assert 'dotenv' not in sys.modules")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0 and not result.stdout, result.stderr
