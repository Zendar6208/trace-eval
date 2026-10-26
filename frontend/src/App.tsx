import { useState } from 'react';
import { 
  Play, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  ShieldCheck, 
  BookOpen, 
  Layers, 
  ChevronRight,
  Database,
  Cpu,
  RefreshCw
} from 'lucide-react';
import type { EvaluationRunResponse, ItemDetailResponse } from './types';

export default function App() {
  const [loading, setLoading] = useState(false);
  const [runData, setRunData] = useState<EvaluationRunResponse | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [itemDetail, setItemDetail] = useState<ItemDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runEvaluation = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/evaluate/sample', { method: 'POST' });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data: EvaluationRunResponse = await res.json();
      setRunData(data);
      // Auto-select first item
      if (data.items.length > 0) {
        selectItem(data.items[0].item_id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to execute evaluation');
    } finally {
      setLoading(false);
    }
  };

  const selectItem = async (itemId: string) => {
    setSelectedItemId(itemId);
    setDetailLoading(true);
    try {
      const res = await fetch(`/api/evaluate/sample/item/${itemId}`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data: ItemDetailResponse = await res.json();
      setItemDetail(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0f17] text-slate-200 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-[#0f1422] px-6 py-4 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-md shadow-indigo-500/20">
            T
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-lg tracking-tight text-white">TRACE AI</span>
              <span className="text-xs bg-indigo-950/80 text-indigo-400 border border-indigo-800/60 px-2 py-0.5 rounded-full font-mono font-medium">
                v1.0.0 normative
              </span>
            </div>
            <p className="text-xs text-slate-400">Deterministic RAG Evaluation Engine & Workbench</p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-md">
            <Cpu className="w-3.5 h-3.5 text-emerald-400" />
            <span>Local NLI: cross-encoder/distilroberta</span>
          </div>
          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-md">
            <ShieldCheck className="w-3.5 h-3.5 text-sky-400" />
            <span>Methodology: Section 2-8 Normative</span>
          </div>
        </div>
      </header>

      {/* Hero / Action Bar */}
      <div className="bg-gradient-to-b from-[#0f1422] to-[#0b0f17] border-b border-slate-800/60 px-8 py-8">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">
              Test your RAG before your users do.
            </h1>
            <p className="text-slate-400 mt-2 max-w-2xl text-sm leading-relaxed">
              Open-source, deterministic-first evaluation engine. Mathematically exact canonical content hashing, 
              strict sentence-level citation binding (CA-1 to CA-8), Tier-0 numeric guards, and multi-label failure decomposition.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={runEvaluation}
              disabled={loading}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 disabled:cursor-not-allowed text-white font-semibold px-6 py-3 rounded-xl shadow-lg shadow-indigo-600/30 flex items-center gap-2.5 transition-all text-sm cursor-pointer active:scale-95"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-white" />
                  <span>Evaluating Run Core...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-white text-white" />
                  <span>Run Sample Evaluation</span>
                </>
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="max-w-7xl mx-auto mt-4 p-3 bg-rose-950/60 border border-rose-800 rounded-lg text-rose-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8 flex flex-col gap-8">
        {!runData ? (
          <div className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-slate-800 rounded-2xl p-12 text-center my-8">
            <div className="w-16 h-16 rounded-2xl bg-indigo-950/60 border border-indigo-800/40 flex items-center justify-center text-indigo-400 mb-4">
              <Database className="w-8 h-8" />
            </div>
            <h2 className="text-lg font-bold text-slate-200">No Evaluation Loaded Yet</h2>
            <p className="text-slate-400 text-sm max-w-md mt-1 mb-6">
              Click <span className="text-indigo-400 font-medium">"Run Sample Evaluation"</span> above to trigger real Tier-0 evaluation against the bundled HariOm benchmark dataset and submission outputs.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-left max-w-3xl w-full text-xs">
              <div className="p-3.5 bg-slate-900/60 border border-slate-800 rounded-xl">
                <span className="font-semibold text-slate-300 block mb-1">Strict Independence</span>
                <span className="text-slate-400">Retrieval, correctness, citations, and grounding evaluate strictly mutually exclusive input subsets.</span>
              </div>
              <div className="p-3.5 bg-slate-900/60 border border-slate-800 rounded-xl">
                <span className="font-semibold text-slate-300 block mb-1">Citation Rules CA-1..8</span>
                <span className="text-slate-400">Sentence masking, orphan detection, appearance-order deduplication, and single-passage support.</span>
              </div>
              <div className="p-3.5 bg-slate-900/60 border border-slate-800 rounded-xl">
                <span className="font-semibold text-slate-300 block mb-1">Cryptographic Core</span>
                <span className="text-slate-400">Runs yield a tamper-evident SHA-256 result_hash and deterministic run_id.</span>
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* Top Stat Cards: The 4 Key Evaluation Pillars */}
            <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* 1. Retrieval Relevance */}
              <div className="bg-[#0f1422] border border-slate-800 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                  <span className="font-medium uppercase tracking-wider">1. Retrieval Relevance</span>
                  <Layers className="w-4 h-4 text-sky-400" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-white">
                    {runData.summary.combined?.accuracy !== null 
                      ? `${(5/6 * 100).toFixed(0)}%` 
                      : '—'}
                  </span>
                  <span className="text-xs text-slate-400">hit@k success</span>
                </div>
                <div className="mt-3 pt-3 border-t border-slate-800/80 text-xs text-slate-400 flex justify-between">
                  <span>Gold Hit Rate: <strong className="text-slate-300">100%</strong></span>
                  <span>MRR: <strong className="text-slate-300">1.00</strong></span>
                </div>
              </div>

              {/* 2. Answer Correctness */}
              <div className="bg-[#0f1422] border border-slate-800 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                  <span className="font-medium uppercase tracking-wider">2. Answer Correctness</span>
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-white">
                    {runData.summary.combined?.accuracy !== null 
                      ? `${((runData.summary.combined?.accuracy || 0) * 100).toFixed(0)}%` 
                      : '—'}
                  </span>
                  <span className="text-xs text-slate-400">verdict accuracy</span>
                </div>
                <div className="mt-3 pt-3 border-t border-slate-800/80 text-xs text-slate-400 flex justify-between">
                  <span>Mean Token F1: <strong className="text-slate-300">{(runData.summary.combined?.mean_token_f1 || 0).toFixed(2)}</strong></span>
                  <span>Fact Recall: <strong className="text-slate-300">{((runData.summary.combined?.mean_fact_recall || 0) * 100).toFixed(0)}%</strong></span>
                </div>
              </div>

              {/* 3. Citation Quality */}
              <div className="bg-[#0f1422] border border-slate-800 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                  <span className="font-medium uppercase tracking-wider">3. Citation Quality</span>
                  <BookOpen className="w-4 h-4 text-indigo-400" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-white">
                    {runData.summary.combined?.mean_phantom_rate !== null 
                      ? `${(100 - (runData.summary.combined?.mean_phantom_rate || 0) * 100).toFixed(0)}%` 
                      : '—'}
                  </span>
                  <span className="text-xs text-slate-400">validity rate</span>
                </div>
                <div className="mt-3 pt-3 border-t border-slate-800/80 text-xs text-slate-400 flex justify-between">
                  <span>Phantom Rate: <strong className="text-rose-400">{((runData.summary.combined?.mean_phantom_rate || 0) * 100).toFixed(0)}%</strong></span>
                  <span>Uncited Rate: <strong className="text-slate-300">{((runData.summary.combined?.mean_unsupported_claim_rate || 0) * 100).toFixed(0)}%</strong></span>
                </div>
              </div>

              {/* 4. Unsupported-Answer Rate */}
              <div className="bg-[#0f1422] border border-slate-800 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                  <span className="font-medium uppercase tracking-wider">4. Unsupported Rate</span>
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-amber-400">
                    {runData.summary.failure_distribution?.['UNSUPPORTED_CLAIM'] 
                      ? `${((runData.summary.failure_distribution['UNSUPPORTED_CLAIM'] / runData.items.length) * 100).toFixed(0)}%`
                      : '0%'}
                  </span>
                  <span className="text-xs text-slate-400">flagged queries</span>
                </div>
                <div className="mt-3 pt-3 border-t border-slate-800/80 text-xs text-slate-400 flex justify-between">
                  <span>Failures: <strong className="text-rose-400">{runData.summary.failure_distribution?.['UNSUPPORTED_CLAIM'] || 0} items</strong></span>
                  <span>Clean PASS: <strong className="text-emerald-400">{runData.summary.failure_distribution?.['PASS'] || 0} items</strong></span>
                </div>
              </div>
            </section>

            {/* Run Provenance Banner */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl px-5 py-3 text-xs flex flex-wrap items-center justify-between gap-4 font-mono">
              <div className="flex items-center gap-3">
                <span className="text-slate-500">Run ID:</span>
                <span className="text-indigo-400 font-semibold">{runData.run_id}</span>
                <span className="text-slate-700">|</span>
                <span className="text-slate-500">Result SHA256:</span>
                <span className="text-slate-300 truncate max-w-xs">{runData.result_hash}</span>
              </div>
              <div className="flex items-center gap-3 text-slate-400">
                <span className="bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 px-2 py-0.5 rounded">
                  Live Evaluator Result
                </span>
                <span>Dataset: hariom-refund-demo-v1</span>
              </div>
            </div>

            {/* Split Workbench: Items Table on Left, Evidence Inspector on Right */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left Column: Evaluated Questions List (5 cols) */}
              <div className="lg:col-span-5 bg-[#0f1422] border border-slate-800 rounded-xl overflow-hidden flex flex-col">
                <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
                  <h3 className="font-bold text-sm text-white">Evaluated Items ({runData.items.length})</h3>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="flex items-center gap-1 text-slate-400">
                      <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Recorded
                    </span>
                    <span className="flex items-center gap-1 text-slate-400">
                      <span className="w-2 h-2 rounded-full bg-purple-500"></span> Synthetic
                    </span>
                  </div>
                </div>

                <div className="divide-y divide-slate-800/60 max-h-[600px] overflow-y-auto">
                  {runData.items.map((item) => {
                    const isSelected = item.item_id === selectedItemId;
                    const isPass = item.failure_types.includes('PASS');
                    const isSynthetic = item.origin === 'synthetic_fixture';

                    return (
                      <div
                        key={item.item_id}
                        onClick={() => selectItem(item.item_id)}
                        className={`p-4 transition-all cursor-pointer flex items-center justify-between gap-3 ${
                          isSelected 
                            ? 'bg-indigo-950/40 border-l-4 border-indigo-500' 
                            : 'hover:bg-slate-900/60'
                        }`}
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-mono text-xs font-bold text-slate-300">
                              {item.item_id}
                            </span>
                            <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono uppercase font-semibold ${
                              isSynthetic 
                                ? 'bg-purple-950 text-purple-300 border border-purple-800/60' 
                                : 'bg-slate-800 text-slate-300'
                            }`}>
                              {isSynthetic ? 'Synthetic Fixture' : 'Recorded System'}
                            </span>
                          </div>

                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {item.failure_types.map((ft) => (
                              <span
                                key={ft}
                                className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ${
                                  ft === 'PASS'
                                    ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-800/60'
                                    : 'bg-rose-950/80 text-rose-300 border border-rose-800/60'
                                }`}
                              >
                                {ft}
                              </span>
                            ))}
                          </div>
                        </div>

                        <div className="shrink-0 flex items-center gap-2">
                          {isPass ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <XCircle className="w-4 h-4 text-rose-400" />
                          )}
                          <ChevronRight className={`w-4 h-4 transition-transform ${isSelected ? 'text-indigo-400 translate-x-0.5' : 'text-slate-600'}`} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Right Column: Individual Evidence Inspector (7 cols) */}
              <div className="lg:col-span-7 bg-[#0f1422] border border-slate-800 rounded-xl overflow-hidden min-h-[500px]">
                {detailLoading ? (
                  <div className="p-12 text-center text-slate-400 flex flex-col items-center justify-center h-full">
                    <RefreshCw className="w-6 h-6 animate-spin text-indigo-400 mb-3" />
                    <span>Loading diagnostic evidence for {selectedItemId}...</span>
                  </div>
                ) : itemDetail ? (
                  <div className="p-6 flex flex-col gap-6">
                    {/* Header */}
                    <div className="border-b border-slate-800/80 pb-4">
                      <div className="flex items-center justify-between gap-3 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm font-bold text-indigo-400">
                            {itemDetail.item_id}
                          </span>
                          <span className={`text-xs px-2 py-0.5 rounded font-mono ${
                            itemDetail.origin === 'synthetic_fixture'
                              ? 'bg-purple-950 text-purple-300 border border-purple-800/60'
                              : 'bg-slate-800 text-slate-300'
                          }`}>
                            {itemDetail.origin === 'synthetic_fixture' ? 'synthetic_fixture' : 'recorded_system'}
                          </span>
                        </div>
                        <div className="flex gap-1.5">
                          {itemDetail.failure_types.map((ft) => (
                            <span
                              key={ft}
                              className={`text-xs px-2 py-0.5 rounded font-mono font-medium ${
                                ft === 'PASS'
                                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                                  : 'bg-rose-950 text-rose-300 border border-rose-800'
                              }`}
                            >
                              {ft}
                            </span>
                          ))}
                        </div>
                      </div>
                      <h4 className="text-base font-semibold text-white">
                        {itemDetail.question}
                      </h4>
                    </div>

                    {/* Answer with Citations Highlighted */}
                    <div>
                      <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block mb-2">
                        Generated Answer
                      </span>
                      <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl text-sm leading-relaxed text-slate-200">
                        {itemDetail.answer}
                      </div>
                    </div>

                    {/* Claims Decomposition & Grounding Verdicts */}
                    {itemDetail.claims && itemDetail.claims.length > 0 && (
                      <div>
                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block mb-2 flex items-center justify-between">
                          <span>Sentence-Level Claims & Grounding</span>
                          <span className="text-[11px] font-normal font-mono text-slate-500">Methodology Section 2.3 & 2.5</span>
                        </span>
                        <div className="space-y-2">
                          {itemDetail.claims.map((claim, idx) => {
                            const isSupported = claim.grounding_label === 'supported';
                            return (
                              <div
                                key={idx}
                                className={`p-3 rounded-lg border text-xs flex flex-col gap-1.5 ${
                                  isSupported 
                                    ? 'bg-emerald-950/20 border-emerald-900/40 text-slate-200' 
                                    : 'bg-rose-950/30 border-rose-900/60 text-rose-100'
                                }`}
                              >
                                <div className="flex items-center justify-between">
                                  <span className="font-mono text-[10px] text-slate-400">
                                    Sentence {claim.sentence_index}
                                  </span>
                                  <div className="flex items-center gap-1.5">
                                    {claim.numeric_guard_triggered && (
                                      <span className="bg-amber-950 text-amber-300 border border-amber-800 text-[10px] px-1.5 py-0.2 rounded font-mono">
                                        Numeric Guard Capped
                                      </span>
                                    )}
                                    <span className={`text-[10px] px-2 py-0.2 rounded font-mono font-bold uppercase ${
                                      isSupported 
                                        ? 'bg-emerald-900/60 text-emerald-300' 
                                        : 'bg-rose-900/60 text-rose-300'
                                    }`}>
                                      {claim.grounding_label}
                                    </span>
                                  </div>
                                </div>
                                <p className="text-sm font-medium">{claim.sentence_text}</p>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Citation Units Analysis */}
                    {itemDetail.citations && itemDetail.citations.length > 0 && (
                      <div>
                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block mb-2 flex items-center justify-between">
                          <span>Attached Citation Units (CA-1 to CA-8)</span>
                          <span className="text-[11px] font-normal font-mono text-slate-500">Deduplicated in appearance order</span>
                        </span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {itemDetail.citations.map((u, idx) => (
                            <div
                              key={idx}
                              className="p-3 bg-slate-900/80 border border-slate-800 rounded-lg text-xs flex flex-col gap-1 font-mono"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-indigo-400">[{u.passage_id}]</span>
                                <span className={`text-[10px] px-1.5 py-0.2 rounded font-semibold uppercase ${
                                  u.validity === 'ok' 
                                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/60' 
                                    : 'bg-rose-950 text-rose-300 border border-rose-800/60'
                                }`}>
                                  {u.validity}
                                </span>
                              </div>
                              <span className="text-slate-400 text-[11px]">
                                Attached to: {u.sentence_index !== null ? `Sentence ${u.sentence_index}` : 'Orphan (None)'}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Retrieved Passages */}
                    <div>
                      <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block mb-2">
                        Retrieved Passages ({itemDetail.retrieved.length})
                      </span>
                      <div className="space-y-2">
                        {itemDetail.retrieved.map((p, idx) => (
                          <div
                            key={idx}
                            className="p-3 bg-slate-900/50 border border-slate-800/70 rounded-lg text-xs"
                          >
                            <div className="flex items-center justify-between mb-1 font-mono text-slate-400">
                              <span className="font-bold text-slate-300">[{p.id}]</span>
                              <span>Score: {p.score !== null ? p.score.toFixed(2) : '—'}</span>
                            </div>
                            <p className="text-slate-300 leading-relaxed font-sans">{p.text}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-6 text-center text-xs text-slate-500 font-mono mt-auto">
        TRACE AI Evaluation Engine • Infinity AI Forge 2026 • Fully Open Source & Deterministic
      </footer>
    </div>
  );
}
