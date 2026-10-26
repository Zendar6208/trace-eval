"""Pydantic v2 data contract for trace.comparison/1.0.

Methodology requirements:
- Paired run comparison with cluster bootstrap confidence intervals.
- Regression detection and flagging for CI gates (e.g. `trace compare --fail-on-regression`).
- Item-level and aggregate metric differences between baseline and candidate runs.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trace_eval.schema.run import RunDatasetReference


class RunReference(BaseModel):
    """Reference to an evaluated run in a paired comparison."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., min_length=1, description="16-character run identifier")
    result_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="64-character SHA-256 result hash",
    )
    system_name: str | None = Field(default=None, description="System or pipeline name")


class MetricDelta(BaseModel):
    """Statistical difference and confidence interval for a single evaluation metric."""

    model_config = ConfigDict(extra="forbid")

    metric_name: str = Field(..., min_length=1, description="Standard metric identifier")
    baseline_value: float | None = Field(default=None, description="Metric value in baseline run")
    candidate_value: float | None = Field(default=None, description="Metric value in candidate run")
    absolute_delta: float | None = Field(
        default=None,
        description="Candidate value minus baseline value",
    )
    relative_delta: float | None = Field(
        default=None,
        description="Relative percentage change if baseline > 0",
    )
    ci_lower: float | None = Field(
        default=None,
        description="Lower bound of cluster bootstrap confidence interval",
    )
    ci_upper: float | None = Field(
        default=None,
        description="Upper bound of cluster bootstrap confidence interval",
    )
    p_value: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Statistical significance p-value",
    )
    significant: bool | None = Field(
        default=None,
        description="True if delta is statistically significant at configured alpha",
    )


class ItemComparison(BaseModel):
    """Item-level paired evaluation difference."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(..., min_length=1, description="Benchmark item identifier")
    baseline_verdict: str | None = Field(
        default=None, description="Correctness verdict in baseline"
    )
    candidate_verdict: str | None = Field(
        default=None,
        description="Correctness verdict in candidate",
    )
    baseline_failure_types: list[str] = Field(
        default_factory=list,
        description="Failure types assigned in baseline",
    )
    candidate_failure_types: list[str] = Field(
        default_factory=list,
        description="Failure types assigned in candidate",
    )
    status: Literal["improved", "regressed", "unchanged"] = Field(
        ...,
        description="Outcome classification for this item",
    )
    notes: str | None = Field(default=None, description="Optional diagnostic notes")


class ComparisonSummary(BaseModel):
    """High-level summary of paired run comparison."""

    model_config = ConfigDict(extra="forbid")

    total_items: int = Field(..., ge=0, description="Total items compared across both runs")
    regressed_items_count: int = Field(default=0, ge=0, description="Items that degraded")
    improved_items_count: int = Field(default=0, ge=0, description="Items that improved")
    unchanged_items_count: int = Field(default=0, ge=0, description="Items with identical verdict")


class ComparisonResult(BaseModel):
    """Paired run comparison document contract (trace.comparison/1.0)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["trace.comparison/1.0"] = Field(
        default="trace.comparison/1.0",
        description="Schema version identifier",
    )
    comparison_id: str = Field(..., min_length=1, description="Unique comparison identifier")
    baseline_run: RunReference = Field(..., description="Baseline reference run")
    candidate_run: RunReference = Field(..., description="Candidate evaluation run")
    dataset: RunDatasetReference = Field(..., description="Common benchmark dataset")
    metrics_diff: dict[str, MetricDelta] = Field(
        default_factory=dict,
        description="Metric deltas and bootstrap confidence intervals",
    )
    regression_detected: bool = Field(
        default=False,
        description="True if any regression gate criteria were breached",
    )
    regression_reasons: list[str] = Field(
        default_factory=list,
        description="Explanations for flagged regressions",
    )
    summary: ComparisonSummary = Field(..., description="High-level item outcome counts")
    item_comparisons: list[ItemComparison] = Field(
        default_factory=list,
        description="Item-level paired comparisons",
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Comparison execution metadata"
    )

    @model_validator(mode="before")
    @classmethod
    def check_schema_version(cls, data: Any) -> Any:
        if isinstance(data, dict):
            version = data.get("schema_version", "trace.comparison/1.0")
            if version != "trace.comparison/1.0":
                raise ValueError(
                    f"Unsupported schema version '{version}'. Expected 'trace.comparison/1.0'."
                )
        return data
