import random
import unittest

from game_logic import (
    add_indices_to_mask,
    calculate_board_size,
    count_remaining_words,
    count_used_words,
    empty_used_mask,
    initialize_game_state,
    resolve_turn,
)


class GameLogicTests(unittest.TestCase):
    def test_calculate_board_size_respects_bounds(self) -> None:
        self.assertEqual(calculate_board_size(0), 5)
        self.assertEqual(calculate_board_size(9), 5)
        self.assertEqual(calculate_board_size(12), 6)
        self.assertEqual(calculate_board_size(100), 20)

    def test_initialize_game_state_draws_unique_opening_board(self) -> None:
        rng = random.Random(7)
        state = initialize_game_state(40, "demo.txt", rng=rng)

        self.assertEqual(state["score"], 0)
        self.assertEqual(len(state["board_indices"]), 5)
        self.assertEqual(len(set(state["board_indices"])), 5)
        self.assertIn(state["target_index"], state["board_indices"])
        self.assertEqual(count_used_words(state["used_mask"]), 5)

    def test_resolve_turn_hit_removes_danger_zone_slice_and_spawns_unseen_words(self) -> None:
        initial_board = [10, 11, 12, 13, 14]
        state = {
            "score": 0,
            "board_indices": initial_board,
            "target_index": 10,
            "used_mask": add_indices_to_mask(empty_used_mask(), initial_board),
            "turn_count": 0,
            "started_at_ms": 1,
            "last_latency_ms": None,
            "last_provider": None,
            "used_fallback": False,
            "last_warning": None,
            "last_clue": None,
            "game_over": False,
            "vocabulary_name": "demo.txt",
        }

        turn = resolve_turn(
            state=state,
            ranked_indices_most_to_least=[10, 11, 12, 13, 14],
            vocabulary_size=25,
            rng=random.Random(3),
        )

        self.assertEqual(turn.resolution, "hit")
        self.assertEqual(turn.words_removed_indices, [10, 11, 12, 13])
        self.assertEqual(turn.state["score"], 4)
        self.assertEqual(turn.state["turn_count"], 1)
        self.assertEqual(len(turn.spawned_indices), 4)
        self.assertEqual(turn.new_board_indices[-1], 14)
        self.assertTrue(set(turn.spawned_indices).isdisjoint(initial_board))
        self.assertEqual(count_remaining_words(25, turn.state["used_mask"]), 16)

    def test_resolve_turn_miss_reorders_without_scoring(self) -> None:
        initial_board = [0, 1, 2, 3, 4]
        state = {
            "score": 6,
            "board_indices": initial_board,
            "target_index": 0,
            "used_mask": add_indices_to_mask(empty_used_mask(), initial_board),
            "turn_count": 4,
            "started_at_ms": 1,
            "last_latency_ms": None,
            "last_provider": None,
            "used_fallback": False,
            "last_warning": None,
            "last_clue": None,
            "game_over": False,
            "vocabulary_name": "demo.txt",
        }

        turn = resolve_turn(
            state=state,
            ranked_indices_most_to_least=[3, 4, 2, 1, 0],
            vocabulary_size=10,
            rng=random.Random(1),
        )

        self.assertEqual(turn.resolution, "miss")
        self.assertEqual(turn.words_removed_indices, [])
        self.assertEqual(turn.state["score"], 6)
        self.assertEqual(turn.state["board_indices"], [0, 1, 2, 4, 3])
        self.assertEqual(turn.state["turn_count"], 5)

    def test_resolve_turn_sets_end_timestamp_when_run_is_cleared(self) -> None:
        state = {
            "score": 0,
            "board_indices": [0],
            "target_index": 0,
            "used_mask": add_indices_to_mask(empty_used_mask(), [0]),
            "turn_count": 0,
            "started_at_ms": 1,
            "ended_at_ms": None,
            "last_latency_ms": None,
            "last_provider": None,
            "used_fallback": False,
            "last_warning": None,
            "last_clue": None,
            "game_over": False,
            "vocabulary_name": "demo.txt",
        }

        turn = resolve_turn(
            state=state,
            ranked_indices_most_to_least=[0],
            vocabulary_size=1,
            rng=random.Random(2),
        )

        self.assertTrue(turn.state["game_over"])
        self.assertEqual(turn.state["board_indices"], [])
        self.assertIsNotNone(turn.state["ended_at_ms"])


if __name__ == "__main__":
    unittest.main()
