# Project Brief: Semantris Plus Refresh

## 1. Purpose

This project is a modern rebuild of the original Semantris arcade idea using contemporary LLMs for semantic ranking. The current prototype already proves the central mechanic, but it is still a tightly coupled afternoon demo. The next phase should turn it into a polished, reliable, contractor-friendly product that is visually intentional, mechanically fair, and structurally maintainable.

This brief is written to help future AI contractors work from a shared implementation contract instead of re-discovering the repo from scratch.

## 2. Current Repository Snapshot

### Existing files

- `app.py`: Flask server, Gemini configuration, vocabulary loading, gameplay logic, session mutation, and API behavior are all mixed together.
- `templates/arcade.html`: Entire UI, styling, animation, and client state live in one template file.
- `assets/*.txt`: Vocabulary packs with varying sizes.
- `testing/api_latency.py`: Ad hoc latency script for provider comparison.
- `README.md`: Informal project overview and setup notes.
- `requirements.txt`: Python dependencies.

### Architectural reality today

- The app is a server-rendered Flask page with one JSON endpoint.
- Frontend logic is embedded directly inside the template.
- Backend state is stored in Flask session keys.
- LLM output parsing is permissive and fragile.
- There is no real automated test suite.
- There is no formal product brief, engineering roadmap, or contributor contract.

## 3. Product Direction

Build a professional-feeling arcade word game that keeps the playful spirit of Semantris while embracing modern LLM-backed semantics, better visual design, and stronger engineering discipline.

The intended result should feel:

- fast
- legible
- satisfying
- replayable
- resilient when the LLM misbehaves
- easy for future contractors to extend

## 4. Core Problems To Solve

### Gameplay/system problems

- Word reuse is not controlled across the whole session, so previously seen words can return.
- There is no proper run lifecycle or meaningful end-state.
- The session only tracks a minimal state shape.
- The game depends too heavily on one model response format.
- Invalid or partial LLM answers can break the round.
- Difficulty scaling is only partially implemented.

### Frontend/UI problems

- The visual language is still prototype-level.
- Layout hierarchy is weak; the tower, HUD, and action area compete instead of reinforcing each other.
- The current template is monolithic and hard to maintain.
- Motion is incomplete: reorder, collapse, and spawn animations do not fully sell the arcade effect.
- There is limited feedback for loading, errors, streaks, progress, and session completion.
- The interface is not clearly designed around desktop plus mobile responsiveness.

### Engineering/maintainability problems

- `app.py` mixes configuration, domain logic, LLM logic, and route handlers.
- Frontend code is not separated into reusable assets.
- There is no pure-domain test coverage for board mutation logic.
- Configuration is implicit instead of centralized.
- Documentation is missing a proper roadmap and technical overview.

## 5. Non-Negotiable Product Requirements

These requirements should guide all implementation work.

### Core loop

- A session starts with a tower and one highlighted target word.
- The player submits a clue.
- The LLM ranks every visible word from most related to least related.
- The tower should display the most related words at the bottom and the least related words at the top.
- The bottom four positions are the destruction zone.
- If the target lands inside the destruction zone, remove the target and every word between it and the bottom-most eligible removal boundary.
- Score should increase by the number of removed words.
- New words should fall in from the top.
- If the target is not in the destruction zone, the tower should simply reorder.

### Session progression

- Board size must scale with score and remain readable.
- Words should not repeat within a run until the vocabulary pool is exhausted.
- The session should track elapsed time.
- The session should expose useful metadata such as score, seen-word count, remaining-word count, turn count, and last latency.
- There should be a defined end condition or at minimum a clearly defined “run exhausted” state.

### Reliability

- LLM output must be validated against the current board.
- The app should recover gracefully from malformed model output.
- A fallback ranking strategy should exist so the game does not become unusable when the provider fails.

## 6. Target UX Vision

### Experience principles

- Arcade clarity over clutter.
- Minimal but not sterile.
- Motion should communicate state changes, not decorate them.
- The target word must be impossible to miss.
- Information density should feel deliberate and premium.
- Inputs should feel immediate and keyboard-first.

### Visual direction

- Avoid generic Tailwind-demo styling.
- Use a strong typographic pairing with a more intentional look than default sans-serif UI kits.
- Use layered backgrounds, subtle glows, and contrast-based depth.
- The tower should feel like a physical semantic stack, not a plain list.
- The destruction zone should be visually understandable without overwhelming the playfield.
- The tower viewport should comfortably support the maximum visible tower density.

### Motion direction

- Reorders should animate as travel to destination, not teleportation.
- Removed words should visibly break apart, fade, or burst.
- Surviving words should collapse downward into reclaimed space.
- Spawned words should drop in from above with timing that matches the game rhythm.
- Loading should have clear “AI is thinking” feedback without freezing the whole interface.

## 7. Recommended Technical Refactor

### Backend separation

Refactor the current backend into clearer responsibilities:

- app entrypoint and Flask setup
- configuration loading
- vocabulary/session state helpers
- pure gameplay rules
- LLM provider and ranking validation

Suggested shape:

- `app.py`: Flask wiring and route registration only
- `game_logic.py`: board size, session initialization, word replenishment, turn resolution
- `llm_client.py`: prompt construction, provider call, parsing, validation, fallback behavior
- `templates/arcade.html`: HTML shell only
- `static/css/app.css`: visual system and animation styling
- `static/js/game.js`: client state, rendering, animation orchestration, API calls

