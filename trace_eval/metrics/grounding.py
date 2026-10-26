"""Grounding evaluation metrics and claim evidence conforming to Methodology Section 3 & 2.5.

Methodology requirements:
- For each assessable claim sentence, evaluate against windows of all retrieved passages.
- Numeric guard (Tier 0): number or date in claim missing from all retrieved texts caps label at unsupported.
- Label supported if entail >= entail_threshold.
- Label contradicted if contradict >= contradict_threshold and contradict > entail.
- Else label unsupported.
- Non-assessable claims (< 3 word tokens) get label 'not_assessable' and are excluded from claim rates.
- unsupported_claim_rate: (unsupported + contradicted) / assessable claims.
- is_unsupported_answer: True if any assessable claim is not supported,
  or if unanswerable item was not refused.
- Tier 0 preservation: when NLI model is not run, claims are unassessed by NLI,
  preserving Tier 0 results without falsely marking unassessed claims as verified.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from trace_eval.claims import RawSentence
from trace_eval.nli import check_numeric_guard, extract_premise_windows
from trace_eval.schema.run import ClaimSentenceEvidence, GroundingMetrics

if TYPE_CHECKING:
    from trace_eval.nli import NLIEvaluator


def evaluate_grounding(
    sentences: Sequence[RawSentence],
    retrieved_texts: Sequence[str],
    unanswerable: bool = False,
    is_refusal: bool = False,
    nli_evaluator: NLIEvaluator | None = None,
    entail_threshold: float = 0.8,
    contradict_threshold: float = 0.7,
    window_sentences: int = 3,
) -> tuple[GroundingMetrics, list[ClaimSentenceEvidence]]:
    """Evaluate grounding of all claim sentences across all retrieved passages."""
    evidence_list: list[ClaimSentenceEvidence] = []
    claim_sentences = [s for s in sentences if s.is_claim]

    # Pre-extract premise windows from all retrieved passages
    all_windows: list[str] = []
    valid_texts = [t for t in retrieved_texts if t and t.strip()]
    for text in valid_texts:
        all_windows.extend(extract_premise_windows(text, window_sentences=window_sentences))

    unsupported_count = 0
    contradicted_count = 0
    assessable_count = 0
    any_num_guard_triggered = False

    for s in claim_sentences:
        if not s.is_assessable:
            evidence_list.append(
                ClaimSentenceEvidence(
                    sentence_index=s.index,
                    sentence_text=s.clean_text,
                    is_assessable=False,
                    grounding_label="not_assessable",
                    best_entail_prob=None,
                    best_contradict_prob=None,
                    numeric_guard_triggered=False,
                )
            )
            continue

        assessable_count += 1

        # Check Tier-0 Numeric Guard (only if retrieved passages exist)
        num_guard_triggered = False
        if valid_texts:
            num_guard_triggered = check_numeric_guard(s.clean_text, valid_texts)
            if num_guard_triggered:
                any_num_guard_triggered = True

        best_entail: float | None = None
        best_contra: float | None = None

        if nli_evaluator is not None and all_windows:
            pairs = [(win, s.clean_text) for win in all_windows]
            preds = nli_evaluator.predict(pairs)

            if preds:
                best_entail = max(p.entailment for p in preds)
                best_contra = max(p.contradiction for p in preds)

        # Determine grounding label
        label: Literal["supported", "unsupported", "contradicted", "not_assessable"]

        if num_guard_triggered:
            # Numeric guard caps label at unsupported
            label = "unsupported"
            unsupported_count += 1
        elif nli_evaluator is not None:
            if best_entail is not None and best_entail >= entail_threshold:
                label = "supported"
            elif (
                best_contra is not None
                and best_contra >= contradict_threshold
                and best_contra > (best_entail or 0.0)
            ):
                label = "contradicted"
                contradicted_count += 1
            else:
                label = "unsupported"
                unsupported_count += 1
        else:
            # Tier 0 mode: NLI not run
            label = "unsupported"

        evidence_list.append(
            ClaimSentenceEvidence(
                sentence_index=s.index,
                sentence_text=s.clean_text,
                is_assessable=True,
                grounding_label=label,
                best_entail_prob=best_entail,
                best_contradict_prob=best_contra,
                numeric_guard_triggered=num_guard_triggered,
            )
        )

    # Compute aggregate grounding metrics
    if nli_evaluator is None:
        # Tier 0 mode: NLI was not run, so Tier-1 rate is null
        unsupported_claim_rate = None
        unanswerable_violation = unanswerable and (not is_refusal)
        is_unsupported_answer = any_num_guard_triggered or unanswerable_violation
    else:
        if assessable_count == 0:
            unsupported_claim_rate = None
        else:
            unsupported_claim_rate = round(
                (unsupported_count + contradicted_count) / assessable_count, 6
            )

        has_unsupported_claim = any(
            ev.is_assessable and ev.grounding_label != "supported" for ev in evidence_list
        )
        unanswerable_violation = unanswerable and (not is_refusal)
        is_unsupported_answer = has_unsupported_claim or unanswerable_violation

    metrics = GroundingMetrics(
        unsupported_claim_rate=unsupported_claim_rate,
        is_unsupported_answer=is_unsupported_answer,
    )

    return metrics, evidence_list
