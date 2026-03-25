# 2 New Modes Technical Brief

## Short answer

Yes. Both proposed modes are implementable in this codebase.

- `Blocks Mode` is feasible, but it should be implemented as a separate game loop and UI, not as a small extension of the current tower resolver.
- `Thematic Restriction Mode` is feasible and is best implemented as a variation of the current iteration/tower mode with an extra clue-validation step and a rule catalog.

This brief is detailed enough for a contractor or another AI to implement from. It names the files to edit, the new files to add, the data contracts to introduce, the algorithms to use, and the verification steps to run.

## Important reality check

The current game is a single-mode system centered on one assumption:

- there is one vertical board
- there is one target word
- one LLM call returns a full ranking
- `resolve_turn()` decides hit or miss from that ranking

That fits `Iteration Mode`, but it does **not** directly fit either of the new ideas:

- `Blocks Mode` has no single persistent target and needs a 2D grid, gravity, flood-fill, and combo scoring.
- `Restriction Mode` still uses the tower, but it introduces rule judgment, strikes, rule rotation, and possibly failure states.

So the correct answer is:

- yes, both modes can be added
- no, they should not be hacked into the current `resolve_turn()` path as conditionals

The safest implementation path is to keep `Iteration Mode` working as-is and add two parallel mode implementations beside it.

## Recommended implementation strategy

Use three separate mode flows:

1. `Iteration Mode`
2. `Restriction Mode`
3. `Blocks Mode`

Do **not** try to force all three through a single frontend controller or a single backend resolver on the first pass.

Recommended principle:

- keep `Iteration Mode` stable
- reuse shared helpers where it is cheap
- isolate new logic per mode so contractors can work without breaking the existing playable mode

## Existing codebase map

The current implementation splits cleanly into these layers:

- `app.py`
  Flask routes, session setup, API responses, serialization
- `game_logic.py`
  current iteration/tower rules
- `llm_client.py`
  provider prompts, parsing, validation, fallback behavior
- `templates/home.html`
  landing page and mode entry
- `templates/arcade.html`
  iteration-mode page shell
- `frontend/src/*`
  TypeScript frontend for the iteration board
- `tests/test_app.py`
  Flask route coverage
- `tests/test_game_logic.py`
  core game-logic coverage
- `tests/test_llm_client.py`
  LLM contract and fallback coverage

That structure is good enough to support the two new modes without a rewrite.

## High-level architecture changes

### 1. Add mode-specific backend logic files

Add:

- `game_logic_blocks.py`
- `game_logic_restriction.py`

Keep `game_logic.py` for current iteration mode.

### 2. Add mode-specific templates

Add:

- `templates/restriction.html`
- `templates/blocks.html`

Keep `templates/arcade.html` for current iteration mode.

### 3. Add mode-specific frontend entry points

Add:

- `frontend/src/restriction.ts`
- `frontend/src/restriction_controller.ts`
- `frontend/src/restriction_api.ts`
- `frontend/src/restriction_dom.ts`
- `frontend/src/restriction_types.ts`
- `frontend/src/blocks.ts`
- `frontend/src/blocks_controller.ts`
- `frontend/src/blocks_api.ts`
- `frontend/src/blocks_dom.ts`
- `frontend/src/blocks_types.ts`
- `frontend/src/blocks_board.ts`
- `frontend/src/blocks_animations.ts`

Do not overload the existing `frontend/src/controller.ts` with both new modes. It is currently clean because it only thinks in terms of the current tower mode.

### 4. Add a rule catalog for restriction mode

Add:

- `assets/restriction_rules.json`

Use JSON, not free-form text, so rules are machine-readable and deterministic where possible.

### 5. Expand the frontend build

Edit:

- `scripts/build-frontend.mjs`

Add new bundle entry points:

- `restriction: "frontend/src/restriction.ts"`
- `blocks: "frontend/src/blocks.ts"`

No change is needed to the existing `game` and `theme` entries beyond keeping them intact.

### 6. Expand home-page mode selection

Edit:

- `templates/home.html`

Add entry cards/buttons/forms for:

- Restriction Mode
- Blocks Mode

Each start form should submit:

- selected vocabulary pack
- selected mode

## Cross-cutting backend changes

## `app.py`

### What to keep

Keep these existing responsibilities:

- vocabulary loading
- catalog building
- selected vocabulary pack handling
- LLM provider bootstrap

### What to add

Add a mode registry near the top of the file:

