from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Sequence

from game_logic import add_indices_to_mask, count_remaining_words, draw_unseen_indices, empty_used_mask

BLOCKS_GRID_WIDTH = 8
BLOCKS_GRID_HEIGHT = 10
BLOCKS_TARGET_OCCUPIED_CELLS = 32
BLOCKS_COMBO_THRESHOLD = 75
BLOCKS_BASE_POINTS = 10
BLOCKS_COMBO_GROWTH_BASE = 2.5


@dataclass
class BlocksTurnResolution:
    state: dict[str, Any]
    primary_cell: int
    primary_index: int
    removed_cells: list[int]
    removed_indices: list[int]
    spawned_cells: list[int]
    spawned_indices: list[int]
    scored_cells: list[dict[str, int]]
    score_gain: int


def cell_index(row: int, col: int, width: int) -> int:
    return row * width + col


def row_col(index: int, width: int) -> tuple[int, int]:
    return divmod(index, width)


def occupied_neighbors(
    grid_indices: Sequence[int | None],
    cell: int,
    width: int,
    height: int,
) -> list[int]:
    row, col = row_col(cell, width)
    neighbors: list[int] = []
    for next_row, next_col in (
        (row - 1, col),
        (row + 1, col),
        (row, col - 1),
        (row, col + 1),
    ):
        if next_row < 0 or next_row >= height or next_col < 0 or next_col >= width:
            continue
        next_cell = cell_index(next_row, next_col, width)
        if grid_indices[next_cell] is not None:
            neighbors.append(next_cell)
    return neighbors


def occupied_component_from(
    grid_indices: Sequence[int | None],
    start_cell: int,
    width: int,
    height: int,
) -> list[int]:
    if grid_indices[start_cell] is None:
        return []

    visited: set[int] = {start_cell}
    queue: list[int] = [start_cell]

    while queue:
        current = queue.pop(0)
        for neighbor in occupied_neighbors(grid_indices, current, width, height):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append(neighbor)

    return sorted(visited)


def occupied_word_indices(grid_indices: Sequence[int | None]) -> list[int]:
    return [index for index in grid_indices if index is not None]


def apply_vertical_gravity(
    grid_indices: Sequence[int | None],
    width: int,
    height: int,
) -> list[int | None]:
    next_grid: list[int | None] = [None] * len(grid_indices)

    for col in range(width):
        column_words = [
            grid_indices[cell_index(row, col, width)]
            for row in range(height)
            if grid_indices[cell_index(row, col, width)] is not None
        ]
        destination_row = height - 1
        for word_index in reversed(column_words):
            next_grid[cell_index(destination_row, col, width)] = word_index
            destination_row -= 1

    return next_grid


def spawn_words_into_top_slots(
    grid_indices: Sequence[int | None],
    spawned_indices_by_cell: dict[int, int],
) -> list[int | None]:
    next_grid = list(grid_indices)
    for cell, word_index in spawned_indices_by_cell.items():
        next_grid[cell] = word_index
    return next_grid


def serialize_blocks_grid(
    grid_indices: Sequence[int | None],
    vocabulary: Sequence[str],
    width: int,
) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for cell, word_index in enumerate(grid_indices):
        row, col = row_col(cell, width)
        cells.append(
            {
                "cell": cell,
                "row": row,
                "col": col,
                "word": vocabulary[word_index] if word_index is not None else None,
            }
        )
    return cells


def score_gain_for_chain(chain_size: int) -> int:
    if chain_size <= 0:
        return 0
    return round(BLOCKS_BASE_POINTS * (BLOCKS_COMBO_GROWTH_BASE ** max(chain_size - 1, 0)))


def _initial_column_heights(
    occupied_cells: int,
    width: int,
    height: int,
    rng: random.Random | None = None,
) -> list[int]:
    rng = rng or random
    heights = [0] * width
    for _ in range(occupied_cells):
        candidates = [column for column, value in enumerate(heights) if value < height]
        column = rng.choice(candidates)
        heights[column] += 1
    return heights


def _build_initial_grid(
    occupied_indices: Sequence[int],
    *,
    width: int,
    height: int,
    rng: random.Random | None = None,
) -> list[int | None]:
    rng = rng or random
    heights = _initial_column_heights(len(occupied_indices), width, height, rng=rng)
    shuffled_indices = list(occupied_indices)
    rng.shuffle(shuffled_indices)
    next_grid: list[int | None] = [None] * (width * height)
    cursor = 0
    for col, height_count in enumerate(heights):
        for offset in range(height_count):
            row = height - 1 - offset
            next_grid[cell_index(row, col, width)] = shuffled_indices[cursor]
            cursor += 1
    return next_grid


