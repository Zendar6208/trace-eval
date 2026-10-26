import React, { useState, useEffect, useRef } from 'react';
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
  X,
  Target,
  GitCompare,
  Database
} from 'lucide-react';
import type {
  EvaluationRunResponse,
  ItemDetailResponse,
  BenchmarkInfo,
  ComparisonRunResponse
} from './types';
import { ComparisonView } from './ComparisonView';

const API_BASE = (import.meta as any).env?.VITE_API_URL || '';

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

// Lightweight smooth number count-up component
function AnimatedNumber({ value, suffix = '' }: { value: number | null | undefined; suffix?: string }) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (value === null || value === undefined) return;
    const target = Math.round(value * 100);
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      setDisplay(target);
      return;
    }

    const duration = 450;
    const start = performance.now();

    const frame = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // easeOutExpo
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setDisplay(Math.round(eased * target));
      if (progress < 1) {
        requestAnimationFrame(frame);
      }
    };

    requestAnimationFrame(frame);
  }, [value]);

  if (value === null || value === undefined) return <span>Not evaluated</span>;
  return <span>{display}{suffix}</span>;
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
  const [comparisonData, setComparisonData] = useState<ComparisonRunResponse | null>(null);
  const [benchmarks, setBenchmarks] = useState<BenchmarkInfo[]>([]);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [itemDetail, setItemDetail] = useState<ItemDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('Evaluating benchmark cases...');
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Motion & Interactive Tracing State
  const [activeClaimIndex, setActiveClaimIndex] = useState<number | null>(null);
  const [activePassageId, setActivePassageId] = useState<string | null>(null);

  // Upload State
  const [customMode, setCustomMode] = useState<'single' | 'compare'>('single');
  const [datasetFile, setDatasetFile] = useState<File | null>(null);
  const [submissionFile, setSubmissionFile] = useState<File | null>(null);
  const [submissionBFile, setSubmissionBFile] = useState<File | null>(null);
  const [requireCitations, setRequireCitations] = useState(true);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // UI Toggles
  const [showHowItWorks, setShowHowItWorks] = useState(false);
  const [showTechDetails, setShowTechDetails] = useState(false);
  const [showEvidenceTechDetails, setShowEvidenceTechDetails] = useState(false);
  const [copiedHash, setCopiedHash] = useState(false);
  const [filterStatus, setFilterStatus] = useState<'all' | 'failed' | 'passed'>('all');

  const evidenceSectionRef = useRef<HTMLDivElement>(null);

  // Load benchmarks on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/benchmarks`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load benchmarks');
        return res.json();
      })
      .then((data) => setBenchmarks(data))
      .catch((err) => console.warn('Benchmarks fetch warning:', err));
  }, []);

  // ── Actions ──────────────────────────────────────────────────────────────────

  const runSampleEvaluation = async () => {
    setLoading(true);
    setLoadingMessage('Evaluating customer service benchmark...');
    setError(null);
    setComparisonData(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluate/sample`, { method: 'POST' });
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

  const runBenchmarkEvaluation = async (benchmarkId: string, pipeline: string = 'a') => {
    setLoading(true);
    setLoadingMessage(`Evaluating ${benchmarkId} (${pipeline.toUpperCase()})...`);
    setError(null);
    setComparisonData(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/evaluate/benchmark/${benchmarkId}?pipeline=${pipeline}`,
        { method: 'POST' }
      );
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
      setError(err.message || 'Benchmark evaluation failed');
    } finally {
      setLoading(false);
    }
  };

  const runBenchmarkComparison = async (benchmarkId: string) => {
    setLoading(true);
    setLoadingMessage('Running side-by-side RAG evaluation & comparison...');
    setError(null);
    setRunData(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluate/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ benchmark_id: benchmarkId }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `HTTP error ${res.status}`);
      }
      const data: ComparisonRunResponse = await res.json();
      setComparisonData(data);
    } catch (err: any) {
      setError(err.message || 'Comparison failed');
    } finally {
      setLoading(false);
    }
  };

  const handleUploadComparison = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!datasetFile || !submissionFile || !submissionBFile) {
      setUploadError('Please select dataset.json, Submission A, and Submission B files.');
      return;
    }

    setLoading(true);
    setLoadingMessage('Evaluating and comparing both custom RAG pipelines...');
    setUploadError(null);
    setRunData(null);
    try {
      const datasetText = await datasetFile.text();
      const submissionAText = await submissionFile.text();
      const submissionBText = await submissionBFile.text();

      let datasetJson: any;
      let submissionAJson: any;
      let submissionBJson: any;

      try {
        datasetJson = JSON.parse(datasetText);
      } catch {
        throw new Error('Dataset file is not valid JSON.');
      }
      try {
        submissionAJson = JSON.parse(submissionAText);
      } catch {
        throw new Error('Submission A file is not valid JSON.');
      }
      try {
        submissionBJson = JSON.parse(submissionBText);
      } catch {
        throw new Error('Submission B file is not valid JSON.');
      }

      const res = await fetch(`${API_BASE}/api/evaluate/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset: datasetJson,
          submission_a: submissionAJson,
          submission_b: submissionBJson,
          require_citations: requireCitations,
          citation_style: 'id',
          phantom_mode: 'bracket',
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `HTTP ${res.status}: Comparison evaluation failed.`);
      }

      const result: ComparisonRunResponse = await res.json();
      setComparisonData(result);
    } catch (err: any) {
      setUploadError(err.message || 'Comparison evaluation failed.');
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

      const res = await fetch(`${API_BASE}/api/evaluate/upload`, {
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
    setActiveClaimIndex(null);
    setActivePassageId(null);
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/evaluate/item/${itemId}`);
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

  const toggleClaimTrace = (sentenceIndex: number) => {
    if (activeClaimIndex === sentenceIndex) {
      setActiveClaimIndex(null);
      setActivePassageId(null);
    } else {
      setActiveClaimIndex(sentenceIndex);
      // Find attached citation passage IDs
      if (itemDetail?.citations) {
        const matchingCits = itemDetail.citations.filter((c) => c.sentence_index === sentenceIndex);
        if (matchingCits.length > 0) {
          setActivePassageId(matchingCits[0].passage_id);
        } else {
          setActivePassageId(null);
        }
      }
      // Smoothly scroll down to evidence if not in view
      if (evidenceSectionRef.current) {
        evidenceSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  };

  const togglePassageTrace = (passageId: string) => {
    if (activePassageId === passageId) {
      setActivePassageId(null);
      setActiveClaimIndex(null);
    } else {
      setActivePassageId(passageId);
      // Find corresponding sentence index
      if (itemDetail?.citations) {
        const matchingCit = itemDetail.citations.find((c) => c.passage_id === passageId);
        if (matchingCit && matchingCit.sentence_index !== null) {
          setActiveClaimIndex(matchingCit.sentence_index);
        }
      }
    }
  };

  const copyHashToClipboard = () => {
    if (runData?.result_hash) {
      navigator.clipboard.writeText(runData.result_hash);
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 2000);
    }
  };

  const downloadSample = async (type: 'dataset' | 'submission' | 'submission_b') => {
    try {
      const res = await fetch(`${API_BASE}/api/sample/${type}`);
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
      <header className="border-b border-[#1F2639] bg-[#141824]/80 backdrop-blur-md sticky top-0 z-40 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#10B981] text-[#0C0F17] flex items-center justify-center font-serif font-black text-lg shadow-sm">
              T
            </div>
            <div className="flex items-center gap-2">
              <span className="font-serif font-bold text-xl tracking-tight text-white">TRACE.</span>
              <span className="text-[11px] font-mono tracking-wider bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/30 px-2 py-0.5 rounded font-semibold">
                RAG Diagnostic Workbench
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <button
              onClick={() => setShowHowItWorks(true)}
              className="inline-flex items-center gap-1.5 text-[#94A3B8] hover:text-[#F8FAFC] font-medium transition cursor-pointer active:scale-95"
            >
              <HelpCircle className="w-4 h-4" />
              <span>How TRACE evaluates</span>
            </button>
            <div className="h-4 w-[1px] bg-[#1F2639]" />
            <a
              href="https://github.com/Zendar6208/trace-eval"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-[#94A3B8] hover:text-[#F8FAFC] font-medium transition active:scale-95"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>GitHub</span>
            </a>
          </div>
        </div>
      </header>

      {/* ── Main View ── */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          /* ══════════════════════════════════════════════════════════════════════
             LOADING ANIMATION: SIGNATURE 4-STAGE EVALUATION SEQUENCE
             ══════════════════════════════════════════════════════════════════════ */
          <div className="max-w-2xl mx-auto pt-16 pb-24 animate-hero-1">
            <div className="bg-[#141824] border border-[#10B981]/40 rounded-3xl p-8 sm:p-12 text-center shadow-2xl space-y-8 animate-card-1">
              <div className="space-y-3">
                <div className="w-12 h-12 rounded-full border-2 border-[#10B981] border-t-transparent animate-spin mx-auto shadow-lg" />
                <h2 className="text-2xl font-serif font-bold text-white">
                  {loadingMessage}
                </h2>
                <p className="text-sm text-[#94A3B8] max-w-md mx-auto">
                  Running deterministic metrics and local cross-encoder NLI verification.
                </p>
              </div>

              {/* The 4-Stage Evaluation Sequence */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 max-w-xl mx-auto text-left font-mono text-xs">
                <div className="p-3 rounded-xl bg-[#0C0F17] border border-[#1F2639] flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#10B981] animate-ping" />
                  <span className="text-[#94A3B8]">1. Passages</span>
                </div>
                <div className="p-3 rounded-xl bg-[#0C0F17] border border-[#1F2639] flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#10B981] animate-ping" />
                  <span className="text-[#94A3B8]">2. Correctness</span>
                </div>
                <div className="p-3 rounded-xl bg-[#0C0F17] border border-[#1F2639] flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#10B981] animate-ping" />
                  <span className="text-[#94A3B8]">3. Citations</span>
                </div>
                <div className="p-3 rounded-xl bg-[#0C0F17] border border-[#1F2639] flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#10B981] animate-ping" />
                  <span className="text-[#94A3B8]">4. Grounding</span>
                </div>
              </div>
            </div>
          </div>
        ) : comparisonData ? (
          /* ══════════════════════════════════════════════════════════════════════
             SCREEN 3: RAG COMPARISON LAB
             ══════════════════════════════════════════════════════════════════════ */
          <ComparisonView data={comparisonData} onBack={() => setComparisonData(null)} />
        ) : !runData ? (
          /* ══════════════════════════════════════════════════════════════════════
             SCREEN 1: DUAL-ENTRY HOMEPAGE (EVALUATE → EXPLAIN → COMPARE)
             ══════════════════════════════════════════════════════════════════════ */
          <div className="space-y-12 max-w-5xl mx-auto pt-4 pb-16">
            {/* Signature Animation 1: Kinetic Editorial Hero */}
            <div className="text-center space-y-4">
              <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/20 text-xs font-semibold animate-hero-1">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Evaluate → Explain → Compare • TRACE AI</span>
              </div>

              <h1 className="text-4xl sm:text-6xl font-serif font-bold tracking-tight text-white leading-[1.1] animate-hero-1">
                Know when your AI{' '}
                <span className="emphasis-glitch">gets it wrong.</span>
              </h1>

              <p className="text-base sm:text-lg text-[#94A3B8] max-w-2xl mx-auto leading-relaxed animate-hero-2">
                Trace factual claims back to retrieved evidence, identify hallucinations with local
                cross-encoder inference, and compare RAG pipelines with cryptographic reproducibility.
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

            {/* ── TWO CLEAR ENTRY POINTS: Option A & Option B ── */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start animate-hero-3">
              {/* Option A: Bring Your Own Data (7 cols) */}
              <div className="lg:col-span-7 bg-[#141824] border border-[#1F2639] rounded-3xl p-6 sm:p-8 flex flex-col justify-between hover:border-[#10B981]/40 transition duration-200 shadow-xl space-y-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold bg-[#10B981]/15 text-[#10B981] px-3 py-1 rounded-lg border border-[#10B981]/30 flex items-center gap-1.5">
                      <Upload className="w-3.5 h-3.5" />
                      <span>Option A</span>
                    </span>

                    {/* Mode Toggle Pills */}
                    <div className="flex items-center gap-1 bg-[#0C0F17] p-1 rounded-xl border border-[#1F2639] text-xs font-mono">
                      <button
                        type="button"
                        onClick={() => {
                          setCustomMode('single');
                          setUploadError(null);
                        }}
                        className={`px-3 py-1 rounded-lg transition cursor-pointer ${
                          customMode === 'single'
                            ? 'bg-[#10B981] text-[#0C0F17] font-bold'
                            : 'text-[#94A3B8] hover:text-white'
                        }`}
                      >
                        Single Evaluation
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setCustomMode('compare');
                          setUploadError(null);
                        }}
                        className={`px-3 py-1 rounded-lg transition cursor-pointer ${
                          customMode === 'compare'
                            ? 'bg-[#10B981] text-[#0C0F17] font-bold'
                            : 'text-[#94A3B8] hover:text-white'
                        }`}
                      >
                        Compare Two
                      </button>
                    </div>
                  </div>

                  <div>
                    <h2 className="font-serif text-2xl font-bold text-white">Bring Your Own Data</h2>
                    <p className="text-xs sm:text-sm text-[#94A3B8] mt-1 leading-relaxed">
                      {customMode === 'single'
                        ? 'Evaluate your own RAG system by uploading your dataset and submission JSON files conforming to TRACE methodology contracts.'
                        : 'Upload two RAG submissions evaluated against the same dataset to compare retrieval, citation quality, and grounding side by side.'}
                    </p>
                  </div>

                  <form
                    id="custom-form"
                    onSubmit={customMode === 'single' ? handleUploadEvaluation : handleUploadComparison}
                    className="space-y-4 pt-2"
                  >
                    <div>
                      <label className="block text-xs font-medium text-[#F8FAFC] mb-1">
                        Evaluation Dataset (<span className="font-mono text-[11px] text-[#94A3B8]">trace.dataset/1.0</span>)
                      </label>
                      <input
                        type="file"
                        accept=".json"
                        onChange={(e) => setDatasetFile(e.target.files?.[0] || null)}
                        className="w-full text-xs text-[#94A3B8] file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[#10B981]/20 file:text-[#10B981] hover:file:bg-[#10B981]/30 file:cursor-pointer border border-[#1F2639] rounded-xl p-2 bg-[#0C0F17]"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-[#F8FAFC] mb-1">
                        {customMode === 'single' ? 'System Submission JSON' : 'Submission A (Baseline System)'} (<span className="font-mono text-[11px] text-[#94A3B8]">trace.submission/1.0</span>)
                      </label>
                      <input
                        type="file"
                        accept=".json"
                        onChange={(e) => setSubmissionFile(e.target.files?.[0] || null)}
                        className="w-full text-xs text-[#94A3B8] file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[#10B981]/20 file:text-[#10B981] hover:file:bg-[#10B981]/30 file:cursor-pointer border border-[#1F2639] rounded-xl p-2 bg-[#0C0F17]"
                      />
                    </div>

                    {customMode === 'compare' && (
                      <div className="animate-scale-in">
                        <label className="block text-xs font-medium text-[#F8FAFC] mb-1">
                          Submission B (Candidate System) (<span className="font-mono text-[11px] text-[#94A3B8]">trace.submission/1.0</span>)
                        </label>
                        <input
                          type="file"
                          accept=".json"
                          onChange={(e) => setSubmissionBFile(e.target.files?.[0] || null)}
                          className="w-full text-xs text-[#94A3B8] file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[#10B981]/20 file:text-[#10B981] hover:file:bg-[#10B981]/30 file:cursor-pointer border border-[#1F2639] rounded-xl p-2 bg-[#0C0F17]"
                        />
                      </div>
                    )}

                    <label className="flex items-center gap-2 pt-1 text-xs text-[#94A3B8] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={requireCitations}
                        onChange={(e) => setRequireCitations(e.target.checked)}
                        className="rounded border-[#1F2639] text-[#10B981] focus:ring-[#10B981] bg-[#0C0F17]"
                      />
                      <span>Require & evaluate inline citations</span>
                    </label>

                    {/* Template download links */}
                    <div className="flex flex-wrap items-center gap-2.5 pt-1 text-[11px] text-[#64748B]">
                      <button
                        type="button"
                        onClick={() => downloadSample('dataset')}
                        className="inline-flex items-center gap-1 hover:text-[#10B981] underline cursor-pointer active:scale-95"
                      >
                        <Download className="w-3 h-3" />
                        <span>Dataset template</span>
                      </button>
                      <span>•</span>
                      <button
                        type="button"
                        onClick={() => downloadSample('submission')}
                        className="inline-flex items-center gap-1 hover:text-[#10B981] underline cursor-pointer active:scale-95"
                      >
                        <Download className="w-3 h-3" />
                        <span>Submission A template</span>
                      </button>
                      {customMode === 'compare' && (
                        <>
                          <span>•</span>
                          <button
                            type="button"
                            onClick={() => downloadSample('submission_b')}
                            className="inline-flex items-center gap-1 hover:text-[#10B981] underline cursor-pointer active:scale-95"
                          >
                            <Download className="w-3 h-3" />
                            <span>Submission B template</span>
                          </button>
                        </>
                      )}
                    </div>

                    {uploadError && (
                      <div className="p-3 rounded-xl bg-[#7F1D1D]/30 border border-[#EF4444]/30 text-[#F87171] text-xs">
                        {uploadError}
                      </div>
                    )}
                  </form>
                </div>

                <div className="pt-2">
                  <button
                    type="submit"
                    form="custom-form"
                    disabled={
                      loading ||
                      !datasetFile ||
                      !submissionFile ||
                      (customMode === 'compare' && !submissionBFile)
                    }
                    className="w-full inline-flex items-center justify-center gap-2 bg-[#F8FAFC] hover:bg-white text-[#0C0F17] font-semibold py-3 px-4 rounded-xl transition cursor-pointer active:scale-[0.98] disabled:opacity-40 text-sm shadow-md"
                  >
                    {customMode === 'single' ? (
                      <>
                        <Upload className="w-4 h-4" />
                        <span>Evaluate Uploaded Files</span>
                      </>
                    ) : (
                      <>
                        <GitCompare className="w-4 h-4" />
                        <span>Compare Two Pipelines</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Option B: Explore Benchmarks (5 cols) */}
              <div className="lg:col-span-5 space-y-4">
                <div className="flex items-center justify-between px-1">
                  <span className="text-xs font-mono font-bold bg-[#1F2639] text-[#94A3B8] px-3 py-1 rounded-lg flex items-center gap-1.5">
                    <Database className="w-3.5 h-3.5 text-[#10B981]" />
                    <span>Option B</span>
                  </span>
                  <span className="text-[11px] font-mono text-[#64748B]">Ready-to-Evaluate Benchmarks</span>
                </div>

                <div className="space-y-4">
                  {(benchmarks.length > 0
                    ? benchmarks
                    : [
                        {
                          id: 'hariom-refund-demo-v1',
                          name: 'Customer Support & Refund Policies',
                          category: 'Enterprise Policy',
                          badge: '2 Pipelines • Ready to Compare',
                          description:
                            'Evaluates multi-tier refund policies, 30-day timelines, return shipping exceptions, and unsupported questions.',
                          item_count: 6,
                          corpus_size: 6,
                          license: 'CC-BY-4.0',
                          has_comparison: true,
                          pipeline_a: { name: 'Dense+BM25', model: 'Flash' },
                          pipeline_b: { name: 'Grounded', model: 'Pro' },
                        },
                        {
                          id: 'cloud-incident-runbooks-v1',
                          name: 'Cloud Infrastructure Runbooks',
                          category: 'DevOps & Cloud SRE',
                          badge: 'DevOps & Cloud SRE',
                          description:
                            'Mission-critical incident response benchmark testing PostgreSQL connection pool saturation, Redis LRU memory watermarks, and TLS renewals.',
                          item_count: 6,
                          corpus_size: 6,
                          license: 'CC-BY-4.0',
                          has_comparison: false,
                          pipeline_a: { name: 'DevOps Assistant', model: 'Llama-3-70b' },
                          pipeline_b: null,
                        },
                      ]
                  ).map((bm: any) => (
                    <div
                      key={bm.id}
                      className={`bg-[#141824] border rounded-3xl p-6 shadow-xl space-y-4 transition ${
                        bm.has_comparison
                          ? 'border-[#10B981]/30 hover:border-[#10B981]/60'
                          : 'border-[#1F2639] hover:border-[#10B981]/40'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span
                          className={`text-[10px] font-mono uppercase tracking-wider px-2.5 py-0.5 rounded-full font-bold ${
                            bm.has_comparison
                              ? 'text-[#10B981] bg-[#10B981]/15 border border-[#10B981]/30'
                              : 'text-[#94A3B8] bg-[#0C0F17] border border-[#1F2639]'
                          }`}
                        >
                          {bm.badge || bm.category}
                        </span>
                        <span className="text-[10px] font-mono text-[#64748B]">{bm.license}</span>
                      </div>

                      <div>
                        <h3 className="font-serif text-lg font-bold text-white">{bm.name}</h3>
                        <p className="text-xs text-[#94A3B8] mt-1 leading-relaxed">{bm.description}</p>
                      </div>

                      <div className="p-3 rounded-xl bg-[#0C0F17] border border-[#1F2639] text-xs font-mono space-y-1.5 text-[#94A3B8]">
                        <div className="flex items-center justify-between">
                          <span>Cases: {bm.item_count} questions</span>
                          <span>Corpus: {bm.corpus_size} passages</span>
                        </div>
                        {bm.pipeline_b ? (
                          <div className="text-[11px] text-[#64748B] pt-1 border-t border-[#1F2639]/60 flex items-center justify-between">
                            <span>A: {bm.pipeline_a?.name || 'Baseline'} ({bm.pipeline_a?.model || 'Flash'})</span>
                            <span className="text-[#10B981]">B: {bm.pipeline_b?.name || 'Grounded'} ({bm.pipeline_b?.model || 'Pro'})</span>
                          </div>
                        ) : (
                          <div className="text-[11px] text-[#64748B] pt-1 border-t border-[#1F2639]/60">
                            Model: {bm.pipeline_a?.model || 'Default'}
                          </div>
                        )}
                      </div>

                      <div className={`grid gap-2 pt-1 ${bm.has_comparison ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1'}`}>
                        <button
                          onClick={() => bm.id === 'hariom-refund-demo-v1' ? runSampleEvaluation() : runBenchmarkEvaluation(bm.id, 'a')}
                          disabled={loading}
                          className="inline-flex items-center justify-center gap-1.5 bg-[#1F2639] hover:bg-[#2A344D] text-[#E2E8F0] font-semibold py-2.5 px-3 rounded-xl transition cursor-pointer text-xs active:scale-95"
                        >
                          <Play className="w-3.5 h-3.5 fill-current text-[#10B981]" />
                          <span>{bm.has_comparison ? 'Evaluate Baseline' : 'Evaluate Benchmark'}</span>
                        </button>
                        {bm.has_comparison && (
                          <button
                            onClick={() => runBenchmarkComparison(bm.id)}
                            disabled={loading}
                            className="inline-flex items-center justify-center gap-1.5 bg-[#10B981] hover:bg-[#059669] text-[#0C0F17] font-bold py-2.5 px-3 rounded-xl transition cursor-pointer text-xs active:scale-95 shadow-md"
                          >
                            <GitCompare className="w-3.5 h-3.5" />
                            <span>Compare (Lab)</span>
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* ══════════════════════════════════════════════════════════════════════
             SCREEN 2 & 3: REFINED RESULTS & INTERACTIVE EVIDENCE WORKBENCH
             ══════════════════════════════════════════════════════════════════════ */
          <div className="space-y-8 animate-hero-1">
            {/* Top Navigation Bar */}
            <div className="flex items-center justify-between pb-2">
              <button
                onClick={() => {
                  setRunData(null);
                  setSelectedItemId(null);
                  setItemDetail(null);
                  setActiveClaimIndex(null);
                  setActivePassageId(null);
                }}
                className="inline-flex items-center gap-2 text-xs font-medium text-[#94A3B8] hover:text-white transition cursor-pointer active:scale-95"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Back to Evaluation Workspace</span>
              </button>

              <div className="flex items-center gap-3">
                <span className="text-xs font-mono bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30 px-3 py-1 rounded-full">
                  {runData.evaluation_tier}
                </span>
                {diagnostic?.isDemonstration && (
                  <span className="text-xs font-mono bg-[#1F2639] text-[#94A3B8] border border-[#2A324B] px-3 py-1 rounded-full">
                    Demonstration Benchmark • 5 Cases
                  </span>
                )}
              </div>
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
                  className="inline-flex items-center gap-1.5 text-xs font-mono font-medium text-[#94A3B8] hover:text-[#10B981] cursor-pointer transition active:scale-95"
                >
                  {showTechDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  <span>{showTechDetails ? 'Hide Technical Metadata & Hashes' : 'Technical Details & Reproducibility'}</span>
                </button>

                {showTechDetails && (
                  <div className="mt-4 p-4 rounded-xl bg-[#0C0F17] border border-[#1F2639] grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono text-[#94A3B8] animate-hero-1">
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
                            className="text-[#94A3B8] hover:text-[#10B981] p-1 cursor-pointer active:scale-90"
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

            {/* ── Signature Animation 4: Staggered Dimension Reveal & Count-ups ── */}
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
                <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 shadow-lg flex flex-col justify-between space-y-4 animate-card-1">
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
                        return <AnimatedNumber value={avg} suffix="%" />;
                      })()}
                    </div>
                    <div className="text-[11px] text-[#64748B] mt-1.5 font-mono">
                      Hit@5 • Recall@5: {formatPercent(runData.items.reduce((acc, i) => acc + (i.retrieval?.recall_at_k?.['5'] || 0), 0) / (runData.items.length || 1))}
                    </div>
                  </div>
                </div>

                {/* 2. Answered correctly */}
                <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 shadow-lg flex flex-col justify-between space-y-4 animate-card-2">
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
                      <AnimatedNumber value={runData.summary.combined?.mean_fact_recall} suffix="%" />
                    </div>
                    <div className="text-[11px] text-[#64748B] mt-1.5 font-mono">
                      Fact Recall • Token F1: {formatDecimal(runData.summary.combined?.mean_token_f1)}
                    </div>
                  </div>
                </div>

                {/* 3. Backed up its claims */}
                <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 shadow-lg flex flex-col justify-between space-y-4 animate-card-3">
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
                      <AnimatedNumber value={runData.summary.combined?.mean_citation_precision} suffix="%" />
                    </div>
                    <div className="text-[11px] text-[#64748B] mt-1.5 font-mono">
                      Citation Precision • Phantom: {formatPercent(runData.summary.combined?.mean_phantom_rate)}
                    </div>
                  </div>
                </div>

                {/* 4. Avoided making things up */}
                <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 shadow-lg flex flex-col justify-between space-y-4 animate-card-4">
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
                        return <AnimatedNumber value={1 - rate} suffix="%" />;
                      })()}
                    </div>
                    <div className="text-[11px] text-[#64748B] mt-1.5 font-mono">
                      Supported Claims • Unsupported: {formatPercent(runData.summary.combined?.mean_unsupported_claim_rate)}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Signature Animation 5: Interactive Evidence Tracing Workbench ── */}
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
                      className={`px-2.5 py-1 rounded-md cursor-pointer transition active:scale-95 ${
                        filterStatus === 'all'
                          ? 'bg-[#10B981] text-[#0C0F17] font-bold'
                          : 'text-[#94A3B8] hover:text-white'
                      }`}
                    >
                      All ({runData.items.length})
                    </button>
                    <button
                      onClick={() => setFilterStatus('failed')}
                      className={`px-2.5 py-1 rounded-md cursor-pointer transition active:scale-95 ${
                        filterStatus === 'failed'
                          ? 'bg-[#F87171] text-[#0C0F17] font-bold'
                          : 'text-[#94A3B8] hover:text-white'
                      }`}
                    >
                      Failed ({diagnostic?.failedCount})
                    </button>
                    <button
                      onClick={() => setFilterStatus('passed')}
                      className={`px-2.5 py-1 rounded-md cursor-pointer transition active:scale-95 ${
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
                        className={`w-full text-left p-4 transition-all duration-150 cursor-pointer flex flex-col gap-2 ${
                          isSelected
                            ? 'bg-[#1A2030] border-l-4 border-l-[#10B981] shadow-inner'
                            : 'hover:bg-[#1A2030]/50 border-l-4 border-l-transparent active:bg-[#1A2030]/30'
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

              {/* Right Column: Signature Evidence Inspector with Interactive Tracing */}
              <div className="lg:col-span-7 space-y-6">
                {detailLoading ? (
                  <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-12 text-center shadow-xl">
                    <div className="w-6 h-6 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                    <p className="text-sm text-[#94A3B8]">Loading diagnostic trace and retrieved evidence...</p>
                  </div>
                ) : itemDetail ? (
                  <div className="bg-[#141824] border border-[#1F2639] rounded-2xl shadow-xl p-6 sm:p-8 space-y-8 animate-hero-1">
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

                    {/* B. What the AI Answered with Interactive Claim Tracing */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono uppercase tracking-wider text-[#94A3B8] block">
                          What the AI Answered
                        </span>
                        <span className="text-[11px] text-[#10B981] font-mono flex items-center gap-1">
                          <Target className="w-3.5 h-3.5" />
                          <span>Click sentences below to trace evidence</span>
                        </span>
                      </div>

                      {/* Interactive Sentence Claim Badges */}
                      <div className="p-4 rounded-xl bg-[#0C0F17] border border-[#1F2639] text-sm text-[#F8FAFC] leading-relaxed space-y-2">
                        {itemDetail.claims && itemDetail.claims.length > 0 ? (
                          itemDetail.claims.map((claim) => {
                            const isClaimActive = activeClaimIndex === claim.sentence_index;
                            const isSupported = claim.grounding_label === 'supported';

                            return (
                              <span
                                key={claim.sentence_index}
                                onClick={() => toggleClaimTrace(claim.sentence_index)}
                                className={`inline-block mr-1.5 p-1 rounded-md transition-all duration-150 cursor-pointer ${
                                  isClaimActive
                                    ? isSupported
                                      ? 'bg-[#10B981]/20 border border-[#10B981] text-white shadow-sm'
                                      : 'bg-[#EF4444]/20 border border-[#EF4444] text-white shadow-sm'
                                    : 'hover:bg-[#1A2030] text-[#F8FAFC]'
                                }`}
                                title="Click to highlight supporting passage"
                              >
                                <span className={`text-[10px] font-mono px-1 py-0.2 rounded mr-1.5 ${
                                  isSupported ? 'bg-[#10B981]/25 text-[#10B981]' : 'bg-[#EF4444]/25 text-[#F87171]'
                                }`}>
                                  S{claim.sentence_index + 1}
                                </span>
                                {claim.sentence_text}{' '}
                              </span>
                            );
                          })
                        ) : (
                          <p>{itemDetail.answer || <span className="text-[#64748B] italic">No answer provided</span>}</p>
                        )}
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

                    {/* D. What the Retrieved Evidence Actually Says (Interactive Tracing Target) */}
                    <div ref={evidenceSectionRef} className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono uppercase tracking-wider text-[#94A3B8] flex items-center gap-2">
                          <span>What the Retrieved Evidence Actually Says</span>
                          {activeClaimIndex !== null && (
                            <span className="text-[10px] text-[#10B981] bg-[#10B981]/15 px-2 py-0.5 rounded-full font-sans">
                              Tracing Sentence S{activeClaimIndex + 1}
                            </span>
                          )}
                        </span>
                        <span className="text-xs text-[#64748B] font-mono">
                          {itemDetail.retrieved?.length || 0} passage{itemDetail.retrieved?.length === 1 ? '' : 's'} retrieved
                        </span>
                      </div>

                      <div className="space-y-3">
                        {itemDetail.retrieved && itemDetail.retrieved.length > 0 ? (
                          itemDetail.retrieved.map((p, idx) => {
                            const isLinkedToActiveClaim = activePassageId === p.id;
                            const activeClaim = activeClaimIndex !== null ? itemDetail.claims?.[activeClaimIndex] : null;
                            const isClaimSupported = activeClaim?.grounding_label === 'supported';

                            return (
                              <div
                                key={p.id}
                                onClick={() => togglePassageTrace(p.id)}
                                className={`border rounded-xl p-4 bg-[#0C0F17] space-y-2 text-xs transition-all duration-200 cursor-pointer ${
                                  isLinkedToActiveClaim
                                    ? isClaimSupported
                                      ? 'evidence-target-active'
                                      : 'evidence-target-conflict'
                                    : 'border-[#1F2639] hover:border-[#2A324B]'
                                }`}
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <span className="font-mono font-bold text-[#10B981] bg-[#10B981]/15 px-2 py-0.5 rounded text-[11px]">
                                      {p.id}
                                    </span>
                                    <span className="text-[11px] text-[#64748B] font-mono">Rank #{idx + 1}</span>
                                    {isLinkedToActiveClaim && (
                                      <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                                        isClaimSupported ? 'bg-[#10B981] text-[#0C0F17]' : 'bg-[#EF4444] text-[#0C0F17]'
                                      }`}>
                                        {isClaimSupported ? `Evidence for S${(activeClaimIndex || 0) + 1}` : `Fails to support S${(activeClaimIndex || 0) + 1}`}
                                      </span>
                                    )}
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
                            );
                          })
                        ) : (
                          <p className="text-xs text-[#64748B] italic">No retrieved passages recorded.</p>
                        )}
                      </div>
                    </div>

                    {/* E. Supporting Technical Details */}
                    <div className="border-t border-[#1F2639] pt-4">
                      <button
                        onClick={() => setShowEvidenceTechDetails(!showEvidenceTechDetails)}
                        className="inline-flex items-center gap-2 text-xs font-mono font-semibold text-[#10B981] hover:underline cursor-pointer active:scale-95"
                      >
                        {showEvidenceTechDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        <span>
                          {showEvidenceTechDetails
                            ? 'Hide Sentence Grounding Trace & Technical Metrics'
                            : 'View Sentence-by-Sentence Grounding Trace & NLI Scores'}
                        </span>
                      </button>

                      {showEvidenceTechDetails && (
                        <div className="mt-4 space-y-6 animate-hero-1">
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
          <div className="bg-[#141824] border border-[#1F2639] rounded-2xl max-w-2xl w-full p-6 sm:p-8 space-y-6 shadow-2xl relative max-h-[90vh] overflow-y-auto animate-card-1">
            <button
              onClick={() => setShowHowItWorks(false)}
              className="absolute top-6 right-6 text-[#94A3B8] hover:text-white cursor-pointer active:scale-90"
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
                className="bg-[#10B981] text-[#0C0F17] text-xs font-semibold px-4 py-2 rounded-lg hover:bg-[#059669] transition cursor-pointer active:scale-95"
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
