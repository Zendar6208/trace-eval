import { useState } from 'react';
import {
  ArrowLeft,
  CheckCircle2,
  GitCompare,
  TrendingUp,
  TrendingDown,
  Minus,
  Check,
  X,
  ChevronDown,
  ChevronUp,
  Copy,
  Layers,
  Sparkles
} from 'lucide-react';
import type { ComparisonRunResponse } from './types';

interface ComparisonViewProps {
  data: ComparisonRunResponse;
  onBack: () => void;
}

export function ComparisonView({ data, onBack }: ComparisonViewProps) {
  const [filter, setFilter] = useState<'all' | 'improved' | 'passed' | 'failed'>('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showTechDetails, setShowTechDetails] = useState(false);
  const [copiedHash, setCopiedHash] = useState<'a' | 'b' | null>(null);

  const formatPercent = (val: number | null | undefined): string => {
    if (val === null || val === undefined) return 'N/A';
    return `${Math.round(val * 100)}%`;
  };

  const formatDelta = (val: number, isReductionGood = false) => {
    const isZero = Math.abs(val) < 0.005;
    if (isZero) {
      return (
        <span className="inline-flex items-center gap-1 text-[#94A3B8] font-mono text-xs">
          <Minus className="w-3 h-3" />
          <span>0.0%</span>
        </span>
      );
    }
    const isGood = isReductionGood ? val < 0 : val > 0;
    const sign = val > 0 ? '+' : '';
    const text = `${sign}${Math.round(val * 100)}%`;
    return (
      <span
        className={`inline-flex items-center gap-1 font-mono text-xs font-bold px-2 py-0.5 rounded-full ${
          isGood
            ? 'bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30'
            : 'bg-[#EF4444]/15 text-[#F87171] border border-[#EF4444]/30'
        }`}
      >
        {isGood ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
        <span>{text}</span>
      </span>
    );
  };

  const copyHash = (hash: string, target: 'a' | 'b') => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(target);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const filteredQuestions = data.questions.filter((q) => {
    if (filter === 'improved') return q.verdict === 'b_improved';
    if (filter === 'passed') return q.verdict === 'both_passed';
    if (filter === 'failed') return q.verdict === 'both_failed' || q.verdict === 'a_better';
    return true;
  });

  const improvedCount = data.questions.filter((q) => q.verdict === 'b_improved').length;
  const bothPassedCount = data.questions.filter((q) => q.verdict === 'both_passed').length;
  const bothFailedCount = data.questions.filter((q) => q.verdict === 'both_failed').length;

  return (
    <div className="space-y-10 animate-fade-in pb-16">
      {/* ── Top Navigation Bar ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#1F2639]">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="inline-flex items-center gap-2 text-sm text-[#94A3B8] hover:text-white transition bg-[#141824] hover:bg-[#1A2234] border border-[#1F2639] px-3.5 py-2 rounded-xl cursor-pointer active:scale-95 shadow-sm"
          >
            <ArrowLeft className="w-4 h-4 text-[#10B981]" />
            <span>Back to Workspace</span>
          </button>
          <div className="h-5 w-[1px] bg-[#1F2639] hidden sm:block" />
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/30 text-xs font-semibold">
            <GitCompare className="w-3.5 h-3.5" />
            <span>RAG Comparison Lab</span>
          </div>
        </div>

        <button
          onClick={() => setShowTechDetails(!showTechDetails)}
          className="inline-flex items-center gap-2 text-xs text-[#94A3B8] hover:text-[#F8FAFC] transition font-mono cursor-pointer self-start sm:self-auto"
        >
          <span>Cryptographic Hashes & Config</span>
          {showTechDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Expandable Technical Details */}
      {showTechDetails && (
        <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 text-xs font-mono space-y-4 animate-scale-in">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 rounded-xl bg-[#0C0F17] border border-[#1F2639] space-y-1.5">
              <span className="text-[#64748B] block text-[10px] uppercase tracking-wider">System A Result Hash</span>
              <div className="flex items-center justify-between gap-2">
                <span className="text-[#E2E8F0] truncate">{data.system_a.result_hash}</span>
                <button
                  onClick={() => copyHash(data.system_a.result_hash, 'a')}
                  className="text-[#94A3B8] hover:text-[#10B981] p-1 cursor-pointer"
                >
                  {copiedHash === 'a' ? <Check className="w-3.5 h-3.5 text-[#10B981]" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-[#0C0F17] border border-[#1F2639] space-y-1.5">
              <span className="text-[#64748B] block text-[10px] uppercase tracking-wider">System B Result Hash</span>
              <div className="flex items-center justify-between gap-2">
                <span className="text-[#E2E8F0] truncate">{data.system_b.result_hash}</span>
                <button
                  onClick={() => copyHash(data.system_b.result_hash, 'b')}
                  className="text-[#94A3B8] hover:text-[#10B981] p-1 cursor-pointer"
                >
                  {copiedHash === 'b' ? <Check className="w-3.5 h-3.5 text-[#10B981]" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          </div>
          <div className="text-[11px] text-[#64748B]">
            Evaluation conducted under normative TRACE Methodology v1.0.0. Both pipelines evaluated on identical dataset `{data.dataset.dataset_id}` using shared NLI thresholds.
          </div>
        </div>
      )}

      {/* ── Editorial Diagnostic Header ── */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-mono uppercase tracking-widest text-[#94A3B8] font-semibold">
            {data.dataset.name} • {data.dataset.item_count} Evaluation Cases
          </span>
        </div>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-gradient-to-r from-[#141824] via-[#10B981]/5 to-[#141824] border border-[#10B981]/30 rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="space-y-2 max-w-2xl">
            <h1 className="text-2xl sm:text-3xl font-serif font-bold text-white leading-tight">
              {data.deltas.pass_count_delta > 0
                ? `${data.system_b.name} outperforms baseline with +${data.deltas.pass_count_delta} passing question${data.deltas.pass_count_delta > 1 ? 's' : ''}.`
                : `${data.system_a.name} vs ${data.system_b.name}`}
            </h1>
            <p className="text-sm text-[#94A3B8] leading-relaxed">
              {improvedCount > 0
                ? `System B eliminated ${improvedCount} critical failure${improvedCount > 1 ? 's' : ''} found in System A, raising citation precision by ${Math.round(data.deltas.citation_precision_delta * 100)}% with verified cross-encoder grounding.`
                : `Both systems evaluated with deterministic and NLI verification across 4 core dimensions.`}
            </p>
          </div>

          {/* Pass comparison pill badge */}
          <div className="flex items-center gap-4 bg-[#0C0F17]/80 border border-[#1F2639] rounded-2xl p-4 shrink-0 font-mono">
            <div className="text-center">
              <span className="text-[10px] text-[#64748B] block uppercase tracking-wider">System A</span>
              <span className="text-xl font-bold text-[#E2E8F0]">
                {data.system_a.metrics.pass_count}/{data.dataset.item_count}
              </span>
            </div>
            <div className="text-[#64748B] font-bold text-sm">vs</div>
            <div className="text-center">
              <span className="text-[10px] text-[#10B981] block uppercase tracking-wider">System B</span>
              <span className="text-xl font-bold text-[#10B981]">
                {data.system_b.metrics.pass_count}/{data.dataset.item_count}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── 4 Dimensions Side-by-Side Cards ── */}
      <div className="space-y-4">
        <h2 className="text-lg font-serif font-bold text-white flex items-center gap-2">
          <Layers className="w-4 h-4 text-[#10B981]" />
          <span>Core Dimension Benchmarks</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 1. Retrieval */}
          <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 shadow-lg flex flex-col justify-between space-y-4">
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono uppercase tracking-wider text-[#94A3B8] font-semibold">
                  1. Retrieval
                </span>
                {formatDelta(data.deltas.retrieval_hit_delta)}
              </div>
              <h3 className="font-serif text-base font-bold text-white">Found right documents</h3>
            </div>

            <div className="space-y-2 pt-3 border-t border-[#1F2639]">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#94A3B8] truncate max-w-[130px]">{data.system_a.name}</span>
                <span className="font-mono font-bold text-white">{formatPercent(data.system_a.metrics.retrieval_hit)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#10B981] truncate max-w-[130px]">{data.system_b.name}</span>
                <span className="font-mono font-bold text-[#10B981]">{formatPercent(data.system_b.metrics.retrieval_hit)}</span>
              </div>
            </div>
          </div>

          {/* 2. Correctness */}
          <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 shadow-lg flex flex-col justify-between space-y-4">
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono uppercase tracking-wider text-[#94A3B8] font-semibold">
                  2. Correctness
                </span>
                {formatDelta(data.deltas.fact_recall_delta)}
              </div>
              <h3 className="font-serif text-base font-bold text-white">Answered correctly</h3>
            </div>

            <div className="space-y-2 pt-3 border-t border-[#1F2639]">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#94A3B8] truncate max-w-[130px]">{data.system_a.name}</span>
                <span className="font-mono font-bold text-white">{formatPercent(data.system_a.metrics.fact_recall)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#10B981] truncate max-w-[130px]">{data.system_b.name}</span>
                <span className="font-mono font-bold text-[#10B981]">{formatPercent(data.system_b.metrics.fact_recall)}</span>
              </div>
            </div>
          </div>

          {/* 3. Citations */}
          <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 shadow-lg flex flex-col justify-between space-y-4">
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono uppercase tracking-wider text-[#94A3B8] font-semibold">
                  3. Citations
                </span>
                {formatDelta(data.deltas.citation_precision_delta)}
              </div>
              <h3 className="font-serif text-base font-bold text-white">Backed up its claims</h3>
            </div>

            <div className="space-y-2 pt-3 border-t border-[#1F2639]">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#94A3B8] truncate max-w-[130px]">{data.system_a.name}</span>
                <span className="font-mono font-bold text-white">{formatPercent(data.system_a.metrics.citation_precision)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#10B981] truncate max-w-[130px]">{data.system_b.name}</span>
                <span className="font-mono font-bold text-[#10B981]">{formatPercent(data.system_b.metrics.citation_precision)}</span>
              </div>
            </div>
          </div>

          {/* 4. Grounding */}
          <div className="bg-[#141824] border border-[#1F2639] rounded-2xl p-5 shadow-lg flex flex-col justify-between space-y-4">
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono uppercase tracking-wider text-[#94A3B8] font-semibold">
                  4. Grounding
                </span>
                {formatDelta(data.deltas.supported_claims_delta)}
              </div>
              <h3 className="font-serif text-base font-bold text-white">Avoided hallucinations</h3>
            </div>

            <div className="space-y-2 pt-3 border-t border-[#1F2639]">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#94A3B8] truncate max-w-[130px]">{data.system_a.name}</span>
                <span className="font-mono font-bold text-white">{formatPercent(data.system_a.metrics.supported_claims)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#10B981] truncate max-w-[130px]">{data.system_b.name}</span>
                <span className="font-mono font-bold text-[#10B981]">{formatPercent(data.system_b.metrics.supported_claims)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Question-Level Matrix & Side-by-Side Inspection ── */}
      <div className="bg-[#141824] border border-[#1F2639] rounded-3xl p-6 sm:p-8 shadow-xl space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-serif font-bold text-white">Question-by-Question Comparison</h2>
            <p className="text-xs text-[#94A3B8] mt-1">
              Inspect how both RAG architectures answered each individual benchmark case.
            </p>
          </div>

          {/* Filter tabs */}
          <div className="flex items-center gap-1 bg-[#0C0F17] border border-[#1F2639] p-1 rounded-xl text-xs font-mono self-start sm:self-auto">
            <button
              onClick={() => setFilter('all')}
              className={`px-3 py-1.5 rounded-lg cursor-pointer transition ${
                filter === 'all' ? 'bg-[#10B981] text-[#0C0F17] font-bold shadow-sm' : 'text-[#94A3B8] hover:text-white'
              }`}
            >
              All ({data.questions.length})
            </button>
            <button
              onClick={() => setFilter('improved')}
              className={`px-3 py-1.5 rounded-lg cursor-pointer transition ${
                filter === 'improved'
                  ? 'bg-[#10B981] text-[#0C0F17] font-bold shadow-sm'
                  : 'text-[#94A3B8] hover:text-white'
              }`}
            >
              System B Improved ({improvedCount})
            </button>
            <button
              onClick={() => setFilter('passed')}
              className={`px-3 py-1.5 rounded-lg cursor-pointer transition ${
                filter === 'passed'
                  ? 'bg-[#10B981] text-[#0C0F17] font-bold shadow-sm'
                  : 'text-[#94A3B8] hover:text-white'
              }`}
            >
              Both Passed ({bothPassedCount})
            </button>
            {bothFailedCount > 0 && (
              <button
                onClick={() => setFilter('failed')}
                className={`px-3 py-1.5 rounded-lg cursor-pointer transition ${
                  filter === 'failed'
                    ? 'bg-[#EF4444] text-white font-bold shadow-sm'
                    : 'text-[#94A3B8] hover:text-white'
                }`}
              >
                Both Failed ({bothFailedCount})
              </button>
            )}
          </div>
        </div>

        {/* Question Cards */}
        <div className="space-y-4">
          {filteredQuestions.map((q) => {
            const isExpanded = expandedId === q.item_id;
            return (
              <div
                key={q.item_id}
                className={`border rounded-2xl transition duration-200 overflow-hidden ${
                  q.verdict === 'b_improved'
                    ? 'border-[#10B981]/40 bg-[#0C0F17]/90'
                    : 'border-[#1F2639] bg-[#0C0F17]/60'
                }`}
              >
                {/* Header row */}
                <div
                  onClick={() => setExpandedId(isExpanded ? null : q.item_id)}
                  className="p-4 sm:p-5 flex items-start sm:items-center justify-between gap-4 cursor-pointer hover:bg-[#141824]/50 transition"
                >
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#1F2639] text-[#CBD5E1] font-semibold">
                        {q.item_id}
                      </span>

                      {/* Verdict Pill */}
                      {q.verdict === 'b_improved' && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/40">
                          <Sparkles className="w-3 h-3" />
                          <span>System B Improved</span>
                        </span>
                      )}
                      {q.verdict === 'both_passed' && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-[#1F2639]/50 text-[#94A3B8]">
                          <Check className="w-3 h-3 text-[#10B981]" />
                          <span>Both Passed</span>
                        </span>
                      )}
                      {q.verdict === 'both_failed' && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-[#EF4444]/20 text-[#F87171] border border-[#EF4444]/30">
                          <X className="w-3 h-3" />
                          <span>Both Failed</span>
                        </span>
                      )}

                      <span className="text-xs text-[#64748B] hidden md:inline">• {q.summary}</span>
                    </div>

                    <h4 className="text-sm sm:text-base font-serif font-bold text-white truncate">{q.question}</h4>
                  </div>

                  <div className="flex items-center gap-4 shrink-0">
                    <div className="hidden sm:flex items-center gap-2 font-mono text-xs">
                      <span
                        className={`px-2 py-0.5 rounded ${
                          q.run_a.status === 'PASS'
                            ? 'bg-[#10B981]/15 text-[#10B981]'
                            : 'bg-[#EF4444]/15 text-[#F87171]'
                        }`}
                      >
                        A: {q.run_a.status}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded ${
                          q.run_b.status === 'PASS'
                            ? 'bg-[#10B981]/20 text-[#10B981] font-bold'
                            : 'bg-[#EF4444]/20 text-[#F87171]'
                        }`}
                      >
                        B: {q.run_b.status}
                      </span>
                    </div>

                    <button className="text-[#94A3B8] p-1">
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Expanded side-by-side comparison */}
                {isExpanded && (
                  <div className="border-t border-[#1F2639] p-5 bg-[#0C0F17] space-y-4 animate-scale-in">
                    <div className="p-3 rounded-xl bg-[#141824] border border-[#1F2639] text-xs text-[#94A3B8]">
                      <strong className="text-white">Analysis:</strong> {q.summary}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* System A Answer Card */}
                      <div className="p-4 rounded-xl bg-[#141824] border border-[#1F2639] space-y-3">
                        <div className="flex items-center justify-between pb-2 border-b border-[#1F2639]">
                          <span className="text-xs font-mono font-bold text-[#94A3B8]">{data.system_a.name}</span>
                          <span
                            className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                              q.run_a.status === 'PASS'
                                ? 'bg-[#10B981]/20 text-[#10B981]'
                                : 'bg-[#EF4444]/20 text-[#F87171]'
                            }`}
                          >
                            {q.run_a.status}
                          </span>
                        </div>
                        <p className="text-xs text-[#E2E8F0] leading-relaxed font-sans">{q.run_a.answer}</p>
                        {q.run_a.failure_types.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-2">
                            {q.run_a.failure_types.map((f, idx) => (
                              <span
                                key={idx}
                                className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#EF4444]/15 text-[#F87171] border border-[#EF4444]/30"
                              >
                                {f}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* System B Answer Card */}
                      <div className="p-4 rounded-xl bg-[#141824] border border-[#10B981]/30 space-y-3">
                        <div className="flex items-center justify-between pb-2 border-b border-[#1F2639]">
                          <span className="text-xs font-mono font-bold text-[#10B981]">{data.system_b.name}</span>
                          <span
                            className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                              q.run_b.status === 'PASS'
                                ? 'bg-[#10B981]/20 text-[#10B981]'
                                : 'bg-[#EF4444]/20 text-[#F87171]'
                            }`}
                          >
                            {q.run_b.status}
                          </span>
                        </div>
                        <p className="text-xs text-[#E2E8F0] leading-relaxed font-sans">{q.run_b.answer}</p>
                        {q.run_b.failure_types.length > 0 ? (
                          <div className="flex flex-wrap gap-1.5 pt-2">
                            {q.run_b.failure_types.map((f, idx) => (
                              <span
                                key={idx}
                                className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#EF4444]/15 text-[#F87171] border border-[#EF4444]/30"
                              >
                                {f}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <div className="text-[11px] text-[#10B981] flex items-center gap-1 font-mono pt-2">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>100% verified citation & claim grounding</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
