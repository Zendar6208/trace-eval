"""NLI-based evidence verification and numeric guard conforming to Methodology Section 3 & 4.

Methodology requirements:
- Section 4:
  - Label mapping is never hardcoded. At model load, read config.id2label.
    Require exactly the names contradiction, entailment, neutral (case-insensitive).
  - Run three hand-written sanity pairs:
    1. ("The dog is running in the park.", "An animal is outside.") -> entailment
    2. ("The door is firmly closed.", "The door is open.") -> contradiction
    3. ("Mary bought a new car yesterday.", "Mary loves driving fast.") -> neutral
    Refuse to start if argmax labels do not match.
  - Probabilities are softmax over the three logits, rounded to 4 decimals.
  - Premise windows are 1 to 3 consecutive sentences of a passage (config window_sentences).
  - Hypothesis is claim sentence (markers removed).
  - max_length, batch_size and truncation_policy are config-controlled and hashed.
- Section 3:
  - Numeric guard (Tier 0): a number or date in the claim, after normalization,
    that appears in no retrieved text caps the label at unsupported.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from trace_eval.claims import split_sentences_raw
from trace_eval.text_norm import normalize_for_matching

SANITY_PAIRS = [
    ("The dog is running in the park.", "An animal is outside.", "entailment"),
    ("The door is firmly closed.", "The door is open.", "contradiction"),
    ("Mary bought a new car yesterday.", "Mary loves driving fast.", "neutral"),
]

# Patterns for extracting numbers and dates for the Tier-0 numeric guard
NUMBER_PATTERN = re.compile(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b")
DATE_PATTERN = re.compile(
    r"\b(?:"
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"  # 01/02/2023 or 1-2-23
    r"|(?:19|20)\d{2}"  # 1999, 2024
    r"|(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:,\s*(?:19|20)\d{2})?"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NLIPrediction:
    """Softmax output probabilities for a single premise-hypothesis pair."""

    entailment: float
    contradiction: float
    neutral: float
    argmax_label: Literal["entailment", "contradiction", "neutral"]


def normalize_numeric_token(token: str) -> str:
    """Normalize a numeric token (remove commas, drop trailing .0) per Section 2.1."""
    cleaned = token.replace(",", "").strip()
    try:
        val = float(cleaned)
        if val.is_integer():
            return str(int(val))
        return f"{val:g}"
    except ValueError:
        return cleaned.lower()


def extract_numbers_and_dates(text: str) -> list[str]:
    """Extract and normalize all numbers and dates from claim text."""
    found: list[str] = []

    # Dates first
    for m in DATE_PATTERN.finditer(text):
        found.append(normalize_for_matching(m.group(0)))

    # Numbers
    for m in NUMBER_PATTERN.finditer(text):
        norm_num = normalize_numeric_token(m.group(0))
        if norm_num not in found:
            found.append(norm_num)

    return found


def check_numeric_guard(claim_text: str, retrieved_texts: Sequence[str]) -> bool:
    """Check if any number or date in the claim is missing from all retrieved texts.

    Returns:
        True if the numeric guard triggers (i.e. ungrounded number/date found),
        capping the verdict at 'unsupported'.
    """
    claim_nums = extract_numbers_and_dates(claim_text)
    if not claim_nums:
        return False

    norm_retrieved = [normalize_for_matching(t) for t in retrieved_texts if t]
    if not norm_retrieved:
        return True  # Numbers present in claim but no retrieved text

    for num in claim_nums:
        # Check presence in any retrieved text
        present = False
        for doc in norm_retrieved:
            if num in doc:
                present = True
                break
        if not present:
            return True  # Ungrounded number or date found!

    return False


def extract_premise_windows(
    passage_text: str,
    window_sentences: int = 3,
) -> list[str]:
    """Extract consecutive sentence premise windows (1 to window_sentences) from passage."""
    if not passage_text or not passage_text.strip():
        return []

    spans = split_sentences_raw(passage_text)
    if not spans:
        return [passage_text.strip()]

    sentences = [re.sub(r"\s+", " ", s[2]).strip() for s in spans if s[2].strip()]
    if not sentences:
        return [passage_text.strip()]

    windows: list[str] = []
    seen: set[str] = set()
    n = len(sentences)

    for w in range(1, min(window_sentences, n) + 1):
        for i in range(n - w + 1):
            window_str = " ".join(sentences[i : i + w]).strip()
            if window_str and window_str not in seen:
                seen.add(window_str)
                windows.append(window_str)

    return windows if windows else [passage_text.strip()]


class NLIEvaluator:
    """Local NLI evaluator wrapping a sequence classification model conforming to Section 4."""

    def __init__(
        self,
        model_name: str = "cross-encoder/nli-distilroberta-base",
        revision: str | None = "b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
        device: str = "cpu",
        max_length: int = 512,
        batch_size: int = 16,
        truncation_policy: str = "longest_first",
        id2label_override: dict[str, str] | None = None,
        local_files_only: bool = True,
    ) -> None:
        self.model_name = model_name
        self.revision = revision
        self.device = device
        self.max_length = max_length
        self.batch_size = batch_size
        self.truncation_policy = truncation_policy
        self.local_files_only = local_files_only

        self._tokenizer = None
        self._model = None
        self._id2label: dict[int, Literal["contradiction", "entailment", "neutral"]] = {}
        self._label2id: dict[str, int] = {}

        self._load_and_validate(id2label_override)

    def _load_and_validate(self, id2label_override: dict[str, str] | None) -> None:
        """Load model, resolve label mapping, and execute the 3 mandatory sanity checks."""
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        tokenizer_kwargs = {"local_files_only": self.local_files_only}
        model_kwargs = {"local_files_only": self.local_files_only}
        if self.revision:
            tokenizer_kwargs["revision"] = self.revision
            model_kwargs["revision"] = self.revision

        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                **tokenizer_kwargs,
            )
        except Exception:
            if self.local_files_only:
                tokenizer_kwargs["local_files_only"] = False
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    **tokenizer_kwargs,
                )
            else:
                raise

        try:
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name,
                **model_kwargs,
            )
        except Exception:
            if self.local_files_only:
                model_kwargs["local_files_only"] = False
                self._model = AutoModelForSequenceClassification.from_pretrained(
                    self.model_name,
                    **model_kwargs,
                )
            else:
                raise
        self._model.to(self.device)
        self._model.eval()

        # Resolve id2label
        raw_mapping = id2label_override or self._model.config.id2label
        if not raw_mapping:
            raise ValueError(
                "NLI model has no id2label mapping in config.id2label and none was supplied."
            )

        # Validate label mapping per Section 4:
        # Require exactly the names contradiction, entailment, neutral (case-insensitive)
        resolved: dict[int, Literal["contradiction", "entailment", "neutral"]] = {}
        for k, v in raw_mapping.items():
            idx = int(k)
            v_lower = str(v).lower()
            if v_lower not in {"contradiction", "entailment", "neutral"}:
                raise ValueError(
                    f"id2label mapping values must be exactly 'contradiction', 'entailment', or 'neutral', got '{v}'"
                )
            resolved[idx] = v_lower  # type: ignore[assignment]

        expected_labels = {"contradiction", "entailment", "neutral"}
        if set(resolved.values()) != expected_labels:
            raise ValueError(
                f"id2label mapping must contain exactly {expected_labels}, got {set(resolved.values())}"
            )

        self._id2label = resolved
        self._label2id = {v: k for k, v in self._id2label.items()}

        # Run 3 mandatory sanity checks
        self._run_sanity_checks()

    def _run_sanity_checks(self) -> None:
        """Run the 3 methodology-required hand-written sanity pairs."""
        pairs = [(p[0], p[1]) for p in SANITY_PAIRS]
        preds = self.predict(pairs)

        for i, (premise, hypothesis, expected_label) in enumerate(SANITY_PAIRS):
            pred = preds[i]
            if pred.argmax_label != expected_label:
                raise ValueError(
                    f"NLI sanity check failed for pair {i + 1}:\n"
                    f"Premise: '{premise}'\n"
                    f"Hypothesis: '{hypothesis}'\n"
                    f"Expected label: '{expected_label}', got '{pred.argmax_label}'\n"
                    f"Probabilities: {pred}"
                )

    def get_id2label_dict(self) -> dict[str, str]:
        """Return the validated stringified id2label dictionary for RunConfig."""
        return {str(k): v for k, v in self._id2label.items()}

    def predict(self, pairs: Sequence[tuple[str, str]]) -> list[NLIPrediction]:
        """Run batched NLI inference over premise-hypothesis pairs."""
        if not pairs:
            return []

        import torch

        results: list[NLIPrediction] = []
        truncation = True if self.truncation_policy == "longest_first" else self.truncation_policy

        for i in range(0, len(pairs), self.batch_size):
            batch = pairs[i : i + self.batch_size]
            premises = [b[0] for b in batch]
            hypotheses = [b[1] for b in batch]

            inputs = self._tokenizer(
                premises,
                hypotheses,
                padding=True,
                truncation=truncation,
                max_length=self.max_length,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                outputs = self._model(**inputs)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=-1)

            entail_id = self._label2id["entailment"]
            contra_id = self._label2id["contradiction"]
            neut_id = self._label2id["neutral"]

            for row_idx in range(len(batch)):
                p_entail = round(probs[row_idx, entail_id].item(), 4)
                p_contra = round(probs[row_idx, contra_id].item(), 4)
                p_neut = round(probs[row_idx, neut_id].item(), 4)

                argmax_idx = torch.argmax(logits[row_idx]).item()
                argmax_label = self._id2label[argmax_idx]

                results.append(
                    NLIPrediction(
                        entailment=p_entail,
                        contradiction=p_contra,
                        neutral=p_neut,
                        argmax_label=argmax_label,
                    )
                )

        return results
