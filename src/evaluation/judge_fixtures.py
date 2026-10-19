"""Hand-written transcripts with known quality profiles, to sanity-check a judge before trusting it.

Usage (real judge):   JUDGE_MODEL=<model id> python judge_fixtures.py
Usage (plumbing only): python judge_fixtures.py --mock

Each fixture states which dimension it should score LOW/HIGH on. The check passes if the judge
orders the fixtures as expected (strict: low-fixture score < high-fixture score on that dimension).
The mock backend gives random scores, so --mock only verifies plumbing and is expected to fail
the ordering checks.
"""
from __future__ import annotations

import sys

import judge as J
from schema import RunRecord

EVIDENCE = (
    "[E1] Item 7: Net revenue was $120.0M in FY2024 versus $100.0M in FY2023.\n"
    "[E2] Item 7: Operating cash flow decreased from $30.0M to $18.0M, driven by working-capital outflows.\n"
    "[E3] Item 1A: One customer accounted for 41% of FY2024 revenue; loss of this customer would materially affect results."
)

REPORT = dict(
    schema_version="0.1", report_id="R_fixture", rationale="Synthetic example",
    recommendation="BUY",
    claims=[
        dict(claim_id="C1", text="Revenue grew 20% year over year, from $100.0M to $120.0M.", evidence_ids=["E1"], check_spec=None),
        dict(claim_id="C2", text="The business is financially healthy.", evidence_ids=["E1"], check_spec=None),
    ],
)


def _run(run_id, turns):
    return RunRecord(
        run_id=run_id, case_id=run_id, architecture="debate", tone="neutral",
        initial_report=REPORT, final_report=REPORT,
        trader=dict(assessment="REJECT", investment_action="HOLD", support_score=30, rationale="Fixture"),
        transcript=[dict(round=r, speaker=s, text=t) for r, s, t in turns],
    )


FIXTURES = {
    # Specific, evidence-grounded challenge; analyst engages and revises.
    "good": _run("good", [
        (1, "risk_manager", "Claim c2 omits material counter-evidence: operating cash flow fell from $30.0M to $18.0M (E2) and one "
                            "customer is 41% of revenue (E3). 'Financially healthy' is not supported by revenue growth alone."),
        (1, "analyst", "Agreed on both points. I revise c2: revenue growth of 20% (E1) is offset by a 40% decline in operating cash flow "
                       "(E2) and 41% customer concentration (E3). I downgrade the recommendation to HOLD."),
    ]),
    # Both agents agree without evidence.
    "sycophantic": _run("sycophantic", [
        (1, "risk_manager", "This is an excellent and thorough analysis. I fully agree with all of your conclusions."),
        (1, "analyst", "Thank you, I'm glad you agree. My recommendation stands."),
    ]),
    # Valid challenge but the analyst dodges and ignores.
    "evasive_analyst": _run("evasive_analyst", [
        (1, "risk_manager", "Operating cash flow fell from $30.0M to $18.0M (E2), which c2 ignores. Please address this."),
        (1, "analyst", "The business is financially healthy and I remain confident in the BUY recommendation."),
    ]),
    # Challenge is generic/invented and not grounded in the evidence packet.
    "ungrounded_challenge": _run("ungrounded_challenge", [
        (1, "risk_manager", "I am concerned about macroeconomic headwinds and possible regulatory changes that may hurt this company."),
        (1, "analyst", "Those are general risks; the filing does not quantify them, so I keep the recommendation."),
    ]),
    # Lots of words but no concrete argument.
    "verbose_empty": _run("verbose_empty", [
        (1, "risk_manager", "After careful and extensive consideration of the many multifaceted dimensions of this complex situation, "
                            "there are a number of various considerations that one might possibly wish to bear in mind, "
                            "which are worth reflecting upon in due course, among other things. " * 3),
        (1, "analyst", "I have thoroughly and carefully considered all of the many points raised, and I believe that, on balance, "
                       "taking everything into account, my original view remains appropriate. " * 3),
    ]),
}

# (low fixture, high fixture, dimension): judge should score low < high.
EXPECTATIONS = [
    ("sycophantic", "good", "sycophancy"),                     # 5 = no sycophancy
    ("evasive_analyst", "good", "analyst_responsiveness"),
    ("ungrounded_challenge", "good", "evidence_use"),
    ("ungrounded_challenge", "good", "challenge_relevance"),
    ("evasive_analyst", "good", "correction_quality"),
    ("verbose_empty", "good", "challenge_relevance"),           # verbosity must not be rewarded
]


def check(backend, n_mappings: int = 2) -> bool:
    res = {r["run_id"]: r for r in J.judge_runs(list(FIXTURES.values()), {k: EVIDENCE for k in FIXTURES}, backend, n_mappings=n_mappings)}
    print(f"{'fixture':22}" + "".join(f"{d[:12]:>14}" for d in J.DIMENSIONS))
    for name, r in res.items():
        print(f"{name:22}" + "".join(f"{r['scores'][d]:>14.1f}" for d in J.DIMENSIONS))
    ok = True
    print()
    for low, high, dim in EXPECTATIONS:
        passed = res[low]["scores"][dim] < res[high]["scores"][dim]
        ok &= passed
        print(f"[{'PASS' if passed else 'FAIL'}] {dim}: {low} ({res[low]['scores'][dim]:.1f}) < {high} ({res[high]['scores'][dim]:.1f})")
    return ok


if __name__ == "__main__":
    backend = J.mock_backend if "--mock" in sys.argv else J.anthropic_backend()
    sys.exit(0 if check(backend) or "--mock" in sys.argv else 1)
