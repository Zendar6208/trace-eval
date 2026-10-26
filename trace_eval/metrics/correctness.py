"""Deterministic answer correctness metrics (Tier 0) conforming to Methodology Section 3.

Metrics implemented:
- Normalized containment of required facts.
- Alias-based required fact matching.
- SQuAD-style token F1 against reference answers.
- Rule-based refusal detection for unanswerable items.
- Deterministic verdicts ('correct', 'partial', 'incorrect').

Independence contract:
Correctness reads ONLY the answer text (markers stripped), gold reference answers,
and required facts. It NEVER reads retrieved passages, passage order, or citations.
"""

from __future__ import annotations

import collections
from collections.abc import Sequence
from typing import Any

from trace_eval.refusal import is_refusal
from trace_eval.schema.dataset import RequiredFact
from trace_eval.text_norm import normalize_for_matching, tokenize


def compute_token_f1_single(prediction: str, reference: str) -> float:
    """Compute SQuAD-style multiset token F1 score between prediction and reference."""
    pred_tokens = tokenize(prediction)
    ref_tokens = tokenize(reference)

    if not pred_tokens and not ref_tokens:
        return 1.0
    if not pred_tokens or not ref_tokens:
        return 0.0

    common = collections.Counter(pred_tokens) & collections.Counter(ref_tokens)
    num_same = sum(common.values())

    if num_same == 0:
        return 0.0

    precision = num_same / len(pred_tokens)
    recall = num_same / len(ref_tokens)
    f1 = (2.0 * precision * recall) / (precision + recall)
    return round(f1, 6)


def compute_token_f1(prediction: str, references: Sequence[str]) -> float:
    """Compute max token F1 over all gold reference answers."""
    if not references:
        return 0.0
    return max(compute_token_f1_single(prediction, ref) for ref in references)


def match_required_facts(
    answer: str,
    required_facts: Sequence[RequiredFact],
) -> tuple[float, list[dict[str, Any]]]:
    """Match required facts against answer using normalized text and aliases.

    Returns:
        (fact_recall: float, fact_details: list[dict])
    """
    if not required_facts:
        return 1.0, []

    norm_answer = normalize_for_matching(answer)
    matched_count = 0
    fact_details: list[dict[str, Any]] = []

    for fact in required_facts:
        norm_fact_text = normalize_for_matching(fact.text)
        matched = False
        method = "unmatched"
        matched_alias = None

        # 1. Primary fact text normalized containment
        if norm_fact_text in norm_answer:
            matched = True
            method = "normalized_containment"
        else:
            # 2. Alias normalized containment
            for alias in fact.aliases:
                norm_alias = normalize_for_matching(alias)
                if norm_alias and norm_alias in norm_answer:
                    matched = True
                    method = "alias_containment"
                    matched_alias = alias
                    break

        if matched:
            matched_count += 1

        fact_details.append(
            {
                "fact_id": fact.fact_id,
                "text": fact.text,
                "matched": matched,
                "method": method,
                "matched_alias": matched_alias,
            }
        )

    fact_recall = round(matched_count / len(required_facts), 6)
    return fact_recall, fact_details


def evaluate_correctness(
    answer: str,
    reference_answers: Sequence[str],
    required_facts: Sequence[RequiredFact],
    unanswerable: bool = False,
) -> dict[str, Any]:
    """Evaluate Tier-0 answer correctness per Methodology Section 3.

    Verdict logic:
    - For unanswerable items: 'correct' iff the answer is a refusal; else 'incorrect'.
    - For answerable items:
      - 'correct' if all required facts matched (fact_recall == 1.0) and no contradiction.
      - 'partial' if some required facts matched (0 < fact_recall < 1.0) and no contradiction.
      - 'incorrect' if no required facts matched (fact_recall == 0.0).
      - If no required facts specified: falls back to token F1 threshold (>= 0.8 correct, >= 0.4 partial).
    """
    answer_is_refusal = is_refusal(answer)

    if unanswerable:
        # For unanswerable items, correct if and only if the answer is a refusal
        verdict = "correct" if answer_is_refusal else "incorrect"
        token_f1 = 1.0 if answer_is_refusal else 0.0
        return {
            "fact_recall": 1.0 if answer_is_refusal else 0.0,
            "token_f1": token_f1,
            "contradicts_reference": False,
            "verdict": verdict,
            "is_refusal": answer_is_refusal,
            "fact_details": [],
        }

    # Answerable query
    if answer_is_refusal:
        # A refusal on an answerable query is incorrect (FALSE_REFUSAL)
        return {
            "fact_recall": 0.0,
            "token_f1": 0.0,
            "contradicts_reference": False,
            "verdict": "incorrect",
            "is_refusal": True,
            "fact_details": [],
        }

    # Match facts and compute token F1
    token_f1 = compute_token_f1(answer, reference_answers)
    fact_recall, fact_details = match_required_facts(answer, required_facts)

    if required_facts:
        if fact_recall == 1.0:
            verdict = "correct"
        elif fact_recall > 0.0:
            verdict = "partial"
        else:
            verdict = "incorrect"
    else:
        # Fallback to token F1 when no atomic facts provided
        if token_f1 >= 0.8:
            verdict = "correct"
        elif token_f1 >= 0.4:
            verdict = "partial"
        else:
            verdict = "incorrect"

    return {
        "fact_recall": fact_recall,
        "token_f1": token_f1,
        "contradicts_reference": False,
        "verdict": verdict,
        "is_refusal": False,
        "fact_details": fact_details,
    }
