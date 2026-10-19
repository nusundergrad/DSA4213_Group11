from difflib import SequenceMatcher
from itertools import combinations

def unit_to_num(unit):
    if "million" in unit:
        return 1000000
    elif "billion" in unit:
        return 1000000000

def get_pct_change(earlier, later):
    return ((later - earlier) / earlier) * 100

def check_numeric_match(num, fact):
    metric_match = num.metric == fact.metric
    period_match = num.period == fact.period
    val_match = float(num.value)*unit_to_num(num.unit) == float(fact.value)*unit_to_num(fact.unit)
    return all((metric_match, period_match, val_match))

def check_pc_match(num, from_fact, to_fact):
    metric_match = num.metric == from_fact.metric == to_fact.metric
    periods_match = (num.from_period == from_fact.period) and (num.to_period == to_fact.period)
    true_pc = round(get_pct_change(float(from_fact.value), float(to_fact.value)), 2)
    pc_match = float(num.value) == true_pc
    return all((metric_match, periods_match, pc_match))


# def verifier_with_text(report, packet):
#     """
#     Function to check Analyst agent's textual and numerical claims against the original evidence packet.
#     Returns a dictionary with each key being a claim_id and the corresponding values being a boolean representing whether the claim is true.
#     """
#     threshold = 0.8
#     out = {}
#     packet_evidence = {e.evidence_id: e.text for e in packet.evidence}
#     packet_facts = {f.fact_id: f for f in packet.facts}
    
#     for claim in report.claims:
#         # check text of claim
#         evidence = ""
#         for evidence_id in claim.evidence_ids:
#             evidence += packet_evidence[evidence_id]
#         sm = SequenceMatcher(lambda x: x in ["\n", "\t"], claim.text, evidence) #can change to different similarity metric if needed
#         match = sm.find_longest_match()
#         sim = match.size / len(claim.text)
#         print(sim) #debugging

#         # check numerical calculations
#         num = claim.check_spec
#         if num is None:
#             num_check = True
#         else:
#             if num.kind == "numeric":
#                 num_check = check_numeric_match(num, packet_facts[num.fact_id])

#             elif num.kind == "percentage_change":
#                 from_fact = packet_facts[num.from_fact_id]
#                 to_fact = packet_facts[num.to_fact_id]
#                 num_check = check_pc_match(num, from_fact, to_fact)

#         #out[claim.claim_id] = (sim >= threshold) and num_check
#         out[claim.claim_id] = f"text check: {(sim >= threshold)}, numerical check: {num_check}"

#     return out

def verifier(report, packet):
    """
    Function to check Analyst agent's numerical claims against the original evidence packet.
    Returns a dictionary with each key being a claim_id and the corresponding values being a boolean representing whether the claim is true.
    """
    out = {}
    packet_facts = {f.fact_id: f for f in packet.facts}
    
    for claim in report.claims:
        # check numerical calculations
        num = claim.check_spec
        
        if num.kind == "numeric":
            num_check = check_numeric_match(num, packet_facts[num.fact_id])

        elif num.kind == "percentage_change":
            from_fact = packet_facts[num.from_fact_id]
            to_fact = packet_facts[num.to_fact_id]
            num_check = check_pc_match(num, from_fact, to_fact)

        out[claim.claim_id] = num_check

    return out