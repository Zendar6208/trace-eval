"""Pydantic v2 data contract for trace.submission/1.0.

Methodology requirements:
- Explicit provenance classes: 'synthetic_fixture' and 'recorded_system'.
- 'synthetic_fixture' strictly requires 'fixture_note'.
- 'recorded_system' requires 'system.provenance'.
- Outputs are ordered and include retrieved passage lists with order and IDs.
- Unique item IDs across submission outputs.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RetrievedPassage(BaseModel):
    """A passage retrieved by the RAG pipeline in rank order."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, description="Corpus passage identifier")
    text: str | None = Field(default=None, description="Optional passage text snippet if recorded")
    score: float | None = Field(default=None, description="Retrieval score or similarity metric")
    metadata: dict[str, Any] | None = Field(default=None, description="Pipeline-specific metadata")


class SystemProvenance(BaseModel):
    """Detailed pipeline execution provenance for recorded system outputs."""

    model_config = ConfigDict(extra="forbid")

    pipeline_description: str = Field(
        ..., min_length=1, description="Description of the RAG pipeline"
    )
    model_name: str | None = Field(default=None, description="Generator model identifier")
    retriever_name: str | None = Field(
        default=None, description="Retriever / search engine identifier"
    )
    run_timestamp: str | None = Field(default=None, description="ISO 8601 execution timestamp")
    parameters: dict[str, Any] | None = Field(
        default=None, description="Pipeline generation parameters"
    )


class SystemMetadata(BaseModel):
    """Identification and provenance metadata for the evaluated system."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="System or pipeline name")
    version: str | None = Field(default=None, description="System version or commit hash")
    provenance: SystemProvenance | None = Field(
        default=None,
        description="Execution provenance (mandatory if outputs contain recorded_system items)",
    )


class SubmissionOutput(BaseModel):
    """The generated response and retrieval result for a single benchmark item."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(..., min_length=1, description="Referenced benchmark item ID")
    origin: Literal["recorded_system", "synthetic_fixture"] = Field(
        ...,
        description="Provenance class: 'recorded_system' or 'synthetic_fixture'",
    )
    fixture_note: str | None = Field(
        default=None,
        description="Mandatory explanation of the failure mode exhibited by a synthetic fixture",
    )
    answer: str = Field(..., description="Generated answer text (may include citation markers)")
    retrieved: list[RetrievedPassage] = Field(
        default_factory=list,
        description="Ordered list of passages retrieved for this query",
    )
    metadata: dict[str, Any] | None = Field(default=None, description="Item-level output metadata")

    @model_validator(mode="after")
    def validate_origin_constraints(self) -> SubmissionOutput:
        if self.origin == "synthetic_fixture":
            if not self.fixture_note or not self.fixture_note.strip():
                raise ValueError(
                    f"Output for item '{self.item_id}' has origin 'synthetic_fixture' "
                    f"but is missing mandatory 'fixture_note'."
                )
        return self


class Submission(BaseModel):
    """Submission data contract (trace.submission/1.0)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["trace.submission/1.0"] = Field(
        default="trace.submission/1.0",
        description="Schema version identifier",
    )
    dataset_id: str = Field(..., min_length=1, description="Identifier of the target dataset")
    system: SystemMetadata = Field(..., description="System metadata and provenance")
    outputs: list[SubmissionOutput] = Field(
        ...,
        min_length=1,
        description="List of system or synthetic outputs per benchmark item",
    )

    @model_validator(mode="before")
    @classmethod
    def check_schema_version(cls, data: Any) -> Any:
        if isinstance(data, dict):
            version = data.get("schema_version", "trace.submission/1.0")
            if version != "trace.submission/1.0":
                raise ValueError(
                    f"Unsupported schema version '{version}'. Expected 'trace.submission/1.0'."
                )
        return data

    @model_validator(mode="after")
    def validate_submission_integrity(self) -> Submission:
        seen_items: set[str] = set()
        has_recorded_system = False

        for output in self.outputs:
            if output.item_id in seen_items:
                raise ValueError(f"Duplicate item_id '{output.item_id}' in submission outputs")
            seen_items.add(output.item_id)

            if output.origin == "recorded_system":
                has_recorded_system = True

        if has_recorded_system and self.system.provenance is None:
            raise ValueError(
                "Submission contains 'recorded_system' outputs, but 'system.provenance' is missing."
            )

        return self
