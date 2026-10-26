"""Helper to generate committed golden fixtures."""

import hashlib
import json
from pathlib import Path

from trace_eval.canonical import canonical_json
from trace_eval.hashing import (
    compute_run_hashes,
    hash_dataset,
    hash_labels,
    hash_submission,
)
from trace_eval.schema.comparison import ComparisonResult
from trace_eval.schema.dataset import Dataset
from trace_eval.schema.labels import LabelsDocument
from trace_eval.schema.run import RunResult
from trace_eval.schema.submission import Submission

fixtures_dir = Path("tests/fixtures")
fixtures_dir.mkdir(parents=True, exist_ok=True)

# 1. Golden canonical serialization test cases
raw_cases = [
    {
        "name": "dict_key_sorting",
        "description": "Ensure dictionary keys are sorted by Unicode code point with no whitespace",
        "input": {"z": 1, "b": 2, "a": 3},
        "expected_canonical_str": '{"a":3,"b":2,"z":1}',
    },
    {
        "name": "unicode_nfc_normalization",
        "description": "NFD combining characters are normalized to NFC in keys and string values",
        "input": {"caf\u00e9": "re\u0301sume\u0301"},
        "expected_canonical_str": '{"caf\u00e9":"r\u00e9sum\u00e9"}',
    },
    {
        "name": "float_rounding_and_types",
        "description": "Six-decimal float rounding, negative zero normalization, and int vs float distinction",
        "input": {
            "bool_val": False,
            "float_int": 1.0,
            "float_round_down": 1.1234564,
            "float_round_up": 1.1234567,
            "int_val": 1,
            "negative_zero": -0.0,
            "null_val": None,
        },
        "expected_canonical_str": '{"bool_val":false,"float_int":1.0,"float_round_down":1.123456,"float_round_up":1.123457,"int_val":1,"negative_zero":0.0,"null_val":null}',
    },
]

canonical_cases = []
for c in raw_cases:
    b = canonical_json(c["input"])
    canonical_cases.append(
        {
            "name": c["name"],
            "description": c["description"],
            "input": c["input"],
            "expected_canonical_str": c["expected_canonical_str"],
            "expected_canonical_bytes_hex": b.hex(),
            "expected_sha256": hashlib.sha256(b).hexdigest(),
        }
    )

# Write golden canonical cases
(fixtures_dir / "golden_canonical.json").write_text(
    json.dumps(canonical_cases, indent=2), encoding="utf-8"
)

# 2. Golden dataset
dataset_obj = {
    "schema_version": "trace.dataset/1.0",
    "dataset_id": "sample-finance-benchmark",
    "name": "Sample Finance RAG Benchmark",
    "description": "Normative golden benchmark dataset for verification.",
    "language": "en",
    "license": "Apache-2.0",
    "corpus": [
        {
            "id": "p01",
            "text": "Refunds are processed within 30 business days of initial request.",
            "title": "Refund Policy",
            "metadata": {"section": "billing"},
        },
        {
            "id": "p02",
            "text": "Cancellation requests must be submitted at least 24 hours prior to renewal.",
            "title": "Cancellation Terms",
            "metadata": {"section": "subscriptions"},
        },
    ],
    "items": [
        {
            "id": "item-001",
            "group_id": "refund-case",
            "split": "dev",
            "question": "How long do refunds take to process?",
            "unanswerable": False,
            "gold_passage_ids": ["p01"],
            "reference_answers": ["Refunds take up to 30 business days."],
            "required_facts": [
                {
                    "fact_id": "f1",
                    "text": "30 business days",
                    "aliases": ["30 days"],
                    "is_numeric": True,
                }
            ],
            "metadata": {"complexity": "simple"},
        },
        {
            "id": "item-002",
            "group_id": "cancel-case",
            "split": "test",
            "question": "Can I cancel right after renewal?",
            "unanswerable": False,
            "gold_passage_ids": ["p02"],
            "reference_answers": [
                "Cancellations must be requested at least 24 hours before renewal."
            ],
            "required_facts": [
                {
                    "fact_id": "f2",
                    "text": "24 hours prior to renewal",
                    "aliases": [],
                    "is_numeric": True,
                }
            ],
            "metadata": {"complexity": "simple"},
        },
    ],
}
dataset_model = Dataset.model_validate(dataset_obj)
(fixtures_dir / "golden_dataset.json").write_text(
    json.dumps(dataset_model.model_dump(mode="json"), indent=2), encoding="utf-8"
)
dataset_hash = hash_dataset(dataset_model)

