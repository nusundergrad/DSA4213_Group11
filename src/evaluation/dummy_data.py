"""Synthetic contract fixtures. Planted outcomes are software checks, not findings."""
from __future__ import annotations

import random

from schema import ARCHITECTURES, TONES, OBJECTIVE_DEFECTS, REASONING_DEFECTS, Case, RunRecord
from scoring import score_run

PLANTED = {
    "baseline": dict(det_obj=0, det_rea=0, corr=0, acc_clean=.95, acc_undet=.85, acc_det=.85, shift=15),
    "debate": dict(det_obj=.35, det_rea=.55, corr=.6, acc_clean=.90, acc_undet=.80, acc_det=.35, shift=8),
    "verification": dict(det_obj=.85, det_rea=0, corr=0, acc_clean=.93, acc_undet=.80, acc_det=.30, shift=4),
    "hybrid": dict(det_obj=.90, det_rea=.60, corr=.7, acc_clean=.92, acc_undet=.60, acc_det=.15, shift=2),
}
TONE_SIGN = {"underconfident": -1, "neutral": 0, "overconfident": 1}


def make_cases(n_pairs=40, n_tone_pairs=12, seed=0):
    rng = random.Random(seed)
    types = ([REASONING_DEFECTS[i % 2] for i in range(max(2, n_pairs // 5))] +
             [OBJECTIVE_DEFECTS[i % len(OBJECTIVE_DEFECTS)] for i in range(n_pairs - max(2, n_pairs // 5))])
    rng.shuffle(types)
    tone_pairs = set(rng.sample(range(n_pairs), n_tone_pairs))
    cases = {}
    for i in range(n_pairs):
        pair_id = f"PAIR_{i:04d}"
        target = f"C{rng.randint(1, 3)}"
        for flawed in (False, True):
            case_id = f"CASE_{2*i + int(flawed):04d}"
            defect = ({"target_claim_id": target, "defect_type": types[i],
                       "detection_criterion": "Identify the planted claim error",
                       "correction_criterion": "Repair or retract the planted claim",
                       "materiality_criterion": "Unresolved claim supports acceptance"} if flawed else None)
            cases[case_id] = Case(case_id, pair_id, "injected_error" if flawed else "unmodified",
                                  i in tone_pairs, defect)
    return cases


def _report(case, flawed, tone):
    claims = []
    for i in range(1, 4):
        cid = f"C{i}"
        statement = f"Synthetic claim {i}" + (" [PLANTED ERROR]" if flawed and cid == case.defect["target_claim_id"] else "")
        claims.append(dict(claim_id=cid, text=statement, evidence_ids=["EP_0001_E01"], check_spec=None))
    report_id = "R_" + (case.case_id + tone).replace("_", "")
    return dict(schema_version="0.1", report_id=report_id, recommendation="BUY",
                claims=claims, rationale="Synthetic rationale")


def make_runs(cases, seed=0, architectures=ARCHITECTURES):
    runs, scores = [], []
    for case in cases.values():
        for arch in architectures:
            p = PLANTED[arch]
            rng = random.Random(f"{seed}|{case.case_id}|{arch}")
            u_det, u_corr, u_acc, u_noise = (rng.random() for _ in range(4))
            for tone in (TONES if case.confidence_subset else ("neutral",)):
                shift = TONE_SIGN[tone] * p["shift"]
                det_p = p["det_obj"] if case.defect and case.defect["defect_type"] in OBJECTIVE_DEFECTS else p["det_rea"]
                det_p = max(0, min(1, det_p - (shift / 200 if arch in ("debate", "hybrid") else 0)))
                found = case.is_flawed and u_det < det_p
                corrected = found and arch in ("debate", "hybrid") and u_corr < p["corr"]
                acc_p = (p["acc_clean"] if not case.is_flawed or corrected else
                         p["acc_det"] if found else p["acc_undet"])
                accepted = u_acc < max(0, min(1, acc_p + shift / 100))
                support = max(0, min(100, (80 if accepted else 30) + shift + (u_noise - .5) * 10))
                initial = _report(case, case.is_flawed, tone)
                final = _report(case, case.is_flawed and not corrected, tone)
                target = case.defect["target_claim_id"] if case.defect else None
                verifier = None
                if arch in ("verification", "hybrid"):
                    statuses = []
                    for claim in initial["claims"]:
                        status = ("NOT_CHECKABLE" if case.is_flawed and claim["claim_id"] == target and
                                  case.defect["defect_type"] in REASONING_DEFECTS else
                                  "FAIL" if found and claim["claim_id"] == target else "PASS")
                        statuses.append(dict(claim_id=claim["claim_id"], status=status, reason="synthetic"))
                    verifier = dict(schema_version="0.1", claim_checks=[], claim_statuses=statuses)
                risk_turns = None
                revisions = None
                transcript = None
                if arch in ("debate", "hybrid"):
                    challenge = (dict(challenge_id="RM_R1_01", target_claim_id=target,
                                      defect_type=case.defect["defect_type"], evidence_ids=["EP_0001_E01"],
                                      explanation="Synthetic challenge", requested_change="Revise") if found else None)
                    risk_turns = [dict(schema_version="0.1", round=1, challenges=[challenge] if challenge else [],
                                       calibration_concern=None, overall_assessment="Synthetic assessment")]
                    revisions = [dict(schema_version="0.1", round=1, responses=[], updated_report=final,
                                      retracted_claim_ids=[])]
                    transcript = [dict(round=1, speaker="risk_manager", text="Challenge to claim" if found else "No material issue"),
                                  dict(round=1, speaker="analyst", text="I revise the claim" if corrected else "I maintain the claim")]
                run = RunRecord(run_id=f"{case.case_id}|{arch}|{tone}", case_id=case.case_id,
                                architecture=arch, tone=tone, initial_report=initial, final_report=final,
                                trader=dict(schema_version="0.1", assessment="ACCEPT" if accepted else "REJECT",
                                            support_score=support, investment_action="BUY" if accepted else "HOLD",
                                            relied_on_claim_ids=[target] if case.is_flawed and accepted and not corrected else [],
                                            rationale="Synthetic rationale"), verifier=verifier,
                                risk_manager_turns=risk_turns, analyst_revision_turns=revisions, transcript=transcript,
                                usage=dict(input_tokens=1000, output_tokens=300, latency_ms=2000, estimated_cost_usd=.01))
                runs.append(run)
                scores.append(score_run(run, case, verifier_detected=(found and case.defect["defect_type"] in OBJECTIVE_DEFECTS if case.is_flawed and arch in ("verification", "hybrid") else None),
                                        risk_manager_detected=(found if arch in ("debate", "hybrid") else None),
                                        defect_resolved=(corrected if case.is_flawed else None),
                                        materially_used_by_trader=(accepted and not corrected if case.is_flawed else None),
                                        scoring_provenance={"scorer": "synthetic_fixture"}))
    return runs, scores