```python
SELECTED_MODE_SESSION_KEY = "selected_mode_id"

MODE_IDS = {
    "iteration": "iteration",
    "restriction": "restriction",
    "blocks": "blocks",
}
```

Add helper functions:

- `selected_mode_id_from_session()`
- `set_selected_mode(mode_id: str)`
- `initialize_iteration_session(pack: VocabularyPack)`
- `initialize_restriction_session(pack: VocabularyPack)`
- `initialize_blocks_session(pack: VocabularyPack)`

Recommended behavior:

- starting a mode clears any existing run in the session
- the chosen pack remains explicit in session
- the chosen mode remains explicit in session

### New routes to add

Add page routes:

- `GET /restriction-mode`
- `POST /start-restriction-mode`
- `GET /blocks-mode`
- `POST /start-blocks-mode`

Keep the existing:

- `GET /iteration-mode`
- `POST /start-iteration-mode`

### New API routes to add

Add separate API namespaces instead of cramming mode branches into the existing endpoints:

- `GET /api/restriction/state`
- `POST /api/restriction/new`
- `POST /api/restriction/turn`
- `GET /api/blocks/state`
- `POST /api/blocks/new`
- `POST /api/blocks/turn`

This is the least risky approach because:

- current iteration endpoints stay untouched
- frontend payload types stay simpler
- each mode can evolve independently

### Serialization changes

Add new serializer functions instead of bloating `serialize_state()`:

- `serialize_iteration_state()`
- `serialize_restriction_state()`
- `serialize_blocks_state()`

Keep the current `serialize_state()` as either:

- a thin dispatcher, or
- iteration-only logic renamed to `serialize_iteration_state()`

## `llm_client.py`

This file needs the biggest shared change because both new modes need more than plain ranking.

### Current limitation

Right now the public surface is effectively:

- `rank_words(clue, words) -> RankingResult`

That is enough for iteration mode only.

### New public capabilities to add

Add these result models:

```python
@dataclass
class RuleJudgeResult:
    rule_passed: bool
    short_reason: str
    ranked_words: list[str] | None
    latency_ms: int
    provider: str
    used_fallback: bool
    warning: str | None = None

@dataclass
class WordScore:
    word: str
    score: int

@dataclass
class WordScoringResult:
    scored_words: list[WordScore]
    latency_ms: int
    provider: str
    used_fallback: bool
    warning: str | None = None
```

Add these Pydantic payloads:

```python
class RestrictedRankingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_passed: bool
    short_reason: str
    ranked_words: list[str] | None = None

class WordScoreItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    word: str
    score: int

class WordScoringPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scored_words: list[WordScoreItemPayload]
```

### New provider methods

Extend both provider classes and the resilient wrapper with:

- `judge_restricted_clue(rule_text, clue, words) -> RuleJudgeResult`
- `score_words_against_clue(clue, words) -> WordScoringResult`

### Prompting guidance

Do **not** implement this with hidden chain-of-thought requirements.

Use a short, user-displayable justification field:

- `short_reason`

For restriction mode, request JSON like:

```json
{
  "rule_passed": true,
  "short_reason": "The clue is a fictional character name and satisfies the active rule.",
  "ranked_words": ["mafia", "family", "italy", "business", "apple"]
}
```

For blocks local scoring, request JSON like:

```json
{
  "scored_words": [
    { "word": "ocean", "score": 91 },
    { "word": "boat", "score": 84 },
    { "word": "anchor", "score": 77 },
    { "word": "forest", "score": 18 }
  ]
}
```

### Validation rules to enforce

Add strict validators:

- restriction ranking must either return `ranked_words=None` when `rule_passed=False` or a valid full permutation when `rule_passed=True`
- word scoring must return every expected word exactly once
- scores must be clamped or rejected unless they are integers in `0..100`

### Fallback behavior

This is important.

#### Restriction mode fallback

Not every rule can be judged locally.

Implement two fallback paths:

1. Deterministic local validation for typed rules where possible
2. Safe degradation when the model is unavailable

For example:

- `forbidden_initials` can be validated locally
- `max_words` can be validated locally
- `regex_match` can be validated locally
- `pop_culture_entity` probably cannot be validated reliably locally
- `antonym_target` cannot be validated reliably locally

For rules that do **not** have a trustworthy local validator:

- if the provider fails, let the clue proceed as a normal ranked turn
- do **not** apply the bonus multiplier
- attach a warning in the response