# 3. Golden submission
submission_obj = {
    "schema_version": "trace.submission/1.0",
    "dataset_id": "sample-finance-benchmark",
    "system": {
        "name": "ProductionRAG",
        "version": "v1.2.0",
        "provenance": {
            "pipeline_description": "BM25 + Dense Retriever with Llama-3-70B",
            "model_name": "llama-3-70b-instruct",
            "retriever_name": "bge-large-en-v1.5",
            "run_timestamp": "2026-10-26T10:00:00Z",
            "parameters": {"temperature": 0.0, "top_k": 2},
        },
    },
    "outputs": [
        {
            "item_id": "item-001",
            "origin": "recorded_system",
            "fixture_note": None,
            "answer": "Refunds are processed within 30 business days.[p01]",
            "retrieved": [
                {"id": "p01", "score": 0.95, "text": None, "metadata": None},
                {"id": "p02", "score": 0.45, "text": None, "metadata": None},
            ],
            "metadata": None,
        },
        {
            "item_id": "item-002",
            "origin": "synthetic_fixture",
            "fixture_note": "Synthetic bad citation to phantom ID p99",
            "answer": "You can cancel anytime.[p99]",
            "retrieved": [
                {"id": "p02", "score": 0.88, "text": None, "metadata": None},
            ],
            "metadata": None,
        },
    ],
}
submission_model = Submission.model_validate(submission_obj)
(fixtures_dir / "golden_submission.json").write_text(
    json.dumps(submission_model.model_dump(mode="json"), indent=2), encoding="utf-8"
)
submission_hash = hash_submission(submission_model)

# 4. Golden labels
labels_obj = {
    "schema_version": "trace.labels/1.0",
    "dataset_id": "sample-finance-benchmark",
    "submission_content_sha256": submission_hash,
    "annotator_notes": "Annotated by primary annotator; excluded from content hash.",
    "items": [
        {
            "item_id": "item-001",
            "annotator_id": "annotator-01",
            "correctness_verdict": "correct",
            "notes": None,
            "sentences": [
                {
                    "sentence_index": 0,
                    "sentence_text": "Refunds are processed within 30 business days.",
                    "is_claim": True,
                    "grounding_label": "supported",
                    "citation_labels": [{"passage_id": "p01", "supports": True, "notes": None}],
                    "notes": None,
                }
            ],
        },
        {
            "item_id": "item-002",
            "annotator_id": "annotator-01",
            "correctness_verdict": "incorrect",
            "notes": None,
            "sentences": [
                {
                    "sentence_index": 0,
                    "sentence_text": "You can cancel anytime.",
                    "is_claim": True,
                    "grounding_label": "contradicted",
                    "citation_labels": [
                        {"passage_id": "p99", "supports": False, "notes": "Phantom citation"}
                    ],
                    "notes": None,
                }
            ],
        },
    ],
}
labels_model = LabelsDocument.model_validate(labels_obj)
(fixtures_dir / "golden_labels.json").write_text(
    json.dumps(labels_model.model_dump(mode="json"), indent=2), encoding="utf-8"
)
labels_hash = hash_labels(labels_model)

