from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, ValidationError

from semantic_cache import NullSemanticCache, SemanticCache, build_cache_key, build_semantic_cache
from settings import Settings

try:
    from google import genai
except Exception:  # pragma: no cover - import safety only
    genai = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import safety only
    OpenAI = None

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover - import safety only
    fuzz = None


RANKING_SYSTEM_PROMPT = """
You are the ranking engine for an arcade word association game.
Rank the provided words from MOST related to LEAST related to the clue.

Rules:
- Use every input word exactly once.
- Preserve the original spelling of each word.
- Return the ranking result only.
""".strip()

RESTRICTION_SYSTEM_PROMPT = """
You judge whether a clue satisfies an active game rule and, only when it does,
rank the provided words from MOST related to LEAST related to the clue.

Rules:
- Return JSON only.
- Preserve the original spelling of each word.
- If the clue fails the rule, set rule_passed=false and ranked_words=null.
- If the clue passes the rule, set rule_passed=true and ranked_words to a full
  permutation of every provided word exactly once.
- short_reason must be brief and safe to show directly to a player.
""".strip()

SCORING_SYSTEM_PROMPT = """
You score how strongly each provided word relates to the clue.

Rules:
- Return JSON only.
- Use every input word exactly once.
- Preserve the original spelling of each word.
- Each score must be an integer from 0 to 100.
- Higher scores mean stronger semantic relevance to the clue.
""".strip()

BLOCKS_PRIMARY_SYSTEM_PROMPT = """
You choose the single best candidate for a semantic chain-reaction word game.

Rules:
- Return JSON only.
- Pick exactly one candidate_id from the provided candidate list.
- candidate_id must match one of the provided candidates exactly.
- candidate_id is the only meaningful output field.
- Never return the word text instead of the candidate_id.
- Example valid response: {"candidate_id": 7}
- Do not return explanations or extra text.
""".strip()

BLOCKS_SCORING_SYSTEM_PROMPT = """
You score how strongly each provided candidate relates to the clue.

Rules:
- Return JSON only.
- Use every provided candidate_id exactly once.
- candidate_id must match one of the provided candidates exactly.
- Each score must be an integer from 0 to 100.
- candidate_id is authoritative; word text is only a label.
- Example valid response: {"scored_candidates": [{"candidate_id": 7, "score": 91}, {"candidate_id": 12, "score": 44}]}
""".strip()


def render_ranking_input(clue: str, words: Sequence[str]) -> str:
    return f"Clue: {clue.strip()}\nWords:\n" + "\n".join(words)


def render_ranking_prompt(clue: str, words: Sequence[str]) -> str:
    return f"{RANKING_SYSTEM_PROMPT}\n\n{render_ranking_input(clue, words)}"


def render_restriction_input(rule_text: str, clue: str, words: Sequence[str]) -> str:
    return (
        f"Active rule: {rule_text.strip()}\n"
        f"Clue: {clue.strip()}\n"
        "Words:\n"
        + "\n".join(words)
    )


def render_restriction_prompt(rule_text: str, clue: str, words: Sequence[str]) -> str:
    return f"{RESTRICTION_SYSTEM_PROMPT}\n\n{render_restriction_input(rule_text, clue, words)}"


def render_scoring_input(clue: str, words: Sequence[str]) -> str:
    return f"Clue: {clue.strip()}\nWords:\n" + "\n".join(words)


def render_scoring_prompt(clue: str, words: Sequence[str]) -> str:
    return f"{SCORING_SYSTEM_PROMPT}\n\n{render_scoring_input(clue, words)}"


@dataclass(frozen=True)
class BlocksCandidate:
    candidate_id: int
    word: str


def render_blocks_candidates(candidates: Sequence[BlocksCandidate]) -> str:
    return "\n".join(f"{candidate.candidate_id}: {candidate.word}" for candidate in candidates)


def render_blocks_primary_input(clue: str, candidates: Sequence[BlocksCandidate]) -> str:
    return (
        f"Clue: {clue.strip()}\n"
        f"Candidate count: {len(candidates)}\n"
        "Candidates:\n"
        + render_blocks_candidates(candidates)
    )


def render_blocks_primary_prompt(clue: str, candidates: Sequence[BlocksCandidate]) -> str:
    return f"{BLOCKS_PRIMARY_SYSTEM_PROMPT}\n\n{render_blocks_primary_input(clue, candidates)}"


def render_blocks_scoring_input(clue: str, candidates: Sequence[BlocksCandidate]) -> str:
    return (
        f"Clue: {clue.strip()}\n"
        f"Candidate count: {len(candidates)}\n"
        "Candidates:\n"
        + render_blocks_candidates(candidates)
    )


def render_blocks_scoring_prompt(clue: str, candidates: Sequence[BlocksCandidate]) -> str:
    return f"{BLOCKS_SCORING_SYSTEM_PROMPT}\n\n{render_blocks_scoring_input(clue, candidates)}"


_DEBUG_FLAG_OVERRIDES: dict[str, bool] = {}


def _env_flag(name: str) -> bool:
    raw_value = os.getenv(name)
    if raw_value is not None:
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(_DEBUG_FLAG_OVERRIDES.get(name, False))


def _emit_blocks_llm_debug_trace(
    *,
    stage: str,
    model_name: str,
    request_text: str,
    response_text: str,
    response_parsed: Any,
    expected_candidate_ids: Sequence[int],
    error: Exception | None = None,
    force: bool = False,
) -> None:
    if not force and not _env_flag("SEMANTRIS_DEBUG_BLOCKS_LLM"):
        return

    print(f"[Blocks LLM Debug] stage={stage} model={model_name}", flush=True)
    print("[Blocks LLM Debug] expected_candidate_ids=", list(expected_candidate_ids), flush=True)
    print("[Blocks LLM Debug] request_begin", flush=True)
    print(request_text, flush=True)
    print("[Blocks LLM Debug] request_end", flush=True)
    print("[Blocks LLM Debug] response_parsed=", repr(response_parsed), flush=True)
    print("[Blocks LLM Debug] response_text_begin", flush=True)
    print(response_text if response_text else "<empty>", flush=True)
    print("[Blocks LLM Debug] response_text_end", flush=True)
    if error is not None:
        print(
            f"[Blocks LLM Debug] validation_error={error.__class__.__name__}: {error}",
            flush=True,
        )


def _serialize_debug_payload(payload: Any) -> str:
    try:
        return json.dumps(payload, indent=2, sort_keys=True, default=str)
    except Exception:
        return repr(payload)


def _emit_openai_llm_debug_trace(
    *,
    stage: str,
    model_name: str,
    request_payload: dict[str, Any],
    response_payload: Any,
    response_text: str,
    error: Exception | None = None,
    force: bool = False,
) -> None:
    if not force and not _env_flag("SEMANTRIS_DEBUG_OPENAI_LLM"):
        return

    print(f"[OpenAI LLM Debug] stage={stage} model={model_name}", flush=True)
    print("[OpenAI LLM Debug] request_payload_begin", flush=True)
    print(_serialize_debug_payload(request_payload), flush=True)
    print("[OpenAI LLM Debug] request_payload_end", flush=True)
    print("[OpenAI LLM Debug] response_payload_begin", flush=True)
    print(_serialize_debug_payload(response_payload), flush=True)
    print("[OpenAI LLM Debug] response_payload_end", flush=True)
    print("[OpenAI LLM Debug] extracted_text_begin", flush=True)
    print(response_text if response_text else "<empty>", flush=True)
    print("[OpenAI LLM Debug] extracted_text_end", flush=True)
    if error is not None:
        print(
            f"[OpenAI LLM Debug] validation_error={error.__class__.__name__}: {error}",
            flush=True,
        )


class RankingError(RuntimeError):
    pass


@dataclass
class RankingResult:
    ranked_words: list[str]
    latency_ms: int
    provider: str
    used_fallback: bool
    warning: str | None = None


@dataclass
class RuleJudgeResult:
    rule_passed: bool
    short_reason: str
    ranked_words: list[str] | None
    latency_ms: int
    provider: str
    used_fallback: bool
    warning: str | None = None


@dataclass(frozen=True)
class WordScore:
    word: str
    score: int


