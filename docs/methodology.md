# TRACE AI Methodology (normative)

`methodology_version: 1.0.0`

This document is normative. Code must match it. Any change to a rule here bumps `methodology_version`, adds a CHANGELOG entry, and (because versions are hashed) changes run hashes by design.

---

## Clarifications & Errata (M0 Baseline)

The following clarifications are formally incorporated into v1.0.0 for Milestone M0:

1. **Citation Metrics and Retrieved Passages (Clarification to Section 3 and CA-7):**
   Citation metrics inspect `retrieved` passage IDs exclusively to establish citation validity (e.g., verifying whether a cited passage was in `retrieved` vs. `not_retrieved` vs. `unknown_id` per CA-7). However, citation support evidence (NLI entailment) must come strictly and exclusively from the cited passage's own text windows, never from un-cited retrieved passages or gold references.
2. **MM-5 Unsupported-Claim Rate Gating (Clarification to Section 7):**
   In metamorphic operator MM-5 (`append_offtopic_sentence`), the expected increase in `unsupported_claim_rate` is a Tier-1 gated expectation (evaluated at the standard pre-registered gate of $\ge 90\%$), rather than an unconditional $100\%$ invariant, recognizing non-deterministic boundary effects in NLI evaluation when baseline claim rates approach unity.
3. **Committed Golden Fixtures for Serialization and Hashing (Clarification to Section 8):**
   Canonical JSON serialization (`canonical_json`) and content hashing functions must be verified against committed golden test fixtures with explicit expected byte representations and SHA-256 hashes, ensuring cross-platform repeatability and preventing self-referential test regressions.

---

## 1. Provenance classes

Three kinds of thing appear in TRACE. They must never be conflated in code, UI or docs.

| Class | Definition | Where it lives | May support claims about |
|---|---|---|---|
| `synthetic_fixture` | An output authored by a human or script to exhibit one specific failure. Not a measurement of any real system. | `outputs[].origin` in a submission; requires `fixture_note`. | Evaluator validity only. Never RAG system quality. |
| `recorded_system` | An output genuinely produced by a real RAG pipeline at a recorded time and stored. The pipeline is not re-run at demo time. | `outputs[].origin`; requires `system.provenance`. | System quality, and evaluator validity. |
| live evaluator result | Metric values computed by this engine from inputs. | `trace.run` documents. | The measured quantities, under the stated config. |

Live evaluator results have a **runtime status**, assigned by the server or CLI and never stored in the hashed run core:

- `live`: computed in this request, on this machine, now.
- `startup_recomputed`: preloaded demo run, recomputed on server start from its inputs, and compared to the committed `result_hash`. Mismatch must be shown in the UI.
- `loaded`: read from a file. `hash_verified` or `hash_unverified`.
- `replayed_judge`: Tier 2 verdicts replayed from a hash-keyed cache (optional feature). Must display model, date and prompt hash.

Reporting rule: any statistic about "RAG system quality" is computed from `recorded_system` outputs only. Validity statistics are reported separately per origin and combined.

## 2. Text processing

### 2.1 Normalization
- All text is Unicode NFC. `\r\n` and `\r` become `\n`.
- Matching normalization (for fact matching and token F1): lowercase, strip punctuation except inside numbers, collapse whitespace, normalize numbers (remove thousands separators, `1,000` equals `1000`, trailing `.0` dropped). Number words are not converted in v1.

### 2.2 Citation marker syntax
- `citation_style: "id"` (default): a marker group is `[` ID (SEP ID)* `]`, with ID matching `[A-Za-z0-9_.:-]+` and SEP being `,` or `;` with optional spaces.
- `citation_style: "index"`: a marker group is `[` N (SEP N)* `]`, with N an integer. N refers to the 1-based position in the `retrieved` list. Out-of-range is a phantom.
- Adjacent groups separated only by whitespace (`[p1][p2]`, `[p1] [p2]`) form one citation set.
- `phantom_mode: "bracket"` (default): any bracketed token matching the syntax is a citation, and unknown IDs are phantoms. Known limitation: text such as `[sic]` is treated as a phantom citation. `phantom_mode: "known_only"`: only IDs present in `retrieved` or the corpus count as citations, so phantoms cannot occur.

