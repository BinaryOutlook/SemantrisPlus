import os
import unittest
from unittest.mock import patch

import llm_client as llm_module
from llm_client import GeminiRanker, RankingError, ResilientRanker, build_ranker_from_env, parse_ranked_words


class FakeResponse:
    def __init__(self, text="", parsed=None):
        self.text = text
        self.parsed = parsed


class FakeModels:
    def __init__(self, response):
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


class FakeClient:
    def __init__(self, response):
        self.models = FakeModels(response)


class ExplodingPrimary:
    provider = "gemini"

    def rank_words(self, clue, words):
        raise RankingError("provider exploded")


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

    def test_gemini_ranker_uses_structured_output_config(self) -> None:
        response = FakeResponse(
            parsed={"ranked_words": ["Anchor", "Orbit", "Harbor"]},
            text='{"ranked_words": ["Anchor", "Orbit", "Harbor"]}',
        )
        client = FakeClient(response)
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

    def test_resilient_ranker_falls_back_when_primary_fails_at_runtime(self) -> None:
        ranker = ResilientRanker(primary=ExplodingPrimary())

        result = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertTrue(result.used_fallback)
        self.assertEqual(result.provider, "heuristic-fallback")
        self.assertIn("provider exploded", result.warning)

    def test_build_ranker_from_env_warns_when_api_key_is_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            ranker = build_ranker_from_env()

        result = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertTrue(result.used_fallback)
        self.assertIn("GEMINI_API_KEY", result.warning)

    def test_build_ranker_from_env_warns_when_primary_initialization_fails(self) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            with patch.object(llm_module, "GeminiRanker", side_effect=RankingError("bad init")):
                ranker = build_ranker_from_env()

        result = ranker.rank_words("boat", ["Anchor", "Harbor", "Orbit"])

        self.assertTrue(result.used_fallback)
        self.assertIn("bad init", result.warning)


if __name__ == "__main__":
    unittest.main()
