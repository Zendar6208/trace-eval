"""Pydantic v2 data contract for trace.labels/1.0.

Methodology requirements:
- Human labels describe a specific output and are keyed to the submission's content hash.
- Stored separately from the dataset.
- Each label entry carries 'sentence_text' to detect segmentation changes.
- Labels support grounding verdicts (supported, unsupported, contradicted, not_assessable)
  and citation unit support flags.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CitationUnitLabel(BaseModel):
    """Human annotation for a single (sentence, passage_id) citation unit."""

    model_config = ConfigDict(extra="forbid")

    passage_id: str = Field(..., min_length=1, description="Cited passage identifier")
    supports: bool = Field(
        ...,
        description="Whether the cited passage text genuinely supports the sentence claim",
    )
    notes: str | None = Field(default=None, description="Optional annotation note")


class SentenceLabel(BaseModel):
    """Ground truth annotation for an individual sentence in an evaluated answer."""

    model_config = ConfigDict(extra="forbid")

    sentence_index: int = Field(
        ..., ge=0, description="0-based sentence index in the segmented answer"
    )
    sentence_text: str = Field(
        ...,
        min_length=1,
        description="Verbatim sentence text used to verify segmentation alignment",
    )
    is_claim: bool = Field(
        default=True,
        description="Whether this sentence constitutes a factual claim (vs. pleasantry or refusal)",
    )
    grounding_label: (
        Literal["supported", "unsupported", "contradicted", "not_assessable"] | None
    ) = Field(
        default=None,
        description="Grounding verdict relative to all retrieved passages",
    )
    citation_labels: list[CitationUnitLabel] = Field(
        default_factory=list,
        description="Evaluated citation units attached to this sentence",
    )
    notes: str | None = Field(default=None, description="Optional sentence-level annotator notes")


class ItemLabels(BaseModel):
    """Human annotations for a specific benchmark item output."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(..., min_length=1, description="Referenced benchmark item identifier")
    annotator_id: str | None = Field(default=None, description="Identifier of the human annotator")
    correctness_verdict: Literal["correct", "partial", "incorrect"] | None = Field(
        default=None,
        description="Human gold correctness verdict against reference facts and question intent",
    )
    sentences: list[SentenceLabel] = Field(
        default_factory=list,
        description="Annotated sentences for grounding and citation verification",
    )
    notes: str | None = Field(default=None, description="Optional item-level notes")

    @model_validator(mode="after")
    def validate_sentence_indices(self) -> ItemLabels:
        seen_indices: set[int] = set()
        for s in self.sentences:
            if s.sentence_index in seen_indices:
                raise ValueError(
                    f"Duplicate sentence_index {s.sentence_index} in item '{self.item_id}'"
                )
            seen_indices.add(s.sentence_index)
        return self


class LabelsDocument(BaseModel):
    """Labels document data contract (trace.labels/1.0)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["trace.labels/1.0"] = Field(
        default="trace.labels/1.0",
        description="Schema version identifier",
    )
    dataset_id: str = Field(..., min_length=1, description="Target dataset identifier")
    submission_content_sha256: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="Content SHA-256 of the exact submission being annotated",
    )
    annotator_notes: str | None = Field(
        default=None,
        description="General notes by annotators (excluded from content hash)",
    )
    items: list[ItemLabels] = Field(
        ...,
        min_length=1,
        description="Annotated items for human-evaluator agreement assessment",
    )

    @model_validator(mode="before")
    @classmethod
    def check_schema_version(cls, data: Any) -> Any:
        if isinstance(data, dict):
            version = data.get("schema_version", "trace.labels/1.0")
            if version != "trace.labels/1.0":
                raise ValueError(
                    f"Unsupported schema version '{version}'. Expected 'trace.labels/1.0'."
                )
        return data

    @model_validator(mode="after")
    def validate_unique_items(self) -> LabelsDocument:
        seen: set[str] = set()
        for item in self.items:
            if item.item_id in seen:
                raise ValueError(f"Duplicate item_id '{item.item_id}' in labels items")
            seen.add(item.item_id)
        return self