### 2.3 Sentence segmentation (rule-based, no ML)
Marker spans are masked first (replaced by same-length placeholder characters) so that periods inside IDs never split. Then:
1. A blank line, or a newline followed by a list marker (`-`, `*`, `•`, `\d+[.)]`), is a hard boundary.
2. Within a unit, a soft boundary is `[.!?]`, then optional closing quote or bracket characters, then whitespace, then an uppercase letter, digit, or opening quote or bracket.
3. No split after a protected abbreviation (`e.g`, `i.e`, `vs`, `mr`, `mrs`, `ms`, `dr`, `prof`, `inc`, `ltd`, `co`, `no`, `fig`, `approx`, `st`; case-insensitive). No split on a period between digits not followed by whitespace (decimals, versions).
4. A single newline inside a unit becomes a space.
5. Segmentation is pinned by golden tests. Any change bumps `methodology_version`.

### 2.4 Citation-to-sentence attachment (exact rules)
- **CA-1** Mask marker spans, segment, then reattach (2.3).
- **CA-2** A marker group inside a sentence attaches to that sentence.
- **CA-3** A marker group that appears after the sentence-final punctuation (optionally followed by closing quote or bracket) and before the next sentence's first non-space character attaches to the preceding sentence. Example: `Refunds take 30 days.[p03] Fees apply.` attaches `p03` to sentence 0.
- **CA-4** A marker group at the very start of the answer, before any sentence text, is an **orphan**. It is a citation unit with `sentence_index = null`, is non-supporting, and is counted in the precision denominator.
- **CA-5** Per sentence, the cited IDs are deduplicated in first-appearance order. Each distinct (sentence, ID) pair is one **citation unit**. The duplicate count is recorded.
- **CA-6** Each unit is evaluated independently against the cited passage only (premise windows drawn from that passage; see section 4). A sentence is **citation-supported** if at least one of its units supports it. v1 limitation: claims that need two passages jointly are undercounted. Joint support is out of scope for v1.
- **CA-7** Unit validity: `ok` if the ID is in `retrieved`; `not_retrieved` if it is in the corpus but not in `retrieved`; `unknown_id` if it is in neither; `index_out_of_range` for index style. Anything other than `ok` is non-supporting.
- **CA-8** Marker text is removed from the sentence (whitespace collapsed) before NLI and before correctness matching.

### 2.5 Claim sentences and uncited claims
- A **claim sentence** is any sentence except: (a) sentences matching `refusal_patterns`, (b) sentences with no alphanumeric content after marker removal, (c) sentences matching `non_claim_patterns` (small configurable list, for example bare "Sure." or "Here is the answer:").
- A claim sentence with fewer than 3 word tokens is `not_assessable` for grounding (for example a bare "Yes."). It is excluded from claim rates, counted, and reported. v1 limitation: yes/no answers are not assessed by NLI.
- A claim sentence with zero citation units is **uncited**. Uncited claim sentences are still evaluated for grounding against the retrieved set. They count in the citation-recall denominator as not citation-supported. They add nothing to the citation-precision denominator. They are reported as `uncited_claim_rate`.
- `require_citations: false` means the system under test does not cite. Citation metrics are then `null` (not applicable), never 0 or 1, and the failure types `BAD_CITATION` and `UNCITED_CLAIM` are not assigned.
- With `require_citations: true` and an answer containing no citations: citation recall is 0, precision is `null`. No vacuous 1.0.

## 3. Metric definitions

Each metric reads only the inputs listed. These independence relations are what the metamorphic suite (section 7) tests.

| Metric group | Reads | Does not read |
|---|---|---|
| Retrieval (hit, recall, precision, MRR, nDCG) | `retrieved` (order and IDs), gold passages | answer |
| Correctness | answer (markers stripped), reference answer, required facts | retrieved, citations |
| Citation (precision, recall, phantom, uncited) | answer markers, cited passage text, sentence text, retrieved passage IDs (validity check only) | other retrieved passages text, gold |
| Grounding (claim labels, unsupported rates) | answer sentences, **all** retrieved passages | citations, gold |

