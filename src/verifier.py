from decimal import Decimal
# from difflib import SequenceMatcher
# from itertools import combinations

def unit_to_num(unit):
    """Scale factor of a unit label; units with no scale word (percent, USD_per_share) are 1."""
    unit = (unit or "").lower()
    if "billion" in unit:
        return 1000000000
    if "million" in unit:
        return 1000000
    if "thousand" in unit:
        return 1000
    return 1

def get_pct_change(earlier, later):
    return ((later - earlier) / earlier) * 100

def check_numeric_match(num, fact):
    metric_match = num.metric == fact.metric
    period_match = num.period == fact.period
    unit_match = unit_dimension(num.unit) == unit_dimension(fact.unit)
    val_match = Decimal(num.value)*unit_to_num(num.unit) == Decimal(fact.value)*unit_to_num(fact.unit)
    return all((metric_match, period_match, unit_match, val_match))


def unit_dimension(unit):
    return unit.lower().removesuffix('_billion').removesuffix('_million').removesuffix('_thousand')

def check_pc_match(num, from_fact, to_fact):
    metric_match = num.metric == from_fact.metric == to_fact.metric
    periods_match = (num.from_period == from_fact.period) and (num.to_period == to_fact.period)
    if unit_dimension(from_fact.unit) != unit_dimension(to_fact.unit):
        return None
    earlier = Decimal(from_fact.value) * unit_to_num(from_fact.unit)
    later = Decimal(to_fact.value) * unit_to_num(to_fact.unit)
    if earlier == 0:
        return None
    true_pc = get_pct_change(earlier, later)
    pc_match = abs(Decimal(num.value) - true_pc) <= Decimal('0.01')
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
    True/False checks only the structured assertion; None means not checkable.
    A passing number does not certify the prose or reasoning.
    """
    out = {}
    packet_facts = {f.fact_id: f for f in packet.facts}
    
    for claim in report.claims:
        # check numerical calculations
        num = claim.check_spec
        if num is None:
            num_check = None
        else:
            if num.kind == "numeric":
                fact = packet_facts.get(num.fact_id)
                num_check = check_numeric_match(num, fact) if fact else None
                if fact and fact.evidence_id not in claim.evidence_ids:
                    num_check = False

            elif num.kind == "percentage_change":
                from_fact = packet_facts.get(num.from_fact_id)
                to_fact = packet_facts.get(num.to_fact_id)
                num_check = check_pc_match(num, from_fact, to_fact) if from_fact and to_fact else None
                if from_fact and to_fact and any(f.evidence_id not in claim.evidence_ids for f in (from_fact, to_fact)):
                    num_check = False

        out[claim.claim_id] = num_check

    return out
