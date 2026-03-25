import os
import unittest
from unittest.mock import patch

import llm_client as llm_module
from llm_client import (
    GeminiRanker,
    OpenAICompatibleRanker,
    RankingError,
    ResilientRanker,
    build_ranker_from_env,
    format_startup_probe_message,
    parse_ranked_words,
    parse_restricted_ranking,
    parse_word_scoring,
    run_startup_probe,
)


class FakeGeminiResponse:
    def __init__(self, text: str = "", parsed=None):
        self.text = text
        self.parsed = parsed


class FakeGeminiModels:
    def __init__(self, response: FakeGeminiResponse):
        self.response = response
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append(
            {
                "model": model,
                "contents": contents,
                "config": config,
            }
        )
        return self.response


class FakeGeminiClient:
    def __init__(self, response: FakeGeminiResponse):
        self.models = FakeGeminiModels(response)


class FakeOpenAIMessage:
    def __init__(self, content):
        self.content = content


class FakeOpenAIChoice:
    def __init__(self, message: FakeOpenAIMessage):
        self.message = message


class FakeOpenAICompletion:
    def __init__(self, content):
        self.choices = [FakeOpenAIChoice(FakeOpenAIMessage(content))]


class FakeOpenAICompletions:
    def __init__(self, response: FakeOpenAICompletion):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeOpenAIChat:
    def __init__(self, response: FakeOpenAICompletion):
        self.completions = FakeOpenAICompletions(response)


class FakeOpenAIClient:
    def __init__(self, response: FakeOpenAICompletion):
        self.chat = FakeOpenAIChat(response)


class FakeAPIStatusError(Exception):
    def __init__(self, message: str, *, status_code: int, request_id: str, body: dict):
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id
        self.body = body


class ExplodingPrimary:
    provider = "gemini"

    @property
    def model_name(self) -> str:
        return "exploding-primary"

    def rank_words(self, clue, words):
        raise RankingError("provider exploded")

    def judge_restricted_clue(self, rule_text, clue, words):
        raise RankingError("provider exploded")

    def score_words_against_clue(self, clue, words):
        raise RankingError("provider exploded")


class StatusFailingPrimary:
    provider = "openai"
    model_name = "gpt-5.2-mini"
    base_url = "https://example.com/v1"

    def rank_words(self, clue, words):
        raise FakeAPIStatusError(
            "invalid api key",
            status_code=401,
            request_id="req_123",
            body={
                "error": {
                    "type": "invalid_request_error",
                    "code": "invalid_api_key",
                }
            },
        )

    def judge_restricted_clue(self, rule_text, clue, words):
        return self.rank_words(clue, words)

    def score_words_against_clue(self, clue, words):
        return self.rank_words(clue, words)