- **Retrieval** (Tier 0): hit@k, recall@k, precision@k, MRR, nDCG@k with graded gains. Matching by ID; fallback token overlap at least 0.8 against gold passage text. Unanswerable items and items without gold are excluded, with `n` reported.
- **Correctness** (Tier 0 with Tier 1 fallback): per required fact, matched by normalized containment of the text or any alias; if unmatched and NLI is enabled, matched if `P(entail | answer sentence, fact) >= entail threshold`, recorded as method `nli`. `fact_recall` is matched over total. `token_f1` is SQuAD-style. `contradicts_reference` is NLI contradiction at or above the contradict threshold against the reference answer. Verdict: `correct` if all facts matched and no contradiction; `partial` if some matched and no contradiction; else `incorrect`. For unanswerable items, `correct` if and only if the answer is a refusal. **Correctness measures presence of and conflict with reference facts; it does not penalize extra unsupported content.** That is a definition, not a truth about quality, and grounding exists to catch extra content.
- **Citation** (Tier 0 parsing, Tier 1 support): unit `supports` if the maximum entail probability over windows of the cited passage is at or above the entail threshold. `citation_precision` is supporting units over all units. `citation_recall` is citation-supported claim sentences over claim sentences. `phantom_rate` is non-`ok` units over all units. `cites_gold` is a diagnostic.
- **Grounding** (Tier 1 with Tier 0 guard): for each assessable claim sentence, take the best entail and best contradict probability over windows of all retrieved passages (after BM25 prefilter when enabled). Label `supported` if entail is at or above the entail threshold; else `contradicted` if contradict is at or above the contradict threshold and above entail; else `unsupported`. **Numeric guard (Tier 0):** a number or date in the claim, after normalization, that appears in no retrieved text caps the label at `unsupported`. `unsupported_claim_rate` is (unsupported + contradicted) over assessable claims. `is_unsupported_answer` is true if any assessable claim is not `supported`, and for any non-refusal answer to an unanswerable item.
- **Failure types** (derived deterministically, multi-label): `RETRIEVAL_MISS`, `WRONG_ANSWER`, `UNSUPPORTED_CLAIM`, `UNCITED_CLAIM`, `BAD_CITATION`, `ANSWERED_UNANSWERABLE`, `FALSE_REFUSAL`, `PASS`. `PASS` only if no other type applies.

Tiers: `rule` (pure code), `local_nli` (pinned local model), `llm_judge` (optional, replayed or BYO-key; off by default).

## 4. NLI protocol

- **Label mapping is never hardcoded.** At model load, read `config.id2label`. Require exactly the names contradiction, entailment, neutral (case-insensitive). If the model exposes generic names (`LABEL_0..2`), the mapping must be supplied in config. In both cases run three hand-written sanity pairs (clear entailment, clear contradiction, clear neutral) and refuse to start if the argmax labels do not match. The mapping used is recorded in the run config.
- Probabilities are the softmax over the three logits, rounded to 4 decimals.
- Premise windows are 1 to 3 consecutive sentences of a passage (config `window_sentences`). Hypothesis is the claim sentence (markers removed). `max_length`, `batch_size` and truncation policy are config and are hashed.
- BM25 prefilter of top-m windows is optional (config `prefilter_top_m`, `null` disables it). Metamorphic monotonicity tests run with the prefilter disabled.

## 5. Calibration and human-evaluator agreement

- **Parameters:** exactly two free parameters, `entail` and `contradict`, shared by correctness, citation and grounding. Per-task thresholds are not added without a documented reason, because the benchmark is too small to support them.
- **Splits:** each item has `group_id` (variants of one underlying case share it) and `split` in {dev, test}. Assigned once by a seeded, group-level, stratified script **before any evaluator output is viewed**, then committed. Splitting by group prevents leakage between variants.
- **Calibration objective (pre-registered):** grid `entail` and `contradict` over 0.05 to 0.95 step 0.05; choose the pair maximizing macro-F1 over {supported, unsupported, contradicted} on dev claims, excluding `not_assessable`; ties go to the pair nearest 0.5. Record the dev split hash, grid, objective and chosen pair in a `calibration` block.
- **Test evaluation:** done once with frozen thresholds. Any re-tuning after viewing test results is reported as post-hoc, with both results shown.
- **Agreement metrics:** per label dimension, report confusion matrix, per-class precision/recall/F1, balanced accuracy, Cohen's kappa, and class prevalence. Kappa is reported alongside prevalence because it behaves badly under imbalance. Intervals use a **cluster bootstrap by `group_id`** (10,000 resamples, fixed seed), because variants of one case are not independent.
- **Terminology:** "human-evaluator agreement" describes the evaluator vs the annotator. It is not inter-annotator agreement. If an LLM second pass is run on a sample, it is reported as "human vs LLM second pass", not as a second independent human.
- **Labels file:** human labels describe a specific output, so they live in a separate `trace.labels` document keyed to the submission's content hash, not in the dataset. Each label entry carries `sentence_text` so that a segmentation change is detected rather than silently misaligning labels.

