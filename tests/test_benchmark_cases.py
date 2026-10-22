"""answer keys built from the real data/benchmark/private/pairs.json"""
import json

import pytest

from schema import DEFECT_TYPES
from benchmark_cases import DEFAULT_ROOT, build_cases, load_agent_input_for, load_clean_report

CASES, MANIFEST = build_cases()


def test_counts_and_defect_types():
    flawed = [c for c in CASES.values() if c.is_flawed]
    controls = [c for c in CASES.values() if not c.is_flawed]
    pairs = json.loads((DEFAULT_ROOT / "private" / "pairs.json").read_text(encoding="utf-8"))["pairs"]
    assert len(flawed) == len(pairs)
    assert len(controls) == len({p["clean_report_id"] for p in pairs})   # one control per clean report, not per pair
    assert {c.defect["defect_type"] for c in flawed} == {p["defect_type"] for p in pairs}
    assert {c.defect["defect_type"] for c in flawed} <= set(DEFECT_TYPES)  # metrics only reports known types
    for c in flawed:
        assert c.defect["target_claim_id"] is None or c.defect["target_claim_id"].startswith("C")
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


def test_run_list_covers_every_report_per_situation_and_tone_subset_gets_triplets():
    from make_run_list import make_run_list
    assert {r['tone'] for r in make_run_list(MANIFEST, cases=CASES)} == {'neutral'}
    runs = make_run_list(MANIFEST, cases=CASES, tone_variants=True)
    neutral = [r for r in runs if r["tone"] == "neutral"]
    assert len(neutral) == len(CASES) * 4                                  # situations 0-3
    for r in runs:
        assert (DEFAULT_ROOT / "public" / "reports" / r["evidence_packet"] / (r["report"] + ".json")).is_file()
    subset = [c for c in CASES.values() if c.confidence_subset]
    assert len([c for c in subset if c.is_flawed]) == 12                   # the planned 12-pair subset
    assert len(runs) == len(neutral) + len(subset) * 4 * 2                 # + under/overconfident for each
    assert len(make_run_list(MANIFEST, (2,), ["EP_0001"], CASES, tone_variants=False)) == 7


def test_default_confidence_pairs_are_deterministic_and_cover_every_defect_type():
    from benchmark_cases import default_confidence_pairs
    pairs = json.loads((DEFAULT_ROOT / "private" / "pairs.json").read_text(encoding="utf-8"))["pairs"]
    chosen = default_confidence_pairs(pairs)
    assert chosen == default_confidence_pairs(list(reversed(pairs))) and len(chosen) == 12
    assert {p["defect_type"] for p in pairs if p["pair_id"] in chosen} == {p["defect_type"] for p in pairs}
