from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from game_logic import (
    DESTRUCTION_ZONE_SIZE,
    calculate_board_size,
    count_remaining_words,
    initialize_game_state,
    resolve_turn,
)
from game_logic_blocks import (
    initialize_blocks_state,
    occupied_component_from,
    occupied_word_indices,
    resolve_blocks_turn,
    serialize_blocks_grid,
)
from game_logic_restriction import (
    RestrictionRule,
    initialize_restriction_state,
    load_restriction_rules,
    local_rule_supported,
    resolve_restriction_turn,
    validate_clue_locally,
)
from llm_client import build_ranker_from_env, format_startup_probe_message, normalize_word, run_startup_probe

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
DEFAULT_VOCAB_FILE = ASSETS_DIR / "aviation_1.txt"
RESTRICTION_RULES_FILE = ASSETS_DIR / "restriction_rules.json"
CONFIGURED_VOCAB_FILE = Path(os.getenv("SEMANTRIS_VOCAB_FILE", str(DEFAULT_VOCAB_FILE)))
SELECTED_PACK_SESSION_KEY = "selected_pack_id"
SELECTED_MODE_SESSION_KEY = "selected_mode_id"
ACTIVE_LLM_PROVIDER = os.getenv("SEMANTRIS_LLM_PROVIDER", "gemini").strip().lower()

MODE_IDS = {
    "iteration": "iteration",
    "restriction": "restriction",
    "blocks": "blocks",
}

MODE_PAGE_ENDPOINTS = {
    MODE_IDS["iteration"]: "iteration_mode",
    MODE_IDS["restriction"]: "restriction_mode",
    MODE_IDS["blocks"]: "blocks_mode",
}

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(24)


def load_vocabulary(vocab_file: Path) -> list[str]:
    if not vocab_file.exists():
        raise FileNotFoundError(f"Vocabulary file not found: {vocab_file}")

    deduped_words: list[str] = []
    seen: set[str] = set()

    with vocab_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            word = raw_line.strip()
            if not word:
                continue

            normalized = normalize_word(word)
            if normalized in seen:
                continue

            seen.add(normalized)
            deduped_words.append(word)

    if not deduped_words:
        raise ValueError(f"Vocabulary file is empty: {vocab_file}")

    return deduped_words


@dataclass(frozen=True)
class VocabularyPack:
    pack_id: str
    file_path: Path
    display_name: str
    words: tuple[str, ...]

    @property
    def word_count(self) -> int:
        return len(self.words)


def build_vocabulary_catalog(assets_dir: Path) -> dict[str, VocabularyPack]:
    catalog: dict[str, VocabularyPack] = {}

    for vocab_file in sorted(assets_dir.glob("*.txt")):
        pack_id = vocab_file.stem
        if pack_id in catalog:
            raise ValueError(f"Duplicate vocabulary pack id: {pack_id}")

        catalog[pack_id] = VocabularyPack(
            pack_id=pack_id,
            file_path=vocab_file,
            display_name=pack_id,
            words=tuple(load_vocabulary(vocab_file)),
        )

    if not catalog:
        raise ValueError(f"No vocabulary packs found in {assets_dir}")

    return catalog


def resolve_default_pack_id(catalog: dict[str, VocabularyPack]) -> str:
    configured_id = CONFIGURED_VOCAB_FILE.stem
    if configured_id in catalog:
        return configured_id

    default_id = DEFAULT_VOCAB_FILE.stem
    if default_id in catalog:
        return default_id

    return next(iter(catalog))


VOCABULARY_CATALOG = build_vocabulary_catalog(ASSETS_DIR)
DEFAULT_VOCAB_PACK_ID = resolve_default_pack_id(VOCABULARY_CATALOG)
RESTRICTION_RULES = load_restriction_rules(RESTRICTION_RULES_FILE)
RESTRICTION_RULES_BY_ID = {rule.rule_id: rule for rule in RESTRICTION_RULES}
RANKER = build_ranker_from_env(provider_name=ACTIVE_LLM_PROVIDER)