## 6. Benchmark limitations (must appear in README and UI)

- About 60 items, English only, one fictional domain, short passages.
- One annotator. Labels frozen before evaluator runs, but there is no inter-annotator estimate.
- Synthetic fixtures over-represent failures by construction. Prevalence in the benchmark is not prevalence in any real system, so headline "accuracy" is never presented as real-world performance. Stratified per-class metrics are the reporting unit.
- The NLI model was trained on SNLI and MNLI and is evaluated on a different domain. Results do not establish generalization.
- Intervals will be wide. Report them.

## 7. Metamorphic suite

The suite checks that metric **definitions in section 3** respond to controlled edits as those definitions say they should. Operators are designed from the same definitions, so the suite cannot detect a wrong definition. That is what human-evaluator agreement is for.

Notation: `=` unchanged; `↓` / `↑` decreases / increases; `≤` / `≥` monotone; blank means not asserted. Tier-0 assertions must hold on 100% of applicable items. Tier-1 assertions have a pre-registered gate of at least 90% (provisional; changing it requires a CHANGELOG reason). A failed assertion is reported as a finding, not hidden.

| Op | Transformation (narrow) | Applicable when | Assertions |
|---|---|---|---|
| MM-0 `whitespace_perturb` | Only whitespace changes (extra spaces, `\n` to space); text otherwise identical | always | **All metrics `=`** (exact in pinned environment) |
| MM-1 `reorder_retrieved` | Permute `retrieved` order; `id` citation style only | `len(retrieved) >= 2` | `=`: recall@\|R\|, hit@\|R\|, correctness, grounding labels, citation units. Not asserted: MRR, nDCG, precision@k for k < \|R\| |
| MM-2 `drop_gold_passages` | Remove all gold passages from `retrieved`; answer unchanged | recall@k > 0 before | `↓`: hit, recall to 0. `=`: correctness (all fields). `≥`: unsupported_claim_rate (prefilter off). `≥`: phantom_rate (cited gold units become `not_retrieved`). `≤`: citation_precision, citation_recall. Not asserted: individual claim labels (a claim may flip from unsupported to contradicted) |
| MM-3 `swap_citation_nonsupporting` | Replace each cited ID with a retrieved, non-gold passage that contains no required-fact text or alias and shares no numbers with the sentence | item has at least one unit | `↓`: citation_precision, citation_recall (Tier 1, gated at 90%). `=`: retrieval, correctness, all claim labels (grounding ignores markers) |
| MM-4 `phantom_citation` | Replace each cited ID with an ID absent from `retrieved` and the corpus | item has at least one unit | `↑`: phantom_rate to 1.0. `↓`: citation_precision to 0, citation_recall to 0 (Tier 0 once validity is `not ok`). `=`: retrieval, correctness, all claim labels |
| MM-5 `append_offtopic_sentence` | Append one uncited declarative sentence from a vetted bank: no digits; no token of 5 or more characters shared with any retrieved passage, the reference or the question | always | `↑`: unsupported_claim_rate (when baseline < 1; Tier 1 gated at 90%), `is_unsupported_answer` becomes true, uncited_claim_rate (when citations required). `↓`: citation_recall (denominator grows), token_f1 (≤). `=`: retrieval, fact_recall, citation_precision, existing claim labels. **Correctness verdict: `=` expected under v1's definition, but the contradiction check may legitimately fire; any change is recorded as a finding and reported separately** |
| MM-6 `substitute_fact_value` | Replace the numeric surface form of one matched required fact with a different number absent from the retrieved text and reference | a numeric required fact is matched | `↓`: fact_recall (strict), verdict not `correct` (Tier 0). `↑`: unsupported_claim_rate via numeric guard (Tier 0). `=`: retrieval. Expected but non-gating: that sentence's citation units stop supporting (NLI-dependent) |

