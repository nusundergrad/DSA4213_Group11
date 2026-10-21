"""Aggregate adjudicated v0.1 results from the Group11 shared contract.

Requires one completed execution and matching scored result per condition. Pending
semantic judgements and failed executions are reported as missing, not successes.
"""
from __future__ import annotations

import math
import random
import re

from schema import ARCHITECTURES, DEFECT_TYPES, TONES, load_runs, load_scores


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - h) / d), min(1.0, (c + h) / d))


def rate(flags):
    flags = [v for v in flags if v is not None]
    n, k = len(flags), sum(flags)
    lo, hi = wilson(k, n)
    return dict(k=k, n=n, rate=k / n if n else None, lo=lo if n else None, hi=hi if n else None)


def joined(runs, scores):
    """Fail on duplicates and unmatched records; never silently choose a retry."""
    for field in ('model', 'temperature', 'max_debate_rounds', 'max_tokens', 'reasoning_effort', 'trader_evidence_access'):
        values = {r.config[field] for r in runs if field in r.config}
        if len(values) > 1:
            raise ValueError(f'mixed {field} settings; analyze configurations separately')
    by_run = {}
    for run in runs:
        if run.run_id in by_run:
            raise ValueError(f"duplicate run_id: {run.run_id}")
        by_run[run.run_id] = run
    by_score = {}
    for score in scores:
        if score.run_id in by_score:
            raise ValueError(f"duplicate score for run_id: {score.run_id}")
        by_score[score.run_id] = score
    if set(by_run) != set(by_score):
        raise ValueError("every execution needs exactly one scored result")
    keys = set()
    rows = []
    for run_id, run in by_run.items():
        score = by_score[run_id]
        if score.case_id != run.case_id:
            raise ValueError("run and scored result case_id mismatch")
        if (score.scoring_status == "complete" and score.ground_truth["content_label"] == "injected_error"
                and score.false_acceptance is None):
            raise ValueError("complete injected score needs false_acceptance")
        key = (run.case_id, run.architecture, run.tone)
        if key in keys:
            raise ValueError(f"multiple attempts for condition {key}; select one before analysis")
        keys.add(key)
        rows.append((run, score))
    return rows


def _eligible(run, score):
    return run.status == "completed" and score.scoring_status in ("complete", "not_applicable")


def primary_metrics(runs, scores, tone="neutral", architectures=ARCHITECTURES, defect_type=None):
    rows = joined(runs, scores)
    out = {}
    for arch in architectures:
        all_rows = [(r, s) for r, s in rows if r.architecture == arch and r.tone == tone]
        relevant = [(r, s) for r, s in all_rows if defect_type is None or
                    s.ground_truth["content_label"] == "unmodified" or
                    s.ground_truth["defect_type"] == defect_type]
        flawed = [(r, s) for r, s in relevant if s.ground_truth["content_label"] == "injected_error"]
        clean = [(r, s) for r, s in relevant if s.ground_truth["content_label"] == "unmodified"]
        eligible_f = [(r, s) for r, s in flawed if _eligible(r, s)]
        eligible_c = [(r, s) for r, s in clean if _eligible(r, s)]
        completed_f = [(r, s) for r, s in flawed if r.status == 'completed']
        detected = [s for _, s in completed_f if s.detected is True]
        # Runs whose Risk Manager output is unstructured (challenges None) cannot be counted either way.
        challenges = [r for r, s in eligible_c if r.risk_manager_turns
                      and r.risk_manager_turns[0].get('challenges') is not None]
        out[arch] = dict(
            coverage=dict(flawed_total=len(flawed), flawed_scored=len(eligible_f),
                          clean_total=len(clean), clean_scored=len(eligible_c),
                          failed=sum(r.status != 'completed' for r, s in relevant)),
            detection=rate([s.detected for _, s in completed_f]),
            correction=rate([s.corrected_after_detection for s in detected]),
            resolution=rate([s.defect_resolved for _, s in completed_f]),
            flawed_acceptance=rate([r.trader['assessment'] == 'ACCEPT' for r, _ in completed_f]),
            far=rate([s.false_acceptance for _, s in completed_f]),
            tar=rate([r.trader["assessment"] == "ACCEPT" for r, _ in eligible_c]),
            false_challenge=rate([bool(r.risk_manager_turns[0]['challenges']) for r in challenges]),
        )
    return out


def by_failure_category(runs, scores):
    return {d: primary_metrics(runs, scores, defect_type=d) for d in DEFECT_TYPES}


