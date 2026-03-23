from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session

from game_logic import (
    DESTRUCTION_ZONE_SIZE,
    calculate_board_size,
    count_remaining_words,
    initialize_game_state,
    resolve_turn,
)
from llm_client import build_ranker_from_env, normalize_word

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_VOCAB_FILE = BASE_DIR / "assets" / "general_1.txt"
VOCAB_FILE = Path(os.getenv("SEMANTRIS_VOCAB_FILE", str(DEFAULT_VOCAB_FILE)))

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


VOCABULARY = load_vocabulary(VOCAB_FILE)
RANKER = build_ranker_from_env()


def words_for_indices(indices: list[int]) -> list[str]:
    return [VOCABULARY[index] for index in indices]


def serialize_state(state: dict[str, Any]) -> dict[str, Any]:
    board_words = words_for_indices(state["board_indices"])
    target_index = state.get("target_index")
    target_word = VOCABULARY[target_index] if target_index is not None else None
    remaining_words = count_remaining_words(len(VOCABULARY), state["used_mask"])
    danger_zone_size = min(DESTRUCTION_ZONE_SIZE, len(board_words))

    return {
        "score": state["score"],
        "board": board_words,
        "target_word": target_word,
        "turn_count": state["turn_count"],
        "started_at_ms": state["started_at_ms"],
        "last_latency_ms": state.get("last_latency_ms"),
        "last_provider": state.get("last_provider"),
        "used_fallback": state.get("used_fallback", False),
        "last_warning": state.get("last_warning"),
        "last_clue": state.get("last_clue"),
        "game_over": state.get("game_over", False),
        "vocabulary_name": state["vocabulary_name"],
        "board_goal_size": min(calculate_board_size(state["score"]), len(VOCABULARY)),
        "danger_zone_size": danger_zone_size,
        "danger_zone_words": board_words[-danger_zone_size:],
        "remaining_words": remaining_words,
        "seen_words": len(VOCABULARY) - remaining_words,
        "total_vocabulary": len(VOCABULARY),
        "run_exhausted": remaining_words == 0,
    }


def initialize_session() -> dict[str, Any]:
    state = initialize_game_state(
        vocabulary_size=len(VOCABULARY),
        vocabulary_name=VOCAB_FILE.name,
    )
    session.clear()
    session.update(state)
    session.modified = True
    return state


def current_state() -> dict[str, Any]:
    if "board_indices" not in session:
        return initialize_session()
    return dict(session)


@app.get("/")
def index() -> str:
    return render_template("arcade.html")


@app.get("/api/game/state")
def game_state() -> Any:
    state = current_state()
    return jsonify({"state": serialize_state(state)})


@app.post("/api/game/new")
def new_game() -> Any:
    state = initialize_session()
    return jsonify(
        {
            "message": "New run started.",
            "state": serialize_state(state),
        }
    )


@app.post("/api/game/turn")
def game_turn() -> Any:
    state = current_state()
    if state.get("game_over"):
        return jsonify({"error": "This run is finished. Start a new game to play again."}), 400

    payload = request.get_json(silent=True) or {}
    clue = str(payload.get("clue", "")).strip()
    if not clue:
        return jsonify({"error": "Enter a clue before submitting."}), 400

    board_indices = state["board_indices"]
    board_words = words_for_indices(board_indices)
    board_lookup = {
        normalize_word(word): index
        for index, word in zip(board_indices, board_words)
    }

    ranking = RANKER.rank_words(clue, board_words)
    ranked_indices = [board_lookup[normalize_word(word)] for word in ranking.ranked_words]
    turn = resolve_turn(
        state=state,
        ranked_indices_most_to_least=ranked_indices,
        vocabulary_size=len(VOCABULARY),
    )

    updated_state = {
        **turn.state,
        "last_latency_ms": ranking.latency_ms,
        "last_provider": ranking.provider,
        "used_fallback": ranking.used_fallback,
        "last_warning": ranking.warning,
        "last_clue": clue,
    }

    session.clear()
    session.update(updated_state)
    session.modified = True

    return jsonify(
        {
            "message": _build_turn_message(turn.resolution, len(turn.words_removed_indices), updated_state),
            "resolution": turn.resolution,
            "ranked_board": words_for_indices(turn.ranked_board_indices),
            "new_board": words_for_indices(turn.new_board_indices),
            "words_removed": words_for_indices(turn.words_removed_indices),
            "spawned_words": words_for_indices(turn.spawned_indices),
            "target_word_before": board_words[board_indices.index(state["target_index"])],
            "state": serialize_state(updated_state),
        }
    )


def _build_turn_message(resolution: str, removed_count: int, state: dict[str, Any]) -> str:
    if state.get("game_over"):
        return "Run complete. You cleared the tower."
    if resolution == "hit":
        if state["used_mask"] and count_remaining_words(len(VOCABULARY), state["used_mask"]) == 0:
            return f"Hit. Removed {removed_count} word(s). Final stretch: no unseen words remain."
        return f"Hit. Removed {removed_count} word(s)."
    return "Miss. Tower reordered."


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "1") == "1"
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=debug_mode, port=port)
