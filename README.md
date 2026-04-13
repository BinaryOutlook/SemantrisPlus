# Semantris Plus

LLM-powered semantic arcade game inspired by the original Semantris concept, built as a maintainable Flask application with a TypeScript-powered browser client.

## Overview

Semantris is still one of the most compelling word game ideas ever made. It turns semantic intuition into visible motion: you type a clue, language itself becomes the game state, and meaning decides what survives.

This project exists because I wanted a better Semantris-style experience for the LLM era.

The original idea is still excellent, but modern language models make it possible to revisit that loop with a much broader, more current semantic engine. Instead of relying on older ranking systems, this version uses a contemporary LLM stack to reorder words by association and create a more flexible, extensible foundation for a new arcade interpretation.

Semantris Plus is not trying to pretend it surpasses the original Semantris. The original was a real product built by a strong design and engineering team. This repository is an ambitious small-game project: a playable modern reinterpretation with stronger AI-era semantics, cleaner code structure, and a roadmap toward a more polished game.

## Vision

The ambition for this repo is straightforward:

- build a Semantris-like arcade game that feels modern instead of prototype-grade
- use current LLMs where semantic ranking actually adds value
- preserve the clarity and immediacy of the original idea
- make the codebase maintainable enough for future contractors or contributors to extend safely
- improve both the game feel and the engineering quality at the same time

This is intentionally both a game project and a software-structure project.

## Current Modes

The game now ships with three playable modes, Version Code "0.3.1" :

### Iteration Mode

The original tower-based arcade variant:

- the game starts with a tower of words and one highlighted target word
- the player enters a clue
- the ranking engine orders the visible words from most related to least related
- the tower is displayed so the bottom-most word is the most correlated result
- the bottom four words form the destruction zone
- if the target lands in that zone, the target and the words between it and the zone boundary are removed
- score increases by the number of removed words
- new words drop in from the top
- the session tracks time, score, turns, and vocabulary progress

### Restriction Mode

A harder tower variant where every clue must also obey a rotating rule:

- the tower and target behave like Iteration Mode
- an active rule is shown above the board
- your clue must both satisfy the rule and still semantically pull the target into the destruction zone
- if the clue passes the rule, the tower resolves like Iteration Mode
- if the clue fails the rule, you take a strike and penalty words are inserted at the bottom of the tower
- the run ends if you reach 3 strikes or a penalty insertion pushes the target out of the tower
- the active rule rotates every 10 turns
- some successful rule-compliant turns award a score multiplier bonus

### Blocks Mode

A separate grid-based chain reaction mode:

- the board is an `8 x 10` grid with up to `32` occupied cells at a time
- you type a clue and the system picks the single best matching word as the primary hit
- nearby words are scored for how strongly they relate to the clue
- any orthogonally connected neighbor scoring `75` or higher can join the chain
- the chain keeps expanding outward through qualifying neighbors
- all chained words are removed together
- score grows by combo size using an accelerating formula, starting at `10` points for a one-word clear
- words above fall downward, and new words refill empty slots from the top while unseen vocabulary remains
- the run ends in a win when the unseen pool is exhausted and the board has been fully cleared

## How To Play

### Starting a run

1. Run the app locally.
2. Open the landing page.
3. Choose a vocabulary pack.
4. Launch `Iteration Mode`, `Restriction Mode`, or `Blocks Mode`.

### Playing Restriction Mode

1. Read the active rule before typing.
2. Enter a clue that obeys the rule and points toward the highlighted target word.
3. Submit the clue.
4. If the clue passes, the ranked tower resolves like normal tower play.
5. If the clue fails, you take a strike and extra penalty words are added to the bottom.
6. Survive the rotating rules and clear the tower before hitting 3 strikes.

Tips:

- Shorter clues are often easier to keep rule-compliant.
- Local-format rules are exact, so wording details matter.
- A safe clue that misses is usually better than an illegal clue that adds a strike.

