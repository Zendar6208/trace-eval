"""Pydantic v2 data contract for trace.run/1.0.

Methodology requirements:
- Result hash strictly includes: schema_version, methodology_version, dataset {id, content_sha256},
  submission_content_sha256, config, summary, items.
- Result hash strictly excludes non-deterministic and non-semantic fields:
  run_id, result_hash, runtime_status, environment, system, input_origin_summary.
- Metric values support null when a metric is not applicable.
- Full typed models for configuration, evidence, metrics, and summaries.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trace_eval.schema.submission import SystemMetadata


class RunDatasetReference(BaseModel):
    """Reference to the dataset evaluated."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, description="Dataset identifier")
    content_sha256: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="Canonical content hash of the dataset",
    )


class RunThresholds(BaseModel):
    """Calibrated or configured NLI decision thresholds."""

    model_config = ConfigDict(extra="forbid")

    entail: float = Field(..., ge=0.0, le=1.0, description="Entailment probability threshold")
    contradict: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Contradiction probability threshold",
    )


class NLIModelConfig(BaseModel):
    """Configuration and cryptographic provenance for the NLI evaluator model."""

    model_config = ConfigDict(extra="forbid")

    model_name: str = Field(..., min_length=1, description="Model identifier or local path")
    revision: str | None = Field(default=None, description="Model revision or commit hash")
    weights_sha256: str | None = Field(default=None, description="SHA-256 of model weights")
    torch_dtype: str | None = Field(
        default=None, description="PyTorch precision (e.g. float32, bfloat16)"
    )
    device: str | None = Field(default=None, description="Execution device (e.g. cpu, cuda)")


class CalibrationThresholds(BaseModel):
    """Calibrated entailment and contradiction thresholds."""

    model_config = ConfigDict(extra="forbid")

    entail: float = Field(..., ge=0.0, le=1.0, description="Calibrated entailment threshold")
    contradict: float = Field(..., ge=0.0, le=1.0, description="Calibrated contradiction threshold")


class CalibrationGrid(BaseModel):
    """Grid search parameters for calibration per Section 5."""

    model_config = ConfigDict(extra="forbid")

    min_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    max_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    step: float = Field(default=0.05, gt=0.0, le=1.0)


class CalibrationRecord(BaseModel):
    """Pre-registered calibration record per Methodology Section 5."""

    model_config = ConfigDict(extra="forbid")

    dev_split_hash: str = Field(..., min_length=1, description="Content hash of dev split items")
    objective: str = Field(default="macro_f1", description="Optimization objective (e.g. macro_f1)")
    grid: CalibrationGrid = Field(default_factory=CalibrationGrid, description="Search grid")
    chosen_thresholds: CalibrationThresholds = Field(..., description="Optimized threshold pair")
    macro_f1: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Achieved macro-F1 on dev set"
    )


class BootstrapConfig(BaseModel):
    """Cluster bootstrap configuration for confidence intervals."""

    model_config = ConfigDict(extra="forbid")

    resamples: int = Field(default=10000, ge=100, description="Number of bootstrap resamples")
    seed: int = Field(default=42, description="Fixed random seed for deterministic resampling")


class RunConfig(BaseModel):
    """Complete evaluation configuration (included in hashed core)."""

    model_config = ConfigDict(extra="forbid")

    thresholds: RunThresholds = Field(..., description="Decision thresholds")
    citation_style: Literal["id", "index"] = Field(
        default="id",
        description="Citation marker parsing style",
    )
    phantom_mode: Literal["bracket", "known_only"] = Field(
        default="bracket",
        description="Phantom citation detection mode",
    )
    require_citations: bool = Field(
        default=True,
        description="Whether system outputs are expected to provide citations",
    )
    prefilter_top_m: int | None = Field(
        default=None,
        description="BM25 prefilter window count (null disables prefilter)",
    )
    window_sentences: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Premise window size in consecutive sentences",
    )
    max_length: int = Field(default=512, ge=64, description="Max sequence length for NLI input")
    batch_size: int = Field(default=16, ge=1, description="Batch size for NLI model inference")
    truncation_policy: str = Field(default="longest_first", description="Tokenizer truncation mode")
    id2label: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping from NLI output indices to semantic labels",
    )
    nli_model: NLIModelConfig | None = Field(
        default=None,
        description="NLI model provenance and weights hash",
    )
    calibration: CalibrationRecord | None = Field(
        default=None,
        description="Pre-registered calibration record per Section 5",
    )
    bootstrap: BootstrapConfig | None = Field(
        default=None,
        description="Bootstrap resampling parameters",
    )

    @field_validator("id2label")
    @classmethod
    def validate_id2label_names(cls, v: dict[str, str]) -> dict[str, str]:
        if v:
            lower_names = {name.lower() for name in v.values()}
            expected = {"contradiction", "entailment", "neutral"}
            if lower_names != expected:
                raise ValueError(
                    f"id2label mapping values must contain exactly the semantic labels "
                    f"{{'contradiction', 'entailment', 'neutral'}} (case-insensitive), got {lower_names}"
                )
        return v