def selected_pack_id_from_session() -> str:
    pack_id = session.get(SELECTED_PACK_SESSION_KEY)
    if isinstance(pack_id, str) and pack_id in VOCABULARY_CATALOG:
        return pack_id

    return DEFAULT_VOCAB_PACK_ID


def selected_mode_id_from_session() -> str:
    mode_id = session.get(SELECTED_MODE_SESSION_KEY)
    if isinstance(mode_id, str) and mode_id in MODE_IDS.values():
        return mode_id
    return MODE_IDS["iteration"]


def get_selected_pack() -> VocabularyPack:
    return VOCABULARY_CATALOG[selected_pack_id_from_session()]


def vocabulary_pack_options() -> list[dict[str, Any]]:
    return [
        {
            "id": pack.pack_id,
            "display_name": pack.display_name,
            "word_count": pack.word_count,
        }
        for pack in VOCABULARY_CATALOG.values()
    ]


def words_for_indices(indices: list[int], vocabulary: tuple[str, ...]) -> list[str]:
    return [vocabulary[index] for index in indices]


def _game_result_for_state(state: dict[str, Any]) -> str | None:
    game_result = state.get("game_result")
    if isinstance(game_result, str):
        return game_result
    if state.get("game_over"):
        return "win"
    return None


def serialize_iteration_state(state: dict[str, Any], pack: VocabularyPack) -> dict[str, Any]:
    board_words = words_for_indices(state["board_indices"], pack.words)
    target_index = state.get("target_index")
    target_word = pack.words[target_index] if target_index is not None else None
    remaining_words = count_remaining_words(pack.word_count, state["used_mask"])
    danger_zone_size = min(DESTRUCTION_ZONE_SIZE, len(board_words))

    return {
        "mode_id": state.get("mode_id", MODE_IDS["iteration"]),
        "score": state["score"],
        "board": board_words,
        "target_word": target_word,
        "turn_count": state["turn_count"],
        "started_at_ms": state["started_at_ms"],
        "ended_at_ms": state.get("ended_at_ms"),
        "last_latency_ms": state.get("last_latency_ms"),
        "last_provider": state.get("last_provider"),
        "used_fallback": state.get("used_fallback", False),
        "last_warning": state.get("last_warning"),
        "last_clue": state.get("last_clue"),
        "game_over": state.get("game_over", False),
        "game_result": _game_result_for_state(state),
        "vocabulary_name": state["vocabulary_name"],
        "board_goal_size": min(calculate_board_size(state["score"]), pack.word_count),
        "danger_zone_size": danger_zone_size,
        "danger_zone_words": board_words[-danger_zone_size:],
        "remaining_words": remaining_words,
        "seen_words": pack.word_count - remaining_words,
        "total_vocabulary": pack.word_count,
        "run_exhausted": remaining_words == 0,
    }


def serialize_restriction_state(state: dict[str, Any], pack: VocabularyPack) -> dict[str, Any]:
    payload = serialize_iteration_state(state, pack)
    active_rule = RESTRICTION_RULES_BY_ID.get(str(state.get("active_rule_id", "")).strip())
    payload.update(
        {
            "mode_id": MODE_IDS["restriction"],
            "strike_count": state.get("strike_count", 0),
            "max_strikes": state.get("max_strikes", 0),
            "active_rule_id": state.get("active_rule_id"),
            "active_rule_name": active_rule.display_name if active_rule else "Unknown rule",
            "active_rule_description": active_rule.description if active_rule else "No rule loaded.",
            "last_rule_passed": state.get("last_rule_passed"),
            "last_rule_reason": state.get("last_rule_reason"),
        }
    )
    return payload