### Playing Blocks Mode

1. Look for a small cluster of words that could all plausibly answer the same clue.
2. Enter one clue for that cluster.
3. The system chooses a primary word first.
4. The chain then spreads through adjacent words that also match strongly enough.
5. Cleared words disappear together, gravity pulls columns downward, and new words spawn in.
6. Repeat until the unseen pool is empty and the board is cleared.

Tips:

- Think in connected neighborhoods, not isolated words.
- A clue that strongly matches one word but weakly matches its neighbors usually produces only a short clear.
- Broad category clues can be useful, but the best clears usually come from tight local themes.

## Why LLMs Here

Modern LLMs are not deterministic ranking machines, and that matters. Even at low temperature, semantic ordering can still vary.

That said, for short clue-and-word ranking tasks, modern models are strong enough to make this design space genuinely fun again. Their broader world knowledge also makes the game more flexible across themed vocab packs and future content expansions.

This repo supports two remote ranking modes: Gemini through Google’s Gen AI SDK, and an OpenAI-compatible mode through the `openai` Python client. The selected provider is chosen at startup, and the game still includes a local heuristic fallback so the app remains playable if the configured model path fails.

## Project Status

Current status: strengthened local prototype with a modular Flask backend, a typed frontend client, OpenAI/Gemini-compatible ranking, local run persistence, deterministic browser tests, and a three-theme UI system with manual light, dark, and Cupertino switching.

The current planning packet is `PRDs/v0.5/`, which defines the HMAS readiness and architecture modernization pass. The most recent completed infrastructure packet is `PRDs/v0.4/`, and the Cupertino frontend theme packet remains in `PRDs/v0.3.1/`.

What is already in place:

- modularized gameplay logic instead of one monolithic server file
- explicit JSON API for session state and turns
- three playable game modes with shared pack selection
- no-repeat word handling until the unseen pool is exhausted
- improved tower presentation and animation sequencing
- a TypeScript frontend source tree compiled into a browser bundle
- a shared theme controller with manual light/dark/Cupertino switching across the landing page and the game
- a polished light mode, a flatter surface-led dark mode, and a Cupertino theme with a more restrained product-style shell
- frontend type-checking and Vitest coverage for key browser-side logic
- fake-ranker support for deterministic browser tests
- semantic caching, semantic fallback, and heuristic fallback paths for resilience
- local SQLAlchemy run persistence and best-score metadata
- automated tests for gameplay rules, API behavior, provider fallback behavior, frontend DOM behavior, and browser flows

What is still unfinished:

- HMAS-ready ownership boundaries for future parallel agents
- final game feel polish
- richer end-of-run UX
- broader frontend test coverage across full interaction flows
- richer leaderboard and run-history surfaces
- stronger semantic fallback quality and observability
- model selection tuning across Gemini and OpenAI-compatible providers

## Architecture

This repository is now structured around clear responsibilities instead of mixing UI, session state, LLM calls, build concerns, and game rules in a single file.

### Runtime flow

1. Flask serves the landing page and game HTML shells.
2. The browser applies the stored or system theme and loads the compiled TypeScript bundles.
3. The game frontend loads current session state from the JSON API.
4. The player submits a clue.
5. The backend sends the visible board to the ranking provider.
6. The ranking result is validated and converted into board mutations.
7. The frontend animates reorder, removal, collapse, spawn events, and end-of-run UI state.

### Key design choices

- Gameplay rules are isolated so they can be tested without the web app.
- LLM interaction is isolated so provider changes do not require rewriting the game loop.
- The interactive frontend now lives in dedicated TypeScript modules compiled into served browser bundles.
- Session state is explicit so the frontend can render the game from stable API payloads.
- The frontend build and validation steps are small but formalized so browser code can evolve safely.
- Theme state is handled in the frontend so all pages stay visually consistent while still respecting system light/dark preference by default.

## Repository Structure

