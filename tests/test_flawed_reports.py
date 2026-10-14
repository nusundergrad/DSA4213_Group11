import copy
import json
from decimal import Decimal
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
    assert_masked(flawed, read(ROOT / "private/aliases.json"))
    before, after = clean["initial_report"], flawed["initial_report"]
    assert make_report(before, pair) == after
    assert before["recommendation"] == after["recommendation"]
    assert before["claims"][1:] == after["claims"][1:]
    assert before["claims"][0]["evidence_ids"] == after["claims"][0]["evidence_ids"]
    spec = after["claims"][0]["check_spec"]
    packet = Packet.model_validate(clean["evidence_packet"])
    result = check_report(packet, Report.model_validate(after))
    if pair["defect_type"] == "reporting_period":
        assert spec["from_period"]["label"] == "FY2023"
        assert spec["to_period"]["label"] == "FY2024"
        assert spec["value"] == before["claims"][0]["check_spec"]["value"]
        assert any("ambiguous/missing" in note for note in result["human_review"])
    else:
        assert result["errors"]  # strict clean validation still rejects these
        with pytest.raises(ValueError, match="asserted"):
            load_agent_input(packet_path, flawed_path)
        if pair["defect_type"] == "wrong_number":
            old = next(f for f in packet.facts if f.metric == spec["metric"]
                       and f.period.model_dump(mode="json") == spec["from_period"])
            actual = (Decimal(pair["injected"]["value"]) - Decimal(old.value)) / Decimal(old.value) * 100
            assert abs(actual - Decimal(spec["value"])) <= Decimal("0.01")
        else:
            assert Decimal(spec["value"]) - Decimal(pair["expected"]["growth_percent"]) == 10


def test_rebuild_is_repeatable_and_does_not_overwrite_reviewed_inputs(tmp_path):
    shutil.copytree(ROOT / "public", tmp_path / "public")
    for filename in ("pairs.json", "aliases.json"):
        save(tmp_path / "private" / filename, read(ROOT / "private" / filename))
    before = {p: p.read_bytes() for p in (tmp_path / "public").rglob("*.json")}
    assert len(create_flawed_reports(tmp_path)) == 6
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
