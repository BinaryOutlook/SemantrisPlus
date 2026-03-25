from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from game_logic import (
    MAX_BOARD_SIZE,
    add_indices_to_mask,
    draw_unseen_indices,
    initialize_game_state,
    resolve_turn,
)

RULE_ROTATION_INTERVAL = 10
DEFAULT_MAX_STRIKES = 3


@dataclass(frozen=True)
class RestrictionRule:
    rule_id: str
    display_name: str
    description: str
    kind: str
    params: dict[str, Any]
    bonus_multiplier: float
    penalty_bottom_inserts: int
    local_validator: bool


@dataclass
class RestrictionTurnResolution:
    state: dict[str, Any]
    resolution: str
    ranked_board_indices: list[int] | None
    new_board_indices: list[int]
    words_removed_indices: list[int]
    spawned_indices: list[int]
    penalty_indices: list[int]
    bonus_multiplier_applied: float


def load_restriction_rules(file_path: Path) -> list[RestrictionRule]:
    with file_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list) or not payload:
        raise ValueError("Restriction rule catalog must contain at least one rule.")

    rules: list[RestrictionRule] = []
    seen_ids: set[str] = set()

    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Restriction rule entries must be JSON objects.")

        rule_id = str(item.get("id", "")).strip()
        if not rule_id:
            raise ValueError("Restriction rules must define a non-empty id.")
        if rule_id in seen_ids:
            raise ValueError(f"Duplicate restriction rule id: {rule_id}")
        seen_ids.add(rule_id)

        rules.append(
            RestrictionRule(
                rule_id=rule_id,
                display_name=str(item.get("display_name", rule_id)).strip() or rule_id,
                description=str(item.get("description", "")).strip() or rule_id,
                kind=str(item.get("kind", "")).strip() or "semantic",
                params=dict(item.get("params") or {}),
                bonus_multiplier=float(item.get("bonus_multiplier", 1.0)),
                penalty_bottom_inserts=max(0, int(item.get("penalty_bottom_inserts", 1))),
                local_validator=bool(item.get("local_validator", False)),
            )
        )

    return rules


def local_rule_supported(rule: RestrictionRule) -> bool:
    return rule.local_validator and rule.kind in {
        "forbidden_initials",
        "max_words",
        "regex_match",
    }


def validate_clue_locally(rule: RestrictionRule, clue: str) -> tuple[bool, str]:
    normalized_clue = clue.strip()
    normalized_tokens = re.findall(r"[a-z0-9']+", normalized_clue.casefold())

    if rule.kind == "forbidden_initials":
        letters = {str(letter).casefold() for letter in rule.params.get("letters", [])}
        offenders = [token for token in normalized_tokens if token and token[0] in letters]
        if offenders:
            return (
                False,
                f"Clue contains words starting with forbidden initials: {', '.join(offenders)}.",
            )
        return True, "Clue satisfies the current letter restriction."

    if rule.kind == "max_words":
        max_words = max(1, int(rule.params.get("count", 1)))
        if len(normalized_tokens) > max_words:
            return False, f"Clue uses {len(normalized_tokens)} words but the limit is {max_words}."
        return True, "Clue stays within the word-count limit."

    if rule.kind == "regex_match":
        pattern = str(rule.params.get("pattern", "")).strip()
        if not pattern:
            return True, "Rule has no active pattern."
        if re.fullmatch(pattern, normalized_clue) is None:
            return False, "Clue does not match the active pattern."
        return True, "Clue matches the active pattern."

    return True, "Rule uses provider-side validation."


def _choose_next_rule_id(
    rules: Sequence[RestrictionRule],
    previous_rule_id: str | None,
    rng: random.Random | None = None,
) -> str:
    if not rules:
        raise ValueError("At least one restriction rule is required.")

    rng = rng or random
    candidates = [rule.rule_id for rule in rules if rule.rule_id != previous_rule_id]
    if not candidates:
        candidates = [rules[0].rule_id]
    return rng.choice(candidates)


def maybe_rotate_rule(
    state: dict[str, Any],
    rules: Sequence[RestrictionRule],
    rng: random.Random | None = None,
) -> dict[str, Any]:
    if state.get("game_over"):
        return state

    turn_count = int(state.get("turn_count", 0))
    if turn_count <= 0 or turn_count % RULE_ROTATION_INTERVAL != 0:
        return state

    next_rule_id = _choose_next_rule_id(rules, state.get("active_rule_id"), rng=rng)
    return {
        **state,
        "active_rule_id": next_rule_id,
        "active_rule_started_turn": turn_count,
    }


def initialize_restriction_state(
    vocabulary_size: int,
    vocabulary_name: str,
    rules: Sequence[RestrictionRule],
    rng: random.Random | None = None,
) -> dict[str, Any]:
    if not rules:
        raise ValueError("Restriction mode requires at least one rule.")

    rng = rng or random
    base_state = initialize_game_state(vocabulary_size, vocabulary_name, rng=rng)
    active_rule_id = _choose_next_rule_id(rules, None, rng=rng)

    return {
        **base_state,
        "mode_id": "restriction",
        "game_result": None,
        "strike_count": 0,
        "max_strikes": DEFAULT_MAX_STRIKES,
        "active_rule_id": active_rule_id,
        "active_rule_started_turn": 0,
        "last_rule_passed": None,
        "last_rule_reason": None,
    }


