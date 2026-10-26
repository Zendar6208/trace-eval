"""TRACE AI: Deterministic-first RAG evaluation engine and workbench."""

from trace_eval.canonical import canonical_json
from trace_eval.hashing import (
    compute_run_hashes,
    extract_run_core,
    hash_dataset,
    hash_labels,
    hash_submission,
    verify_run_hashes,
)
from trace_eval.validation import (
    CrossDocumentValidationError,
    validate_cross_document_integrity,
    validate_labels_against_submission,
    validate_run_against_inputs,
    validate_submission_against_dataset,
)

__version__ = "0.1.0"
__methodology_version__ = "1.0.0"

__all__ = [
    "canonical_json",
    "hash_dataset",
    "hash_submission",
    "hash_labels",
    "extract_run_core",
    "compute_run_hashes",
    "verify_run_hashes",
    "CrossDocumentValidationError",
    "validate_cross_document_integrity",
    "validate_submission_against_dataset",
    "validate_labels_against_submission",
    "validate_run_against_inputs",
]
