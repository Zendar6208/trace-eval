import React, { useState } from 'react';
import {
  Play,
  CheckCircle2,
  AlertTriangle,
  ArrowLeft,
  Upload,
  Download,
  FileText,
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

// Plain-English diagnostic mappings for failure types
const FAILURE_DESCRIPTIONS: Record<string, { short: string; explanation: string }> = {
  RETRIEVAL_MISS: {
    short: 'Wrong information retrieved',
    explanation: 'The retrieval component failed to find the source passages needed to answer this question.',
  },
  WRONG_ANSWER: {
    short: 'Answer contradicts reference facts',
    explanation: 'The response omitted required facts or made statements that contradict verified ground truth.',
  },
  BAD_CITATION: {
    short: 'Citation does not support claim',
    explanation: 'The cited passage does not logically support or prove the statement made in the answer.',
  },
  UNSUPPORTED_CLAIM: {
    short: 'Statement lacks evidence',
    explanation: 'The response made a factual assertion that cannot be verified by any retrieved passage in context.',
  },
  UNCITED_CLAIM: {
    short: 'Factual statement missing citation',
    explanation: 'A factual claim was made without attaching an inline citation to retrieved evidence.',
  },
  CONTRADICTS_REFERENCE: {
    short: 'Direct contradiction with ground truth',
    explanation: 'The answer directly asserts facts that contradict the verified reference answer.',
  },
  PHANTOM_CITATION: {
    short: 'Cited non-existent passage',
    explanation: 'The answer cited a passage ID that was never retrieved or does not exist.',
  },
};

// Filter out 'PASS' to obtain genuine failures
function getActualFailures(failureTypes: string[] | undefined | null): string[] {
  if (!failureTypes) return [];
  return failureTypes.filter((ft) => ft !== 'PASS');
}

function formatPercent(val: number | null | undefined): string {
  if (val === null || val === undefined) return 'Not evaluated';
  return `${Math.round(val * 100)}%`;
}

function formatDecimal(val: number | null | undefined): string {
  if (val === null || val === undefined) return '—';
  return val.toFixed(3);
}

// Compute an intelligent, human-readable diagnostic headline from backend metrics
function computeDiagnosticSummary(runData: EvaluationRunResponse) {
  const items = runData.items;
  const isDemonstration =
    items.some((i) => i.origin === 'synthetic_fixture') ||
    items.some((i) => i.item_id.startsWith('q'));

  const failedItems = items.filter((i) => getActualFailures(i.failure_types).length > 0);
  const passedItems = items.filter((i) => getActualFailures(i.failure_types).length === 0);

  const retItems = items.filter((i) => i.retrieval?.hit_at_k?.['5'] !== undefined);
  const avgHit5 = retItems.length
    ? retItems.reduce((acc, i) => acc + (i.retrieval?.hit_at_k?.['5'] || 0), 0) / retItems.length
    : null;

  const meanFactRecall = runData.summary.combined?.mean_fact_recall ?? null;
  const meanUnsupported = runData.summary.combined?.mean_unsupported_claim_rate ?? null;

  let headline = 'Evaluation completed.';
  let narrative =
    'Here is the verified breakdown of your RAG system performance across documents, answers, and evidence.';

  if (failedItems.length === 0) {
    headline = 'Your AI retrieved the right evidence and answered accurately.';
    narrative = `All ${items.length} questions passed verification with required facts confirmed and zero unsupported assertions.`;
  } else if (avgHit5 !== null && avgHit5 >= 0.8 && meanFactRecall !== null && meanFactRecall < 0.8) {
    headline = 'Your AI found the right documents.\nBut its answers need work.';
    narrative = `Retrieval succeeded on ${Math.round(avgHit5 * 100)}% of queries, but answer correctness reached only ${Math.round(
      meanFactRecall * 100
    )}% because ${failedItems.length} question${
      failedItems.length > 1 ? 's' : ''
    } missed required facts or contained unverified assertions.`;
  } else if (avgHit5 !== null && avgHit5 < 0.8) {
    headline = "Retrieval misses are undermining your AI's answers.";
    narrative = `The retrieval component missed required source documents on ${Math.round(
      (1 - avgHit5) * 100
    )}% of queries, causing downstream inaccuracies.`;
  } else if (meanUnsupported !== null && meanUnsupported > 0.2) {
    headline = 'Your AI is making claims without supporting evidence.';
    narrative = `${Math.round(
      meanUnsupported * 100
    )}% of factual statements could not be verified by the retrieved passages.`;
  } else {
    headline = 'Strong retrieval with isolated answer edge cases.';
    narrative = `${passedItems.length} of ${items.length} questions passed cleanly, with ${failedItems.length} specific issue${
      failedItems.length > 1 ? 's' : ''
    } identified below.`;
  }

  return { headline, narrative, isDemonstration, failedCount: failedItems.length, passedCount: passedItems.length };
}

export default function App() {
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

  // UI Toggles
  const [showHowItWorks, setShowHowItWorks] = useState(false);
  const [showTechDetails, setShowTechDetails] = useState(false);
  const [showEvidenceTechDetails, setShowEvidenceTechDetails] = useState(false);
  const [copiedHash, setCopiedHash] = useState(false);
  const [filterStatus, setFilterStatus] = useState<'all' | 'failed' | 'passed'>('all');

  // ── Actions ──────────────────────────────────────────────────────────────────

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
      setError(err.message || 'Failed to execute sample evaluation');
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
      alert(`Error downloading template: ${err}`);
    }
  };

  // Filtered items
  const filteredItems = (runData?.items || []).filter((item) => {
    const failures = getActualFailures(item.failure_types);
    if (filterStatus === 'failed') return failures.length > 0;
    if (filterStatus === 'passed') return failures.length === 0;
    return true;
  });

  const diagnostic = runData ? computeDiagnosticSummary(runData) : null;

  return (
    <div className="min-h-screen bg-[#0C0F17] text-[#F8FAFC] font-sans antialiased flex flex-col selection:bg-[#10B981]/20 selection:text-[#10B981]">
      {/* ── Top Header ── */}
      <header className="border-b border-[#1F2639] bg-[#141824]/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#10B981] text-[#0C0F17] flex items-center justify-center font-serif font-black text-lg shadow-sm">
              T
            </div>
            <div className="flex items-center gap-2">
              <span className="font-serif font-bold text-xl tracking-tight text-white">TRACE.</span>
              <span className="text-[11px] font-mono tracking-wider bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/30 px-2 py-0.5 rounded font-semibold">
                RAG Diagnostic Report
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <button
              onClick={() => setShowHowItWorks(true)}
              className="inline-flex items-center gap-1.5 text-[#94A3B8] hover:text-[#F8FAFC] font-medium transition cursor-pointer"
            >
              <HelpCircle className="w-4 h-4" />
              <span>How TRACE evaluates</span>
            </button>
            <div className="h-4 w-[1px] bg-[#1F2639]" />
            <a
              href="https://github.com/darshan-sheth/trace-eval"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-[#94A3B8] hover:text-[#F8FAFC] font-medium transition"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>GitHub</span>
            </a>
          </div>
        </div>
      </header>

      {/* ── Main View ── */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
        {!runData ? (
          /* ══════════════════════════════════════════════════════════════════════
             SCREEN 1: SIMPLE EVALUATION WORKSPACE
             ══════════════════════════════════════════════════════════════════════ */
          <div className="space-y-12 max-w-4xl mx-auto pt-6 pb-16">
            <div className="text-center space-y-4">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/20 text-xs font-medium">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Deterministic-First RAG Evaluation Engine</span>
              </div>
              <h1 className="text-4xl sm:text-5xl font-serif font-bold tracking-tight text-white">
                Know when your AI gets it wrong.
              </h1>
              <p className="text-base sm:text-lg text-[#94A3B8] max-w-2xl mx-auto leading-relaxed">
                Receive an intelligent diagnostic report on your RAG system. Trace every factual claim back
                to retrieved evidence, detect hallucinations, and isolate retrieval misses.
              </p>
            </div>

            {error && (
              <div className="p-4 rounded-xl bg-[#7F1D1D]/30 border border-[#EF4444]/40 text-[#F87171] text-sm flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-semibold">Evaluation failed</p>
                  <p>{error}</p>
                </div>
              </div>
            )}

            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-stretch">
                {/* Option 1: Sample Evaluation */}
                <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-6 flex flex-col justify-between hover:border-[#10B981]/40 transition-colors shadow-lg">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-medium bg-[#10B981]/15 text-[#10B981] px-2.5 py-1 rounded-md">
                        Instant • Curated Benchmark
                      </span>
                    </div>

                    <div>
                      <h2 className="font-serif text-2xl font-bold text-white">Try Sample Evaluation</h2>
                      <p className="text-sm text-[#94A3B8] mt-2 leading-relaxed">
                        Test TRACE with a curated enterprise benchmark comparing customer support queries,
                        policy lookups, phantom citations, and unsupported answers.
                      </p>
                    </div>

                    <div className="space-y-2 pt-2 text-xs text-[#94A3B8] border-t border-[#1F2639]">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-[#10B981]" />
                        <span>Pre-configured dataset & model responses</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-[#10B981]" />
                        <span>Real local cross-encoder NLI inference</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-[#10B981]" />
                        <span>Sentence-level claim and citation verification</span>
                      </div>
                    </div>
                  </div>

                  <div className="pt-6">
                    <button
                      onClick={runSampleEvaluation}
                      disabled={loading}
                      className="w-full inline-flex items-center justify-center gap-2 bg-[#10B981] hover:bg-[#059669] text-[#0C0F17] font-semibold py-3 px-4 rounded-xl transition cursor-pointer disabled:opacity-50 text-sm shadow-md"
                    >
                      {loading ? (
                        <>
                          <div className="w-4 h-4 border-2 border-[#0C0F17]/30 border-t-[#0C0F17] rounded-full animate-spin" />
                          <span>Analyzing benchmark cases...</span>
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 fill-[#0C0F17]" />
                          <span>Run Sample Evaluation</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Option 2: Upload Evaluation */}
                <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-6 flex flex-col justify-between hover:border-[#10B981]/40 transition-colors shadow-lg">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-medium bg-[#1F2639] text-[#94A3B8] px-2.5 py-1 rounded-md">
                        Custom Run
                      </span>
                    </div>

                    <div>
                      <h2 className="font-serif text-2xl font-bold text-white">Upload Evaluation Data</h2>
                      <p className="text-sm text-[#94A3B8] mt-2 leading-relaxed">
                        Evaluate your own RAG system by uploading your dataset and submission JSON files
                        conforming to TRACE methodology contracts.
                      </p>
                    </div>

                    <form id="upload-form" onSubmit={handleUploadEvaluation} className="space-y-3 pt-1">
                      <div>
                        <label className="block text-xs font-medium text-[#F8FAFC] mb-1">
                          Dataset JSON (<span className="font-mono text-[11px] text-[#94A3B8]">trace.dataset/1.0</span>)
                        </label>
                        <input
                          type="file"
                          accept=".json"
                          onChange={(e) => setDatasetFile(e.target.files?.[0] || null)}
                          className="w-full text-xs text-[#94A3B8] file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[#10B981]/20 file:text-[#10B981] hover:file:bg-[#10B981]/30 file:cursor-pointer border border-[#1F2639] rounded-lg p-1.5 bg-[#0C0F17]"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-[#F8FAFC] mb-1">
                          Submission JSON (<span className="font-mono text-[11px] text-[#94A3B8]">trace.submission/1.0</span>)
                        </label>
                        <input
                          type="file"
                          accept=".json"
                          onChange={(e) => setSubmissionFile(e.target.files?.[0] || null)}
                          className="w-full text-xs text-[#94A3B8] file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[#10B981]/20 file:text-[#10B981] hover:file:bg-[#10B981]/30 file:cursor-pointer border border-[#1F2639] rounded-lg p-1.5 bg-[#0C0F17]"
                        />
                      </div>

                      <label className="flex items-center gap-2 pt-1 text-xs text-[#94A3B8] cursor-pointer">
                        <input
                          type="checkbox"
                          checked={requireCitations}
                          onChange={(e) => setRequireCitations(e.target.checked)}
                          className="rounded border-[#1F2639] text-[#10B981] focus:ring-[#10B981] bg-[#0C0F17]"
                        />
                        <span>Require & evaluate citations</span>
                      </label>

                      <div className="flex items-center gap-3 pt-1 text-[11px] text-[#64748B]">
                        <button
                          type="button"
                          onClick={() => downloadSample('dataset')}
                          className="inline-flex items-center gap-1 hover:text-[#10B981] underline cursor-pointer"
                        >
                          <Download className="w-3 h-3" />
                          <span>Sample dataset.json</span>
                        </button>
                        <span>•</span>
                        <button
                          type="button"
                          onClick={() => downloadSample('submission')}
                          className="inline-flex items-center gap-1 hover:text-[#10B981] underline cursor-pointer"
                        >
                          <Download className="w-3 h-3" />
                          <span>Sample submission.json</span>
                        </button>
                      </div>

                      {uploadError && (
                        <div className="p-2.5 rounded-lg bg-[#7F1D1D]/30 border border-[#EF4444]/30 text-[#F87171] text-xs">
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
                      className="w-full inline-flex items-center justify-center gap-2 bg-[#F8FAFC] hover:bg-white text-[#0C0F17] font-semibold py-3 px-4 rounded-xl transition cursor-pointer disabled:opacity-40 text-sm shadow-md"
                    >
                      {loading ? (
                        <>
                          <div className="w-4 h-4 border-2 border-[#0C0F17]/30 border-t-[#0C0F17] rounded-full animate-spin" />
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
             SCREEN 2 & 3: REFINED RESULTS & DIAGNOSTIC REPORT
             ══════════════════════════════════════════════════════════════════════ */
          <div className="space-y-8">
            {/* Navigation Bar */}
            <div className="flex items-center justify-between pb-2">
              <button
                onClick={() => {
                  setRunData(null);
                  setSelectedItemId(null);
                  setItemDetail(null);
                }}
                className="inline-flex items-center gap-2 text-xs font-medium text-[#94A3B8] hover:text-white transition cursor-pointer"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Back to Evaluation Workspace</span>
              </button>

              {diagnostic?.isDemonstration && (
                <span className="text-xs font-mono bg-[#1F2639] text-[#94A3B8] border border-[#2A324B] px-3 py-1 rounded-full">
                  Demonstration Benchmark • 5 Cases
                </span>
              )}
            </div>

            {/* ── Human-Readable Diagnostic Summary ── */}
            <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-6 sm:p-8 space-y-4 shadow-xl">
              <div className="space-y-2">
                <span className="text-xs font-mono uppercase tracking-wider text-[#10B981] font-semibold">
                  Diagnostic Overview
                </span>
                <h1 className="text-3xl sm:text-4xl font-serif font-bold text-white whitespace-pre-line leading-tight">
                  {diagnostic?.headline}
                </h1>
                <p className="text-sm sm:text-base text-[#94A3B8] max-w-3xl leading-relaxed">
                  {diagnostic?.narrative}
                </p>
              </div>

              {/* Collapsible Technical Details (Progressive Disclosure) */}
              <div className="pt-2 border-t border-[#1F2639]/80">
                <button
                  onClick={() => setShowTechDetails(!showTechDetails)}
                  className="inline-flex items-center gap-1.5 text-xs font-mono font-medium text-[#94A3B8] hover:text-[#10B981] cursor-pointer transition"
                >
                  {showTechDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  <span>{showTechDetails ? 'Hide Technical Metadata & Hashes' : 'Technical Details & Reproducibility'}</span>
                </button>

                {showTechDetails && (
                  <div className="mt-4 p-4 rounded-xl bg-[#0C0F17] border border-[#1F2639] grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono text-[#94A3B8]">
                    <div className="space-y-2">
                      <div>
                        <span className="text-[#64748B] block text-[10px] uppercase">Run ID</span>
                        <span className="text-white select-all">{runData.run_id}</span>
                      </div>
                      <div>
                        <span className="text-[#64748B] block text-[10px] uppercase">Evaluation Tier</span>
                        <span className="text-white">{runData.evaluation_tier}</span>
                      </div>
                      <div>
                        <span className="text-[#64748B] block text-[10px] uppercase">Methodology</span>
                        <span className="text-white">{runData.methodology_version}</span>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div>
                        <span className="text-[#64748B] block text-[10px] uppercase">Cryptographic Result Hash</span>
                        <div className="flex items-center gap-2">
                          <span className="text-white truncate select-all">{runData.result_hash}</span>
                          <button
                            onClick={copyHashToClipboard}
                            className="text-[#94A3B8] hover:text-[#10B981] p-1 cursor-pointer"
                            title="Copy full hash"
                          >
                            {copiedHash ? <Check className="w-3.5 h-3.5 text-[#10B981]" /> : <Copy className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      </div>
                      <div>
                        <span className="text-[#64748B] block text-[10px] uppercase">Raw Failure Distribution</span>
                        <span className="text-white">
                          {JSON.stringify(runData.summary.failure_distribution)}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ── The 4 Primary Evaluation Dimensions ── */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xs font-mono uppercase tracking-wider text-[#94A3B8] font-semibold">
                  Core Evaluation Dimensions
                </h2>
                <span className="text-xs text-[#64748B]">
                  Independent, non-aggregated metrics
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* 1. Found the right information */}
                <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 shadow-lg flex flex-col justify-between space-y-4">
                  <div className="space-y-1">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#94A3B8] font-semibold">
                      Retrieval
                    </span>
                    <h3 className="font-serif text-lg font-bold text-white">Found the right information</h3>
                    <p className="text-xs text-[#94A3B8] leading-relaxed">
                      Did the retrieval component find the required source passages?
                    </p>
                  </div>
                  <div className="pt-3 border-t border-[#1F2639]">
                    <div className="text-3xl font-serif font-black text-[#10B981]">
                      {(() => {
                        const items = runData.items.filter((i) => i.retrieval?.hit_at_k?.['5'] !== undefined);
                        if (!items.length) return 'Not evaluated';
                        const avg = items.reduce((acc, i) => acc + (i.retrieval?.hit_at_k?.['5'] || 0), 0) / items.length;
                        return formatPercent(avg);
                      })()}
                    </div>
                    <div className="text-[11px] text-[#64748B] mt-1.5 font-mono">
                      Hit@5 • Recall@5: {formatPercent(runData.items.reduce((acc, i) => acc + (i.retrieval?.recall_at_k?.['5'] || 0), 0) / (runData.items.length || 1))}
                    </div>
                  </div>
                </div>

                {/* 2. Answered correctly */}
                <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 shadow-lg flex flex-col justify-between space-y-4">
                  <div className="space-y-1">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#94A3B8] font-semibold">
                      Correctness
                    </span>
                    <h3 className="font-serif text-lg font-bold text-white">Answered correctly</h3>
                    <p className="text-xs text-[#94A3B8] leading-relaxed">
                      Did the response contain all mandatory facts from reference answers?
                    </p>
                  </div>
                  <div className="pt-3 border-t border-[#1F2639]">
                    <div className="text-3xl font-serif font-black text-[#10B981]">
                      {formatPercent(runData.summary.combined?.mean_fact_recall)}
                    </div>
                    <div className="text-[11px] text-[#64748B] mt-1.5 font-mono">
                      Fact Recall • Token F1: {formatDecimal(runData.summary.combined?.mean_token_f1)}
                    </div>
                  </div>
                </div>

                {/* 3. Backed up its claims */}
                <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 shadow-lg flex flex-col justify-between space-y-4">
                  <div className="space-y-1">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#94A3B8] font-semibold">
                      Citations
                    </span>
                    <h3 className="font-serif text-lg font-bold text-white">Backed up its claims</h3>
                    <p className="text-xs text-[#94A3B8] leading-relaxed">
                      Do cited passages actually support and prove the sentence claim?
                    </p>
                  </div>
                  <div className="pt-3 border-t border-[#1F2639]">
                    <div className="text-3xl font-serif font-black text-[#10B981]">
                      {formatPercent(runData.summary.combined?.mean_citation_precision)}
                    </div>
                    <div className="text-[11px] text-[#64748B] mt-1.5 font-mono">
                      Citation Precision • Phantom: {formatPercent(runData.summary.combined?.mean_phantom_rate)}
                    </div>
                  </div>
                </div>

                {/* 4. Avoided making things up */}
                <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 shadow-lg flex flex-col justify-between space-y-4">
                  <div className="space-y-1">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#94A3B8] font-semibold">
                      Grounding
                    </span>
                    <h3 className="font-serif text-lg font-bold text-white">Avoided making things up</h3>
                    <p className="text-xs text-[#94A3B8] leading-relaxed">
                      Is every factual assertion logically entailed by the retrieved text?
                    </p>
                  </div>
                  <div className="pt-3 border-t border-[#1F2639]">
                    <div className="text-3xl font-serif font-black text-[#10B981]">
                      {(() => {
                        const rate = runData.summary.combined?.mean_unsupported_claim_rate;
                        if (rate === null || rate === undefined) return 'Not evaluated';
                        return formatPercent(1 - rate);
                      })()}
                    </div>
                    <div className="text-[11px] text-[#64748B] mt-1.5 font-mono">
                      Supported Claims • Unsupported: {formatPercent(runData.summary.combined?.mean_unsupported_claim_rate)}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Explore Your Results & Evidence Inspector Split Layout ── */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left Column: Explore Your Results (5 cols) */}
              <div className="lg:col-span-5 bg-[#141824] border border-[#1F2639] rounded-2xl shadow-xl overflow-hidden">
                <div className="p-4 border-b border-[#1F2639] flex items-center justify-between bg-[#0F121C]">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-[#10B981]" />
                    <span className="font-serif font-bold text-sm text-white">Explore your results</span>
                  </div>

                  {/* Filter tabs */}
                  <div className="flex items-center gap-1 text-[11px] font-mono bg-[#0C0F17] border border-[#1F2639] p-0.5 rounded-lg">
                    <button
                      onClick={() => setFilterStatus('all')}
                      className={`px-2.5 py-1 rounded-md cursor-pointer transition ${
                        filterStatus === 'all'
                          ? 'bg-[#10B981] text-[#0C0F17] font-bold'
                          : 'text-[#94A3B8] hover:text-white'
                      }`}
                    >
                      All ({runData.items.length})
                    </button>
                    <button
                      onClick={() => setFilterStatus('failed')}
                      className={`px-2.5 py-1 rounded-md cursor-pointer transition ${
                        filterStatus === 'failed'
                          ? 'bg-[#F87171] text-[#0C0F17] font-bold'
                          : 'text-[#94A3B8] hover:text-white'
                      }`}
                    >
                      Failed ({diagnostic?.failedCount})
                    </button>
                    <button
                      onClick={() => setFilterStatus('passed')}
                      className={`px-2.5 py-1 rounded-md cursor-pointer transition ${
                        filterStatus === 'passed'
                          ? 'bg-[#10B981]/20 text-[#10B981] font-bold'
                          : 'text-[#94A3B8] hover:text-white'
                      }`}
                    >
                      Passed ({diagnostic?.passedCount})
                    </button>
                  </div>
                </div>

                <div className="divide-y divide-[#1F2639] max-h-[700px] overflow-y-auto">
                  {filteredItems.map((item) => {
                    const isSelected = item.item_id === selectedItemId;
                    const failures = getActualFailures(item.failure_types);
                    const isPassed = failures.length === 0;

                    return (
                      <button
                        key={item.item_id}
                        onClick={() => selectItem(item.item_id)}
                        className={`w-full text-left p-4 transition cursor-pointer flex flex-col gap-2 ${
                          isSelected
                            ? 'bg-[#1A2030] border-l-4 border-l-[#10B981]'
                            : 'hover:bg-[#1A2030]/50 border-l-4 border-l-transparent'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono text-xs font-semibold text-[#64748B]">
                            {item.item_id}
                          </span>

                          {/* Single Clear Verdict Badge */}
                          {isPassed ? (
                            <span className="text-[11px] font-medium bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30 px-2 py-0.5 rounded-full flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" />
                              <span>Passed</span>
                            </span>
                          ) : (
                            <span className="text-[11px] font-medium bg-[#7F1D1D]/30 text-[#F87171] border border-[#EF4444]/30 px-2 py-0.5 rounded-full flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" />
                              <span>Needs attention</span>
                            </span>
                          )}
                        </div>

                        {/* Real Question Text */}
                        <p className="text-sm font-medium text-white line-clamp-2 leading-snug">
                          {item.question || `Question ${item.item_id}`}
                        </p>

                        {/* One Concise Diagnostic */}
                        <div className="text-xs">
                          {isPassed ? (
                            <span className="text-[#10B981] text-[11px]">
                              All checks passed cleanly
                            </span>
                          ) : (
                            <span className="text-[#F87171] text-[11px]">
                              {FAILURE_DESCRIPTIONS[failures[0]]?.short || failures[0]}
                            </span>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Right Column: Narrative Evidence Inspector (7 cols) */}
              <div className="lg:col-span-7 space-y-6">
                {detailLoading ? (
                  <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-12 text-center shadow-xl">
                    <div className="w-6 h-6 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                    <p className="text-sm text-[#94A3B8]">Loading diagnostic trace and retrieved evidence...</p>
                  </div>
                ) : itemDetail ? (
                  <div className="bg-[#141824] border border-[#1F2639] rounded-2xl shadow-xl p-6 sm:p-8 space-y-8">
                    {/* A. The Question */}
                    <div className="space-y-2 border-b border-[#1F2639] pb-6">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono font-semibold text-[#10B981] uppercase tracking-wider">
                          Question {itemDetail.item_id}
                        </span>
                        <span className="text-xs font-mono text-[#64748B]">
                          {itemDetail.origin === 'synthetic_fixture' ? 'Demonstration Fixture' : 'Recorded RAG System'}
                        </span>
                      </div>
                      <h2 className="text-2xl font-serif font-bold text-white leading-snug">
                        {itemDetail.question || 'Question text not available'}
                      </h2>
                    </div>

                    {/* B. What the AI Answered */}
                    <div className="space-y-2">
                      <span className="text-xs font-mono uppercase tracking-wider text-[#94A3B8] block">
                        What the AI Answered
                      </span>
                      <div className="p-4 rounded-xl bg-[#0C0F17] border border-[#1F2639] text-sm text-[#F8FAFC] leading-relaxed whitespace-pre-wrap">
                        {itemDetail.answer || <span className="text-[#64748B] italic">No answer provided</span>}
                      </div>
                    </div>

                    {/* C. Our Finding */}
                    <div className="space-y-2">
                      <span className="text-xs font-mono uppercase tracking-wider text-[#94A3B8] block">
                        Our Finding
                      </span>
                      {(() => {
                        const failures = getActualFailures(itemDetail.failure_types);
                        if (failures.length === 0) {
                          return (
                            <div className="p-4 rounded-xl bg-[#10B981]/10 border border-[#10B981]/30 flex items-start gap-3 text-sm text-[#F8FAFC]">
                              <CheckCircle2 className="w-5 h-5 text-[#10B981] shrink-0 mt-0.5" />
                              <div className="space-y-1">
                                <p className="font-semibold text-[#10B981]">Clean pass across all checks</p>
                                <p className="text-xs text-[#94A3B8]">
                                  The AI answer contains all required facts from reference answers, correctly cites
                                  retrieved evidence, and contains no unsupported assertions.
                                </p>
                              </div>
                            </div>
                          );
                        }

                        return (
                          <div className="p-4 rounded-xl bg-[#7F1D1D]/20 border border-[#EF4444]/30 space-y-3">
                            <div className="flex items-center gap-2 text-[#F87171] font-bold text-sm">
                              <AlertTriangle className="w-4 h-4 shrink-0" />
                              <span>{failures.length} issue{failures.length > 1 ? 's' : ''} detected</span>
                            </div>
                            <ul className="text-xs text-[#F8FAFC] space-y-2 pl-5 list-disc">
                              {failures.map((ft) => (
                                <li key={ft}>
                                  <strong className="text-[#F87171]">
                                    {FAILURE_DESCRIPTIONS[ft]?.short || ft}:
                                  </strong>{' '}
                                  <span className="text-[#94A3B8]">
                                    {FAILURE_DESCRIPTIONS[ft]?.explanation}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        );
                      })()}
                    </div>

                    {/* D. What the Retrieved Evidence Actually Says */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono uppercase tracking-wider text-[#94A3B8]">
                          What the Retrieved Evidence Actually Says
                        </span>
                        <span className="text-xs text-[#64748B] font-mono">
                          {itemDetail.retrieved?.length || 0} passage{itemDetail.retrieved?.length === 1 ? '' : 's'} retrieved
                        </span>
                      </div>

                      <div className="space-y-3">
                        {itemDetail.retrieved && itemDetail.retrieved.length > 0 ? (
                          itemDetail.retrieved.map((p, idx) => (
                            <div
                              key={p.id}
                              className="border border-[#1F2639] rounded-xl p-4 bg-[#0C0F17] space-y-2 text-xs"
                            >
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span className="font-mono font-bold text-[#10B981] bg-[#10B981]/15 px-2 py-0.5 rounded text-[11px]">
                                    {p.id}
                                  </span>
                                  <span className="text-[11px] text-[#64748B] font-mono">Rank #{idx + 1}</span>
                                </div>
                                {p.score !== null && (
                                  <span className="text-[11px] font-mono text-[#64748B]">
                                    Score: {formatDecimal(p.score)}
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-[#94A3B8] leading-relaxed">
                                {p.text}
                              </p>
                            </div>
                          ))
                        ) : (
                          <p className="text-xs text-[#64748B] italic">No retrieved passages recorded.</p>
                        )}
                      </div>
                    </div>

                    {/* E. Supporting Technical Details (Sentence Grounding, NLI, Advanced Metrics) */}
                    <div className="border-t border-[#1F2639] pt-4">
                      <button
                        onClick={() => setShowEvidenceTechDetails(!showEvidenceTechDetails)}
                        className="inline-flex items-center gap-2 text-xs font-mono font-semibold text-[#10B981] hover:underline cursor-pointer"
                      >
                        {showEvidenceTechDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        <span>
                          {showEvidenceTechDetails
                            ? 'Hide Sentence Grounding Trace & Technical Metrics'
                            : 'View Sentence-by-Sentence Grounding Trace & NLI Scores'}
                        </span>
                      </button>

                      {showEvidenceTechDetails && (
                        <div className="mt-4 space-y-6">
                          {/* Sentence Breakdown */}
                          <div className="space-y-3">
                            <span className="text-xs font-mono uppercase text-[#64748B] block">
                              Sentence Grounding Breakdown
                            </span>
                            {itemDetail.claims && itemDetail.claims.length > 0 ? (
                              itemDetail.claims.map((claim) => {
                                const attachedCitations = (itemDetail.citations || []).filter(
                                  (c) => c.sentence_index === claim.sentence_index
                                );

                                return (
                                  <div
                                    key={claim.sentence_index}
                                    className={`border rounded-xl p-4 space-y-2 text-xs ${
                                      claim.grounding_label === 'supported'
                                        ? 'bg-[#10B981]/5 border-[#10B981]/30'
                                        : claim.grounding_label === 'contradicted'
                                        ? 'bg-[#7F1D1D]/20 border-[#EF4444]/40'
                                        : claim.grounding_label === 'unsupported'
                                        ? 'bg-[#7F1D1D]/10 border-[#EF4444]/25'
                                        : 'bg-[#0C0F17] border-[#1F2639]'
                                    }`}
                                  >
                                    <div className="flex items-start justify-between gap-3">
                                      <div className="flex items-start gap-2">
                                        <span className="font-mono text-[11px] font-bold text-[#64748B] bg-[#141824] border border-[#1F2639] px-1.5 py-0.5 rounded">
                                          S{claim.sentence_index + 1}
                                        </span>
                                        <p className="text-xs text-[#F8FAFC] font-medium leading-relaxed">
                                          "{claim.sentence_text}"
                                        </p>
                                      </div>

                                      <span
                                        className={`shrink-0 font-mono text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                                          claim.grounding_label === 'supported'
                                            ? 'bg-[#10B981] text-[#0C0F17]'
                                            : claim.grounding_label === 'contradicted'
                                            ? 'bg-[#F87171] text-[#0C0F17]'
                                            : claim.grounding_label === 'unsupported'
                                            ? 'bg-[#7F1D1D]/50 text-[#F87171] border border-[#EF4444]/40'
                                            : 'bg-[#1F2639] text-[#94A3B8]'
                                        }`}
                                      >
                                        {claim.grounding_label}
                                      </span>
                                    </div>

                                    {/* Probabilities & Guards */}
                                    <div className="flex flex-wrap items-center gap-4 text-[11px] font-mono text-[#64748B] pt-2 border-t border-[#1F2639]">
                                      {claim.best_entail_prob !== null && (
                                        <span>Entailment Prob: {formatDecimal(claim.best_entail_prob)}</span>
                                      )}
                                      {claim.best_contradict_prob !== null && (
                                        <span>Contradiction Prob: {formatDecimal(claim.best_contradict_prob)}</span>
                                      )}
                                      {claim.numeric_guard_triggered && (
                                        <span className="text-[#F87171] font-bold bg-[#7F1D1D]/40 px-2 py-0.5 rounded border border-[#EF4444]/30">
                                          Numeric Guard: Mismatched numbers detected
                                        </span>
                                      )}
                                    </div>

                                    {/* Attached Citations */}
                                    {attachedCitations.length > 0 && (
                                      <div className="pt-2 space-y-1">
                                        <span className="text-[10px] font-mono uppercase text-[#64748B] block">
                                          Attached Citations:
                                        </span>
                                        <div className="flex flex-wrap gap-2">
                                          {attachedCitations.map((cit, idx) => (
                                            <div
                                              key={idx}
                                              className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-mono border ${
                                                cit.validity === 'ok' && cit.supports
                                                  ? 'bg-[#10B981]/10 border-[#10B981]/30 text-[#10B981]'
                                                  : 'bg-[#7F1D1D]/30 border-[#EF4444]/30 text-[#F87171]'
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
                              <p className="text-xs text-[#64748B] italic">No sentence claims evaluated.</p>
                            )}
                          </div>

                          {/* Advanced Metrics Table */}
                          <div className="p-4 rounded-xl bg-[#0C0F17] border border-[#1F2639] grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
                            <div>
                              <span className="text-[10px] text-[#64748B] uppercase block">Hit@1</span>
                              <span className="font-bold text-white">{itemDetail.retrieval?.hit_at_k?.['1'] ?? '—'}</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-[#64748B] uppercase block">Hit@5</span>
                              <span className="font-bold text-white">{itemDetail.retrieval?.hit_at_k?.['5'] ?? '—'}</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-[#64748B] uppercase block">MRR</span>
                              <span className="font-bold text-white">{formatDecimal(itemDetail.retrieval?.mrr)}</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-[#64748B] uppercase block">nDCG@5</span>
                              <span className="font-bold text-white">{formatDecimal(itemDetail.retrieval?.ndcg_at_k?.['5'])}</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-[#64748B] uppercase block">Fact Recall</span>
                              <span className="font-bold text-white">{formatPercent(itemDetail.correctness?.fact_recall)}</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-[#64748B] uppercase block">Token F1</span>
                              <span className="font-bold text-white">{formatDecimal(itemDetail.correctness?.token_f1)}</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-[#64748B] uppercase block">Citation Precision</span>
                              <span className="font-bold text-white">{formatPercent(itemDetail.citation?.citation_precision)}</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-[#64748B] uppercase block">Phantom Rate</span>
                              <span className="font-bold text-white">{formatPercent(itemDetail.citation?.phantom_rate)}</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-12 text-center text-[#64748B] shadow-xl">
                    Select a question from the list to view its complete evidence and diagnostic trace.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-[#1F2639] bg-[#141824] py-6 text-xs text-[#64748B]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-serif font-bold text-white">TRACE AI</span>
            <span>—</span>
            <span>Deterministic RAG Evaluation Engine & Diagnostic Workbench</span>
          </div>
          <div className="flex items-center gap-4 font-mono text-[11px]">
            <span>Methodology v1.0.0 Normative</span>
            <span>•</span>
            <span>Cryptographic Reproducibility</span>
          </div>
        </div>
      </footer>

      {/* ── How It Works Modal ── */}
      {showHowItWorks && (
        <div className="fixed inset-0 bg-[#0C0F17]/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-[#141824] border border-[#1F2639] rounded-2xl max-w-2xl w-full p-6 sm:p-8 space-y-6 shadow-2xl relative max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setShowHowItWorks(false)}
              className="absolute top-6 right-6 text-[#94A3B8] hover:text-white cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="space-y-2">
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-[#10B981] bg-[#10B981]/10 border border-[#10B981]/20 px-2.5 py-1 rounded">
                Methodology Guide
              </span>
              <h2 className="text-2xl font-serif font-bold text-white">How TRACE Evaluates Your RAG</h2>
              <p className="text-sm text-[#94A3B8]">
                TRACE AI is built on a deterministic-first architecture designed to eliminate metric drift and non-reproducible RAG benchmarks.
              </p>
            </div>

            <div className="space-y-4 text-xs text-[#F8FAFC] leading-relaxed">
              <div className="p-4 rounded-xl bg-[#0C0F17] border border-[#1F2639] space-y-1.5">
                <h3 className="font-bold text-sm text-[#10B981]">1. The Four Orthogonal Axes</h3>
                <p className="text-[#94A3B8]">
                  Instead of fabricating a single vague percentage, TRACE evaluates RAG systems across four independent dimensions:
                  Retrieval Relevance, Answer Correctness, Citation Quality, and Grounding & Faithfulness.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#0C0F17] border border-[#1F2639] space-y-1.5">
                <h3 className="font-bold text-sm text-[#10B981]">2. Deterministic Claim Identification</h3>
                <p className="text-[#94A3B8]">
                  Answers are segmented into sentences using deterministic regex boundary rules. Factual claims, refusals,
                  and unassessable statements are identified without LLM variance.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#0C0F17] border border-[#1F2639] space-y-1.5">
                <h3 className="font-bold text-sm text-[#10B981]">3. Local NLI Cross-Encoder Verification</h3>
                <p className="text-[#94A3B8]">
                  Grounding is computed by running a local NLI model (<code className="font-mono text-[11px] bg-[#1F2639] px-1 rounded text-[#10B981]">cross-encoder/nli-distilroberta-base</code>)
                  with frozen SHA-256 weights, combined with a deterministic Numeric Guard to catch numerical drift.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#0C0F17] border border-[#1F2639] space-y-1.5">
                <h3 className="font-bold text-sm text-[#10B981]">4. Cryptographic Provenance</h3>
                <p className="text-[#94A3B8]">
                  Every run produces a canonical JSON representation and a SHA-256 result hash. Any change in inputs,
                  passages, or metrics alters the hash, guaranteeing audit reproducibility.
                </p>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setShowHowItWorks(false)}
                className="bg-[#10B981] text-[#0C0F17] text-xs font-semibold px-4 py-2 rounded-lg hover:bg-[#059669] transition cursor-pointer"
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
