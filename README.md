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

## Current Mode

The current playable mode is `Iteration Mode`, a tower-based arcade variant:

- the game starts with a tower of words and one highlighted target word
- the player enters a clue
- the ranking engine orders the visible words from most related to least related
- the tower is displayed so the bottom-most word is the most correlated result
- the bottom four words form the destruction zone
- if the target lands in that zone, the target and the words between it and the zone boundary are removed
- score increases by the number of removed words
- new words drop in from the top
- the session tracks time, score, turns, and vocabulary progress

## Why LLMs Here

Modern LLMs are not deterministic ranking machines, and that matters. Even at low temperature, semantic ordering can still vary.

That said, for short clue-and-word ranking tasks, modern models are strong enough to make this design space genuinely fun again. Their broader world knowledge also makes the game more flexible across themed vocab packs and future content expansions.

This repo currently uses Gemini as the primary ranking provider and includes a local heuristic fallback so the game remains playable if the model path fails.

## Project Status

Current status: `v0.2` active prototype with a modular Flask backend, a typed frontend client, and a stronger browser-side development workflow.

What is already in place:

- modularized gameplay logic instead of one monolithic server file
- explicit JSON API for session state and turns
- no-repeat word handling until the unseen pool is exhausted
- improved tower presentation and animation sequencing
- a TypeScript frontend source tree compiled into a browser bundle
- frontend type-checking and Vitest coverage for key browser-side logic
- fallback ranking path for resilience
- automated tests for gameplay rules, API behavior, and provider fallback behavior

What is still unfinished:

- final game feel polish
- richer end-of-run UX
- broader frontend test coverage across full interaction flows
- leaderboard or persistence systems
- stronger fallback ranking quality
- model selection tuning between Gemini Flash-Lite and Flash

## Architecture

This repository is now structured around clear responsibilities instead of mixing UI, session state, LLM calls, build concerns, and game rules in a single file.

### Runtime flow

1. Flask serves the HTML shell.
2. The browser loads the compiled TypeScript frontend bundle.
3. The frontend loads current session state from the JSON API.
4. The player submits a clue.
5. The backend sends the visible board to the ranking provider.
6. The ranking result is validated and converted into board mutations.
7. The frontend animates reorder, removal, collapse, and spawn events.

### Key design choices

- Gameplay rules are isolated so they can be tested without the web app.
- LLM interaction is isolated so provider changes do not require rewriting the game loop.
- The interactive frontend now lives in dedicated TypeScript modules compiled into a served browser bundle.
- Session state is explicit so the frontend can render the game from stable API payloads.
- The frontend build and validation steps are small but formalized so browser code can evolve safely.

## Repository Structure

```text
SemantrisPlus/
├── app.py                 # Flask app, route wiring, session serialization
├── game_logic.py          # Pure board/session rules
├── llm_client.py          # Google Gen AI integration, validation, fallback ranking
├── brief.md               # Contractor-facing project brief and roadmap
├── GeminiMoving.md        # Migration evaluation and decision record
├── README.md              # Project overview and setup
├── requirements.txt       # Python dependencies
├── assets/                # Vocabulary packs
│   ├── aviation_1.txt
│   ├── basic_vocab.txt
│   ├── general_1.txt
│   └── lite_1.txt
├── docs/
│   ├── V0.1.md            # Structural cleanup release note
│   └── V0.2.md            # Frontend TypeScript migration note
├── frontend/
│   └── src/               # TypeScript source for the interactive game client
├── package.json           # Frontend scripts and dependencies
├── tsconfig.json          # TypeScript compiler configuration
├── vitest.config.ts       # Frontend test configuration
├── scripts/
│   └── build-frontend.mjs # esbuild entry for browser bundle output
├── static/
│   ├── css/app.css        # Visual system and layout styling
│   └── js/game.bundle.js  # Compiled browser bundle served by Flask
├── templates/
│   └── arcade.html        # HTML shell for the game
├── testing/
│   └── api_latency.py     # Optional provider latency experiment
└── tests/
    ├── test_app.py        # API contract tests
    └── test_game_logic.py # Gameplay rule tests
```

## Tech Stack

- Python
- Flask
- Jinja templates
- TypeScript for the interactive browser views
- esbuild for frontend bundling
- custom CSS
- Google Gemini API via the Google Gen AI SDK
- `unittest` for automated tests
- Vitest for frontend unit and DOM tests

## Getting Started

### 1. Install dependencies

```bash
python3 -m pip install -r requirements.txt
npm install
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY="YOUR_API_KEY"
FLASK_SECRET_KEY="YOUR_SECRET_KEY"
```

Optional configuration:

```env
SEMANTRIS_VOCAB_FILE="assets/general_1.txt"
GEMINI_MODEL="gemini-2.5-flash-lite"
PORT="5001"
FLASK_DEBUG="1"
```

### 3. Run the app

```bash
npm run build
python3 app.py
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001), then launch `Iteration Mode` from the landing page.

### 4. Rebuild the frontend after TypeScript changes

If you change anything under `frontend/src/`, rebuild the browser bundle before running or testing the app:

```bash
npm run build
```

## Running A Session

For a normal local play session:

```bash
npm run build
python3 app.py
```

For a validation pass before or after changes:

```bash
npm run check:frontend
npm run test:frontend
python3 -m unittest discover -s tests
```

## Configuration

### Vocabulary packs

Vocabulary packs are plain newline-separated `.txt` files under `assets/`.

Current included packs:

- `assets/general_1.txt`
- `assets/lite_1.txt`
- `assets/basic_vocab.txt`
- `assets/aviation_1.txt`

To switch packs, set:

```env
SEMANTRIS_VOCAB_FILE="assets/aviation_1.txt"
```

### Ranking provider

The game currently prefers Gemini through Google’s supported `google-genai` client. The backend requests structured JSON output from Gemini and then validates that the ranking is still a correct permutation of the current board before resolving the turn.

If Gemini is unavailable, fails validation, or cannot initialize, the backend falls back to a deterministic local heuristic ranker so the session does not hard-fail.

This fallback is intentionally simple. It is a resilience feature, not a semantic replacement for the primary model.

## Development

### Run tests

```bash
npm run check:frontend
npm run test:frontend
python3 -m unittest discover -s tests
```

### Frontend commands

- `npm run build`: compile the TypeScript frontend into the browser bundle served by Flask
- `npm run check:frontend`: run TypeScript type-checking without emitting files
- `npm run test:frontend`: run frontend unit and DOM tests with Vitest

### Supporting documents

- `brief.md`: product brief for future contractors
- `docs/V0.1.md`: implementation note for the structural cleanup release
- `docs/V0.2.md`: implementation note for the frontend TypeScript migration
- `GeminiMoving.md`: migration evaluation and recommendation memo

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
- there is no persistent profile, save system, or leaderboard yet
- the current game mode is only the first structured version of the larger idea

## Roadmap

Near-term priorities:

- improve end-of-run states and summaries
- strengthen visual polish and motion design
- add richer difficulty and session options
- improve fallback ranking quality
- evaluate whether `gemini-2.5-flash` feels better than `gemini-2.5-flash-lite` for ranking quality

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

If you are extending the codebase structurally, start with `brief.md`, `docs/V0.1.md`, and `docs/V0.2.md` so the architecture direction stays consistent.

## Notes

- This project is inspired by Semantris, but it is an independent fan reimagining.
- Free-tier API access from Google AI Studio is usually enough for local experimentation.
- The project is intentionally small in scope today, but it is being shaped like a repo that can scale cleanly.
