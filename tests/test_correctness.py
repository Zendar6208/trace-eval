"""Tests for Tier-0 answer correctness (Token F1, fact matching, aliases, refusal)."""

from trace_eval.metrics.correctness import (
    compute_token_f1,
    evaluate_correctness,
    match_required_facts,
)
from trace_eval.refusal import is_refusal
from trace_eval.schema.dataset import RequiredFact


def test_token_f1():
    # Exact match
    assert compute_token_f1("Refunds take 30 days.", ["Refunds take 30 days."]) == 1.0

    # Partial match
    f1 = compute_token_f1("Refunds take 30 days.", ["Refunds take 60 days."])
    # tokens: ['refunds', 'take', '30', 'days'] vs ['refunds', 'take', '60', 'days']
    # 3 common / 4 tokens each -> F1 = 0.75
    assert f1 == 0.75

    # Completely disjoint
    assert compute_token_f1("Hello world.", ["Goodbye everyone."]) == 0.0

    # Multiple references: takes max
    assert compute_token_f1("30 days.", ["60 days.", "Refunds take 30 days."]) > compute_token_f1(
        "30 days.", ["60 days."]
    )


def test_required_fact_matching_exact():
    facts = [
        RequiredFact(fact_id="f1", text="30 business days", aliases=["30 days"]),
        RequiredFact(fact_id="f2", text="written request", aliases=[]),
    ]
    answer = "All refunds require a written request and take 30 business days."
    recall, details = match_required_facts(answer, facts)
    assert recall == 1.0
    assert all(d["matched"] for d in details)
    assert details[0]["method"] == "normalized_containment"


def test_required_fact_alias_matching():
    facts = [
        RequiredFact(fact_id="f1", text="thirty business days", aliases=["30 days", "1 month"]),
    ]
    # Primary text "thirty business days" is not present, but alias "30 days" is present
    answer = "The process takes 30 days.[p01]"
    recall, details = match_required_facts(answer, facts)
    assert recall == 1.0
    assert details[0]["matched"] is True
    assert details[0]["method"] == "alias_containment"
    assert details[0]["matched_alias"] == "30 days"


def test_missing_required_facts():
    facts = [
        RequiredFact(fact_id="f1", text="fact one"),
        RequiredFact(fact_id="f2", text="fact two"),
    ]
    # Only fact one present -> partial
    res_partial = evaluate_correctness("We only have fact one.", ["Gold"], facts)
    assert res_partial["fact_recall"] == 0.5
    assert res_partial["verdict"] == "partial"

    # Neither fact present -> incorrect
    res_incorrect = evaluate_correctness("Nothing relevant here.", ["Gold"], facts)
    assert res_incorrect["fact_recall"] == 0.0
    assert res_incorrect["verdict"] == "incorrect"


def test_unanswerable_question_handling():
    facts = [RequiredFact(fact_id="f1", text="some fact")]

    # Unanswerable with valid refusal -> correct
    refusal_answer = "The provided documents do not contain information to answer this question."
    assert is_refusal(refusal_answer) is True
    res_refusal = evaluate_correctness(refusal_answer, [], facts, unanswerable=True)
    assert res_refusal["verdict"] == "correct"

    # Unanswerable with non-refusal answer -> incorrect
    hallucinated_answer = "The answer is 42."
    assert is_refusal(hallucinated_answer) is False
    res_hallucinated = evaluate_correctness(hallucinated_answer, [], facts, unanswerable=True)
    assert res_hallucinated["verdict"] == "incorrect"


def test_answerable_question_false_refusal():
    # Answerable question met with a refusal -> incorrect (false refusal)
    facts = [RequiredFact(fact_id="f1", text="30 days")]
    refusal_answer = "I cannot answer this question."
    res = evaluate_correctness(refusal_answer, ["Takes 30 days."], facts, unanswerable=False)
    assert res["verdict"] == "incorrect"
    assert res["is_refusal"] is True