def tone_metrics(runs, scores, cases, architectures=ARCHITECTURES):
    rows = {(r.case_id, r.architecture, r.tone): (r, s) for r, s in joined(runs, scores)}
    out = {}
    for arch in architectures:
        out[arch] = {}
        for tone in ("underconfident", "overconfident"):
            ids = [cid for cid, case in cases.items() if case.confidence_subset and
                   all((cid, arch, t) in rows and rows[cid, arch, t][0].status == 'completed' and
                       rows[cid, arch, t][0].trader.get("support_score") is not None for t in TONES)]
            if not ids:
                continue
            pairs = [(rows[cid, arch, "neutral"], rows[cid, arch, tone]) for cid in ids]
            diffs = [b[0].trader["support_score"] - a[0].trader["support_score"] for a, b in pairs]
            flawed = [(a, b) for cid, (a, b) in zip(ids, pairs) if cases[cid].is_flawed]
            def delta(field):
                known = [(a, b) for a, b in flawed if getattr(a[1], field) is not None and getattr(b[1], field) is not None]
                left = rate([getattr(a[1], field) for a, b in known])
                right = rate([getattr(b[1], field) for a, b in known])
                return right["rate"] - left["rate"] if left["rate"] is not None and right["rate"] is not None else None
            # Correction is conditional on detection in each tone.
            corr_n = rate([a[1].corrected_after_detection for a, b in flawed if a[1].detected is True])
            corr_o = rate([b[1].corrected_after_detection for a, b in flawed if b[1].detected is True])
            out[arch][tone] = dict(n=len(ids), sensitivity_mean=sum(diffs) / len(diffs),
                                   sensitivity_abs=sum(map(abs, diffs)) / len(diffs),
                                   flip=sum(a[0].trader["assessment"] != b[0].trader["assessment"] for a, b in pairs) / len(pairs),
                                   dD=delta("detected"),
                                   dC=corr_o["rate"] - corr_n["rate"] if corr_n["rate"] is not None and corr_o["rate"] is not None else None,
                                   dP=delta("false_acceptance"))
    return out


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def paired_comparison(runs, scores, arch_a, arch_b, field="far", n_boot=2000, seed=0):
    rows = {(r.case_id, r.architecture): (r, s) for r, s in joined(runs, scores) if r.tone == "neutral"}
    ids = [cid for cid, arch in rows if arch == arch_a and (cid, arch_b) in rows and
           all(rows[cid, arch][0].status == 'completed' and
               (field != 'far' or rows[cid, arch][1].false_acceptance is not None) for arch in (arch_a, arch_b)) and
           rows[cid, arch_a][1].ground_truth["content_label"] == ("injected_error" if field == "far" else "unmodified")]
    if not ids:
        return None
    def outcome(cid, arch):
        r, s = rows[cid, arch]
        return int(s.false_acceptance if field == "far" else r.trader["assessment"] == "ACCEPT")
    a, b = [outcome(i, arch_a) for i in ids], [outcome(i, arch_b) for i in ids]
    a_only = sum(x and not y for x, y in zip(a, b))
    b_only = sum(y and not x for x, y in zip(a, b))
    rng = random.Random(seed)
    # Resample whole packets, keeping the three related flawed variants together.
    groups = {}
    for i, cid in enumerate(ids):
        report = rows[cid, arch_a][0].initial_report
        evidence = [e for c in report.get('claims', []) for e in c.get('evidence_ids', [])]
        packet = next((e.rsplit('_', 1)[0] for e in evidence if re.fullmatch(r'EP_\d+_E\d+', e)), cid)
        groups.setdefault(packet, []).append(i)
    clusters = list(groups.values())
    diffs = []
    for _ in range(n_boot):
        sample = [j for _ in clusters for j in clusters[rng.randrange(len(clusters))]]
        diffs.append(sum(a[j] - b[j] for j in sample) / len(sample))
    diffs.sort()
    return dict(n=len(ids), rate_a=sum(a) / len(ids), rate_b=sum(b) / len(ids),
                n_clusters=len(clusters),
                diff=(sum(a) - sum(b)) / len(ids),
                ci=(diffs[int(.025*n_boot)], diffs[int(.975*n_boot)-1]) if diffs else None,
                a_only=a_only, b_only=b_only, p_mcnemar=mcnemar_exact(a_only, b_only))


def efficiency(runs):
    out = {}
    for arch in ARCHITECTURES:
        rs = [r for r in runs if r.architecture == arch and r.status == "completed"]
        if not rs:
            continue
        def total(field):
            values = [r.usage.get(field) for r in rs]
            return sum(values) if all(v is not None for v in values) else None
        latency = [r.usage.get('wall_latency_ms', r.usage.get('latency_ms')) for r in rs]
        out[arch] = dict(runs=len(rs), input_tokens=total('input_tokens'), output_tokens=total('output_tokens'),
                         estimated_cost_usd=total('estimated_cost_usd'),
                         mean_latency_ms=sum(latency) / len(rs) if all(v is not None for v in latency) else None)
    return out


def _fmt_rate(x):
    return "n/a" if x is None or x["rate"] is None else f"{x['rate']:.2f} [{x['lo']:.2f},{x['hi']:.2f}] (n={x['n']})"


