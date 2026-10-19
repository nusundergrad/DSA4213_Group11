from difflib import SequenceMatcher
from itertools import combinations

def unit_to_num(unit):
    if "million" in unit:
        return 1000000
    elif "billion" in unit:
        return 1000000000

def compare_periods(fact1, fact2):
    period1 = fact1["period"]
    period2 = fact2["period"]
    # assume period["label"] is in the format "FY202X"
    y1 = int(period1["label"][-4:])
    y2 = int(period2["label"][-4:])
    if y1 > y2:
        return {"earlier": fact2, "later": fact1}
    else:
        return {"earlier": fact1, "later": fact2}

def get_pct_change(earlier, later):
    return ((later - earlier) / earlier) * 100

def check_numeric_match(num, fact):
    metric_match = num["metric"] == fact["metric"]
    period_match = num["period"] == fact["period"]
    val_match = float(num["value"])*unit_to_num(num["unit"]) == float(fact["value"])*unit_to_num(fact["unit"])
    return all((metric_match, period_match, val_match))

def check_pc_match(num, fact1, fact2):
    metric_match = num["metric"] == fact1["metric"] == fact2["metric"]
    periods_match = ((num["from_period"] == fact1["period"]) and (num["to_period"] == fact2["period"])) or ((num["from_period"] == fact2["period"]) and (num["to_period"] == fact1["period"]))
    # assume period["label"] is in the format "FY202X"
    compared = compare_periods(fact1, fact2)
    earlier_val = float(compared["earlier"]["value"])
    later_val = float(compared["later"]["value"])
    true_pc = round(get_pct_change(earlier_val, later_val), 2)
    pc_match = float(num["value"]) == true_pc
    return all(metric_match, periods_match, pc_match)


def verifier(report, packet):
    """
    Function to check Analyst agent's textual and numerical claims against the original evidence packet.
    Returns a dictionary with each key being a claim_id and the corresponding values being a boolean representing whether the claim is true.
    """
    threshold = 0.8
    out = {}
    packet_evidence = {e["evidence_id"]: e["text"] for e in packet["evidence"]}
    packet_facts = {f["fact_id"]: f for f in packet["facts"]}
    
    for claim in report["claims"]:
        # check text of claim
        evidence = ""
        for evidence_id in claim["evidence_ids"]:
            evidence += packet_evidence[evidence_id]
        sim = SequenceMatcher(lambda x: x in ["\n", "\t"], claim["text"], evidence) #can change to different similarity metric if needed

        # check numerical calculations
        num = claim["check_spec"]
        num_check = False
        
        if num["kind"] == "numeric":
            for fact_id in claim["fact_ids"]: #assuming fact_ids has been added to the schema
                if check_numeric_match(num, packet_facts[fact_id]):
                    num_check = True
                    break

        elif num["kind"] == "percentage_change":
            all_facts = [packet_facts[fact_id] for fact_id in claim["fact_ids"]]
            all_pairs = list(combinations(all_facts, 2))
            for fact1, fact2 in all_pairs:
                if check_pc_match(num, fact1, fact2):
                    num_check = True
                    break

        out[claim["claim_id"]] = (sim >= threshold) and num_check

    return out

def verifier_no_text(report, packet):
    """
    Function to check Analyst agent's numerical claims against the original evidence packet.
    Returns a dictionary with each key being a claim_id and the corresponding values being a boolean representing whether the claim is true.
    """
    out = {}
    packet_facts = {f["fact_id"]: f for f in packet["facts"]}
    
    for claim in report["claims"]:
        # check numerical calculations
        num = claim["check_spec"]
        num_check = False
        
        if num["kind"] == "numeric":
            for fact_id in claim["fact_ids"]: #assuming fact_ids has been added to the schema
                if check_numeric_match(num, packet_facts[fact_id]):
                    num_check = True
                    break

        elif num["kind"] == "percentage_change":
            all_facts = [packet_facts[fact_id] for fact_id in claim["fact_ids"]]
            all_pairs = list(combinations(all_facts, 2))
            for fact1, fact2 in all_pairs:
                if check_pc_match(num, fact1, fact2):
                    num_check = True
                    break

        out[claim["claim_id"]] = num_check

    return out