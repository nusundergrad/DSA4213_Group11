"""Small shared types for masked benchmark inputs, independent of the agent graph."""
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, strict=True)]
Number = Annotated[str, Field(pattern=r"^-?\d+(\.\d+)?$", strict=True)]
FactID = Annotated[str, Field(pattern=r"^EP_\d+_F\d+$", strict=True)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Period(Record):
    label: Text
    start: date
    end: date

    @model_validator(mode="after")
    def ordered(self):
        if self.start > self.end:
            raise ValueError("Period start must not follow end")
        return self


class Evidence(Record):
    evidence_id: Annotated[str, Field(pattern=r"^EP_\d+_E\d+$")]
    section: Literal["Item 1A", "Item 7"]
    text: Text


class Fact(Record):
    fact_id: Annotated[str, Field(pattern=r"^EP_\d+_F\d+$")]
    evidence_id: Text
    metric: Text
    period: Period
    value: Number
    unit: Text


class Packet(Record):
    schema_version: Literal["0.1"] = "0.1"
    packet_id: Annotated[str, Field(pattern=r"^EP_\d+$")]
    company_alias: Annotated[str, Field(pattern=r"^COMPANY_\d+$")]
    fiscal_year: Annotated[int, Field(ge=1900, le=2100, strict=True)]
    evidence: Annotated[list[Evidence], Field(min_length=1)]
    facts: list[Fact]

    @model_validator(mode="after")
    def references(self):
        ids = [e.evidence_id for e in self.evidence]
        fact_ids = [f.fact_id for f in self.facts]
        if len(ids) != len(set(ids)) or len(fact_ids) != len(set(fact_ids)):
            raise ValueError("Duplicate evidence or fact IDs")
        if any(not x.startswith(self.packet_id + "_") for x in ids + fact_ids):
            raise ValueError("Evidence and fact IDs must belong to the packet")
        if any(f.evidence_id not in ids for f in self.facts):
            raise ValueError("Fact references missing evidence")
        return self


class Numeric(Record):
    kind: Literal["numeric"]
    fact_id: FactID | None = None
    metric: Text
    period: Period
    value: Number
    unit: Text


class PercentageChange(Record):
    kind: Literal["percentage_change"]
    from_fact_id: FactID | None = None
    to_fact_id: FactID | None = None
    metric: Text
    from_period: Period
    to_period: Period
    value: Number
    unit: Literal["percent"]

    @model_validator(mode="after")
    def complete_fact_references(self):
        if (self.from_fact_id is None) != (self.to_fact_id is None):
            raise ValueError("Supply both from_fact_id and to_fact_id, or neither for a legacy report")
        return self


class Claim(Record):
    claim_id: Annotated[str, Field(pattern=r"^C\d+$")]
    text: Text
    evidence_ids: list[Text]
    check_spec: Annotated[Numeric | PercentageChange, Field(discriminator="kind")] | None


class Report(Record):
    schema_version: Literal["0.1"] = "0.1"
    report_id: Annotated[str, Field(pattern=r"^R_[a-zA-Z0-9]+$")]
    recommendation: Literal["BUY", "SELL", "HOLD"]
    claims: Annotated[list[Claim], Field(min_length=3, max_length=5)]
    rationale: Text

    @model_validator(mode="after")
    def unique_claims(self):
        ids = [c.claim_id for c in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate claim IDs")
        return self
