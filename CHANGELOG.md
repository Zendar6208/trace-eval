# Changelog

All notable changes to the TRACE AI engine (`trace-eval`) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