@dataclass
class WordScoringResult:
    scored_words: list[WordScore]
    latency_ms: int
    provider: str
    used_fallback: bool
    warning: str | None = None


@dataclass
class BlocksPrimaryChoiceResult:
    candidate_id: int
    latency_ms: int
    provider: str
    used_fallback: bool
    warning: str | None = None


@dataclass(frozen=True)
class BlocksCandidateScore:
    candidate_id: int
    score: int


@dataclass
class BlocksCandidateScoringResult:
    scored_candidates: list[BlocksCandidateScore]
    latency_ms: int
    provider: str
    used_fallback: bool
    warning: str | None = None


@dataclass(frozen=True)
class StartupProbeResult:
    attempted: bool
    success: bool
    provider: str
    model_name: str | None
    latency_ms: int | None
    detail: str
    ranked_words: tuple[str, ...] = ()


class RankedWordsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ranked_words: list[str]


class RestrictedRankingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_passed: bool
    short_reason: str
    ranked_words: list[str] | None = None


class WordScoreItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str
    score: int


class WordScoringPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scored_words: list[WordScoreItemPayload]


class BlocksPrimaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: int


class BlocksCandidateScoreItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: int
    score: int


class BlocksCandidateScoringPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scored_candidates: list[BlocksCandidateScoreItemPayload]