def serialize_blocks_state(state: dict[str, Any], pack: VocabularyPack) -> dict[str, Any]:
    remaining_words = count_remaining_words(pack.word_count, state["used_mask"])
    last_primary_index = state.get("last_primary_index")
    last_scored_cells = []
    for item in state.get("last_scored_cells", []):
        index = item.get("index")
        if index is None:
            continue
        last_scored_cells.append(
            {
                "cell": item.get("cell"),
                "word": pack.words[index],
                "score": item.get("score"),
            }
        )

    return {
        "mode_id": MODE_IDS["blocks"],
        "score": state["score"],
        "turn_count": state["turn_count"],
        "started_at_ms": state["started_at_ms"],
        "ended_at_ms": state.get("ended_at_ms"),
        "last_latency_ms": state.get("last_latency_ms"),
        "last_provider": state.get("last_provider"),
        "used_fallback": state.get("used_fallback", False),
        "last_warning": state.get("last_warning"),
        "last_clue": state.get("last_clue"),
        "game_over": state.get("game_over", False),
        "game_result": _game_result_for_state(state),
        "vocabulary_name": state["vocabulary_name"],
        "remaining_words": remaining_words,
        "seen_words": pack.word_count - remaining_words,
        "total_vocabulary": pack.word_count,
        "grid_width": state["grid_width"],
        "grid_height": state["grid_height"],
        "cells": serialize_blocks_grid(state["grid_indices"], pack.words, state["grid_width"]),
        "target_occupied_cells": state["target_occupied_cells"],
        "last_primary_word": pack.words[last_primary_index] if last_primary_index is not None else None,
        "last_primary_cell": state.get("last_primary_cell"),
        "last_chain_words": words_for_indices(list(state.get("last_chain_indices", [])), pack.words),
        "last_chain_size": state.get("last_chain_size", 0),
        "last_scored_cells": last_scored_cells,
    }


def _commit_session_state(pack: VocabularyPack, mode_id: str, state: dict[str, Any]) -> None:
    session.clear()
    session[SELECTED_PACK_SESSION_KEY] = pack.pack_id
    session[SELECTED_MODE_SESSION_KEY] = mode_id
    session.update(state)
    session.modified = True


def initialize_iteration_session(pack: VocabularyPack | None = None) -> dict[str, Any]:
    pack = pack or get_selected_pack()
    state = initialize_game_state(
        vocabulary_size=pack.word_count,
        vocabulary_name=pack.file_path.name,
    )
    state = {
        **state,
        "mode_id": MODE_IDS["iteration"],
        "game_result": None,
    }
    _commit_session_state(pack, MODE_IDS["iteration"], state)
    return state


def initialize_restriction_session(pack: VocabularyPack | None = None) -> dict[str, Any]:
    pack = pack or get_selected_pack()
    state = initialize_restriction_state(
        vocabulary_size=pack.word_count,
        vocabulary_name=pack.file_path.name,
        rules=RESTRICTION_RULES,
    )
    _commit_session_state(pack, MODE_IDS["restriction"], state)
    return state


def initialize_blocks_session(pack: VocabularyPack | None = None) -> dict[str, Any]:
    pack = pack or get_selected_pack()
    state = initialize_blocks_state(
        vocabulary_size=pack.word_count,
        vocabulary_name=pack.file_path.name,
    )
    _commit_session_state(pack, MODE_IDS["blocks"], state)
    return state


def initialize_session(pack: VocabularyPack | None = None) -> dict[str, Any]:
    return initialize_iteration_session(pack)


def _initialize_mode_session(mode_id: str, pack: VocabularyPack | None = None) -> dict[str, Any]:
    if mode_id == MODE_IDS["iteration"]:
        return initialize_iteration_session(pack)
    if mode_id == MODE_IDS["restriction"]:
        return initialize_restriction_session(pack)
    if mode_id == MODE_IDS["blocks"]:
        return initialize_blocks_session(pack)
    raise ValueError(f"Unsupported mode id: {mode_id}")


def _mode_state_matches(
    session_state: dict[str, Any],
    mode_id: str,
    pack: VocabularyPack,
) -> bool:
    if session_state.get(SELECTED_MODE_SESSION_KEY) != mode_id:
        return False
    if session_state.get("mode_id") != mode_id:
        return False
    if session_state.get("vocabulary_name") != pack.file_path.name:
        return False
    if mode_id in {MODE_IDS["iteration"], MODE_IDS["restriction"]}:
        return "board_indices" in session_state
    if mode_id == MODE_IDS["blocks"]:
        return "grid_indices" in session_state
    return False


