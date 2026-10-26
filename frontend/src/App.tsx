import React, { useState } from 'react';
import {
  Play,
  CheckCircle2,
  AlertTriangle,
  ArrowLeft,
  Upload,
  Download,
  FileText,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Copy,
  Check,
  Sparkles,
  HelpCircle,
  X
} from 'lucide-react';
import type { EvaluationRunResponse, ItemDetailResponse } from './types';

// Human-friendly failure explanations
const FAILURE_LABELS: Record<string, { title: string; desc: string }> = {
  RETRIEVAL_MISS: {
    title: 'Wrong information retrieved',
    desc: 'The retrieval component failed to find the gold passages containing the facts required to answer this question.',
  },
  WRONG_ANSWER: {
    title: 'Answer does not match expected facts',
    desc: 'The AI model generated an answer that omits mandatory facts or contradicts the verified reference answer.',
  },
  BAD_CITATION: {
    title: 'Citation does not support claim',
    desc: 'The cited passage was retrieved, but its text does not logically entail or prove the sentence making the claim.',
  },
  UNSUPPORTED_CLAIM: {
    title: 'Statement lacks supporting evidence',
    desc: 'The AI made a factual claim that cannot be verified by any retrieved passage in the context.',
  },
  CONTRADICTS_REFERENCE: {
    title: 'Contradicts ground truth',
    desc: 'The answer directly contradicts the verified reference answer.',
  },
  PHANTOM_CITATION: {
    title: 'Phantom citation detected',
    desc: 'The AI cited a passage ID that was never retrieved or does not exist.',
  },
};

function formatPercent(val: number | null | undefined): string {
  if (val === null || val === undefined) return 'Not evaluated';
  return `${Math.round(val * 100)}%`;
}

function formatDecimal(val: number | null | undefined): string {
  if (val === null || val === undefined) return '—';
  return val.toFixed(3);
}

