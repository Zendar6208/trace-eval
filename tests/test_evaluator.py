"""Tests for the end-to-end Tier-0 evaluator engine."""

import json
from pathlib import Path

from trace_eval.evaluator import evaluate_item, evaluate_run
from trace_eval.hashing import verify_run_hashes
from trace_eval.schema.dataset import Dataset
from trace_eval.schema.run import RunResult
from trace_eval.schema.submission import Submission, SubmissionOutput

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> dict:
    return json.loads((FIXTURES_DIR / filename).read_text(encoding="utf-8"))


def test_evaluate_item_pass():
    dataset = Dataset.model_validate(load_fixture("golden_dataset_m0_corrected.json"))
    item = dataset.items[0]

    output = SubmissionOutput(
        item_id=item.id,
        origin="recorded_system",
        answer="Refunds take 30 business days.[p01]",
        retrieved=[{"id": "p01", "score": 0.95}],
    )

    result = evaluate_item(item, output)
    assert result.item_id == item.id
    assert result.failure_types == ["PASS"]
    assert result.metrics.correctness.verdict == "correct"
    assert result.metrics.retrieval.hit_at_k["1"] == 1.0


def test_evaluate_item_retrieval_miss():
    dataset = Dataset.model_validate(load_fixture("golden_dataset_m0_corrected.json"))
    item = dataset.items[0]  # gold is p01

    output = SubmissionOutput(
        item_id=item.id,
        origin="recorded_system",
        answer="Refunds take 30 business days.[p01]",
        retrieved=[{"id": "p_irrelevant", "score": 0.95}],  # misses p01
    )

    result = evaluate_item(item, output)
    assert "RETRIEVAL_MISS" in result.failure_types
    # Answer text is correct, but retrieval failed
    assert result.metrics.correctness.verdict == "correct"


def test_evaluate_item_wrong_answer():
    dataset = Dataset.model_validate(load_fixture("golden_dataset_m0_corrected.json"))
    item = dataset.items[0]

    output = SubmissionOutput(
        item_id=item.id,
        origin="recorded_system",
        answer="I have no idea about refunds.",
        retrieved=[{"id": "p01", "score": 0.95}],
    )

    result = evaluate_item(item, output)
    assert "WRONG_ANSWER" in result.failure_types
    assert result.metrics.correctness.verdict == "incorrect"


def test_evaluate_item_answered_unanswerable():
    dataset = Dataset.model_validate(load_fixture("golden_dataset_m0_corrected.json"))
    item = dataset.items[0]
    item.unanswerable = True

    output = SubmissionOutput(
        item_id=item.id,
        origin="recorded_system",
        answer="Refunds take 30 business days.",  # Did not refuse!
        retrieved=[],
    )

    result = evaluate_item(item, output)
    assert "ANSWERED_UNANSWERABLE" in result.failure_types


def test_evaluate_run_full_lifecycle():
    dataset = Dataset.model_validate(load_fixture("golden_dataset_m0_corrected.json"))
    submission = Submission.model_validate(load_fixture("golden_submission.json"))

    run_result = evaluate_run(dataset, submission)

    assert isinstance(run_result, RunResult)
    assert run_result.schema_version == "trace.run/1.0"
    assert len(run_result.items) == 2
    assert run_result.summary.combined.count == 2
    assert run_result.summary.recorded_system is not None
    assert run_result.summary.synthetic_fixture is not None

    # Cryptographic integrity
    assert run_result.result_hash is not None
    assert run_result.run_id is not None
    assert len(run_result.result_hash) == 64
    assert len(run_result.run_id) == 16
    assert verify_run_hashes(run_result)
