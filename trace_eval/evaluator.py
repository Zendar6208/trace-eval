"""Deterministic Tier-0 evaluation engine for TRACE AI (Milestone M1).

Orchestrates:
- Metric independence: retrieval evaluates only retrieval list and gold; correctness evaluates only answer and facts.
- Tier-0 retrieval metrics: hit@k, recall@k, precision@k, MRR, nDCG@k.
- Tier-0 correctness metrics: fact recall, token F1, refusal detection, verdicts.
- Deterministic failure type assignment:
  - RETRIEVAL_MISS: gold passages exist, but hit@k (k=max) is 0.0
  - WRONG_ANSWER: verdict is 'incorrect' for an answerable query
  - ANSWERED_UNANSWERABLE: unanswerable query answered without refusal
  - FALSE_REFUSAL: answerable query met with a refusal
  - PASS: assigned if and only if no other failure type applies
- Summary aggregation stratified by origin (recorded_system, synthetic_fixture, combined).
- Automated cryptographic result hashing and run_id derivation.
"""

from __future__ import annotations

import collections
from collections.abc import Sequence

from trace_eval.hashing import compute_run_hashes, hash_dataset, hash_submission
from trace_eval.metrics.correctness import evaluate_correctness
from trace_eval.metrics.retrieval import evaluate_retrieval
from trace_eval.schema.dataset import Dataset, DatasetItem
from trace_eval.schema.run import (
    AggregateMetrics,
    CorrectnessMetrics,
    FailureType,
    InputOriginSummary,
    ItemMetrics,
    RetrievalMetrics,
    RunConfig,
    RunItemResult,
    RunResult,
    RunSummary,
    RunThresholds,
)
from trace_eval.schema.submission import Submission, SubmissionOutput
from trace_eval.validation import validate_submission_against_dataset


def evaluate_item(
    item: DatasetItem,
    output: SubmissionOutput,
    cutoffs: Sequence[int] = (1, 3, 5, 10),
    gold_texts: dict[str, str] | None = None,
) -> RunItemResult:
    """Evaluate a single benchmark item and submission output using Tier-0 deterministic rules.

    Maintains strict metric independence:
    - Retrieval evaluation reads only output.retrieved and item gold data.
    - Correctness evaluation reads only output.answer, item.reference_answers, and item.required_facts.
    """
    # 1. Retrieval Metrics
    gold_rel_map = item.get_gold_relevance_map()
    retrieved_ids = [p.id for p in output.retrieved]
    retrieved_texts = {p.id: p.text for p in output.retrieved if p.text is not None}

    retrieval_res = evaluate_retrieval(
        retrieved_ids=retrieved_ids,
        gold_relevance_map=gold_rel_map,
        cutoffs=cutoffs,
        retrieved_texts=retrieved_texts,
        gold_texts=gold_texts,
    )
    retrieval_metrics = RetrievalMetrics(**retrieval_res) if retrieval_res is not None else None

    # 2. Correctness Metrics
    correctness_res = evaluate_correctness(
        answer=output.answer,
        reference_answers=item.reference_answers,
        required_facts=item.required_facts,
        unanswerable=item.unanswerable,
    )
    correctness_metrics = CorrectnessMetrics(
        fact_recall=correctness_res["fact_recall"],
        token_f1=correctness_res["token_f1"],
        contradicts_reference=correctness_res["contradicts_reference"],
        verdict=correctness_res["verdict"],
    )

    # 3. Deterministic Failure Type Assignment
    failure_types: list[FailureType] = []

    # Check unanswerable handling
    if item.unanswerable:
        if not correctness_res["is_refusal"]:
            failure_types.append("ANSWERED_UNANSWERABLE")
    else:
        # Answerable query
        if correctness_res["is_refusal"]:
            failure_types.append("FALSE_REFUSAL")
        elif correctness_metrics.verdict == "incorrect":
            failure_types.append("WRONG_ANSWER")

    # Check retrieval miss: gold passages exist, but no gold passage was retrieved
    if gold_rel_map and retrieved_ids:
        max_k = max(cutoffs)
        hit_max = retrieval_metrics.hit_at_k.get(str(max_k), 0.0) if retrieval_metrics else 0.0
        if hit_max == 0.0:
            failure_types.append("RETRIEVAL_MISS")
    elif gold_rel_map and not retrieved_ids:
        failure_types.append("RETRIEVAL_MISS")

    if not failure_types:
        failure_types.append("PASS")

    return RunItemResult(
        item_id=item.id,
        origin=output.origin,
        metrics=ItemMetrics(
            retrieval=retrieval_metrics,
            correctness=correctness_metrics,
            citation=None,
            grounding=None,
        ),
        failure_types=failure_types,
        evidence=None,
    )


