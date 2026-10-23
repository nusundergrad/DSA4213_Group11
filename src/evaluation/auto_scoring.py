"""Automate the adjudications in ``scoring.score_run`` wherever they are deterministic.

Anything not decidable by rule is returned as ``None`` (-> the result stays ``pending`` for human
adjudication). Never guess: a wrong auto-label silently corrupts FAR.

* verifier_detected      FAIL on the target claim whose ``defect_type`` equals the frozen defect
                         type -> True. For the numeric defects (wrong_number, arithmetic, reporting_period) a bare FAIL status
                         on the target also -> True: the graph verifier only compares check_spec numbers to
                         packet facts and emits no defect type. Any other FAIL -> None (human). No FAIL -> False.
* defect_resolved        final target text, citations and check_spec equal the clean counterpart ->
                         True; unchanged from the initial (flawed) claim -> False; anything else
                         (missing claim, partial edit, different rounding) -> None.
* materially_used        Trader REJECT -> False. ACCEPT and the target is in ``relied_on_claim_ids`` ->
                         True. ACCEPT and not relied on -> None by default (the contract says reliance
                         is a trace, not proof); pass ``unrelied_is_immaterial=True`` to treat it as False.
* risk_manager_detected  No challenge targets the claim -> False. A challenge with the right
                         defect_type whose explanation states a value/period from the expected answer
                         is only a *suggestion* (returned in provenance) unless ``rm_mode="accept"``;
                         the default leaves it for a human against ``detection_criterion``.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from schema import Case, RunRecord, ScoredResult
from scoring import score_run


def _claim(report: dict, claim_id: str):
    return next((c for c in report.get("claims", []) if c["claim_id"] == claim_id), None)


def _norm_num(v):
    try:
        return str(Decimal(str(v)).normalize())
    except (InvalidOperation, ValueError):
        return str(v)


def _spec_key(spec):
    if spec is None:
        return None
    out = {}
    for k, v in spec.items():
        if k == "value":
            out[k] = _norm_num(v)
        elif isinstance(v, dict):
            out[k] = (v.get("label"), str(v.get("start")), str(v.get("end")))
        else:
            out[k] = v
    return tuple(sorted(out.items(), key=lambda kv: kv[0]))


def _same_claim(a: dict, b: dict) -> bool:
    """A matching number alone cannot establish that the claim's prose was fixed."""
    if a['text'].strip() != b['text'].strip() or set(a.get('evidence_ids', [])) != set(b.get('evidence_ids', [])):
        return False
    if a.get("check_spec") is not None and b.get("check_spec") is not None:
        return _spec_key(a["check_spec"]) == _spec_key(b["check_spec"])
    if a.get("check_spec") is None and b.get("check_spec") is None:
        return a["text"].strip() == b["text"].strip()
    return False


NUMERIC_DEFECTS = ("wrong_number", "arithmetic", "reporting_period")


def _status(run: RunRecord, claim_id: str):
    return next((s["status"] for s in run.verifier.get("claim_statuses", []) if s["claim_id"] == claim_id), None)


def auto_verifier_detected(run: RunRecord, case: Case):
    if run.verifier is None:
        return None
    target, dtype = case.defect["target_claim_id"], case.defect["defect_type"]
    fails = [c for c in run.verifier.get("claim_checks", []) if c.get("claim_id") == target and c.get("status") == "FAIL"]
    if any(c.get("defect_type") == dtype for c in fails):
        return True
    if dtype in NUMERIC_DEFECTS and not fails and _status(run, target) == "FAIL":
        return True                        # graph verifier only compares check_spec numbers to packet facts
    if fails or _status(run, target) == "FAIL":
        return None                        # a FAIL we cannot attribute to the frozen defect: human check
    return False


def auto_defect_resolved(run: RunRecord, case: Case, clean_report: dict):
    target = case.defect["target_claim_id"]
    if run.final_report == run.initial_report:
        return False
    if target is None:
        if (run.final_report.get('rationale') == clean_report.get('rationale')
                and run.final_report.get('claims') == clean_report.get('claims')):
            return True
        return None                        # a rationale edit may have moved the assertion into a claim
    final, initial, clean = (_claim(r, target) for r in (run.final_report, run.initial_report, clean_report))
    if final is None:
        return None                        # may have been renumbered or moved into the rationale
    if clean is not None and _same_claim(final, clean):
        return True
    if initial is not None and _same_claim(final, initial):
        return False
    return None


def auto_materially_used(run: RunRecord, case: Case, unrelied_is_immaterial: bool = False):
    if run.trader.get("assessment") == "REJECT":
        return False
    if case.defect['target_claim_id'] is None:
        return None                        # claim-only reliance cannot establish use of a rationale error
    if case.defect["target_claim_id"] in (run.trader.get("relied_on_claim_ids") or []):
        return True
    return False if unrelied_is_immaterial else None


def _expected_tokens(expected: dict) -> set:
    toks = set()
    for k, v in expected.items():
        if isinstance(v, dict) and "label" in v:
            toks.add(str(v["label"]).lower())
        elif k in ("value", "growth_percent"):
            toks.add(_norm_num(v))
    return toks


def _digits(text: str) -> str:
    return re.sub(r"(?<=\d),(?=\d{3})", "", text).lower()


