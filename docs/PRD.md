# Semantris Plus PRD

Status: Active foundation document
Owner: BinaryOutlook
Last updated: 2026-03-30
Project phase: Solo-built prototype moving toward a maintainable small product

## 1. Purpose

This PRD defines the stable product direction for Semantris Plus in its current phase.

It exists to answer four questions:

- what the product is
- what is in scope right now
- what quality bar the project should meet
- how the codebase should grow without turning into spaghetti

This document is intentionally product-first. It should stay valid across many implementation iterations.

It does not replace:

- `README.md` for setup and repo overview
- `brief.md` for contractor-style orientation
- `docs/V*.md` for historical release notes
- technical design notes or ADRs for implementation decisions

## 2. Product Summary

Semantris Plus is a modern semantic word arcade built as a small but serious reinterpretation of the original Semantris idea.

The product uses an LLM-backed ranking layer to turn short text clues into visible board motion. The current product includes three playable modes:

- Iteration Mode: classic tower play built around moving a target into the clear zone
- Restriction Mode: tower play with rotating clue rules, strikes, and score bonuses
- Blocks Mode: a semantic chain-reaction grid with local scoring and gravity

The project is small in team size, but it should be treated as a maintainable product, not as a disposable prototype.

## 3. Problem Statement

There are two connected problems this project is solving.

### 3.1 Player problem

Semantic word games are compelling when clue quality directly affects board motion, but many implementations either feel mechanically limited, semantically shallow, or structurally frozen in an older technical era.

Semantris Plus aims to deliver:

- short replayable runs
- satisfying semantic cause-and-effect
- a cleaner modern presentation
- multiple modes built on the same core idea

### 3.2 Development problem

As the game grows, features can easily spread across routes, templates, mode logic, frontend controllers, and ranking code in an unstructured way.

This project must therefore solve for product quality and code maintainability at the same time.

## 4. Why This Matters Now

The codebase is no longer a one-file prototype. It already has:

- multiple playable modes
- distinct backend gameplay modules
- a typed frontend source tree
- an explicit JSON API
- test coverage across core logic and browser-side utilities

That is exactly the point where a stable PRD becomes useful. Without one, future changes will be guided by scattered release notes, memory, and convenience, which is how small projects drift into documentation debt and spaghetti structure.

## 5. Product Goals

For the current phase, Semantris Plus should:

- deliver a polished local-play semantic word game with three distinct modes
- keep the core loop legible and satisfying even when the ranking provider is imperfect
- remain resilient when the remote model fails, times out, or returns invalid output
- stay understandable enough that future contributors can extend it safely
- preserve clean mode boundaries so new features do not create cross-mode tangles

## 6. Non-Goals

The current phase is not trying to become:

- a generic word-game engine
- a multiplayer product
- a live-service platform with accounts and cloud persistence
- a mobile-native app
- a fully framework-replatformed frontend
- an over-abstracted architecture built for imaginary scale

If a future feature does not clearly improve the current playable product or the maintainability of the repo, it should not be treated as default scope.

## 7. Primary Users

### 7.1 Primary builder

The immediate primary user is the solo developer maintaining the repo. The codebase, docs, and workflows must support fast re-entry after time away from the project.

### 7.2 Players

The player is someone who wants a short, replayable, browser-based semantic puzzle with low setup friction and clear feedback.

### 7.3 Future contributors

Future contractors or collaborators should be able to understand:

- which files own which mode
- where gameplay rules live
- where provider logic lives
- which docs define product direction versus implementation history

## 8. Current Product Scope

### 8.1 Shared capabilities

The product currently supports:

- local browser play through Flask-rendered pages
- selectable vocabulary packs from `assets/`
- multiple game modes from one landing page
- session-based run state
- Gemini or OpenAI-compatible provider selection through environment configuration
- deterministic local fallback behavior when remote ranking fails
- light and dark themes with manual override
- automated backend and frontend tests

### 8.2 Iteration Mode

Iteration Mode is the core tower loop.

Requirements:

- a run starts with a visible tower and a highlighted target word
- the player submits one clue per turn
- the ranking layer orders visible words from most related to least related
- the tower displays the strongest matches at the bottom
- the bottom four positions form the clear zone
- if the target lands in the clear zone, the target and the words between it and the zone boundary are removed
- score increases based on removed words
- new words refill from the unseen vocabulary pool

### 8.3 Restriction Mode

Restriction Mode is a harder tower variant.

Requirements:

- an active rule is always visible
- each clue must satisfy the active rule before a turn can resolve normally
- a failed rule check produces a strike and inserts penalty words at the bottom
- rules rotate during the run
- legal clues may apply a score bonus
- the run can end by reaching the strike limit or by pushing the target out of the tower

### 8.4 Blocks Mode

Blocks Mode is a separate grid-based chain-reaction mode.

Requirements:

- the board is a two-dimensional occupied grid
- each clue selects a primary semantic hit
- neighboring occupied cells can join the chain if their local score is high enough
- chain growth is based on orthogonal adjacency
- cleared cells trigger gravity and refill
- scoring rewards larger chains
- the mode ends in a win when the unseen pool is exhausted and the board is fully cleared

## 9. Functional Requirements

### 9.1 Run lifecycle

- A player can start a new run from the landing page for any supported mode.
- The selected mode and vocabulary pack remain explicit in session state.
- Each mode exposes a stable state payload that the frontend can render without hidden assumptions.
- Runs track score, turns, elapsed time, progress through the vocabulary, and end-state information.

### 9.2 Vocabulary handling

