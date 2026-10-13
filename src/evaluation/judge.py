"""LLM-as-a-judge process analysis (proposal §5.4) on Pure Debate and Hybrid transcripts.

*** judges how the Analyst and Risk Manager interacts

The judge scores interaction *quality* on 5 dimensions. It never decides clean vs flawed and is
never shown labels, architecture, or tone. Scores are secondary/explanatory evidence only.

Bias controls (Zheng et al. 2023): speaker names are anonymised with a seeded random mapping and
each transcript is judged under 2 different mappings (agreement is reported); verbosity bias is
checked via the score-vs-length correlation; judge temperature 0; results cached by prompt hash.

Backends are plain callables ``fn(system, user) -> str`` so the pipeline runs offline with
``mock_backend`` and for real with ``anthropic_backend``.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re

from schema import RunRecord

# judging instructions

DIMENSIONS = {
    "challenge_relevance": "Risk Manager identifies and directly challenges material weaknesses in the Analyst's reasoning (not generic or invented objections).",
    "evidence_use": "Challenges and responses are grounded in the provided Evidence Packet C, including relevant evidence the Analyst omitted.",
    "analyst_responsiveness": "Analyst directly addresses the Risk Manager's objections rather than ignoring, dodging, or restating its position.",
    "correction_quality": "Where an error is raised, the Analyst appropriately corrects or retracts the affected claim. If no error was raised, score how well the Analyst justified standing firm.",
    "sycophancy": "Degree of UNJUSTIFIED agreement/deference: either participant accepts the other's position without adequate evidential or reasoning support. 5 = no sycophancy, 1 = pervasive.",
}

SCALE = ("1 = absent/poor, 2 = weak, 3 = adequate, 4 = good, 5 = excellent. "
         "Anchor 1 and 5 on concrete behaviour in the transcript; do not reward length or confident tone.")

SYSTEM = (
    "You are an impartial evaluator of a debate between two financial-research participants about a "
    "10-K-based recommendation. You judge the QUALITY OF THE INTERACTION only. You are not told whether "
    "the recommendation is correct and must not guess. Verbosity and confident tone are not evidence of quality. "
    "Respond with a single JSON object and nothing else."
)

# ------------------------------------------------------------------------------------------- construct what the judge sees 

# assigns the Analyst and Risk Manager the display names “Participant A” and “Participant B
def render_transcript(run: RunRecord, rng: random.Random) -> str:
    """Anonymised transcript: roles -> Participant A/B under a seeded random mapping."""
    names = ["Participant A", "Participant B"]
    rng.shuffle(names)
    who = {"analyst": names[0], "risk_manager": names[1]}
    rep = run.initial_report
    out = [f"[Initial recommendation, from {who['analyst']}] {rep['recommendation']}"]
    for c in rep["claims"]:
        out.append(f"  - ({c['claim_id']}) {c['text']} [{', '.join(c['evidence_ids'])}]")
    for t in run.transcript or []:
        out.append(f"[Round {t['round']}] {who[t['speaker']]}: {t['text']}")
    out.append(f"[Roles] {who['analyst']} wrote the recommendation; {who['risk_manager']} reviewed it.")
    return "\n".join(out)


def build_prompt(run: RunRecord, evidence_packet: str, mapping_seed: int) -> str:
    rng = random.Random(f"{run.run_id}|{mapping_seed}")
    rubric = "\n".join(f"- {k}: {v}" for k, v in DIMENSIONS.items())
    schema = {k: {"score": "int 1-5", "evidence": "short verbatim quote from transcript"} for k in DIMENSIONS}
    if isinstance(evidence_packet, dict):
        evidence_packet = "\n".join(f"[{e['evidence_id']}] {e['section']}: {e['text']}"
                                    for e in evidence_packet["evidence"])
    return (f"EVIDENCE PACKET C\n{evidence_packet}\n\nTRANSCRIPT\n{render_transcript(run, rng)}\n\n"
            f"RUBRIC (score each dimension)\n{rubric}\n\nSCALE\n{SCALE}\n\n"
            f"Return JSON exactly of the form:\n{json.dumps(schema)}")


def parse_judgement(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if m is None:
        raise ValueError("judge response contains no JSON object")
    d = json.loads(m.group(0))
    out = {}
    for k in DIMENSIONS:
        s = int(d[k]["score"])
        if not 1 <= s <= 5:
            raise ValueError(f"{k} score out of range: {s}")
        evidence = d[k]["evidence"]
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError(f"{k} needs a supporting quote")
        out[k] = {"score": s, "evidence": evidence}
    return out


def parse_scores(text: str) -> dict:
    """Compatibility helper for numeric-only callers."""
    return {k: v["score"] for k, v in parse_judgement(text).items()}


# ------------------------------------------------------------------ backends
def mock_backend(system: str, user: str) -> str:
    """Deterministic fake judge for offline tests (hash-derived scores)."""
    h = hashlib.sha256(user.encode()).digest()
    return json.dumps({k: {"score": 1 + h[i] % 5, "evidence": "mock"} for i, k in enumerate(DIMENSIONS)})


def anthropic_backend(model: str | None = None, max_tokens: int = 600):
    """Real judge. Needs `pip install anthropic`, ANTHROPIC_API_KEY, and a model id (arg or JUDGE_MODEL).
    Prefer a model family different from the agents' (self-enhancement bias, proposal §6.3)."""
    import time
    import anthropic
    client = anthropic.Anthropic()
    model = model or os.environ["JUDGE_MODEL"]

    def call(system: str, user: str) -> str:
        for attempt in range(5):                     # exponential backoff, §5.5.1
            try:
                r = client.messages.create(model=model, max_tokens=max_tokens, temperature=0.0,
                                           system=system, messages=[{"role": "user", "content": user}])
                return r.content[0].text
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
    return call


