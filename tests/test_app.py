import unittest
from unittest.mock import patch

import app as app_module
from llm_client import RankingResult


class DummyRanker:
    def rank_words(self, clue, words):
        ranked = sorted(words, key=lambda word: (word.casefold() != clue.casefold(), word.casefold()))
        return RankingResult(
            ranked_words=ranked,
            latency_ms=12,
            provider="dummy-ranker",
            used_fallback=True,
            warning="Test ranker used.",
        )


class AppRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module.app.config.update(TESTING=True)
        self.client = app_module.app.test_client()

    def test_state_endpoint_initializes_session(self) -> None:
        response = self.client.get("/api/game/state")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["state"]["board"]), 5)
        self.assertIn(payload["state"]["target_word"], payload["state"]["board"])

    def test_turn_endpoint_returns_structured_turn_payload(self) -> None:
        with patch.object(app_module, "RANKER", DummyRanker()):
            with self.client as client:
                state_payload = client.get("/api/game/state").get_json()["state"]
                target = state_payload["target_word"]

                response = client.post("/api/game/turn", json={"clue": target})
                payload = response.get_json()

                self.assertEqual(response.status_code, 200)
                self.assertEqual(payload["resolution"], "hit")
                self.assertGreaterEqual(payload["state"]["score"], 1)
                self.assertEqual(payload["state"]["last_provider"], "dummy-ranker")
                self.assertTrue(payload["state"]["used_fallback"])
                self.assertIn("state", payload)
                self.assertIn("ranked_board", payload)
                self.assertIn("new_board", payload)


if __name__ == "__main__":
    unittest.main()
