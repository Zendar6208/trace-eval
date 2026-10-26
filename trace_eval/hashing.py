"""Cryptographic content and result hashing conforming to Methodology Sections 8.2 & 8.3.

This module implements deterministic SHA-256 content hashing for:
- Dataset: canonical JSON of {schema_version, dataset_id, language, corpus, items}.
  Excludes: name, description, license.
- Submission: canonical JSON of {schema_version, dataset_id, outputs}.
  Excludes: system.
- Labels: canonical JSON of the whole document except annotator_notes.
- Run result: canonical JSON of {schema_version, methodology_version, dataset: {id, content_sha256},
  submission_content_sha256, config, summary, items}.
  Strictly excludes: run_id, result_hash, runtime_status, environment, system, input_origin_summary.
- run_id derivation: first 16 hexadecimal characters of result_hash.

All functions are guaranteed to be side-effect free and never mutate their inputs.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from pydantic import BaseModel

from trace_eval.canonical import canonical_json


def _to_clean_dict(obj: BaseModel | dict[str, Any]) -> dict[str, Any]:
    """Convert a Pydantic model or dict to an isolated, unmutated dict."""
    if isinstance(obj, BaseModel):
        # model_dump with nulls included and mode='json'
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return copy.deepcopy(obj)
    raise TypeError(f"Expected BaseModel or dict, got {type(obj).__name__}")


def hash_dataset(dataset: BaseModel | dict[str, Any]) -> str:
    """Compute dataset.content_sha256 per Methodology Section 8.2.

    Includes: schema_version, dataset_id, language, corpus, items.
    Excludes: name, description, license.

    Returns:
        64-character lowercase hexadecimal SHA-256 digest.
    """
    data = _to_clean_dict(dataset)
    core = {
        "schema_version": data["schema_version"],
        "dataset_id": data["dataset_id"],
        "language": data.get("language", "en"),
        "corpus": data.get("corpus", []),
        "items": data["items"],
    }
    canonical_bytes = canonical_json(core)
    return hashlib.sha256(canonical_bytes).hexdigest()


def hash_submission(submission: BaseModel | dict[str, Any]) -> str:
    """Compute submission.content_sha256 per Methodology Section 8.2.

    Includes: schema_version, dataset_id, outputs.
    Excludes: system (name, version, provenance).

    Returns:
        64-character lowercase hexadecimal SHA-256 digest.
    """
    data = _to_clean_dict(submission)
    core = {
        "schema_version": data["schema_version"],
        "dataset_id": data["dataset_id"],
        "outputs": data["outputs"],
    }
    canonical_bytes = canonical_json(core)
    return hashlib.sha256(canonical_bytes).hexdigest()


def hash_labels(labels: BaseModel | dict[str, Any]) -> str:
    """Compute labels.content_sha256 per Methodology Section 8.2.

    Includes: whole labels document.
    Excludes: annotator_notes.

    Returns:
        64-character lowercase hexadecimal SHA-256 digest.
    """
    data = _to_clean_dict(labels)
    core = {k: v for k, v in data.items() if k != "annotator_notes"}
    canonical_bytes = canonical_json(core)
    return hashlib.sha256(canonical_bytes).hexdigest()


def extract_run_core(run: BaseModel | dict[str, Any]) -> dict[str, Any]:
    """Extract the deterministic semantic core of an evaluation run per Section 8.3.

    Includes: schema_version, methodology_version, dataset {id, content_sha256},
    submission_content_sha256, config, summary, items.

    Excludes: run_id, result_hash, runtime_status, environment, system, input_origin_summary.
    """
    data = _to_clean_dict(run)
    dataset_ref = data["dataset"]
    return {
        "schema_version": data["schema_version"],
        "methodology_version": data.get("methodology_version", "1.0.0"),
        "dataset": {
            "id": dataset_ref["id"],
            "content_sha256": dataset_ref["content_sha256"],
        },
        "submission_content_sha256": data["submission_content_sha256"],
        "config": data["config"],
        "summary": data["summary"],
        "items": data["items"],
    }


def compute_run_hashes(run: BaseModel | dict[str, Any]) -> tuple[str, str]:
    """Compute result_hash and derive run_id per Methodology Section 8.3.

    Args:
        run: RunResult model or dict.

    Returns:
        tuple of (result_hash [64 hex chars], run_id [16 hex chars]).
    """
    core = extract_run_core(run)
    canonical_bytes = canonical_json(core)
    result_hash = hashlib.sha256(canonical_bytes).hexdigest()
    run_id = result_hash[:16]
    return result_hash, run_id


def verify_run_hashes(run: BaseModel | dict[str, Any]) -> bool:
    """Verify that a run document's result_hash and run_id match its semantic core."""
    data = _to_clean_dict(run)
    expected_result_hash, expected_run_id = compute_run_hashes(data)
    actual_result_hash = data.get("result_hash")
    actual_run_id = data.get("run_id")
    return actual_result_hash == expected_result_hash and actual_run_id == expected_run_id