def _compute_aggregate(items: list[RunItemResult]) -> AggregateMetrics:
    """Compute aggregate averages for a subset of evaluated items."""
    count = len(items)
    if count == 0:
        return AggregateMetrics(count=0)

    token_f1s = [
        it.metrics.correctness.token_f1
        for it in items
        if it.metrics.correctness and it.metrics.correctness.token_f1 is not None
    ]
    fact_recalls = [
        it.metrics.correctness.fact_recall
        for it in items
        if it.metrics.correctness and it.metrics.correctness.fact_recall is not None
    ]
    correct_count = sum(
        1 for it in items if it.metrics.correctness and it.metrics.correctness.verdict == "correct"
    )

    mean_f1 = round(sum(token_f1s) / len(token_f1s), 6) if token_f1s else None
    mean_recall = round(sum(fact_recalls) / len(fact_recalls), 6) if fact_recalls else None
    accuracy = round(correct_count / count, 6)

    return AggregateMetrics(
        count=count,
        mean_token_f1=mean_f1,
        mean_fact_recall=mean_recall,
        accuracy=accuracy,
    )


def evaluate_run(
    dataset: Dataset,
    submission: Submission,
    config: RunConfig | None = None,
) -> RunResult:
    """Run full deterministic Tier-0 evaluation across all items in a submission.

    Validates inputs, executes item evaluations, aggregates stratified summaries,
    computes deterministic result_hash and run_id, and returns a verified RunResult.
    """
    # 1. Referential integrity check
    errors = validate_submission_against_dataset(dataset, submission)
    if errors:
        raise ValueError("Submission does not match dataset:\n" + "\n".join(errors))

    # 2. Default config if not supplied
    if config is None:
        config = RunConfig(
            thresholds=RunThresholds(entail=0.8, contradict=0.7),
            citation_style="id",
            phantom_mode="bracket",
            require_citations=True,
        )

    # Index dataset corpus texts and items
    gold_texts = {p.id: p.text for p in dataset.corpus}
    dataset_items_map = {item.id: item for item in dataset.items}

    # 3. Item evaluations
    evaluated_items: list[RunItemResult] = []
    failure_counts: collections.Counter[str] = collections.Counter()

    for output in submission.outputs:
        item = dataset_items_map[output.item_id]
        res = evaluate_item(item, output, gold_texts=gold_texts)
        evaluated_items.append(res)
        for ft in res.failure_types:
            failure_counts[ft] += 1

    # 4. Stratified Summaries per Section 1 reporting rule
    rec_items = [it for it in evaluated_items if it.origin == "recorded_system"]
    syn_items = [it for it in evaluated_items if it.origin == "synthetic_fixture"]

    summary = RunSummary(
        recorded_system=_compute_aggregate(rec_items) if rec_items else None,
        synthetic_fixture=_compute_aggregate(syn_items) if syn_items else None,
        combined=_compute_aggregate(evaluated_items),
        failure_distribution=dict(failure_counts),
    )

    origin_summary = InputOriginSummary(
        recorded_system_count=len(rec_items),
        synthetic_fixture_count=len(syn_items),
        total_count=len(evaluated_items),
    )

    # 5. Build core run result and compute hashes
    draft_run_dict = {
        "schema_version": "trace.run/1.0",
        "methodology_version": "1.0.0",
        "dataset": {
            "id": dataset.dataset_id,
            "content_sha256": hash_dataset(dataset),
        },
        "submission_content_sha256": hash_submission(submission),
        "config": config.model_dump(mode="json"),
        "summary": summary.model_dump(mode="json"),
        "items": [it.model_dump(mode="json") for it in evaluated_items],
        "run_id": None,
        "result_hash": None,
        "runtime_status": "live",
        "environment": None,
        "system": submission.system.model_dump(mode="json"),
        "input_origin_summary": origin_summary.model_dump(mode="json"),
    }

    result_hash, run_id = compute_run_hashes(draft_run_dict)
    draft_run_dict["result_hash"] = result_hash
    draft_run_dict["run_id"] = run_id

    return RunResult.model_validate(draft_run_dict)
