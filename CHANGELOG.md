# Changelog

All notable changes to the TRACE AI engine (`trace-eval`) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-10-26

### Added - Milestone M1: Deterministic Evaluation (Tier 0)

- **Deterministic Retrieval Metrics (`trace_eval/metrics/retrieval.py`)**:
  - `hit_at_k`: 1.0 if any gold passage appears in top-k, else 0.0.
  - `recall_at_k`: Fraction of gold passages retrieved in top-k.
  - `precision_at_k`: Fraction of top-k passages that are gold.
  - `compute_mrr`: Mean Reciprocal Rank (1/rank of first gold passage).
  - `compute_ndcg_at_k`: Normalized Discounted Cumulative Gain with graded gains ($2^{\text{rel}} - 1$) and $\log_2(i+1)$ discounting.
  - Fallback token overlap ($\ge 0.8$) against gold passage text for unindexed chunk IDs per Section 3.
- **Deterministic Answer Correctness (`trace_eval/metrics/correctness.py`)**:
  - `compute_token_f1`: Multiset SQuAD-style token F1 against multiple gold reference answers.
  - `match_required_facts`: Normalized containment matching on fact text and registered aliases.
  - `evaluate_correctness`: Correct/partial/incorrect verdict determination.
- **Refusal Detection & Unanswerables (`trace_eval/refusal.py`)**:
  - Rule-based regex refusal patterns per Section 2.5.
  - For unanswerable items, verdict is `correct` if and only if the answer is a refusal; non-refusals flagged as `ANSWERED_UNANSWERABLE`.
  - False refusals on answerable items flagged as `FALSE_REFUSAL` and graded `incorrect`.
- **Metric Independence Enforcement (`tests/test_metric_independence.py`)**:
  - Verified retrieval metrics strictly read only `retrieved` and gold passages, never reading answer or citations.
  - Verified correctness metrics strictly read only answer text, references, and required facts, never reading retrieval results or citations.
- **End-to-End Tier-0 Evaluator (`trace_eval/evaluator.py`)**:
  - `evaluate_item`: Single item evaluation and multi-label failure type assignment (`RETRIEVAL_MISS`, `WRONG_ANSWER`, `ANSWERED_UNANSWERABLE`, `FALSE_REFUSAL`, `PASS`).
  - `evaluate_run`: Full submission evaluation across all benchmark items, aggregating stratified summaries (`recorded_system`, `synthetic_fixture`, `combined`) and generating verified `RunResult` with cryptographic `result_hash` and derived `run_id`.

## [0.1.1] - 2026-10-26

### Added - Milestone M0 Corrections

- **Calibration Record Contract (`trace_eval/schema/run.py`)**:
  - Added typed `CalibrationRecord`, `CalibrationGrid`, and `CalibrationThresholds` to `RunConfig` per Section 5.
- **Run Hash & ID Integrity Enforcement**:
  - `RunResult` automatically verifies that `result_hash` and `run_id` match the computed hash of the deterministic semantic core upon validation.
- **Semantic Citation Support Validators**:
  - Enforced CA-4: Orphan citations (`sentence_index=None`) strictly cannot have `supports=True`.
  - Enforced CA-7: Non-`ok` citations (`not_retrieved`, `unknown_id`, `index_out_of_range`) strictly cannot have `supports=True`.
- **Graded Relevance Contract (`trace_eval/schema/dataset.py`)**:
  - Added `GoldPassageRelevance` (relevance 1-3) to `DatasetItem` for graded nDCG gains.
- **Cross-Document Integrity Verification (`trace_eval/validation.py`)**:
  - Validates referential and cryptographic bindings across `Dataset`, `Submission`, `LabelsDocument`, and `RunResult`.
- **Versioned Reference Fixtures**:
  - Created `golden_dataset_m0_corrected.json`, `golden_run_m0_corrected.json`, and `golden_hashes_m0_corrected.json` documenting the schema additions.

## [0.1.0] - 2026-10-26

### Added - Milestone M0: Repository Foundation, Data Contracts, Canonical Serialization & Testing Infrastructure