def _current_mode_state(mode_id: str) -> dict[str, Any]:
    pack = get_selected_pack()
    session_state = dict(session)
    if not _mode_state_matches(session_state, mode_id, pack):
        return _initialize_mode_session(mode_id, pack)
    return session_state


def current_state() -> dict[str, Any]:
    return _current_mode_state(MODE_IDS["iteration"])


def current_iteration_state() -> dict[str, Any]:
    return _current_mode_state(MODE_IDS["iteration"])


def current_restriction_state() -> dict[str, Any]:
    return _current_mode_state(MODE_IDS["restriction"])


def current_blocks_state() -> dict[str, Any]:
    return _current_mode_state(MODE_IDS["blocks"])


def _selected_pack_from_form() -> VocabularyPack | None:
    pack_id = str(request.form.get("vocabulary_pack_id", "")).strip()
    return VOCABULARY_CATALOG.get(pack_id)


def _page_endpoint_for_mode(mode_id: str) -> str:
    return MODE_PAGE_ENDPOINTS.get(mode_id, MODE_PAGE_ENDPOINTS[MODE_IDS["iteration"]])


def _current_target_word(state: dict[str, Any], pack: VocabularyPack) -> str | None:
    target_index = state.get("target_index")
    if target_index is None:
        return None
    return pack.words[target_index]


def _combine_provider_labels(*providers: str | None) -> str | None:
    labels = [provider for provider in providers if provider]
    if not labels:
        return None
    if len(set(labels)) == 1:
        return labels[0]
    return "/".join(labels)


def _join_warnings(*warnings: str | None) -> str | None:
    parts = [warning for warning in warnings if warning]
    if not parts:
        return None
    return " ".join(parts)


@app.get("/")
def index() -> str:
    return render_template(
        "home.html",
        vocabulary_packs=vocabulary_pack_options(),
        selected_pack_id=selected_pack_id_from_session(),
        selected_mode_id=selected_mode_id_from_session(),
    )


@app.get("/iteration-mode")
def iteration_mode() -> str:
    return render_template("arcade.html")


@app.post("/start-iteration-mode")
def start_iteration_mode() -> Any:
    pack = _selected_pack_from_form()
    if pack is None:
        return ("Unknown vocabulary pack.", 400)

    initialize_iteration_session(pack)
    return redirect(url_for("iteration_mode"))


@app.get("/restriction-mode")
def restriction_mode() -> str:
    return render_template("restriction.html")


@app.post("/start-restriction-mode")
def start_restriction_mode() -> Any:
    pack = _selected_pack_from_form()
    if pack is None:
        return ("Unknown vocabulary pack.", 400)

    initialize_restriction_session(pack)
    return redirect(url_for("restriction_mode"))


@app.get("/blocks-mode")
def blocks_mode() -> str:
    return render_template("blocks.html")


@app.post("/start-blocks-mode")
def start_blocks_mode() -> Any:
    pack = _selected_pack_from_form()
    if pack is None:
        return ("Unknown vocabulary pack.", 400)

    initialize_blocks_session(pack)
    return redirect(url_for("blocks_mode"))


@app.get("/play")
def play() -> Any:
    return redirect(url_for(_page_endpoint_for_mode(selected_mode_id_from_session())))


@app.get("/api/game/state")
def game_state() -> Any:
    state = current_iteration_state()
    pack = get_selected_pack()
    return jsonify({"state": serialize_iteration_state(state, pack)})


@app.post("/api/game/new")
def new_game() -> Any:
    pack = get_selected_pack()
    state = initialize_iteration_session(pack)
    return jsonify(
        {
            "message": "New run started.",
            "state": serialize_iteration_state(state, pack),
        }
    )


