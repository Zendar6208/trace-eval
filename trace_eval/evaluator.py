"""Deterministic Tier-0 and Tier-1 evaluation engine for TRACE AI (Milestones M1 and M2).

Orchestrates:
- Metric independence:
  - Retrieval evaluates only retrieval list and gold passages.
  - Correctness evaluates only cleaned answer and reference facts.
  - Citation evaluates answer markers, cited passage text, and retrieved IDs for validity.
  - Grounding evaluates answer sentences and all retrieved passages.
- Tier-0 retrieval metrics: hit@k, recall@k, precision@k, MRR, nDCG@k.
- Tier-0 correctness metrics: fact recall, token F1, refusal detection, verdicts.
- Citation metrics: precision, recall, phantom rate, uncited claim rate, cites_gold diagnostic.
- Grounding metrics: unsupported claim rate, is_unsupported_answer, Tier-0 numeric guard.
- Deterministic multi-label failure types:
  - RETRIEVAL_MISS
  - WRONG_ANSWER
  - UNSUPPORTED_CLAIM
  - UNCITED_CLAIM
  - BAD_CITATION
  - ANSWERED_UNANSWERABLE
  - FALSE_REFUSAL
  - PASS (assigned if and only if no other failure type applies)
- Summary aggregation stratified by origin (recorded_system, synthetic_fixture, combined).
- Automated cryptographic result hashing and run_id derivation.
"""

from __future__ import annotations

import collections
from collections.abc import Sequence

