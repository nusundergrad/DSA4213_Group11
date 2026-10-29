"""Rebuild the three-round findings from saved runs and source-review decisions. No API calls."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'src/evaluation'))
from benchmark_cases import build_cases, DEFAULT_ROOT
from metrics import format_report, primary_metrics, by_failure_category, efficiency
from outcome_judge import build_input, digest, reviewed_score, validate_response
from schema import load_cases, load_runs, write_jsonl
from src.benchmark.schemas import Packet

BATCHES = ['main_study_3rounds', 'confidence_study_3rounds', 'confidence_repeat_3rounds']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def rate_text(value):
    return f"{value['k']}/{value['n']} ({value['rate']:.1%})" if value['n'] else 'N/A'


def csv_rows(path, rows):
    if not rows:
        return
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def organize_runs(source, destination):
    """Copy the selected raw attempts into a browsable view; keep originals intact."""
    from graph_adapter import record_to_run

    cases = {name: load_cases(destination / name / 'cases.jsonl') for name in BATCHES}
    expected = {(name, run.run_id): run for name in BATCHES
                for run in load_runs(destination / name / 'runs.jsonl')}
    seen, targets, copies, index = set(), set(), [], []
    for item in read(source / 'attempt_selection.json'):
        original = REPO / item['selected_attempt']
        if not original.resolve().is_relative_to(REPO) or not original.is_file():
            raise ValueError('Organizing raw runs needs the original saved attempt: ' + str(original))
        record = read(original)
        name = item['batch']
        run = record_to_run(record, cases[name])
        key = name, run.run_id
        if key in seen or run != expected.get(key):
            raise ValueError('Selected attempt differs from the final evaluation: ' + run.run_id)
        seen.add(key)
        target = destination / name / 'runs' / record['evidence_packet'] / record['situation'] / record['report']
        if name != 'main_study_3rounds':
            target /= run.tone
        target /= original.name
        if not target.resolve().is_relative_to(destination.resolve()) or target in targets:
            raise ValueError('Invalid or duplicate organized run path: ' + str(target))
        targets.add(target)
        fingerprint = hashlib.sha256(original.read_bytes()).hexdigest()
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != fingerprint:
            raise ValueError('Existing run copy differs; inspect before replacing: ' + str(target))
        copies.append((original, target))
        index.append(dict(batch=name, run_id=run.run_id, packet=record['evidence_packet'],
                          architecture=run.architecture, case=record['report'], tone=run.tone,
                          status=run.status, recovered=item['recovered'],
                          run_path=target.relative_to(destination).as_posix(),
                          source_path=item['selected_attempt'], sha256=fingerprint))
    if seen != set(expected):
        raise ValueError('The organized view would omit final evaluation conditions')
    for original, target in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(original, target)
    csv_rows(destination / 'run_index.csv', sorted(index, key=lambda row: row['run_path']))
    return len(copies)


def confidence_comparison(batches):
    study = batches['confidence_study_3rounds'][0]
    repeats = batches['confidence_repeat_3rounds'][0]
    rows, flips = [], []
    for architecture in ['baseline', 'hybrid']:
        groups = {tone: {r.case_id: r for r in study if r.status == 'completed'
                         and r.architecture == architecture and r.tone == tone}
                  for tone in ['underconfident', 'neutral', 'overconfident']}
        groups['neutral_repeat'] = {r.case_id: r for r in repeats
            if r.status == 'completed' and r.architecture == architecture}
        shared = set.intersection(*(set(group) for group in groups.values()))
        for tone in ['underconfident', 'overconfident', 'neutral_repeat']:
            changes, count = [], 0
            for case_id in sorted(shared):
                before, after = groups['neutral'][case_id], groups[tone][case_id]
                changes.append(after.trader['support_score'] - before.trader['support_score'])
                if before.trader['assessment'] != after.trader['assessment']:
                    count += 1
                    flips.append(dict(architecture=architecture, comparison=tone, case_id=case_id,
                                      neutral=before.run_id, changed=after.run_id))
            rows.append({'architecture': architecture, 'comparison': tone, 'matched cases': len(shared),
                         'verdict flips': count, 'flip %': count / len(shared) * 100 if shared else None,
                         'mean support change': sum(changes) / len(changes) if changes else None,
                         'mean absolute change': sum(map(abs, changes)) / len(changes) if changes else None})
    return rows, flips


def finalize(source, destination):
    if source.resolve() == destination.resolve() or destination.resolve() in source.resolve().parents:
        raise ValueError('Keep source reviews and the rebuilt export separate.')
    review = read(source / 'review_summary.json')
    if not review['review_complete']:
        raise ValueError('Finish the source cross-check and resolve its review queue first.')
    items = read(source / 'outcomes.json')
    by_run = {(row['batch'], row['run_id']): row for row in items}
    if len(by_run) != len(items):
        raise ValueError('Duplicate reviewed run IDs')
    _, manifest = build_cases(confidence_pair_ids=set())
    case_names = {case_id: Path(item['report_path']).with_suffix('').as_posix().removeprefix('reports/')
                  for case_id, item in manifest.items()}
    destination.mkdir(parents=True, exist_ok=True)
    batches, uncertainties, examples, counted = {}, [], [], set()
    for name in BATCHES:
        before = source / 'inputs' / name
        after = destination / name
        after.mkdir(exist_ok=True)
        cases, runs = load_cases(before / 'cases.jsonl'), load_runs(before / 'runs.jsonl')
        scores = []
        for run in runs:
            if run.status != 'completed':
                scores.append(reviewed_score(run, cases[run.case_id]))
                continue
            key = name, run.run_id
            item = by_run[key]
            packet = Packet.model_validate_json((DEFAULT_ROOT / 'public' / manifest[run.case_id]['packet_path']).read_text(encoding='utf-8')).model_dump(mode='json')
            payload = build_input(run, cases[run.case_id], packet)
            if digest(payload) != item['input_sha256']:
                raise ValueError('Reviewed inputs changed: ' + run.run_id)
            outcome = validate_response(json.dumps(item['labels'], ensure_ascii=False), payload)
            score = reviewed_score(run, cases[run.case_id], outcome)
            score.scoring_provenance.update(scorer='source_crosscheck_and_adjudication',
                independent_human_review=False, review=item['provenance'])
            scores.append(score)
            counted.add(key)
            unresolved = []
            if cases[run.case_id].is_flawed:
                for field in ['detected', 'defect_resolved', 'false_acceptance']:
                    if field == 'detected' and run.architecture == 'baseline':
                        continue
                    if getattr(score, field) is None:
                        unresolved.append(field)
            if score.new_error_present is None:
                unresolved.append('new_error_present')
            if unresolved:
                uncertainties.append(dict(batch=name, run_id=run.run_id, fields=unresolved))
            if score.new_error_present is True:
                examples.append(dict(batch=name, run_id=run.run_id, architecture=run.architecture,
                    case=case_names[run.case_id],
                    reason=score.new_error_explanation))
        write_jsonl(after / 'runs.jsonl', runs)
        write_jsonl(after / 'cases.jsonl', cases.values())
        write_jsonl(after / 'scored.jsonl', scores)
        batches[name] = runs, scores, cases
    if counted != set(by_run):
        raise ValueError('Review contains outputs outside the selected experiment')
    for name, (runs, scores, cases) in batches.items():
        repeat = batches['confidence_repeat_3rounds'] if name == 'confidence_study_3rounds' else None
        report = format_report(runs, scores, cases, 'Three-round evaluation',
            repeat_runs=repeat[0] if repeat else None, repeat_scores=repeat[1] if repeat else None)
        (destination / name / 'findings.md').write_text(report + '\n', encoding='utf-8')
    main_runs, main_scores, _ = batches['main_study_3rounds']
    main = primary_metrics(main_runs, main_scores)
    summary = dict(execution=read(source / 'execution_coverage.json'), main=main,
                   by_error=by_failure_category(main_runs, main_scores), efficiency=efficiency(main_runs),
                   review=review, uncertain_runs=len(uncertainties))
    save(destination / 'summary.json', summary)
    save(destination / 'uncertain.json', uncertainties)
    save(destination / 'case_names.json', case_names)
    confidence, flips = confidence_comparison(batches)
    csv_rows(destination / 'confidence_matched.csv', confidence)
    save(destination / 'confidence_flips.json', flips)
    csv_rows(destination / 'metrics.csv', [dict(architecture=arch, metric=metric, numerator=v['k'],
        denominator=v['n'], rate=v['rate']) for arch, values in main.items()
        for metric, v in values.items() if isinstance(v, dict) and 'k' in v])
    csv_rows(destination / 'new_error_examples.csv', examples)
    csv_rows(destination / 'execution_coverage.csv', [dict(batch=name, **value) for name, value in summary['execution'].items()])
    lines = ['# Three-round findings', '',
        'All four architectures use the same masked benchmark. Debate and hybrid use three Risk Manager-Analyst rounds; Trader does not receive the source packet.', '',
        '## Execution', '', '| Batch | Assigned | First-pass completed | Recovery attempts | Selected completed | Selected failed |',
        '|---|---:|---:|---:|---:|---:|']
    for name, value in summary['execution'].items():
        lines.append(f"| {name} | {value['assigned']} | {value['first_completed']} | {value['recoveries']} | {value['selected_completed']} | {value['selected_failed']} |")
    lines += ['', 'One explicit identical recovery was allowed for each prespecified transport/quota failure. Its result was selected even when it failed. Malformed or truncated model responses were retained without retries. All original attempts remain preserved.', '',
              '## Main comparison', '', '| Architecture | Detection | Resolution | Accepted unresolved | FAR | TAR | New errors |',
              '|---|---|---|---|---|---|---|']
    for arch, values in main.items():
        lines.append('| ' + arch + ' | ' + ' | '.join(rate_text(values[m]) for m in ['detection', 'resolution', 'accepted_unresolved', 'far', 'tar', 'new_error']) + ' |')
    lines += ['', 'Rates show numerator / known outcomes. Unknown labels and execution failures remain separate; all architectures were assigned 90 flawed and 15 clean conditions.', '',
              'FAR additionally requires expressed reliance on the erroneous part. Acceptance of an unresolved error is broader. TAR concerns a clean initial input and does not certify that later revisions stayed error-free.', '',
              'Use the [main report](main_study_3rounds/findings.md) for matched comparisons and packet-bootstrap intervals. Related error variants are not independent companies.', '',
              '## What the results show', '',
              '- Debate and hybrid resolve about four-fifths of completed flawed inputs. Their similar resolution rates do not establish that hybrid is better at correction.',
              '- Verification detects all completed arithmetic and period errors (30/30), but does not rewrite reports. The Trader still accepts 5/30 of these flagged reports. Its 0% resolution is a consequence of this architecture.',
              '- Omissions remain the main weakness: debate restores 3/15 and hybrid 1/15. All 12 remaining debate omissions and 14 remaining hybrid omissions are accepted. Correct retained facts can hide missing counter-evidence even when the reviewer sees the packet.',
              '- Hybrid introduces fewer identified new errors than debate (3/98 versus 12/101 known labels). This is a descriptive result from one model and 15 packets, not proof of general superiority.',
              '- Hybrid has zero known FAR events, but 15 completed flawed cases have unknown reliance and 5 failed. Its all-assigned FAR bounds are 0/90 to 20/90. An uncertain label does not establish safety.',
              '- All completed main-study clean inputs were accepted. That measures input acceptance; debate can still introduce a new error in a clean control.', '',
              'Examples for the presentation:', '',
              '| Case | Observation | Interpretation |',
              '|---|---|---|',
              '| EP_0002, arithmetic, baseline | Trader uses the injected 24.93% revenue growth to justify ACCEPT/HOLD; the correct growth is 14.93%. | HOLD can still propagate an error. |',
              '| EP_0001, citation error, debate | The citation is repaired, but the final report attributes 13% Services growth to the FY2025 filing column, which actually says 14%. | Resolving the injected defect does not certify the rest of the revision. |',
              '| EP_0012, omission, hybrid | Three reviews report no remaining defect while positive downstream earnings growth remains omitted. | Repeated agreement can miss missing counter-evidence. |', '',
              '## Confidence and reviewer challenges', '',
              'The [confidence report](confidence_study_3rounds/findings.md) compares fixed low/high wording against neutral and an identical neutral repeat. The notebook also restricts all comparisons to cases completed in all four conditions. Support scores are uncalibrated.', '',
              'On cases completed in all four conditions:', '',
              '| Architecture | Comparison with neutral | Matched cases | Verdict flips | Mean support change |',
              '|---|---|---:|---:|---:|']
    for row in confidence:
        lines.append(f"| {row['architecture']} | {row['comparison']} | {row['matched cases']} | {row['verdict flips']} | {row['mean support change']:+.2f} |")
    lines += ['', 'Low confidence changes one baseline verdict from ACCEPT to REJECT on an unresolved period error (EP_0006). It also changes one hybrid verdict to REJECT on a clean EP_0006 input, where revisions create rounding/specification disagreements. High confidence causes no verdict flips on the matched cases; neither do neutral repeats. These results show score sensitivity and rare verdict changes, not a reliable general persuasion effect.', '',
              'Confidence acts through the full architecture: hybrid may revise the report before the Trader decides. A verdict change does not by itself isolate Trader persuasion or show improvement.', '',
              'The fixed-report disagreement example in `src/justification.ipynb` is separate. It challenges the Risk Manager, not the Trader. Its two exploratory examples do not estimate a population failure rate.', '',
              '## Review and limitations', '',
              'Saved primary judge labels were cross-checked against source evidence using a second model pass, deterministic numerical checks and recorded adjudications. The cross-check uses the application model family, so correlated errors remain possible. Model agreement is not ground truth or independent human validation.', '',
              'Positive errors have source references and output quotes. Semantic uncertainty remains null. Rounded filing percentages, calculated assertions and verifier interface failures are distinguished; see `uncertain.json` and the review notes.', '',
              'The previous one-round results remain preserved. This is not an isolated test of round count: turn instructions and message handling also changed.', '']
    lines += [f"Cumulative key usage after the recovery judging was **${review['account_usage_usd']:.2f}**. The additional paid judge allowance consumed was about **${review['additional_primary_judge_budget_cost_usd']:.2f}**; the application and secondary cross-check used the free model. Evaluation spending is separate from the application efficiency table.", '']
    (destination / 'findings.md').write_text('\n'.join(lines), encoding='utf-8')
    for name in ['review_summary.json', 'attempt_selection.json', 'execution_coverage.json',
                 'execution_audit.json', 'decisions.json', 'label_changes.json']:
        shutil.copyfile(source / name, destination / name)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=REPO / 'output/final_review_3rounds_20261027')
    parser.add_argument('--out', type=Path, default=REPO / 'output/final_evaluation_3rounds_20261027')
    parser.add_argument('--organize-runs', action='store_true',
                        help='Also copy selected raw runs into company/architecture/case folders; requires original attempts.')
    args = parser.parse_args()
    result = finalize(args.source, args.out)
    if args.organize_runs:
        print('Organized selected runs:', organize_runs(args.source, args.out))
    print(args.out)
    print(json.dumps(result['execution'], indent=2))