@app.post("/api/game/turn")
def game_turn() -> Any:
    state = current_iteration_state()
    pack = get_selected_pack()
    if state.get("game_over"):
        return jsonify({"error": "This run is finished. Start a new game to play again."}), 400

    payload = request.get_json(silent=True) or {}
    clue = str(payload.get("clue", "")).strip()
    if not clue:
        return jsonify({"error": "Enter a clue before submitting."}), 400

    board_indices = state["board_indices"]
    board_words = words_for_indices(board_indices, pack.words)
    board_lookup = {
        normalize_word(word): index
        for index, word in zip(board_indices, board_words)
    }

    ranking = RANKER.rank_words(clue, board_words)
    ranked_indices = [board_lookup[normalize_word(word)] for word in ranking.ranked_words]
    turn = resolve_turn(
        state=state,
        ranked_indices_most_to_least=ranked_indices,
        vocabulary_size=pack.word_count,
    )

    updated_state = {
        **turn.state,
        "mode_id": MODE_IDS["iteration"],
        "last_latency_ms": ranking.latency_ms,
        "last_provider": ranking.provider,
        "used_fallback": ranking.used_fallback,
        "last_warning": ranking.warning,
        "last_clue": clue,
    }

    _commit_session_state(pack, MODE_IDS["iteration"], updated_state)

    return jsonify(
        {
            "message": _build_turn_message(
                turn.resolution,
                len(turn.words_removed_indices),
                updated_state,
                pack.word_count,
            ),
            "resolution": turn.resolution,
            "ranked_board": words_for_indices(turn.ranked_board_indices, pack.words),
            "new_board": words_for_indices(turn.new_board_indices, pack.words),
            "words_removed": words_for_indices(turn.words_removed_indices, pack.words),
            "spawned_words": words_for_indices(turn.spawned_indices, pack.words),
            "target_word_before": _current_target_word(state, pack),
            "state": serialize_iteration_state(updated_state, pack),
        }
    )


@app.get("/api/restriction/state")
def restriction_state() -> Any:
    state = current_restriction_state()
    pack = get_selected_pack()
    return jsonify({"state": serialize_restriction_state(state, pack)})


@app.post("/api/restriction/new")
def new_restriction_game() -> Any:
    pack = get_selected_pack()
    state = initialize_restriction_session(pack)
    return jsonify(
        {
            "message": "New restriction run started.",
            "state": serialize_restriction_state(state, pack),
        }
    )


def _active_rule_from_state(state: dict[str, Any]) -> RestrictionRule:
    rule_id = str(state.get("active_rule_id", "")).strip()
    rule = RESTRICTION_RULES_BY_ID.get(rule_id)
    if rule is None:
        raise ValueError(f"Unknown restriction rule id: {rule_id}")
    return rule


