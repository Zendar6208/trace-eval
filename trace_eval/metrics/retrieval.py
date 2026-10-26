"""Deterministic retrieval metrics (Tier 0) conforming to Methodology Section 3.

Metrics implemented:
- hit@k
- recall@k
- precision@k
- Mean Reciprocal Rank (MRR)
- nDCG@k with graded relevance gains (1-3)

Independence contract:
Retrieval metrics read ONLY retrieved items (order, IDs, optional text) and gold passages.
They NEVER read the answer text or citations.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from trace_eval.text_norm import tokenize


def _compute_token_overlap(text1: str, text2: str) -> float:
    """Compute token recall/overlap of text1 against text2."""
    tokens1 = set(tokenize(text1))
    tokens2 = set(tokenize(text2))
    if not tokens1 or not tokens2:
        return 0.0
    common = tokens1 & tokens2
    # overlap ratio relative to gold passage text tokens
    return len(common) / len(tokens2)


def compute_hit_at_k(
    retrieved_ids: Sequence[str],
    gold_ids: set[str],
    k: int,
) -> float:
    """Compute hit@k: 1.0 if any gold passage appears in the top-k retrieved list, else 0.0."""
    if not gold_ids or k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    return 1.0 if any(pid in gold_ids for pid in top_k) else 0.0


def compute_recall_at_k(
    retrieved_ids: Sequence[str],
    gold_ids: set[str],
    k: int,
) -> float:
    """Compute recall@k: fraction of gold passages retrieved in top-k."""
    if not gold_ids or k <= 0:
        return 0.0
    top_k = set(retrieved_ids[:k])
    matched = top_k & gold_ids
    return round(len(matched) / len(gold_ids), 6)


def compute_precision_at_k(
    retrieved_ids: Sequence[str],
    gold_ids: set[str],
    k: int,
) -> float:
    """Compute precision@k: fraction of top-k retrieved passages that are gold."""
    if k <= 0:
        return 0.0
    top_k = set(retrieved_ids[:k])
    matched = top_k & gold_ids
    return round(len(matched) / k, 6)


def compute_mrr(
    retrieved_ids: Sequence[str],
    gold_ids: set[str],
) -> float:
    """Compute Reciprocal Rank: 1 / rank of the first relevant passage, or 0.0 if none retrieved."""
    if not gold_ids:
        return 0.0
    for idx, pid in enumerate(retrieved_ids, start=1):
        if pid in gold_ids:
            return round(1.0 / idx, 6)
    return 0.0


def compute_ndcg_at_k(
    retrieved_ids: Sequence[str],
    relevance_map: dict[str, int],
    k: int,
) -> float:
    """Compute nDCG@k using standard graded relevance gains (2^rel - 1) / log2(i + 1).

    Args:
        retrieved_ids: Ranked list of retrieved passage IDs.
        relevance_map: Mapping of passage_id to graded relevance score (1-3).
        k: Cutoff rank.

    Returns:
        nDCG@k score in [0.0, 1.0], rounded to 6 decimal places.
    """
    if not relevance_map or k <= 0:
        return 0.0

    # Calculate DCG@k
    dcg = 0.0
    top_k = retrieved_ids[:k]
    for i, pid in enumerate(top_k, start=1):
        rel = relevance_map.get(pid, 0)
        if rel > 0:
            gain = (2**rel) - 1
            discount = math.log2(i + 1)
            dcg += gain / discount

    # Calculate Ideal DCG@k (IDCG@k)
    ideal_relevances = sorted(relevance_map.values(), reverse=True)[:k]
    idcg = 0.0
    for i, rel in enumerate(ideal_relevances, start=1):
        if rel > 0:
            gain = (2**rel) - 1
            discount = math.log2(i + 1)
            idcg += gain / discount

    if idcg == 0.0:
        return 0.0

    return round(dcg / idcg, 6)


def evaluate_retrieval(
    retrieved_ids: Sequence[str],
    gold_relevance_map: dict[str, int],
    cutoffs: Sequence[int] = (1, 3, 5, 10),
    retrieved_texts: dict[str, str] | None = None,
    gold_texts: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Compute the full Tier-0 retrieval metrics suite for an evaluated item.

    Returns None if the item has no gold passages (excluded from retrieval reporting).
    """
    if not gold_relevance_map:
        return None

    # Fallback token overlap resolution per Section 3:
    # If retrieved passage text is available and matches gold text >= 0.8, treat as matched.
    effective_relevance = dict(gold_relevance_map)
    effective_ids: list[str] = list(retrieved_ids)

    if retrieved_texts and gold_texts:
        for r_id in effective_ids:
            if r_id not in effective_relevance and r_id in retrieved_texts:
                r_text = retrieved_texts[r_id]
                for g_id, g_text in gold_texts.items():
                    if _compute_token_overlap(r_text, g_text) >= 0.8:
                        # Inherit gold relevance for this retrieved ID
                        effective_relevance[r_id] = gold_relevance_map.get(g_id, 3)
                        break

    gold_id_set = set(effective_relevance.keys())

    hit_at_k: dict[str, float] = {}
    recall_at_k: dict[str, float] = {}
    precision_at_k: dict[str, float] = {}
    ndcg_at_k: dict[str, float] = {}

    for k in cutoffs:
        str_k = str(k)
        hit_at_k[str_k] = compute_hit_at_k(effective_ids, gold_id_set, k)
        recall_at_k[str_k] = compute_recall_at_k(effective_ids, gold_id_set, k)
        precision_at_k[str_k] = compute_precision_at_k(effective_ids, gold_id_set, k)
        ndcg_at_k[str_k] = compute_ndcg_at_k(effective_ids, effective_relevance, k)

    mrr = compute_mrr(effective_ids, gold_id_set)

    return {
        "hit_at_k": hit_at_k,
        "recall_at_k": recall_at_k,
        "precision_at_k": precision_at_k,
        "mrr": mrr,
        "ndcg_at_k": ndcg_at_k,
    }