Monotonicity assertions (`≥`, `≤`) are tested with `prefilter_top_m = null`; with the prefilter on, they are reported at aggregate level only, because removing passages can change which windows the prefilter keeps.

## 8. Hashing and reproducibility

### 8.1 Canonical JSON
`canonical_json(obj) -> bytes`:
- Accepts only dict (string keys), list, str, int, bool, None, finite float. Anything else, including NaN and infinity, raises.
- Strings and keys are NFC-normalized. Keys are sorted by Unicode code point. No insignificant whitespace. UTF-8, no ASCII escaping.
- Floats are rounded to 6 decimal places before serialization and written with Python's shortest round-trip `repr`; negative zero becomes `0.0`. Ints and floats stay distinct (`1` vs `1.0`).
- This is a TRACE-specific canonical form, **not** RFC 8785 (JCS). We do not claim JCS compliance.
- Models are dumped with `model_dump(mode="json")` with **no field exclusion and nulls included**. Adding a field to a schema changes hashes of existing data, which is why schema changes require a new `schema_version`.

### 8.2 Content hashes
- `dataset.content_sha256`: canonical JSON of `{schema_version, dataset_id, language, corpus, items}`. Excludes `name`, `description`, `license`.
- `submission.content_sha256`: canonical JSON of `{schema_version, dataset_id, outputs}`. Excludes `system`.
- `labels.content_sha256`: canonical JSON of the whole labels document except `annotator_notes`.

### 8.3 Result hash
`result_hash = sha256(canonical_json(core))` where `core = {schema_version, methodology_version, dataset: {id, content_sha256}, submission_content_sha256, config, summary, items}`.
**Excluded (non-deterministic or non-semantic):** `run_id` (derived: first 16 hex chars of `result_hash`), `result_hash` itself, `environment` (timestamps, hostnames, paths, durations, git SHA, library versions, thread counts), `system` name and provenance, `input_origin_summary` (derived).
`config` is included in full, including thresholds, citation settings, NLI identity (model name, revision, weights hash, label mapping, `max_length`, `batch_size`, window settings) and bootstrap settings and seed.

### 8.4 Reproducibility levels
- **Level A, Tier 0 metrics:** pure Python on IEEE doubles, rounded to 6 decimals. Expected identical across platforms; claimed only for platforms exercised in CI.
- **Level B, Tier 1 metrics, pinned environment:** reproducible when the model revision and weights hash, torch/transformers/numpy versions (lockfile), CPU architecture, `batch_size`, thread count and `eval()` mode are the same. Batch composition and thread count can change floating-point results in the last bits.
- **Not claimed:** bitwise determinism of Tier 1 across platforms or hardware. Values near a rounding boundary or a threshold can flip.
- `trace verify` has two modes. `strict`: recompute and compare `result_hash`. `tolerant`: compare Tier-0 values exactly; compare Tier-1 probabilities within 1e-3; report any label that differs, flagging those within 0.01 of a threshold as boundary flips.

## 9. Positioning

TRACE does not claim to be the first or only tool with any of the following. TRACE's value is judged by these demonstrated capabilities, each tied to an artifact:

| Capability | Demonstrated by |
|---|---|
| Runs without any API key (Tier 0 and Tier 1) | CI job running the demo evaluation with outbound network disabled after model fetch |
| Per-claim and per-citation evidence | UI inspector, run JSON `evidence` fields |
| Evaluator validity report shipped with releases | `trace validate` output: human-evaluator agreement (with cluster-bootstrap intervals) and metamorphic pass rates |
| Hash-verifiable results | `trace verify` strict and tolerant modes |
| Paired run comparison with CIs and a CI gate | `trace compare --fail-on-regression` exit code and tests |
| Open versioned schemas | `schema/*.json` generated from the models, drift-checked in CI |

Comparisons to other tools are made only where we have run both on the same data and report the result.