@app.post("/api/restriction/turn")
def restriction_turn() -> Any:
    state = current_restriction_state()
    pack = get_selected_pack()
    if state.get("game_over"):
        return jsonify({"error": "This run is finished. Start a new game to play again."}), 400

    payload = request.get_json(silent=True) or {}
    clue = str(payload.get("clue", "")).strip()
    if not clue:
        return jsonify({"error": "Enter a clue before submitting."}), 400

    rule = _active_rule_from_state(state)
    board_indices = state["board_indices"]
    board_words = words_for_indices(board_indices, pack.words)
    board_lookup = {
        normalize_word(word): index
        for index, word in zip(board_indices, board_words)
    }
    target_word_before = _current_target_word(state, pack)

    if local_rule_supported(rule):
        rule_passed, rule_reason = validate_clue_locally(rule, clue)
        if rule_passed:
            ranking = RANKER.rank_words(clue, board_words)
            ranked_indices = [board_lookup[normalize_word(word)] for word in ranking.ranked_words]
            turn = resolve_restriction_turn(
                state=state,
                rule=rule,
                rule_passed=True,
                rule_reason=rule_reason,
                ranked_indices_most_to_least=ranked_indices,
                vocabulary_size=pack.word_count,
                allow_bonus=True,
                rules=RESTRICTION_RULES,
            )
            updated_state = {
                **turn.state,
                "last_latency_ms": ranking.latency_ms,
                "last_provider": ranking.provider,
                "used_fallback": ranking.used_fallback,
                "last_warning": ranking.warning,
                "last_clue": clue,
            }
        else:
            turn = resolve_restriction_turn(
                state=state,
                rule=rule,
                rule_passed=False,
                rule_reason=rule_reason,
                ranked_indices_most_to_least=None,
                vocabulary_size=pack.word_count,
                allow_bonus=False,
                rules=RESTRICTION_RULES,
            )
            updated_state = {
                **turn.state,
                "last_latency_ms": 0,
                "last_provider": "local-rule-validator",
                "used_fallback": False,
                "last_warning": None,
                "last_clue": clue,
            }
    else:
        judgment = RANKER.judge_restricted_clue(rule.description, clue, board_words)
        ranked_indices = None
        if judgment.ranked_words is not None:
            ranked_indices = [board_lookup[normalize_word(word)] for word in judgment.ranked_words]

        turn = resolve_restriction_turn(
            state=state,
            rule=rule,
            rule_passed=judgment.rule_passed,
            rule_reason=judgment.short_reason,
            ranked_indices_most_to_least=ranked_indices,
            vocabulary_size=pack.word_count,
            allow_bonus=judgment.rule_passed and not judgment.used_fallback,
            rules=RESTRICTION_RULES,
        )
        updated_state = {
            **turn.state,
            "last_latency_ms": judgment.latency_ms,
            "last_provider": judgment.provider,
            "used_fallback": judgment.used_fallback,
            "last_warning": judgment.warning,
            "last_clue": clue,
        }

    _commit_session_state(pack, MODE_IDS["restriction"], updated_state)

    return jsonify(
        {
            "message": _build_restriction_turn_message(turn, updated_state, pack.word_count),
            "resolution": turn.resolution,
            "rule_passed": bool(updated_state.get("last_rule_passed")),
            "rule_reason": updated_state.get("last_rule_reason"),
            "strike_delta": updated_state.get("strike_count", 0) - state.get("strike_count", 0),
            "bonus_multiplier_applied": turn.bonus_multiplier_applied,
            "ranked_board": (
                words_for_indices(turn.ranked_board_indices, pack.words)
                if turn.ranked_board_indices is not None
                else None
            ),
            "new_board": words_for_indices(turn.new_board_indices, pack.words),
            "words_removed": words_for_indices(turn.words_removed_indices, pack.words),
            "spawned_words": words_for_indices(turn.spawned_indices, pack.words),
            "penalty_words": words_for_indices(turn.penalty_indices, pack.words),
            "target_word_before": target_word_before,
            "state": serialize_restriction_state(updated_state, pack),
        }
    )


@app.get("/api/blocks/state")
def blocks_state() -> Any:
    state = current_blocks_state()
    pack = get_selected_pack()
    return jsonify({"state": serialize_blocks_state(state, pack)})


@app.post("/api/blocks/new")
def new_blocks_game() -> Any:
    pack = get_selected_pack()
    state = initialize_blocks_session(pack)
    return jsonify(
        {
            "message": "New blocks run started.",
            "state": serialize_blocks_state(state, pack),
        }
    )