def initialize_blocks_state(
    vocabulary_size: int,
    vocabulary_name: str,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    if vocabulary_size <= 0:
        raise ValueError("Vocabulary must contain at least one word.")

    rng = rng or random
    occupied_count = min(BLOCKS_TARGET_OCCUPIED_CELLS, vocabulary_size, BLOCKS_GRID_WIDTH * BLOCKS_GRID_HEIGHT)
    opening_indices = draw_unseen_indices(
        vocabulary_size=vocabulary_size,
        used_mask=empty_used_mask(),
        count=occupied_count,
        rng=rng,
    )
    grid_indices = _build_initial_grid(
        opening_indices,
        width=BLOCKS_GRID_WIDTH,
        height=BLOCKS_GRID_HEIGHT,
        rng=rng,
    )

    return {
        "mode_id": "blocks",
        "score": 0,
        "grid_width": BLOCKS_GRID_WIDTH,
        "grid_height": BLOCKS_GRID_HEIGHT,
        "grid_indices": grid_indices,
        "used_mask": add_indices_to_mask(empty_used_mask(), opening_indices),
        "turn_count": 0,
        "started_at_ms": int(time.time() * 1000),
        "ended_at_ms": None,
        "last_latency_ms": None,
        "last_provider": None,
        "used_fallback": False,
        "last_warning": None,
        "last_clue": None,
        "game_over": False,
        "game_result": None,
        "vocabulary_name": vocabulary_name,
        "target_occupied_cells": occupied_count,
        "last_primary_index": None,
        "last_primary_cell": None,
        "last_chain_indices": [],
        "last_chain_size": 0,
        "last_scored_cells": [],
    }


def resolve_blocks_turn(
    state: dict[str, Any],
    primary_cell: int,
    scored_cells: dict[int, int],
    vocabulary_size: int,
    rng: random.Random | None = None,
) -> BlocksTurnResolution:
    rng = rng or random
    width = int(state["grid_width"])
    height = int(state["grid_height"])
    current_grid = list(state["grid_indices"])
    primary_index = current_grid[primary_cell]
    if primary_index is None:
        raise ValueError("Primary cell must contain a word.")

    eligible_cells = {primary_cell}
    for cell, score in scored_cells.items():
        if score >= BLOCKS_COMBO_THRESHOLD and current_grid[cell] is not None:
            eligible_cells.add(cell)

    queue: list[int] = [primary_cell]
    chain_cells: list[int] = []
    visited: set[int] = {primary_cell}

    while queue:
        cell = queue.pop(0)
        chain_cells.append(cell)
        for neighbor in occupied_neighbors(current_grid, cell, width, height):
            if neighbor in visited or neighbor not in eligible_cells:
                continue
            visited.add(neighbor)
            queue.append(neighbor)

    removed_indices = [current_grid[cell] for cell in chain_cells if current_grid[cell] is not None]
    grid_after_removal = list(current_grid)
    for cell in chain_cells:
        grid_after_removal[cell] = None

    grid_after_gravity = apply_vertical_gravity(grid_after_removal, width, height)
    occupied_after_gravity = occupied_word_indices(grid_after_gravity)

    target_occupied = min(int(state["target_occupied_cells"]), width * height, vocabulary_size)
    missing_count = max(0, target_occupied - len(occupied_after_gravity))
    spawned_indices = draw_unseen_indices(
        vocabulary_size=vocabulary_size,
        used_mask=state["used_mask"],
        count=missing_count,
        rng=rng,
        exclude_indices=occupied_after_gravity,
    )
    updated_used_mask = add_indices_to_mask(state["used_mask"], spawned_indices)

    empty_cells = [cell for cell, value in enumerate(grid_after_gravity) if value is None]
    spawned_cells = empty_cells[: len(spawned_indices)]
    spawned_indices_by_cell = {
        cell: word_index for cell, word_index in zip(spawned_cells, spawned_indices)
    }
    next_grid = spawn_words_into_top_slots(grid_after_gravity, spawned_indices_by_cell)

    remaining_words = count_remaining_words(vocabulary_size, updated_used_mask)
    occupied_count = len(occupied_word_indices(next_grid))
    game_over = remaining_words == 0 and occupied_count == 0
    ended_at_ms = int(time.time() * 1000) if game_over else None
    score_gain = score_gain_for_chain(len(chain_cells))

    normalized_scored_cells = [
        {
            "cell": cell,
            "index": current_grid[cell],
            "score": score,
        }
        for cell, score in sorted(scored_cells.items())
        if current_grid[cell] is not None
    ]

    updated_state = {
        **state,
        "grid_indices": next_grid,
        "used_mask": updated_used_mask,
        "score": state["score"] + score_gain,
        "turn_count": state["turn_count"] + 1,
        "game_over": game_over,
        "game_result": "win" if game_over else None,
        "ended_at_ms": ended_at_ms,
        "last_primary_index": primary_index,
        "last_primary_cell": primary_cell,
        "last_chain_indices": removed_indices,
        "last_chain_size": len(chain_cells),
        "last_scored_cells": normalized_scored_cells,
    }

    return BlocksTurnResolution(
        state=updated_state,
        primary_cell=primary_cell,
        primary_index=primary_index,
        removed_cells=sorted(chain_cells),
        removed_indices=[index for index in removed_indices if index is not None],
        spawned_cells=spawned_cells,
        spawned_indices=spawned_indices,
        scored_cells=normalized_scored_cells,
        score_gain=score_gain,
    )