This prevents the game from becoming unfair or unplayable during provider outages.

#### Blocks mode fallback

If primary provider scoring fails:

- choose the primary word with the existing heuristic ranker
- compute local scores with a normalized heuristic derived from token overlap plus string similarity
- map heuristic values into `0..100`

This keeps the mode playable offline.

## Restriction Mode

## Feasibility verdict

Yes. This mode is a straightforward extension of the current tower mode.

The correct design is:

- keep the existing tower board
- keep the target-word goal
- add a rule banner
- validate the clue before applying ranking
- apply bonus/penalty behavior based on the judge result

## Recommended gameplay design

Use these defaults:

- rule rotates every `10` turns
- maximum strikes: `3`
- bonus multiplier on a passed rule: `2.0`
- failed rule does not rank the board
- failed rule increments `strike_count`
- failed rule inserts one penalty word at the **bottom** of the tower

Why bottom insertion:

- in this game, the destruction zone is at the bottom
- inserting a word at the bottom pushes every current word one slot farther from the destruction zone
- this is the cleanest analog to the pitch's "tower pushes up faster"

Do **not** try to literally add a real-time rising-timer mechanic in the first implementation. That is a larger redesign than the rest of the mode requires.

## Restriction rule catalog

Add:

- `assets/restriction_rules.json`

Recommended schema:

```json
[
  {
    "id": "taboo_initials_str",
    "display_name": "Taboo Initials",
    "description": "Do not use clue words starting with S, T, or R.",
    "kind": "forbidden_initials",
    "params": { "letters": ["s", "t", "r"] },
    "bonus_multiplier": 2.0,
    "penalty_bottom_inserts": 1,
    "local_validator": true
  },
  {
    "id": "pop_culture_only",
    "display_name": "Pop Culture Only",
    "description": "The clue must be a real celebrity or fictional character.",
    "kind": "semantic_entity_class",
    "params": { "allowed_classes": ["celebrity", "fictional_character"] },
    "bonus_multiplier": 2.5,
    "penalty_bottom_inserts": 1,
    "local_validator": false
  }
]
```

Do not store only plain-English rules. The code needs:

- stable `id`
- `kind`
- `params`
- multiplier
- penalty strength
- whether a local validator exists

## Restriction mode state shape

Implement a dedicated state initializer in `game_logic_restriction.py`.

Recommended state keys:

```python
{
    "mode_id": "restriction",
    "score": 0,
    "board_indices": [...],
    "target_index": 12,
    "used_mask": "...",
    "turn_count": 0,
    "started_at_ms": 0,
    "ended_at_ms": None,
    "last_latency_ms": None,
    "last_provider": None,
    "used_fallback": False,
    "last_warning": None,
    "last_clue": None,
    "game_over": False,
    "game_result": None,
    "vocabulary_name": "aviation_1.txt",
    "strike_count": 0,
    "max_strikes": 3,
    "active_rule_id": "taboo_initials_str",
    "active_rule_started_turn": 0,
    "last_rule_passed": None,
    "last_rule_reason": None,
}
```

Add a helper to rotate rules:

- `maybe_rotate_rule(state, rules, rng)`

Rotation logic:

- pick a rule at game start
- rotate when `turn_count > 0 and turn_count % RULE_ROTATION_INTERVAL == 0`
- avoid immediately repeating the same rule if the catalog has more than one rule

## Restriction mode resolver

Add `resolve_restriction_turn()` in `game_logic_restriction.py`.

It should:

1. validate or judge the clue against the active rule
2. if rule fails:
   - increment strikes
   - apply bottom insertion penalty
   - increment turn count
   - set `last_rule_passed=False`
   - set `last_rule_reason`
   - check if `strike_count >= max_strikes`
3. if rule passes:
   - rank as normal
   - call iteration resolver
   - replace base score gain with `round(removed_count * bonus_multiplier)`
   - set `last_rule_passed=True`
   - set `last_rule_reason`
4. rotate rule if needed after the turn resolves

### Bottom insertion penalty

Add a helper:

- `insert_penalty_words_at_bottom(state, vocabulary_size, count, rng)`

Behavior:

- draw unseen words when available
- if unseen words are exhausted, recycle from the vocabulary words not currently on the board
- append penalty words so they become the new bottom-most words
- keep board size capped at `MAX_BOARD_SIZE` by trimming from the top if necessary

Trimming from the top is correct because:

- the bottom is the scoring zone
- a penalty should remove safety margin from the top

If the target word is trimmed out, the run should end as a loss:

- `game_over=True`
- `game_result="loss"`
- `ended_at_ms=now`

## Restriction mode serialization

Add `serialize_restriction_state()` in `app.py`.

Include all existing iteration fields plus:

- `mode_id`
- `game_result`
- `strike_count`
- `max_strikes`
- `active_rule_id`
- `active_rule_name`
- `active_rule_description`
- `last_rule_passed`
- `last_rule_reason`

## Restriction mode API response shape

Use:

```json
{
  "message": "Rule passed. Hit. Removed 2 word(s) with a 2x bonus.",
  "resolution": "hit",
  "rule_passed": true,
  "rule_reason": "The clue meets the active rule.",
  "strike_delta": 0,
  "ranked_board": ["..."],
  "new_board": ["..."],
  "words_removed": ["..."],
  "spawned_words": ["..."],
  "penalty_words": [],
  "target_word_before": "airport",
  "state": { "...": "..." }
}
```

For a failed rule:

```json
{
  "message": "Rule failed. Strike 2 of 3.",
  "resolution": "rule_fail",
  "rule_passed": false,
  "rule_reason": "The clue starts with a forbidden letter.",
  "strike_delta": 1,
  "ranked_board": null,
  "new_board": ["..."],
  "words_removed": [],
  "spawned_words": [],
  "penalty_words": ["storm"],
  "target_word_before": "airport",
  "state": { "...": "..." }
}
```

## Restriction mode frontend changes

Add:

- `templates/restriction.html`

This can largely copy `templates/arcade.html`, but add:

- active rule banner
- strike meter
- rule-result explanation line

Suggested new element ids:

- `active-rule-name`
- `active-rule-description`
- `strike-value`
- `rule-result-value`

Add new frontend files:

- `frontend/src/restriction_types.ts`
- `frontend/src/restriction_dom.ts`
- `frontend/src/restriction_api.ts`
- `frontend/src/restriction_controller.ts`
- `frontend/src/restriction.ts`

### `restriction_types.ts`

Define:

- `RestrictionState`
- `RestrictionStateResponse`
- `RestrictionTurnResponse`

Keep them separate from `frontend/src/types.ts` to avoid muddying the current iteration types.

### `restriction_dom.ts`

Mirror `frontend/src/dom.ts`, but add the rule and strike elements.

### `restriction_api.ts`

Mirror `frontend/src/api.ts`, but call:

- `/api/restriction/state`
- `/api/restriction/new`
- `/api/restriction/turn`

### `restriction_controller.ts`

Reuse these existing ideas from the iteration controller:

- load state
- submit clue
- animate hit/miss
- update HUD

Add new branches:

- if `resolution === "rule_fail"`, skip reorder animation
- animate penalty-word insertion at the bottom
- update strike meter immediately

### CSS changes

Edit:

- `static/css/app.css`

Add styles for:

- rule banner
- strike pills
- rule-pass and rule-fail status states

## Restriction mode tests

Add Python tests:

- `tests/test_game_logic_restriction.py`
- extend `tests/test_app.py`
- extend `tests/test_llm_client.py`

Required backend test cases:

- local validator rejects forbidden initials
- model-judged rule returns pass and ranking
- model-judged rule returns fail and no ranking
- failed rule increments strike count
- failed rule inserts bottom penalty word
- third strike ends run with `game_result="loss"`
- rule rotates on turn `10`
- provider failure on non-local rule degrades safely to normal ranking with warning and no bonus

Add frontend tests:

- `frontend/src/__tests__/restriction_dom.test.ts`
- `frontend/src/__tests__/restriction_controller.test.ts`

Required frontend test cases:

- rule banner renders from state payload
- strike display updates after failed rule
- rule-fail response does not try to run reorder animation
- successful rule hit shows bonus-oriented message

## Blocks Mode

## Feasibility verdict

Yes, but this is a new game mode, not a toggle on the current one.

It requires:

- 2D board state
- grid rendering
- gravity
- flood-fill chain logic
- combo scoring
- a different API contract

## One necessary design clarification

The concept note suggests:

1. rank the whole board to find the epicenter
2. grab all contiguous blocks
3. score that cluster

That is close, but it needs one implementation tweak:

- if the board is densely filled, the connected occupied component can become very large

The correct implementation is:

