"""Apply the exact edits in private/pairs.json; no model calls or random IDs."""
import argparse
import copy
from pathlib import Path
import re

from .prepare import ROOT, assert_masked, load_agent_input, read, save
from .schemas import Report


def make_report(clean, pair):
    if clean["report_id"] != pair["clean_report_id"]:
        raise ValueError("Wrong clean report for this pair")
    if pair["flawed_report_id"] == pair["clean_report_id"]:
        raise ValueError("Flawed report needs a separate ID")
    result = copy.deepcopy(clean)
    claim_index = next(i for i, c in enumerate(clean["claims"])
                       if c["claim_id"] == pair["target_claim_id"])
    seen = set()
    for change in pair["changes"]:
        path = change["path"]
        if (path != ["rationale"] and
                not (len(path) >= 3 and path[:2] == ["claims", claim_index]
                     and path[2] in {"text", "check_spec"})):
            raise ValueError("Only the target claim and its rationale may change")
        if tuple(path) in seen:
            raise ValueError("Duplicate change path")
        seen.add(tuple(path))
        parent = result
        for key in path[:-1]:
            parent = parent[key]
        if parent[path[-1]] != change["before"]:
            raise ValueError(f"Original differs at {path}; review the pair again")
        parent[path[-1]] = copy.deepcopy(change["after"])
    if result["claims"][claim_index] == clean["claims"][claim_index]:
        raise ValueError("Target claim must change")
    result["report_id"] = pair["flawed_report_id"]
    return Report.model_validate(result).model_dump(mode="json")


def create_flawed_reports(root=ROOT):
    root = Path(root)
    pairs = read(root / "private/pairs.json")["pairs"]
    aliases = read(root / "private/aliases.json")
    ids = [p["flawed_report_id"] for p in pairs]
    if len(ids) != len(set(ids)) or set(ids) & {p["clean_report_id"] for p in pairs}:
        raise ValueError("Flawed report IDs must be unique and separate from clean reports")
    pending = []
    for pair in pairs:
        # Check the paths before reading or writing reports.
        if not (re.fullmatch(r"EP_\d+", pair["packet_id"])
                and re.fullmatch(r"R_[a-zA-Z0-9]+", pair["clean_report_id"])
                and re.fullmatch(r"R_[a-zA-Z0-9]+", pair["flawed_report_id"])):
            raise ValueError("Invalid packet or report ID")
        if (type(pair["error_index"]) is not int or pair["error_index"] < 1
                or not re.fullmatch(r"[a-z_]+", pair["defect_type"])):
            raise ValueError("Invalid error index or type")
        report_folder = f"reports/{pair['packet_id']}"
        if (pair["clean_report_path"] != f"{report_folder}/clean.json"
                or pair["flawed_report_path"] !=
                f"{report_folder}/error_{pair['error_index']:02d}_{pair['defect_type']}.json"):
            raise ValueError("Pair paths must match the packet, error index and type")
        payload = load_agent_input(root / "public/evidence_packets" / (pair["packet_id"] + ".json"),
                                   root / "public" / pair["clean_report_path"])
        result = make_report(payload["initial_report"], pair)
        assert_masked(result, aliases)
        path = root / "public" / pair["flawed_report_path"]
        if any(path == previous for previous, _ in pending):
            raise ValueError("Each flawed report needs a unique path")
        if path.exists() and read(path) != result:
            raise ValueError(f"Existing report differs: {path}; use a new index and ID for a revised copy")
        pending.append((path, result))
    for path, result in pending:
        save(path, result)
    return [path for path, _ in pending]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    for path in create_flawed_reports(parser.parse_args().root):
        print(path)
