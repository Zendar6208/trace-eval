export interface MetricSummary {
  count: number;
  mean_token_f1: number | null;
  mean_fact_recall: number | null;
  accuracy: number | null;
  mean_citation_precision: number | null;
  mean_citation_recall: number | null;
  mean_phantom_rate: number | null;
  mean_unsupported_claim_rate: number | null;
}

export interface EvaluationItemSummary {
  item_id: string;
  origin: "recorded_system" | "synthetic_fixture";
  failure_types: string[];
  retrieval: {
    hit_at_k: Record<string, number>;
    recall_at_k: Record<string, number>;
    mrr: number | null;
    ndcg_at_k: Record<string, number>;
  } | null;
  correctness: {
    fact_recall: number | null;
    token_f1: number | null;
    verdict: "correct" | "partial" | "incorrect" | null;
    contradicts_reference: boolean | null;
  } | null;
  citation: {
    citation_precision: number | null;
    citation_recall: number | null;
    phantom_rate: number | null;
    uncited_claim_rate: number | null;
    cites_gold: boolean | null;
  } | null;
  grounding: {
    unsupported_claim_rate: number | null;
    is_unsupported_answer: boolean | null;
  } | null;
}

export interface EvaluationRunResponse {
  run_id: string;
  result_hash: string;
  methodology_version: string;
  nli_enabled: boolean;
  evaluation_tier: string;
  summary: {
    combined: MetricSummary | null;
    recorded_system: MetricSummary | null;
    synthetic_fixture: MetricSummary | null;
    failure_distribution: Record<string, number>;
  };
  items: EvaluationItemSummary[];
}

export interface ClaimEvidence {
  sentence_index: number;
  sentence_text: string;
  is_assessable: boolean;
  grounding_label: "supported" | "unsupported" | "contradicted" | "not_assessable";
  best_entail_prob: number | null;
  best_contradict_prob: number | null;
  numeric_guard_triggered: boolean;
}

export interface CitationEvidence {
  sentence_index: number | null;
  passage_id: string;
  validity: "ok" | "not_retrieved" | "unknown_id" | "index_out_of_range";
  supports: boolean;
  entail_prob: number | null;
  best_window: string | null;
}

export interface ItemDetailResponse extends EvaluationItemSummary {
  question: string | null;
  answer: string | null;
  reference_answers: string[];
  required_facts: { fact_id: string; text: string }[];
  retrieved: { id: string; score: number | null; text: string }[];
  claims: ClaimEvidence[];
  citations: CitationEvidence[];
}
