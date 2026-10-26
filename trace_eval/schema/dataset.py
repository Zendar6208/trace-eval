"""Pydantic v2 data contract for trace.dataset/1.0.

Methodology requirements:
- Unique passage IDs within corpus.
- Unique item IDs across dataset items.
- Explicit group_id and split (dev, test) for cluster bootstrap evaluation.
- Required facts with optional aliases and numeric flagging.
- Schema version validation with informative errors.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PASSAGE_ID_REGEX = re.compile(r"^[A-Za-z0-9_.:-]+$")


class Passage(BaseModel):
    """A corpus passage available for retrieval and citation support."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Unique passage identifier, matching [A-Za-z0-9_.:-]+")
    text: str = Field(..., min_length=1, description="Passage body text")
    title: str | None = Field(default=None, description="Optional title or section header")
    metadata: dict[str, Any] | None = Field(default=None, description="Arbitrary passage metadata")

    @field_validator("id")
    @classmethod
    def validate_passage_id(cls, v: str) -> str:
        if not PASSAGE_ID_REGEX.match(v):
            raise ValueError(f"Passage ID '{v}' does not match required format [A-Za-z0-9_.:-]+")
        return v


class RequiredFact(BaseModel):
    """A atomic fact required in a correct response, matched by normalized text, aliases, or NLI."""

    model_config = ConfigDict(extra="forbid")

    fact_id: str = Field(..., description="Unique identifier for the fact within the item")
    text: str = Field(..., min_length=1, description="Primary surface form of the required fact")
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative surface forms or synonyms of the fact",
    )
    is_numeric: bool = Field(
        default=False,
        description="Whether this fact contains numeric/date values subject to the numeric guard",
    )


class DatasetItem(BaseModel):
    """A single evaluation benchmark item."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Unique benchmark item identifier")
    group_id: str = Field(
        ...,
        description="Case grouping identifier shared by item variants for cluster bootstrapping",
    )
    split: Literal["dev", "test"] = Field(
        ...,
        description="Data partition: dev (for calibration) or test (for frozen evaluation)",
    )
    question: str = Field(..., min_length=1, description="Query or prompt posed to the RAG system")
    unanswerable: bool = Field(
        default=False,
        description="True if the question cannot be answered from the corpus and requires a refusal",
    )
    gold_passage_ids: list[str] = Field(
        default_factory=list,
        description="IDs of corpus passages that ground the correct answer",
    )
    reference_answers: list[str] = Field(
        default_factory=list,
        description="One or more gold reference answers against which correctness is measured",
    )
    required_facts: list[RequiredFact] = Field(
        default_factory=list,
        description="Atomic required facts that must be recalled",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional domain, category, or difficulty tags",
    )

    @field_validator("required_facts")
    @classmethod
    def validate_unique_fact_ids(cls, v: list[RequiredFact]) -> list[RequiredFact]:
        fact_ids: set[str] = set()
        for fact in v:
            if fact.fact_id in fact_ids:
                raise ValueError(f"Duplicate fact_id '{fact.fact_id}' in item required_facts")
            fact_ids.add(fact.fact_id)
        return v


class Dataset(BaseModel):
    """Benchmark dataset contract (trace.dataset/1.0)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["trace.dataset/1.0"] = Field(
        default="trace.dataset/1.0",
        description="Schema version identifier",
    )
    dataset_id: str = Field(..., min_length=1, description="Unique identifier of the dataset")
    name: str = Field(..., min_length=1, description="Human-readable name of the dataset")
    description: str | None = Field(default=None, description="Dataset description and scope")
    language: str = Field(default="en", description="Language code (e.g. 'en')")
    license: str | None = Field(default=None, description="Dataset license identifier")
    corpus: list[Passage] = Field(
        default_factory=list,
        description="Corpus of documents/passages for retrieval and citation checking",
    )
    items: list[DatasetItem] = Field(
        ...,
        min_length=1,
        description="List of benchmark query items",
    )

    @model_validator(mode="before")
    @classmethod
    def check_schema_version(cls, data: Any) -> Any:
        if isinstance(data, dict):
            version = data.get("schema_version", "trace.dataset/1.0")
            if version != "trace.dataset/1.0":
                raise ValueError(
                    f"Unsupported schema version '{version}'. Expected 'trace.dataset/1.0'."
                )
        return data

    @model_validator(mode="after")
    def validate_integrity(self) -> Dataset:
        # Check passage ID uniqueness
        passage_ids: set[str] = set()
        for p in self.corpus:
            if p.id in passage_ids:
                raise ValueError(f"Duplicate passage ID '{p.id}' found in corpus")
            passage_ids.add(p.id)

        # Check item ID uniqueness and gold passage validity
        item_ids: set[str] = set()
        for item in self.items:
            if item.id in item_ids:
                raise ValueError(f"Duplicate item ID '{item.id}' found in dataset items")
            item_ids.add(item.id)

            for gold_id in item.gold_passage_ids:
                if gold_id not in passage_ids:
                    raise ValueError(
                        f"Item '{item.id}' references gold passage ID '{gold_id}' not found in corpus"
                    )

        return self
