import random
import unittest

from game_logic import add_indices_to_mask, empty_used_mask
from game_logic_restriction import (
    RestrictionRule,
    resolve_restriction_turn,
    validate_clue_locally,
)


class RestrictionGameLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.local_rule = RestrictionRule(
            rule_id="taboo_initials_str",
            display_name="Taboo Initials",
            description="Do not use clue words starting with S, T, or R.",
            kind="forbidden_initials",
            params={"letters": ["s", "t", "r"]},
            bonus_multiplier=2.0,
            penalty_bottom_inserts=1,
            local_validator=True,
        )
        self.semantic_rule = RestrictionRule(
            rule_id="pop_culture_only",
            display_name="Pop Culture Only",
            description="The clue must be a real celebrity or fictional character.",
            kind="semantic_entity_class",
            params={"allowed_classes": ["celebrity", "fictional_character"]},
            bonus_multiplier=2.5,
            penalty_bottom_inserts=1,
            local_validator=False,
        )

    def _base_state(self) -> dict:
        board = [10, 11, 12, 13, 14]
        return {
            "mode_id": "restriction",
            "score": 0,
            "board_indices": board,
            "target_index": 10,
            "used_mask": add_indices_to_mask(empty_used_mask(), board),
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
            "strike_count": 0,
            "max_strikes": 3,
            "active_rule_id": self.local_rule.rule_id,
            "active_rule_started_turn": 0,
            "last_rule_passed": None,
            "last_rule_reason": None,
        }

    def test_local_validator_rejects_forbidden_initials(self) -> None:
        passed, reason = validate_clue_locally(self.local_rule, "storm port")

        self.assertFalse(passed)
        self.assertIn("storm", reason)

    def test_rule_fail_adds_strike_and_bottom_penalty_word(self) -> None:
        state = self._base_state()

        turn = resolve_restriction_turn(
            state=state,
            rule=self.local_rule,
            rule_passed=False,
            rule_reason="Clue starts with a forbidden letter.",
            ranked_indices_most_to_least=None,
            vocabulary_size=40,
            allow_bonus=False,
            rules=[self.local_rule, self.semantic_rule],
            rng=random.Random(3),
        )

        self.assertEqual(turn.resolution, "rule_fail")
        self.assertEqual(turn.state["strike_count"], 1)
        self.assertEqual(len(turn.penalty_indices), 1)
        self.assertEqual(turn.new_board_indices[-1], turn.penalty_indices[0])
        self.assertFalse(turn.state["game_over"])

    def test_third_strike_ends_the_run_as_a_loss(self) -> None:
        state = {
            **self._base_state(),
            "strike_count": 2,
        }

        turn = resolve_restriction_turn(
            state=state,
            rule=self.local_rule,
            rule_passed=False,
            rule_reason="Clue starts with a forbidden letter.",
            ranked_indices_most_to_least=None,
            vocabulary_size=40,
            allow_bonus=False,
            rules=[self.local_rule, self.semantic_rule],
            rng=random.Random(2),
        )

        self.assertTrue(turn.state["game_over"])
        self.assertEqual(turn.state["game_result"], "loss")
        self.assertEqual(turn.state["strike_count"], 3)

    def test_passed_rule_applies_bonus_multiplier_to_score(self) -> None:
        state = self._base_state()

        turn = resolve_restriction_turn(
            state=state,
            rule=self.local_rule,
            rule_passed=True,
            rule_reason="Clue satisfies the current rule.",
            ranked_indices_most_to_least=[10, 11, 12, 13, 14],
            vocabulary_size=30,
            allow_bonus=True,
            rules=[self.local_rule, self.semantic_rule],
            rng=random.Random(5),
        )

        self.assertEqual(turn.resolution, "hit")
        self.assertEqual(turn.bonus_multiplier_applied, 2.0)
        self.assertEqual(turn.state["score"], 8)

    def test_rule_rotates_after_tenth_turn(self) -> None:
        state = {
            **self._base_state(),
            "turn_count": 9,
            "active_rule_id": self.local_rule.rule_id,
        }

        turn = resolve_restriction_turn(
            state=state,
            rule=self.local_rule,
            rule_passed=True,
            rule_reason="Clue satisfies the current rule.",
            ranked_indices_most_to_least=[14, 13, 12, 11, 10],
            vocabulary_size=30,
            allow_bonus=True,
            rules=[self.local_rule, self.semantic_rule],
            rng=random.Random(7),
        )

        self.assertEqual(turn.state["turn_count"], 10)
        self.assertEqual(turn.state["active_rule_id"], self.semantic_rule.rule_id)


if __name__ == "__main__":
    unittest.main()
