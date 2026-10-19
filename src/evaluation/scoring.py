"""Join completed executions to private answers after agents finish.

Human review supplies semantic judgements. A matching claim ID alone is not proof
that a challenge identified the actual defect described in the frozen answer key.
"""
from __future__ import annotations

from schema import Case, RunRecord, ScoredResult


def score_run(run: RunRecord, case: Case, *, verifier_detected=None, risk_manager_detected=None,
              defect_resolved=None, materially_used_by_trader=None,
              scoring_provenance=None) -> ScoredResult:
    if run.case_id != case.case_id:
        raise ValueError("run and answer key refer to different cases")
    if run.status != "completed":
        raise ValueError("failed or unfinished runs cannot be scored")
    if run.trader.get("assessment") not in ("ACCEPT", "REJECT"):
        raise ValueError("Trader assessment must be ACCEPT or REJECT")
    score = run.trader.get("support_score")
    # support_score only feeds the tone analysis; None means the graph did not produce one.
    if score is not None and (not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100):
        raise ValueError("Trader support_score must be between 0 and 100")
    truth = {"content_label": case.content_label, "pair_id": case.pair_id,
             "target_claim_id": case.defect["target_claim_id"] if case.defect else None,
             "defect_type": case.defect["defect_type"] if case.defect else None}
    base = dict(run_id=run.run_id, case_id=run.case_id, ground_truth=truth,
                scoring_provenance=scoring_provenance or {})
    if not case.is_flawed:
        return ScoredResult(scoring_status="not_applicable", **base)
    if not case.defect:
        raise ValueError("injected case needs a defect answer key")

    target = case.defect["target_claim_id"]
    if run.architecture in ("verification", "hybrid"):
        if run.verifier is None:
            raise ValueError("verifier output missing")
        # FAIL is a candidate; the evaluator must verify the failed rule matches
        # the frozen defect criterion before supplying a scored Boolean.
        statuses = run.verifier.get("claim_statuses", [])
        if verifier_detected is True and not any(x["claim_id"] == target and x["status"] == "FAIL" for x in statuses):
            raise ValueError("verifier_detected=True requires a FAIL on the target claim")
        if verifier_detected is not None and type(verifier_detected) is not bool:
            raise ValueError("verifier_detected must be bool or None")
    else:
        verifier_detected = None
    if run.architecture in ("debate", "hybrid"):
        if run.risk_manager_turns is None:
            raise ValueError("risk manager turns missing")
        # A reviewer checks the challenge against the frozen detection criterion.
        if risk_manager_detected is not None and type(risk_manager_detected) is not bool:
            raise ValueError("risk_manager_detected must be bool or None")
        if risk_manager_detected is True and not any(
            challenge.get("target_claim_id") == target and
            challenge.get("defect_type") == case.defect["defect_type"]
            for turn in run.risk_manager_turns for challenge in (turn.get("challenges") or [])
        ):
            raise ValueError("risk_manager_detected=True requires a matching challenge")
    else:
        risk_manager_detected = None
    detected = (verifier_detected is True or risk_manager_detected is True) if run.architecture != "baseline" else None
    if run.architecture in ("debate", "hybrid") and risk_manager_detected is None:
        detected = None if verifier_detected is not True else True

    if defect_resolved is not None and type(defect_resolved) is not bool:
        raise ValueError("defect_resolved must be bool or None")
    if materially_used_by_trader is not None and type(materially_used_by_trader) is not bool:
        raise ValueError("materially_used_by_trader must be bool or None")
    corrected = (defect_resolved if detected is True else None) if run.architecture in ("debate", "hybrid") else None
    complete = defect_resolved is not None and (detected is not None or run.architecture == "baseline")
    if run.trader["assessment"] == "ACCEPT" and defect_resolved is False:
        complete = complete and materially_used_by_trader is not None
    false_acceptance = None
    if complete:
        false_acceptance = (run.trader["assessment"] == "ACCEPT" and
                            defect_resolved is False and materially_used_by_trader is True)
    return ScoredResult(scoring_status="complete" if complete else "pending",
                        verifier_detected=verifier_detected,
                        risk_manager_detected=risk_manager_detected, detected=detected,
                        corrected_after_detection=corrected, defect_resolved=defect_resolved,
                        materially_used_by_trader=materially_used_by_trader,
                        false_acceptance=false_acceptance, **base)
