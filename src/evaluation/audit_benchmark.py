"""Check source provenance, masked inputs and frozen pair edits without model calls."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.benchmark.prepare import ROOT, assert_masked, check_report, load_agent_input, mask, read
from src.benchmark.schemas import Evidence, Fact, Packet, Report


def audit(root=ROOT):
    root = Path(root)
    aliases = read(root / 'private/aliases.json')
    pairs = read(root / 'private/pairs.json')['pairs']
    errors, hashes = [], {}
    packets = sorted((root / 'public/evidence_packets').glob('*.json'))
    for path in packets:
        try:
            original = read(root / 'private/packets' / path.name)
            source_path = root / 'private/sources' / (original['source_id'] + '.txt')
            source_bytes = source_path.read_bytes()
            meta = read(source_path.with_suffix('.json'))
            assert hashlib.sha256(source_bytes).hexdigest() == meta['text_sha256'], 'source hash differs'
            source = source_bytes.decode('utf-8').replace('\r\n', '\n')
            excerpts = {e['evidence_id']: e for e in original['evidence']}
            for e in excerpts.values():
                assert source[slice(*e['source_span'])] == e['text'], 'source span differs: ' + e['evidence_id']
            for f in original['facts']:
                assert f['source_value'] in excerpts[f['evidence_id']]['text'], 'fact absent from excerpt: ' + f['fact_id']
                assert Decimal(f['source_value'].replace(',', '')) == Decimal(f['value']), 'fact value differs'
            public = {k: original[k] for k in ('packet_id', 'company_alias', 'fiscal_year')}
            public['evidence'] = [{k: e[k] for k in Evidence.model_fields} for e in original['evidence']]
            public['facts'] = [{k: f[k] for k in Fact.model_fields} for f in original['facts']]
            expected = Packet.model_validate(mask(public, aliases)).model_dump(mode='json')
            assert read(path) == expected, 'public packet differs from deterministic masking'
            for report_path in sorted((root / 'public/reports' / path.stem).glob('*.json')):
                data = load_agent_input(path, report_path, check_clean=False)
                assert_masked(data, aliases)
                if report_path.stem == 'clean':
                    checks = check_report(Packet.model_validate(expected), Report.model_validate(data['initial_report']), require_fact_ids=True)
                    assert not checks['errors'], checks['errors']
                hashes[str(report_path.relative_to(root))] = hashlib.sha256(report_path.read_bytes()).hexdigest()
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        except (AssertionError, ValueError, KeyError, OSError) as exc:
            errors.append({'packet': path.stem, 'error': str(exc)})
    for pair in pairs:
        try:
            expected = read(root / 'public' / pair['clean_report_path'])
            for change in pair['changes']:
                target = expected
                for key in change['path'][:-1]:
                    target = target[key]
                key = change['path'][-1]
                assert target[key] == change['before'], 'before value differs'
                target[key] = change['after']
            expected['report_id'] = pair['flawed_report_id']
            assert expected == read(root / 'public' / pair['flawed_report_path']), 'unrecorded pair edits'
        except (AssertionError, ValueError, KeyError, OSError) as exc:
            errors.append({'pair': pair['pair_id'], 'error': str(exc)})
    return {'packets': len(packets), 'clean_reports': len(packets), 'flawed_reports': len(pairs),
            'defect_counts': dict(Counter(p['defect_type'] for p in pairs)), 'errors': errors,
            'public_file_sha256': hashes,
            'scope': 'Source spans, masking, structured assertions and frozen edits. Semantic clean-report review remains a human responsibility.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = audit(args.root)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'public_file_sha256'}, indent=2))
    sys.exit(bool(result['errors']))
