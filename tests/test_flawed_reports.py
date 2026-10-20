import copy
import json
import shutil

import pytest
from pydantic import ValidationError

from src.benchmark.create_flawed_reports import create_flawed_reports, make_report
from src.benchmark.prepare import ROOT, assert_masked, check_report, load_agent_input, read, save
from src.benchmark.schemas import Packet, Report


PAIRS = read(ROOT / "private/pairs.json")["pairs"]


@pytest.mark.parametrize("pair", PAIRS, ids=[p["pair_id"] for p in PAIRS])
def test_paired_inputs_and_intended_error(pair):
    packet_path = ROOT / "public/evidence_packets" / (pair["packet_id"] + ".json")
    clean_path = ROOT / "public" / pair["clean_report_path"]
    flawed_path = ROOT / "public" / pair["flawed_report_path"]
    clean = load_agent_input(packet_path, clean_path, check_clean=False)
    flawed = load_agent_input(packet_path, flawed_path, check_clean=False)
    assert clean["evidence_packet"] == flawed["evidence_packet"]
    assert set(flawed) == {"evidence_packet", "initial_report"}
    encoded = json.dumps(flawed)
    for label in ("error_index", "defect_type", "clean_report_path", "flawed_report_path",
                  "expected", "injected", flawed_path.name, clean_path.name):
        assert label not in encoded
    with pytest.raises(ValueError, match="same public dataset"):
        load_agent_input(packet_path, flawed_path.parent.with_name("EP_9999") / flawed_path.name,
                         check_clean=False)
    # The packet is shared unchanged; validate the generated report here.
    assert_masked(flawed["initial_report"], read(ROOT / "private/aliases.json"))
    before, after = clean["initial_report"], flawed["initial_report"]
    assert make_report(before, pair) == after
    assert before["recommendation"] == after["recommendation"]
    target = pair["target_claim_id"]
    rationale_only = all(e["path"] == ["rationale"] for e in pair["changes"])
    assert (target is None) == rationale_only
    if "claim_id" in pair["expected"]:
        assert pair["expected"]["claim_id"] == target
    assert [c for c in before["claims"] if c["claim_id"] != target] == [
        c for c in after["claims"] if c["claim_id"] != target]
    # Reversing the private edits restores the clean report exactly.
    restored = copy.deepcopy(after)
    for edit in reversed(pair["changes"]):
        parent = restored
        for key in edit["path"][:-1]:
            parent = parent[key]
        assert parent[edit["path"][-1]] == edit["after"]
        parent[edit["path"][-1]] = copy.deepcopy(edit["before"])
    restored["report_id"] = before["report_id"]
    assert restored == before
    packet = Packet.model_validate(clean["evidence_packet"])
    errors = check_report(packet, Report.model_validate(after))["errors"]
    if pair["defect_type"] in {"arithmetic", "reporting_period"}:
        assert len(errors) == 1  # One numerical defect, never a combined report.
    else:
        assert not errors  # Semantic defects need evidence-based review.


def test_six_single_error_variants_per_packet():
    from collections import Counter
    assert len(PAIRS) == 90
    assert Counter(p["packet_id"] for p in PAIRS) == {
        f"EP_{i:04d}": 6 for i in range(1, 16)}
    assert len({p["pair_id"] for p in PAIRS}) == 90
    assert len({p["flawed_report_id"] for p in PAIRS}) == 90
    for packet_id in {p["packet_id"] for p in PAIRS}:
        variants = [p for p in PAIRS if p["packet_id"] == packet_id]
        assert {p["error_index"] for p in variants} == set(range(1, 7))
        assert {p["defect_type"] for p in variants} == {
            "arithmetic", "reporting_period", "direct_factual_contradiction",
            "material_omission", "citation_misattribution", "unsupported_inference"}
        assert len(list((ROOT / "public/reports" / packet_id).glob("error_*.json"))) == 6
    assert all(p["defect_type"] != "six_errors" for p in PAIRS)


def test_rebuild_is_repeatable_and_does_not_overwrite_reviewed_inputs(tmp_path):
    shutil.copytree(ROOT / "public", tmp_path / "public")
    for filename in ("pairs.json", "aliases.json"):
        save(tmp_path / "private" / filename, read(ROOT / "private" / filename))
    before = {p: p.read_bytes() for p in (tmp_path / "public").rglob("*.json")}
    assert len(create_flawed_reports(tmp_path)) == 90
    assert all(p.read_bytes() == value for p, value in before.items())
    changed_path = tmp_path / "public" / PAIRS[0]["flawed_report_path"]
    changed = read(changed_path)
    changed["rationale"] = "An existing revision."
    save(changed_path, changed)
    with pytest.raises(ValueError, match="Existing report differs"):
        create_flawed_reports(tmp_path)
    assert read(changed_path) == changed


