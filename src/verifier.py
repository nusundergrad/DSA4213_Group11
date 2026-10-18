from decimal import Decimal

def unit_to_num(unit):
    if "million" in unit:
        return 1000000
    elif "billion" in unit:
        return 1000000000

def compare_periods(fact1, fact2):
    period1 = fact1.period
    period2 = fact2.period
    # assume period.label is in the format "FY202X"
    y1 = int(period1.label[-4:])
    y2 = int(period2.label[-4:])
    if y1 > y2:
        return {"earlier": fact2, "later": fact1}
    else:
        return {"earlier": fact1, "later": fact2}

def get_pct_change(earlier, later):
    return ((later - earlier) / earlier) * 100

def check_numeric_match(num, fact):
    metric_match = num.metric == fact.metric
    period_match = num.period == fact.period
    val_match = float(num.value)*unit_to_num(num.unit) == float(fact.value)*unit_to_num(fact.unit)
    return all((metric_match, period_match, val_match))

def check_pc_match(num, fact1, fact2):
    metric_match = num.metric == fact1.metric == fact2.metric
    periods_match = ((num.from_period == fact1.period) and (num.to_period == fact2.period)) or ((num.from_period == fact2.period) and (num.to_period == fact1.period))
    # assume period.label is in the format "FY202X"
    compared = compare_periods(fact1, fact2)
    earlier_val = float(compared["earlier"].value)
    later_val = float(compared["later"].value)
    true_pc = round(get_pct_change(earlier_val, later_val), 2)
    pc_match = float(num.value) == true_pc
    return all((metric_match, periods_match, pc_match))


def verifier(report, packet):
    """
    Function to check Analyst agent's textual and numerical claims against the original evidence packet.
    Returns a dictionary with each key being a claim_id and the corresponding values being a boolean representing whether the claim is true.
    """
    out = {}
    packet_facts = {f.fact_id: f for f in packet.facts}

    for claim in report.claims:
        num = claim.check_spec
        citations_valid = all(
            evidence_id in {e.evidence_id for e in packet.evidence}
            for evidence_id in claim.evidence_ids
        )

        if not citations_valid:
            out[claim.claim_id] = False
        elif num is None:
            out[claim.claim_id] = True
        elif num.kind == "numeric":
            fact = packet_facts.get(num.fact_id)
            out[claim.claim_id] = fact is not None and check_numeric_match(num, fact)
        else:
            first = packet_facts.get(num.from_fact_id)
            second = packet_facts.get(num.to_fact_id)
            out[claim.claim_id] = (
                first is not None and second is not None
                and check_pc_match(num, first, second)
            )

    return out
