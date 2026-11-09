"""Strict API and tool inputs. Money crosses the boundary only as BDT strings."""

import re
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

Kind = Literal["invoice", "payment", "expense", "advance", "cash_return", "delivery", "statement"]
FINANCIAL_KINDS = {"invoice", "payment", "expense", "advance", "cash_return"}
MONEY_LIMIT = 9223372036854775807


def money_string(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,17}(?:\.[0-9]{1,2})?", value):
        raise ValueError("amount_bdt must be a nonnegative decimal string with at most two decimal places")
    amount = int(Decimal(value) * 100)
    if amount > MONEY_LIMIT:
        raise ValueError("amount_bdt is too large")
    return f"{amount // 100}.{amount % 100:02d}"


Money = Annotated[str, BeforeValidator(money_string)]
ShortText = Annotated[str, Field(min_length=1, max_length=200)]
LongText = Annotated[str, Field(min_length=1, max_length=12000)]
Id = Annotated[int, Field(gt=0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @field_validator("*", mode="before")
    @classmethod
    def trim_strings(cls, value, info):
        if info.field_name == "transaction_id":
            return value
        return value.strip() if isinstance(value, str) else value


class TripCreate(StrictModel):
    code: ShortText | None = None
    customer: ShortText
    driver: ShortText
    truck: ShortText
    origin: str = Field(default="", max_length=200)
    destination: str = Field(default="", max_length=200)

    @field_validator("code", mode="before")
    @classmethod
    def optional_code(cls, value):
        return None if isinstance(value, str) and not value.strip() else value


class ReviewFields(StrictModel):
    kind: Kind
    amount_bdt: Money | None = None
    transaction_id: str | None = Field(default=None, max_length=200)
    trip_ref: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=12000)
    text: str | None = Field(default=None, max_length=12000)
    delivered: bool | None = None

    @field_validator("transaction_id", "trip_ref")
    @classmethod
    def empty_to_none(cls, value):
        return value if value and value.strip() else None


class EvidenceCreate(ReviewFields):
    title: ShortText


class Extraction(ReviewFields):
    title: ShortText | None = None
    confidence: dict[str, float | None] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def valid_confidence(cls, value):
        allowed = set(ReviewFields.model_fields) | {"title"}
        if any(key not in allowed or (score is not None and not 0 <= score <= 1) for key, score in value.items()):
            raise ValueError("invalid field confidence")
        # Providers may report null for an inapplicable field. Omit that hint;
        # never invent a zero/one confidence or reject otherwise valid amounts.
        return {key: score for key, score in value.items() if score is not None}


class EvidenceReview(StrictModel):
    decision: Literal["confirm", "exclude"]
    fields: ReviewFields | None = None


class Reply(StrictModel):
    text: LongText


class ActionDecision(StrictModel):
    decision: Literal["approve", "reject"]


class CloseDecision(StrictModel):
    decision: Literal["approve_settlement"]


class TripTool(StrictModel):
    trip_id: Id


class InspectTool(StrictModel):
    evidence_id: Id


class CompareTool(StrictModel):
    evidence_ids: list[Id] = Field(min_length=1, max_length=100)


class QuestionTool(StrictModel):
    question: LongText
    recipient: ShortText
    evidence_ids: list[Id] = Field(max_length=100)


class FollowupTool(StrictModel):
    recipient: ShortText
    message: LongText
    evidence_ids: list[Id] = Field(min_length=1, max_length=100)


class FinishTool(StrictModel):
    summary: LongText
    evidence_ids: list[Id] = Field(max_length=100)
