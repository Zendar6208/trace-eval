"""TRACE AI deterministic evaluation metrics (Tier 0)."""

from trace_eval.metrics.correctness import (
    compute_token_f1,
    evaluate_correctness,
    match_required_facts,
)
from trace_eval.metrics.retrieval import (
    compute_hit_at_k,
    compute_mrr,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_recall_at_k,
    evaluate_retrieval,
)

__all__ = [
    # Retrieval
    "compute_hit_at_k",
    "compute_recall_at_k",
    "compute_precision_at_k",
    "compute_mrr",
    "compute_ndcg_at_k",
    "evaluate_retrieval",
    # Correctness
    "compute_token_f1",
    "match_required_facts",
    "evaluate_correctness",
]
