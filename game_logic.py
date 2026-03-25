from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Sequence

MIN_BOARD_SIZE = 5
MAX_BOARD_SIZE = 20
DESTRUCTION_ZONE_SIZE = 4


def calculate_board_size(score: int) -> int:
    return min(MAX_BOARD_SIZE, max(MIN_BOARD_SIZE, score // 2))


def empty_used_mask() -> str:
    return "0"


def count_used_words(used_mask: str) -> int:
    return int(used_mask or "0", 16).bit_count()


def count_remaining_words(vocabulary_size: int, used_mask: str) -> int:
    return max(0, vocabulary_size - count_used_words(used_mask))


def add_indices_to_mask(used_mask: str, indices: Sequence[int]) -> str:
    mask_value = int(used_mask or "0", 16)
    for index in indices:
        mask_value |= 1 << index
    return format(mask_value, "x")


def _used_index_set(used_mask: str) -> set[int]:
    value = int(used_mask or "0", 16)
    indices: set[int] = set()
    bit_index = 0

    while value:
        if value & 1:
            indices.add(bit_index)
        value >>= 1
        bit_index += 1

    return indices


def draw_unseen_indices(
    vocabulary_size: int,
    used_mask: str,
    count: int,
    rng: random.Random | None = None,
    exclude_indices: Sequence[int] | None = None,
) -> list[int]:
    if count <= 0 or vocabulary_size <= 0:
        return []

    rng = rng or random
    excluded = set(exclude_indices or [])
    used = _used_index_set(used_mask)
    available = [
        index
        for index in range(vocabulary_size)
        if index not in used and index not in excluded
    ]

    if not available:
        return []

    selection_size = min(count, len(available))
    return rng.sample(available, selection_size)


def initialize_game_state(
    vocabulary_size: int,
    vocabulary_name: str,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    if vocabulary_size <= 0:
        raise ValueError("Vocabulary must contain at least one word.")

    rng = rng or random
    initial_size = min(calculate_board_size(0), vocabulary_size)
    board_indices = draw_unseen_indices(
        vocabulary_size=vocabulary_size,
        used_mask=empty_used_mask(),
        count=initial_size,
        rng=rng,
    )
    used_mask = add_indices_to_mask(empty_used_mask(), board_indices)
    target_index = rng.choice(board_indices)

    return {
        "score": 0,
        "board_indices": board_indices,
        "target_index": target_index,
        "used_mask": used_mask,
        "turn_count": 0,
        "started_at_ms": int(time.time() * 1000),
        "ended_at_ms": None,
        "last_latency_ms": None,
        "last_provider": None,
        "used_fallback": False,
        "last_warning": None,
        "last_clue": None,
        "game_over": False,
        "vocabulary_name": vocabulary_name,
    }


@dataclass
class TurnResolution:
    state: dict[str, Any]
    resolution: str
    ranked_board_indices: list[int]
    new_board_indices: list[int]
    words_removed_indices: list[int]
    spawned_indices: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution": self.resolution,
            "ranked_board_indices": self.ranked_board_indices,
            "new_board_indices": self.new_board_indices,
            "words_removed_indices": self.words_removed_indices,
            "spawned_indices": self.spawned_indices,
        }


def resolve_turn(
    state: dict[str, Any],
    ranked_indices_most_to_least: Sequence[int],
    vocabulary_size: int,
    score_gain_multiplier: float = 1.0,
    rng: random.Random | None = None,
) -> TurnResolution:
    rng = rng or random
    ranked_indices = list(ranked_indices_most_to_least)
    target_index = state["target_index"]
    zone_size = min(DESTRUCTION_ZONE_SIZE, len(ranked_indices))

    if target_index not in ranked_indices:
        raise ValueError("Target word is missing from the ranked board.")

    ranked_board_indices = list(reversed(ranked_indices))
    target_rank_index = ranked_indices.index(target_index)

    if target_rank_index < zone_size:
        removed = ranked_indices[target_rank_index:zone_size]
        survivors_ranked = ranked_indices[:target_rank_index] + ranked_indices[zone_size:]
        score_gain = max(0, round(len(removed) * score_gain_multiplier))
        new_score = state["score"] + score_gain
        desired_size = calculate_board_size(new_score)
        spawned = draw_unseen_indices(
            vocabulary_size=vocabulary_size,
            used_mask=state["used_mask"],
            count=max(0, desired_size - len(survivors_ranked)),
            rng=rng,
            exclude_indices=survivors_ranked,
        )
        updated_used_mask = add_indices_to_mask(state["used_mask"], spawned)
        new_board_indices = spawned + list(reversed(survivors_ranked))
        next_target = None
        if spawned:
            next_target = rng.choice(spawned)
        elif new_board_indices:
            next_target = rng.choice(new_board_indices)

        updated_state = {
            **state,
            "score": new_score,
            "board_indices": new_board_indices,
            "target_index": next_target,
            "used_mask": updated_used_mask,
            "turn_count": state["turn_count"] + 1,
            "game_over": not new_board_indices,
            "ended_at_ms": int(time.time() * 1000) if not new_board_indices else None,
            "game_result": "win" if not new_board_indices else None,
        }
        return TurnResolution(
            state=updated_state,
            resolution="hit",
            ranked_board_indices=ranked_board_indices,
            new_board_indices=new_board_indices,
            words_removed_indices=removed,
            spawned_indices=spawned,
        )

    updated_state = {
        **state,
        "board_indices": ranked_board_indices,
        "turn_count": state["turn_count"] + 1,
        "game_over": False,
        "ended_at_ms": None,
        "game_result": None,
    }
    return TurnResolution(
        state=updated_state,
        resolution="miss",
        ranked_board_indices=ranked_board_indices,
        new_board_indices=ranked_board_indices,
        words_removed_indices=[],
        spawned_indices=[],
    )