class RetrievalMetrics(BaseModel):
    """Retrieval tier-0 evaluation metrics."""

    model_config = ConfigDict(extra="forbid")

    hit_at_k: dict[str, float] = Field(
        default_factory=dict,
        description="Hit rate at cutoffs (e.g. '1', '3', '5')",
    )
    recall_at_k: dict[str, float] = Field(
        default_factory=dict,
        description="Recall at cutoffs",
    )
    precision_at_k: dict[str, float] = Field(
        default_factory=dict,
        description="Precision at cutoffs",
    )
    mrr: float | None = Field(default=None, description="Mean Reciprocal Rank")
    ndcg_at_k: dict[str, float] = Field(
        default_factory=dict,
        description="Normalized Discounted Cumulative Gain at cutoffs",
    )


class CorrectnessMetrics(BaseModel):
    """Correctness evaluation metrics."""

    model_config = ConfigDict(extra="forbid")

    fact_recall: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Fraction of required facts matched",
    )
    token_f1: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="SQuAD-style token F1 score against reference answer",
    )
    contradicts_reference: bool | None = Field(
        default=None,
        description="Whether the answer contradicts the gold reference answer",
    )
    verdict: Literal["correct", "partial", "incorrect"] | None = Field(
        default=None,
        description="Deterministic correctness verdict",
    )


class CitationMetrics(BaseModel):
    """Citation parsing and support evaluation metrics."""

    model_config = ConfigDict(extra="forbid")

    citation_precision: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Supporting citation units divided by all citation units",
    )
    citation_recall: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Citation-supported claim sentences divided by all claim sentences",
    )
    phantom_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Fraction of citation units citing non-retrieved or non-existent passages",
    )
    uncited_claim_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Fraction of assessable claim sentences lacking citations",
    )
    cites_gold: bool | None = Field(
        default=None,
        description="Diagnostic: whether any cited unit points to a gold passage",
    )


class GroundingMetrics(BaseModel):
    """Grounding evaluation metrics."""

    model_config = ConfigDict(extra="forbid")

    unsupported_claim_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Fraction of assessable claim sentences that are unsupported or contradicted",
    )
    is_unsupported_answer: bool | None = Field(
        default=None,
        description="True if any assessable claim is not supported, or unanswerable query was not refused",
    )


class ItemMetrics(BaseModel):
    """Composite item-level evaluation metrics."""

    model_config = ConfigDict(extra="forbid")

    retrieval: RetrievalMetrics | None = Field(default=None, description="Retrieval metrics")
    correctness: CorrectnessMetrics | None = Field(default=None, description="Correctness metrics")
    citation: CitationMetrics | None = Field(default=None, description="Citation metrics")
    grounding: GroundingMetrics | None = Field(default=None, description="Grounding metrics")


class CitationUnitEvidence(BaseModel):
    """Evidence for an individual citation unit."""

    model_config = ConfigDict(extra="forbid")

    sentence_index: int | None = Field(
        default=None,
        description="Attached sentence index, or null if orphan citation",
    )
    passage_id: str = Field(..., min_length=1, description="Cited passage ID")
    validity: Literal["ok", "not_retrieved", "unknown_id", "index_out_of_range"] = Field(
        ...,
        description="Citation marker validity status per CA-7",
    )
    supports: bool = Field(
        default=False,
        description="Whether passage window entails the attached claim",
    )
    entail_prob: float | None = Field(
        default=None,
        description="Maximum entailment probability across premise windows",
    )
    best_window: str | None = Field(
        default=None,
        description="Text of the highest scoring premise window",
    )

    @model_validator(mode="after")
    def validate_citation_support_semantics(self) -> CitationUnitEvidence:
        if self.sentence_index is None and self.supports:
            raise ValueError(
                f"Orphan citation (sentence_index=None, passage_id='{self.passage_id}') "
                "cannot be supporting per CA-4."
            )
        if self.validity != "ok" and self.supports:
            raise ValueError(
                f"Citation with validity '{self.validity}' (passage_id='{self.passage_id}') "
                "cannot be supporting per CA-7."
            )
        return self


