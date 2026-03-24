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

    def test_home_page_loads_iteration_mode_entry_and_pack_selector(self) -> None:
        response = self.client.get("/")
        default_pack = app_module.VOCABULARY_CATALOG[app_module.DEFAULT_VOCAB_PACK_ID]

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Iteration Mode", response.data)
        self.assertIn(b'name="vocabulary_pack_id"', response.data)
        self.assertIn(default_pack.display_name.encode("utf-8"), response.data)
        self.assertIn(f"({default_pack.word_count})".encode("utf-8"), response.data)

    def test_iteration_mode_page_loads(self) -> None:
        response = self.client.get("/iteration-mode")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Send Clue", response.data)

    def test_start_iteration_mode_selects_requested_pack(self) -> None:
        pack = app_module.VOCABULARY_CATALOG["super_light_test"]

        with self.client as client:
            response = client.post(
                "/start-iteration-mode",
                data={"vocabulary_pack_id": pack.pack_id},
            )

            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.location.endswith("/iteration-mode"))

            state_payload = client.get("/api/game/state").get_json()["state"]
            self.assertEqual(state_payload["vocabulary_name"], pack.file_path.name)
            self.assertEqual(state_payload["total_vocabulary"], pack.word_count)

    def test_start_iteration_mode_rejects_unknown_pack(self) -> None:
        response = self.client.post(
            "/start-iteration-mode",
            data={"vocabulary_pack_id": "not-a-real-pack"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Unknown vocabulary pack.", response.data)

    def test_should_run_startup_probe_respects_skip_env_and_reloader(self) -> None:
        with patch.dict("os.environ", {"SEMANTRIS_SKIP_LLM_STARTUP_PROBE": "1"}, clear=False):
            self.assertFalse(app_module.should_run_startup_probe(debug_mode=False))

        with patch.dict("os.environ", {}, clear=True):
            self.assertTrue(app_module.should_run_startup_probe(debug_mode=False))
            self.assertFalse(app_module.should_run_startup_probe(debug_mode=True))

        with patch.dict("os.environ", {"WERKZEUG_RUN_MAIN": "true"}, clear=True):
            self.assertTrue(app_module.should_run_startup_probe(debug_mode=True))

    def test_state_endpoint_initializes_session(self) -> None:
        response = self.client.get("/api/game/state")
        payload = response.get_json()
        default_pack = app_module.VOCABULARY_CATALOG[app_module.DEFAULT_VOCAB_PACK_ID]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["state"]["board"]), 5)
        self.assertIn(payload["state"]["target_word"], payload["state"]["board"])
        self.assertEqual(payload["state"]["vocabulary_name"], default_pack.file_path.name)
        self.assertEqual(payload["state"]["total_vocabulary"], default_pack.word_count)

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
