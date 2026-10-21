"""Write the list of cases ``graph.run_batch`` should execute (every benchmark report x situation x tone).

    python src/evaluation/make_run_list.py --out output/cases_all.json
    python src/evaluation/make_run_list.py --out output/cases_pilot.json --packets EP_0001 EP_0002 --situations 0 1 3
    python src/evaluation/make_run_list.py --out output/cases_neutral.json --no-tone-variants

Situations: 0 baseline, 1 debate, 2 verification, 3 hybrid. Every report is run with the neutral confidence
sentence. Reports in the 12-pair confidence subset (and the clean report their pair shares) are also run
with the underconfident and overconfident sentences, because Evaluation 2 needs matched triplets.
The list holds only public names (packet, report file, situation, tone), never labels. Report file names do
reveal the injected error to a human reader, but ``run_batch`` never sends them to a model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark_cases import build_cases
from schema import TONES


def make_run_list(manifest: dict, situations=(0, 1, 2, 3), packets=None, cases=None, tone_variants=False) -> list:
    entries, seen = [], set()
    for case_id, m in manifest.items():
        packet = Path(m["packet_path"]).stem
        report = Path(m["report_path"]).stem
        if (packets and packet not in packets) or (packet, report) in seen:
            continue
        seen.add((packet, report))
        in_subset = bool(tone_variants and cases and cases[case_id].confidence_subset)
        tones = TONES if in_subset else ("neutral",)
        entries += [dict(evidence_packet=packet, report=report, situation=s, tone=t)
                    for s in situations for t in tones]
    return sorted(entries, key=lambda e: (e["evidence_packet"], e["report"], e["situation"], e["tone"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--situations", nargs="+", type=int, default=[0, 1, 2, 3])
    ap.add_argument("--packets", nargs="*", help="limit to these packet IDs, e.g. EP_0001 EP_0002")
    ap.add_argument("--no-tone-variants", action="store_true", help="neutral tone only")
    ap.add_argument('--tone-variants', action='store_true', help='opt in to supplementary low/high confidence conditions')
    args = ap.parse_args()
    cases, manifest = build_cases()
    runs = make_run_list(manifest, args.situations, args.packets, cases, args.tone_variants and not args.no_tone_variants)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(runs, indent=2), encoding="utf-8")
    print(f"{len(runs)} runs -> {args.out}")
