from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, ValidationError

try:
    from google import genai
except Exception:  # pragma: no cover - import safety only
    genai = None


PROMPT_TEMPLATE = """
You are the ranking engine for an arcade word association game.
Rank the provided words from MOST related to LEAST related to the clue.

Rules:
- Use every input word exactly once.
- Preserve the original spelling of each word.
- Return the ranking result only.

Clue: {clue}
Words:
{word_list}
"""


class RankingError(RuntimeError):
    pass


@dataclass
class RankingResult:
    ranked_words: list[str]
    latency_ms: int
    provider: str
    used_fallback: bool
    warning: str | None = None


class RankedWordsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ranked_words: list[str]


def normalize_word(word: str) -> str:
    return word.strip().casefold()


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def _extract_json_candidate(text: str) -> str | None:
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(0)
    return None


def validate_ranked_words(ranked_words: Sequence[str], expected_words: Sequence[str]) -> list[str]:
    normalized_expected = [normalize_word(word) for word in expected_words]
    normalized_ranked = [normalize_word(word) for word in ranked_words]

    if len(normalized_ranked) != len(normalized_expected):
        raise RankingError("Model returned the wrong number of words.")

    if len(set(normalized_ranked)) != len(normalized_expected):
        raise RankingError("Model returned duplicate words.")

    if set(normalized_ranked) != set(normalized_expected):
        raise RankingError("Model returned unknown or missing words.")

    canonical_lookup = {normalize_word(word): word for word in expected_words}
    return [canonical_lookup[word] for word in normalized_ranked]


def _parse_ranked_words_payload(payload: object) -> list[str] | None:
    if payload is None:
        return None

    if isinstance(payload, list):
        return [str(item).strip() for item in payload]

    try:
        parsed = RankedWordsPayload.model_validate(payload)
    except ValidationError:
        return None

    return [str(item).strip() for item in parsed.ranked_words]


def parse_ranked_words(response_text: str, expected_words: Sequence[str]) -> list[str]:
    cleaned = _strip_code_fences(response_text)
    parsed_words: list[str] | None = None

    for candidate in filter(None, [cleaned, _extract_json_candidate(cleaned)]):
        try:
            parsed_words = _parse_ranked_words_payload(json.loads(candidate))
        except json.JSONDecodeError:
            parsed_words = None

        if parsed_words is not None:
            break

    if parsed_words is None:
        parsed_words = [line.strip() for line in cleaned.splitlines() if line.strip()]

    return validate_ranked_words(parsed_words, expected_words)


class GeminiRanker:
    provider = "gemini"

    def __init__(self, api_key: str, model_name: str, client: Any | None = None) -> None:
        if client is None and genai is None:
            raise RankingError("google.genai is not available. Install the google-genai package.")

        self._client = client or genai.Client(api_key=api_key)
        self._model_name = model_name
        self._generation_config = {
            "temperature": 0.0,
            "max_output_tokens": 512,
            "response_mime_type": "application/json",
            "response_json_schema": RankedWordsPayload.model_json_schema(),
        }

    def rank_words(self, clue: str, words: Sequence[str]) -> list[str]:
        prompt = PROMPT_TEMPLATE.format(
            clue=clue.strip(),
            word_list="\n".join(words),
        )
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=self._generation_config,
        )
        parsed_words = _parse_ranked_words_payload(getattr(response, "parsed", None))
        if parsed_words is not None:
            return validate_ranked_words(parsed_words, words)

        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise RankingError("Model returned an empty response.")

        return parse_ranked_words(text, words)


class HeuristicRanker:
    provider = "heuristic-fallback"

    def rank_words(self, clue: str, words: Sequence[str]) -> list[str]:
        clue_normalized = normalize_word(clue)
        clue_tokens = set(re.findall(r"[a-z0-9]+", clue_normalized))

        def score_word(word: str) -> tuple[float, float, str]:
            word_normalized = normalize_word(word)
            word_tokens = set(re.findall(r"[a-z0-9]+", word_normalized))
            overlap = len(clue_tokens & word_tokens) * 3.0
            substring_bonus = 1.5 if clue_normalized in word_normalized or word_normalized in clue_normalized else 0.0
            similarity = SequenceMatcher(None, clue_normalized, word_normalized).ratio()
            return (overlap + substring_bonus + similarity, similarity, word_normalized)

        return sorted(words, key=score_word, reverse=True)


class ResilientRanker:
    def __init__(
        self,
        primary: GeminiRanker | None,
        fallback: HeuristicRanker | None = None,
        initial_warning: str | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback or HeuristicRanker()
        self.initial_warning = initial_warning

    def rank_words(self, clue: str, words: Sequence[str]) -> RankingResult:
        start = time.perf_counter()

        if self.primary is not None:
            try:
                ranked_words = self.primary.rank_words(clue, words)
                latency_ms = round((time.perf_counter() - start) * 1000)
                return RankingResult(
                    ranked_words=ranked_words,
                    latency_ms=latency_ms,
                    provider=self.primary.provider,
                    used_fallback=False,
                )
            except Exception as exc:
                fallback_words = self.fallback.rank_words(clue, words)
                latency_ms = round((time.perf_counter() - start) * 1000)
                return RankingResult(
                    ranked_words=fallback_words,
                    latency_ms=latency_ms,
                    provider=self.fallback.provider,
                    used_fallback=True,
                    warning=f"Primary ranking provider failed: {exc}",
                )

        fallback_words = self.fallback.rank_words(clue, words)
        latency_ms = round((time.perf_counter() - start) * 1000)
        return RankingResult(
            ranked_words=fallback_words,
            latency_ms=latency_ms,
            provider=self.fallback.provider,
            used_fallback=True,
            warning=self.initial_warning or "Gemini is not configured, so the local fallback ranker was used.",
        )


def build_ranker_from_env() -> ResilientRanker:
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

    if not api_key:
        return ResilientRanker(
            primary=None,
            initial_warning="Gemini is not configured because GEMINI_API_KEY is missing, so the local fallback ranker was used.",
        )

    try:
        primary = GeminiRanker(api_key=api_key, model_name=model_name)
        return ResilientRanker(primary=primary)
    except Exception as exc:
        return ResilientRanker(
            primary=None,
            initial_warning=f"Gemini initialization failed, so the local fallback ranker was used: {exc}",
        )