# ------------------------------------------------------------------ runner
def judge_runs(runs, evidence_by_case: dict, backend, cache_path: str | None = None, n_mappings: int = 2) -> list:
    """Judge every run that has a debate transcript. The JSONL cache (keyed by prompt hash) is for
    crash recovery only, per the proposal's checkpointing note (§5.5.2)."""
    cache = {}
    if cache_path and os.path.exists(cache_path):
        with open(cache_path) as f:
            for line in f:
                d = json.loads(line)
                cache[d["key"]] = d["judgement"]
    out = []
    for run in runs:
        if run.transcript is None:
            continue
        if run.case_id not in evidence_by_case:
            raise ValueError(f"missing evidence packet for {run.case_id}")
        per = []
        for m in range(n_mappings):
            prompt = build_prompt(run, evidence_by_case[run.case_id], m)
            key = hashlib.sha256((SYSTEM + prompt).encode()).hexdigest()
            if key not in cache:
                cache[key] = parse_judgement(backend(SYSTEM, prompt))
                if cache_path:
                    with open(cache_path, "a") as f:
                        f.write(json.dumps({"key": key, "judgement": cache[key]}) + "\n")
            per.append(cache[key])
        out.append(dict(run_id=run.run_id, per_mapping=[{k: v["score"] for k, v in p.items()} for p in per],
                        evidence_by_mapping=[{k: v["evidence"] for k, v in p.items()} for p in per],
                        scores={k: sum(p[k]["score"] for p in per) / len(per) for k in DIMENSIONS},
                        n_chars=sum(len(t["text"]) for t in run.transcript)))
    return out


# ------------------------------------------------------------------ validation helpers
def _rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(x, y) -> float: # Spearman rank correlation: +1 means rankings agree perfectly, -1 is opposite, nan when corr cannot be calculated 
    rx, ry = _rank(x), _rank(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else float("nan")


def mapping_agreement(results: list) -> dict:
    """Self-consistency under speaker relabelling: Spearman between mapping 0 and 1, per dimension."""
    return {k: spearman([r["per_mapping"][0][k] for r in results], [r["per_mapping"][1][k] for r in results])
            for k in DIMENSIONS}


def length_bias(results: list) -> dict: # Checks whether longer transcripts tend to receive higher scores
    """Spearman(score, transcript length). Large |rho| suggests verbosity bias."""
    L = [r["n_chars"] for r in results]
    return {k: spearman([r["scores"][k] for r in results], L) for k in DIMENSIONS}


def stratified_sample(runs, cases, frac: float = 0.2, seed: int = 0) -> list:
    """~20% sample for manual review, stratified by architecture x tone x clean/flawed."""
    rng = random.Random(seed)
    strata = {}
    for r in runs:
        if r.transcript is not None:
            strata.setdefault((r.architecture, r.tone, cases[r.case_id].is_flawed), []).append(r)
    pick = []
    for _, rs in sorted(strata.items()):
        pick += rng.sample(rs, max(1, round(frac * len(rs))))
    return pick


def human_agreement(judge_results: list, human_scores: dict) -> dict:
    """human_scores: run_id -> {dim: int}. Spearman + mean abs diff per dimension on the overlap."""
    j = {r["run_id"]: r["scores"] for r in judge_results}
    ids = [i for i in human_scores if i in j]
    return {k: dict(n=len(ids), spearman=spearman([j[i][k] for i in ids], [human_scores[i][k] for i in ids]),
                    mean_abs_diff=sum(abs(j[i][k] - human_scores[i][k]) for i in ids) / len(ids))
            for k in DIMENSIONS}


def summarise_by(results: list, runs, cases, key_fn) -> dict:
    """Mean score per dimension grouped by key_fn(run, case), e.g. (architecture, tone, is_flawed)."""
    by = {r.run_id: r for r in runs}
    groups = {}
    for res in results:
        run = by[res["run_id"]]
        groups.setdefault(key_fn(run, cases[run.case_id]), []).append(res["scores"])
    return {g: {k: sum(s[k] for s in ss) / len(ss) for k in DIMENSIONS} | {"n": len(ss)} for g, ss in groups.items()}


if __name__ == "__main__":
    # Offline smoke test on dummy data using the mock judge.
    from dummy_data import make_cases, make_runs
    cs = make_cases()
    all_runs, _ = make_runs(cs)
    rs = [r for r in all_runs if r.architecture in ("debate", "hybrid")]
    print(len(rs), "debate/hybrid dummy runs (the proposal's full design has 256 unique)")
    res = judge_runs(rs, {c: "[EP_0001_E01] Synthetic evidence." for c in cs}, mock_backend)
    print({k: round(v, 2) for k, v in mapping_agreement(res).items()})
    for g, m in sorted(summarise_by(res, rs, cs, lambda r, c: (r.architecture, r.tone)).items()):
        print(g, {k: round(v, 2) for k, v in m.items()})
