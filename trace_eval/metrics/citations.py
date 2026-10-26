"""Citation evaluation metrics conforming to Methodology Sections 2.4, 2.5, and 3.

Methodology requirements:
- CA-6: Each unit is evaluated against cited passage only. Sentence is supported if >= 1 unit supports it.
- CA-7: Anything other than ok is non-supporting.
- CA-4: Orphan citations (sentence_index = None) are non-supporting and count in precision denominator.
- citation_precision: supporting units / all units (null if no units or NLI not run).
- citation_recall: citation-supported claim sentences / all claim sentences (0.0 if require_citations: true and no citations; null if require_citations: false or NLI not run).
- phantom_rate: non-ok units / all units (null if no units).
- uncited_claim_rate: fraction of assessable claim sentences lacking citations.
- cites_gold: diagnostic whether any cited unit points to a gold passage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trace_eval.citations import ParsedCitationUnit
from trace_eval.claims import RawSentence
from trace_eval.nli import extract_premise_windows
from trace_eval.schema.run import CitationMetrics

if TYPE_CHECKING:
    from trace_eval.nli import NLIEvaluator


def evaluate_citations(
    units: list[ParsedCitationUnit],
    sentences: list[RawSentence],
    retrieved_texts: dict[str, str],
    gold_passage_ids: set[str],
    require_citations: bool = True,
    nli_evaluator: NLIEvaluator | None = None,
    entail_threshold: float = 0.8,
    window_sentences: int = 3,
) -> tuple[CitationMetrics, list[ParsedCitationUnit]]:
    """Evaluate citation validity, support, and aggregate metrics for an answer."""
    # Section 2.5: require_citations: false means citation metrics are null (not applicable)
    if not require_citations:
        return (
            CitationMetrics(
                citation_precision=None,
                citation_recall=None,
                phantom_rate=None,
                uncited_claim_rate=None,
                cites_gold=None,
            ),
            units,
        )

    # 1. Evaluate individual unit support
    sentences_by_idx = {s.index: s for s in sentences}

    for unit in units:
        # CA-4 and CA-7: non-ok and orphan units are strictly non-supporting
        if unit.validity != "ok" or unit.sentence_index is None:
            unit.supports = False
            unit.entail_prob = None
            unit.best_window = None
            continue

        passage_text = retrieved_texts.get(unit.passage_id, "")
        attached_sentence = sentences_by_idx.get(unit.sentence_index)
        if not passage_text or not attached_sentence:
            unit.supports = False
            unit.entail_prob = None
            unit.best_window = None
            continue

        if nli_evaluator is not None:
            windows = extract_premise_windows(passage_text, window_sentences=window_sentences)
            pairs = [(win, attached_sentence.clean_text) for win in windows]
            preds = nli_evaluator.predict(pairs)

            if preds:
                best_idx = max(range(len(preds)), key=lambda i: preds[i].entailment)
                best_prob = preds[best_idx].entailment
                unit.entail_prob = best_prob
                unit.best_window = windows[best_idx]
                unit.supports = best_prob >= entail_threshold
            else:
                unit.supports = False
                unit.entail_prob = 0.0
        else:
            # Deterministic Tier 0 mode without NLI model
            unit.supports = False
            unit.entail_prob = None

    # 2. Compute aggregate citation metrics
    total_units = len(units)
    claim_sentences = [s for s in sentences if s.is_claim]
    assessable_claims = [s for s in sentences if s.is_assessable]

    # Citation Precision (Tier 1 requires NLI)
    if nli_evaluator is None:
        precision = None
    elif total_units == 0:
        precision = None
    else:
        supporting_units = sum(1 for u in units if u.supports)
        precision = round(supporting_units / total_units, 6)

    # Citation Recall (Tier 1 requires NLI)
    if nli_evaluator is None:
        recall = None
    elif not claim_sentences:
        recall = None
    elif total_units == 0:
        # Section 2.5: require_citations: true and no citations -> recall is 0, precision is null
        recall = 0.0
    else:
        supported_indices = {
            u.sentence_index for u in units if u.supports and u.sentence_index is not None
        }
        supported_claims_count = sum(1 for s in claim_sentences if s.index in supported_indices)
        recall = round(supported_claims_count / len(claim_sentences), 6)

    # Phantom Rate (Tier 0 deterministic)
    if total_units == 0:
        phantom_rate = None
    else:
        non_ok_count = sum(1 for u in units if u.validity != "ok")
        phantom_rate = round(non_ok_count / total_units, 6)

    # Uncited Claim Rate (Tier 0 deterministic)
    if not assessable_claims:
        uncited_claim_rate = None
    else:
        cited_indices = {u.sentence_index for u in units if u.sentence_index is not None}
        uncited_count = sum(1 for s in assessable_claims if s.index not in cited_indices)
        uncited_claim_rate = round(uncited_count / len(assessable_claims), 6)

    # Cites Gold Diagnostic (Tier 0 deterministic)
    cites_gold = any(u.passage_id in gold_passage_ids for u in units) if total_units > 0 else False

    return (
        CitationMetrics(
            citation_precision=precision,
            citation_recall=recall,
            phantom_rate=phantom_rate,
            uncited_claim_rate=uncited_claim_rate,
            cites_gold=cites_gold,
        ),
        units,
    )