export default function App() {
  // Navigation / View State
  const [runData, setRunData] = useState<EvaluationRunResponse | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [itemDetail, setItemDetail] = useState<ItemDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Upload State
  const [datasetFile, setDatasetFile] = useState<File | null>(null);
  const [submissionFile, setSubmissionFile] = useState<File | null>(null);
  const [requireCitations, setRequireCitations] = useState(true);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // UI Modals / Toggles
  const [showHowItWorks, setShowHowItWorks] = useState(false);
  const [showAdvancedMetrics, setShowAdvancedMetrics] = useState(false);
  const [copiedHash, setCopiedHash] = useState(false);
  const [filterStatus, setFilterStatus] = useState<'all' | 'failed' | 'passed'>('all');

  // ── Handlers ──────────────────────────────────────────────────────────────────

  const runSampleEvaluation = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/evaluate/sample', { method: 'POST' });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP error ${res.status}`);
      }
      const data: EvaluationRunResponse = await res.json();
      setRunData(data);
      if (data.items.length > 0) {
        selectItem(data.items[0].item_id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to run sample evaluation');
    } finally {
      setLoading(false);
    }
  };

  const handleUploadEvaluation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!datasetFile || !submissionFile) {
      setUploadError('Please select both dataset.json and submission.json files.');
      return;
    }

    setLoading(true);
    setUploadError(null);
    try {
      const datasetText = await datasetFile.text();
      const submissionText = await submissionFile.text();

      let datasetJson: any;
      let submissionJson: any;

      try {
        datasetJson = JSON.parse(datasetText);
      } catch {
        throw new Error('Dataset file is not valid JSON.');
      }

      try {
        submissionJson = JSON.parse(submissionText);
      } catch {
        throw new Error('Submission file is not valid JSON.');
      }

      const res = await fetch('/api/evaluate/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset: datasetJson,
          submission: submissionJson,
          require_citations: requireCitations,
          citation_style: 'id',
          phantom_mode: 'bracket',
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `HTTP ${res.status}: Upload evaluation failed.`);
      }

      const result: EvaluationRunResponse = await res.json();
      setRunData(result);
      if (result.items.length > 0) {
        selectItem(result.items[0].item_id);
      }
    } catch (err: any) {
      setUploadError(err.message || 'Upload evaluation failed.');
    } finally {
      setLoading(false);
    }
  };

  const selectItem = async (itemId: string) => {
    setSelectedItemId(itemId);
    setDetailLoading(true);
    try {
      const res = await fetch(`/api/evaluate/item/${itemId}`);
      if (!res.ok) {
        throw new Error(`Failed to load evidence for item ${itemId}`);
      }
      const data: ItemDetailResponse = await res.json();
      setItemDetail(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setDetailLoading(false);
    }
  };

  const copyHashToClipboard = () => {
    if (runData?.result_hash) {
      navigator.clipboard.writeText(runData.result_hash);
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 2000);
    }
  };

  const downloadSample = async (type: 'dataset' | 'submission') => {
    try {
      const res = await fetch(`/api/sample/${type}`);
      if (!res.ok) throw new Error('Failed to fetch template');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sample-${type}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(`Error downloading sample: ${err}`);
    }
  };

  // Filtered items
  const filteredItems = (runData?.items || []).filter((item) => {
    if (filterStatus === 'failed') return item.failure_types.length > 0;
    if (filterStatus === 'passed') return item.failure_types.length === 0;
    return true;
  });

  return (
    <div className="min-h-screen bg-[#F8F7F4] text-[#171717] font-sans antialiased flex flex-col selection:bg-[#E4EBE4] selection:text-[#174D3A]">
      {/* ── Header ── */}
      <header className="border-b border-[#E5E3DD] bg-[#FFFFFF]/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-[#174D3A] text-white flex items-center justify-center font-serif font-black text-lg shadow-xs">
              T
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-serif font-bold text-xl tracking-tight text-[#171717]">
                  TRACE.
                </span>
                <span className="text-[11px] font-mono uppercase tracking-wider bg-[#E4EBE4] text-[#174D3A] px-2 py-0.5 rounded font-semibold">
                  v1.0.0 Normative
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <button
              onClick={() => setShowHowItWorks(true)}
              className="inline-flex items-center gap-1.5 text-[#73736D] hover:text-[#171717] font-medium transition cursor-pointer"
            >
              <HelpCircle className="w-4 h-4" />
              <span>How it works</span>
            </button>
            <div className="h-4 w-[1px] bg-[#E5E3DD]" />
            <a
              href="https://github.com/darshan-sheth/trace-eval"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-[#73736D] hover:text-[#171717] font-medium transition"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>GitHub</span>
            </a>
          </div>
        </div>
      </header>

      {/* ── Main Content Area ── */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
        {!runData ? (
          /* ══════════════════════════════════════════════════════════════════════
             SCREEN 1: SIMPLE EVALUATION WORKSPACE
             ══════════════════════════════════════════════════════════════════════ */
          <div className="space-y-12 max-w-4xl mx-auto pt-6 pb-16">
            {/* Hero */}
            <div className="text-center space-y-4">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#E4EBE4] text-[#174D3A] text-xs font-medium">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Deterministic-First RAG Evaluation</span>
              </div>
              <h1 className="text-4xl sm:text-5xl font-serif font-bold tracking-tight text-[#171717]">
                Know when your AI gets it wrong.
              </h1>
              <p className="text-lg text-[#73736D] max-w-2xl mx-auto leading-relaxed">
                Evaluate your RAG system's answers, citations and retrieved evidence. Detect unsupported
                claims, phantom citations, and retrieval misses with mathematical precision.
              </p>
            </div>

            {/* Error Message if any */}
            {error && (
              <div className="p-4 rounded-lg bg-[#FBEBE8] border border-[#C4513D]/20 text-[#C4513D] text-sm flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-semibold">Evaluation failed</p>
                  <p>{error}</p>
                </div>
              </div>
            )}

            {/* Workspace Choices */}
            <div className="space-y-4">
              <h2 className="text-xs font-mono uppercase tracking-wider text-[#73736D] font-semibold text-center">
                What would you like to evaluate?
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-stretch">
                {/* Option 1: Sample Evaluation */}
                <div className="bg-[#FFFFFF] border border-[#E5E3DD] rounded-xl p-6 flex flex-col justify-between shadow-xs hover:border-[#174D3A]/40 transition-colors">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-medium bg-[#E4EBE4] text-[#174D3A] px-2.5 py-1 rounded">
                        Instant • 5 benchmark cases
                      </span>
                      <ShieldCheck className="w-5 h-5 text-[#174D3A]" />
                    </div>

                    <div>
                      <h3 className="font-serif text-xl font-bold text-[#171717]">
                        Try Sample Evaluation
                      </h3>
                      <p className="text-sm text-[#73736D] mt-2 leading-relaxed">
                        Test TRACE AI with a curated 5-case RAG benchmark covering enterprise customer support,
                        warranty policy lookups, phantom citations, and unsupported answer detection.
                      </p>
                    </div>

                    <div className="space-y-2 pt-2 text-xs text-[#73736D] border-t border-[#E5E3DD]/60">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-[#2E6B4F]" />
                        <span>Pre-configured dataset & model responses</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-[#2E6B4F]" />
                        <span>Real local NLI cross-encoder inference</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-[#2E6B4F]" />
                        <span>Sentence-level claim and citation verification</span>
                      </div>
                    </div>
                  </div>

                  <div className="pt-6">
                    <button
                      onClick={runSampleEvaluation}
                      disabled={loading}
                      className="w-full inline-flex items-center justify-center gap-2 bg-[#174D3A] hover:bg-[#123e2e] text-white font-medium py-3 px-4 rounded-lg transition-colors cursor-pointer disabled:opacity-50 text-sm shadow-xs"
                    >
                      {loading ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          <span>Evaluating benchmark...</span>
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 fill-white" />
                          <span>Run Sample Evaluation</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Option 2: Upload Evaluation */}
                <div className="bg-[#FFFFFF] border border-[#E5E3DD] rounded-xl p-6 flex flex-col justify-between shadow-xs hover:border-[#174D3A]/40 transition-colors">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-medium bg-[#F8F7F4] text-[#73736D] border border-[#E5E3DD] px-2.5 py-1 rounded">
                        Custom Run
                      </span>
                      <Upload className="w-5 h-5 text-[#73736D]" />
                    </div>

                    <div>
                      <h3 className="font-serif text-xl font-bold text-[#171717]">
                        Upload Evaluation Data
                      </h3>
                      <p className="text-sm text-[#73736D] mt-2 leading-relaxed">
                        Evaluate your own RAG system by uploading your dataset and submission JSON files conforming
                        to the TRACE AI schema.
                      </p>
                    </div>

                    <form id="upload-form" onSubmit={handleUploadEvaluation} className="space-y-3 pt-1">
                      {/* Dataset input */}
                      <div>
                        <label className="block text-xs font-medium text-[#171717] mb-1">
                          Dataset JSON (<span className="font-mono text-[11px]">trace.dataset/1.0</span>)
                        </label>
                        <input
                          type="file"
                          accept=".json"
                          onChange={(e) => setDatasetFile(e.target.files?.[0] || null)}
                          className="w-full text-xs text-[#73736D] file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-[#E4EBE4] file:text-[#174D3A] hover:file:bg-[#d5e2d5] file:cursor-pointer border border-[#E5E3DD] rounded p-1 bg-[#F8F7F4]"
                        />
                      </div>

                      {/* Submission input */}
                      <div>
                        <label className="block text-xs font-medium text-[#171717] mb-1">
                          Submission JSON (<span className="font-mono text-[11px]">trace.submission/1.0</span>)
                        </label>
                        <input
                          type="file"
                          accept=".json"
                          onChange={(e) => setSubmissionFile(e.target.files?.[0] || null)}
                          className="w-full text-xs text-[#73736D] file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-[#E4EBE4] file:text-[#174D3A] hover:file:bg-[#d5e2d5] file:cursor-pointer border border-[#E5E3DD] rounded p-1 bg-[#F8F7F4]"
                        />
                      </div>

                      {/* Require Citations */}
                      <label className="flex items-center gap-2 pt-1 text-xs text-[#171717] cursor-pointer">
                        <input
                          type="checkbox"
                          checked={requireCitations}
                          onChange={(e) => setRequireCitations(e.target.checked)}
                          className="rounded border-[#E5E3DD] text-[#174D3A] focus:ring-[#174D3A]"
                        />
                        <span>Require & evaluate citations</span>
                      </label>

                      {/* Download templates */}
                      <div className="flex items-center gap-3 pt-1 text-[11px] text-[#73736D]">
                        <button
                          type="button"
                          onClick={() => downloadSample('dataset')}
                          className="inline-flex items-center gap-1 hover:text-[#174D3A] underline cursor-pointer"
                        >
                          <Download className="w-3 h-3" />
                          <span>Sample dataset.json</span>
                        </button>
                        <span>•</span>
                        <button
                          type="button"
                          onClick={() => downloadSample('submission')}
                          className="inline-flex items-center gap-1 hover:text-[#174D3A] underline cursor-pointer"
                        >
                          <Download className="w-3 h-3" />
                          <span>Sample submission.json</span>
                        </button>
                      </div>

                      {uploadError && (
                        <div className="p-2.5 rounded bg-[#FBEBE8] border border-[#C4513D]/30 text-[#C4513D] text-xs">
                          {uploadError}
                        </div>
                      )}
                    </form>
                  </div>

                  <div className="pt-6">
                    <button
                      type="submit"
                      form="upload-form"
                      disabled={loading || !datasetFile || !submissionFile}
                      className="w-full inline-flex items-center justify-center gap-2 bg-[#171717] hover:bg-[#333333] text-white font-medium py-3 px-4 rounded-lg transition-colors cursor-pointer disabled:opacity-40 text-sm shadow-xs"
                    >
                      {loading ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          <span>Validating & evaluating...</span>
                        </>
                      ) : (
                        <>
                          <Upload className="w-4 h-4" />
                          <span>Evaluate Uploaded Files</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* ══════════════════════════════════════════════════════════════════════
             SCREEN 2 & 3: CLEAN RESULTS WORKSPACE & SIGNATURE EVIDENCE INSPECTOR
             ══════════════════════════════════════════════════════════════════════ */
          <div className="space-y-8">
            {/* Navigation & Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E5E3DD]">
              <div>
                <button
                  onClick={() => {
                    setRunData(null);
                    setSelectedItemId(null);
                    setItemDetail(null);
                  }}
                  className="inline-flex items-center gap-1.5 text-xs text-[#73736D] hover:text-[#171717] font-medium mb-2 cursor-pointer transition"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Back to Evaluation Workspace</span>
                </button>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl sm:text-3xl font-serif font-bold text-[#171717]">
                    Evaluation complete.
                  </h1>
                  <span className="text-xs font-mono bg-[#EBF3EE] text-[#2E6B4F] border border-[#2E6B4F]/20 px-2 py-0.5 rounded font-medium">
                    {runData.evaluation_tier === 'tier_0'
                      ? 'Tier 0 — Deterministic evaluation'
                      : 'Tier 1 — Hybrid Deterministic + NLI'}
                  </span>
                </div>
              </div>

              {/* Provenance strip */}
              <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-[#73736D] bg-[#FFFFFF] border border-[#E5E3DD] p-2.5 rounded-lg shadow-xs">
                <div>
                  <span className="text-[#9E9E98]">Run ID: </span>
                  <span className="text-[#171717] font-semibold">{runData.run_id.slice(0, 16)}...</span>
                </div>
                <div className="h-3 w-[1px] bg-[#E5E3DD]" />
                <div className="flex items-center gap-1.5">
                  <span className="text-[#9E9E98]">Result Hash: </span>
                  <span className="text-[#171717] font-semibold">{runData.result_hash.slice(0, 14)}...</span>
                  <button
                    onClick={copyHashToClipboard}
                    title="Copy full cryptographic result hash"
                    className="hover:text-[#174D3A] cursor-pointer p-0.5"
                  >
                    {copiedHash ? <Check className="w-3.5 h-3.5 text-[#2E6B4F]" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            </div>

            {/* ── 4 Primary Evaluation Dimensions ── */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-mono uppercase tracking-wider text-[#73736D] font-semibold">
                  Primary Evaluation Dimensions
                </h2>
                <span className="text-xs text-[#73736D]">
                  {runData.items.length} question{runData.items.length === 1 ? '' : 's'} evaluated
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* 1. Retrieval Relevance */}
                <div className="bg-[#FFFFFF] border border-[#E5E3DD] rounded-xl p-5 shadow-xs flex flex-col justify-between">
                  <div className="space-y-1">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#73736D] font-semibold">
                      Dimension 1
                    </span>
                    <h3 className="font-serif text-lg font-bold text-[#171717]">Retrieval Relevance</h3>
                    <p className="text-xs text-[#73736D] italic">
                      Did the system retrieve the right evidence?
                    </p>
                  </div>
                  <div className="mt-4 pt-4 border-t border-[#E5E3DD]/60">
                    <div className="text-3xl font-serif font-black text-[#174D3A]">
                      {(() => {
                        const items = runData.items.filter((i) => i.retrieval?.hit_at_k?.['5'] !== undefined);
                        if (!items.length) return 'Not evaluated';
                        const avg = items.reduce((acc, i) => acc + (i.retrieval?.hit_at_k?.['5'] || 0), 0) / items.length;
                        return formatPercent(avg);
                      })()}
                    </div>
                    <div className="text-[11px] text-[#73736D] mt-1 flex items-center justify-between font-mono">
                      <span>Recall@5: {formatPercent(runData.items.reduce((acc, i) => acc + (i.retrieval?.recall_at_k?.['5'] || 0), 0) / (runData.items.length || 1))}</span>
                      <span>MRR: {formatDecimal(runData.items.reduce((acc, i) => acc + (i.retrieval?.mrr || 0), 0) / (runData.items.length || 1))}</span>
                    </div>
                  </div>
                </div>

                {/* 2. Answer Correctness */}
                <div className="bg-[#FFFFFF] border border-[#E5E3DD] rounded-xl p-5 shadow-xs flex flex-col justify-between">
                  <div className="space-y-1">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#73736D] font-semibold">
                      Dimension 2
                    </span>
                    <h3 className="font-serif text-lg font-bold text-[#171717]">Answer Correctness</h3>
                    <p className="text-xs text-[#73736D] italic">
                      Did the response contain all required facts?
                    </p>
                  </div>
                  <div className="mt-4 pt-4 border-t border-[#E5E3DD]/60">
                    <div className="text-3xl font-serif font-black text-[#174D3A]">
                      {formatPercent(runData.summary.combined?.mean_fact_recall)}
                    </div>
                    <div className="text-[11px] text-[#73736D] mt-1 flex items-center justify-between font-mono">
                      <span>Mean Fact Recall</span>
                      <span>Token F1: {formatDecimal(runData.summary.combined?.mean_token_f1)}</span>
                    </div>
                  </div>
                </div>

                {/* 3. Citation Quality */}
                <div className="bg-[#FFFFFF] border border-[#E5E3DD] rounded-xl p-5 shadow-xs flex flex-col justify-between">
                  <div className="space-y-1">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#73736D] font-semibold">
                      Dimension 3
                    </span>
                    <h3 className="font-serif text-lg font-bold text-[#171717]">Citation Quality</h3>
                    <p className="text-xs text-[#73736D] italic">
                      Are citations pointing to real, retrieved sources?
                    </p>
                  </div>
                  <div className="mt-4 pt-4 border-t border-[#E5E3DD]/60">
                    <div className="text-3xl font-serif font-black text-[#174D3A]">
                      {formatPercent(runData.summary.combined?.mean_citation_precision)}
                    </div>
                    <div className="text-[11px] text-[#73736D] mt-1 flex items-center justify-between font-mono">
                      <span>Citation Precision</span>
                      <span>Phantom Rate: {formatPercent(runData.summary.combined?.mean_phantom_rate)}</span>
                    </div>
                  </div>
                </div>

                {/* 4. Grounding & Faithfulness */}
                <div className="bg-[#FFFFFF] border border-[#E5E3DD] rounded-xl p-5 shadow-xs flex flex-col justify-between">
                  <div className="space-y-1">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#73736D] font-semibold">
                      Dimension 4
                    </span>
                    <h3 className="font-serif text-lg font-bold text-[#171717]">Grounding & Faithfulness</h3>
                    <p className="text-xs text-[#73736D] italic">
                      Is every factual statement backed by evidence?
                    </p>
                  </div>
                  <div className="mt-4 pt-4 border-t border-[#E5E3DD]/60">
                    <div className="text-3xl font-serif font-black text-[#174D3A]">
                      {(() => {
                        const rate = runData.summary.combined?.mean_unsupported_claim_rate;
                        if (rate === null || rate === undefined) return 'Not evaluated';
                        return formatPercent(1 - rate);
                      })()}
                    </div>
                    <div className="text-[11px] text-[#73736D] mt-1 flex items-center justify-between font-mono">
                      <span>Supported Claim Rate</span>
                      <span>Unsupported: {formatPercent(runData.summary.combined?.mean_unsupported_claim_rate)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Evaluated Questions & Evidence Inspector Split Layout ── */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left Column: Questions List (5 cols on lg) */}
              <div className="lg:col-span-5 bg-[#FFFFFF] border border-[#E5E3DD] rounded-xl shadow-xs overflow-hidden">
                <div className="p-4 border-b border-[#E5E3DD] flex items-center justify-between bg-[#F8F7F4]/50">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-[#174D3A]" />
                    <span className="font-serif font-bold text-sm text-[#171717]">Evaluated Questions</span>
                  </div>

                  {/* Filter tabs */}
                  <div className="flex items-center gap-1 text-[11px] font-mono bg-[#FFFFFF] border border-[#E5E3DD] p-0.5 rounded">
                    <button
                      onClick={() => setFilterStatus('all')}
                      className={`px-2 py-0.5 rounded cursor-pointer transition ${
                        filterStatus === 'all' ? 'bg-[#174D3A] text-white font-semibold' : 'text-[#73736D] hover:text-[#171717]'
                      }`}
                    >
                      All ({runData.items.length})
                    </button>
                    <button
                      onClick={() => setFilterStatus('failed')}
                      className={`px-2 py-0.5 rounded cursor-pointer transition ${
                        filterStatus === 'failed' ? 'bg-[#C4513D] text-white font-semibold' : 'text-[#73736D] hover:text-[#171717]'
                      }`}
                    >
                      Failed ({runData.items.filter((i) => i.failure_types.length > 0).length})
                    </button>
                    <button
                      onClick={() => setFilterStatus('passed')}
                      className={`px-2 py-0.5 rounded cursor-pointer transition ${
                        filterStatus === 'passed' ? 'bg-[#2E6B4F] text-white font-semibold' : 'text-[#73736D] hover:text-[#171717]'
                      }`}
                    >
                      Passed ({runData.items.filter((i) => i.failure_types.length === 0).length})
                    </button>
                  </div>
                </div>

                <div className="divide-y divide-[#E5E3DD] max-h-[680px] overflow-y-auto">
                  {filteredItems.map((item) => {
                    const isSelected = item.item_id === selectedItemId;
                    const hasFailures = item.failure_types.length > 0;

                    return (
                      <button
                        key={item.item_id}
                        onClick={() => selectItem(item.item_id)}
                        className={`w-full text-left p-4 transition cursor-pointer flex flex-col gap-2 ${
                          isSelected
                            ? 'bg-[#E4EBE4]/40 border-l-4 border-l-[#174D3A]'
                            : 'hover:bg-[#F8F7F4] border-l-4 border-l-transparent'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-xs text-[#171717]">{item.item_id}</span>
                            <span className="text-[10px] font-mono uppercase tracking-wider text-[#73736D] bg-[#F8F7F4] border border-[#E5E3DD] px-1.5 py-0.5 rounded">
                              {item.origin === 'recorded_system' ? 'Recorded' : 'Fixture'}
                            </span>
                          </div>

                          {/* Verdict Badge */}
                          {hasFailures ? (
                            <span className="text-[11px] font-medium bg-[#FBEBE8] text-[#C4513D] border border-[#C4513D]/20 px-2 py-0.5 rounded-full flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" />
                              <span>{item.failure_types.length} failure{item.failure_types.length === 1 ? '' : 's'}</span>
                            </span>
                          ) : (
                            <span className="text-[11px] font-medium bg-[#EBF3EE] text-[#2E6B4F] border border-[#2E6B4F]/20 px-2 py-0.5 rounded-full flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" />
                              <span>Pass</span>
                            </span>
                          )}
                        </div>

                        {/* Human Translated Failure Labels */}
                        {hasFailures ? (
                          <div className="flex flex-wrap gap-1 mt-0.5">
                            {item.failure_types.map((ft) => (
                              <span
                                key={ft}
                                className="text-[10px] font-medium bg-[#FBEBE8] text-[#C4513D] px-1.5 py-0.5 rounded"
                              >
                                {FAILURE_LABELS[ft]?.title || ft}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-xs text-[#73736D]">All checks passed</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Right Column: Signature Evidence Inspector (7 cols on lg) */}
              <div className="lg:col-span-7 space-y-6">
                {detailLoading ? (
                  <div className="bg-[#FFFFFF] border border-[#E5E3DD] rounded-xl p-12 text-center shadow-xs">
                    <div className="w-6 h-6 border-2 border-[#174D3A] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                    <p className="text-sm text-[#73736D]">Loading item evidence and grounding trace...</p>
                  </div>
                ) : itemDetail ? (
                  <div className="bg-[#FFFFFF] border border-[#E5E3DD] rounded-xl shadow-xs p-6 space-y-6">
                    {/* Header: Question & Origin */}
                    <div className="border-b border-[#E5E3DD] pb-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-[#174D3A] bg-[#E4EBE4] px-2 py-0.5 rounded">
                            {itemDetail.item_id}
                          </span>
                          <span className="text-xs font-mono text-[#73736D]">
                            Origin: {itemDetail.origin === 'recorded_system' ? 'Recorded RAG System' : 'Synthetic Fixture'}
                          </span>
                        </div>

                        {itemDetail.failure_types.length === 0 ? (
                          <span className="text-xs font-medium bg-[#EBF3EE] text-[#2E6B4F] px-2.5 py-1 rounded-full flex items-center gap-1.5">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Evaluation Passed</span>
                          </span>
                        ) : (
                          <span className="text-xs font-medium bg-[#FBEBE8] text-[#C4513D] px-2.5 py-1 rounded-full flex items-center gap-1.5">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            <span>{itemDetail.failure_types.length} Failure{itemDetail.failure_types.length === 1 ? '' : 's'} Detected</span>
                          </span>
                        )}
                      </div>

                      <h2 className="font-serif text-xl sm:text-2xl font-bold text-[#171717] leading-snug">
                        {itemDetail.question || 'Question text not available'}
                      </h2>
                    </div>

                    {/* What Went Wrong Banner */}
                    {itemDetail.failure_types.length > 0 ? (
                      <div className="p-4 rounded-lg bg-[#FBEBE8] border border-[#C4513D]/20 space-y-2">
                        <div className="flex items-center gap-2 text-[#C4513D] font-bold text-sm">
                          <AlertTriangle className="w-4 h-4 shrink-0" />
                          <span>What went wrong</span>
                        </div>
                        <ul className="text-xs text-[#171717] space-y-1.5 pl-6 list-disc">
                          {itemDetail.failure_types.map((ft) => (
                            <li key={ft}>
                              <strong className="text-[#C4513D]">{FAILURE_LABELS[ft]?.title || ft}:</strong>{' '}
                              <span className="text-[#73736D]">{FAILURE_LABELS[ft]?.desc}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : (
                      <div className="p-4 rounded-lg bg-[#EBF3EE] border border-[#2E6B4F]/20 flex items-center gap-2.5 text-xs text-[#2E6B4F]">
                        <CheckCircle2 className="w-4 h-4 shrink-0" />
                        <span>All claims were successfully entailed by retrieved passages and citations are verified.</span>
                      </div>
                    )}

                    {/* Answers Comparison */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* AI Response */}
                      <div className="border border-[#E5E3DD] rounded-lg p-4 bg-[#F8F7F4]/60 space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-mono font-bold text-[#171717] uppercase tracking-wider">AI System Answer</span>
                          <span className="text-[11px] text-[#73736D] font-mono">Evaluated</span>
                        </div>
                        <p className="text-xs text-[#171717] leading-relaxed whitespace-pre-wrap">
                          {itemDetail.answer || <span className="text-[#73736D] italic">No answer provided</span>}
                        </p>
                      </div>

                      {/* Reference Gold Answer */}
                      <div className="border border-[#E5E3DD] rounded-lg p-4 bg-[#FFFFFF] space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-mono font-bold text-[#171717] uppercase tracking-wider">Reference Answer (Gold)</span>
                          <span className="text-[11px] text-[#2E6B4F] font-mono">Ground Truth</span>
                        </div>
                        <p className="text-xs text-[#73736D] leading-relaxed">
                          {itemDetail.reference_answers?.[0] || 'No reference answer provided'}
                        </p>
                        {itemDetail.required_facts?.length > 0 && (
                          <div className="pt-2 border-t border-[#E5E3DD]/60">
                            <span className="text-[10px] font-mono uppercase text-[#73736D] block mb-1">Required Facts:</span>
                            <ul className="text-[11px] text-[#73736D] space-y-1 list-disc pl-4">
                              {itemDetail.required_facts.map((rf) => (
                                <li key={rf.fact_id}>{rf.text}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Sentence-by-Sentence Grounding & Citation Diagnostics */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <h3 className="font-serif text-base font-bold text-[#171717]">
                          Sentence Grounding & Citation Trace
                        </h3>
                        <span className="text-xs text-[#73736D] font-mono">
                          {itemDetail.claims?.length || 0} sentence{itemDetail.claims?.length === 1 ? '' : 's'}
                        </span>
                      </div>

                      <div className="space-y-3">
                        {itemDetail.claims && itemDetail.claims.length > 0 ? (
                          itemDetail.claims.map((claim) => {
                            // Find citations attached to this sentence
                            const attachedCitations = (itemDetail.citations || []).filter(
                              (c) => c.sentence_index === claim.sentence_index
                            );

                            return (
                              <div
                                key={claim.sentence_index}
                                className={`border rounded-lg p-3.5 space-y-2 text-xs ${
                                  claim.grounding_label === 'supported'
                                    ? 'bg-[#EBF3EE]/30 border-[#2E6B4F]/30'
                                    : claim.grounding_label === 'contradicted'
                                    ? 'bg-[#FBEBE8]/40 border-[#C4513D]/40'
                                    : claim.grounding_label === 'unsupported'
                                    ? 'bg-[#FBEBE8]/20 border-[#C4513D]/20'
                                    : 'bg-[#F8F7F4] border-[#E5E3DD]'
                                }`}
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <div className="flex items-start gap-2">
                                    <span className="font-mono text-[11px] font-bold text-[#73736D] bg-[#FFFFFF] border border-[#E5E3DD] px-1.5 py-0.5 rounded">
                                      S{claim.sentence_index + 1}
                                    </span>
                                    <p className="text-xs text-[#171717] font-medium leading-relaxed">
                                      "{claim.sentence_text}"
                                    </p>
                                  </div>

                                  {/* Grounding label badge */}
                                  <span
                                    className={`shrink-0 font-mono text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                                      claim.grounding_label === 'supported'
                                        ? 'bg-[#2E6B4F] text-white'
                                        : claim.grounding_label === 'contradicted'
                                        ? 'bg-[#C4513D] text-white'
                                        : claim.grounding_label === 'unsupported'
                                        ? 'bg-[#FBEBE8] text-[#C4513D] border border-[#C4513D]/30'
                                        : 'bg-[#E5E3DD] text-[#73736D]'
                                    }`}
                                  >
                                    {claim.grounding_label}
                                  </span>
                                </div>

                                {/* Probabilities & Numeric Guard */}
                                <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono text-[#73736D] pt-1 border-t border-[#E5E3DD]/40">
                                  {claim.best_entail_prob !== null && (
                                    <span>Entailment: {formatDecimal(claim.best_entail_prob)}</span>
                                  )}
                                  {claim.best_contradict_prob !== null && (
                                    <span>Contradiction: {formatDecimal(claim.best_contradict_prob)}</span>
                                  )}
                                  {claim.numeric_guard_triggered && (
                                    <span className="text-[#C4513D] font-bold bg-[#FBEBE8] px-1.5 py-0.5 rounded">
                                      Numeric Guard Triggered
                                    </span>
                                  )}
                                </div>

                                {/* Attached Citations */}
                                {attachedCitations.length > 0 && (
                                  <div className="pt-2 space-y-1">
                                    <span className="text-[10px] font-mono uppercase text-[#73736D] block">
                                      Attached Citations:
                                    </span>
                                    <div className="flex flex-wrap gap-2">
                                      {attachedCitations.map((cit, idx) => (
                                        <div
                                          key={idx}
                                          className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-mono border ${
                                            cit.validity === 'ok' && cit.supports
                                              ? 'bg-[#EBF3EE] border-[#2E6B4F]/30 text-[#2E6B4F]'
                                              : 'bg-[#FBEBE8] border-[#C4513D]/30 text-[#C4513D]'
                                          }`}
                                        >
                                          <span className="font-bold">[{cit.passage_id}]</span>
                                          <span>•</span>
                                          <span>
                                            {cit.validity === 'ok'
                                              ? cit.supports
                                                ? 'Supports Claim'
                                                : 'Fails to Support'
                                              : cit.validity === 'not_retrieved'
                                              ? 'Not Retrieved (Phantom)'
                                              : cit.validity}
                                          </span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })
                        ) : (
                          <p className="text-xs text-[#73736D] italic">No sentence claims evaluated for this item.</p>
                        )}
                      </div>
                    </div>

                    {/* Retrieved Evidence Passages */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <h3 className="font-serif text-base font-bold text-[#171717]">Retrieved Evidence Passages</h3>
                        <span className="text-xs text-[#73736D] font-mono">
                          {itemDetail.retrieved?.length || 0} retrieved
                        </span>
                      </div>

                      <div className="space-y-2">
                        {itemDetail.retrieved && itemDetail.retrieved.length > 0 ? (
                          itemDetail.retrieved.map((p, idx) => {
                            return (
                              <div
                                key={p.id}
                                className="border border-[#E5E3DD] rounded-lg p-3 bg-[#FFFFFF] space-y-1.5 text-xs shadow-2xs"
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <span className="font-mono font-bold text-[#174D3A] bg-[#E4EBE4] px-1.5 py-0.5 rounded text-[11px]">
                                      {p.id}
                                    </span>
                                    <span className="text-[11px] text-[#73736D] font-mono">Rank #{idx + 1}</span>
                                  </div>
                                  {p.score !== null && (
                                    <span className="text-[11px] font-mono text-[#73736D]">
                                      Score: {formatDecimal(p.score)}
                                    </span>
                                  )}
                                </div>
                                <p className="text-xs text-[#171717] leading-relaxed line-clamp-3 hover:line-clamp-none transition-all">
                                  {p.text}
                                </p>
                              </div>
                            );
                          })
                        ) : (
                          <p className="text-xs text-[#73736D] italic">No retrieved passages recorded.</p>
                        )}
                      </div>
                    </div>

                    {/* Collapsible Advanced Metrics */}
                    <div className="border-t border-[#E5E3DD] pt-4">
                      <button
                        onClick={() => setShowAdvancedMetrics(!showAdvancedMetrics)}
                        className="inline-flex items-center gap-2 text-xs font-mono font-semibold text-[#174D3A] hover:underline cursor-pointer"
                      >
                        {showAdvancedMetrics ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        <span>{showAdvancedMetrics ? 'Hide Advanced Metrics' : 'Show Advanced Metrics & Scores'}</span>
                      </button>

                      {showAdvancedMetrics && (
                        <div className="mt-4 p-4 rounded-lg bg-[#F8F7F4] border border-[#E5E3DD] grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
                          <div>
                            <span className="text-[10px] text-[#73736D] uppercase block">Hit@1</span>
                            <span className="font-bold text-[#171717]">{itemDetail.retrieval?.hit_at_k?.['1'] ?? '—'}</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-[#73736D] uppercase block">Hit@5</span>
                            <span className="font-bold text-[#171717]">{itemDetail.retrieval?.hit_at_k?.['5'] ?? '—'}</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-[#73736D] uppercase block">MRR</span>
                            <span className="font-bold text-[#171717]">{formatDecimal(itemDetail.retrieval?.mrr)}</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-[#73736D] uppercase block">nDCG@5</span>
                            <span className="font-bold text-[#171717]">{formatDecimal(itemDetail.retrieval?.ndcg_at_k?.['5'])}</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-[#73736D] uppercase block">Fact Recall</span>
                            <span className="font-bold text-[#171717]">{formatPercent(itemDetail.correctness?.fact_recall)}</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-[#73736D] uppercase block">Token F1</span>
                            <span className="font-bold text-[#171717]">{formatDecimal(itemDetail.correctness?.token_f1)}</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-[#73736D] uppercase block">Citation Precision</span>
                            <span className="font-bold text-[#171717]">{formatPercent(itemDetail.citation?.citation_precision)}</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-[#73736D] uppercase block">Phantom Rate</span>
                            <span className="font-bold text-[#171717]">{formatPercent(itemDetail.citation?.phantom_rate)}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="bg-[#FFFFFF] border border-[#E5E3DD] rounded-xl p-12 text-center text-[#73736D] shadow-xs">
                    Select a question from the list to inspect its evidence and sentence grounding trace.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-[#E5E3DD] bg-[#FFFFFF] py-6 text-xs text-[#73736D]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-serif font-bold text-[#171717]">TRACE AI</span>
            <span>—</span>
            <span>Deterministic RAG Evaluation Engine & Workbench</span>
          </div>
          <div className="flex items-center gap-4 font-mono text-[11px]">
            <span>Methodology v1.0.0</span>
            <span>•</span>
            <span>Infinity AI Forge 2026</span>
          </div>
        </div>
      </footer>

      {/* ── How It Works Modal ── */}
      {showHowItWorks && (
        <div className="fixed inset-0 bg-[#171717]/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-150">
          <div className="bg-[#FFFFFF] border border-[#E5E3DD] rounded-2xl max-w-2xl w-full p-6 sm:p-8 space-y-6 shadow-xl relative max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setShowHowItWorks(false)}
              className="absolute top-6 right-6 text-[#73736D] hover:text-[#171717] cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="space-y-2">
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-[#174D3A] bg-[#E4EBE4] px-2.5 py-1 rounded">
                Methodology Guide
              </span>
              <h2 className="text-2xl font-serif font-bold text-[#171717]">How TRACE AI Works</h2>
              <p className="text-sm text-[#73736D]">
                TRACE AI is built on a deterministic-first architecture designed to eliminate metric drift and non-reproducible RAG benchmarks.
              </p>
            </div>

            <div className="space-y-4 text-xs text-[#171717] leading-relaxed">
              <div className="p-4 rounded-lg bg-[#F8F7F4] border border-[#E5E3DD] space-y-1.5">
                <h3 className="font-bold text-sm text-[#174D3A]">1. The Four Independent Dimensions</h3>
                <p className="text-[#73736D]">
                  Instead of generating a vague single score, TRACE evaluates RAG across four orthogonal axes:
                  Retrieval Relevance (Hit@k, Recall@k, MRR), Answer Correctness (Fact Recall, Token F1),
                  Citation Quality (Precision, Recall, Phantom Detection), and Grounding & Faithfulness (Unsupported Claim Rate).
                </p>
              </div>

              <div className="p-4 rounded-lg bg-[#F8F7F4] border border-[#E5E3DD] space-y-1.5">
                <h3 className="font-bold text-sm text-[#174D3A]">2. Deterministic Claim Identification</h3>
                <p className="text-[#73736D]">
                  TRACE segments responses into sentences using regex boundary rules. It identifies factual claims,
                  refusals, and unassessable statements without non-deterministic prompt variance.
                </p>
              </div>

              <div className="p-4 rounded-lg bg-[#F8F7F4] border border-[#E5E3DD] space-y-1.5">
                <h3 className="font-bold text-sm text-[#174D3A]">3. Local NLI Cross-Encoder Verification</h3>
                <p className="text-[#73736D]">
                  Grounding is computed by running a local NLI model (<code className="font-mono text-[11px] bg-[#E5E3DD] px-1 rounded">cross-encoder/nli-distilroberta-base</code>)
                  with frozen SHA-256 weights, combined with a deterministic Numeric Guard to catch subtle numerical hallucinations.
                </p>
              </div>

              <div className="p-4 rounded-lg bg-[#F8F7F4] border border-[#E5E3DD] space-y-1.5">
                <h3 className="font-bold text-sm text-[#174D3A]">4. Cryptographic Provenance</h3>
                <p className="text-[#73736D]">
                  Every run generates a canonical JSON representation and a SHA-256 result hash. Any alteration
                  in input, output, or metric configuration changes the hash, guaranteeing tamper-proof evaluation audits.
                </p>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setShowHowItWorks(false)}
                className="bg-[#174D3A] text-white text-xs font-semibold px-4 py-2 rounded-lg hover:bg-[#123e2e] transition cursor-pointer"
              >
                Close Guide
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