class LLMClientTests(unittest.TestCase):
    def test_parse_ranked_words_accepts_structured_json(self) -> None:
        words = ["Anchor", "Harbor", "Orbit"]
        ranked = parse_ranked_words(
            '{"ranked_words": ["Anchor", "Orbit", "Harbor"]}',
            words,
        )

        self.assertEqual(ranked, ["Anchor", "Orbit", "Harbor"])

    def test_parse_ranked_words_rejects_invalid_permutation(self) -> None:
        words = ["Anchor", "Harbor", "Orbit"]

        with self.assertRaises(RankingError):
            parse_ranked_words(
                '{"ranked_words": ["Anchor", "Anchor", "Orbit"]}',
                words,
            )

    def test_parse_restricted_ranking_accepts_valid_json(self) -> None:
        words = ["Anchor", "Harbor", "Orbit"]

        rule_passed, short_reason, ranked_words = parse_restricted_ranking(
            '{"rule_passed": true, "short_reason": "Rule satisfied.", "ranked_words": ["Anchor", "Orbit", "Harbor"]}',
            words,
        )

        self.assertTrue(rule_passed)
        self.assertEqual(short_reason, "Rule satisfied.")
        self.assertEqual(ranked_words, ["Anchor", "Orbit", "Harbor"])

    def test_parse_word_scoring_accepts_valid_json(self) -> None:
        words = ["Anchor", "Harbor", "Orbit"]

        scored_words = parse_word_scoring(
            '{"scored_words": [{"word": "Anchor", "score": 100}, {"word": "Harbor", "score": 60}, {"word": "Orbit", "score": 20}]}',
            words,
        )

        self.assertEqual(scored_words[0].word, "Anchor")
        self.assertEqual(scored_words[0].score, 100)
        self.assertEqual(len(scored_words), 3)

    def test_gemini_ranker_uses_structured_output_config(self) -> None:
        response = FakeGeminiResponse(
            parsed={"ranked_words": ["Anchor", "Orbit", "Harbor"]},
            text='{"ranked_words": ["Anchor", "Orbit", "Harbor"]}',
        )
        client = FakeGeminiClient(response)
        ranker = GeminiRanker(
            api_key="test-key",
            model_name="gemini-2.5-flash-lite",
            client=client,
        )

        ranked = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertEqual(ranked, ["Anchor", "Orbit", "Harbor"])
        self.assertEqual(client.models.calls[0]["model"], "gemini-2.5-flash-lite")
        self.assertEqual(client.models.calls[0]["config"]["response_mime_type"], "application/json")
        self.assertIn("response_json_schema", client.models.calls[0]["config"])

    def test_openai_ranker_accepts_json_content(self) -> None:
        response = FakeOpenAICompletion('{"ranked_words": ["Anchor", "Orbit", "Harbor"]}')
        client = FakeOpenAIClient(response)
        ranker = OpenAICompatibleRanker(
            api_key="test-key",
            base_url="https://example.com/v1",
            model_name="gpt-5.2-mini",
            client=client,
        )

        ranked = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertEqual(ranked, ["Anchor", "Orbit", "Harbor"])
        self.assertEqual(client.chat.completions.calls[0]["model"], "gpt-5.2-mini")
        self.assertEqual(client.chat.completions.calls[0]["messages"][0]["role"], "system")
        self.assertEqual(client.chat.completions.calls[0]["messages"][1]["role"], "user")

    def test_openai_ranker_accepts_line_based_content(self) -> None:
        response = FakeOpenAICompletion("Anchor\nOrbit\nHarbor")
        ranker = OpenAICompatibleRanker(
            api_key="test-key",
            base_url="https://example.com/v1",
            model_name="gpt-5.2-mini",
            client=FakeOpenAIClient(response),
        )

        ranked = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertEqual(ranked, ["Anchor", "Orbit", "Harbor"])

    def test_openai_ranker_rejects_empty_content(self) -> None:
        response = FakeOpenAICompletion("")
        ranker = OpenAICompatibleRanker(
            api_key="test-key",
            base_url="https://example.com/v1",
            model_name="gpt-5.2-mini",
            client=FakeOpenAIClient(response),
        )

        with self.assertRaises(RankingError):
            ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

    def test_resilient_ranker_falls_back_when_primary_fails_at_runtime(self) -> None:
        ranker = ResilientRanker(primary=ExplodingPrimary())

        result = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertTrue(result.used_fallback)
        self.assertEqual(result.provider, "heuristic-fallback")
        self.assertIn("provider exploded", result.warning)

    def test_resilient_ranker_restriction_judge_falls_back_to_bonusless_pass(self) -> None:
        ranker = ResilientRanker(primary=ExplodingPrimary())

        result = ranker.judge_restricted_clue("Use a celebrity name.", "boat", ["Anchor", "Harbor", "Orbit"])

        self.assertTrue(result.rule_passed)
        self.assertTrue(result.used_fallback)
        self.assertIsNotNone(result.ranked_words)
        self.assertIn("provider exploded", result.warning)

    def test_resilient_ranker_scoring_falls_back_when_primary_fails(self) -> None:
        ranker = ResilientRanker(primary=ExplodingPrimary())

        result = ranker.score_words_against_clue("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertTrue(result.used_fallback)
        self.assertEqual(result.provider, "heuristic-fallback")
        self.assertEqual(len(result.scored_words), 3)

    def test_build_ranker_from_env_warns_when_gemini_api_key_is_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            ranker = build_ranker_from_env("gemini")

        result = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertTrue(result.used_fallback)
        self.assertIn("GEMINI_API_KEY", result.warning)
        self.assertIn("stage=configuration", result.warning)
        self.assertIn("request_attempted=no", result.warning)

    def test_build_ranker_from_env_warns_when_gemini_initialization_fails(self) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            with patch.object(llm_module, "GeminiRanker", side_effect=RankingError("bad init")):
                ranker = build_ranker_from_env("gemini")

        result = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertTrue(result.used_fallback)
        self.assertIn("bad init", result.warning)

    def test_build_ranker_from_env_warns_when_openai_api_key_is_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            ranker = build_ranker_from_env("openai")

        result = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertTrue(result.used_fallback)
        self.assertIn("OPENAI_API_KEY", result.warning)
        self.assertIn("missing_env=OPENAI_API_KEY", result.warning)
        self.assertIn("request_attempted=no", result.warning)

    def test_build_ranker_from_env_warns_when_openai_base_url_is_missing(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            ranker = build_ranker_from_env("openai")

        result = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertTrue(result.used_fallback)
        self.assertIn("OPENAI_BASE_URL", result.warning)

    def test_build_ranker_from_env_warns_when_openai_initialization_fails(self) -> None:
        env = {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://example.com/v1",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch.object(llm_module, "OpenAICompatibleRanker", side_effect=RankingError("bad init")):
                ranker = build_ranker_from_env("openai")

        result = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertTrue(result.used_fallback)
        self.assertIn("bad init", result.warning)

    def test_build_ranker_from_env_reports_dependency_missing_during_openai_initialization(self) -> None:
        env = {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://example.com/v1",
            "OPENAI_MODEL": "gpt-5.2-mini",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch.object(llm_module, "OpenAI", None):
                ranker = build_ranker_from_env("openai")

        result = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertTrue(result.used_fallback)
        self.assertIn("category=dependency-missing", result.warning)
        self.assertIn("stage=initialization", result.warning)
        self.assertIn("request_attempted=no", result.warning)
        self.assertIn("base_url=https://example.com/v1", result.warning)

    def test_build_ranker_from_env_openai_mode_does_not_construct_gemini(self) -> None:
        env = {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://example.com/v1",
            "OPENAI_MODEL": "gpt-5.2-mini",
        }
        stub_ranker = object()

        with patch.dict(os.environ, env, clear=True):
            with patch.object(llm_module, "GeminiRanker", side_effect=AssertionError("should not build Gemini")):
                with patch.object(llm_module, "OpenAICompatibleRanker", return_value=stub_ranker) as patched_openai:
                    ranker = build_ranker_from_env("openai")

        self.assertIs(ranker.primary, stub_ranker)
        patched_openai.assert_called_once()

    def test_build_ranker_from_env_gemini_mode_does_not_construct_openai(self) -> None:
        env = {
            "GEMINI_API_KEY": "test-key",
            "GEMINI_MODEL": "gemini-2.5-flash-lite",
        }
        stub_ranker = object()

        with patch.dict(os.environ, env, clear=True):
            with patch.object(llm_module, "OpenAICompatibleRanker", side_effect=AssertionError("should not build OpenAI")):
                with patch.object(llm_module, "GeminiRanker", return_value=stub_ranker) as patched_gemini:
                    ranker = build_ranker_from_env("gemini")

        self.assertIs(ranker.primary, stub_ranker)
        patched_gemini.assert_called_once()

    def test_build_ranker_from_env_rejects_unknown_provider(self) -> None:
        with self.assertRaises(ValueError):
            build_ranker_from_env("not-a-provider")

    def test_run_startup_probe_reports_success_for_primary(self) -> None:
        response = FakeGeminiResponse(
            parsed={"ranked_words": ["Runway", "Anchor", "Forest"]},
            text='{"ranked_words": ["Runway", "Anchor", "Forest"]}',
        )
        primary = GeminiRanker(
            api_key="test-key",
            model_name="gemini-2.5-flash-lite",
            client=FakeGeminiClient(response),
        )

        result = run_startup_probe(ResilientRanker(primary=primary))

        self.assertTrue(result.attempted)
        self.assertTrue(result.success)
        self.assertEqual(result.provider, "gemini")
        self.assertEqual(result.model_name, "gemini-2.5-flash-lite")
        self.assertEqual(result.ranked_words, ("Runway", "Anchor", "Forest"))
        self.assertIsNotNone(result.latency_ms)

    def test_run_startup_probe_reports_skipped_when_primary_missing(self) -> None:
        result = run_startup_probe(ResilientRanker(primary=None, initial_warning="No API key."))

        self.assertFalse(result.attempted)
        self.assertFalse(result.success)
        self.assertIn("No API key.", result.detail)

    def test_run_startup_probe_reports_status_code_and_request_id(self) -> None:
        result = run_startup_probe(ResilientRanker(primary=StatusFailingPrimary()))

        self.assertTrue(result.attempted)
        self.assertFalse(result.success)
        self.assertIn("status_code=401", result.detail)
        self.assertIn("request_id=req_123", result.detail)
        self.assertIn("api_error_code=invalid_api_key", result.detail)
        self.assertIn("endpoint_reached=yes", result.detail)

    def test_format_startup_probe_message_includes_latency_and_ranking(self) -> None:
        message = format_startup_probe_message(
            llm_module.StartupProbeResult(
                attempted=True,
                success=True,
                provider="openai",
                model_name="gpt-5.2-mini",
                latency_ms=123,
                detail="Primary provider responded successfully to the startup probe.",
                ranked_words=("Runway", "Anchor", "Forest"),
            )
        )

        self.assertIn("Provider reachable via openai", message)
        self.assertIn("123 ms", message)
        self.assertIn("Runway, Anchor, Forest", message)
        self.assertNotIn("Gemini reachable", message)


if __name__ == "__main__":
    unittest.main()