from trace_eval.citations import parse_and_attach_citations, strip_citation_markers
from trace_eval.hashing import compute_run_hashes, hash_dataset, hash_submission
from trace_eval.metrics.citations import evaluate_citations
from trace_eval.metrics.correctness import evaluate_correctness
from trace_eval.metrics.grounding import evaluate_grounding
from trace_eval.metrics.retrieval import evaluate_retrieval
from trace_eval.nli import NLIEvaluator
from trace_eval.schema.dataset import Dataset, DatasetItem
from trace_eval.schema.run import (
    AggregateMetrics,
    CorrectnessMetrics,
    FailureType,
    InputOriginSummary,
    ItemMetrics,
    RetrievalMetrics,
    RunConfig,
    RunItemEvidence,
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
    config: RunConfig | None = None,
    nli_evaluator: NLIEvaluator | None = None,
) -> RunItemResult:
    """Evaluate a single benchmark item and submission output using Tier-0/1 rules."""
    if config is None:
        config = RunConfig(
            thresholds=RunThresholds(entail=0.8, contradict=0.7),
            citation_style="id",
            phantom_mode="bracket",
            require_citations=True,
        )

    # Resolve retrieved texts (from submission or dataset corpus)
    gold_rel_map = item.get_gold_relevance_map()
    retrieved_ids = [p.id for p in output.retrieved]
    retrieved_texts: dict[str, str] = {}
    for p in output.retrieved:
        if p.text is not None:
            retrieved_texts[p.id] = p.text
        elif gold_texts and p.id in gold_texts:
            retrieved_texts[p.id] = gold_texts[p.id]

    # 1. Retrieval Metrics
    retrieval_res = evaluate_retrieval(
        retrieved_ids=retrieved_ids,
        gold_relevance_map=gold_rel_map,
        cutoffs=cutoffs,
        retrieved_texts=retrieved_texts,
        gold_texts=gold_texts,
    )
    retrieval_metrics = RetrievalMetrics(**retrieval_res) if retrieval_res is not None else None

    # 2. Citation Parsing & Attachment (CA-1 to CA-8)
    corpus_ids = set(gold_texts.keys()) if gold_texts else set()
    citation_res = parse_and_attach_citations(
        output.answer,
        retrieved_ids=retrieved_ids,
        corpus_ids=corpus_ids,
        citation_style=config.citation_style,
        phantom_mode=config.phantom_mode,
    )
    sentences = citation_res.sentences
    parsed_units = citation_res.units

    # 3. Citation Evaluation
    gold_ids = set(gold_rel_map.keys())
    citation_metrics, evaluated_units = evaluate_citations(
        units=parsed_units,
        sentences=sentences,
        retrieved_texts=retrieved_texts,
        gold_passage_ids=gold_ids,
        require_citations=config.require_citations,
        nli_evaluator=nli_evaluator,
        entail_threshold=config.thresholds.entail,
        window_sentences=config.window_sentences,
    )

    # 4. Correctness Metrics (CA-8: evaluated on marker-stripped text)
    clean_answer = strip_citation_markers(
        output.answer,
        citation_style=config.citation_style,
        phantom_mode=config.phantom_mode,
        retrieved_ids=retrieved_ids,
        corpus_ids=corpus_ids,
    )
    correctness_res = evaluate_correctness(
        answer=clean_answer,
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

    # 5. Grounding Evaluation
    retrieved_texts_list = [retrieved_texts[pid] for pid in retrieved_ids if pid in retrieved_texts]
    grounding_metrics, claim_evidences = evaluate_grounding(
        sentences=sentences,
        retrieved_texts=retrieved_texts_list,
        unanswerable=item.unanswerable,
        is_refusal=correctness_res["is_refusal"],
        nli_evaluator=nli_evaluator,
        entail_threshold=config.thresholds.entail,
        contradict_threshold=config.thresholds.contradict,
        window_sentences=config.window_sentences,
    )

    # 6. Detailed Item Evidence
    item_evidence = RunItemEvidence(
        claims=claim_evidences,
        citations=[u.to_evidence() for u in evaluated_units],
    )

    # 7. Deterministic Multi-Label Failure Type Assignment per Section 3
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

    # Check grounding failures
    if grounding_metrics.is_unsupported_answer:
        failure_types.append("UNSUPPORTED_CLAIM")

    # Check citation failures (only assigned when citations are required)
    if config.require_citations:
        if (
            citation_metrics.uncited_claim_rate is not None
            and citation_metrics.uncited_claim_rate > 0.0
        ):
            failure_types.append("UNCITED_CLAIM")

        # BAD_CITATION:
        # If NLI ran: check if any unit does not support or validity != ok
        # If NLI did not run: check if validity != ok or orphan
        if nli_evaluator is not None:
            has_bad_citation = any(
                (not u.supports) or (u.validity != "ok") for u in evaluated_units
            )
        else:
            has_bad_citation = any(
                (u.validity != "ok") or (u.sentence_index is None) for u in evaluated_units
            )
        if has_bad_citation:
            failure_types.append("BAD_CITATION")

    if not failure_types:
        failure_types.append("PASS")

    return RunItemResult(
        item_id=item.id,
        origin=output.origin,
        metrics=ItemMetrics(
            retrieval=retrieval_metrics,
            correctness=correctness_metrics,
            citation=citation_metrics,
            grounding=grounding_metrics,
        ),
        failure_types=failure_types,
        evidence=item_evidence,
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

    precisions = [
        it.metrics.citation.citation_precision
        for it in items
        if it.metrics.citation and it.metrics.citation.citation_precision is not None
    ]
    recalls = [
        it.metrics.citation.citation_recall
        for it in items
        if it.metrics.citation and it.metrics.citation.citation_recall is not None
    ]
    phantoms = [
        it.metrics.citation.phantom_rate
        for it in items
        if it.metrics.citation and it.metrics.citation.phantom_rate is not None
    ]
    unsupporteds = [
        it.metrics.grounding.unsupported_claim_rate
        for it in items
        if it.metrics.grounding and it.metrics.grounding.unsupported_claim_rate is not None
    ]

    mean_f1 = round(sum(token_f1s) / len(token_f1s), 6) if token_f1s else None
    mean_recall = round(sum(fact_recalls) / len(fact_recalls), 6) if fact_recalls else None
    accuracy = round(correct_count / count, 6)

    mean_prec = round(sum(precisions) / len(precisions), 6) if precisions else None
    mean_rec = round(sum(recalls) / len(recalls), 6) if recalls else None
    mean_ph = round(sum(phantoms) / len(phantoms), 6) if phantoms else None
    mean_unsup = round(sum(unsupporteds) / len(unsupporteds), 6) if unsupporteds else None

    return AggregateMetrics(
        count=count,
        mean_token_f1=mean_f1,
        mean_fact_recall=mean_recall,
        accuracy=accuracy,
        mean_citation_precision=mean_prec,
        mean_citation_recall=mean_rec,
        mean_phantom_rate=mean_ph,
        mean_unsupported_claim_rate=mean_unsup,
    )


def evaluate_run(
    dataset: Dataset,
    submission: Submission,
    config: RunConfig | None = None,
    nli_evaluator: NLIEvaluator | None = None,
) -> RunResult:
    """Run evaluation across all items in a submission."""
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

    # Initialize NLI model if configured and evaluator not supplied
    if nli_evaluator is None and config.nli_model is not None:
        try:
            nli_evaluator = NLIEvaluator(
                model_name=config.nli_model.model_name,
                revision=config.nli_model.revision,
                device=config.nli_model.device or "cpu",
                max_length=config.max_length,
                batch_size=config.batch_size,
                truncation_policy=config.truncation_policy,
                id2label_override=config.id2label if config.id2label else None,
                local_files_only=True,
            )
            # Sync id2label if config was empty
            if not config.id2label:
                config.id2label = nli_evaluator.get_id2label_dict()
        except Exception:
            # Fallback gracefully to Tier-0 evaluation without NLI
            nli_evaluator = None

    # Index dataset corpus texts and items
    gold_texts = {p.id: p.text for p in dataset.corpus}
    dataset_items_map = {item.id: item for item in dataset.items}

    # 3. Item evaluations
    evaluated_items: list[RunItemResult] = []
    failure_counts: collections.Counter[str] = collections.Counter()

    for output in submission.outputs:
        item = dataset_items_map[output.item_id]
        res = evaluate_item(
            item,
            output,
            gold_texts=gold_texts,
            config=config,
            nli_evaluator=nli_evaluator,
        )
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
