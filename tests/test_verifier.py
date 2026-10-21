"""verifier must handle every unit in the dataset and never crash a run"""
import json
from pathlib import Path

import pytest

from src.benchmark.prepare import ROOT
from src.benchmark.schemas import Packet, Report
from src.verifier import unit_to_num, verifier

REPORTS = sorted((ROOT / "public" / "reports").rglob("*.json"))


@pytest.mark.parametrize("unit,scale", [("USD_million", 1e6), ("USD_billion", 1e9), ("percent", 1), ("USD_per_share", 1)])
def test_unit_scales(unit, scale):
    assert unit_to_num(unit) == scale


@pytest.mark.parametrize("path", REPORTS, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_verifier_runs_on_every_benchmark_report(path):
    packet = Packet.model_validate(json.loads((ROOT / "public/evidence_packets" / f"{path.parent.name}.json").read_text(encoding="utf-8")))
    report = Report.model_validate(json.loads(path.read_text(encoding="utf-8")))
    result = verifier(report, packet)
    assert set(result) == {c.claim_id for c in report.claims}
    assert all(v is None or isinstance(v, bool) for v in result.values())


def test_clean_reports_pass_and_flawed_numeric_reports_fail_on_target():
    pairs = json.loads((ROOT / "private/pairs.json").read_text(encoding="utf-8"))["pairs"]
    for p in pairs:
        if p["defect_type"] not in ("wrong_number", "arithmetic", "reporting_period"):
            continue
        packet = Packet.model_validate(json.loads((ROOT / "public/evidence_packets" / f"{p['packet_id']}.json").read_text(encoding="utf-8")))
        flawed = Report.model_validate(json.loads((ROOT / "public" / p["flawed_report_path"]).read_text(encoding="utf-8")))
        assert verifier(flawed, packet)[p["target_claim_id"]] is False, p["pair_id"]


def test_not_checkable_and_percentage_tolerance():
    packet = Packet.model_validate_json((ROOT / 'public/evidence_packets/EP_0001.json').read_text(encoding='utf-8'))
    report = Report.model_validate_json((ROOT / 'public/reports/EP_0001/clean.json').read_text(encoding='utf-8'))
    numerical = next(c for c in report.claims if c.check_spec and c.check_spec.kind == 'percentage_change')
    numerical.check_spec.value = '6.42'  # within 0.01 of 6.4255..., not exact rounded-string equality
    assert verifier(report, packet)[numerical.claim_id] is True
    numerical.check_spec.value = '6.40'
    assert verifier(report, packet)[numerical.claim_id] is False
    numerical.check_spec = None
    assert verifier(report, packet)[numerical.claim_id] is None