def format_report(runs, scores, cases, title="Evaluation report"):
    lines = [f"# {title}", "", "## Evaluation 1 (neutral tone)", "",
             "Known outcomes use their own denominators. Pending labels and failed runs are not successes.", "",
             "| architecture | detection | correction after detection | resolution | FAR | TAR | challenges on initial controls | fully scored flawed | failed |",
             "|---|---|---|---|---|---|---|---|---|"]
    for arch, m in primary_metrics(runs, scores).items():
        c = m["coverage"]
        lines.append(f"| {arch} | {_fmt_rate(m['detection'])} | {_fmt_rate(m['correction'])} | {_fmt_rate(m['resolution'])} | {_fmt_rate(m['far'])} | "
                     f"{_fmt_rate(m['tar'])} | {_fmt_rate(m['false_challenge'])} | {c['flawed_scored']}/{c['flawed_total']} | {c['failed']} |")
    lines += ['', 'FAR requires an accepted recommendation, an unresolved defect and material reliance. It is not simply acceptance of a flawed input.',
              'TAR means acceptance when the input is a clean control; it does not establish that later revisions stayed correct. Resolution concerns the injected defect, not certification that no new error appeared.',
              'Control challenges are an observed rate, not automatically false challenges; their validity needs review.',
              'Per-rate Wilson intervals are descriptive case-level summaries. Paired difference intervals resample whole evidence packets; variants are not independent companies. One-packet intervals cannot establish generality.',
              'Check final reports and rationales for new errors separately before making a project-level conclusion.']
    lines += ["", "### FAR by failure category", "", "| category | " + " | ".join(ARCHITECTURES) + " |",
              "|---|" + "---|" * len(ARCHITECTURES)]
    for d, per in by_failure_category(runs, scores).items():
        if not any(per[a]["coverage"]["flawed_total"] for a in ARCHITECTURES):
            continue                                   # category absent from this dataset
        cell = lambda a: "n/a" if per[a]["far"]["rate"] is None else f"{per[a]['far']['rate']:.2f} (n={per[a]['far']['n']})"
        lines.append(f"| {d} | " + " | ".join(cell(a) for a in ARCHITECTURES) + " |")
    lines += ["", "### H1: hybrid vs each other architecture (paired, neutral tone)", ""]
    for other in ("baseline", "debate", "verification"):
        far = paired_comparison(runs, scores, "hybrid", other, "far")
        tar = paired_comparison(runs, scores, "hybrid", other, "tar")
        if far is None or tar is None:
            lines.append(f"- hybrid vs {other}: no overlapping scored cases")
            continue
        lines.append(f"- hybrid vs {other}: FAR {far['rate_a']:.2f} vs {far['rate_b']:.2f}, diff {far['diff']:+.2f} "
                     f"packet-bootstrap CI [{far['ci'][0]:+.2f},{far['ci'][1]:+.2f}] ({far['n_clusters']} packets); "
                     f"TAR {tar['rate_a']:.2f} vs {tar['rate_b']:.2f} ({tar['n_clusters']} packets)")
    lines += ["", "## Supplementary: tone changes from neutral (support scale 0-100)", "",
              "Support scores are self-reported, not calibrated probabilities. Compare verdict flips and neutral repeats before attributing differences to tone.", "",
              "| architecture | tone | n | mean support change | mean abs change | flip | dD | dC | dP |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    fmt = lambda x: "n/a" if x is None else f"{x:+.2f}"
    for arch, group in tone_metrics(runs, scores, cases).items():
        for tone, m in group.items():
            lines.append(f"| {arch} | {tone} | {m['n']} | {m['sensitivity_mean']:+.2f} | {m['sensitivity_abs']:.2f} | "
                         f"{m['flip']:.2f} | {fmt(m['dD'])} | {fmt(m['dC'])} | {fmt(m['dP'])} |")
    lines += ["", "## Efficiency", "", "| architecture | runs | input tokens | output tokens | USD | mean latency ms |",
              "|---|---:|---:|---:|---:|---:|"]
    for arch, e in efficiency(runs).items():
        cost = f"{e['estimated_cost_usd']:.4f}" if e['estimated_cost_usd'] is not None else 'n/a'
        latency = f"{e['mean_latency_ms']:.0f}" if e['mean_latency_ms'] is not None else 'n/a'
        lines.append(f"| {arch} | {e['runs']} | {e['input_tokens']} | {e['output_tokens']} | "
                     f"{cost} | {latency} |")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    from dummy_data import make_cases, make_runs
    from schema import load_cases
    p = argparse.ArgumentParser()
    p.add_argument("--dummy", action="store_true")
    p.add_argument("--cases")
    p.add_argument("--runs")
    p.add_argument("--scores")
    p.add_argument('--out', help='write a UTF-8 report instead of relying on shell redirection')
    args = p.parse_args()
    if args.dummy:
        cases = make_cases()
        runs, scores = make_runs(cases)
    else:
        if not all((args.cases, args.runs, args.scores)):
            p.error("--cases, --runs, and --scores are required for real data")
        cases, runs, scores = load_cases(args.cases), load_runs(args.runs), load_scores(args.scores)
    report = format_report(runs, scores, cases, "Synthetic evaluation report" if args.dummy else "Evaluation report")
    if args.out:
        from pathlib import Path
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report + '\n', encoding='utf-8')
        print(args.out)
    else:
        print(report)
