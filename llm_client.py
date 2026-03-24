from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, ValidationError

try:
    from google import genai
except Exception:  # pragma: no cover - import safety only
    genai = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import safety only
    OpenAI = None


SYSTEM_PROMPT = """
You are the ranking engine for an arcade word association game.
Rank the provided words from MOST related to LEAST related to the clue.

Rules:
- Use every input word exactly once.
- Preserve the original spelling of each word.
- Return the ranking result only.
""".strip()


def render_ranking_input(clue: str, words: Sequence[str]) -> str:
    return f"Clue: {clue.strip()}\nWords:\n" + "\n".join(words)


def render_ranking_prompt(clue: str, words: Sequence[str]) -> str:
    return f"{SYSTEM_PROMPT}\n\n{render_ranking_input(clue, words)}"


class RankingError(RuntimeError):
    pass


@dataclass
class RankingResult:
    ranked_words: list[str]
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


class PrimaryRanker(Protocol):
    provider: str

    @property
    def model_name(self) -> str:
        ...

    def rank_words(self, clue: str, words: Sequence[str]) -> list[str]:
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
        return "\n".join(parts).strip()

    return ""


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
        raise RankingError("Model returned an empty response.")

    return text


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

    @property
    def model_name(self) -> str:
        return self._model_name

    def rank_words(self, clue: str, words: Sequence[str]) -> list[str]:
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=render_ranking_prompt(clue, words),
            config=self._generation_config,
        )
        parsed_words = _parse_ranked_words_payload(getattr(response, "parsed", None))
        if parsed_words is not None:
            return validate_ranked_words(parsed_words, words)

        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise RankingError("Model returned an empty response.")

        return parse_ranked_words(text, words)


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

    def rank_words(self, clue: str, words: Sequence[str]) -> list[str]:
        completion = self._client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": render_ranking_input(clue, words)},
            ],
            **self._request_options,
        )
        return parse_ranked_words(_extract_openai_response_text(completion), words)


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
        primary: PrimaryRanker | None,
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
                    warning=(
                        "Primary ranking provider failed. "
                        + format_provider_diagnostic(
                            exc,
                            provider=getattr(self.primary, "provider", "primary"),
                            stage="ranking",
                            context=_provider_context(self.primary),
                        )
                    ),
                )

        fallback_words = self.fallback.rank_words(clue, words)
        latency_ms = round((time.perf_counter() - start) * 1000)
        return RankingResult(
            ranked_words=fallback_words,
            latency_ms=latency_ms,
            provider=self.fallback.provider,
            used_fallback=True,
            warning=(
                self.initial_warning
                or "Primary provider is not configured, so the local fallback ranker was used."
            ),
        )


def _build_gemini_ranker_from_env() -> ResilientRanker:
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

    if not api_key:
        return ResilientRanker(
            primary=None,
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
        return ResilientRanker(primary=primary)
    except Exception as exc:
        return ResilientRanker(
            primary=None,
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


def _build_openai_ranker_from_env() -> ResilientRanker:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("OPENAI_MODEL", "gpt-5.2-mini")

    if not api_key:
        return ResilientRanker(
            primary=None,
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
        return ResilientRanker(primary=primary)
    except Exception as exc:
        return ResilientRanker(
            primary=None,
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


def build_ranker_from_env(provider_name: str) -> ResilientRanker:
    normalized_provider = provider_name.strip().casefold()

    if normalized_provider == "gemini":
        return _build_gemini_ranker_from_env()
    if normalized_provider == "openai":
        return _build_openai_ranker_from_env()

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
