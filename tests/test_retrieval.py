"""Tests for Tier-0 retrieval metrics (hit@k, recall@k, precision@k, MRR, nDCG@k)."""

from trace_eval.metrics.retrieval import (
    compute_hit_at_k,
    compute_mrr,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_recall_at_k,
    evaluate_retrieval,
)


def test_perfect_retrieval():
    """Gold passages retrieved at the top ranks."""
    retrieved = ["p01", "p02", "p03", "p04"]
    gold_map = {"p01": 3, "p02": 3}
    gold_set = set(gold_map.keys())

    assert compute_hit_at_k(retrieved, gold_set, k=1) == 1.0
    assert compute_recall_at_k(retrieved, gold_set, k=2) == 1.0
    assert compute_precision_at_k(retrieved, gold_set, k=2) == 1.0
    assert compute_mrr(retrieved, gold_set) == 1.0
    assert compute_ndcg_at_k(retrieved, gold_map, k=2) == 1.0


def test_irrelevant_retrieval():
    """No gold passages retrieved."""
    retrieved = ["p99", "p98", "p97"]
    gold_map = {"p01": 3, "p02": 3}
    gold_set = set(gold_map.keys())

    assert compute_hit_at_k(retrieved, gold_set, k=3) == 0.0
    assert compute_recall_at_k(retrieved, gold_set, k=3) == 0.0
    assert compute_precision_at_k(retrieved, gold_set, k=3) == 0.0
    assert compute_mrr(retrieved, gold_set) == 0.0
    assert compute_ndcg_at_k(retrieved, gold_map, k=3) == 0.0


def test_mixed_relevance_and_ndcg_grading():
    """Graded relevance: p01 (rel=3), p02 (rel=2), p03 (rel=1)."""
    # Ideal order: p01, p02, p03
    retrieved_ideal = ["p01", "p02", "p03"]
    gold_map = {"p01": 3, "p02": 2, "p03": 1}

    ndcg_ideal = compute_ndcg_at_k(retrieved_ideal, gold_map, k=3)
    assert ndcg_ideal == 1.0

    # Suboptimal order: p03 (rel=1), p02 (rel=2), p01 (rel=3)
    retrieved_suboptimal = ["p03", "p02", "p01"]
    ndcg_sub = compute_ndcg_at_k(retrieved_suboptimal, gold_map, k=3)
    assert 0.0 < ndcg_sub < 1.0
    assert ndcg_sub < ndcg_ideal


def test_incorrect_retrieval_order():
    """Gold passage appears late in ranking, lowering MRR."""
    retrieved = ["p_noise1", "p_noise2", "p_gold"]
    gold_set = {"p_gold"}
    # Gold at rank 3 -> MRR = 1/3 = 0.333333
    assert compute_mrr(retrieved, gold_set) == 0.333333


def test_evaluate_retrieval_full_suite():
    retrieved = ["p01", "p03", "p02"]
    gold_map = {"p01": 3, "p02": 2}

    res = evaluate_retrieval(retrieved, gold_map, cutoffs=(1, 2, 3))
    assert res is not None
    assert res["hit_at_k"]["1"] == 1.0
    assert res["recall_at_k"]["1"] == 0.5
    assert res["recall_at_k"]["3"] == 1.0
    assert res["mrr"] == 1.0


def test_evaluate_retrieval_no_gold_passages():
    """Items without gold passages return None per Section 3."""
    res = evaluate_retrieval(["p01", "p02"], {})
    assert res is None


def test_fallback_token_overlap():
    """Retrieved passage with unknown ID matches gold if token overlap >= 0.8."""
    retrieved_ids = ["p_custom_chunk"]
    gold_map = {"p_gold": 3}
    gold_texts = {"p_gold": "Refunds are processed within 30 business days of initial request."}
    retrieved_texts = {
        "p_custom_chunk": "Refunds are processed within 30 business days of initial request."
    }

    res = evaluate_retrieval(
        retrieved_ids=retrieved_ids,
        gold_relevance_map=gold_map,
        cutoffs=(1,),
        retrieved_texts=retrieved_texts,
        gold_texts=gold_texts,
    )
    assert res is not None
    assert res["hit_at_k"]["1"] == 1.0
    assert res["mrr"] == 1.0