- Vocabulary packs are newline-separated text files under `assets/`.
- Duplicates should be eliminated by normalized form during loading.
- Words should not repeat within a run until the unseen pool is exhausted, except where a specific mode intentionally recycles from exhausted supply.

### 9.3 Ranking and validation

- Remote provider output must be validated against the current board or candidate set before it is trusted.
- Invalid remote output must not corrupt gameplay state.
- A deterministic fallback path must exist so local play remains possible when the remote provider path fails.

### 9.4 UI and feedback

- The landing page must clearly present the available modes and pack selection.
- Each game page must expose the most important run state at a glance.
- Input, loading, failure, and end-of-run states must be visible without opening dev tools.
- The target word or primary result must be visually obvious.

## 10. Non-Functional Requirements

### 10.1 Maintainability

- New features should fit the existing responsibility boundaries rather than weakening them.
- Mode-specific behavior should stay mode-specific unless a shared abstraction is clearly justified.
- The codebase should remain readable after time away from the project.

### 10.2 Reliability

- Provider failures must degrade gracefully.
- Session state should remain explicit and serializable.
- The app should remain playable even when the best provider path is unavailable.

### 10.3 Testability

- Core gameplay rules should remain testable outside Flask where practical.
- Every meaningful gameplay rule change should add or update tests.
- Frontend behavior with stable contracts should continue to be validated by typed code and targeted tests.

### 10.4 Usability

- Runs should feel fast to start and easy to replay.
- The product should remain keyboard-friendly.
- Visual polish should support clarity rather than bury it under chrome.

### 10.5 Documentation hygiene

- Stable product intent belongs here in the PRD.
- Setup and repo orientation belong in `README.md`.
- Historical change summaries belong in `docs/V*.md` and `CHANGELOG.md`.
- Major implementation decisions should be recorded separately when they would otherwise be rediscovered repeatedly.

## 11. Engineering Guardrails

This section is the anti-spaghetti contract for the project.

### 11.1 Preserve clear ownership by layer

- `app.py` owns route wiring, session coordination, and API serialization.
- `game_logic.py`, `game_logic_restriction.py`, and `game_logic_blocks.py` own mode rules.
- `llm_client.py` owns provider communication, validation, and fallback behavior.
- `frontend/src/*` owns browser-side rendering, page orchestration, and animation.
- `templates/*.html` should stay page shells, not become logic containers.

### 11.2 Preserve clear ownership by mode

- Iteration, Restriction, and Blocks should continue to have distinct code paths where their rules differ materially.
- Do not force all modes through one giant resolver or one giant frontend controller just to reduce file count.
- Shared helpers should be extracted only after duplication is real and the abstraction is obvious.

### 11.3 Prefer explicit contracts over hidden coupling

- Session payloads should remain explicit.
- Frontend code should consume backend-provided state instead of quietly re-encoding gameplay rules.
- Mode-specific API namespaces are preferable to ambiguous mega-endpoints when behavior differs meaningfully.

### 11.4 Keep LLM behavior isolated

- No gameplay module should call the provider directly.
- Prompting, parsing, validation, and fallback rules should remain centralized.
- Provider-specific changes should not force edits across unrelated gameplay files.

### 11.5 Keep documentation layered

- `README.md` explains what the repo is and how to run it.
- `docs/PRD.md` explains what the product is trying to become in this phase.
- `brief.md` helps future helpers re-enter the project quickly.
- `docs/V*.md` explain why specific milestones happened.
- New architecture decisions that shape future work should be written down as ADR-style notes instead of living only in commits or memory.

### 11.6 Prefer small, test-backed changes

- Avoid wide refactors that change multiple layers without a clear reason.
- When a feature touches several files, the ownership and data flow should still be obvious.
- A change that requires editing unrelated modes is a warning sign and should trigger a design pause.

### 11.7 Avoid dumping-ground files

- Do not create vague catch-all modules like `helpers_everything.py` or `misc.ts`.
- Shared utilities should stay small, named by purpose, and used by more than one real caller.
- If `app.py` continues to grow substantially, split it intentionally by responsibility before adding more cross-cutting behavior.

## 12. Success Criteria For This Phase

This phase is successful if:

- the repo has one stable product foundation document instead of relying on scattered historical notes
- all three modes remain locally playable through the existing landing page flow
- the ranking path remains resilient through validation and fallback behavior
- future work can usually stay within one mode slice without breaking others
- contributors can understand where to make a change after reading `README.md` and this PRD
- code quality continues to improve without requiring a large-framework rewrite

## 13. Near-Term Priorities

The next wave of work should focus on quality, not uncontrolled scope growth.

Priority areas:

- stronger end-of-run states and summaries
- continued UI and motion polish
- broader frontend behavior coverage
- better fallback ranking quality
- clearer difficulty and tuning choices across modes
- continued cleanup if `app.py` becomes too large for comfortable ownership

## 14. Open Questions

These questions are intentionally left open for future design work:

- Should Semantris Plus eventually support persistence, or stay session-only for a longer period?
- Which metrics best define "good" ranking quality for each mode?
- Should vocabulary packs gain metadata beyond filename and word count?
- At what point should `app.py` be split into smaller modules?
- Which longer-term mode ideas are truly product-improving versus just mechanically interesting?

## 15. Update Policy

Update this PRD when the stable product direction changes.

Do not update it for every small implementation change.

Use this rule of thumb:

- if the change affects what the product is, what it promises, or how the repo should stay maintainable, update the PRD
- if the change only affects how something was implemented, update technical docs, release notes, or code comments instead