1. rank all occupied words to find the primary word
2. find the occupied connected component containing that primary cell
3. score every word in that component once against the clue
4. run BFS starting from the primary cell through only cells whose score is above the combo threshold

That preserves chain semantics while keeping LLM usage bounded.

## Recommended gameplay design

Use these defaults:

- grid width: `8`
- grid height: `10`
- target occupied cells: `32`
- combo threshold: `75`
- base points: `10`
- combo growth base: `2.5`

Score formula:

```python
score_gain = round(10 * (2.5 ** max(chain_size - 1, 0)))
```

That produces:

- 1 pop -> 10
- 2 pop -> 25
- 3 pop -> 62
- 4 pop -> 156
- 5 pop -> 391
- 6 pop -> 977

That is close to the intended "1 block is small, 6-block chain is huge" feel.

### Why use only 32 occupied cells in an 8x10 grid

This is the best compromise for v1:

- visually still feels like a real well/grid
- keeps global LLM ranking calls near current scale
- prevents the first implementation from requiring 80-word ranking every turn
- makes connected components smaller and more interesting

If the team later wants a denser board, raise the occupied-cell target after the mode works.

## Blocks mode state shape

Add `initialize_blocks_state()` in `game_logic_blocks.py`.

Recommended state keys:

```python
{
    "mode_id": "blocks",
    "score": 0,
    "grid_width": 8,
    "grid_height": 10,
    "grid_indices": [None, None, 14, ...],  # row-major, length = width * height
    "used_mask": "...",
    "turn_count": 0,
    "started_at_ms": 0,
    "ended_at_ms": None,
    "last_latency_ms": None,
    "last_provider": None,
    "used_fallback": False,
    "last_warning": None,
    "last_clue": None,
    "game_over": False,
    "game_result": None,
    "vocabulary_name": "aviation_1.txt",
    "target_occupied_cells": 32,
    "last_primary_word": None,
    "last_primary_cell": None,
    "last_chain_words": [],
    "last_chain_size": 0,
    "last_scored_cells": [],
}
```

## Blocks mode helper functions

Implement these in `game_logic_blocks.py`:

- `cell_index(row, col, width) -> int`
- `row_col(index, width) -> tuple[int, int]`
- `occupied_neighbors(grid_indices, cell, width, height) -> list[int]`
- `occupied_component_from(grid_indices, start_cell, width, height) -> list[int]`
- `apply_vertical_gravity(grid_indices, width, height) -> list[int | None]`
- `spawn_words_into_top_slots(grid_indices, width, height, spawned_indices_by_cell) -> list[int | None]`
- `occupied_word_indices(grid_indices) -> list[int]`
- `serialize_blocks_grid(grid_indices, vocabulary) -> list[dict[str, Any]]`

## Blocks mode turn algorithm

Implement `resolve_blocks_turn()` in `game_logic_blocks.py`.

Detailed algorithm:

1. Read all occupied cells from `grid_indices`
2. Convert occupied word indices into `board_words`
3. Call `RANKER.rank_words(clue, board_words)`
4. Take the first ranked word as the `primary_word`
5. Locate its cell in the grid
6. Find the occupied connected component containing that cell
7. Ask `score_words_against_clue(clue, component_words)`
8. Mark a cell as `eligible` if:
   - it is the primary cell, or
   - its score is `>= BLOCKS_COMBO_THRESHOLD`
9. Run BFS from the primary cell through only eligible cells
10. Remove every reached cell
11. Apply vertical gravity
12. Spawn new unseen words into top empty slots until:
   - occupied count returns to `target_occupied_cells`, or
   - no unseen words remain
13. Compute score gain from chain size
14. End the run only when:
   - no unseen words remain, and
   - the grid is empty

This keeps the mode relaxed and puzzle-like, which fits the concept note.

## Blocks mode serialization

Add `serialize_blocks_state()` in `app.py`.

Return:

```json
{
  "mode_id": "blocks",
  "score": 120,
  "turn_count": 6,
  "started_at_ms": 0,
  "ended_at_ms": null,
  "last_latency_ms": 410,
  "last_provider": "gemini",
  "used_fallback": false,
  "last_warning": null,
  "last_clue": "ocean",
  "game_over": false,
  "game_result": null,
  "vocabulary_name": "aviation_1.txt",
  "remaining_words": 240,
  "seen_words": 32,
  "total_vocabulary": 272,
  "grid_width": 8,
  "grid_height": 10,
  "cells": [
    { "cell": 0, "row": 0, "col": 0, "word": null },
    { "cell": 1, "row": 0, "col": 1, "word": null },
    { "cell": 2, "row": 0, "col": 2, "word": "Anchor" }
  ],
  "target_occupied_cells": 32,
  "last_primary_word": "Anchor",
  "last_chain_words": ["Anchor", "Harbor", "Dock"],
  "last_chain_size": 3
}
```