@app.post("/api/blocks/turn")
def blocks_turn() -> Any:
    state = current_blocks_state()
    pack = get_selected_pack()
    if state.get("game_over"):
        return jsonify({"error": "This run is finished. Start a new game to play again."}), 400

    payload = request.get_json(silent=True) or {}
    clue = str(payload.get("clue", "")).strip()
    if not clue:
        return jsonify({"error": "Enter a clue before submitting."}), 400

    occupied_indices = occupied_word_indices(state["grid_indices"])
    if not occupied_indices:
        return jsonify({"error": "The grid is empty. Start a new game to play again."}), 400

    occupied_words = words_for_indices(occupied_indices, pack.words)
    cell_lookup = {
        normalize_word(pack.words[word_index]): cell
        for cell, word_index in enumerate(state["grid_indices"])
        if word_index is not None
    }

    ranking = RANKER.rank_words(clue, occupied_words)
    primary_word = ranking.ranked_words[0]
    primary_cell = cell_lookup[normalize_word(primary_word)]

    component_cells = occupied_component_from(
        state["grid_indices"],
        primary_cell,
        state["grid_width"],
        state["grid_height"],
    )
    component_words = [
        pack.words[state["grid_indices"][cell]]
        for cell in component_cells
        if state["grid_indices"][cell] is not None
    ]
    scoring = RANKER.score_words_against_clue(clue, component_words)
    component_lookup = {
        normalize_word(pack.words[state["grid_indices"][cell]]): cell
        for cell in component_cells
        if state["grid_indices"][cell] is not None
    }
    scored_cells = {
        component_lookup[normalize_word(item.word)]: item.score
        for item in scoring.scored_words
    }

    turn = resolve_blocks_turn(
        state=state,
        primary_cell=primary_cell,
        scored_cells=scored_cells,
        vocabulary_size=pack.word_count,
    )

    updated_state = {
        **turn.state,
        "last_latency_ms": ranking.latency_ms + scoring.latency_ms,
        "last_provider": _combine_provider_labels(ranking.provider, scoring.provider),
        "used_fallback": ranking.used_fallback or scoring.used_fallback,
        "last_warning": _join_warnings(ranking.warning, scoring.warning),
        "last_clue": clue,
    }

    _commit_session_state(pack, MODE_IDS["blocks"], updated_state)

    return jsonify(
        {
            "message": _build_blocks_turn_message(turn),
            "resolution": "chain",
            "primary_word": pack.words[turn.primary_index],
            "primary_cell": turn.primary_cell,
            "scored_cells": [
                {
                    "cell": item["cell"],
                    "word": pack.words[item["index"]],
                    "score": item["score"],
                }
                for item in turn.scored_cells
            ],
            "removed_words": words_for_indices(turn.removed_indices, pack.words),
            "removed_cells": turn.removed_cells,
            "spawned_words": words_for_indices(turn.spawned_indices, pack.words),
            "spawned_cells": turn.spawned_cells,
            "state": serialize_blocks_state(updated_state, pack),
        }
    )


def _build_turn_message(
    resolution: str,
    removed_count: int,
    state: dict[str, Any],
    vocabulary_size: int,
) -> str:
    if state.get("game_over"):
        return "Run complete. You cleared the tower."
    if resolution == "hit":
        if state["used_mask"] and count_remaining_words(vocabulary_size, state["used_mask"]) == 0:
            return f"Hit. Removed {removed_count} word(s). Final stretch: no unseen words remain."
        return f"Hit. Removed {removed_count} word(s)."
    return "Miss. Tower reordered."


def _build_restriction_turn_message(
    turn: Any,
    state: dict[str, Any],
    vocabulary_size: int,
) -> str:
    if turn.resolution == "rule_fail":
        strike_count = state.get("strike_count", 0)
        max_strikes = state.get("max_strikes", 0)
        if state.get("game_over"):
            return f"Rule failed. Strike {strike_count} of {max_strikes}. Run over."
        return f"Rule failed. Strike {strike_count} of {max_strikes}."

    if state.get("game_over") and _game_result_for_state(state) == "win":
        return "Rule passed. Run complete. You cleared the tower."

    if turn.resolution == "hit":
        removed_count = len(turn.words_removed_indices)
        bonus_suffix = ""
        if turn.bonus_multiplier_applied > 1.0:
            bonus_suffix = f" with a {turn.bonus_multiplier_applied:g}x bonus"
        if state["used_mask"] and count_remaining_words(vocabulary_size, state["used_mask"]) == 0:
            return (
                f"Rule passed. Hit. Removed {removed_count} word(s){bonus_suffix}. "
                "Final stretch: no unseen words remain."
            )
        return f"Rule passed. Hit. Removed {removed_count} word(s){bonus_suffix}."

    return "Rule passed. Miss. Tower reordered."


def _build_blocks_turn_message(turn: Any) -> str:
    removed_count = len(turn.removed_indices)
    suffix = "word" if removed_count == 1 else "words"
    return f"Chain cleared {removed_count} {suffix} for {turn.score_gain} points."


def should_run_startup_probe(debug_mode: bool) -> bool:
    if os.getenv("SEMANTRIS_SKIP_LLM_STARTUP_PROBE", "0") == "1":
        return False

    if not debug_mode:
        return True

    return os.getenv("WERKZEUG_RUN_MAIN") == "true"


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "1") == "1"
    port = int(os.getenv("PORT", "5001"))

    if should_run_startup_probe(debug_mode):
        print(format_startup_probe_message(run_startup_probe(RANKER)), flush=True)

    app.run(debug=debug_mode, port=port)