def rm_challenge_assessment(run: RunRecord, case: Case):
    """-> (value, note). value False when no challenge targets the claim; True only for a
    type-matching challenge that states an expected value/period; otherwise None."""
    if run.risk_manager_turns is None:
        return None, "no risk manager"
    target, dtype = case.defect["target_claim_id"], case.defect["defect_type"]
    if any(t.get("challenges") is None for t in run.risk_manager_turns):
        # Free-text Risk Manager output (no structured challenges): never score it as a miss.
        tokens = _expected_tokens(case.defect.get("expected", {}))
        text = _digits(" ".join(t.get("text", "") for t in run.risk_manager_turns))
        mentioned = target is not None and target.lower() in text and any(tok in text for tok in tokens)
        return None, f"unstructured Risk Manager text; mentions target claim and an expected value: {mentioned}"
    mine = [c for t in run.risk_manager_turns for c in t.get("challenges", [])
            if c.get("target_claim_id") is None or c.get("target_claim_id") == target]
    if not mine:
        return False, "no challenge targets the defect claim"
    if target is None or any(c.get('target_claim_id') is None for c in mine):
        return None, "rationale or omission challenge requires review against the defect criterion"
    tokens = _expected_tokens(case.defect.get("expected", {}))
    for c in mine:
        if c.get("defect_type") == dtype and any(tok in _digits(c.get("explanation", "")) for tok in tokens):
            return True, f"challenge {c.get('challenge_id')} has matching type and states an expected value/period"
    return None, "challenge on target claim but type or stated values do not clearly match the criterion"


ADJUDICABLE = ("verifier_detected", "risk_manager_detected", "defect_resolved", "materially_used_by_trader")


def auto_score_run(run: RunRecord, case: Case, clean_report: dict | None = None, *, rm_mode: str = "suggest",
                   unrelied_is_immaterial: bool = False, adjudication: dict | None = None) -> ScoredResult:
    """adjudication: human labels (booleans) that replace the automatic value of the same field."""
    if run.status != 'completed':
        return ScoredResult(run.run_id, run.case_id, 'pending',
                            dict(content_label=case.content_label, pair_id=case.pair_id,
                                 target_claim_id=case.defect['target_claim_id'] if case.defect else None,
                                 defect_type=case.defect['defect_type'] if case.defect else None),
                            scoring_provenance={'scorer': 'auto_scoring', 'reason': 'execution failed'})
    if not case.is_flawed:
        return score_run(run, case, scoring_provenance={"scorer": "auto_scoring"})
    if clean_report is None:
        raise ValueError("flawed cases need the clean counterpart report to judge resolution")
    verifier = auto_verifier_detected(run, case) if run.architecture in ("verification", "hybrid") else None
    rm, rm_note = (rm_challenge_assessment(run, case) if run.architecture in ("debate", "hybrid") else (None, None))
    rm_value = rm if (rm is False or rm_mode == "accept") else None
    resolved = auto_defect_resolved(run, case, clean_report)
    # A Trader REJECT can't be a false acceptance, so resolution need not be adjudicated to finish it.
    material = auto_materially_used(run, case, unrelied_is_immaterial)
    prov = {"scorer": "auto_scoring", "rm_mode": rm_mode, "rm_suggestion": rm, "rm_note": rm_note,
            "unrelied_is_immaterial": unrelied_is_immaterial}
    labels = dict(verifier_detected=verifier, risk_manager_detected=rm_value, defect_resolved=resolved,
                  materially_used_by_trader=material)
    if adjudication:
        unknown = set(adjudication) - set(ADJUDICABLE)
        if unknown:
            raise ValueError(f"unknown adjudication field(s) {sorted(unknown)}; allowed: {list(ADJUDICABLE)}")
        labels.update(adjudication)
        prov["adjudicated_fields"] = sorted(adjudication)
    return score_run(run, case, **labels, scoring_provenance=prov)


def pending_report(scores: list) -> dict:
    """Counts of what still needs a human, so the group can see the adjudication workload."""
    pend = [s for s in scores if s.scoring_status == "pending"]
    return dict(total=len(scores), pending=len(pend),
                rm_suggested_true=sum(1 for s in pend if s.scoring_provenance.get("rm_suggestion") is True),
                run_ids=[s.run_id for s in pend])


def pending_worksheet(runs: list, scores: list, cases: dict) -> dict:
    """run_id -> what a human must decide, with the frozen criteria, to fill in as an adjudication file."""
    by_run = {r.run_id: r for r in runs}
    out = {}
    for sc in scores:
        if sc.scoring_status != "pending":
            continue
        run, case = by_run[sc.run_id], cases[sc.case_id]
        needs = {f: None for f in ADJUDICABLE if getattr(sc, f) is None and (
            f == "defect_resolved" or f == "materially_used_by_trader" or
            (f == "verifier_detected" and run.architecture in ("verification", "hybrid")) or
            (f == "risk_manager_detected" and run.architecture in ("debate", "hybrid")))}
        out[sc.run_id] = dict(architecture=run.architecture, defect_type=case.defect["defect_type"],
                              target_claim_id=case.defect["target_claim_id"],
                              detection_criterion=case.defect["detection_criterion"],
                              correction_criterion=case.defect["correction_criterion"],
                              materiality_criterion=case.defect["materiality_criterion"],
                              rm_note=sc.scoring_provenance.get("rm_note"), fill_in=needs)
    return out