def _recyclable_indices(
    vocabulary_size: int,
    board_indices: Sequence[int],
    exclude_indices: Sequence[int] | None = None,
) -> list[int]:
    excluded = set(exclude_indices or [])
    board_set = set(board_indices)
    return [
        index
        for index in range(vocabulary_size)
        if index not in board_set and index not in excluded
    ]


def insert_penalty_words_at_bottom(
    state: dict[str, Any],
    vocabulary_size: int,
    count: int,
    rng: random.Random | None = None,
) -> tuple[list[int], str, list[int], list[int], bool, str | None, int | None]:
    rng = rng or random
    existing_board = list(state["board_indices"])
    penalty_indices = draw_unseen_indices(
        vocabulary_size=vocabulary_size,
        used_mask=state["used_mask"],
        count=count,
        rng=rng,
        exclude_indices=existing_board,
    )
    unseen_penalties = list(penalty_indices)

    if len(penalty_indices) < count:
        recycled_pool = _recyclable_indices(
            vocabulary_size=vocabulary_size,
            board_indices=existing_board,
            exclude_indices=penalty_indices,
        )
        recycle_count = min(count - len(penalty_indices), len(recycled_pool))
        if recycle_count:
            penalty_indices.extend(rng.sample(recycled_pool, recycle_count))

    next_board = existing_board + penalty_indices
    trimmed_indices: list[int] = []
    if len(next_board) > MAX_BOARD_SIZE:
        overflow = len(next_board) - MAX_BOARD_SIZE
        trimmed_indices = next_board[:overflow]
        next_board = next_board[overflow:]

    updated_used_mask = add_indices_to_mask(state["used_mask"], unseen_penalties)

    target_trimmed = state["target_index"] in trimmed_indices
    ended_at_ms = int(time.time() * 1000) if target_trimmed else None
    return (
        next_board,
        updated_used_mask,
        penalty_indices,
        trimmed_indices,
        target_trimmed,
        "loss" if target_trimmed else None,
        ended_at_ms,
    )


def resolve_restriction_turn(
    state: dict[str, Any],
    rule: RestrictionRule,
    rule_passed: bool,
    rule_reason: str,
    ranked_indices_most_to_least: Sequence[int] | None,
    vocabulary_size: int,
    *,
    allow_bonus: bool,
    rng: random.Random | None = None,
    rules: Sequence[RestrictionRule] | None = None,
) -> RestrictionTurnResolution:
    rng = rng or random

    if not rule_passed:
        (
            next_board,
            updated_used_mask,
            penalty_indices,
            trimmed_indices,
            target_trimmed,
            game_result,
            ended_at_ms,
        ) = insert_penalty_words_at_bottom(
            state=state,
            vocabulary_size=vocabulary_size,
            count=rule.penalty_bottom_inserts,
            rng=rng,
        )

        strike_count = int(state.get("strike_count", 0)) + 1
        game_over = target_trimmed or strike_count >= int(state.get("max_strikes", DEFAULT_MAX_STRIKES))
        if game_over and ended_at_ms is None:
            ended_at_ms = int(time.time() * 1000)
            game_result = "loss"

        updated_state = {
            **state,
            "board_indices": next_board,
            "target_index": None if target_trimmed else state.get("target_index"),
            "used_mask": updated_used_mask,
            "turn_count": state["turn_count"] + 1,
            "game_over": game_over,
            "game_result": game_result,
            "ended_at_ms": ended_at_ms,
            "strike_count": strike_count,
            "last_rule_passed": False,
            "last_rule_reason": rule_reason,
        }
        if rules is not None:
            updated_state = maybe_rotate_rule(updated_state, rules, rng=rng)

        return RestrictionTurnResolution(
            state=updated_state,
            resolution="rule_fail",
            ranked_board_indices=None,
            new_board_indices=next_board,
            words_removed_indices=[],
            spawned_indices=[],
            penalty_indices=penalty_indices,
            bonus_multiplier_applied=1.0,
        )

    if ranked_indices_most_to_least is None:
        raise ValueError("A passing restriction turn requires ranked board indices.")

    bonus_multiplier = rule.bonus_multiplier if allow_bonus else 1.0
    turn = resolve_turn(
        state=state,
        ranked_indices_most_to_least=ranked_indices_most_to_least,
        vocabulary_size=vocabulary_size,
        score_gain_multiplier=bonus_multiplier,
        rng=rng,
    )

    updated_state = {
        **turn.state,
        "mode_id": "restriction",
        "strike_count": state.get("strike_count", 0),
        "max_strikes": state.get("max_strikes", DEFAULT_MAX_STRIKES),
        "active_rule_id": state.get("active_rule_id"),
        "active_rule_started_turn": state.get("active_rule_started_turn", 0),
        "last_rule_passed": True,
        "last_rule_reason": rule_reason,
        "game_result": turn.state.get("game_result"),
    }

    if rules is not None:
        updated_state = maybe_rotate_rule(updated_state, rules, rng=rng)

    return RestrictionTurnResolution(
        state=updated_state,
        resolution=turn.resolution,
        ranked_board_indices=turn.ranked_board_indices,
        new_board_indices=turn.new_board_indices,
        words_removed_indices=turn.words_removed_indices,
        spawned_indices=turn.spawned_indices,
        penalty_indices=[],
        bonus_multiplier_applied=bonus_multiplier,
    )
