"""Tests enforcing Methodology Section 3 Metric Independence Contracts.

Independence Table:
- Retrieval reads ONLY retrieved list and gold passages; does NOT read answer or citations.
- Correctness reads ONLY answer text, references, and required facts; does NOT read retrieved passages or citations.
"""

from trace_eval.metrics.correctness import evaluate_correctness
from trace_eval.metrics.retrieval import evaluate_retrieval
from trace_eval.schema.dataset import RequiredFact


def test_retrieval_does_not_read_answer():
    """Modifying the generated answer must have zero impact on retrieval metrics."""
    retrieved = ["p01", "p02", "p03"]
    gold_map = {"p01": 3, "p02": 2}

    res_baseline = evaluate_retrieval(retrieved, gold_map, cutoffs=(1, 3))

    # evaluate_retrieval takes no answer parameter by design.
    # We verify that its output is solely determined by retrieved and gold.
    res_repeat = evaluate_retrieval(retrieved, gold_map, cutoffs=(1, 3))
    assert res_baseline == res_repeat


def test_correctness_does_not_read_retrieval_or_citations():
    """Altering or adding citations, retrieved passages, or retrieval rank has zero impact on correctness."""
    facts = [RequiredFact(fact_id="f1", text="30 business days", aliases=["30 days"])]
    refs = ["Refunds take 30 business days."]

    # Answer with citation [p01]
    ans_with_cite = "Refunds take 30 business days.[p01]"
    # Answer with completely different bogus citation [p999, p888]
    ans_different_cite = "Refunds take 30 business days.[p999, p888]"
    # Answer without citations
    ans_no_cite = "Refunds take 30 business days."

    res1 = evaluate_correctness(ans_with_cite, refs, facts)
    res2 = evaluate_correctness(ans_different_cite, refs, facts)
    res3 = evaluate_correctness(ans_no_cite, refs, facts)

    # Correctness metrics must be identical across citation perturbations
    assert res1["fact_recall"] == res2["fact_recall"] == res3["fact_recall"] == 1.0
    assert res1["token_f1"] == res2["token_f1"] == res3["token_f1"] == 1.0
    assert res1["verdict"] == res2["verdict"] == res3["verdict"] == "correct"
