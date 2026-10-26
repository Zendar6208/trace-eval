"""FastAPI backend for TRACE AI evaluation workbench.

Provides endpoints for:
- Running the bundled sample evaluation
- Retrieving run results with full evidence
- NLI inference status
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from trace_eval.evaluator import evaluate_run
from trace_eval.schema.dataset import Dataset
from trace_eval.schema.run import RunConfig, RunResult, RunThresholds
from trace_eval.schema.submission import Submission

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


def _load_sample_data() -> tuple[Dataset, Submission]:
    global _dataset, _submission
    if _dataset is None:
        with open(SAMPLE_DATA_DIR / "dataset.json", encoding="utf-8") as f:
            _dataset = Dataset.model_validate(json.load(f))
    if _submission is None:
        with open(SAMPLE_DATA_DIR / "submission.json", encoding="utf-8") as f:
            _submission = Submission.model_validate(json.load(f))
    return _dataset, _submission


# ── Helpers ────────────────────────────────────────────────────────────────────
def _item_summary(item: Any) -> dict:
    """Convert a RunItemResult to a frontend-friendly summary dict."""
    m = item.metrics
    ret = m.retrieval
    cor = m.correctness
    cit = m.citation
    gro = m.grounding

    return {
        "item_id": item.item_id,
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
    # Get question from dataset
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
                    "text": retrieved_texts.get(r.id, ""),
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


# ── Routes ─────────────────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return {"service": "TRACE AI", "version": "0.1.0", "status": "ready"}


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/api/evaluate/sample")
async def run_sample_evaluation():
    """Run deterministic Tier-0 evaluation on the bundled sample dataset."""
    global _last_run

    dataset, submission = _load_sample_data()
    config = RunConfig(
        thresholds=RunThresholds(entail=0.8, contradict=0.7),
        require_citations=True,
        citation_style="id",
        phantom_mode="bracket",
    )

    try:
        run_result = evaluate_run(dataset, submission, config=config)
        _last_run = run_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}") from e

    # Build response
    items_summary = [_item_summary(item) for item in run_result.items]

    combined = run_result.summary.combined
    recorded = run_result.summary.recorded_system
    synthetic = run_result.summary.synthetic_fixture

    return {
        "run_id": run_result.run_id,
        "result_hash": run_result.result_hash,
        "methodology_version": "1.0.0",
        "nli_enabled": False,
        "evaluation_tier": "Tier 0 (deterministic)",
        "summary": {
            "combined": combined.model_dump() if combined else None,
            "recorded_system": recorded.model_dump() if recorded else None,
            "synthetic_fixture": synthetic.model_dump() if synthetic else None,
            "failure_distribution": run_result.summary.failure_distribution,
        },
        "items": items_summary,
    }


@app.get("/api/evaluate/sample/item/{item_id}")
async def get_item_detail(item_id: str):
    """Get detailed evidence for a single evaluated item."""
    global _last_run

    if _last_run is None:
        raise HTTPException(
            status_code=404,
            detail="No run available. Run /api/evaluate/sample first.",
        )

    dataset, submission = _load_sample_data()

    item = next((i for i in _last_run.items if i.item_id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found in last run")

    return _item_evidence(item, dataset, submission)


@app.get("/api/nli/status")
async def nli_status():
    """Report NLI model status and sanity check results."""
    try:
        from trace_eval.nli import SANITY_PAIRS, NLIEvaluator

        ev = NLIEvaluator(
            model_name="cross-encoder/nli-distilroberta-base",
            revision="b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
            local_files_only=True,
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
