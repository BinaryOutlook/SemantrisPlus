import random
import unittest

from game_logic_blocks import (
    apply_vertical_gravity,
    initialize_blocks_state,
    occupied_component_from,
    resolve_blocks_turn,
)


class BlocksGameLogicTests(unittest.TestCase):
    def test_initialize_blocks_state_populates_target_occupied_cells(self) -> None:
        state = initialize_blocks_state(80, "demo.txt", rng=random.Random(4))

        occupied_count = sum(1 for cell in state["grid_indices"] if cell is not None)
        self.assertEqual(occupied_count, state["target_occupied_cells"])
        self.assertEqual(state["target_occupied_cells"], 32)

    def test_occupied_component_uses_four_way_adjacency(self) -> None:
        grid = [
            0, None, None,
            None, 1, None,
            None, None, 2,
        ]

        component = occupied_component_from(grid, 0, width=3, height=3)

        self.assertEqual(component, [0])

    def test_apply_vertical_gravity_compacts_each_column(self) -> None:
        grid = [
            None, None, None,
            1, None, None,
            None, 2, None,
            3, 4, None,
        ]

        compacted = apply_vertical_gravity(grid, width=3, height=4)

        self.assertEqual(
            compacted,
            [
                None, None, None,
                None, None, None,
                1, 2, None,
                3, 4, None,
            ],
        )

    def test_resolve_blocks_turn_clears_chain_scores_and_refills(self) -> None:
        state = {
            "mode_id": "blocks",
            "score": 0,
            "grid_width": 3,
            "grid_height": 4,
            "grid_indices": [
                None, None, None,
                None, None, None,
                0, 1, None,
                2, 3, None,
            ],
            "used_mask": format((1 << 0) | (1 << 1) | (1 << 2) | (1 << 3), "x"),
            "turn_count": 0,
            "started_at_ms": 1,
            "ended_at_ms": None,
            "last_latency_ms": None,
            "last_provider": None,
            "used_fallback": False,
            "last_warning": None,
            "last_clue": None,
            "game_over": False,
            "game_result": None,
            "vocabulary_name": "demo.txt",
            "target_occupied_cells": 4,
            "last_primary_index": None,
            "last_primary_cell": None,
            "last_chain_indices": [],
            "last_chain_size": 0,
            "last_scored_cells": [],
        }

        turn = resolve_blocks_turn(
            state=state,
            primary_cell=6,
            scored_cells={6: 100, 7: 88},
            vocabulary_size=20,
            rng=random.Random(6),
        )

        self.assertEqual(turn.primary_cell, 6)
        self.assertEqual(turn.removed_cells, [6, 7])
        self.assertEqual(turn.score_gain, 25)
        self.assertEqual(turn.state["last_chain_size"], 2)
        self.assertEqual(len(turn.spawned_indices), 2)
        self.assertEqual(sum(1 for cell in turn.state["grid_indices"] if cell is not None), 4)


if __name__ == "__main__":
    unittest.main()