```text
SemantrisPlus/
├── app.py                 # Flask app, route wiring, session serialization
├── game_logic.py          # Iteration-mode board/session rules
├── game_logic_restriction.py # Restriction-mode rules, strikes, and rule rotation
├── game_logic_blocks.py   # Blocks-mode grid, gravity, and chain resolution
├── llm_client.py          # Provider integration, validation, and fallback ranking
├── CHANGELOG.md           # Curated notable changes
├── README.md              # Project overview and setup
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable template
├── assets/                # Vocabulary packs
│   ├── aviation_1.txt
│   ├── basic_vocab.txt
│   ├── general_1.txt
│   ├── lite_1.txt
│   └── restriction_rules.json
├── PRDs/
│   ├── README.md          # Versioned iteration workflow
│   ├── references/
│   │   └── v0.3.1-cupertino-source-packet/
│   │       ├── DESIGN.md  # Imported Apple-inspired source design notes
│   │       ├── README.md  # Source packet overview
│   │       ├── preview.html
│   │       └── preview-dark.html
│   ├── v0.3/
│   │   ├── v0.3.md        # Initial version-scoped PRD packet
│   │   └── v0.3-demo.html # Static design demo for the iteration
│   ├── v0.3.1/
│   │   ├── v0.3.1.md      # Cupertino frontend iteration PRD
│   │   └── v0.3.1-demo.html # Cupertino design target for implementation
│   ├── v0.4/
│   │   ├── v0.4.md        # Technical strengthening iteration PRD
│   │   └── v0.4-demo.html # Technical readiness reference
│   ├── v0.5/
│   │   ├── v0.5.md        # HMAS readiness and architecture modernization PRD
│   │   └── v0.5-demo.html # HMAS command-board reference
├── docs/
│   ├── README.md          # Documentation map and placement rules
│   ├── PRD.md             # Foundation product requirements document
│   ├── briefs/
│   │   └── project-brief.md # Contractor-facing orientation brief
│   ├── decisions/
│   │   ├── gemini-sdk-migration.md
│   │   └── llm-provider-diversification.md
│   ├── history/
│   │   └── releases/
│   │       ├── v0.1-structural-cleanup.md
│   │       ├── v0.1.2-frontend-enhancement.md
│   │       └── v0.2-typescript-frontend-migration.md
│   └── proposals/
│       ├── frontend-typescript-rewrite-assessment.md
│       └── modes/
│           ├── blocks-and-restriction-concept.md
│           └── blocks-and-restriction-technical-brief.md
├── frontend/
│   └── src/               # TypeScript source for all interactive game clients
├── package.json           # Frontend scripts and dependencies
├── tsconfig.json          # TypeScript compiler configuration
├── vitest.config.ts       # Frontend test configuration
├── scripts/
│   └── build-frontend.mjs # esbuild entry for browser bundle output
├── static/
│   ├── css/app.css        # Visual system and layout styling
│   └── js/                # Compiled browser bundles served by Flask
├── templates/
│   ├── arcade.html        # HTML shell for Iteration Mode
│   ├── restriction.html   # HTML shell for Restriction Mode
│   ├── blocks.html        # HTML shell for Blocks Mode
│   └── home.html          # HTML shell for the landing page
├── testing/
│   └── api_latency.py     # Optional provider latency experiment
└── tests/
    ├── test_app.py        # API contract tests
    ├── test_game_logic.py # Gameplay rule tests
    ├── test_game_logic_restriction.py # Restriction-mode rule tests
    ├── test_game_logic_blocks.py # Blocks-mode grid and chain tests
    └── test_llm_client.py # Provider selection and fallback tests
```

## Tech Stack

- Python
- Flask
- Jinja templates
- TypeScript for the interactive browser views
- esbuild for frontend bundling
- custom CSS
- system-aware light/dark theming with manual override
- Pydantic Settings for typed runtime configuration
- SQLAlchemy for local run persistence and best-score queries
- Google Gemini API via the Google Gen AI SDK
- OpenAI-compatible model access via the OpenAI Python client
- `unittest` for automated tests
- Vitest for frontend unit and DOM tests
- Playwright for end-to-end browser flows
- Biome for frontend linting and formatting checks