## Blocks mode API response shape

Use:

```json
{
  "message": "Chain cleared 3 words for 62 points.",
  "resolution": "chain",
  "primary_word": "Anchor",
  "primary_cell": 42,
  "scored_cells": [
    { "cell": 42, "word": "Anchor", "score": 100 },
    { "cell": 50, "word": "Harbor", "score": 88 },
    { "cell": 58, "word": "Dock", "score": 77 }
  ],
  "removed_words": ["Anchor", "Harbor", "Dock"],
  "removed_cells": [42, 50, 58],
  "spawned_words": ["Pilot", "Radar", "Runway"],
  "spawned_cells": [2, 10, 18],
  "state": { "...": "..." }
}
```

If the clue only hits the primary cell:

- still count it as a valid chain of size `1`
- still remove it
- still apply gravity and refill

## Blocks mode frontend changes

Add:

- `templates/blocks.html`

This should not reuse the iteration tower DOM. It needs a proper grid.

Suggested required element ids:

- `blocks-grid`
- `score-value`
- `timer-value`
- `remaining-value`
- `progress-value`
- `progress-bar`
- `provider-badge`
- `latency-value`
- `status-banner`
- `last-clue-value`
- `last-primary-value`
- `new-game-button`
- `clue-form`
- `clue-input`
- `submit-button`
- `game-over-modal`
- `game-over-title`
- `game-over-message`
- `game-over-new-game-button`

### New frontend files

Add:

- `frontend/src/blocks_types.ts`
- `frontend/src/blocks_dom.ts`
- `frontend/src/blocks_api.ts`
- `frontend/src/blocks_board.ts`
- `frontend/src/blocks_animations.ts`
- `frontend/src/blocks_controller.ts`
- `frontend/src/blocks.ts`

### `blocks_types.ts`

Define:

- `BlocksCell`
- `BlocksState`
- `BlocksStateResponse`
- `BlocksTurnResponse`

Suggested `BlocksCell` shape:

```ts
export interface BlocksCell {
  cell: number;
  row: number;
  col: number;
  word: string | null;
}
```

### `blocks_board.ts`

Implement:

- `renderBlocksGrid(elements, cells, state)`
- `applyBlocksCellClasses(element, cell, state)`
- `highlightPrimaryCell(...)`
- `highlightScoredCells(...)`

CSS classes to support:

- `blocks-cell`
- `blocks-cell--filled`
- `blocks-cell--primary`
- `blocks-cell--combo`
- `blocks-cell--spawned`
- `blocks-cell--empty`

### `blocks_animations.ts`

Implement animations for:

- primary hit flash
- combo pulse for all removed cells
- falling survivors after gravity
- top-entry spawn motion

The easiest approach is FLIP animation similar to the current tower animation code, but keyed by cell id rather than by word string.

That matters because:

- duplicate words may exist in future packs
- grid mode should not assume words are unique DOM keys

### `blocks_controller.ts`

Implement flow:

1. load current state
2. render grid
3. submit clue
4. disable input while busy
5. run primary highlight
6. run combo highlight/removal animation
7. animate gravity
8. animate spawned words
9. update HUD

## CSS changes for blocks mode

Edit:

- `static/css/app.css`

Add a blocks-specific section:

- grid layout
- square or near-square cells
- responsive fallback to narrower columns on small screens
- visual distinction between empty and filled cells
- primary-cell and chain-cell treatment

Do not try to force the current tower CSS classes to serve both layouts.

## Blocks mode tests

Add Python tests:

- `tests/test_game_logic_blocks.py`
- extend `tests/test_app.py`
- extend `tests/test_llm_client.py`

Required backend test cases:

- initial blocks state creates exactly `target_occupied_cells` words
- occupied component detection respects 4-way adjacency only
- BFS chain only traverses above-threshold cells connected to the primary
- gravity compacts each column downward
- refill inserts into top empty slots only
- score formula matches expected values
- run ends only when unseen pool is exhausted and grid is empty
- heuristic fallback scoring returns all expected words with `0..100` scores

