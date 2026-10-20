"""Build evaluation-only answer keys (``Case``) from the benchmark's private ``pairs.json``.

Outputs two eval-only things, neither of which may reach an agent:

* ``cases``    - case_id -> ``Case`` (content label, defect criteria, expected/injected values)
* ``manifest`` - case_id -> public paths of the packet, the report to feed the agents, and the
                 clean counterpart (needed by ``auto_scoring`` to tell whether a defect was fixed)

Case IDs are opaque (derived from the report ID). The clean report of a packet is reused by up to
three flawed copies, so there is ONE control case per clean report, not one per pair; its
``pair_id`` is ``CONTROL_<packet_id>``. Report that sharing as a limitation: the controls are not
independent.

CLI (writes private eval files; keep them out of agent-visible folders):
    python src/evaluation/benchmark_cases.py --out outputs/eval_private
"""
from __future__ import annotations

import json
from pathlib import Path

from schema import Case, write_jsonl

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "benchmark"
MATERIALITY = "The unresolved defect is relied on to support an accepted recommendation."
DEFECT_KEYS = ("target_claim_id", "defect_type", "evidence_ids", "expected", "injected", "explanation",
               "detection_criterion", "correction_criterion")


def case_id_for(report_id: str) -> str:
    return "CASE_" + report_id.removeprefix("R_")


def default_confidence_pairs(pairs, n=12):
    """The planned 12-pair tone subset: round-robin over defect types (then pair ID), so every defect
    type is represented before any type is repeated. Deterministic, so every teammate gets the same set."""
    by_type = {}
    for p in sorted(pairs, key=lambda p: p["pair_id"]):
        by_type.setdefault(p["defect_type"], []).append(p["pair_id"])
    picked, queues = [], [by_type[t] for t in sorted(by_type)]
    while len(picked) < min(n, len(pairs)):
        for q in queues:
            if q and len(picked) < n:
                picked.append(q.pop(0))
    return set(picked)


def build_cases(root=DEFAULT_ROOT, confidence_pair_ids=None):
    """confidence_pair_ids: pair IDs whose cases belong to the tone subset. None (default) selects the
    planned 12 pairs with ``default_confidence_pairs``; pass an empty set for no tone subset."""
    root = Path(root)
    pairs = json.loads((root / "private" / "pairs.json").read_text(encoding="utf-8"))["pairs"]
    if confidence_pair_ids is None:
        confidence_pair_ids = default_confidence_pairs(pairs)
    cases, manifest = {}, {}
    for p in pairs:
        packet_path = f"evidence_packets/{p['packet_id']}.json"
        cid = case_id_for(p["clean_report_id"])
        if cid not in cases:
            cases[cid] = Case(cid, "CONTROL_" + p["packet_id"], "unmodified", False, None)
            manifest[cid] = dict(packet_path=packet_path, report_path=p["clean_report_path"],
                                 clean_report_path=p["clean_report_path"])
        fid = case_id_for(p["flawed_report_id"])
        defect = {k: p[k] for k in DEFECT_KEYS} | {"materiality_criterion": MATERIALITY}
        in_subset = p["pair_id"] in confidence_pair_ids
        cases[fid] = Case(fid, p["pair_id"], "injected_error", in_subset, defect)
        manifest[fid] = dict(packet_path=packet_path, report_path=p["flawed_report_path"],
                             clean_report_path=p["clean_report_path"])
        if in_subset:
            cases[cid].confidence_subset = True
    return cases, manifest


def load_clean_report(manifest_entry, root=DEFAULT_ROOT) -> dict:
    return json.loads((Path(root) / "public" / manifest_entry["clean_report_path"]).read_text(encoding="utf-8"))


def load_agent_input_for(case_id, manifest, root=DEFAULT_ROOT):
    """Public packet + report for the runner. Uses the benchmark loader (check_clean=False for
    clean AND flawed cases, per docs/benchmark.md) so no labels or filenames reach the agent."""
    from src.benchmark.prepare import load_agent_input  # repo-root import
    m = manifest[case_id]
    return load_agent_input(Path(root) / "public" / m["packet_path"], Path(root) / "public" / m["report_path"],
                            check_clean=False)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--out", required=True, help="eval-only output folder")
    args = ap.parse_args()
    cases, manifest = build_cases(args.root)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "cases.jsonl", cases.values())
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"{len(cases)} cases ({sum(c.is_flawed for c in cases.values())} flawed) -> {out}")
