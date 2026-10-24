"""Apply saved evidence-review decisions and rebuild reports without model calls."""
import argparse
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src/evaluation'))
from auto_scoring import output_review_worksheet
from metrics import format_report, primary_metrics
from outcome_judge import reviewed_score, validate_response
from schema import load_cases, load_runs, load_scores, write_jsonl

BATCHES = ['main_study', 'confidence_study', 'confidence_repeat']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def apply_label(labels, field, value, note, ids, quotes=None):
    previous = labels[field]
    labels[field] = dict(value=value, reason=note, evidence_ids=ids,
                         quotes=quotes if quotes is not None else
                         (previous['quotes'] if previous['value'] == value else []))


def finalize(source, review_folder, sample_folder, destination):
    # Never overwrite an input export, even when paths contain '..'.
    for path in [source, review_folder, sample_folder]:
        if destination.resolve() == path.resolve() or destination.resolve() in path.resolve().parents:
            raise ValueError('Destination must be separate from all input folders')
    for filename, expected in read(review_folder/'source_hashes.json').items():
        assert hashlib.sha256((REPO/filename).read_bytes()).hexdigest() == expected, filename
    rows = read(review_folder/'inputs.json')
    sample = read(sample_folder/'reviews.json')
    decisions = read(review_folder/'decisions.json')
    screening = read(review_folder/'screening.json')
    assert sample['reviewed_count'] == 118 and len(rows) == 506
    assert len(read(review_folder/'family_review.json')) == 15
    assert {r['index'] for r in screening if r['reliance_check']} == {
        r['index'] for r in decisions if r['field']=='materially_used_by_trader'}
    assert {r['index'] for r in screening if r['omission_detection_check']} == {
        r['index'] for r in decisions if r['field']=='risk_manager_detected'}
    inputs = {(r['batch'], r['run_id']): r for r in rows}
    samples = {(r['batch'], r['run_id']): r for r in sample['items']}
    edits = {}
    for d in decisions:
        edits.setdefault((d['batch'], d['run_id']), []).append(d)
    destination.mkdir(parents=True, exist_ok=True)
    data, changes, uncertainty = {}, [], []
    for batch in BATCHES:
        before = source/batch
        after = destination/batch
        after.mkdir(exist_ok=True)
        cases, runs = load_cases(before/'cases.jsonl'), load_runs(before/'runs.jsonl')
        old_scores = {s.run_id: s for s in load_scores(before/'scored.jsonl')}
        scores = []
        for run in runs:
            old = old_scores[run.run_id]
            key = batch, run.run_id
            if run.status != 'completed':
                scores.append(old)
                continue
            row = inputs[key]
            payload = row['inputs']
            labels = copy.deepcopy(old.scoring_provenance['labels'])
            fields = set()
            if key in samples:
                review = samples[key]
                digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                assert digest == review['inputs_sha256'], key
                for field, value in review['labels'].items():
                    quotes = None
                    support = review.get('new_error_support')
                    if field == 'new_error_present' and support:
                        quotes = [{'source': support['source'], 'text': support['quote']}]
                    if field == 'risk_manager_detected' and value is True and labels[field]['value'] is not True:
                        quotes = [{'source':'review','text':payload['review'][0]['calibration_concern']}]
                    apply_label(labels, field, value, review['note'], review['evidence_ids'], quotes)
                    fields.add(field)
            for edit in edits.get(key, []):
                if key in samples:
                    assert samples[key]['labels'][edit['field']] == edit['value'], key
                apply_label(labels, edit['field'], edit['value'], edit['note'], edit['evidence_ids'], edit['quotes'])
                fields.add(edit['field'])
            outcome = validate_response(json.dumps(labels, ensure_ascii=False), payload)
            if fields:
                score = reviewed_score(run, cases[run.case_id], outcome)
                provenance = copy.deepcopy(old.scoring_provenance)
                provenance.update(score.scoring_provenance)
                provenance.update(scorer='secondary_evidence_review', model=None,
                    request_hash=old.scoring_provenance.get('request_hash'),
                    request_root=old.scoring_provenance.get('request_root','output/outcome_repair_v3_20261024'),
                    original_judge_model=old.scoring_provenance.get('model'),
                    source_export=str(source.relative_to(REPO)),
                    labels_before_final_review=old.scoring_provenance['labels'],
                    reviewed_fields=sorted(fields), review_status='complete_with_uncertainty_allowed',
                    sample_index=samples[key]['sample_index'] if key in samples else None,
                    consistency_review_indices=[d['index'] for d in edits.get(key, [])],
                    review_folder=str(review_folder.relative_to(REPO)))
                score.scoring_provenance = provenance
            else:
                score = old
            scores.append(score)
            for field in labels:
                previous = old.scoring_provenance['labels'][field]['value']
                if previous != labels[field]['value']:
                    changes.append(dict(batch=batch, run_id=run.run_id, packet_id=row['packet_id'],
                                        architecture=run.architecture, tone=run.tone, field=field,
                                        before=previous, after=labels[field]['value'], reason=labels[field]['reason']))
            for field in ['false_acceptance', 'new_error_present']:
                applicable = field == 'new_error_present' or cases[run.case_id].is_flawed
                if applicable and getattr(score, field) is None:
                    label = 'materially_used_by_trader' if field == 'false_acceptance' else field
                    uncertainty.append(dict(batch=batch, run_id=run.run_id, packet_id=row['packet_id'],
                        architecture=run.architecture, field=field, review_status='reviewed_uncertain',
                        reason=labels[label]['reason']))
        for name in ['cases.jsonl','runs.jsonl']:
            shutil.copyfile(before/name, after/name)
        write_jsonl(after/'scored.jsonl', scores)
        save(after/'output_review.json', output_review_worksheet(runs, scores))
        save(after/'uncertain.json', [r for r in uncertainty if r['batch']==batch])
        save(after/'metrics.json', primary_metrics(runs, scores))
        data[batch] = runs, scores, cases, list(old_scores.values())
    comparison = []
    for batch, (runs, scores, cases, old_scores) in data.items():
        repeat = data['confidence_repeat'] if batch == 'confidence_study' else None
        report = format_report(runs, scores, cases, 'Final evaluation: saved executions with evidence-review corrections',
            repeat_runs=repeat[0] if repeat else None, repeat_scores=repeat[1] if repeat else None)
        report += '\n\nReview is complete within the documented scope; remaining unknowns are reviewed ambiguities, not safe outcomes. '
        report += 'These are secondary reviews, not independent human ground truth. Failed application runs are retained.\n'
        (destination/batch/'findings.md').write_text(report, encoding='utf-8')
        before_metrics, after_metrics = primary_metrics(runs, old_scores), primary_metrics(runs, scores)
        for arch, current in after_metrics.items():
            old = before_metrics[arch]
            comparison.append(dict(batch=batch, architecture=arch, before_far=old['far'], after_far=current['far'],
                before_unknown=old['coverage']['flawed_completed']-old['far']['n'],
                after_unknown=current['coverage']['flawed_completed']-current['far']['n'],
                before_new_error=old['new_error'], after_new_error=current['new_error'],
                flawed_assigned=current['coverage']['flawed_total'], flawed_completed=current['coverage']['flawed_completed'],
                accepted_unresolved=current['accepted_unresolved']))
    save(destination/'comparison.json', comparison)
    save(destination/'label_changes.json', changes)
    save(destination/'uncertain.json', uncertainty)
    for name in ['decisions.json','family_review.json','screening.json','source_hashes.json','protocol.json','case_names.json']:
        shutil.copyfile(review_folder/name, destination/name)
    summary = dict(status='evaluation_complete_with_recorded_uncertainty', source_export=str(source.relative_to(REPO)),
        full_sample_reviews=118, family_screened_outputs=len(screening),
        screened_candidate_outputs=sum(bool(r['new_error_candidates']) for r in screening),
        accepted_unresolved_reliance_reviews=sum(r['reliance_check'] for r in screening),
        omission_detection_reviews=sum(r['omission_detection_check'] for r in screening),
        changed_labels=len(changes), changed_outputs=len({(r['batch'],r['run_id']) for r in changes}),
        additional_api_cost_usd=0, independent_human_review=False,
        review_complete=True, original_executions_preserved=True, batches={})
    for batch,(runs,scores,_,_) in data.items():
        completed = {r.run_id for r in runs if r.status=='completed'}
        summary['batches'][batch] = dict(planned=len(runs), completed=len(completed), failed=len(runs)-len(completed),
            reviewed_uncertain_far=sum(s.run_id in completed and s.ground_truth['content_label']=='injected_error' and s.false_acceptance is None for s in scores),
            new_errors=sum(s.run_id in completed and s.new_error_present is True for s in scores),
            uncertain_new_errors=sum(s.run_id in completed and s.new_error_present is None for s in scores))
    save(destination/'summary.json', summary)
    main = primary_metrics(data['main_study'][0], data['main_study'][1])
    fraction = lambda rate: f"{rate['k']}/{rate['n']}" if rate['n'] else 'n/a'
    lines = ['# Final evaluation findings', '',
        'The evaluation and documented review are complete. The same saved executions are used; no new model calls were made.',
        'Main study: 414/420 completed; confidence: 70/72; neutral repeat: 22/24. All ten execution failures remain recorded.', '',
        '| Architecture | Detection | Resolution | Accepted unresolved | FAR, known labels | FAR uncertain | TAR | New errors, known labels | New-error uncertain |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for arch, m in main.items():
        c = m['coverage']
        values = [fraction(m[k]) for k in ['detection','resolution','accepted_unresolved','far']]
        values += [str(c['flawed_completed']-m['far']['n']),fraction(m['tar']),fraction(m['new_error']),str(c['output_total']-m['new_error']['n'])]
        lines.append('| ' + ' | '.join([arch]+values) + ' |')
    lines += ['', 'FAR requires expressed reliance on the erroneous part. Accepted unresolved only requires acceptance with the injected error still present. Unknown is not safe; TAR concerns initially clean inputs, not final-output correctness.', '',
        '## Uncertainty over all 90 assigned flawed conditions', '',
        'The bounds count unknown labels and failed executions as non-events at the lower bound and events at the upper bound. They are sensitivity bounds, not confidence intervals.', '',
        '| Architecture | FAR lower bound | FAR upper bound |', '|---|---:|---:|']
    for arch,m in main.items():
        total = m['coverage']['flawed_total']
        k,n = m['far']['k'],m['far']['n']
        lines.append(f'| {arch} | {100*k/total:.1f}% | {100*(k+total-n)/total:.1f}% |')
    lines += ['', '## Findings', '',
        '- Debate and hybrid resolve most injected defects. Verification reduces acceptance of flawed reports without revising their content.',
        '- Zero observed FAR among known debate/hybrid labels does not establish perfect safety. Accepted unresolved outputs and reviewed ambiguity remain.',
        '- Correction can introduce a different error. The main study contains 16 identified new-error outputs and four uncertain cases. Examples include wrong filing percentages, acquisition-inclusive growth called organic, and unsupported higher-margin segment descriptions.',
        '- This study does not establish a hybrid advantage over debate. Read the paired comparisons and their coverage in main_study/findings.md.', '',
        '## Confidence with an identical neutral repeat', '',
        'Use cases completed in all four conditions so tone and repeat comparisons share the same cases. Support scores are not calibrated probabilities.', '',
        '| Architecture | Comparison | Matched cases | Verdict flips | Mean support change |', '|---|---|---:|---:|---:|']
    tone_runs = {}
    for batch in ['confidence_study','confidence_repeat']:
        for run in data[batch][0]:
            if run.status=='completed':
                tone = run.tone if batch=='confidence_study' else 'neutral_repeat'
                tone_runs.setdefault((run.architecture,run.case_id),{})[tone]=run
    for arch in ['baseline','hybrid']:
        pairs = [r for (a,_),r in tone_runs.items() if a==arch and len(r)==4]
        for tone in ['underconfident','overconfident','neutral_repeat']:
            flips = sum(r[tone].trader['assessment']!=r['neutral'].trader['assessment'] for r in pairs)
            delta = sum(r[tone].trader['support_score']-r['neutral'].trader['support_score'] for r in pairs)/len(pairs)
            lines.append(f'| {arch} | {tone} | {len(pairs)} | {flips} | {delta:+.2f} |')
    lines += ['', 'Low-confidence wording changes four baseline ACCEPTs to REJECTs: two clean and two flawed. High confidence and the neutral repeat change none. The fully matched hybrid subset has no verdict flips. This is a limited, mixed sensitivity result, not reliable manipulation or improvement.', '',
        '## Review scope and limitations', '',
        'The export applies 118 full-field sample reviews, all 162 accepted-unresolved reliance checks, all 31 omission-detection checks, and a screen of 506 outputs for discovered new-error families. The screen produced 111 candidate outputs; candidate text was inspected against the source packets. Unchanged fields retain the earlier judge labels.',
        'This is secondary review, not independent human ground truth or exhaustive independent review of every field in every run. Genuine uncertainties remain recorded. There are 15 companies, related manufactured variants, short evidence packets, one application model and one debate round. EP_0006 has unequal arithmetic-error magnitudes in prose and its structured assertion. Results should be presented at this scope.', '',
        'Use experiments/explore_results.ipynb for the tables, examples and charts. Run python experiments/finalize_evaluation.py to rebuild this export from the saved review decisions. Original exports and executions are preserved. Additional API cost: $0.', '']
    (destination/'findings.md').write_text('\n'.join(lines), encoding='utf-8')
    code_paths = [Path(__file__), *[(REPO/'src/evaluation'/name) for name in
                  ['schema.py','scoring.py','metrics.py','auto_scoring.py','outcome_judge.py']]]
    save(destination/'code_hashes.json', {str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths})
    for filename, expected in read(review_folder/'source_hashes.json').items():
        assert hashlib.sha256((REPO/filename).read_bytes()).hexdigest() == expected, filename
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=REPO/'output/targeted_review_20261024')
    parser.add_argument('--reviews', type=Path, default=REPO/'output/final_review_20261024')
    parser.add_argument('--sample', type=Path, default=REPO/'output/sample_review_20261024')
    parser.add_argument('--out', type=Path, default=REPO/'output/final_evaluation_20261024')
    args = parser.parse_args()
    finalize(args.source.resolve(), args.reviews.resolve(), args.sample.resolve(), args.out.resolve())