# 5. Golden run
run_obj = {
    "schema_version": "trace.run/1.0",
    "methodology_version": "1.0.0",
    "dataset": {
        "id": "sample-finance-benchmark",
        "content_sha256": dataset_hash,
    },
    "submission_content_sha256": submission_hash,
    "config": {
        "thresholds": {"entail": 0.8, "contradict": 0.7},
        "citation_style": "id",
        "phantom_mode": "bracket",
        "require_citations": True,
        "prefilter_top_m": None,
        "window_sentences": 3,
        "max_length": 512,
        "batch_size": 16,
        "truncation_policy": "longest_first",
        "id2label": {"0": "contradiction", "1": "neutral", "2": "entailment"},
        "nli_model": {
            "model_name": "roberta-large-snli_mnli",
            "revision": "v1.0",
            "weights_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        },
        "bootstrap": {"resamples": 10000, "seed": 42},
    },
    "summary": {
        "recorded_system": {
            "count": 1,
            "mean_token_f1": 0.85,
            "mean_fact_recall": 1.0,
            "accuracy": 1.0,
            "mean_citation_precision": 1.0,
            "mean_citation_recall": 1.0,
            "mean_phantom_rate": 0.0,
            "mean_unsupported_claim_rate": 0.0,
        },
        "synthetic_fixture": {
            "count": 1,
            "mean_token_f1": 0.1,
            "mean_fact_recall": 0.0,
            "accuracy": 0.0,
            "mean_citation_precision": 0.0,
            "mean_citation_recall": 0.0,
            "mean_phantom_rate": 1.0,
            "mean_unsupported_claim_rate": 1.0,
        },
        "combined": {
            "count": 2,
            "mean_token_f1": 0.475,
            "mean_fact_recall": 0.5,
            "accuracy": 0.5,
            "mean_citation_precision": 0.5,
            "mean_citation_recall": 0.5,
            "mean_phantom_rate": 0.5,
            "mean_unsupported_claim_rate": 0.5,
        },
        "failure_distribution": {
            "PASS": 1,
            "BAD_CITATION": 1,
            "UNSUPPORTED_CLAIM": 1,
        },
    },
    "items": [
        {
            "item_id": "item-001",
            "origin": "recorded_system",
            "metrics": {
                "retrieval": {
                    "hit_at_k": {"1": 1.0, "2": 1.0},
                    "recall_at_k": {"1": 1.0, "2": 1.0},
                    "precision_at_k": {"1": 1.0, "2": 0.5},
                    "mrr": 1.0,
                    "ndcg_at_k": {"1": 1.0, "2": 1.0},
                },
                "correctness": {
                    "fact_recall": 1.0,
                    "token_f1": 0.85,
                    "contradicts_reference": False,
                    "verdict": "correct",
                },
                "citation": {
                    "citation_precision": 1.0,
                    "citation_recall": 1.0,
                    "phantom_rate": 0.0,
                    "uncited_claim_rate": 0.0,
                    "cites_gold": True,
                },
                "grounding": {
                    "unsupported_claim_rate": 0.0,
                    "is_unsupported_answer": False,
                },
            },
            "failure_types": ["PASS"],
            "evidence": {
                "claims": [
                    {
                        "sentence_index": 0,
                        "sentence_text": "Refunds are processed within 30 business days.",
                        "is_assessable": True,
                        "grounding_label": "supported",
                        "best_entail_prob": 0.98,
                        "best_contradict_prob": 0.01,
                        "numeric_guard_triggered": False,
                    }
                ],
                "citations": [
                    {
                        "sentence_index": 0,
                        "passage_id": "p01",
                        "validity": "ok",
                        "supports": True,
                        "entail_prob": 0.98,
                        "best_window": "Refunds are processed within 30 business days of initial request.",
                    }
                ],
            },
        },
        {
            "item_id": "item-002",
            "origin": "synthetic_fixture",
            "metrics": {
                "retrieval": {
                    "hit_at_k": {"1": 0.0},
                    "recall_at_k": {"1": 0.0},
                    "precision_at_k": {"1": 0.0},
                    "mrr": 0.0,
                    "ndcg_at_k": {"1": 0.0},
                },
                "correctness": {
                    "fact_recall": 0.0,
                    "token_f1": 0.1,
                    "contradicts_reference": True,
                    "verdict": "incorrect",
                },
                "citation": {
                    "citation_precision": 0.0,
                    "citation_recall": 0.0,
                    "phantom_rate": 1.0,
                    "uncited_claim_rate": 0.0,
                    "cites_gold": False,
                },
                "grounding": {
                    "unsupported_claim_rate": 1.0,
                    "is_unsupported_answer": True,
                },
            },
            "failure_types": ["BAD_CITATION", "UNSUPPORTED_CLAIM", "WRONG_ANSWER"],
            "evidence": {
                "claims": [
                    {
                        "sentence_index": 0,
                        "sentence_text": "You can cancel anytime.",
                        "is_assessable": True,
                        "grounding_label": "contradicted",
                        "best_entail_prob": 0.02,
                        "best_contradict_prob": 0.94,
                        "numeric_guard_triggered": False,
                    }
                ],
                "citations": [
                    {
                        "sentence_index": 0,
                        "passage_id": "p99",
                        "validity": "unknown_id",
                        "supports": False,
                        "entail_prob": None,
                        "best_window": None,
                    }
                ],
            },
        },
    ],
    # Non-core fields
    "run_id": None,
    "result_hash": None,
    "runtime_status": "loaded",
    "environment": {
        "timestamp": "2026-10-26T10:15:00Z",
        "duration_seconds": 12.345,
        "hostname": "eval-worker-01",
        "os": "Linux-5.15.0",
        "python_version": "3.11.9",
        "git_sha": "0123456789abcdef0123456789abcdef01234567",
        "library_versions": {"torch": "2.14.0", "transformers": "4.51.3"},
        "thread_count": 4,
    },
    "system": submission_model.system,
    "input_origin_summary": {
        "recorded_system_count": 1,
        "synthetic_fixture_count": 1,
        "total_count": 2,
    },
}

run_result_hash, run_id = compute_run_hashes(run_obj)
run_obj["result_hash"] = run_result_hash
run_obj["run_id"] = run_id
run_model = RunResult.model_validate(run_obj)
(fixtures_dir / "golden_run.json").write_text(
    json.dumps(run_model.model_dump(mode="json"), indent=2), encoding="utf-8"
)

# 6. Golden comparison
comparison_obj = {
    "schema_version": "trace.comparison/1.0",
    "comparison_id": "comp-baseline-vs-candidate",
    "baseline_run": {
        "run_id": run_id,
        "result_hash": run_result_hash,
        "system_name": "ProductionRAG",
    },
    "candidate_run": {
        "run_id": run_id,
        "result_hash": run_result_hash,
        "system_name": "CandidateRAG",
    },
    "dataset": {
        "id": "sample-finance-benchmark",
        "content_sha256": dataset_hash,
    },
    "metrics_diff": {
        "token_f1": {
            "metric_name": "token_f1",
            "baseline_value": 0.475,
            "candidate_value": 0.55,
            "absolute_delta": 0.075,
            "relative_delta": 0.157895,
            "ci_lower": 0.01,
            "ci_upper": 0.14,
            "p_value": 0.035,
            "significant": True,
        }
    },
    "regression_detected": False,
    "regression_reasons": [],
    "summary": {
        "total_items": 2,
        "regressed_items_count": 0,
        "improved_items_count": 1,
        "unchanged_items_count": 1,
    },
    "item_comparisons": [
        {
            "item_id": "item-001",
            "baseline_verdict": "correct",
            "candidate_verdict": "correct",
            "baseline_failure_types": ["PASS"],
            "candidate_failure_types": ["PASS"],
            "status": "unchanged",
            "notes": None,
        },
        {
            "item_id": "item-002",
            "baseline_verdict": "incorrect",
            "candidate_verdict": "partial",
            "baseline_failure_types": ["BAD_CITATION", "UNSUPPORTED_CLAIM", "WRONG_ANSWER"],
            "candidate_failure_types": ["BAD_CITATION"],
            "status": "improved",
            "notes": "Answer improved to partial",
        },
    ],
    "metadata": {"comparator": "trace-eval-v0.1.0"},
}
comp_model = ComparisonResult.model_validate(comparison_obj)
(fixtures_dir / "golden_comparison.json").write_text(
    json.dumps(comp_model.model_dump(mode="json"), indent=2), encoding="utf-8"
)

# 7. Record expected hashes in golden_hashes.json
golden_hashes = {
    "dataset_content_sha256": dataset_hash,
    "submission_content_sha256": submission_hash,
    "labels_content_sha256": labels_hash,
    "run_result_hash": run_result_hash,
    "run_id": run_id,
}
(fixtures_dir / "golden_hashes.json").write_text(
    json.dumps(golden_hashes, indent=2), encoding="utf-8"
)

print("Generated all golden fixtures successfully:")
print("Dataset content hash:", dataset_hash)
print("Submission content hash:", submission_hash)
print("Labels content hash:", labels_hash)
print("Run result hash:", run_result_hash)
print("Run ID:", run_id)
