"""FastAPI backend for TRACE AI evaluation workbench.

Provides endpoints for:
- Running the bundled sample evaluation
- Uploading custom evaluation datasets & submissions
- Retrieving run results with full evidence
- Downloading sample dataset & submission templates
- NLI inference status
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from trace_eval.evaluator import evaluate_run
from trace_eval.nli import NLIEvaluator
from trace_eval.schema.dataset import Dataset
from trace_eval.schema.run import NLIModelConfig, RunConfig, RunResult, RunThresholds
from trace_eval.schema.submission import Submission
from trace_eval.validation import validate_submission_against_dataset

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TRACE AI",
    description="Deterministic-first RAG evaluation engine and workbench",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory cache ────────────────────────────────────────────────────────────
_last_run: RunResult | None = None
_dataset: Dataset | None = None
_submission: Submission | None = None
_nli_evaluator: NLIEvaluator | None = None


def get_nli_evaluator() -> NLIEvaluator | None:
    """Lazy-load local NLI evaluator singleton for Tier 1 inference."""
    global _nli_evaluator
    if _nli_evaluator is None:
        try:
            _nli_evaluator = NLIEvaluator(
                model_name="cross-encoder/nli-distilroberta-base",
                revision="b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
                device="cpu",
                local_files_only=True,
            )
        except Exception:
            try:
                _nli_evaluator = NLIEvaluator(
                    model_name="cross-encoder/nli-distilroberta-base",
                    revision="b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
                    device="cpu",
                    local_files_only=False,
                )
            except Exception as e:
                print(f"Warning: NLI model failed to load: {e}")
                _nli_evaluator = None
    return _nli_evaluator


# ── Benchmarks Registry ────────────────────────────────────────────────────────
BENCHMARKS = [
    {
        "id": "hariom-refund-demo-v1",
        "name": "Customer Support & Refund Policies",
        "category": "Enterprise Policy",
        "badge": "2 Pipelines Available",
        "description": "Enterprise customer service policy benchmark evaluating tiered refund conditions, numeric timelines, return shipping exceptions, and unanswerable edge queries.",
        "item_count": 6,
        "corpus_size": 6,
        "license": "CC-BY-4.0",
        "has_comparison": True,
        "dataset_file": "dataset.json",
        "pipeline_a": {
            "id": "baseline",
            "name": "Dense + BM25 Baseline RAG",
            "version": "1.0.0",
            "model": "gemini-1.5-flash",
            "retriever": "bm25-dense-hybrid",
            "description": "Standard hybrid retrieval pipeline. Prone to phantom citation hallucination [p99] and ungrounded policy guarantees on edge queries.",
            "file": "submission.json",
        },
        "pipeline_b": {
            "id": "grounded",
            "name": "Grounded Cross-Encoder RAG",
            "version": "2.0.0",
            "model": "gemini-1.5-pro",
            "retriever": "colbert-v2-dense-rerank",
            "description": "Calibrated pipeline with cross-encoder re-ranking and NLI citation verification. Achieves 100% precision and safe refusal.",
            "file": "submission_b.json",
        },
    },
    {
        "id": "cloud-incident-runbooks-v1",
        "name": "Cloud Infrastructure Incident Runbooks",
        "category": "DevOps & SRE",
        "badge": "Standard Benchmark",
        "description": "Mission-critical incident response benchmark testing PostgreSQL connection pool saturation, Redis LRU memory limits, TLS zero-downtime certificate reloads, and OOMKilled pods.",
        "item_count": 6,
        "corpus_size": 6,
        "license": "CC-BY-4.0",
        "has_comparison": False,
        "dataset_file": "runbooks_dataset.json",
        "pipeline_a": {
            "id": "incident_assistant",
            "name": "DevOps Incident Assistant",
            "version": "1.2.0",
            "model": "llama-3-70b-instruct",
            "retriever": "opensearch-bm25",
            "description": "OpenSearch BM25 retriever + Llama-3-70b-instruct reader with verified runbook command retrieval.",
            "file": "runbooks_submission.json",
        },
        "pipeline_b": None,
    },
]


def _load_sample_data() -> tuple[Dataset, Submission]:
    global _dataset, _submission
    if _dataset is None:
        with open(SAMPLE_DATA_DIR / "dataset.json", encoding="utf-8") as f:
            _dataset = Dataset.model_validate(json.load(f))
    if _submission is None:
        with open(SAMPLE_DATA_DIR / "submission.json", encoding="utf-8") as f:
            _submission = Submission.model_validate(json.load(f))
    return _dataset, _submission


# ── Request Models ─────────────────────────────────────────────────────────────
class UploadEvaluationRequest(BaseModel):
    dataset: dict[str, Any] = Field(..., description="trace.dataset/1.0 JSON")
    submission: dict[str, Any] = Field(..., description="trace.submission/1.0 JSON")
    require_citations: bool = Field(default=True, description="Whether citations are evaluated")
    citation_style: Literal["id", "index"] = Field(
        default="id", description="Citation marker style"
    )
    phantom_mode: Literal["bracket", "known_only"] = Field(
        default="bracket", description="Phantom citation detection mode"
    )


class CompareEvaluationRequest(BaseModel):
    benchmark_id: str | None = Field(
        default=None,
        description="Benchmark ID if comparing pre-configured benchmark pipelines",
    )
    dataset: dict[str, Any] | None = Field(
        default=None, description="trace.dataset/1.0 JSON (if custom)"
    )
    submission_a: dict[str, Any] | None = Field(
        default=None, description="First trace.submission/1.0 JSON"
    )
    submission_b: dict[str, Any] | None = Field(
        default=None, description="Second trace.submission/1.0 JSON"
    )
    require_citations: bool = Field(default=True, description="Whether citations are evaluated")
    citation_style: Literal["id", "index"] = Field(
        default="id", description="Citation marker style"
    )
    phantom_mode: Literal["bracket", "known_only"] = Field(
        default="bracket", description="Phantom citation detection mode"
    )


# ── Helpers ────────────────────────────────────────────────────────────────────
def _item_summary(item: Any, question: str | None = None) -> dict:
    """Convert a RunItemResult to a frontend-friendly summary dict."""
    m = item.metrics
    ret = m.retrieval
    cor = m.correctness
    cit = m.citation
    gro = m.grounding

    return {
        "item_id": item.item_id,
        "question": question,
        "origin": item.origin,
        "failure_types": item.failure_types,
        "retrieval": {
            "hit_at_k": ret.hit_at_k if ret else {},
            "recall_at_k": ret.recall_at_k if ret else {},
            "mrr": ret.mrr if ret else None,
            "ndcg_at_k": ret.ndcg_at_k if ret else {},
        }
        if ret
        else None,
        "correctness": {
            "fact_recall": cor.fact_recall,
            "token_f1": cor.token_f1,
            "verdict": cor.verdict,
            "contradicts_reference": cor.contradicts_reference,
        }
        if cor
        else None,
        "citation": {
            "citation_precision": cit.citation_precision,
            "citation_recall": cit.citation_recall,
            "phantom_rate": cit.phantom_rate,
            "uncited_claim_rate": cit.uncited_claim_rate,
            "cites_gold": cit.cites_gold,
        }
        if cit
        else None,
        "grounding": {
            "unsupported_claim_rate": gro.unsupported_claim_rate,
            "is_unsupported_answer": gro.is_unsupported_answer,
        }
        if gro
        else None,
    }


def _item_evidence(item: Any, dataset: Dataset, submission: Submission) -> dict:
    """Build per-item detailed evidence for inspector."""
    ds_item = next((i for i in dataset.items if i.id == item.item_id), None)
    sub_out = next((o for o in submission.outputs if o.item_id == item.item_id), None)

    retrieved_texts: dict[str, str] = {}
    if dataset:
        for p in dataset.corpus:
            retrieved_texts[p.id] = p.text

    retrieved_with_text = []
    if sub_out:
        for r in sub_out.retrieved:
            retrieved_with_text.append(
                {
                    "id": r.id,
                    "score": r.score,
                    "text": retrieved_texts.get(r.id, r.text or ""),
                }
            )

    evidence = item.evidence
    claims_ev = []
    citations_ev = []
    if evidence:
        for c in evidence.claims:
            claims_ev.append(
                {
                    "sentence_index": c.sentence_index,
                    "sentence_text": c.sentence_text,
                    "is_assessable": c.is_assessable,
                    "grounding_label": c.grounding_label,
                    "best_entail_prob": c.best_entail_prob,
                    "best_contradict_prob": c.best_contradict_prob,
                    "numeric_guard_triggered": c.numeric_guard_triggered,
                }
            )
        for u in evidence.citations:
            citations_ev.append(
                {
                    "sentence_index": u.sentence_index,
                    "passage_id": u.passage_id,
                    "validity": u.validity,
                    "supports": u.supports,
                    "entail_prob": u.entail_prob,
                    "best_window": u.best_window,
                }
            )

    return {
        **_item_summary(item),
        "question": ds_item.question if ds_item else None,
        "answer": sub_out.answer if sub_out else None,
        "reference_answers": ds_item.reference_answers if ds_item else [],
        "required_facts": [
            {"fact_id": f.fact_id, "text": f.text}
            for f in (ds_item.required_facts if ds_item else [])
        ],
        "retrieved": retrieved_with_text,
        "claims": claims_ev,
        "citations": citations_ev,
    }


def _format_run_response(run_result: RunResult, dataset: Dataset | None = None) -> dict:
    question_map = {i.id: i.question for i in dataset.items} if dataset else {}
    items_summary = [
        _item_summary(item, question_map.get(item.item_id)) for item in run_result.items
    ]
    combined = run_result.summary.combined
    recorded = run_result.summary.recorded_system
    synthetic = run_result.summary.synthetic_fixture

    return {
        "run_id": run_result.run_id,
        "result_hash": run_result.result_hash,
        "methodology_version": "1.0.0",
        "nli_enabled": run_result.config.nli_model is not None,
        "evaluation_tier": "Tier 1 (hybrid deterministic + NLI)"
        if run_result.config.nli_model is not None
        else "Tier 0 (deterministic)",
        "summary": {
            "combined": combined.model_dump() if combined else None,
            "recorded_system": recorded.model_dump() if recorded else None,
            "synthetic_fixture": synthetic.model_dump() if synthetic else None,
            "failure_distribution": run_result.summary.failure_distribution,
        },
        "items": items_summary,
    }


def _build_comparison_response(
    res_a: RunResult,
    res_b: RunResult,
    dataset: Dataset,
    sub_a: Submission,
    sub_b: Submission,
) -> dict:
    fmt_a = _format_run_response(res_a, dataset)
    fmt_b = _format_run_response(res_b, dataset)

    comb_a = fmt_a["summary"]["combined"] or {}
    comb_b = fmt_b["summary"]["combined"] or {}

    def _hit5(items):
        valid = [
            i
            for i in items
            if i.get("retrieval") and i["retrieval"].get("hit_at_k", {}).get("5") is not None
        ]
        return sum(i["retrieval"]["hit_at_k"]["5"] for i in valid) / (len(valid) or 1)

    def _rec5(items):
        valid = [
            i
            for i in items
            if i.get("retrieval") and i["retrieval"].get("recall_at_k", {}).get("5") is not None
        ]
        return sum(i["retrieval"]["recall_at_k"]["5"] for i in valid) / (len(valid) or 1)

    hit_a, hit_b = _hit5(fmt_a["items"]), _hit5(fmt_b["items"])
    rec_a, rec_b = _rec5(fmt_a["items"]), _rec5(fmt_b["items"])

    supp_a = (
        1.0 - (comb_a.get("mean_unsupported_claim_rate") or 0.0)
        if comb_a.get("mean_unsupported_claim_rate") is not None
        else None
    )
    supp_b = (
        1.0 - (comb_b.get("mean_unsupported_claim_rate") or 0.0)
        if comb_b.get("mean_unsupported_claim_rate") is not None
        else None
    )

    pass_a = sum(1 for i in res_a.items if not [f for f in i.failure_types if f and f != "PASS"])
    pass_b = sum(1 for i in res_b.items if not [f for f in i.failure_types if f and f != "PASS"])

    metrics_a = {
        "retrieval_hit": hit_a,
        "retrieval_recall": rec_a,
        "fact_recall": comb_a.get("mean_fact_recall"),
        "token_f1": comb_a.get("mean_token_f1"),
        "citation_precision": comb_a.get("mean_citation_precision"),
        "phantom_rate": comb_a.get("mean_phantom_rate"),
        "supported_claims": supp_a,
        "unsupported_claims": comb_a.get("mean_unsupported_claim_rate"),
        "pass_count": pass_a,
        "fail_count": len(res_a.items) - pass_a,
    }

    metrics_b = {
        "retrieval_hit": hit_b,
        "retrieval_recall": rec_b,
        "fact_recall": comb_b.get("mean_fact_recall"),
        "token_f1": comb_b.get("mean_token_f1"),
        "citation_precision": comb_b.get("mean_citation_precision"),
        "phantom_rate": comb_b.get("mean_phantom_rate"),
        "supported_claims": supp_b,
        "unsupported_claims": comb_b.get("mean_unsupported_claim_rate"),
        "pass_count": pass_b,
        "fail_count": len(res_b.items) - pass_b,
    }

    deltas = {
        "retrieval_hit_delta": (hit_b - hit_a) if hit_b is not None and hit_a is not None else 0.0,
        "fact_recall_delta": (
            (metrics_b["fact_recall"] or 0.0) - (metrics_a["fact_recall"] or 0.0)
        ),
        "token_f1_delta": ((metrics_b["token_f1"] or 0.0) - (metrics_a["token_f1"] or 0.0)),
        "citation_precision_delta": (
            (metrics_b["citation_precision"] or 0.0) - (metrics_a["citation_precision"] or 0.0)
        ),
        "phantom_rate_delta": (
            (metrics_b["phantom_rate"] or 0.0) - (metrics_a["phantom_rate"] or 0.0)
        ),
        "supported_claims_delta": (
            ((supp_b or 0.0) - (supp_a or 0.0))
            if supp_a is not None and supp_b is not None
            else 0.0
        ),
        "pass_count_delta": pass_b - pass_a,
    }

    question_map = {item.id: item.question for item in dataset.items}
    out_map_a = {o.item_id: o.answer for o in sub_a.outputs}
    out_map_b = {o.item_id: o.answer for o in sub_b.outputs}
    item_map_a = {i.item_id: i for i in res_a.items}
    item_map_b = {i.item_id: i for i in res_b.items}

    question_comparisons = []
    for item in dataset.items:
        it_a = item_map_a.get(item.id)
        it_b = item_map_b.get(item.id)
        if not it_a or not it_b:
            continue

        fails_a = [f for f in it_a.failure_types if f and f != "PASS"]
        fails_b = [f for f in it_b.failure_types if f and f != "PASS"]
        status_a = "PASS" if not fails_a else "FAIL"
        status_b = "PASS" if not fails_b else "FAIL"

        if status_a == "FAIL" and status_b == "PASS":
            verdict = "b_improved"
            summary = f"System B fixed {len(fails_a)} issue(s): eliminated {', '.join(fails_a)}."
        elif status_a == "PASS" and status_b == "FAIL":
            verdict = "a_better"
            summary = f"System A performed better: System B introduced {', '.join(fails_b)}."
        elif status_a == "PASS" and status_b == "PASS":
            verdict = "both_passed"
            summary = "Both systems generated accurate, verified, and well-cited responses."
        else:
            if len(fails_b) < len(fails_a):
                verdict = "b_improved"
                summary = f"System B had fewer issues ({len(fails_b)} vs {len(fails_a)})."
            elif len(fails_a) < len(fails_b):
                verdict = "a_better"
                summary = f"System A had fewer issues ({len(fails_a)} vs {len(fails_b)})."
            else:
                verdict = "both_failed"
                summary = f"Both systems encountered issues: System A ({', '.join(fails_a)}), System B ({', '.join(fails_b)})."

        question_comparisons.append(
            {
                "item_id": item.id,
                "question": question_map.get(item.id, item.id),
                "verdict": verdict,
                "summary": summary,
                "run_a": {
                    "answer": out_map_a.get(item.id, ""),
                    "status": status_a,
                    "failure_types": fails_a,
                    "issues_count": len(fails_a),
                    "citation_precision": it_a.metrics.citation.citation_precision
                    if it_a.metrics.citation
                    else None,
                },
                "run_b": {
                    "answer": out_map_b.get(item.id, ""),
                    "status": status_b,
                    "failure_types": fails_b,
                    "issues_count": len(fails_b),
                    "citation_precision": it_b.metrics.citation.citation_precision
                    if it_b.metrics.citation
                    else None,
                },
            }
        )

    return {
        "dataset": {
            "dataset_id": dataset.dataset_id,
            "name": dataset.name,
            "item_count": len(dataset.items),
        },
        "system_a": {
            "name": sub_a.system.name,
            "version": sub_a.system.version,
            "pipeline": sub_a.system.provenance.pipeline_description
            if sub_a.system.provenance
            else "",
            "run_id": res_a.run_id,
            "result_hash": res_a.result_hash,
            "metrics": metrics_a,
        },
        "system_b": {
            "name": sub_b.system.name,
            "version": sub_b.system.version,
            "pipeline": sub_b.system.provenance.pipeline_description
            if sub_b.system.provenance
            else "",
            "run_id": res_b.run_id,
            "result_hash": res_b.result_hash,
            "metrics": metrics_b,
        },
        "deltas": deltas,
        "questions": question_comparisons,
    }


# ── Routes ─────────────────────────────────────────────────────────────────────


@app.get("/")
async def root():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"service": "TRACE AI", "version": "0.1.0", "status": "ready"}


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/api/sample/dataset")
async def get_sample_dataset():
    """Return the raw sample dataset JSON."""
    with open(SAMPLE_DATA_DIR / "dataset.json", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/sample/submission")
async def get_sample_submission():
    """Return the raw sample submission JSON."""
    with open(SAMPLE_DATA_DIR / "submission.json", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/sample/submission_b")
async def get_sample_submission_b():
    """Return the raw sample submission B (grounded pipeline) JSON."""
    with open(SAMPLE_DATA_DIR / "submission_b.json", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/benchmarks")
async def list_benchmarks():
    """Return available pre-configured evaluation benchmarks."""
    return BENCHMARKS


@app.get("/api/benchmarks/{benchmark_id}")
async def get_benchmark(benchmark_id: str):
    """Get metadata for a specific benchmark."""
    bm = next((b for b in BENCHMARKS if b["id"] == benchmark_id), None)
    if not bm:
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_id}' not found")
    return bm


@app.get("/api/benchmark/{benchmark_id}/dataset")
async def get_benchmark_dataset(benchmark_id: str):
    """Return the raw dataset JSON for a benchmark."""
    bm = next((b for b in BENCHMARKS if b["id"] == benchmark_id), None)
    if not bm:
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_id}' not found")
    file_path = SAMPLE_DATA_DIR / bm["dataset_file"]
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/benchmark/{benchmark_id}/submission/{pipeline_id}")
async def get_benchmark_submission(benchmark_id: str, pipeline_id: str):
    """Return the raw submission JSON for a benchmark pipeline ('a' or 'b')."""
    bm = next((b for b in BENCHMARKS if b["id"] == benchmark_id), None)
    if not bm:
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_id}' not found")

    if pipeline_id.lower() in ("b", "grounded"):
        if not bm.get("pipeline_b"):
            raise HTTPException(
                status_code=404, detail="Pipeline B not available for this benchmark"
            )
        file_path = SAMPLE_DATA_DIR / bm["pipeline_b"]["file"]
    else:
        file_path = SAMPLE_DATA_DIR / bm["pipeline_a"]["file"]

    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/evaluate/sample")
async def run_sample_evaluation():
    """Run real Tier-1 (hybrid deterministic + NLI) evaluation on the bundled sample dataset."""
    global _last_run, _dataset, _submission

    dataset, submission = _load_sample_data()
    nli = get_nli_evaluator()
    nli_cfg = (
        NLIModelConfig(
            model_name="cross-encoder/nli-distilroberta-base",
            revision="b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
            device="cpu",
        )
        if nli
        else None
    )

    config = RunConfig(
        thresholds=RunThresholds(entail=0.8, contradict=0.7),
        require_citations=True,
        citation_style="id",
        phantom_mode="bracket",
        nli_model=nli_cfg,
    )

    try:
        run_result = evaluate_run(dataset, submission, config=config, nli_evaluator=nli)
        _last_run = run_result
        _dataset = dataset
        _submission = submission
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}") from e

    return _format_run_response(run_result, dataset)


@app.post("/api/evaluate/upload")
async def run_upload_evaluation(req: UploadEvaluationRequest):
    """Validate and evaluate user-uploaded dataset and submission."""
    global _last_run, _dataset, _submission

    # 1. Validate Dataset schema
    try:
        parsed_dataset = Dataset.model_validate(req.dataset)
    except ValidationError as e:
        err_msgs = [
            f"Dataset error at '{'.'.join(str(x) for x in err['loc'])}': {err['msg']}"
            for err in e.errors()[:5]
        ]
        raise HTTPException(
            status_code=400, detail=f"Invalid dataset schema: {'; '.join(err_msgs)}"
        ) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Dataset parsing error: {e}") from e

    # 2. Validate Submission schema
    try:
        parsed_submission = Submission.model_validate(req.submission)
    except ValidationError as e:
        err_msgs = [
            f"Submission error at '{'.'.join(str(x) for x in err['loc'])}': {err['msg']}"
            for err in e.errors()[:5]
        ]
        raise HTTPException(
            status_code=400, detail=f"Invalid submission schema: {'; '.join(err_msgs)}"
        ) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Submission parsing error: {e}") from e

    # 3. Cross-document consistency validation
    cross_errors = validate_submission_against_dataset(parsed_dataset, parsed_submission)
    if cross_errors:
        raise HTTPException(
            status_code=400,
            detail=f"Cross-document validation failed: {'; '.join(cross_errors[:5])}",
        )

    # 4. Configure evaluation with NLI if available
    nli = get_nli_evaluator()
    nli_cfg = (
        NLIModelConfig(
            model_name="cross-encoder/nli-distilroberta-base",
            revision="b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
            device="cpu",
        )
        if nli
        else None
    )

    config = RunConfig(
        thresholds=RunThresholds(entail=0.8, contradict=0.7),
        require_citations=req.require_citations,
        citation_style=req.citation_style,
        phantom_mode=req.phantom_mode,
        nli_model=nli_cfg,
    )

    # 5. Run evaluation
    try:
        run_result = evaluate_run(
            parsed_dataset, parsed_submission, config=config, nli_evaluator=nli
        )
        _last_run = run_result
        _dataset = parsed_dataset
        _submission = parsed_submission
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}") from e

    return _format_run_response(run_result, parsed_dataset)


@app.get("/api/evaluate/item/{item_id}")
@app.get("/api/evaluate/sample/item/{item_id}")
async def get_item_detail(item_id: str):
    """Get detailed evidence for a single evaluated item."""
    global _last_run, _dataset, _submission

    if _last_run is None:
        raise HTTPException(
            status_code=404,
            detail="No run available. Run an evaluation first.",
        )

    dataset = _dataset
    submission = _submission
    if dataset is None or submission is None:
        dataset, submission = _load_sample_data()

    item = next((i for i in _last_run.items if i.item_id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found in current run")

    return _item_evidence(item, dataset, submission)


@app.post("/api/evaluate/benchmark/{benchmark_id}")
async def run_benchmark_evaluation(benchmark_id: str, pipeline: str = "a"):
    """Evaluate a pre-configured benchmark with its designated pipeline ('a' or 'b')."""
    global _last_run, _dataset, _submission

    bm = next((b for b in BENCHMARKS if b["id"] == benchmark_id), None)
    if not bm:
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_id}' not found")

    with open(SAMPLE_DATA_DIR / bm["dataset_file"], encoding="utf-8") as f:
        dataset = Dataset.model_validate(json.load(f))

    if pipeline.lower() in ("b", "grounded"):
        if not bm.get("pipeline_b"):
            raise HTTPException(
                status_code=400,
                detail=f"Benchmark '{benchmark_id}' does not have a pipeline B configured",
            )
        sub_file = bm["pipeline_b"]["file"]
    else:
        sub_file = bm["pipeline_a"]["file"]

    with open(SAMPLE_DATA_DIR / sub_file, encoding="utf-8") as f:
        submission = Submission.model_validate(json.load(f))

    nli = get_nli_evaluator()
    nli_cfg = (
        NLIModelConfig(
            model_name="cross-encoder/nli-distilroberta-base",
            revision="b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
            device="cpu",
        )
        if nli
        else None
    )

    config = RunConfig(
        thresholds=RunThresholds(entail=0.8, contradict=0.7),
        require_citations=True,
        citation_style="id",
        phantom_mode="bracket",
        nli_model=nli_cfg,
    )

    try:
        run_result = evaluate_run(dataset, submission, config=config, nli_evaluator=nli)
        _last_run = run_result
        _dataset = dataset
        _submission = submission
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}") from e

    return _format_run_response(run_result, dataset)


@app.post("/api/evaluate/compare")
async def run_comparison_evaluation(req: CompareEvaluationRequest):
    """Run side-by-side evaluation and comparison between two RAG submissions on the same dataset."""
    global _last_run, _dataset, _submission

    if req.benchmark_id:
        bm = next((b for b in BENCHMARKS if b["id"] == req.benchmark_id), None)
        if not bm:
            raise HTTPException(status_code=404, detail=f"Benchmark '{req.benchmark_id}' not found")
        if not bm.get("pipeline_b"):
            raise HTTPException(
                status_code=400,
                detail=f"Benchmark '{req.benchmark_id}' does not have two pipelines for comparison",
            )

        with open(SAMPLE_DATA_DIR / bm["dataset_file"], encoding="utf-8") as f:
            dataset = Dataset.model_validate(json.load(f))
        with open(SAMPLE_DATA_DIR / bm["pipeline_a"]["file"], encoding="utf-8") as f:
            submission_a = Submission.model_validate(json.load(f))
        with open(SAMPLE_DATA_DIR / bm["pipeline_b"]["file"], encoding="utf-8") as f:
            submission_b = Submission.model_validate(json.load(f))
    else:
        if not req.dataset or not req.submission_a or not req.submission_b:
            raise HTTPException(
                status_code=400,
                detail="Custom comparison requires 'dataset', 'submission_a', and 'submission_b'.",
            )

        # Validate Dataset
        try:
            dataset = Dataset.model_validate(req.dataset)
        except ValidationError as e:
            err_msgs = [
                f"Dataset error at '{'.'.join(str(x) for x in err['loc'])}': {err['msg']}"
                for err in e.errors()[:5]
            ]
            raise HTTPException(
                status_code=400, detail=f"Invalid dataset schema: {'; '.join(err_msgs)}"
            ) from e

        # Validate Submission A
        try:
            submission_a = Submission.model_validate(req.submission_a)
        except ValidationError as e:
            err_msgs = [
                f"Submission A error at '{'.'.join(str(x) for x in err['loc'])}': {err['msg']}"
                for err in e.errors()[:5]
            ]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid Submission A schema: {'; '.join(err_msgs)}",
            ) from e

        # Validate Submission B
        try:
            submission_b = Submission.model_validate(req.submission_b)
        except ValidationError as e:
            err_msgs = [
                f"Submission B error at '{'.'.join(str(x) for x in err['loc'])}': {err['msg']}"
                for err in e.errors()[:5]
            ]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid Submission B schema: {'; '.join(err_msgs)}",
            ) from e

        # Validate cross-document consistency
        cross_a = validate_submission_against_dataset(dataset, submission_a)
        if cross_a:
            raise HTTPException(
                status_code=400,
                detail=f"Submission A cross-validation failed: {'; '.join(cross_a[:5])}",
            )

        cross_b = validate_submission_against_dataset(dataset, submission_b)
        if cross_b:
            raise HTTPException(
                status_code=400,
                detail=f"Submission B cross-validation failed: {'; '.join(cross_b[:5])}",
            )

        # Check item compatibility between A and B
        items_a = {o.item_id for o in submission_a.outputs}
        items_b = {o.item_id for o in submission_b.outputs}
        if items_a != items_b:
            diff_a = items_a - items_b
            diff_b = items_b - items_a
            detail = (
                f"Dataset incompatibility between submissions: "
                f"Submission A has items {sorted(items_a)}, but Submission B has items {sorted(items_b)}. "
            )
            if diff_a:
                detail += f"Missing in B: {sorted(diff_a)}. "
            if diff_b:
                detail += f"Missing in A: {sorted(diff_b)}. "
            detail += "Both submissions must evaluate the exact same questions to compare."
            raise HTTPException(status_code=400, detail=detail)

    nli = get_nli_evaluator()
    nli_cfg = (
        NLIModelConfig(
            model_name="cross-encoder/nli-distilroberta-base",
            revision="b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
            device="cpu",
        )
        if nli
        else None
    )

    config = RunConfig(
        thresholds=RunThresholds(entail=0.8, contradict=0.7),
        require_citations=req.require_citations,
        citation_style=req.citation_style,
        phantom_mode=req.phantom_mode,
        nli_model=nli_cfg,
    )

    try:
        res_a = evaluate_run(dataset, submission_a, config=config, nli_evaluator=nli)
        res_b = evaluate_run(dataset, submission_b, config=config, nli_evaluator=nli)
        _last_run = res_a
        _dataset = dataset
        _submission = submission_a
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison evaluation failed: {e}") from e

    return _build_comparison_response(res_a, res_b, dataset, submission_a, submission_b)


@app.get("/api/nli/status")
async def nli_status():
    """Report NLI model status and sanity check results."""
    try:
        from trace_eval.nli import SANITY_PAIRS, NLIEvaluator

        try:
            ev = NLIEvaluator(
                model_name="cross-encoder/nli-distilroberta-base",
                revision="b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
                local_files_only=True,
            )
        except Exception:
            ev = NLIEvaluator(
                model_name="cross-encoder/nli-distilroberta-base",
                revision="b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
                local_files_only=False,
            )
        pairs = [(p[0], p[1]) for p in SANITY_PAIRS]
        preds = ev.predict(pairs)
        checks = []
        all_pass = True
        for i, (_, _, expected) in enumerate(SANITY_PAIRS):
            ok = preds[i].argmax_label == expected
            if not ok:
                all_pass = False
            checks.append(
                {
                    "pair": i + 1,
                    "expected": expected,
                    "predicted": preds[i].argmax_label,
                    "pass": ok,
                    "entail_prob": preds[i].entailment,
                    "contra_prob": preds[i].contradiction,
                    "neutral_prob": preds[i].neutral,
                }
            )
        return {
            "available": True,
            "model": "cross-encoder/nli-distilroberta-base",
            "revision": "b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
            "weights_sha256": "9df3eb5d37118f952f4ba4fb46fde6889e3a9ccedeee0bad09b0110fc64c5c29",
            "all_sanity_pass": all_pass,
            "sanity_checks": checks,
            "id2label": ev.get_id2label_dict(),
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
        }


# ── Static Frontend Serving ───────────────────────────────────────────────────
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve SPA index.html for client-side routing, or static assets."""
    if (
        full_path.startswith("api/")
        or full_path.startswith("docs")
        or full_path.startswith("openapi.json")
    ):
        raise HTTPException(status_code=404, detail="Not Found")
    file_path = FRONTEND_DIST / full_path
    if full_path and file_path.is_file():
        return FileResponse(file_path)
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "TRACE AI API running. Frontend build not found."}
