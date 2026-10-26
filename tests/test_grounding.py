"""Unit tests for grounding evaluation, citation support, and failure types conforming to Methodology Section 3 & 4."""

from trace_eval.citations import parse_and_attach_citations
from trace_eval.evaluator import evaluate_item
from trace_eval.metrics.citations import evaluate_citations
from trace_eval.metrics.grounding import evaluate_grounding
from trace_eval.nli import NLIEvaluator
from trace_eval.schema.dataset import DatasetItem
from trace_eval.schema.run import RunConfig, RunThresholds
from trace_eval.schema.submission import SubmissionOutput


def get_real_nli():
    return NLIEvaluator(
        model_name="cross-encoder/nli-distilroberta-base",
        revision="b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
        device="cpu",
        local_files_only=True,
    )


def test_supported_claim_evaluation():
    nli = get_real_nli()
    retrieved_texts = ["Refund requests are processed within 30 business days of receipt."]
    answer = "Refund requests take 30 business days.[p01]"

    parse_res = parse_and_attach_citations(answer, retrieved_ids=["p01"])
    metrics, evidence = evaluate_grounding(
        sentences=parse_res.sentences,
        retrieved_texts=retrieved_texts,
        nli_evaluator=nli,
        entail_threshold=0.8,
    )

    assert len(evidence) == 1
    assert evidence[0].grounding_label == "supported"
    assert evidence[0].best_entail_prob is not None and evidence[0].best_entail_prob >= 0.8
    assert metrics.unsupported_claim_rate == 0.0
    assert metrics.is_unsupported_answer is False


def test_contradicted_claim_evaluation():
    nli = get_real_nli()
    retrieved_texts = ["Refund requests are strictly non-refundable under all circumstances."]
    answer = "All customers are entitled to complete cash refunds."

    parse_res = parse_and_attach_citations(answer, retrieved_ids=["p01"])
    metrics, evidence = evaluate_grounding(
        sentences=parse_res.sentences,
        retrieved_texts=retrieved_texts,
        nli_evaluator=nli,
        contradict_threshold=0.7,
    )

    assert len(evidence) == 1
    assert evidence[0].grounding_label == "contradicted"
    assert metrics.unsupported_claim_rate == 1.0
    assert metrics.is_unsupported_answer is True


def test_numeric_guard_caps_supported_claim():
    nli = get_real_nli()
    # Passage mentions 30 days
    retrieved_texts = ["Refund requests are processed within 30 business days of receipt."]
    # Answer claims 60 days
    answer = "Refund requests are processed within 60 business days of receipt."

    parse_res = parse_and_attach_citations(answer, retrieved_ids=["p01"])
    metrics, evidence = evaluate_grounding(
        sentences=parse_res.sentences,
        retrieved_texts=retrieved_texts,
        nli_evaluator=nli,
    )

    assert len(evidence) == 1
    assert evidence[0].numeric_guard_triggered is True
    # Capped at unsupported by Tier-0 numeric guard
    assert evidence[0].grounding_label == "unsupported"
    assert metrics.unsupported_claim_rate == 1.0
    assert metrics.is_unsupported_answer is True


def test_metric_independence_citation_vs_grounding():
    """Grounding reads ALL retrieved passages, while citation reads ONLY cited passage."""
    nli = get_real_nli()

    # Passage 1 supports fact A; Passage 2 supports fact B
    p1 = "Refund requests are processed within 30 business days of receipt."
    p2 = "Customers must provide a valid receipt to initiate a return."
    retrieved_texts = {"p01": p1, "p02": p2}

    # Answer cites only p01 for both sentences
    answer = "Refund requests take 30 business days.[p01] Customers must provide a receipt.[p01]"

    parse_res = parse_and_attach_citations(answer, retrieved_ids=["p01", "p02"])

    # 1. Citation evaluation:
    # Sentence 0 cites p01 -> supported by p01!
    # Sentence 1 cites p01 -> NOT supported by p01 (receipt requirement is in p02, not p01)!
    cit_metrics, cit_units = evaluate_citations(
        units=parse_res.units,
        sentences=parse_res.sentences,
        retrieved_texts=retrieved_texts,
        gold_passage_ids={"p01", "p02"},
        nli_evaluator=nli,
    )
    # Unit for sentence 0 supports, unit for sentence 1 does not support
    assert cit_units[0].supports is True
    assert cit_units[1].supports is False
    assert cit_metrics.citation_precision == 0.5

    # 2. Grounding evaluation:
    # Evaluates against ALL retrieved passages (p01 AND p02)!
    # Sentence 1 is supported by p02, even though it cited p01!
    gr_metrics, gr_evidence = evaluate_grounding(
        sentences=parse_res.sentences,
        retrieved_texts=list(retrieved_texts.values()),
        nli_evaluator=nli,
    )
    assert gr_evidence[0].grounding_label == "supported"
    assert gr_evidence[1].grounding_label == "supported"
    assert gr_metrics.unsupported_claim_rate == 0.0
    assert gr_metrics.is_unsupported_answer is False


def test_failure_types_assignment_with_bad_citation_and_unsupported_claim():
    nli = get_real_nli()
    item = DatasetItem(
        id="item_01",
        question="What is the refund timeline?",
        group_id="group_01",
        split="test",
        reference_answers=["30 business days."],
        required_facts=[{"fact_id": "f1", "text": "30 business days"}],
        gold_passage_ids=["p01"],
        unanswerable=False,
    )

    output = SubmissionOutput(
        item_id="item_01",
        origin="recorded_system",
        answer="Refunds take 30 business days.[p999] Also, we give free cars.",
        retrieved=[
            {
                "id": "p01",
                "text": "Refund requests are processed within 30 business days of receipt.",
            }
        ],
    )

    config = RunConfig(
        thresholds=RunThresholds(entail=0.8, contradict=0.7),
        require_citations=True,
    )

    result = evaluate_item(item, output, config=config, nli_evaluator=nli)

    # 1. p999 is unknown_id -> phantom citation -> BAD_CITATION
    assert "BAD_CITATION" in result.failure_types
    # 2. "Also, we give free cars." has no citation -> UNCITED_CLAIM
    assert "UNCITED_CLAIM" in result.failure_types
    # 3. "free cars" is unsupported by retrieved text -> UNSUPPORTED_CLAIM
    assert "UNSUPPORTED_CLAIM" in result.failure_types
    # 4. PASS is NOT assigned because failures occurred
    assert "PASS" not in result.failure_types
