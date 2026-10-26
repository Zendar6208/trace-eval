"""TRACE AI versioned data contracts and schemas."""

from trace_eval.schema.comparison import (
    ComparisonResult,
    ComparisonSummary,
    ItemComparison,
    MetricDelta,
    RunReference,
)
from trace_eval.schema.dataset import (
    Dataset,
    DatasetItem,
    GoldPassageRelevance,
    Passage,
    RequiredFact,
)
from trace_eval.schema.labels import (
    CitationUnitLabel,
    ItemLabels,
    LabelsDocument,
    SentenceLabel,
)
from trace_eval.schema.run import (
    AggregateMetrics,
    BootstrapConfig,
    CalibrationGrid,
    CalibrationRecord,
    CalibrationThresholds,
    CitationMetrics,
    CitationUnitEvidence,
    ClaimSentenceEvidence,
    CorrectnessMetrics,
    EnvironmentMetadata,
    FailureType,
    GroundingMetrics,
    InputOriginSummary,
    ItemMetrics,
    NLIModelConfig,
    RetrievalMetrics,
    RunConfig,
    RunDatasetReference,
    RunItemEvidence,
    RunItemResult,
    RunResult,
    RunSummary,
    RunThresholds,
)
from trace_eval.schema.submission import (
    RetrievedPassage,
    Submission,
    SubmissionOutput,
    SystemMetadata,
    SystemProvenance,
)

__all__ = [
    # Dataset
    "Dataset",
    "DatasetItem",
    "GoldPassageRelevance",
    "Passage",
    "RequiredFact",
    # Submission
    "Submission",
    "SubmissionOutput",
    "RetrievedPassage",
    "SystemMetadata",
    "SystemProvenance",
    # Labels
    "LabelsDocument",
    "ItemLabels",
    "SentenceLabel",
    "CitationUnitLabel",
    # Run
    "RunResult",
    "RunConfig",
    "RunThresholds",
    "RunDatasetReference",
    "RunSummary",
    "RunItemResult",
    "ItemMetrics",
    "RetrievalMetrics",
    "CorrectnessMetrics",
    "CitationMetrics",
    "GroundingMetrics",
    "FailureType",
    "RunItemEvidence",
    "ClaimSentenceEvidence",
    "CitationUnitEvidence",
    "AggregateMetrics",
    "EnvironmentMetadata",
    "InputOriginSummary",
    "NLIModelConfig",
    "CalibrationRecord",
    "CalibrationGrid",
    "CalibrationThresholds",
    "BootstrapConfig",
    # Comparison
    "ComparisonResult",
    "ComparisonSummary",
    "ItemComparison",
    "MetricDelta",
    "RunReference",
]
