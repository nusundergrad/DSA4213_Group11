"""Evaluation records for DSA4213_Group11/docs/shared-data-contract.md (v0.1).

Public agent inputs, private answer keys, execution observations, and scored results
are deliberately separate. The wider run/scoring contract is proposed in the repo;
its benchmark Packet/Report models are already implemented there.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

SCHEMA_VERSION = "0.1"
ARCHITECTURES = ("baseline", "debate", "verification", "hybrid")
TONES = ("underconfident", "neutral", "overconfident")
# Names follow data/benchmark/private/pairs.json.
OBJECTIVE_DEFECTS = ("wrong_number", "arithmetic", "reporting_period",
                     "citation_misattribution", "direct_factual_contradiction")
REASONING_DEFECTS = ("material_omission", "unsupported_inference")
DEFECT_TYPES = OBJECTIVE_DEFECTS + REASONING_DEFECTS


@dataclass
class Case:
    """Private answer key. Never include this object in model input or graph state."""
    case_id: str
    pair_id: str
    content_label: str                 # unmodified | injected_error
    confidence_subset: bool
    defect: dict | None = None         # target_claim_id, defect_type, frozen criteria
    schema_version: str = SCHEMA_VERSION

    @property
    def is_flawed(self) -> bool:
        return self.content_label == "injected_error"


@dataclass
class RunRecord:
    """One execution observation; contains no private benchmark labels."""
    run_id: str
    case_id: str
    architecture: str
    tone: str
    initial_report: dict
    final_report: dict
    trader: dict                       # assessment, support_score (0..100), investment_action
    verifier: dict | None = None       # claim_checks and claim_statuses
    risk_manager_turns: list | None = None
    analyst_revision_turns: list | None = None
    transcript: list | None = None     # full role-labelled messages for the judge
    usage: dict = field(default_factory=dict)
    status: str = "completed"
    schema_version: str = SCHEMA_VERSION
    dataset_version: str | None = None
    input_sha256: str | None = None
    config_sha256: str | None = None
    attempt: int = 1
    started_at: str | None = None
    finished_at: str | None = None
    error: dict | None = None
    config: dict = field(default_factory=dict)
    transcript_path: str | None = None


@dataclass
class ScoredResult:
    """Evaluation-only adjudication, joined to a run through run_id."""
    run_id: str
    case_id: str
    scoring_status: str                # complete | pending | not_applicable
    ground_truth: dict                 # private content_label, pair_id, target, category
    verifier_detected: bool | None = None
    risk_manager_detected: bool | None = None
    detected: bool | None = None
    corrected_after_detection: bool | None = None
    defect_resolved: bool | None = None
    materially_used_by_trader: bool | None = None
    false_acceptance: bool | None = None
    scoring_provenance: dict = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
    new_error_present: bool | None = None
    new_error_explanation: str = ""
    new_error_evidence_ids: list[str] = field(default_factory=list)


def write_jsonl(path, items) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            value = asdict(item) if hasattr(item, "__dataclass_fields__") else item
            f.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_cases(path) -> dict[str, Case]:
    return {row["case_id"]: Case(**row) for row in read_jsonl(path)}


def load_runs(path) -> list[RunRecord]:
    return [RunRecord(**row) for row in read_jsonl(path)]


def load_scores(path) -> list[ScoredResult]:
    return [ScoredResult(**row) for row in read_jsonl(path)]
