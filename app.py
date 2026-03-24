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
from llm_client import build_ranker_from_env, format_startup_probe_message, normalize_word, run_startup_probe

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
DEFAULT_VOCAB_FILE = ASSETS_DIR / "aviation_1.txt"
CONFIGURED_VOCAB_FILE = Path(os.getenv("SEMANTRIS_VOCAB_FILE", str(DEFAULT_VOCAB_FILE)))
SELECTED_PACK_SESSION_KEY = "selected_pack_id"
ACTIVE_LLM_PROVIDER = os.getenv("SEMANTRIS_LLM_PROVIDER", "gemini").strip().lower()

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
RANKER = build_ranker_from_env(provider_name=ACTIVE_LLM_PROVIDER)


def selected_pack_id_from_session() -> str:
    pack_id = session.get(SELECTED_PACK_SESSION_KEY)
    if isinstance(pack_id, str) and pack_id in VOCABULARY_CATALOG:
        return pack_id

    return DEFAULT_VOCAB_PACK_ID


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


def serialize_state(state: dict[str, Any], pack: VocabularyPack) -> dict[str, Any]:
    board_words = words_for_indices(state["board_indices"], pack.words)
    target_index = state.get("target_index")
    target_word = pack.words[target_index] if target_index is not None else None
    remaining_words = count_remaining_words(pack.word_count, state["used_mask"])
    danger_zone_size = min(DESTRUCTION_ZONE_SIZE, len(board_words))

    return {
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
        "vocabulary_name": state["vocabulary_name"],
        "board_goal_size": min(calculate_board_size(state["score"]), pack.word_count),
        "danger_zone_size": danger_zone_size,
        "danger_zone_words": board_words[-danger_zone_size:],
        "remaining_words": remaining_words,
        "seen_words": pack.word_count - remaining_words,
        "total_vocabulary": pack.word_count,
        "run_exhausted": remaining_words == 0,
    }


def initialize_session(pack: VocabularyPack | None = None) -> dict[str, Any]:
    pack = pack or get_selected_pack()
    state = initialize_game_state(
        vocabulary_size=pack.word_count,
        vocabulary_name=pack.file_path.name,
    )
    session.clear()
    session[SELECTED_PACK_SESSION_KEY] = pack.pack_id
    session.update(state)
    session.modified = True
    return state


def current_state() -> dict[str, Any]:
    pack = get_selected_pack()
    if (
        "board_indices" not in session
        or session.get("vocabulary_name") != pack.file_path.name
    ):
        return initialize_session(pack)
    return dict(session)


@app.get("/")
def index() -> str:
    return render_template(
        "home.html",
        vocabulary_packs=vocabulary_pack_options(),
        selected_pack_id=selected_pack_id_from_session(),
    )


@app.get("/iteration-mode")
def iteration_mode() -> str:
    return render_template("arcade.html")


@app.post("/start-iteration-mode")
def start_iteration_mode() -> Any:
    pack_id = str(request.form.get("vocabulary_pack_id", "")).strip()
    pack = VOCABULARY_CATALOG.get(pack_id)
    if pack is None:
        return ("Unknown vocabulary pack.", 400)

    initialize_session(pack)
    return redirect(url_for("iteration_mode"))


@app.get("/play")
def play() -> Any:
    return redirect(url_for("iteration_mode"))


@app.get("/api/game/state")
def game_state() -> Any:
    state = current_state()
    pack = get_selected_pack()
    return jsonify({"state": serialize_state(state, pack)})


@app.post("/api/game/new")
def new_game() -> Any:
    pack = get_selected_pack()
    state = initialize_session(pack)
    return jsonify(
        {
            "message": "New run started.",
            "state": serialize_state(state, pack),
        }
    )


@app.post("/api/game/turn")
def game_turn() -> Any:
    state = current_state()
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
        "last_latency_ms": ranking.latency_ms,
        "last_provider": ranking.provider,
        "used_fallback": ranking.used_fallback,
        "last_warning": ranking.warning,
        "last_clue": clue,
    }

    session.clear()
    session[SELECTED_PACK_SESSION_KEY] = pack.pack_id
    session.update(updated_state)
    session.modified = True

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
            "target_word_before": board_words[board_indices.index(state["target_index"])],
            "state": serialize_state(updated_state, pack),
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
