"""Regression tests for result classification and PASS consistency.

Verifies:
1. An item with failure_types == ['PASS'] represents a clean pass with 0 failures.
2. PASS is never counted as an evaluation failure.
3. Webapp response formatting populates question text and preserves metrics.
"""

from __future__ import annotations

import json
from pathlib import Path

from trace_eval.evaluator import evaluate_run
from trace_eval.schema.dataset import Dataset
from trace_eval.schema.submission import Submission
from webapp.main import _format_run_response, _item_summary

SAMPLE_DATA_DIR = Path(__file__).parent.parent / "webapp" / "sample_data"


def test_pass_is_not_counted_as_failure():
    """Verify that an item with only 'PASS' has 0 real failure types."""
    with open(SAMPLE_DATA_DIR / "dataset.json", encoding="utf-8") as f:
        dataset = Dataset.model_validate(json.load(f))
    with open(SAMPLE_DATA_DIR / "submission.json", encoding="utf-8") as f:
        submission = Submission.model_validate(json.load(f))

    run_result = evaluate_run(dataset, submission)

    # q01 is a clean pass item in the sample dataset
    q01 = next(item for item in run_result.items if item.item_id == "q01")
    assert q01.failure_types == ["PASS"]

    # Classification logic: actual failures exclude 'PASS'
    actual_failures = [ft for ft in q01.failure_types if ft != "PASS"]
    assert len(actual_failures) == 0, f"Expected 0 failures for q01, got {actual_failures}"

    # Item summary must reflect the clean pass
    summary = _item_summary(q01, question="What is the return window for hardware devices?")
    assert summary["item_id"] == "q01"
    assert summary["question"] == "What is the return window for hardware devices?"
    summary_failures = [ft for ft in summary["failure_types"] if ft != "PASS"]
    assert len(summary_failures) == 0


def test_failed_item_has_real_failures_without_pass():
    """Verify that an item with actual failures does not include PASS and has real failures."""
    with open(SAMPLE_DATA_DIR / "dataset.json", encoding="utf-8") as f:
        dataset = Dataset.model_validate(json.load(f))
    with open(SAMPLE_DATA_DIR / "submission.json", encoding="utf-8") as f:
        submission = Submission.model_validate(json.load(f))

    run_result = evaluate_run(dataset, submission)

    # q05 has real failures in the sample dataset
    q05 = next(item for item in run_result.items if item.item_id == "q05")
    assert "PASS" not in q05.failure_types
    actual_failures = [ft for ft in q05.failure_types if ft != "PASS"]
    assert len(actual_failures) > 0
    assert "UNSUPPORTED_CLAIM" in actual_failures


def test_format_run_response_populates_questions():
    """Verify _format_run_response attaches question text to all items."""
    with open(SAMPLE_DATA_DIR / "dataset.json", encoding="utf-8") as f:
        dataset = Dataset.model_validate(json.load(f))
    with open(SAMPLE_DATA_DIR / "submission.json", encoding="utf-8") as f:
        submission = Submission.model_validate(json.load(f))

    run_result = evaluate_run(dataset, submission)
    formatted = _format_run_response(run_result, dataset)

    assert "items" in formatted
    for item in formatted["items"]:
        assert item["question"] is not None
        assert len(item["question"]) > 0
        real_failures = [ft for ft in item["failure_types"] if ft != "PASS"]
        if item["item_id"] == "q01":
            assert len(real_failures) == 0
