"""Cross-document referential and cryptographic integrity verification.

This module validates consistency and bindings across benchmark artifacts:
- Submission conforms to Dataset (dataset_id, item_id presence and coverage, valid corpus IDs).
- Labels conform to Submission (submission_content_sha256 cryptographic binding, item_id presence).
- Run conforms to Dataset & Submission (content_sha256 checks, item coverage).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trace_eval.hashing import hash_dataset, hash_submission

if TYPE_CHECKING:
    from trace_eval.schema.dataset import Dataset
    from trace_eval.schema.labels import LabelsDocument
    from trace_eval.schema.run import RunResult
    from trace_eval.schema.submission import Submission


class CrossDocumentValidationError(ValueError):
    """Raised when cross-document referential or cryptographic constraints are breached."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        formatted = "\n  - " + "\n  - ".join(errors)
        super().__init__(
            f"Cross-document validation failed with {len(errors)} error(s):{formatted}"
        )


def validate_submission_against_dataset(
    dataset: Dataset,
    submission: Submission,
) -> list[str]:
    """Validate referential integrity between a Submission and its target Dataset.

    Checks:
    1. dataset_id match.
    2. Every submission output corresponds to an item in the dataset.
    3. Every dataset item is covered in the submission outputs.
    """
    errors: list[str] = []

    if submission.dataset_id != dataset.dataset_id:
        errors.append(
            f"Dataset ID mismatch: submission targets '{submission.dataset_id}', "
            f"but dataset is '{dataset.dataset_id}'"
        )

    dataset_item_ids = {item.id for item in dataset.items}
    submission_item_ids = {output.item_id for output in submission.outputs}

    # Unknown items in submission
    unknown_items = submission_item_ids - dataset_item_ids
    if unknown_items:
        errors.append(
            f"Submission contains {len(unknown_items)} unknown item_id(s) not in dataset: "
            f"{sorted(unknown_items)[:5]}"
        )

    # Missing items in submission
    missing_items = dataset_item_ids - submission_item_ids
    if missing_items:
        errors.append(
            f"Submission is missing {len(missing_items)} item(s) present in dataset: "
            f"{sorted(missing_items)[:5]}"
        )

    return errors


def validate_labels_against_submission(
    labels: LabelsDocument,
    submission: Submission,
) -> list[str]:
    """Validate cryptographic and referential binding between Labels and Submission.

    Checks:
    1. dataset_id match.
    2. labels.submission_content_sha256 exactly equals computed hash_submission(submission).
    3. Every labeled item corresponds to an output in the submission.
    """
    errors: list[str] = []

    if labels.dataset_id != submission.dataset_id:
        errors.append(
            f"Dataset ID mismatch: labels target dataset '{labels.dataset_id}', "
            f"but submission targets '{submission.dataset_id}'"
        )

    expected_submission_hash = hash_submission(submission)
    if labels.submission_content_sha256 != expected_submission_hash:
        errors.append(
            f"Cryptographic binding mismatch: labels specify submission_content_sha256="
            f"'{labels.submission_content_sha256}', but computed hash is '{expected_submission_hash}'"
        )

    submission_item_ids = {output.item_id for output in submission.outputs}
    for item_labels in labels.items:
        if item_labels.item_id not in submission_item_ids:
            errors.append(
                f"Labels contain item '{item_labels.item_id}' not found in submission outputs"
            )

    return errors


def validate_run_against_inputs(
    run: RunResult,
    dataset: Dataset,
    submission: Submission,
) -> list[str]:
    """Validate that a Run document correctly references and matches its input Dataset and Submission.

    Checks:
    1. run.dataset.id equals dataset.dataset_id.
    2. run.dataset.content_sha256 equals computed hash_dataset(dataset).
    3. run.submission_content_sha256 equals computed hash_submission(submission).
    4. Evaluated items match dataset and submission items.
    """
    errors: list[str] = []

    if run.dataset.id != dataset.dataset_id:
        errors.append(
            f"Run dataset.id '{run.dataset.id}' does not match dataset_id '{dataset.dataset_id}'"
        )

    expected_dataset_hash = hash_dataset(dataset)
    if run.dataset.content_sha256 != expected_dataset_hash:
        errors.append(
            f"Run dataset.content_sha256 '{run.dataset.content_sha256}' does not match "
            f"computed dataset hash '{expected_dataset_hash}'"
        )

    expected_sub_hash = hash_submission(submission)
    if run.submission_content_sha256 != expected_sub_hash:
        errors.append(
            f"Run submission_content_sha256 '{run.submission_content_sha256}' does not match "
            f"computed submission hash '{expected_sub_hash}'"
        )

    run_item_ids = {item.item_id for item in run.items}
    dataset_item_ids = {item.id for item in dataset.items}
    diff = run_item_ids - dataset_item_ids
    if diff:
        errors.append(f"Run contains item IDs not in dataset: {sorted(diff)[:5]}")

    return errors


def validate_cross_document_integrity(
    dataset: Dataset,
    submission: Submission,
    labels: LabelsDocument | None = None,
    run: RunResult | None = None,
    raise_on_error: bool = True,
) -> list[str]:
    """Run full cross-document integrity checks across all provided benchmark documents."""
    all_errors: list[str] = []

    all_errors.extend(validate_submission_against_dataset(dataset, submission))

    if labels is not None:
        all_errors.extend(validate_labels_against_submission(labels, submission))

    if run is not None:
        all_errors.extend(validate_run_against_inputs(run, dataset, submission))

    if all_errors and raise_on_error:
        raise CrossDocumentValidationError(all_errors)

    return all_errors