Add frontend tests:

- `frontend/src/__tests__/blocks_board.test.ts`
- `frontend/src/__tests__/blocks_controller.test.ts`

Required frontend test cases:

- grid renders correct number of cells
- primary cell gets highlighted
- removed cells animate out
- gravity reorders cells visually
- spawned cells animate in from the top

## File-by-file edit checklist

### Backend files to edit

- `app.py`
  Add mode session handling, new routes, new API namespaces, new serializers.
- `llm_client.py`
  Add restriction-judge and word-scoring capabilities, new schemas, validators, and fallback logic.
- `scripts/build-frontend.mjs`
  Add `restriction` and `blocks` bundle entry points.

### Backend files to add

- `game_logic_restriction.py`
- `game_logic_blocks.py`

### Frontend files to edit

- `templates/home.html`
  Add UI to launch the new modes.
- `static/css/app.css`
  Add restriction-mode UI and blocks-grid UI.

### Frontend files to add

- `templates/restriction.html`
- `templates/blocks.html`
- `frontend/src/restriction.ts`
- `frontend/src/restriction_controller.ts`
- `frontend/src/restriction_api.ts`
- `frontend/src/restriction_dom.ts`
- `frontend/src/restriction_types.ts`
- `frontend/src/blocks.ts`
- `frontend/src/blocks_controller.ts`
- `frontend/src/blocks_api.ts`
- `frontend/src/blocks_dom.ts`
- `frontend/src/blocks_types.ts`
- `frontend/src/blocks_board.ts`
- `frontend/src/blocks_animations.ts`

### Data/config files to add

- `assets/restriction_rules.json`

### Test files to add

- `tests/test_game_logic_restriction.py`
- `tests/test_game_logic_blocks.py`
- `frontend/src/__tests__/restriction_dom.test.ts`
- `frontend/src/__tests__/restriction_controller.test.ts`
- `frontend/src/__tests__/blocks_board.test.ts`
- `frontend/src/__tests__/blocks_controller.test.ts`

## Verification plan

Run all of these after implementation:

### Python tests

```bash
python -m unittest
```

### Frontend type-check

```bash
npm run check:frontend
```

### Frontend tests

```bash
npm run test:frontend
```

### Frontend build

```bash
npm run build:frontend
```

### Manual smoke test: Restriction Mode

1. Start a restriction run from the home page.
2. Confirm the rule banner shows a real rule name and description.
3. Submit a clue that obviously fails a deterministic rule.
4. Confirm:
   - no ranking animation occurs
   - strike count increases
   - penalty word is inserted at the bottom
   - status text explains the failure
5. Submit a clue that obviously passes.
6. Confirm:
   - normal ranking animation occurs
   - score gain is multiplied
   - strike count does not increase
7. Fail enough times to hit max strikes.
8. Confirm:
   - game-over modal appears
   - result is a loss, not a win

### Manual smoke test: Blocks Mode

1. Start a blocks run from the home page.
2. Confirm the board renders as an `8x10` grid.
3. Confirm exactly `32` cells are filled on first render.
4. Submit a clue matching one visible word strongly.
5. Confirm:
   - one primary cell is highlighted
   - at least that word is removed
   - gravity pulls surviving words downward
   - new words spawn from the top
6. Submit a clue likely to match a visible cluster.
7. Confirm:
   - multiple adjacent cells clear
   - score jump is much larger than a single-cell clear
8. Exhaust the unseen pool, then continue clearing.
9. Confirm the run ends only when the grid becomes empty.

## Definition of done

The implementation is correct when all of the following are true:

- current `Iteration Mode` still behaves exactly as before
- restriction mode can start, play, score, penalize, rotate rules, and lose correctly
- blocks mode can start, clear chains, apply gravity, refill, score combos, and finish correctly
- provider failures do not make the two new modes crash or become unfair
- all Python tests pass
- all frontend tests pass
- TypeScript type-check passes
- frontend build passes

## Is this brief sufficient for a contractor or another AI?

Yes.

It is sufficient because it includes:

- the architectural boundary for each mode
- the exact files to edit
- the new files to add
- the state fields to introduce
- the API payloads to return
- the algorithms to implement
- the fallback behavior to preserve playability
- the tests and manual checks needed to prove correctness

The only remaining freedom for the implementer is visual polish detail, which is appropriate. The game rules, contracts, and verification requirements are specific enough to build from without needing another design pass.
