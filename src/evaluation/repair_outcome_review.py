"""Revalidate saved judge responses, then repair only affected fields under a spending cap."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from outcome_judge import (Outcome, RelianceOutcome, SYSTEM, call_judge, canonical, digest,
                           request_body, reviewed_score, save_json, validate_response)
from schema import load_cases, load_runs, load_scores, write_jsonl


def needs_reliance(run, case, outcome):
    # Apply to all eligible outputs, including previously true/false labels, not just unknowns.
    return (run.status == 'completed' and case.is_flawed and run.trader['assessment'] == 'ACCEPT'
            and outcome is not None and outcome.answer_key_matches_input.value is True
            and (run.final_report == run.initial_report or outcome.defect_resolved.value is not True))


def apply_corrections(cases, corrections):
    changed = set()
    for correction in corrections:
        case = cases.get(correction['case_id'])
        if case is None:
            continue
        if case.defect != correction['previous_defect']:
            raise ValueError('Annotation correction does not match the frozen source key')
        case.defect = copy.deepcopy(correction['corrected_defect'])
        changed.add(case.case_id)
    return changed


def correct_saved_quote(raw, correction):
    """Apply an explicit, audited quote-only correction. Never edit the judge's labels."""
    data = json.loads(raw)
    quote = data[correction['field']]['quotes'][correction['quote_index']]
    if quote != {'source': correction['source'], 'text': correction['original_quote']}:
        raise ValueError('Quote correction does not match the saved response')
    quote['text'] = correction['replacement_quote']
    return json.dumps(data, ensure_ascii=False)


def capped_request(payload, model, scope):
    request = request_body(payload, model, scope)
    # USD per million tokens. The provider must satisfy these prices, not silently exceed them.
    request['provider']['max_price'] = {'prompt': 0.5, 'completion': 3, 'request': 0}
    return request


def reserve_cost(request):
    # UTF-8 byte length bounds input tokens conservatively, including the structured schema.
    return (len(canonical(request).encode('utf-8')) * .5e-6 + request['max_tokens'] * 3e-6) * 1.1


def budget_allows(spent, reserve, current_key_usage, starting_key_usage, additional_cap, total_cap):
    return (spent + reserve <= additional_cap and
            max(current_key_usage, starting_key_usage + spent) + reserve <= total_cap)


def key_usage(key):
    import httpx
    response = httpx.get('https://openrouter.ai/api/v1/auth/key',
                        headers={'Authorization': f'Bearer {key}'}, timeout=30)
    response.raise_for_status()
    return float(response.json()['data']['usage'])


