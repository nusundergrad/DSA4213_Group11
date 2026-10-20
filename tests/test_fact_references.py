import copy

import pytest
from pydantic import ValidationError

from src.benchmark.prepare import ROOT, check_report, load_agent_input, read, save
from src.benchmark.schemas import Packet, Report


def inputs(packet_id="EP_0002"):
    packet = Packet.model_validate(read(ROOT / "public/evidence_packets" / (packet_id + ".json")))
    report = Report.model_validate(read(ROOT / "public/reports" / packet_id / "clean.json"))
    return packet, report


@pytest.mark.parametrize("field,value,message", [
    ("fact_id", "EP_9999_F01", "unknown fact ID"),
    ("metric", "another_metric", "metric, period or unit mismatch"),
    ("unit", "USD_million", "metric, period or unit mismatch"),
])
def test_numeric_reference_checks(field, value, message):
    packet, report = inputs()
    setattr(report.claims[3].check_spec, field, value)
    assert any(message in error for error in check_report(packet, report)["errors"])


def test_parent_evidence_and_period_must_match():
    packet, report = inputs()
    report.claims[3].evidence_ids = ["EP_0002_E01"]
    assert any("outside the cited evidence" in error for error in check_report(packet, report)["errors"])
    packet, report = inputs()
    report.claims[3].check_spec.period.label = "FY2024"
    assert any("period" in error for error in check_report(packet, report)["errors"])


def test_percentage_references_have_order_and_require_both_ids():
    packet, report = inputs("EP_0001")
    spec = report.claims[0].check_spec
    spec.from_fact_id, spec.to_fact_id = spec.to_fact_id, spec.from_fact_id
    assert any("period" in error for error in check_report(packet, report)["errors"])
    data = report.model_dump(mode="json")
    del data["claims"][0]["check_spec"]["to_fact_id"]
    with pytest.raises(ValidationError, match="Supply both"):
        Report.model_validate(data)


def test_explicit_ids_resolve_duplicate_metric_mappings_and_reject_incompatible_units():
    packet, report = inputs("EP_0001")
    duplicate = packet.facts[0].model_copy(deep=True)
    duplicate.fact_id = "EP_0001_F99"
    packet.facts.append(duplicate)
    assert not check_report(packet, report, require_fact_ids=True)["errors"]
    packet.facts[0].unit = "USD_billion"
    assert any("incompatible units" in error for error in check_report(packet, report)["errors"])


def test_old_model_responses_remain_readable_but_new_reports_require_ids():
    packet, report = inputs("EP_0001")
    data = report.model_dump(mode="json")
    for claim in data["claims"]:
        spec = claim["check_spec"]
        if spec:
            spec.pop("from_fact_id", None)
            spec.pop("to_fact_id", None)
    legacy = Report.model_validate(data)
    assert not check_report(packet, legacy)["errors"]
    assert any("legacy" in note for note in check_report(packet, legacy)["human_review"])
    assert any("requires fact IDs" in error for error in check_report(packet, legacy, require_fact_ids=True)["errors"])


def test_paired_loader_accepts_period_error_but_rejects_broken_fact_links(tmp_path):
    packet_path = tmp_path / "public/evidence_packets/EP_0001.json"
    report_path = tmp_path / "public/reports/EP_0001/error_02_reporting_period.json"
    save(packet_path, read(ROOT / "public/evidence_packets/EP_0001.json"))
    report = read(ROOT / "public/reports/EP_0001/error_02_reporting_period.json")
    save(report_path, report)
    assert load_agent_input(packet_path, report_path, check_clean=False)
    report["claims"][0]["check_spec"]["from_fact_id"] = "EP_9999_F01"
    save(report_path, report)
    with pytest.raises(ValueError, match="unknown facts"):
        load_agent_input(packet_path, report_path, check_clean=False)


def test_all_existing_reports_have_references_without_changing_the_error():
    pairs = {p["flawed_report_path"]: p for p in read(ROOT / "private/pairs.json")["pairs"]}
    for packet_id in ("EP_0001", "EP_0002"):
        packet, clean = inputs(packet_id)
        assert not check_report(packet, clean, require_fact_ids=True)["errors"]
        references = {c.claim_id: c.check_spec.model_dump() if c.check_spec else None for c in clean.claims}
        for path in (ROOT / "public/reports" / packet_id).glob("error_*.json"):
            report = Report.model_validate(read(path))
            for claim in report.claims:
                if claim.check_spec:
                    spec = claim.check_spec.model_dump()
                    fields = ["fact_id"] if spec["kind"] == "numeric" else ["from_fact_id", "to_fact_id"]
                    assert all(spec[field] == references[claim.claim_id][field] for field in fields)
            pair = pairs[f"reports/{packet_id}/{path.name}"]
            errors = check_report(packet, report, require_fact_ids=True)["errors"]
            if pair["defect_type"] in {"arithmetic", "reporting_period"}:
                assert errors
            else:
                # Contradictions and other semantic defects retain valid numerical references.
                assert not errors
