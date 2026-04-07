# Semantris Plus Tech Stack Ideas

Date: 2026-04-08

Status: exploratory proposal

## Purpose

This document captures the current Semantris Plus tech stack, what it is doing well, and which replacement or augmentation paths are worth considering.

The goal is not to force a rewrite. The goal is to make future stack decisions easier by separating:

- what the repo uses now
- what is reasonable to replace
- what is more valuable to augment than replace
- what likely gives the best return for the current product phase

## Current Stack Snapshot

| Area | Current stack | Notes |
| --- | --- | --- |
| Backend app | Python + Flask 3.x | Good fit for a small server-rendered game with session-backed state and simple routing. |
| HTML rendering | Jinja templates | Keeps page shells simple and avoids unnecessary SPA complexity. |
| Frontend app | Vanilla TypeScript modules + `fetch` + DOM APIs | Lightweight and readable. The current module split is already a meaningful maintainability improvement. |
| Frontend build | `esbuild` via `scripts/build-frontend.mjs` | Fast and minimal. Good for a small repo, though less ergonomic than Vite for active frontend iteration. |
| Styling | Custom CSS in `static/css/app.css` | Good fit for a handcrafted visual identity and theme control. |
| Theme system | `localStorage` + `matchMedia` + `data-theme` | Simple and effective for light, dark, and Cupertino switching. |
| LLM providers | `google-genai` + `openai` Python client + local heuristic fallback | One of the cleaner parts of the architecture because provider logic is isolated in `llm_client.py`. |
| Config and validation | `python-dotenv` + env vars + Pydantic v2 | Solid baseline, though configuration is still somewhat hand-wired through `os.getenv`. |
| Backend tests | Python `unittest` | Covers core logic and API behavior well enough for the current phase. |
| Frontend tests | Vitest + `jsdom` | Good unit and DOM-test baseline, but no browser-level end-to-end coverage yet. |
| Dependency footprint | `requirements.txt` is broader than the app imports suggest | Worth reviewing because the runtime path appears smaller than the installed package surface. |

## Current Stack Assessment

| Topic | Assessment | Why it matters |
| --- | --- | --- |
| Overall architecture | Sensible for the repo’s current size | The project is not obviously overbuilt. |
| Backend choice | Still appropriate | Flask matches server-rendered pages, simple JSON APIs, and session-backed local play. |
| Frontend choice | Still appropriate | Vanilla TypeScript is enough because the app is interactive but not yet a large component-heavy client platform. |
| Build choice | Good but basic | `esbuild` keeps the toolchain small, but local frontend iteration could become less pleasant as the UI grows. |
| Styling approach | Strong fit | Custom CSS supports a more distinctive visual system than a default framework would. |
| LLM architecture | Strong fit | The provider boundary is already isolated, which makes future experimentation much easier. |
| Main risk | Product quality depends more on ranking quality and latency than on framework choice | A framework rewrite alone would not solve the most important gameplay risks. |
| Main maintainability gap | Dependency sprawl and missing higher-level testing | These are more actionable than a full stack rewrite right now. |

## Replacement Options

### Backend and API Layer

| Current | Replace with | Best when | Trade-off |
| --- | --- | --- | --- |
| Flask | FastAPI | Stronger typed API ergonomics, async support, automatic docs, or external client consumption become important | Better API tooling, but less natural if server-rendered Jinja pages remain central |
| Flask | Django | Accounts, persistence, admin tools, and content management become core product features | Considerably heavier than the repo currently needs |
| Python backend | NestJS / Express / Hono | A full TypeScript stack becomes a strategic goal | High migration cost with limited short-term gameplay benefit |

### Frontend Layer

| Current | Replace with | Best when | Trade-off |
| --- | --- | --- | --- |
| Vanilla TypeScript modules | React + Vite | UI complexity grows, component reuse becomes dominant, or a richer app shell is needed | More boilerplate, client complexity, and framework overhead |
| Vanilla TypeScript modules | Vue + Vite | A lighter declarative component model is desired without choosing React | Still a framework migration with added moving parts |
| Vanilla TypeScript modules | Svelte / SvelteKit | Animation-heavy UI and compact component code become a bigger priority | Better as a deliberate replatform, not a small incremental swap |

### Frontend Tooling

| Current | Replace with | Best when | Trade-off |
| --- | --- | --- | --- |
| `esbuild` | Vite | Faster day-to-day frontend iteration, HMR, and more polished local dev ergonomics are needed | More tooling surface than the current repo strictly requires |
| `unittest` | `pytest` | Better fixture support, parametrization, and test ergonomics are desired | Migration churn without direct player-facing impact |
| Custom CSS only | Tailwind / UnoCSS | Faster UI construction or utility-driven design tokens become important | Can weaken the current handcrafted visual language if used carelessly |