def test_pair_paths_cannot_target_other_files(tmp_path):
    pairs = copy.deepcopy(PAIRS)
    pairs[0]["flawed_report_path"] = "../private/pairs.json"
    save(tmp_path / "private/pairs.json", {"pairs": pairs})
    save(tmp_path / "private/aliases.json", read(ROOT / "private/aliases.json"))
    with pytest.raises(ValueError, match="Pair paths"):
        create_flawed_reports(tmp_path)
    assert not (tmp_path / "public").exists()


def test_bad_edits_and_private_data_are_rejected(tmp_path):
    pair = copy.deepcopy(PAIRS[0])
    clean = read(ROOT / "public" / pair["clean_report_path"])
    pair["changes"][0]["before"] = "stale text"
    with pytest.raises(ValueError, match="Original differs"):
        make_report(clean, pair)
    pair["changes"][0]["path"] = ["recommendation"]
    with pytest.raises(ValueError, match="Only the target claim"):
        make_report(clean, pair)
    packet_path = tmp_path / "public/evidence_packets/EP_0001.json"
    report_path = tmp_path / "public/reports/EP_0001/clean.json"
    save(packet_path, read(ROOT / "public/evidence_packets/EP_0001.json"))
    clean["expected"] = "private answer"
    save(report_path, clean)
    with pytest.raises(ValidationError):
        load_agent_input(packet_path, report_path, check_clean=False)
    del clean["expected"]
    clean["claims"][0]["evidence_ids"] = ["EP_0002_E01"]
    save(report_path, clean)
    with pytest.raises(ValueError, match="citations"):
        load_agent_input(packet_path, report_path, check_clean=False)
    with pytest.raises(ValueError, match="same public dataset"):
        load_agent_input(ROOT / "private/packets/EP_0001.json", report_path, check_clean=False)


@pytest.mark.parametrize("pair", [p for p in PAIRS
    if p["error_index"] == 1 and int(p["packet_id"][3:]) <= 8],
    ids=lambda p: p["packet_id"])
def test_replaced_number_errors_are_single_evidence_backed_contradictions(pair):
    assert pair["defect_type"] == "direct_factual_contradiction"
    clean = read(ROOT / "public" / pair["clean_report_path"])
    flawed = read(ROOT / "public" / pair["flawed_report_path"])
    packet = read(ROOT / "public/evidence_packets" / (pair["packet_id"] + ".json"))
    assert len(pair["changes"]) == 1
    assert pair["changes"][0]["path"][-1] == "text"
    assert clean["rationale"] == flawed["rationale"]
    assert [c["check_spec"] for c in clean["claims"]] == [
        c["check_spec"] for c in flawed["claims"]]
    for source in pair["expected"]["source_quotes"]:
        evidence = next(e["text"] for e in packet["evidence"]
                        if e["evidence_id"] == source["evidence_id"])
        assert " ".join(source["quote"].split()) in " ".join(evidence.split())
    assert not (ROOT / "public/reports" / pair["packet_id"] /
                "error_01_wrong_number.json").exists()


def test_single_fact_omission_retains_independent_earnings_offset():
    pair = next(p for p in PAIRS if p["pair_id"] == "PAIR_0032")
    flawed = read(ROOT / "public" / pair["flawed_report_path"])
    claim = next(c for c in flawed["claims"] if c["claim_id"] == "C4")
    assert "$1.4 billion increase from structural cost savings" in claim["text"]
    assert "structural cost savings" in flawed["rationale"]
    assert "advantaged volume growth" not in claim["text"] + flawed["rationale"]


def test_joint_venture_contradiction_preserves_partner_priority_risk():
    pair = next(p for p in PAIRS if p["pair_id"] == "PAIR_0044")
    flawed = read(ROOT / "public" / pair["flawed_report_path"])
    claim = next(c for c in flawed["claims"] if c["claim_id"] == "C5")
    assert "has full control" in claim["text"]
    assert "partners may not share business priorities" in claim["text"]
    assert "differing joint venture partner priorities" in flawed["rationale"]
    assert "always share" not in json.dumps(flawed)


@pytest.mark.parametrize("pair_id, retained, removed", [
    ("PAIR_0022", "a higher average selling price per unit", "a lower average selling price per unit"),
    ("PAIR_0078", "a $1.4 billion decrease from structural cost savings", "a $1.4 billion increase from structural cost savings"),
])
def test_contradiction_replaces_original_assertion(pair_id, retained, removed):
    pair = next(p for p in PAIRS if p["pair_id"] == pair_id)
    flawed = read(ROOT / "public" / pair["flawed_report_path"])
    text = next(c["text"] for c in flawed["claims"] if c["claim_id"] == pair["target_claim_id"])
    assert retained in text
    assert removed not in text


def test_rationale_targets_cannot_be_mislabeled_as_claims():
    pair = copy.deepcopy(next(p for p in PAIRS if p["target_claim_id"] is None))
    pair["target_claim_id"] = "C1"
    with pytest.raises(ValueError, match="Rationale-only"):
        make_report(read(ROOT / "public" / pair["clean_report_path"]), pair)