def main():
    import argparse
    import hashlib
    import os
    import shutil
    import sys
    from concurrent.futures import ThreadPoolExecutor
    from dotenv import dotenv_values
    from auto_scoring import output_review_worksheet, pending_worksheet
    from metrics import format_report

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--corrections', required=True, type=Path)
    parser.add_argument('--quote-corrections', type=Path, help='Audited quote-only corrections; all replacements still undergo source validation')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--max-cost-usd', type=float, default=2, help='Additional spending in this repair folder')
    parser.add_argument('--total-budget-usd', type=float, default=10, help='Cumulative usage on the active API key')
    args = parser.parse_args()
    if args.source.resolve() == args.out.resolve() or min(args.workers, args.max_cost_usd, args.total_budget_usd) <= 0:
        parser.error('Use a separate output folder and positive workers/budgets')
    if args.limit is not None and args.limit < 1:
        parser.error('Limit must be positive')
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo))
    from src.benchmark.schemas import Packet
    from benchmark_cases import DEFAULT_ROOT, build_cases

    model = 'google/gemini-3-flash-preview'
    corrections = json.loads(args.corrections.read_text(encoding='utf-8'))['corrections']
    quote_corrections = json.loads(args.quote_corrections.read_text(encoding='utf-8')) if args.quote_corrections else {}
    source_summary = json.loads((args.source / 'summary.json').read_text(encoding='utf-8'))
    names = list(source_summary['batches'])
    protocol = dict(source=str(args.source), model=model, corrections=corrections,
                    quote_corrections=quote_corrections, system_sha256=digest(SYSTEM),
                    source_files={n: {f: hashlib.sha256((args.source / n / f).read_bytes()).hexdigest()
                                      for f in ('cases.jsonl', 'runs.jsonl', 'scored.jsonl')} for n in names},
                    code_sha256={f: hashlib.sha256((Path(__file__).parent / f).read_bytes()).hexdigest()
                                 for f in ('outcome_judge.py', 'repair_outcome_review.py')},
                    max_cost_usd=args.max_cost_usd, total_budget_usd=args.total_budget_usd,
                    scope='Revalidate all quotes; full review for invalid responses/changed keys; reliance for every accepted, unresolved or uncertain flawed report.')
    args.out.mkdir(parents=True, exist_ok=True)
    if (args.out / 'protocol.json').exists():
        if json.loads((args.out / 'protocol.json').read_text(encoding='utf-8')) != protocol:
            raise ValueError('Protocol changed; use another output folder')
    else:
        save_json(args.out / 'protocol.json', protocol)
        for f in protocol['code_sha256']:
            shutil.copyfile(Path(__file__).parent / f, args.out / f)
        shutil.copytree(args.source / 'responses', args.out / 'responses')
        shutil.copyfile(args.source / 'human_validation.json', args.out / 'human_validation.json')

    _, manifest = build_cases(confidence_pair_ids=set())
    batches, items, replay = {}, [], {}
    for name in names:
        cases = load_cases(args.source / name / 'cases.jsonl')
        runs = load_runs(args.source / name / 'runs.jsonl')
        previous = {s.run_id: s for s in load_scores(args.source / name / 'scored.jsonl')}
        changed = apply_corrections(cases, corrections)
        batches[name] = dict(cases=cases, runs=runs)
        for run in runs:
            if run.status != 'completed':
                continue
            case = cases[run.case_id]
            old_hash = previous[run.run_id].scoring_provenance['request_hash']
            result_file = sorted((args.source / 'responses' / old_hash).glob('attempt_*/result.json'))[-1]
            request = json.loads((result_file.parent / 'request.json').read_text(encoding='utf-8'))
            if digest(request) != old_hash or request['model'] != model:
                raise ValueError('Saved request hash or judge model does not match')
            payload = json.loads(request['messages'][1]['content'])
            packet = Packet.model_validate_json((DEFAULT_ROOT / 'public' / manifest[run.case_id]['packet_path']).read_text(encoding='utf-8')).model_dump(mode='json')
            if packet != payload['evidence'] or (run.input_sha256 and digest(
                {'evidence_packet': packet, 'initial_report': run.initial_report}) != run.input_sha256):
                raise ValueError('Saved execution and evidence no longer match')
            outcome, audit, error = None, [], None
            try:
                raw = json.loads((result_file.parent / 'response.txt').read_text(encoding='utf-8'))
                if raw['choices'][0]['finish_reason'] != 'stop':
                    raise ValueError('Incomplete saved response')
                content = raw['choices'][0]['message']['content']
                if old_hash in quote_corrections:
                    content = correct_saved_quote(content, quote_corrections[old_hash])
                    audit.append(dict(method='explicit_quote_correction', **quote_corrections[old_hash]))
                outcome = validate_response(content, payload, quote_audit=audit)
            except (ValueError, KeyError, IndexError) as exc:
                error = str(exc)
            replay[old_hash] = dict(source_result=str(result_file), quote_normalizations=audit,
                                    validation_error=error, outcome=outcome.model_dump() if outcome else None)
            if case.case_id in changed:
                payload['answer_key'] = case.defect
                outcome = None  # Do not reuse any judgement made against the wrong criterion.
            items.append(dict(batch=name, run=run, case=case, payload=payload, outcome=outcome,
                              full_needed=outcome is None, request_hash=old_hash, request_store='responses',
                              key_corrected=case.case_id in changed, quote_normalizations=audit))
    save_json(args.out / 'revalidated.json', replay)

    new_requests = args.out / 'new_requests'
    new_requests.mkdir(exist_ok=True)
    saved, spent = {}, 0.0
    for folder in new_requests.iterdir():
        request = json.loads((folder / 'attempt_001/request.json').read_text(encoding='utf-8'))
        result_path = folder / 'attempt_001/result.json'
        result = json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else {
            'status': 'failed', 'error': 'Interrupted request; reserved its full cost'}
        saved[folder.name] = result
        spent += result.get('usage', {}).get('cost') if result.get('usage', {}).get('cost') is not None else reserve_cost(request)
    api_key, starting_usage, latest_usage = None, None, None
    budget_file = args.out / 'budget.json'
    if budget_file.exists():
        starting_usage = json.loads(budget_file.read_text(encoding='utf-8'))['starting_key_usage_usd']
    if args.execute:
        api_key = os.environ.get('OPENROUTER_API_KEY') or dotenv_values(repo / 'src/.env').get('OPENROUTER_API_KEY')
        if not api_key:
            raise ValueError('OPENROUTER_API_KEY is required')
        latest_usage = key_usage(api_key)
        if starting_usage is None:
            starting_usage = latest_usage
        save_json(budget_file, dict(starting_key_usage_usd=starting_usage,
                                    additional_cap_usd=args.max_cost_usd, total_key_cap_usd=args.total_budget_usd))

    calls, stop_reason, selection = 0, None, {}
    for scope in ('full', 'reliance'):
        chosen = [item for item in items if item['full_needed']] if scope == 'full' else [
            item for item in items if needs_reliance(item['run'], item['case'], item['outcome'])]
        jobs = {}
        for item in chosen:
            payload = copy.deepcopy(item['payload'])
            if scope == 'reliance':
                payload['review'] = []  # Keep both reports; reviewer persuasion is not needed for reliance.
            request = capped_request(payload, model, scope)
            key = digest(request)
            item[scope + '_request'] = key
            jobs[key] = (request, payload)
        selection[scope] = [dict(batch=i['batch'], run_id=i['run'].run_id, request_hash=i[scope + '_request']) for i in chosen]
        # Exercise the two observed rubric failures first; the full pass still covers every eligible run.
        def priority(key):
            payload = jobs[key][1]
            example = (payload['evidence']['packet_id'], (payload['answer_key'] or {}).get('defect_type'))
            return (example not in (('EP_0002', 'arithmetic'), ('EP_0003', 'reporting_period')), key)
        pending = sorted((k for k in jobs if k not in saved), key=priority)
        if args.limit is not None:
            pending = pending[:max(0, args.limit - calls)]
        if args.execute and not stop_reason:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for start in range(0, len(pending), args.workers):
                    keys = pending[start:start + args.workers]
                    reserve = sum(reserve_cost(jobs[k][0]) for k in keys)
                    latest_usage = key_usage(api_key)
                    if not budget_allows(spent, reserve, latest_usage, starting_usage,
                                         args.max_cost_usd, args.total_budget_usd):
                        stop_reason = 'spending cap'
                        break
                    futures = [(k, pool.submit(call_judge, *jobs[k], new_requests / k / 'attempt_001', api_key)) for k in keys]
                    for key, future in futures:
                        result = future.result()
                        saved[key] = result
                        cost = result.get('usage', {}).get('cost')
                        spent += cost if cost is not None else reserve_cost(jobs[key][0])
                        calls += 1
                        print(f'{scope}: {calls} new calls, {result["status"]}, additional cost ${spent:.4f}', flush=True)
                        if result.get('http_status') in (401, 402, 403, 429):
                            stop_reason = f'provider HTTP {result["http_status"]}'
                    if stop_reason:
                        break
        for item in chosen:
            key = item[scope + '_request']
            result = saved.get(key, {})
            if scope == 'full':
                item.update(request_hash=key, request_store='new_requests')
                item['outcome'] = Outcome.model_validate(result['outcome']) if result.get('status') == 'completed' else None
                item['quote_normalizations'] = result.get('quote_normalizations', [])
            else:
                # Never silently keep an old reliance label if its replacement is unavailable.
                item['outcome'].materially_used_by_trader = (RelianceOutcome.model_validate(result['outcome']).materially_used_by_trader
                    if result.get('status') == 'completed' else item['outcome'].materially_used_by_trader.model_copy(
                        update={'value': None, 'reason': 'Reassessment is pending or failed validation.', 'quotes': [], 'evidence_ids': []}))
    save_json(args.out / 'selection.json', selection)

    summary = {}
    lookup = {(i['batch'], i['run'].run_id): i for i in items}
    for name, batch in batches.items():
        folder = args.out / name
        folder.mkdir(exist_ok=True)
        write_jsonl(folder / 'runs.jsonl', batch['runs'])
        write_jsonl(folder / 'cases.jsonl', batch['cases'].values())
        scores = []
        for run in batch['runs']:
            item = lookup.get((name, run.run_id), {})
            score = reviewed_score(run, batch['cases'][run.case_id], item.get('outcome'),
                                  model=model, request_hash=item.get('request_hash'))
            if item:
                score.scoring_provenance.update(request_store=item['request_store'],
                    quote_normalizations=item['quote_normalizations'], annotation_corrected=item['key_corrected'],
                    reliance_request_hash=item.get('reliance_request'), source_review=str(args.source),
                    reliance_quote_normalizations=saved.get(item.get('reliance_request'), {}).get('quote_normalizations', []))
            scores.append(score)
        write_jsonl(folder / 'scored.jsonl', scores)
        completed = {r.run_id for r in batch['runs'] if r.status == 'completed'}
        save_json(folder / 'pending.json', pending_worksheet(batch['runs'], [s for s in scores if s.run_id in completed], batch['cases']))
        save_json(folder / 'output_review.json', output_review_worksheet(batch['runs'], scores))
        (folder / 'findings.md').write_text(format_report(batch['runs'], scores, batch['cases'],
            'Repaired LLM review (independent human validation pending)') + '\n', encoding='utf-8')
        summary[name] = dict(completed=len(completed), primary_pending=sum(s.scoring_status == 'pending' and s.run_id in completed for s in scores),
                             new_error_pending=sum(s.new_error_present is None and s.run_id in completed for s in scores))
    if args.execute:
        latest_usage = key_usage(api_key)
    active_requests = {item['request_hash'] for selected in selection.values() for item in selected}
    save_json(args.out / 'summary.json', dict(batches=summary, additional_cost_usd=spent,
        starting_key_usage_usd=starting_usage, latest_key_usage_usd=latest_usage, stop_reason=stop_reason,
        planned_full=len(selection['full']), planned_reliance=len(selection['reliance']),
        new_requests=len(saved), failed_requests=sum(r['status'] != 'completed' for r in saved.values()),
        active_failed_requests=sum(k in saved and saved[k]['status'] != 'completed' for k in active_requests),
        active_pending_requests=sum(k not in saved for k in active_requests)))
    print((args.out / 'summary.json').read_text(encoding='utf-8'))


if __name__ == '__main__':
    main()