## Best Augmentation Paths

These are the most natural additions if the current stack stays largely intact.

### Reliability, DX, and Product Infrastructure

| Goal | Add or augment with | Why it fits well here |
| --- | --- | --- |
| Browser-level confidence | Playwright | Best next test layer for real user flows like starting runs, submitting clues, and verifying modal/theme behavior |
| Persistence and leaderboards | SQLAlchemy + SQLite or Postgres | Natural path for saved runs, leaderboards, analytics, and future progression systems |
| Faster sessions and caching | Redis | Useful for session storage, caching repeated ranking calls, and rate limiting if the app grows |
| Cleaner configuration | Pydantic Settings | Improves config clarity by replacing scattered `os.getenv` usage with typed settings objects |
| Frontend code quality | ESLint + Prettier or Biome | Complements TypeScript checks with linting and formatting discipline |
| Deployment confidence | GitHub Actions + Docker | Good for repeatable build, test, and deploy workflows |
| Error monitoring | Sentry | High-value addition for Flask exceptions and frontend runtime issues |
| LLM observability | Langfuse or Helicone | Helpful once prompt quality, fallback frequency, and latency become active tuning concerns |

### LLM and Semantic Ranking Layer

| Goal | Add or augment with | Replace or augment | Notes |
| --- | --- | --- | --- |
| Lower cost and faster turns | Redis result cache | Augment | Easiest operational win if clue and board combinations repeat or partially repeat |
| Better pre-ranking | Local embeddings with `sentence-transformers` + FAISS / Qdrant / `pgvector` | Augment | Strong fit if the game needs cheaper and more stable semantic ordering before LLM refinement |
| Stronger fallback quality | Embedding-based fallback or BM25 / RapidFuzz hybrid fallback | Augment or replace fallback | Better long-term option than relying only on a simple heuristic fallback |
| Better semantic reranking | Cross-encoder reranker on top of embeddings | Augment | Higher quality, but more compute-heavy and more complex to tune |
| Full orchestration framework | LangChain or LlamaIndex | Usually avoid for now | The current prompt flow is simple enough that these would likely add more abstraction than value |

## Replace Versus Augment: Practical View

| Question | Better answer right now | Reason |
| --- | --- | --- |
| Replace Flask? | Probably no | Flask still matches the project shape well |
| Replace the frontend with a framework? | Probably no | The current frontend is interactive, but not yet complex enough to justify a framework migration |
| Replace `esbuild`? | Maybe later | Vite is the clearest upgrade if frontend iteration becomes a daily pain point |
| Replace test stack? | Not urgent | Adding E2E coverage matters more than switching `unittest` to `pytest` immediately |
| Augment data and persistence? | Yes | Leaderboards, saved runs, and analytics likely create more product value than a framework swap |
| Augment the LLM layer? | Yes | Ranking quality, latency, and fallback resilience are more important than most framework decisions |
| Augment observability and CI? | Yes | Good return on effort as the project matures |

## Recommended Direction

| Priority | Recommendation | Why |
| --- | --- | --- |
| Highest | Keep Flask + Jinja + TypeScript for now | This stack is a good size match for the current product |
| High | Improve the LLM and semantic ranking layer before considering a major replatform | Gameplay quality depends more on ranking quality and latency than on framework choice |
| High | Add Playwright, linting, and typed config management | These improve confidence and maintainability with relatively low disruption |
| Medium | Add SQLAlchemy with SQLite or Postgres when persistence features become active scope | This is the cleanest path for leaderboard and progression features |
| Medium | Consider Vite if frontend iteration speed starts hurting | This is the most natural tooling upgrade without a full frontend rewrite |
| Low for now | Full React, Next.js, Django, or Node replatform | Likely too much cost relative to the repo’s current needs |

## Short Recommendation

The current stack is more reasonable than it may first appear. The strongest move is not a rewrite. The strongest move is targeted augmentation:

- improve semantic ranking quality and fallback quality
- add persistence when product scope needs it
- add browser-level test coverage
- improve config, linting, CI, and observability

If a larger replatform ever becomes necessary, the cleanest triggers would be:

- accounts and persistent progression becoming core product scope
- the frontend becoming significantly more component-heavy and app-like
- a deliberate decision to standardize the whole repo on TypeScript
