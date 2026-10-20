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
    packet = Packet.model_validate(json.loads((ROOT / "public/evidence_packets" / f"{path.parent.name}.json").read_text()))
    report = Report.model_validate(json.loads(path.read_text()))
    result = verifier(report, packet)
    assert set(result) == {c.claim_id for c in report.claims}
    assert all(isinstance(v, bool) for v in result.values())


def test_clean_reports_pass_and_flawed_numeric_reports_fail_on_target():
    pairs = json.loads((ROOT / "private/pairs.json").read_text())["pairs"]
    for p in pairs:
        if p["defect_type"] not in ("wrong_number", "arithmetic", "reporting_period"):
            continue
        packet = Packet.model_validate(json.loads((ROOT / "public/evidence_packets" / f"{p['packet_id']}.json").read_text()))
        flawed = Report.model_validate(json.loads((ROOT / "public" / p["flawed_report_path"]).read_text()))
        assert verifier(flawed, packet)[p["target_claim_id"]] is False, p["pair_id"]