class PrimaryRanker(Protocol):
    provider: str

    @property
    def model_name(self) -> str:
        ...

    def rank_words(self, clue: str, words: Sequence[str]) -> list[str]:
        ...

    def judge_restricted_clue(
        self,
        rule_text: str,
        clue: str,
        words: Sequence[str],
    ) -> tuple[bool, str, list[str] | None]:
        ...

    def score_words_against_clue(self, clue: str, words: Sequence[str]) -> list[WordScore]:
        ...

    def pick_blocks_primary_candidate(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> int:
        ...

    def score_blocks_candidates(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> list[BlocksCandidateScore]:
        ...


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


def validate_scored_words(
    scored_words: Sequence[WordScore],
    expected_words: Sequence[str],
) -> list[WordScore]:
    normalized_expected = [normalize_word(word) for word in expected_words]
    normalized_scored = [normalize_word(item.word) for item in scored_words]

    if len(normalized_scored) != len(normalized_expected):
        raise RankingError("Model returned the wrong number of scored words.")

    if len(set(normalized_scored)) != len(normalized_expected):
        raise RankingError("Model returned duplicate scored words.")

    if set(normalized_scored) != set(normalized_expected):
        raise RankingError("Model returned unknown or missing scored words.")

    canonical_lookup = {normalize_word(word): word for word in expected_words}
    validated: list[WordScore] = []
    for item in scored_words:
        if not isinstance(item.score, int):
            raise RankingError("Model returned a non-integer score.")
        if item.score < 0 or item.score > 100:
            raise RankingError("Model returned a score outside the 0..100 range.")
        validated.append(
            WordScore(
                word=canonical_lookup[normalize_word(item.word)],
                score=item.score,
            )
        )
    return validated


def validate_candidate_id(candidate_id: int, expected_candidate_ids: Sequence[int]) -> int:
    if candidate_id not in set(expected_candidate_ids):
        raise RankingError("Model returned an unknown candidate id.")
    return candidate_id


def validate_scored_candidates(
    scored_candidates: Sequence[BlocksCandidateScore],
    expected_candidate_ids: Sequence[int],
) -> list[BlocksCandidateScore]:
    candidate_ids = [item.candidate_id for item in scored_candidates]

    if len(candidate_ids) != len(expected_candidate_ids):
        raise RankingError("Model returned the wrong number of scored candidates.")

    if len(set(candidate_ids)) != len(expected_candidate_ids):
        raise RankingError("Model returned duplicate candidate ids.")

    if set(candidate_ids) != set(expected_candidate_ids):
        raise RankingError("Model returned unknown or missing candidate ids.")

    validated: list[BlocksCandidateScore] = []
    for item in scored_candidates:
        if not isinstance(item.score, int):
            raise RankingError("Model returned a non-integer candidate score.")
        if item.score < 0 or item.score > 100:
            raise RankingError("Model returned a candidate score outside the 0..100 range.")
        validated.append(item)
    return validated


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


def _parse_restricted_ranking_payload(
    payload: object,
    expected_words: Sequence[str],
) -> tuple[bool, str, list[str] | None] | None:
    if payload is None:
        return None

    try:
        parsed = RestrictedRankingPayload.model_validate(payload)
    except ValidationError:
        return None

    ranked_words: list[str] | None = None
    if parsed.rule_passed:
        if parsed.ranked_words is None:
            raise RankingError("Model passed the rule without returning a ranking.")
        ranked_words = validate_ranked_words(parsed.ranked_words, expected_words)
    elif parsed.ranked_words is not None:
        raise RankingError("Model returned ranked words for a failed rule.")

    return (parsed.rule_passed, parsed.short_reason.strip(), ranked_words)


def _parse_word_scoring_payload(
    payload: object,
    expected_words: Sequence[str],
) -> list[WordScore] | None:
    if payload is None:
        return None

    try:
        parsed = WordScoringPayload.model_validate(payload)
    except ValidationError:
        return None

    return validate_scored_words(
        [WordScore(word=item.word.strip(), score=item.score) for item in parsed.scored_words],
        expected_words,
    )


def _parse_blocks_primary_payload(
    payload: object,
    expected_candidate_ids: Sequence[int],
) -> int | None:
    if payload is None:
        return None

    candidate_id: int | None = None
    if isinstance(payload, int):
        candidate_id = payload
    elif isinstance(payload, str) and payload.strip().isdigit():
        candidate_id = int(payload.strip())
    elif isinstance(payload, dict):
        raw_value = payload.get("candidate_id", payload.get("id"))
        if isinstance(raw_value, int):
            candidate_id = raw_value
        elif isinstance(raw_value, str) and raw_value.strip().isdigit():
            candidate_id = int(raw_value.strip())
        else:
            try:
                parsed = BlocksPrimaryPayload.model_validate(payload)
            except ValidationError:
                parsed = None
            if parsed is not None:
                candidate_id = parsed.candidate_id

    if candidate_id is None:
        return None

    return validate_candidate_id(candidate_id, expected_candidate_ids)


def _parse_blocks_candidate_scoring_payload(
    payload: object,
    expected_candidate_ids: Sequence[int],
) -> list[BlocksCandidateScore] | None:
    if payload is None:
        return None

    scored_candidates: list[BlocksCandidateScore] | None = None
    if isinstance(payload, list):
        rows: list[BlocksCandidateScore] = []
        for item in payload:
            if not isinstance(item, dict):
                return None
            candidate_id = item.get("candidate_id", item.get("id"))
            score = item.get("score")
            if not isinstance(candidate_id, int) or not isinstance(score, int):
                return None
            rows.append(BlocksCandidateScore(candidate_id=candidate_id, score=score))
        scored_candidates = rows
    elif isinstance(payload, dict) and "scored_candidates" not in payload:
        rows: list[BlocksCandidateScore] = []
        for key, value in payload.items():
            if isinstance(value, dict):
                candidate_id = value.get("candidate_id", value.get("id", key))
                score = value.get("score")
            else:
                candidate_id = key
                score = value
            try:
                candidate_id_int = int(candidate_id)
            except (TypeError, ValueError):
                return None
            if not isinstance(score, int):
                return None
            rows.append(BlocksCandidateScore(candidate_id=candidate_id_int, score=score))
        scored_candidates = rows
    else:
        try:
            parsed = BlocksCandidateScoringPayload.model_validate(payload)
        except ValidationError:
            return None
        scored_candidates = [
            BlocksCandidateScore(candidate_id=item.candidate_id, score=item.score)
            for item in parsed.scored_candidates
        ]

    return validate_scored_candidates(scored_candidates, expected_candidate_ids)


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


def parse_restricted_ranking(
    response_text: str,
    expected_words: Sequence[str],
) -> tuple[bool, str, list[str] | None]:
    cleaned = _strip_code_fences(response_text)

    for candidate in filter(None, [cleaned, _extract_json_candidate(cleaned)]):
        try:
            parsed = _parse_restricted_ranking_payload(json.loads(candidate), expected_words)
        except json.JSONDecodeError:
            parsed = None

        if parsed is not None:
            return parsed

    raise RankingError("Model returned an invalid restriction judgment payload.")


def parse_word_scoring(response_text: str, expected_words: Sequence[str]) -> list[WordScore]:
    cleaned = _strip_code_fences(response_text)

    for candidate in filter(None, [cleaned, _extract_json_candidate(cleaned)]):
        try:
            parsed = _parse_word_scoring_payload(json.loads(candidate), expected_words)
        except json.JSONDecodeError:
            parsed = None

        if parsed is not None:
            return parsed

    raise RankingError("Model returned an invalid word-scoring payload.")


def parse_blocks_primary_candidate(
    response_text: str,
    expected_candidate_ids: Sequence[int],
) -> int:
    cleaned = _strip_code_fences(response_text)

    for candidate in filter(None, [cleaned, _extract_json_candidate(cleaned)]):
        try:
            parsed = _parse_blocks_primary_payload(json.loads(candidate), expected_candidate_ids)
        except json.JSONDecodeError:
            parsed = None

        if parsed is not None:
            return parsed

    for match in re.findall(r"\d+", cleaned):
        try:
            candidate_id = validate_candidate_id(int(match), expected_candidate_ids)
        except RankingError:
            continue
        return candidate_id

    raise RankingError("Model returned an invalid blocks primary-candidate payload.")


def parse_blocks_candidate_scoring(
    response_text: str,
    expected_candidate_ids: Sequence[int],
) -> list[BlocksCandidateScore]:
    cleaned = _strip_code_fences(response_text)

    for candidate in filter(None, [cleaned, _extract_json_candidate(cleaned)]):
        try:
            parsed = _parse_blocks_candidate_scoring_payload(json.loads(candidate), expected_candidate_ids)
        except json.JSONDecodeError:
            parsed = None

        if parsed is not None:
            return parsed

    line_matches = []
    for line in cleaned.splitlines():
        match = re.search(r"(\d+)\s*[:=-]\s*(\d+)", line.strip())
        if match:
            line_matches.append(
                BlocksCandidateScore(
                    candidate_id=int(match.group(1)),
                    score=int(match.group(2)),
                )
            )
    if line_matches:
        return validate_scored_candidates(line_matches, expected_candidate_ids)

    raise RankingError("Model returned an invalid blocks candidate-scoring payload.")


def _clean_detail_value(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip().replace("\n", " ")
    if not text:
        return None

    return text


def _extract_exception_payload(exc: Exception) -> dict[str, Any] | None:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        return body

    response = getattr(exc, "response", None)
    json_method = getattr(response, "json", None)
    if callable(json_method):
        try:
            payload = json_method()
        except Exception:
            payload = None
        if isinstance(payload, dict):
            return payload

    return None


def _extract_api_error_fields(exc: Exception) -> dict[str, str]:
    payload = _extract_exception_payload(exc)
    if not isinstance(payload, dict):
        return {}

    error_payload = payload.get("error")
    if not isinstance(error_payload, dict):
        return {}

    extracted: dict[str, str] = {}
    for source_key, target_key in (
        ("type", "api_error_type"),
        ("code", "api_error_code"),
        ("status", "api_status"),
        ("param", "api_error_param"),
    ):
        text = _clean_detail_value(error_payload.get(source_key))
        if text is not None:
            extracted[target_key] = text

    return extracted


def _infer_failure_shape(exc: Exception, stage: str) -> tuple[str, str, str]:
    message = str(exc).casefold()
    type_name = exc.__class__.__name__.casefold()
    status_code = getattr(exc, "status_code", None)

    if stage in {"configuration", "initialization"}:
        if "install the openai package" in message or "install the google-genai package" in message:
            return ("dependency-missing", "no", "no")
        return (stage, "no", "no")

    if status_code is not None:
        if status_code == 400:
            category = "bad-request"
        elif status_code == 401:
            category = "authentication"
        elif status_code == 403:
            category = "permission-denied"
        elif status_code == 404:
            category = "not-found"
        elif status_code == 422:
            category = "unprocessable-entity"
        elif status_code == 429:
            category = "rate-limit"
        elif status_code >= 500:
            category = "server-error"
        else:
            category = "api-status-error"
        return (category, "yes", "yes")

    if "connection" in type_name or "timeout" in type_name:
        return ("connection", "yes", "no")

    if isinstance(exc, RankingError):
        return ("response-validation", "yes", "yes")

    return ("runtime-error", "yes", "unknown")


def _provider_context(primary: PrimaryRanker | None) -> dict[str, Any]:
    if primary is None:
        return {}

    return {
        "model_name": getattr(primary, "model_name", None),
        "base_url": getattr(primary, "base_url", None),
    }


def format_provider_diagnostic(
    exc: Exception,
    *,
    provider: str,
    stage: str,
    context: dict[str, Any] | None = None,
) -> str:
    category, request_attempted, endpoint_reached = _infer_failure_shape(exc, stage)
    parts = [
        f"provider={provider}",
        f"stage={stage}",
        f"category={category}",
        f"request_attempted={request_attempted}",
        f"endpoint_reached={endpoint_reached}",
        f"type={exc.__class__.__name__}",
    ]

    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        parts.append(f"status_code={status_code}")

    request_id = _clean_detail_value(getattr(exc, "request_id", None))
    if request_id is not None:
        parts.append(f"request_id={request_id}")

    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        parts.append(f"cause_type={cause.__class__.__name__}")

    for key, value in _extract_api_error_fields(exc).items():
        parts.append(f"{key}={value}")

    for key, value in (context or {}).items():
        cleaned = _clean_detail_value(value)
        if cleaned is not None:
            parts.append(f"{key}={cleaned}")

    message = _clean_detail_value(exc)
    if message is not None:
        parts.append(f"message={message}")

    return "; ".join(parts)


def format_configuration_diagnostic(
    *,
    provider: str,
    missing_env: str,
    context: dict[str, Any] | None = None,
) -> str:
    parts = [
        f"provider={provider}",
        "stage=configuration",
        "category=missing-config",
        "request_attempted=no",
        "endpoint_reached=no",
        f"missing_env={missing_env}",
    ]

    for key, value in (context or {}).items():
        cleaned = _clean_detail_value(value)
        if cleaned is not None:
            parts.append(f"{key}={cleaned}")

    return "; ".join(parts)


def _value_from_attr_or_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _coerce_openai_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text_value = _value_from_attr_or_key(item, "text")
            if isinstance(text_value, str) and text_value.strip():
                parts.append(text_value.strip())
                continue

            nested_value = _value_from_attr_or_key(text_value, "value")
            if isinstance(nested_value, str) and nested_value.strip():
                parts.append(nested_value.strip())
        return "\n".join(parts).strip()

    return ""


def _serialize_openai_response(response: Any) -> Any:
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        try:
            return model_dump()
        except TypeError:
            return model_dump(mode="json")
    if isinstance(response, dict):
        return response
    return repr(response)


def _serialize_openai_stream_chunk(chunk: Any) -> Any:
    model_dump = getattr(chunk, "model_dump", None)
    if callable(model_dump):
        try:
            return model_dump()
        except TypeError:
            return model_dump(mode="json")
    if isinstance(chunk, dict):
        return chunk
    return repr(chunk)


def _extract_openai_stream_text(stream: Any) -> tuple[str, list[Any]]:
    parts: list[str] = []
    serialized_chunks: list[Any] = []
    reasoning_seen = False
    finish_reason: str | None = None

    for chunk in stream:
        serialized_chunks.append(_serialize_openai_stream_chunk(chunk))
        choices = _value_from_attr_or_key(chunk, "choices") or []
        if not choices:
            continue

        first_choice = choices[0]
        finish_reason = _value_from_attr_or_key(first_choice, "finish_reason") or finish_reason
        delta = _value_from_attr_or_key(first_choice, "delta")
        if delta is None:
            continue

        delta_content = _value_from_attr_or_key(delta, "content")
        if isinstance(delta_content, str):
            text_piece = delta_content
        elif isinstance(delta_content, list):
            pieces: list[str] = []
            for item in delta_content:
                text_value = _value_from_attr_or_key(item, "text")
                if isinstance(text_value, str):
                    pieces.append(text_value)
                    continue

                nested_value = _value_from_attr_or_key(text_value, "value")
                if isinstance(nested_value, str):
                    pieces.append(nested_value)
            text_piece = "".join(pieces)
        else:
            text_piece = ""
        if text_piece:
            parts.append(text_piece)

        reasoning_content = _value_from_attr_or_key(delta, "reasoning_content")
        if isinstance(reasoning_content, str) and reasoning_content.strip():
            reasoning_seen = True

    text = "".join(parts).strip()
    if text:
        return (text, serialized_chunks)

    if reasoning_seen:
        if finish_reason == "length":
            raise RankingError(
                "Model returned no final answer content; reasoning_content was present and the response hit the max token limit first."
            )
        raise RankingError(
            "Model returned no final answer content; reasoning_content was present but content was empty."
        )

    raise RankingError("Model returned an empty response.")


def _extract_openai_response_text(response: Any) -> str:
    choices = _value_from_attr_or_key(response, "choices")
    if not choices:
        raise RankingError("Model returned no choices.")

    first_choice = choices[0]
    message = _value_from_attr_or_key(first_choice, "message")
    if message is None:
        raise RankingError("Model returned no message.")

    content = _value_from_attr_or_key(message, "content")
    text = _coerce_openai_message_content(content)
    if not text:
        reasoning_content = _value_from_attr_or_key(message, "reasoning_content")
        finish_reason = _value_from_attr_or_key(first_choice, "finish_reason")
        if isinstance(reasoning_content, str) and reasoning_content.strip():
            if finish_reason == "length":
                raise RankingError(
                    "Model returned no final answer content; reasoning_content was present and the response hit the max token limit first."
                )
            raise RankingError(
                "Model returned no final answer content; reasoning_content was present but content was empty."
            )
        raise RankingError("Model returned an empty response.")

    return text


class GeminiRanker:
    provider = "gemini"

    def __init__(self, api_key: str, model_name: str, client: Any | None = None) -> None:
        if client is None and genai is None:
            raise RankingError("google.genai is not available. Install the google-genai package.")

        self._client = client or genai.Client(api_key=api_key)
        self._model_name = model_name
        self._ranking_generation_config = {
            "temperature": 0.0,
            "max_output_tokens": 512,
            "response_mime_type": "application/json",
            "response_json_schema": RankedWordsPayload.model_json_schema(),
        }
        self._restriction_generation_config = {
            "temperature": 0.0,
            "max_output_tokens": 512,
            "response_mime_type": "application/json",
            "response_json_schema": RestrictedRankingPayload.model_json_schema(),
        }
        self._scoring_generation_config = {
            "temperature": 0.0,
            "max_output_tokens": 512,
            "response_mime_type": "application/json",
            "response_json_schema": WordScoringPayload.model_json_schema(),
        }
        self._blocks_primary_generation_config = {
            "temperature": 0.0,
            "max_output_tokens": 96,
            "response_mime_type": "application/json",
            "response_json_schema": BlocksPrimaryPayload.model_json_schema(),
        }
        self._blocks_scoring_generation_config = {
            "temperature": 0.0,
            "max_output_tokens": 512,
            "response_mime_type": "application/json",
            "response_json_schema": BlocksCandidateScoringPayload.model_json_schema(),
        }

    @property
    def model_name(self) -> str:
        return self._model_name

    def rank_words(self, clue: str, words: Sequence[str]) -> list[str]:
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=render_ranking_prompt(clue, words),
            config=self._ranking_generation_config,
        )
        parsed_words = _parse_ranked_words_payload(getattr(response, "parsed", None))
        if parsed_words is not None:
            return validate_ranked_words(parsed_words, words)

        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise RankingError("Model returned an empty response.")

        return parse_ranked_words(text, words)

    def judge_restricted_clue(
        self,
        rule_text: str,
        clue: str,
        words: Sequence[str],
    ) -> tuple[bool, str, list[str] | None]:
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=render_restriction_prompt(rule_text, clue, words),
            config=self._restriction_generation_config,
        )
        parsed_payload = _parse_restricted_ranking_payload(getattr(response, "parsed", None), words)
        if parsed_payload is not None:
            return parsed_payload

        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise RankingError("Model returned an empty response.")

        return parse_restricted_ranking(text, words)

    def score_words_against_clue(self, clue: str, words: Sequence[str]) -> list[WordScore]:
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=render_scoring_prompt(clue, words),
            config=self._scoring_generation_config,
        )
        parsed_payload = _parse_word_scoring_payload(getattr(response, "parsed", None), words)
        if parsed_payload is not None:
            return parsed_payload

        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise RankingError("Model returned an empty response.")

        return parse_word_scoring(text, words)

    def pick_blocks_primary_candidate(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> int:
        expected_candidate_ids = [candidate.candidate_id for candidate in candidates]
        prompt = render_blocks_primary_prompt(clue, candidates)
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=self._blocks_primary_generation_config,
        )
        response_parsed = getattr(response, "parsed", None)
        response_text = getattr(response, "text", "") or ""
        parsed_candidate_id = _parse_blocks_primary_payload(
            response_parsed,
            expected_candidate_ids,
        )
        if parsed_candidate_id is not None:
            _emit_blocks_llm_debug_trace(
                stage="blocks-primary",
                model_name=self._model_name,
                request_text=prompt,
                response_text=response_text,
                response_parsed=response_parsed,
                expected_candidate_ids=expected_candidate_ids,
                force=False,
            )
            return parsed_candidate_id

        if not response_text.strip():
            error = RankingError("Model returned an empty response.")
            _emit_blocks_llm_debug_trace(
                stage="blocks-primary",
                model_name=self._model_name,
                request_text=prompt,
                response_text=response_text,
                response_parsed=response_parsed,
                expected_candidate_ids=expected_candidate_ids,
                error=error,
                force=True,
            )
            raise RankingError("Model returned an empty response.")

        try:
            return parse_blocks_primary_candidate(response_text, expected_candidate_ids)
        except Exception as exc:
            _emit_blocks_llm_debug_trace(
                stage="blocks-primary",
                model_name=self._model_name,
                request_text=prompt,
                response_text=response_text,
                response_parsed=response_parsed,
                expected_candidate_ids=expected_candidate_ids,
                error=exc if isinstance(exc, Exception) else None,
                force=True,
            )
            raise

    def score_blocks_candidates(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> list[BlocksCandidateScore]:
        expected_candidate_ids = [candidate.candidate_id for candidate in candidates]
        prompt = render_blocks_scoring_prompt(clue, candidates)
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=self._blocks_scoring_generation_config,
        )
        response_parsed = getattr(response, "parsed", None)
        response_text = getattr(response, "text", "") or ""
        parsed_payload = _parse_blocks_candidate_scoring_payload(
            response_parsed,
            expected_candidate_ids,
        )
        if parsed_payload is not None:
            _emit_blocks_llm_debug_trace(
                stage="blocks-scoring",
                model_name=self._model_name,
                request_text=prompt,
                response_text=response_text,
                response_parsed=response_parsed,
                expected_candidate_ids=expected_candidate_ids,
                force=False,
            )
            return parsed_payload

        if not response_text.strip():
            error = RankingError("Model returned an empty response.")
            _emit_blocks_llm_debug_trace(
                stage="blocks-scoring",
                model_name=self._model_name,
                request_text=prompt,
                response_text=response_text,
                response_parsed=response_parsed,
                expected_candidate_ids=expected_candidate_ids,
                error=error,
                force=True,
            )
            raise RankingError("Model returned an empty response.")

        try:
            return parse_blocks_candidate_scoring(response_text, expected_candidate_ids)
        except Exception as exc:
            _emit_blocks_llm_debug_trace(
                stage="blocks-scoring",
                model_name=self._model_name,
                request_text=prompt,
                response_text=response_text,
                response_parsed=response_parsed,
                expected_candidate_ids=expected_candidate_ids,
                error=exc if isinstance(exc, Exception) else None,
                force=True,
            )
            raise