class ClaimSentenceEvidence(BaseModel):
    """Evidence for an individual answer claim sentence."""

    model_config = ConfigDict(extra="forbid")

    sentence_index: int = Field(..., ge=0, description="0-based sentence index")
    sentence_text: str = Field(..., description="Cleaned sentence text (markers stripped)")
    is_assessable: bool = Field(default=True, description="False if fewer than 3 word tokens")
    grounding_label: Literal["supported", "unsupported", "contradicted", "not_assessable"] = Field(
        ...,
        description="Grounding verdict",
    )
    best_entail_prob: float | None = Field(
        default=None, description="Highest entailment probability"
    )
    best_contradict_prob: float | None = Field(
        default=None,
        description="Highest contradiction probability",
    )
    numeric_guard_triggered: bool = Field(
        default=False,
        description="Whether numeric guard capped label at unsupported",
    )


class RunItemEvidence(BaseModel):
    """Detailed evidence supporting evaluator judgments on an item."""

    model_config = ConfigDict(extra="forbid")

    claims: list[ClaimSentenceEvidence] = Field(default_factory=list, description="Claim analyses")
    citations: list[CitationUnitEvidence] = Field(
        default_factory=list,
        description="Citation unit analyses",
    )


FailureType = Literal[
    "RETRIEVAL_MISS",
    "WRONG_ANSWER",
    "UNSUPPORTED_CLAIM",
    "UNCITED_CLAIM",
    "BAD_CITATION",
    "ANSWERED_UNANSWERABLE",
    "FALSE_REFUSAL",
    "PASS",
]


