# TRACE AI (`trace-eval`)

Deterministic-First RAG Evaluation Engine and Workbench.

[![CI](https://github.com/trace-ai/trace-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/trace-ai/trace-eval/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)

TRACE AI is an open-source evaluation engine for Retrieval-Augmented Generation (RAG) pipelines. It prioritizes deterministic, reproducible metrics, explicit provenance, and cryptographic result verification over non-deterministic LLM-as-a-judge scores.

---

## Benchmark Limitations

Per Section 6 of the normative [Methodology](docs/methodology.md):

- **Domain Scope**: Approximately 60 items, English language only, single fictional domain, short passages.
- **Single Annotator**: Human gold labels are created by one annotator and frozen before evaluator runs. There is no inter-annotator agreement estimate.
- **Synthetic Fixture Prevalence**: Synthetic fixtures over-represent specific failure modes by construction. Failure prevalence in this benchmark is not representative of real-world operational systems. Headline "accuracy" is never presented as real-world performance; stratified per-class metrics are the reporting unit.
- **Domain Shift**: The local NLI evaluator model was trained on SNLI and MNLI and is evaluated out-of-domain. Results do not establish broad cross-domain generalization.
- **Confidence Intervals**: Given benchmark size, bootstrap confidence intervals will be wide. All reporting must surface intervals.

---

## Developer Experience & Reproducible Setup

This repository requires **no API keys, no external accounts, and no paid services**. All tests and validations run locally in pure Python.

### 1. Prerequisites

- Python 3.11+
- Git

### 2. Create a Virtual Environment

```bash
# macOS/Linux
python3.11 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install Package in Editable Development Mode

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

*Note on offline/sandboxed environments:* If setuptools is already installed in your Python environment, use `--no-build-isolation`:
```bash
python -m pip install --no-build-isolation -e .
```

### 4. Run Tests

Execute the comprehensive pytest suite (including golden canonical serialization and hashing tests):

```bash
pytest -v
```

### 5. Run Ruff (Linting & Formatting)

```bash
# Run linter
ruff check .

# Check formatting
ruff format --check .

# Auto-format code
ruff format .
```

### 6. Export & Regenerate JSON Schemas

TRACE AI auto-generates JSON Schema specifications directly from Pydantic v2 data models into `/schema/`:

```bash
python -m trace_eval.schema.export
```

### 7. Verify Schema Drift in CI

Ensure committed schemas in `/schema/*.json` match current Pydantic models:

```bash
python -m trace_eval.schema.export --check
```

---

## Repository Structure

```text
trace-eval/
├── docs/
│   └── methodology.md        # Normative TRACE AI methodology v1.0.0
├── trace_eval/               # Python package (trace_eval)
│   ├── __init__.py
│   ├── canonical.py          # Deterministic TRACE canonical JSON serialization
│   ├── hashing.py            # Content and result hashing engine
│   └── schema/               # Pydantic v2 versioned data contracts
│       ├── __init__.py
│       ├── dataset.py        # trace.dataset/1.0
│       ├── submission.py     # trace.submission/1.0
│       ├── labels.py         # trace.labels/1.0
│       ├── run.py            # trace.run/1.0
│       ├── comparison.py     # trace.comparison/1.0
│       └── export.py         # JSON Schema exporter & drift detector
├── schema/                   # Generated JSON Schemas
│   ├── trace_dataset_v1.json
│   ├── trace_submission_v1.json
│   ├── trace_labels_v1.json
│   ├── trace_run_v1.json
│   └── trace_comparison_v1.json
├── tests/                    # Test suite and golden fixtures
│   ├── fixtures/             # Committed golden fixtures & hashes
│   │   ├── golden_canonical.json
│   │   ├── golden_dataset.json
│   │   ├── golden_submission.json
│   │   ├── golden_labels.json
│   │   ├── golden_run.json
│   │   ├── golden_comparison.json
│   │   └── golden_hashes.json
│   ├── test_canonical.py     # Canonical serialization test suite
│   ├── test_hashing.py       # Content and result hashing test suite
│   ├── test_schema.py        # Pydantic contracts and validations
│   └── test_schema_export.py # Schema drift detection test
├── .github/
│   └── workflows/
│       └── ci.yml            # GitHub Actions CI workflow
├── pyproject.toml            # PEP 517/621 packaging configuration
├── README.md                 # Project guide & reproduction steps
├── CHANGELOG.md              # Version history & methodology clarifications
├── LICENSE                   # Apache-2.0 License
└── .gitignore                # Git ignore patterns
```

---

## Data Contracts Overview

| Contract | Schema Version | Content Hash Scope | Notes |
|---|---|---|---|
| **Dataset** | `trace.dataset/1.0` | `{schema_version, dataset_id, language, corpus, items}` | Excludes `name`, `description`, `license`. Requires unique item & passage IDs. |
| **Submission** | `trace.submission/1.0` | `{schema_version, dataset_id, outputs}` | Excludes `system`. Enforces `fixture_note` for synthetic fixtures and `system.provenance` for recorded pipelines. |
| **Labels** | `trace.labels/1.0` | Entire document except `annotator_notes` | Keyed by `submission_content_sha256`. Preserves `sentence_text` for segmentation checks. |
| **Run** | `trace.run/1.0` | Core: `{schema_version, methodology_version, dataset, submission_content_sha256, config, summary, items}` | Excludes `run_id`, `result_hash`, `runtime_status`, `environment`, `system`, `input_origin_summary`. |
| **Comparison** | `trace.comparison/1.0` | Paired run evaluation | Captures metric deltas, cluster-bootstrap CIs, and regression gate flags. |

---

## License

This project is licensed under the [Apache License, Version 2.0](LICENSE).
