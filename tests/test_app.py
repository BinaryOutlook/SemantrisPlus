import unittest
from unittest.mock import patch

import app as app_module
from llm_client import (
    BlocksCandidateScoringResult,
    BlocksCandidateScore,
    BlocksPrimaryChoiceResult,
    RankingResult,
    RuleJudgeResult,
    WordScore,
    WordScoringResult,
)
from persistence import NullRunStore


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

    def judge_restricted_clue(self, rule_text, clue, words):
        ranked = sorted(words, key=lambda word: (word.casefold() != clue.casefold(), word.casefold()))
        return RuleJudgeResult(
            rule_passed=True,
            short_reason="Rule accepted for test.",
            ranked_words=ranked,
            latency_ms=15,
            provider="dummy-ranker",
            used_fallback=False,
            warning=None,
        )

    def score_words_against_clue(self, clue, words):
        scored_words = [
            WordScore(word=word, score=max(0, 100 - index * 20))
            for index, word in enumerate(words)
        ]
        return WordScoringResult(
            scored_words=scored_words,
            latency_ms=18,
            provider="dummy-ranker",
            used_fallback=False,
            warning=None,
        )

    def pick_blocks_primary_candidate(self, clue, candidates):
        return BlocksPrimaryChoiceResult(
            candidate_id=candidates[0].candidate_id,
            latency_ms=9,
            provider="dummy-ranker",
            used_fallback=False,
            warning=None,
        )

    def score_blocks_candidates(self, clue, candidates):
        return BlocksCandidateScoringResult(
            scored_candidates=[
                BlocksCandidateScore(
                    candidate_id=candidate.candidate_id,
                    score=max(0, 100 - index * 15),
                )
                for index, candidate in enumerate(candidates)
            ],
            latency_ms=11,
            provider="dummy-ranker",
            used_fallback=False,
            warning=None,
        )


class BatchRecordingBlocksRanker(DummyRanker):
    def __init__(self) -> None:
        self.primary_batch_sizes: list[int] = []
        self.scoring_batch_sizes: list[int] = []

    def pick_blocks_primary_candidate(self, clue, candidates):
        self.primary_batch_sizes.append(len(candidates))
        return super().pick_blocks_primary_candidate(clue, candidates)

    def score_blocks_candidates(self, clue, candidates):
        self.scoring_batch_sizes.append(len(candidates))
        return super().score_blocks_candidates(clue, candidates)


class AppRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module.app.config.update(TESTING=True)
        self.client = app_module.app.test_client()
        self._original_run_store = app_module.RUN_STORE
        app_module.RUN_STORE = NullRunStore()

    def tearDown(self) -> None:
        app_module.RUN_STORE = self._original_run_store

    def test_home_page_loads_iteration_mode_entry_and_pack_selector(self) -> None:
        response = self.client.get("/")
        default_pack = app_module.VOCABULARY_CATALOG[app_module.DEFAULT_VOCAB_PACK_ID]

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Iteration Mode", response.data)
        self.assertIn(b"Restriction Mode", response.data)
        self.assertIn(b"Blocks Mode", response.data)
        self.assertIn(b'name="vocabulary_pack_id"', response.data)
        self.assertIn(default_pack.display_name.encode("utf-8"), response.data)
        self.assertIn(f"({default_pack.word_count})".encode("utf-8"), response.data)

    def test_iteration_mode_page_loads(self) -> None:
        response = self.client.get("/iteration-mode")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Send Clue", response.data)

    def test_restriction_mode_page_loads(self) -> None:
        response = self.client.get("/restriction-mode")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Restriction Mode", response.data)
        self.assertIn(b"strike-meter", response.data)

    def test_blocks_mode_page_loads(self) -> None:
        response = self.client.get("/blocks-mode")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Blocks Mode", response.data)
        self.assertIn(b"blocks-grid", response.data)

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
        self.assertIn("persistence", payload["state"])
        self.assertIn("run_saved", payload["state"]["persistence"])

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
                self.assertIn("persistence", payload["state"])

    def test_restriction_turn_rejects_local_rule_and_adds_a_strike(self) -> None:
        with self.client as client:
            client.get("/api/restriction/state")
            with client.session_transaction() as session_state:
                session_state["active_rule_id"] = "taboo_initials_str"

            response = client.post("/api/restriction/turn", json={"clue": "storm port"})
            payload = response.get_json()

            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["resolution"], "rule_fail")
            self.assertEqual(payload["state"]["strike_count"], 1)
            self.assertEqual(len(payload["penalty_words"]), 1)
            self.assertFalse(payload["rule_passed"])

    def test_blocks_turn_returns_chain_payload(self) -> None:
        with patch.object(app_module, "RANKER", DummyRanker()):
            with self.client as client:
                state_payload = client.get("/api/blocks/state").get_json()["state"]
                first_word = next(cell["word"] for cell in state_payload["cells"] if cell["word"])

                response = client.post("/api/blocks/turn", json={"clue": first_word})
                payload = response.get_json()

                self.assertEqual(response.status_code, 200)
                self.assertEqual(payload["resolution"], "chain")
                self.assertIn("primary_word", payload)
                self.assertGreaterEqual(payload["state"]["last_chain_size"], 1)
                self.assertIn("state", payload)

    def test_blocks_turn_batches_llm_requests_into_small_groups(self) -> None:
        ranker = BatchRecordingBlocksRanker()

        with patch.object(app_module, "RANKER", ranker):
            with self.client as client:
                client.get("/api/blocks/state")
                response = client.post("/api/blocks/turn", json={"clue": "peak"})

                self.assertEqual(response.status_code, 200)
                self.assertGreaterEqual(len(ranker.primary_batch_sizes), 2)
                self.assertTrue(ranker.scoring_batch_sizes)
                self.assertTrue(
                    all(size <= app_module.BLOCKS_PRIMARY_BATCH_SIZE for size in ranker.primary_batch_sizes)
                )
                self.assertTrue(
                    all(size <= app_module.BLOCKS_SCORING_BATCH_SIZE for size in ranker.scoring_batch_sizes)
                )


if __name__ == "__main__":
    unittest.main()
