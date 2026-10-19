"""answer keys built from the real data/benchmark/private/pairs.json"""
import json

import pytest

from benchmark_cases import DEFAULT_ROOT, build_cases, load_agent_input_for, load_clean_report

CASES, MANIFEST = build_cases()


def test_counts_and_defect_types():
    flawed = [c for c in CASES.values() if c.is_flawed]
    controls = [c for c in CASES.values() if not c.is_flawed]
    assert len(flawed) == 6 and len(controls) == 2          # one control per clean report, not per pair
    assert {c.defect["defect_type"] for c in flawed} == {"wrong_number", "reporting_period", "arithmetic"}
    for c in flawed:
        assert c.defect["target_claim_id"] == "C1"
        assert c.defect["detection_criterion"] and c.defect["correction_criterion"] and c.defect["materiality_criterion"]
    assert all(c.defect is None for c in controls)


def test_case_ids_are_opaque_and_unique():
    ids = list(CASES)
    assert len(set(ids)) == len(ids)
    for cid in ids:
        assert cid.startswith("CASE_") and not any(w in cid.lower() for w in ("clean", "flawed", "error", "wrong", "arith"))


@pytest.mark.parametrize("cid", list(CASES))
def test_manifest_points_to_the_right_public_report(cid):
    m = MANIFEST[cid]
    report = json.loads((DEFAULT_ROOT / "public" / m["report_path"]).read_text(encoding="utf-8"))
    assert "CASE_" + report["report_id"].removeprefix("R_") == cid
    assert load_clean_report(m)["claims"]


@pytest.mark.parametrize("cid", list(CASES))
def test_agent_input_has_no_labels(cid):
    payload = load_agent_input_for(cid, MANIFEST)
    assert set(payload) == {"evidence_packet", "initial_report"}
    text = json.dumps(payload)
    for leak in ("detection_criterion", "defect_type", "injected", "error_0", "clean.json", "PAIR_"):
        assert leak not in text


def test_tone_subset_flag():
    cases, _ = build_cases(confidence_pair_ids={"PAIR_0003"})
    assert sum(c.confidence_subset for c in cases.values()) == 2      # that flawed case + its shared control