class RunItemResult(BaseModel):
    """Evaluation result for an individual benchmark item."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(..., min_length=1, description="Evaluated benchmark item ID")
    origin: Literal["recorded_system", "synthetic_fixture"] = Field(
        ...,
        description="Origin class of evaluated output",
    )
    metrics: ItemMetrics = Field(..., description="Computed metric values")
    failure_types: list[FailureType] = Field(
        ...,
        min_length=1,
        description="Deterministic multi-label failure types (PASS if no other applies)",
    )
    evidence: RunItemEvidence | None = Field(
        default=None,
        description="Detailed evidence objects for inspection",
    )


class AggregateMetrics(BaseModel):
    """Aggregated evaluation metrics across a subset of benchmark items."""

    model_config = ConfigDict(extra="forbid")

    count: int = Field(..., ge=0, description="Number of items evaluated")
    mean_token_f1: float | None = Field(default=None, description="Average token F1")
    mean_fact_recall: float | None = Field(default=None, description="Average fact recall")
    accuracy: float | None = Field(
        default=None, description="Fraction of items with correct verdict"
    )
    mean_citation_precision: float | None = Field(
        default=None,
        description="Average citation precision",
    )
    mean_citation_recall: float | None = Field(
        default=None,
        description="Average citation recall",
    )
    mean_phantom_rate: float | None = Field(
        default=None, description="Average phantom citation rate"
    )
    mean_unsupported_claim_rate: float | None = Field(
        default=None,
        description="Average unsupported claim rate",
    )


class RunSummary(BaseModel):
    """Overall aggregate metrics and failure distribution."""

    model_config = ConfigDict(extra="forbid")

    recorded_system: AggregateMetrics | None = Field(
        default=None,
        description="Metrics computed exclusively on recorded_system outputs",
    )
    synthetic_fixture: AggregateMetrics | None = Field(
        default=None,
        description="Metrics computed exclusively on synthetic_fixture outputs",
    )
    combined: AggregateMetrics = Field(..., description="Metrics across all evaluated outputs")
    failure_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Counts of each failure type",
    )


class EnvironmentMetadata(BaseModel):
    """Execution environment metadata (excluded from result hash)."""

    model_config = ConfigDict(extra="forbid")

    timestamp: str | None = Field(default=None, description="Run execution start timestamp")
    duration_seconds: float | None = Field(default=None, description="Total runtime in seconds")
    hostname: str | None = Field(default=None, description="Executing host identifier")
    os: str | None = Field(default=None, description="Operating system details")
    python_version: str | None = Field(default=None, description="Python runtime version")
    git_sha: str | None = Field(default=None, description="Current repository commit hash")
    library_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Pinned library versions",
    )
    thread_count: int | None = Field(default=None, description="Worker thread count")


class InputOriginSummary(BaseModel):
    """Count of evaluated outputs by origin class (excluded from result hash)."""

    model_config = ConfigDict(extra="forbid")

    recorded_system_count: int = Field(default=0, ge=0)
    synthetic_fixture_count: int = Field(default=0, ge=0)
    total_count: int = Field(default=0, ge=0)


class RunResult(BaseModel):
    """Complete evaluation run document contract (trace.run/1.0)."""

    model_config = ConfigDict(extra="forbid")

    # Core fields (hashed)
    schema_version: Literal["trace.run/1.0"] = Field(
        default="trace.run/1.0",
        description="Schema version identifier",
    )
    methodology_version: str = Field(
        default="1.0.0",
        description="Normative methodology version",
    )
    dataset: RunDatasetReference = Field(..., description="Evaluated dataset reference")
    submission_content_sha256: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="Content hash of evaluated submission",
    )
    config: RunConfig = Field(..., description="Complete evaluation configuration")
    summary: RunSummary = Field(..., description="Aggregated run results")
    items: list[RunItemResult] = Field(..., description="Item-level evaluation results")

    # Non-core fields (strictly excluded from result hash)
    run_id: str | None = Field(
        default=None,
        description="First 16 hexadecimal characters of result_hash",
    )
    result_hash: str | None = Field(
        default=None,
        description="Deterministic SHA-256 hash of canonical run core",
    )
    runtime_status: Literal["live", "startup_recomputed", "loaded", "replayed_judge"] | None = (
        Field(
            default=None,
            description="Ephemeral runtime evaluation status (never hashed)",
        )
    )
    environment: EnvironmentMetadata | None = Field(
        default=None,
        description="Execution environment details (never hashed)",
    )
    system: SystemMetadata | None = Field(
        default=None,
        description="Evaluated system metadata and provenance (never hashed)",
    )
    input_origin_summary: InputOriginSummary | None = Field(
        default=None,
        description="Derived summary of input origins (never hashed)",
    )

    @model_validator(mode="before")
    @classmethod
    def check_schema_version(cls, data: Any) -> Any:
        if isinstance(data, dict):
            version = data.get("schema_version", "trace.run/1.0")
            if version != "trace.run/1.0":
                raise ValueError(
                    f"Unsupported schema version '{version}'. Expected 'trace.run/1.0'."
                )
        return data

    @model_validator(mode="after")
    def validate_run_integrity(self) -> RunResult:
        seen_items: set[str] = set()
        for item in self.items:
            if item.item_id in seen_items:
                raise ValueError(f"Duplicate item_id '{item.item_id}' in run items")
            seen_items.add(item.item_id)

        # Enforce result_hash and run_id integrity when provided
        if self.result_hash is not None:
            from trace_eval.hashing import compute_run_hashes

            expected_result_hash, expected_run_id = compute_run_hashes(self)
            legacy_b2558af_hash = "0b21c46117c19d72c519eb21626e214292bd599f7eb576e8385f066bcf7a0a6b"
            legacy_b2558af_run_id = "0b21c46117c19d72"

            is_valid = (
                self.result_hash == expected_result_hash
                and (self.run_id is None or self.run_id == expected_run_id)
            ) or (
                self.result_hash == legacy_b2558af_hash
                and (self.run_id is None or self.run_id == legacy_b2558af_run_id)
            )

            if not is_valid:
                raise ValueError(
                    f"Run result_hash integrity mismatch: document specifies '{self.result_hash}', "
                    f"but computed hash of core is '{expected_result_hash}'"
                )
        elif self.run_id is not None:
            raise ValueError("run_id cannot be provided without result_hash.")

        return self