class OpenAICompatibleRanker:
    provider = "openai"

    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: str,
        client: Any | None = None,
    ) -> None:
        if client is None and OpenAI is None:
            raise RankingError("openai is not available. Install the openai package.")

        self._client = client or OpenAI(api_key=api_key, base_url=base_url)
        self._model_name = model_name
        self._base_url = base_url
        self._request_options = {
            "temperature": 0.0,
            "max_tokens": 512,
        }

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def base_url(self) -> str:
        return self._base_url

    def _complete(
        self,
        stage: str,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, dict[str, Any], Any]:
        request_payload = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **self._request_options,
        }
        completion = self._client.chat.completions.create(**request_payload)
        response_payload = _serialize_openai_response(completion)

        try:
            response_text = _extract_openai_response_text(completion)
        except Exception as exc:
            stream_request_payload = {
                **request_payload,
                "stream": True,
            }
            try:
                stream_completion = self._client.chat.completions.create(**stream_request_payload)
                stream_text, stream_chunks = _extract_openai_stream_text(stream_completion)
                stream_response_payload = {
                    "mode": "stream-fallback",
                    "non_stream_response": response_payload,
                    "stream_chunks": stream_chunks,
                    "non_stream_error": str(exc),
                }
                _emit_openai_llm_debug_trace(
                    stage=stage,
                    model_name=self._model_name,
                    request_payload=stream_request_payload,
                    response_payload=stream_response_payload,
                    response_text=stream_text,
                    force=False,
                )
                return (stream_text, stream_request_payload, stream_response_payload)
            except Exception as stream_exc:
                combined_response_payload = {
                    "mode": "stream-fallback-failed",
                    "non_stream_response": response_payload,
                    "non_stream_error": str(exc),
                    "stream_error": str(stream_exc),
                }
                _emit_openai_llm_debug_trace(
                    stage=stage,
                    model_name=self._model_name,
                    request_payload=stream_request_payload,
                    response_payload=combined_response_payload,
                    response_text="",
                    error=stream_exc if isinstance(stream_exc, Exception) else None,
                    force=True,
                )
                raise stream_exc

        _emit_openai_llm_debug_trace(
            stage=stage,
            model_name=self._model_name,
            request_payload=request_payload,
            response_payload=response_payload,
            response_text=response_text,
            force=False,
        )
        return (response_text, request_payload, response_payload)

    def rank_words(self, clue: str, words: Sequence[str]) -> list[str]:
        response_text, request_payload, response_payload = self._complete(
            "ranking",
            RANKING_SYSTEM_PROMPT,
            render_ranking_input(clue, words),
        )
        try:
            return parse_ranked_words(response_text, words)
        except Exception as exc:
            _emit_openai_llm_debug_trace(
                stage="ranking",
                model_name=self._model_name,
                request_payload=request_payload,
                response_payload=response_payload,
                response_text=response_text,
                error=exc if isinstance(exc, Exception) else None,
                force=True,
            )
            raise

    def judge_restricted_clue(
        self,
        rule_text: str,
        clue: str,
        words: Sequence[str],
    ) -> tuple[bool, str, list[str] | None]:
        response_text, request_payload, response_payload = self._complete(
            "restriction",
            RESTRICTION_SYSTEM_PROMPT,
            render_restriction_input(rule_text, clue, words),
        )
        try:
            return parse_restricted_ranking(response_text, words)
        except Exception as exc:
            _emit_openai_llm_debug_trace(
                stage="restriction",
                model_name=self._model_name,
                request_payload=request_payload,
                response_payload=response_payload,
                response_text=response_text,
                error=exc if isinstance(exc, Exception) else None,
                force=True,
            )
            raise

    def score_words_against_clue(self, clue: str, words: Sequence[str]) -> list[WordScore]:
        response_text, request_payload, response_payload = self._complete(
            "scoring",
            SCORING_SYSTEM_PROMPT,
            render_scoring_input(clue, words),
        )
        try:
            return parse_word_scoring(response_text, words)
        except Exception as exc:
            _emit_openai_llm_debug_trace(
                stage="scoring",
                model_name=self._model_name,
                request_payload=request_payload,
                response_payload=response_payload,
                response_text=response_text,
                error=exc if isinstance(exc, Exception) else None,
                force=True,
            )
            raise

    def pick_blocks_primary_candidate(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> int:
        response_text, request_payload, response_payload = self._complete(
            "blocks-primary",
            BLOCKS_PRIMARY_SYSTEM_PROMPT,
            render_blocks_primary_input(clue, candidates),
        )
        expected_candidate_ids = [candidate.candidate_id for candidate in candidates]
        try:
            return parse_blocks_primary_candidate(response_text, expected_candidate_ids)
        except Exception as exc:
            _emit_openai_llm_debug_trace(
                stage="blocks-primary",
                model_name=self._model_name,
                request_payload=request_payload,
                response_payload=response_payload,
                response_text=response_text,
                error=exc if isinstance(exc, Exception) else None,
                force=True,
            )
            raise

    def score_blocks_candidates(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> list[BlocksCandidateScore]:
        response_text, request_payload, response_payload = self._complete(
            "blocks-scoring",
            BLOCKS_SCORING_SYSTEM_PROMPT,
            render_blocks_scoring_input(clue, candidates),
        )
        expected_candidate_ids = [candidate.candidate_id for candidate in candidates]
        try:
            return parse_blocks_candidate_scoring(response_text, expected_candidate_ids)
        except Exception as exc:
            _emit_openai_llm_debug_trace(
                stage="blocks-scoring",
                model_name=self._model_name,
                request_payload=request_payload,
                response_payload=response_payload,
                response_text=response_text,
                error=exc if isinstance(exc, Exception) else None,
                force=True,
            )
            raise


class HeuristicRanker:
    provider = "heuristic-fallback"

    def _score_tuple(self, clue: str, word: str) -> tuple[float, float, str]:
        clue_normalized = normalize_word(clue)
        word_normalized = normalize_word(word)
        clue_tokens = set(re.findall(r"[a-z0-9]+", clue_normalized))
        word_tokens = set(re.findall(r"[a-z0-9]+", word_normalized))
        overlap = len(clue_tokens & word_tokens) * 3.0
        substring_bonus = 1.5 if clue_normalized in word_normalized or word_normalized in clue_normalized else 0.0
        similarity = SequenceMatcher(None, clue_normalized, word_normalized).ratio()
        return (overlap + substring_bonus + similarity, similarity, word_normalized)

    def _absolute_blocks_score(self, clue: str, word: str) -> int:
        clue_normalized = normalize_word(clue)
        word_normalized = normalize_word(word)
        if not clue_normalized or not word_normalized:
            return 0
        if clue_normalized == word_normalized:
            return 100

        clue_tokens = set(re.findall(r"[a-z0-9]+", clue_normalized))
        word_tokens = set(re.findall(r"[a-z0-9]+", word_normalized))
        shared_tokens = len(clue_tokens & word_tokens)
        token_overlap_score = min(45, shared_tokens * 20)
        substring_score = 25 if clue_normalized in word_normalized or word_normalized in clue_normalized else 0
        similarity_score = round(45 * SequenceMatcher(None, clue_normalized, word_normalized).ratio())
        return max(0, min(100, token_overlap_score + substring_score + similarity_score))

    def rank_words(self, clue: str, words: Sequence[str]) -> list[str]:
        return sorted(words, key=lambda word: self._score_tuple(clue, word), reverse=True)

    def score_words_against_clue(self, clue: str, words: Sequence[str]) -> list[WordScore]:
        ranked_words = self.rank_words(clue, words)
        if not ranked_words:
            return []
        if len(ranked_words) == 1:
            return [WordScore(word=ranked_words[0], score=100)]

        step = 100 / max(1, len(ranked_words) - 1)
        return [
            WordScore(word=word, score=max(0, round(100 - index * step)))
            for index, word in enumerate(ranked_words)
        ]

    def pick_blocks_primary_candidate(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> int:
        if not candidates:
            raise RankingError("No block candidates were provided.")
        ranked_candidates = sorted(
            candidates,
            key=lambda candidate: self._score_tuple(clue, candidate.word),
            reverse=True,
        )
        return ranked_candidates[0].candidate_id

    def score_blocks_candidates(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> list[BlocksCandidateScore]:
        return [
            BlocksCandidateScore(
                candidate_id=candidate.candidate_id,
                score=self._absolute_blocks_score(clue, candidate.word),
            )
            for candidate in candidates
        ]


class SemanticFallbackRanker:
    provider = "semantic-fallback"

    @property
    def model_name(self) -> str:
        return "local-semantic-fallback"

    def _token_overlap_score(self, clue_normalized: str, word_normalized: str) -> float:
        clue_tokens = set(re.findall(r"[a-z0-9]+", clue_normalized))
        word_tokens = set(re.findall(r"[a-z0-9]+", word_normalized))
        if not clue_tokens or not word_tokens:
            return 0.0
        return len(clue_tokens & word_tokens) / len(clue_tokens | word_tokens)

    def _fuzzy_ratio(self, clue_normalized: str, word_normalized: str) -> float:
        if fuzz is None:
            return SequenceMatcher(None, clue_normalized, word_normalized).ratio()
        return max(
            fuzz.ratio(clue_normalized, word_normalized) / 100.0,
            fuzz.partial_ratio(clue_normalized, word_normalized) / 100.0,
            fuzz.token_set_ratio(clue_normalized, word_normalized) / 100.0,
        )

    def _score(self, clue: str, word: str) -> float:
        clue_normalized = normalize_word(clue)
        word_normalized = normalize_word(word)
        if not clue_normalized or not word_normalized:
            return 0.0
        if clue_normalized == word_normalized:
            return 10_000.0

        substring_bonus = 0.25 if clue_normalized in word_normalized or word_normalized in clue_normalized else 0.0
        token_overlap = self._token_overlap_score(clue_normalized, word_normalized)
        fuzzy_ratio = self._fuzzy_ratio(clue_normalized, word_normalized)
        sequence_ratio = SequenceMatcher(None, clue_normalized, word_normalized).ratio()

        return (
            token_overlap * 5.0
            + fuzzy_ratio * 3.0
            + sequence_ratio * 1.5
            + substring_bonus
        )

    def rank_words(self, clue: str, words: Sequence[str]) -> list[str]:
        return sorted(
            words,
            key=lambda word: (self._score(clue, word), normalize_word(word)),
            reverse=True,
        )

    def score_words_against_clue(self, clue: str, words: Sequence[str]) -> list[WordScore]:
        ranked_words = self.rank_words(clue, words)
        if not ranked_words:
            return []

        if len(ranked_words) == 1:
            return [WordScore(word=ranked_words[0], score=100)]

        best_score = max(self._score(clue, word) for word in ranked_words) or 1.0
        return [
            WordScore(
                word=word,
                score=max(0, min(100, round((self._score(clue, word) / best_score) * 100))),
            )
            for word in ranked_words
        ]

    def pick_blocks_primary_candidate(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> int:
        if not candidates:
            raise RankingError("No block candidates were provided.")
        ranked_candidates = sorted(
            candidates,
            key=lambda candidate: (self._score(clue, candidate.word), candidate.candidate_id),
            reverse=True,
        )
        return ranked_candidates[0].candidate_id

    def score_blocks_candidates(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> list[BlocksCandidateScore]:
        scored = [
            BlocksCandidateScore(
                candidate_id=candidate.candidate_id,
                score=max(0, min(100, round(self._score(clue, candidate.word) * 18))),
            )
            for candidate in candidates
        ]
        return scored


class FakeRanker:
    provider = "fake-ranker"

    def __init__(self) -> None:
        self._fallback = SemanticFallbackRanker()

    @property
    def model_name(self) -> str:
        return "semantris-fake-ranker"

    def rank_words(self, clue: str, words: Sequence[str]) -> list[str]:
        return self._fallback.rank_words(clue, words)

    def judge_restricted_clue(
        self,
        rule_text: str,
        clue: str,
        words: Sequence[str],
    ) -> tuple[bool, str, list[str] | None]:
        return (
            True,
            "Fake ranker accepted the clue for deterministic testing.",
            self.rank_words(clue, words),
        )

    def score_words_against_clue(self, clue: str, words: Sequence[str]) -> list[WordScore]:
        return self._fallback.score_words_against_clue(clue, words)

    def pick_blocks_primary_candidate(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> int:
        return self._fallback.pick_blocks_primary_candidate(clue, candidates)

    def score_blocks_candidates(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> list[BlocksCandidateScore]:
        return self._fallback.score_blocks_candidates(clue, candidates)


class ResilientRanker:
    def __init__(
        self,
        primary: PrimaryRanker | None,
        semantic_fallback: SemanticFallbackRanker | None = None,
        fallback: HeuristicRanker | None = None,
        cache: SemanticCache | None = None,
        initial_warning: str | None = None,
    ) -> None:
        self.primary = primary
        self.semantic_fallback = semantic_fallback or SemanticFallbackRanker()
        self.fallback = fallback or HeuristicRanker()
        self.cache = cache or NullSemanticCache()
        self.initial_warning = initial_warning

    def _cache_payload(self, *, provider: str, data: Any) -> dict[str, Any]:
        return {
            "provider": provider,
            "data": data,
        }

    def _cache_hit_provider(self, provider: str) -> str:
        return f"{provider}/cache"

    def _cache_key(self, operation: str, payload: dict[str, Any]) -> str:
        return build_cache_key(operation, payload)

    def rank_words(self, clue: str, words: Sequence[str]) -> RankingResult:
        start = time.perf_counter()
        cache_key = self._cache_key(
            "rank_words",
            {
                "clue": normalize_word(clue),
                "words": [normalize_word(word) for word in words],
            },
        )

        if self.primary is not None:
            cached = self.cache.get(cache_key)
            if isinstance(cached, dict) and isinstance(cached.get("data"), list):
                latency_ms = round((time.perf_counter() - start) * 1000)
                return RankingResult(
                    ranked_words=list(cached["data"]),
                    latency_ms=latency_ms,
                    provider=self._cache_hit_provider(str(cached.get("provider", self.primary.provider))),
                    used_fallback=False,
                )

        if self.primary is not None:
            try:
                ranked_words = self.primary.rank_words(clue, words)
                self.cache.set(
                    cache_key,
                    self._cache_payload(provider=self.primary.provider, data=list(ranked_words)),
                )
                latency_ms = round((time.perf_counter() - start) * 1000)
                return RankingResult(
                    ranked_words=ranked_words,
                    latency_ms=latency_ms,
                    provider=self.primary.provider,
                    used_fallback=False,
                )
            except Exception as exc:
                try:
                    fallback_words = self.semantic_fallback.rank_words(clue, words)
                    latency_ms = round((time.perf_counter() - start) * 1000)
                    return RankingResult(
                        ranked_words=fallback_words,
                        latency_ms=latency_ms,
                        provider=self.semantic_fallback.provider,
                        used_fallback=True,
                        warning=(
                            "Primary ranking provider failed, so the semantic fallback ranker was used. "
                            + format_provider_diagnostic(
                                exc,
                                provider=getattr(self.primary, "provider", "primary"),
                                stage="ranking",
                                context=_provider_context(self.primary),
                            )
                        ),
                    )
                except Exception:
                    fallback_words = self.fallback.rank_words(clue, words)
                    latency_ms = round((time.perf_counter() - start) * 1000)
                    return RankingResult(
                        ranked_words=fallback_words,
                        latency_ms=latency_ms,
                        provider=self.fallback.provider,
                        used_fallback=True,
                        warning=(
                            "Primary ranking provider failed, so the heuristic fallback ranker was used. "
                            + format_provider_diagnostic(
                                exc,
                                provider=getattr(self.primary, "provider", "primary"),
                                stage="ranking",
                                context=_provider_context(self.primary),
                            )
                        ),
                    )

        fallback_words = self.semantic_fallback.rank_words(clue, words)
        latency_ms = round((time.perf_counter() - start) * 1000)
        return RankingResult(
            ranked_words=fallback_words,
            latency_ms=latency_ms,
            provider=self.semantic_fallback.provider,
            used_fallback=True,
            warning=(
                self.initial_warning
                or "Primary provider is not configured, so the local semantic fallback ranker was used."
            ),
        )

    def judge_restricted_clue(
        self,
        rule_text: str,
        clue: str,
        words: Sequence[str],
    ) -> RuleJudgeResult:
        start = time.perf_counter()
        cache_key = self._cache_key(
            "judge_restricted_clue",
            {
                "rule_text": rule_text.strip().casefold(),
                "clue": normalize_word(clue),
                "words": [normalize_word(word) for word in words],
            },
        )

        if self.primary is not None:
            cached = self.cache.get(cache_key)
            if isinstance(cached, dict) and isinstance(cached.get("data"), dict):
                payload = cached["data"]
                latency_ms = round((time.perf_counter() - start) * 1000)
                return RuleJudgeResult(
                    rule_passed=bool(payload["rule_passed"]),
                    short_reason=str(payload["short_reason"]),
                    ranked_words=list(payload["ranked_words"]) if payload["ranked_words"] is not None else None,
                    latency_ms=latency_ms,
                    provider=self._cache_hit_provider(str(cached.get("provider", self.primary.provider))),
                    used_fallback=False,
                )

        if self.primary is not None:
            try:
                rule_passed, short_reason, ranked_words = self.primary.judge_restricted_clue(
                    rule_text,
                    clue,
                    words,
                )
                self.cache.set(
                    cache_key,
                    self._cache_payload(
                        provider=self.primary.provider,
                        data={
                            "rule_passed": rule_passed,
                            "short_reason": short_reason,
                            "ranked_words": list(ranked_words) if ranked_words is not None else None,
                        },
                    ),
                )
                latency_ms = round((time.perf_counter() - start) * 1000)
                return RuleJudgeResult(
                    rule_passed=rule_passed,
                    short_reason=short_reason,
                    ranked_words=ranked_words,
                    latency_ms=latency_ms,
                    provider=self.primary.provider,
                    used_fallback=False,
                )
            except Exception as exc:
                fallback_words = self.semantic_fallback.rank_words(clue, words)
                latency_ms = round((time.perf_counter() - start) * 1000)
                return RuleJudgeResult(
                    rule_passed=True,
                    short_reason="Restriction check unavailable, so this turn used fallback ranking without a bonus.",
                    ranked_words=fallback_words,
                    latency_ms=latency_ms,
                    provider=self.semantic_fallback.provider,
                    used_fallback=True,
                    warning=(
                        "Primary restriction judge failed, so the semantic fallback ranker was used. "
                        + format_provider_diagnostic(
                            exc,
                            provider=getattr(self.primary, "provider", "primary"),
                            stage="restriction-judge",
                            context=_provider_context(self.primary),
                        )
                    ),
                )

        fallback_words = self.semantic_fallback.rank_words(clue, words)
        latency_ms = round((time.perf_counter() - start) * 1000)
        return RuleJudgeResult(
            rule_passed=True,
            short_reason="Restriction check unavailable, so this turn used fallback ranking without a bonus.",
            ranked_words=fallback_words,
            latency_ms=latency_ms,
            provider=self.semantic_fallback.provider,
            used_fallback=True,
            warning=(
                self.initial_warning
                or "Primary provider is not configured, so the local semantic fallback ranker was used."
            ),
        )

    def score_words_against_clue(self, clue: str, words: Sequence[str]) -> WordScoringResult:
        start = time.perf_counter()
        cache_key = self._cache_key(
            "score_words_against_clue",
            {
                "clue": normalize_word(clue),
                "words": [normalize_word(word) for word in words],
            },
        )

        if self.primary is not None:
            cached = self.cache.get(cache_key)
            if isinstance(cached, dict) and isinstance(cached.get("data"), list):
                latency_ms = round((time.perf_counter() - start) * 1000)
                return WordScoringResult(
                    scored_words=[
                        WordScore(word=str(item["word"]), score=int(item["score"]))
                        for item in cached["data"]
                    ],
                    latency_ms=latency_ms,
                    provider=self._cache_hit_provider(str(cached.get("provider", self.primary.provider))),
                    used_fallback=False,
                )

        if self.primary is not None:
            try:
                scored_words = self.primary.score_words_against_clue(clue, words)
                self.cache.set(
                    cache_key,
                    self._cache_payload(
                        provider=self.primary.provider,
                        data=[{"word": item.word, "score": item.score} for item in scored_words],
                    ),
                )
                latency_ms = round((time.perf_counter() - start) * 1000)
                return WordScoringResult(
                    scored_words=scored_words,
                    latency_ms=latency_ms,
                    provider=self.primary.provider,
                    used_fallback=False,
                )
            except Exception as exc:
                fallback_scores = self.semantic_fallback.score_words_against_clue(clue, words)
                latency_ms = round((time.perf_counter() - start) * 1000)
                return WordScoringResult(
                    scored_words=fallback_scores,
                    latency_ms=latency_ms,
                    provider=self.semantic_fallback.provider,
                    used_fallback=True,
                    warning=(
                        "Primary scoring provider failed, so the semantic fallback ranker was used. "
                        + format_provider_diagnostic(
                            exc,
                            provider=getattr(self.primary, "provider", "primary"),
                            stage="word-scoring",
                            context=_provider_context(self.primary),
                        )
                    ),
                )

        fallback_scores = self.semantic_fallback.score_words_against_clue(clue, words)
        latency_ms = round((time.perf_counter() - start) * 1000)
        return WordScoringResult(
            scored_words=fallback_scores,
            latency_ms=latency_ms,
            provider=self.semantic_fallback.provider,
            used_fallback=True,
            warning=(
                self.initial_warning
                or "Primary provider is not configured, so the local semantic fallback ranker was used."
            ),
        )

    def pick_blocks_primary_candidate(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> BlocksPrimaryChoiceResult:
        start = time.perf_counter()
        cache_key = self._cache_key(
            "pick_blocks_primary_candidate",
            {
                "clue": normalize_word(clue),
                "candidates": [
                    {"candidate_id": candidate.candidate_id, "word": normalize_word(candidate.word)}
                    for candidate in candidates
                ],
            },
        )

        if self.primary is not None:
            cached = self.cache.get(cache_key)
            if isinstance(cached, dict) and isinstance(cached.get("data"), int):
                latency_ms = round((time.perf_counter() - start) * 1000)
                return BlocksPrimaryChoiceResult(
                    candidate_id=int(cached["data"]),
                    latency_ms=latency_ms,
                    provider=self._cache_hit_provider(str(cached.get("provider", self.primary.provider))),
                    used_fallback=False,
                )

        if self.primary is not None:
            try:
                candidate_id = self.primary.pick_blocks_primary_candidate(clue, candidates)
                self.cache.set(
                    cache_key,
                    self._cache_payload(provider=self.primary.provider, data=int(candidate_id)),
                )
                latency_ms = round((time.perf_counter() - start) * 1000)
                return BlocksPrimaryChoiceResult(
                    candidate_id=candidate_id,
                    latency_ms=latency_ms,
                    provider=self.primary.provider,
                    used_fallback=False,
                )
            except Exception as exc:
                fallback_candidate_id = self.semantic_fallback.pick_blocks_primary_candidate(clue, candidates)
                latency_ms = round((time.perf_counter() - start) * 1000)
                return BlocksPrimaryChoiceResult(
                    candidate_id=fallback_candidate_id,
                    latency_ms=latency_ms,
                    provider=self.semantic_fallback.provider,
                    used_fallback=True,
                    warning=(
                        "Primary blocks primary-choice provider failed, so the semantic fallback ranker was used. "
                        + format_provider_diagnostic(
                            exc,
                            provider=getattr(self.primary, "provider", "primary"),
                            stage="blocks-primary",
                            context=_provider_context(self.primary),
                        )
                    ),
                )

        fallback_candidate_id = self.semantic_fallback.pick_blocks_primary_candidate(clue, candidates)
        latency_ms = round((time.perf_counter() - start) * 1000)
        return BlocksPrimaryChoiceResult(
            candidate_id=fallback_candidate_id,
            latency_ms=latency_ms,
            provider=self.semantic_fallback.provider,
            used_fallback=True,
            warning=(
                self.initial_warning
                or "Primary provider is not configured, so the local semantic fallback ranker was used."
            ),
        )

    def score_blocks_candidates(
        self,
        clue: str,
        candidates: Sequence[BlocksCandidate],
    ) -> BlocksCandidateScoringResult:
        start = time.perf_counter()
        cache_key = self._cache_key(
            "score_blocks_candidates",
            {
                "clue": normalize_word(clue),
                "candidates": [
                    {"candidate_id": candidate.candidate_id, "word": normalize_word(candidate.word)}
                    for candidate in candidates
                ],
            },
        )

        if self.primary is not None:
            cached = self.cache.get(cache_key)
            if isinstance(cached, dict) and isinstance(cached.get("data"), list):
                latency_ms = round((time.perf_counter() - start) * 1000)
                return BlocksCandidateScoringResult(
                    scored_candidates=[
                        BlocksCandidateScore(
                            candidate_id=int(item["candidate_id"]),
                            score=int(item["score"]),
                        )
                        for item in cached["data"]
                    ],
                    latency_ms=latency_ms,
                    provider=self._cache_hit_provider(str(cached.get("provider", self.primary.provider))),
                    used_fallback=False,
                )

        if self.primary is not None:
            try:
                scored_candidates = self.primary.score_blocks_candidates(clue, candidates)
                self.cache.set(
                    cache_key,
                    self._cache_payload(
                        provider=self.primary.provider,
                        data=[
                            {
                                "candidate_id": item.candidate_id,
                                "score": item.score,
                            }
                            for item in scored_candidates
                        ],
                    ),
                )
                latency_ms = round((time.perf_counter() - start) * 1000)
                return BlocksCandidateScoringResult(
                    scored_candidates=scored_candidates,
                    latency_ms=latency_ms,
                    provider=self.primary.provider,
                    used_fallback=False,
                )
            except Exception as exc:
                fallback_scores = self.semantic_fallback.score_blocks_candidates(clue, candidates)
                latency_ms = round((time.perf_counter() - start) * 1000)
                return BlocksCandidateScoringResult(
                    scored_candidates=fallback_scores,
                    latency_ms=latency_ms,
                    provider=self.semantic_fallback.provider,
                    used_fallback=True,
                    warning=(
                        "Primary blocks scoring provider failed, so the semantic fallback ranker was used. "
                        + format_provider_diagnostic(
                            exc,
                            provider=getattr(self.primary, "provider", "primary"),
                            stage="blocks-scoring",
                            context=_provider_context(self.primary),
                        )
                    ),
                )

        fallback_scores = self.semantic_fallback.score_blocks_candidates(clue, candidates)
        latency_ms = round((time.perf_counter() - start) * 1000)
        return BlocksCandidateScoringResult(
            scored_candidates=fallback_scores,
            latency_ms=latency_ms,
            provider=self.semantic_fallback.provider,
            used_fallback=True,
            warning=(
                self.initial_warning
                or "Primary provider is not configured, so the local semantic fallback ranker was used."
            ),
        )


def _build_gemini_ranker_from_settings(settings: Settings, cache: SemanticCache) -> ResilientRanker:
    api_key = settings.gemini_api_key
    model_name = settings.gemini_model

    if not api_key:
        return ResilientRanker(
            primary=None,
            cache=cache,
            initial_warning=(
                "Gemini mode is not configured because GEMINI_API_KEY is missing, "
                "so the local fallback ranker was used. "
                + format_configuration_diagnostic(
                    provider="gemini",
                    missing_env="GEMINI_API_KEY",
                    context={"model_name": model_name},
                )
            ),
        )

    try:
        primary = GeminiRanker(api_key=api_key, model_name=model_name)
        return ResilientRanker(primary=primary, cache=cache)
    except Exception as exc:
        return ResilientRanker(
            primary=None,
            cache=cache,
            initial_warning=(
                "Gemini initialization failed, so the local fallback ranker was used. "
                + format_provider_diagnostic(
                    exc,
                    provider="gemini",
                    stage="initialization",
                    context={"model_name": model_name},
                )
            ),
        )


def _build_openai_ranker_from_settings(settings: Settings, cache: SemanticCache) -> ResilientRanker:
    api_key = settings.openai_api_key
    base_url = settings.openai_base_url
    model_name = settings.openai_model

    if not api_key:
        return ResilientRanker(
            primary=None,
            cache=cache,
            initial_warning=(
                "OpenAI mode is not configured because OPENAI_API_KEY is missing, "
                "so the local fallback ranker was used. "
                + format_configuration_diagnostic(
                    provider="openai",
                    missing_env="OPENAI_API_KEY",
                    context={"model_name": model_name, "base_url": base_url},
                )
            ),
        )

    if not base_url:
        return ResilientRanker(
            primary=None,
            cache=cache,
            initial_warning=(
                "OpenAI mode is not configured because OPENAI_BASE_URL is missing, "
                "so the local fallback ranker was used. "
                + format_configuration_diagnostic(
                    provider="openai",
                    missing_env="OPENAI_BASE_URL",
                    context={"model_name": model_name},
                )
            ),
        )

    try:
        primary = OpenAICompatibleRanker(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
        )
        return ResilientRanker(primary=primary, cache=cache)
    except Exception as exc:
        return ResilientRanker(
            primary=None,
            cache=cache,
            initial_warning=(
                "OpenAI initialization failed, so the local fallback ranker was used. "
                + format_provider_diagnostic(
                    exc,
                    provider="openai",
                    stage="initialization",
                    context={"model_name": model_name, "base_url": base_url},
                )
            ),
        )


def build_ranker_from_env(
    provider_name: str | None = None,
    *,
    settings: Settings | None = None,
) -> ResilientRanker:
    settings = settings or Settings(_env_file=None)
    _DEBUG_FLAG_OVERRIDES.update(
        {
            "SEMANTRIS_DEBUG_BLOCKS_LLM": settings.semantris_debug_blocks_llm,
            "SEMANTRIS_DEBUG_OPENAI_LLM": settings.semantris_debug_openai_llm,
        }
    )
    normalized_provider = (provider_name or settings.semantris_llm_provider).strip().casefold()
    cache = build_semantic_cache(settings)

    if settings.semantris_use_fake_ranker:
        return ResilientRanker(primary=FakeRanker(), cache=cache)

    if normalized_provider == "gemini":
        return _build_gemini_ranker_from_settings(settings, cache)
    if normalized_provider == "openai":
        return _build_openai_ranker_from_settings(settings, cache)

    raise ValueError(
        "Unsupported SEMANTRIS_LLM_PROVIDER. Expected 'gemini' or 'openai'."
    )


def run_startup_probe(
    ranker: ResilientRanker,
    *,
    clue: str = "flight",
    words: Sequence[str] = ("Runway", "Anchor", "Forest"),
) -> StartupProbeResult:
    if ranker.primary is None:
        return StartupProbeResult(
            attempted=False,
            success=False,
            provider="primary",
            model_name=None,
            latency_ms=None,
            detail=ranker.initial_warning
            or "Primary provider is not configured, so the startup probe was skipped.",
        )

    start = time.perf_counter()
    try:
        ranked_words = tuple(ranker.primary.rank_words(clue, words))
        latency_ms = round((time.perf_counter() - start) * 1000)
        return StartupProbeResult(
            attempted=True,
            success=True,
            provider=ranker.primary.provider,
            model_name=ranker.primary.model_name,
            latency_ms=latency_ms,
            detail="Primary provider responded successfully to the startup probe.",
            ranked_words=ranked_words,
        )
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000)
        return StartupProbeResult(
            attempted=True,
            success=False,
            provider=getattr(ranker.primary, "provider", "primary"),
            model_name=getattr(ranker.primary, "model_name", None),
            latency_ms=latency_ms,
            detail=format_provider_diagnostic(
                exc,
                provider=getattr(ranker.primary, "provider", "primary"),
                stage="startup-probe",
                context=_provider_context(ranker.primary),
            ),
        )


def format_startup_probe_message(result: StartupProbeResult) -> str:
    prefix = "[Startup Probe]"

    if not result.attempted:
        return f"{prefix} Provider probe skipped. {result.detail}"

    model_suffix = f" ({result.model_name})" if result.model_name else ""
    latency_suffix = f" in {result.latency_ms} ms" if result.latency_ms is not None else ""

    if result.success:
        ranked_suffix = (
            f" Sample ranking: {', '.join(result.ranked_words)}."
            if result.ranked_words
            else ""
        )
        return (
            f"{prefix} Provider reachable via {result.provider}{model_suffix}{latency_suffix}. "
            f"{result.detail}{ranked_suffix}"
        )

    return (
        f"{prefix} Provider probe failed via {result.provider}{model_suffix}{latency_suffix}. "
        f"{result.detail}"
    )