## Getting Started

### 1. Install dependencies

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
npm install
```

### 2. Configure environment variables

Create a `.env` file in the project root based on the starter template is also available at `.env.example`.

### 3. Run the app

```bash
npm run build
./.venv/bin/python app.py
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001), then launch `Iteration Mode` from the landing page.

Light, dark, and Cupertino modes are available. The UI follows the system light/dark preference by default, and the top-right toggle on the landing page and each game page lets you override it manually.

### 4. Rebuild the frontend after TypeScript changes

If you change anything under `frontend/src/`, rebuild the browser bundle before running or testing the app:

```bash
npm run build
```

## Running A Session

For a normal local play session:

```bash
npm run build
./.venv/bin/python app.py
```

For a validation pass before or after changes:

```bash
npm run build
npm run check:frontend
npm run lint
npm run test:frontend
./.venv/bin/python -m unittest discover -s tests
npm run test:e2e
```

If you are not using the project virtualenv, run the Python test command with
the interpreter where `requirements.txt` is installed.

## Configuration

### Vocabulary packs

Vocabulary packs are plain newline-separated `.txt` files under `assets/`.

The main webpage automatically populates the vocabulary-pack dropdown by scanning the `assets/` directory for `.txt` files, so adding a new pack there makes it available in the UI.

Current included packs:

- `assets/general_1.txt`
- `assets/lite_1.txt`
- `assets/basic_vocab.txt`
- `assets/aviation_1.txt`