This does not need to become an over-engineered framework. It should simply stop mixing unrelated concerns in the same file.

### Session model

The server-side session should become a stable contract, for example:

- `score`
- `board`
- `target_word`
- `used_words`
- `turn_count`
- `started_at`
- `last_latency_ms`
- `last_clue`
- `game_over`
- `vocabulary_name`

### API contract

Prefer clearer endpoints and payloads:

- `GET /` renders the shell
- `POST /api/game/new` starts a new run
- `GET /api/game/state` returns current session state
- `POST /api/game/turn` resolves one clue submission

Response payloads should be explicit enough for the frontend to animate without deriving hidden rules.

## 8. LLM and Ranking Improvements

### Prompting

- Ask for a clean structured ranking response rather than free-form newline output when feasible.
- Instruct the model to preserve exact word spellings from the provided list.
- Keep temperature low for consistency.

### Validation

- Normalize case and whitespace before comparison.
- Reject outputs with duplicates, missing words, or unknown words.
- Add at least one recovery path if validation fails.

### Fallback behavior

When the provider fails or returns invalid output:

- Use a deterministic local fallback ranking heuristic.
- Return a warning marker in the API response so the UI can message the player appropriately.

This fallback is not meant to replace the LLM, but it is essential for reliability, demos, and local development.

### Provider abstraction

Keep Gemini as the primary provider, but isolate provider configuration so future contractors can add alternatives without rewriting the game loop.

## 9. Frontend Workstream

### Immediate goals

- Move CSS and JavaScript out of the template.
- Rebuild the play screen around a stronger information hierarchy.
- Improve the tower’s perceived depth and spacing.
- Add session stats beyond score and time.
- Make the playfield feel full-height and properly balanced on large screens.

### Core UI areas

#### Hero/HUD

- score
- elapsed time
- target word
- remaining unseen words
- turns taken
- provider/latency status

#### Tower

- tall, centered, readable stack
- explicit destruction zone
- highlighted target word
- clear distinction between safe zone and danger zone
- stronger spatial rhythm between words

#### Action panel

- clue input
- submit action
- loading state
- response/status messaging
- restart/new run action

#### Completion state

- end-of-run summary
- score
- total time
- total turns
- vocabulary pack used
- invitation to replay

### Accessibility and usability

- Ensure color contrast is strong enough for the target and destruction zone.
- Preserve keyboard-first play.
- Add disabled states and clear status messages for network or provider failure.
- Respect reduced-motion preferences where practical.
- Keep the interface usable at mobile widths without sacrificing desktop presentation.

## 10. Gameplay Improvements To Implement

### Must-have

- Eliminate repeat words within a session until necessary.
- Formalize the “top four / bottom four” semantics in code and documentation so orientation bugs stop recurring.
- Add a proper game-over condition tied to vocabulary exhaustion and board depletion.
- Track richer session metrics.

### Should-have

- Expose the vocabulary pack name in the UI.
- Allow easy switching of vocabulary packs via configuration.
- Add turn history or at least last-turn feedback.
- Add a restart button that fully resets the session.

### Could-have

- Difficulty presets
- daily challenge seed
- local leaderboard
- alternate ranked modes
- themed UI skins tied to vocabulary packs

## 11. Testing and Quality Bar

### Automated tests

Add pure Python tests for:

- board size scaling
- session initialization
- no-repeat word selection
- valid hit resolution
- valid miss resolution
- end-of-run detection
- malformed ranking rejection

### Manual verification checklist

- start a new game
- submit a valid clue
- confirm reorder orientation is bottom-most equals most related
- confirm target-hit removal counts are correct
- confirm score increments properly
- confirm new words spawn from above
- confirm previously seen words do not reappear early
- confirm session ends cleanly when the pool is exhausted
- confirm UI works at both mobile and desktop widths

## 12. Documentation Deliverables

The documentation set should include:

- updated `README.md`
- this `brief.md`
- clearer environment setup instructions
- vocabulary pack notes
- known limitations
- future roadmap ideas

The README should become user-facing. This brief should remain contractor-facing.

## 13. Delivery Phases

### Phase 1: Stabilize the core

- separate domain logic from Flask route handlers
- add provider abstraction and fallback ranking
- add a richer session model
- create automated gameplay tests

### Phase 2: Rebuild the frontend

- move CSS/JS to static files
- redesign layout, HUD, tower, and action panel
- improve reorder, removal, and drop-in animations
- add better feedback states and restart flow

### Phase 3: Polish and docs

- tighten copy and messaging
- refresh README
- document configuration and vocabulary packs
- capture remaining backlog and known limitations

## 14. Definition of Done For This Refresh

The refresh should be considered successful when:

- the codebase is modular enough for future contractors to work safely
- the UI feels deliberate and modern instead of prototype-grade
- gameplay orientation and destruction logic are unambiguous and tested
- word repetition is controlled
- a run has a meaningful lifecycle
- the app remains playable even when the primary LLM path fails
- the README and project brief clearly explain the project and next steps

## 15. Immediate Recommendation

The next contractor should not start with cosmetic changes alone. The best first move is:

1. isolate gameplay and ranking logic
2. formalize session state and end conditions
3. move frontend assets out of the template
4. then apply the UI/animation refresh on top of a stable contract

That sequencing will produce a better game and avoid another round of fragile vibe-coded surface polish over unstable mechanics.