- **Normative Methodology (`docs/methodology.md`)**:
  - Imported normative TRACE AI Methodology v1.0.0.
  - Documented three normative clarifications:
    1. *Citation Metrics Validity Scope*: Citation metrics may inspect `retrieved` passage IDs exclusively to establish citation validity (`ok`, `not_retrieved`, `unknown_id`, `index_out_of_range`). Citation support evidence must come exclusively from the cited passage's own text windows.
    2. *MM-5 Gated Expectation*: Metamorphic operator MM-5's expectation of an increased `unsupported_claim_rate` is a Tier-1 gated expectation ($\ge 90\%$), not an unconditional invariant.
    3. *Committed Golden Test Fixtures*: Canonical JSON serialization and content hashing require committed golden fixtures with explicit expected byte representations and SHA-256 digests.
- **Typed Data Contracts (`trace_eval/schema/`)**:
  - `trace.dataset/1.0`: `Dataset`, `Passage`, `DatasetItem`, `RequiredFact`. Validates unique IDs, group-level splits, and fact specifications.
  - `trace.submission/1.0`: `Submission`, `SubmissionOutput`, `RetrievedPassage`, `SystemMetadata`. Validates provenance constraints (`synthetic_fixture` requires `fixture_note`; `recorded_system` requires `system.provenance`).
  - `trace.labels/1.0`: `LabelsDocument`, `ItemLabels`, `SentenceLabel`, `CitationUnitLabel`. Decoupled from dataset, keyed by `submission_content_sha256`, preserving sentence text for segmentation drift detection.
  - `trace.run/1.0`: `RunResult`, `RunDatasetReference`, `RunConfig`, `RunSummary`, `RunItemResult`, `EnvironmentMetadata`. Strict separation of runtime status and execution environment from the deterministically hashed run core.
  - `trace.comparison/1.0`: `ComparisonResult`, `MetricDelta`, `ItemComparison`, `ComparisonSummary`. Paired benchmark evaluation differences with confidence intervals and regression flagging.
- **JSON Schema Exporter (`trace_eval/schema/export.py`)**:
  - Automatic JSON Schema generation from Pydantic v2 models into `schema/*.json`.
  - Schema drift verification preventing out-of-sync schemas in CI.
- **TRACE Canonical JSON Serialization (`trace_eval/canonical.py`)**:
  - Deterministic serialization conforming to Section 8.1.
  - Unicode NFC normalization, UTF-8 encoding without ASCII escapes, sorted dictionary keys.
  - 6-decimal float rounding, negative zero normalization (`-0.0` $\to$ `0.0`), finite float enforcement (rejection of `NaN`, `+Inf`, `-Inf`).
  - Type distinction preservation (integers vs. floating-point).
  - Explicit inclusion of `null` fields in model dumps without field dropping.
- **Cryptographic Hashing Engine (`trace_eval/hashing.py`)**:
  - `hash_dataset`: Hashes `{schema_version, dataset_id, language, corpus, items}`, excluding `name`, `description`, `license`.
  - `hash_submission`: Hashes `{schema_version, dataset_id, outputs}`, excluding `system`.
  - `hash_labels`: Hashes entire labels document excluding `annotator_notes`.
  - `compute_run_hashes`: Computes `result_hash = sha256(canonical_json(core))` and derives `run_id` as the first 16 hex characters. Strict exclusion of runtime status, environment, system metadata, and origin summaries.
  - Zero input mutation guarantee across all operations.
- **Committed Golden Fixtures and Test Suite (`tests/`)**:
  - `tests/fixtures/`: Golden fixtures for canonical serialization and hashing.
  - `tests/test_canonical.py`: Unit tests for float rounding, negative zero, NaN/Inf rejection, Unicode NFC, key sorting, and golden bytes.
  - `tests/test_hashing.py`: Hashing determinism, field sensitivity, non-semantic field exclusion, and golden SHA-256 verification.
  - `tests/test_schema.py`: Schema validity, provenance constraints, required fields, duplicate ID rejections, and schema round-trip tests.
  - `tests/test_schema_export.py`: Schema drift detection test.
- **CI / Build Infrastructure**:
  - Modern `pyproject.toml` targeting Python 3.11+, Pydantic v2.
  - Apache-2.0 License.
  - GitHub Actions workflow (`.github/workflows/ci.yml`).