If you want to change the default pack shown on startup, update this parameter in [app.py](/Users/leoliang/StudyMain/SemantrisPlus/app.py#L24):

```python
DEFAULT_VOCAB_FILE = ASSETS_DIR / "aviation_1.txt"
```

You can also override the startup default with an environment variable:

```env
SEMANTRIS_VOCAB_FILE="assets/aviation_1.txt"
```

### Typed runtime settings

The app now centralizes runtime configuration through `settings.py`.

Common `v0.4` settings include:

```env
SEMANTRIS_USE_FAKE_RANKER="0"
SEMANTRIS_CACHE_BACKEND="memory"
SEMANTRIS_CACHE_MAX_ENTRIES="512"
SEMANTRIS_PERSISTENCE_BACKEND="sqlite"
SEMANTRIS_DATABASE_URL="sqlite:///instance/semantris_plus.sqlite3"
SEMANTRIS_RUN_STORE_ENABLED="1"
SEMANTRIS_SKIP_LLM_STARTUP_PROBE="0"
```

`SEMANTRIS_USE_FAKE_RANKER="1"` is especially useful for deterministic browser testing because it avoids remote LLM dependencies entirely.

### Ranking provider

Choose the active remote provider with:

```env
SEMANTRIS_LLM_PROVIDER="gemini"
```

Supported values:

- `gemini`
- `openai`

When `gemini` mode is active, the backend uses Google’s supported `google-genai` client and requests structured JSON output with schema validation.

When `openai` mode is active, the backend uses the `openai` Python client and can target either OpenAI itself or any OpenAI-compatible endpoint through `OPENAI_BASE_URL`.

If you are debugging an OpenAI-compatible gateway, set `SEMANTRIS_DEBUG_OPENAI_LLM=1` in your shell or `.env` before starting Flask to dump the OpenAI request and raw completion payloads to stdout. Failed OpenAI validation paths also force a one-off trace automatically, which is especially useful when a gateway returns a successful envelope with `choices[0].message.content` empty or pushes output into `reasoning_content` without ever emitting a final answer.

Some OpenAI-compatible local gateways only populate `delta.content` during streaming and leave the non-streaming `message.content` empty. The backend now retries once in streaming mode when that happens so compatible local deployments can still rank words normally.

Only one remote provider is active per process. The app does not fail over from one remote provider to the other at runtime.

If the configured remote provider is unavailable, fails validation checks, or cannot initialize, the backend now falls back to a stronger local semantic fallback ranker and then to the older heuristic fallback if needed.

This local fallback path is still primarily a resilience feature rather than a full semantic replacement for the primary model.

### Persistence

`v0.4` adds local run persistence and best-score tracking.

By default, the app can store completed run summaries in SQLite and surface best-score information back to the frontend so game-over flows can report new local bests.

Persistence is intentionally local and lightweight:

- no accounts
- no cloud sync
- no multiplayer profile system

## Development

### Run tests

```bash
npm run build
npm run check:frontend
npm run lint
npm run test:frontend
./.venv/bin/python -m unittest discover -s tests
npm run test:e2e
```

If you are not using the project virtualenv, run the Python test command with
the interpreter where `requirements.txt` is installed.

### Frontend commands

- `npm run build`: compile the TypeScript frontend into the browser bundles served by Flask
- `npm run check:frontend`: run TypeScript type-checking without emitting files
- `npm run lint`: run Biome frontend checks
- `npm run test:frontend`: run frontend unit and DOM tests with Vitest
- `npm run test:e2e`: run Playwright browser flows with a local fake-ranker server

### Supporting documents

- `docs/README.md`: documentation map and rules for where new Markdown files belong
- `PRDs/README.md`: repeatable version-folder workflow for major iterations
- `PRDs/v0.5/`: current HMAS readiness and architecture modernization planning packet
- `PRDs/v0.4/`: completed technical strengthening packet
- `PRDs/v0.3.1/`: Cupertino frontend theme packet
- `docs/PRD.md`: stable product direction, scope, and engineering guardrails
- `docs/briefs/project-brief.md`: product brief for future contractors
- `docs/history/releases/v0.1-structural-cleanup.md`: implementation note for the structural cleanup release
- `docs/history/releases/v0.2-typescript-frontend-migration.md`: implementation note for the frontend TypeScript migration
- `docs/decisions/gemini-sdk-migration.md`: Gemini client migration evaluation and recommendation memo
- `docs/decisions/llm-provider-diversification.md`: provider-selection decision brief

### Code quality goals

This repo is aiming for a small but professional standard:

- clear file ownership
- testable game rules
- readable API contracts
- documented architecture
- controlled session state
- graceful failure behavior

## Known Limitations

- LLM ranking is probabilistic, so some rounds will feel less stable than deterministic puzzle logic
- the fallback ranker is much weaker than Gemini
- animation quality is improved but still not at final production polish
- there is no persistent profile, account system, or cloud leaderboard yet
- the current set of modes is still an early structured version of the larger idea

## Roadmap

Near-term priorities:

- improve end-of-run states and summaries
- strengthen visual polish and motion design
- add richer difficulty and session options
- improve fallback ranking quality
- evaluate whether `gemini-3.1-flash-lite` feels better than `gemini-2.5-flash-lite` for ranking quality

Longer-term ideas:

- seeded challenge mode
- daily runs
- local leaderboard support
- theme-aware packs and presentation
- additional Semantris-inspired game modes

## Contributing

Pull requests and experiments are welcome across:

- gameplay tuning
- UI and animation polish
- prompt engineering
- provider integrations
- fallback ranking strategies
- vocabulary packs
- tests and documentation

If you are extending the codebase structurally, start with `docs/README.md`, `docs/PRD.md`, `docs/briefs/project-brief.md`, and the relevant release notes under `docs/history/releases/` so the product and architecture direction stay consistent.

## Notes

- This project is inspired by Semantris, but it is an independent fan reimagining.
- Free-tier API access from Google AI Studio is usually enough for local experimentation.
- The project is intentionally small in scope today, but it is being shaped like a repo that can scale cleanly.
