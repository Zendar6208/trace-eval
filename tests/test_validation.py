"""Tests for cross-document referential and cryptographic integrity verification."""

import copy
import json
from pathlib import Path

import pytest

from trace_eval.schema.dataset import Dataset, GoldPassageRelevance
from trace_eval.schema.labels import LabelsDocument
from trace_eval.schema.run import CitationUnitEvidence, RunResult
from trace_eval.schema.submission import Submission
from trace_eval.validation import (
    CrossDocumentValidationError,
    validate_cross_document_integrity,
    validate_labels_against_submission,
    validate_run_against_inputs,
    validate_submission_against_dataset,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> dict:
    return json.loads((FIXTURES_DIR / filename).read_text(encoding="utf-8"))


@pytest.fixture
def valid_dataset() -> Dataset:
    return Dataset.model_validate(load_fixture("golden_dataset_m0_corrected.json"))


@pytest.fixture
def valid_submission() -> Submission:
    return Submission.model_validate(load_fixture("golden_submission.json"))


@pytest.fixture
def valid_labels() -> LabelsDocument:
    return LabelsDocument.model_validate(load_fixture("golden_labels.json"))


@pytest.fixture
def valid_run() -> RunResult:
    return RunResult.model_validate(load_fixture("golden_run_m0_corrected.json"))


def test_cross_document_validation_success(
    valid_dataset, valid_submission, valid_labels, valid_run
):
    """All valid documents together must pass cross-document integrity checks."""
    errors = validate_cross_document_integrity(
        dataset=valid_dataset,
        submission=valid_submission,
        labels=valid_labels,
        run=valid_run,
        raise_on_error=True,
    )
    assert errors == []


def test_submission_dataset_id_mismatch(valid_dataset, valid_submission):
    bad_submission_dict = valid_submission.model_dump(mode="json")
    bad_submission_dict["dataset_id"] = "different-dataset-id"
    bad_submission = Submission.model_validate(bad_submission_dict)

    errors = validate_submission_against_dataset(valid_dataset, bad_submission)
    assert any("Dataset ID mismatch" in e for e in errors)


def test_submission_missing_dataset_item(valid_dataset, valid_submission):
    bad_sub_dict = valid_submission.model_dump(mode="json")
    bad_sub_dict["outputs"] = [bad_sub_dict["outputs"][0]]  # only item-001, missing item-002
    bad_sub = Submission.model_validate(bad_sub_dict)

    errors = validate_submission_against_dataset(valid_dataset, bad_sub)
    assert any("missing 1 item(s)" in e for e in errors)


def test_submission_unknown_dataset_item(valid_dataset, valid_submission):
    bad_sub_dict = valid_submission.model_dump(mode="json")
    bad_sub_dict["outputs"].append(
        {
            "item_id": "item-unknown-999",
            "origin": "synthetic_fixture",
            "fixture_note": "Unknown item",
            "answer": "Answer.",
            "retrieved": [],
        }
    )
    bad_sub = Submission.model_validate(bad_sub_dict)

    errors = validate_submission_against_dataset(valid_dataset, bad_sub)
    assert any("unknown item_id(s)" in e for e in errors)


def test_labels_cryptographic_mismatch(valid_labels, valid_submission):
    bad_labels_dict = valid_labels.model_dump(mode="json")
    bad_labels_dict["submission_content_sha256"] = "a" * 64
    bad_labels = LabelsDocument.model_validate(bad_labels_dict)

    errors = validate_labels_against_submission(bad_labels, valid_submission)
    assert any("Cryptographic binding mismatch" in e for e in errors)


def test_run_tampered_dataset_hash(valid_run, valid_dataset, valid_submission):
    # Alter dataset content
    tampered_dataset_dict = valid_dataset.model_dump(mode="json")
    tampered_dataset_dict["items"][0]["question"] = "Altered question?"
    tampered_dataset = Dataset.model_validate(tampered_dataset_dict)

    errors = validate_run_against_inputs(valid_run, tampered_dataset, valid_submission)
    assert any("dataset.content_sha256" in e for e in errors)


def test_cross_document_raise_on_error(valid_dataset, valid_submission):
    bad_sub_dict = valid_submission.model_dump(mode="json")
    bad_sub_dict["dataset_id"] = "mismatched-id"
    bad_sub = Submission.model_validate(bad_sub_dict)

    with pytest.raises(CrossDocumentValidationError, match="Cross-document validation failed"):
        validate_cross_document_integrity(valid_dataset, bad_sub, raise_on_error=True)


# --- Semantic Validators: Orphan and Invalid Citation Support ---


def test_orphan_citation_cannot_be_supporting():
    with pytest.raises(ValueError, match="Orphan citation.*cannot be supporting per CA-4"):
        CitationUnitEvidence(
            sentence_index=None,
            passage_id="p01",
            validity="ok",
            supports=True,  # Violation of CA-4
        )


def test_invalid_citation_validity_cannot_be_supporting():
    for bad_validity in ["not_retrieved", "unknown_id", "index_out_of_range"]:
        with pytest.raises(ValueError, match="cannot be supporting per CA-7"):
            CitationUnitEvidence(
                sentence_index=0,
                passage_id="p99",
                validity=bad_validity,
                supports=True,  # Violation of CA-7
            )


# --- Graded Relevance Tests ---


def test_graded_gold_relevance_mapping(valid_dataset):
    item = valid_dataset.items[0]
    # Default gold relevance map when gold_passage_relevance is not specified
    rel_map = item.get_gold_relevance_map()
    assert rel_map == {"p01": 3}

    # Explicit graded relevance
    graded_item = copy.deepcopy(item)
    graded_item.gold_passage_relevance = [GoldPassageRelevance(passage_id="p01", relevance=2)]
    assert graded_item.get_gold_relevance_map() == {"p01": 2}


def test_invalid_gold_relevance_score():
    with pytest.raises(ValueError):
        GoldPassageRelevance(passage_id="p01", relevance=0)  # ge=1

    with pytest.raises(ValueError):
        GoldPassageRelevance(passage_id="p01", relevance=4)  # le=3


# --- Run Tampering Tests ---


def test_run_tampered_result_hash_rejected(valid_run):
    run_dict = valid_run.model_dump(mode="json")
    run_dict["result_hash"] = "f" * 64
    with pytest.raises(ValueError, match="result_hash integrity mismatch"):
        RunResult.model_validate(run_dict)


def test_run_tampered_run_id_rejected(valid_run):
    run_dict = valid_run.model_dump(mode="json")
    run_dict["run_id"] = "f" * 16
    with pytest.raises(ValueError, match="result_hash integrity mismatch"):
        RunResult.model_validate(run_dict)
