# Semantris Plus Tech Stack Ideas

Date: 2026-04-09

Status: exploratory proposal for remaining future ideas

Implemented `v0.4` changes are now tracked separately in `docs/history/v0.4_techstack_change.md`.

This proposal should now be read as the list of still-open tech-stack directions that remain available for a future version.

## Purpose

This document captures the current Semantris Plus tech stack after the `v0.4` implementation pass and keeps only the tech-stack ideas that still remain open for future work.

The goal is not to force a rewrite. The goal is to preserve a shortlist of future stack directions that may still be worth pursuing later.

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
| Config and validation | `python-dotenv` + Pydantic Settings + typed runtime config | `v0.4` moved config into a centralized typed settings layer. |
| Backend tests | Python `unittest` | Covers core logic and API behavior well enough for the current phase. |
| Frontend tests | Vitest + `jsdom` + Playwright | The repo now has both unit/DOM coverage and browser-level flow coverage. |
| Persistence | SQLAlchemy + SQLite default run store | Local completed-run persistence and best-score lookup now exist. |
| Frontend quality tooling | Biome | The repo now has a formal frontend lint/check command. |
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
| Main maintainability gap | Dependency sprawl, deeper observability, and more advanced semantic infrastructure | The biggest easy wins from `v0.4` are already in place. |

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

## Remaining Augmentation Paths

These are the most natural additions that still remain open after `v0.4`.

### Reliability, DX, and Product Infrastructure

| Goal | Add or augment with | Why it fits well here |
| --- | --- | --- |
| Redis infrastructure | Redis | Useful if the repo wants a stronger cache/session backend beyond the current in-memory cache |
| Persistence scale-up | Postgres behind the existing SQLAlchemy layer | Natural next step if the local run store grows beyond SQLite-only usage |
| Deployment confidence | GitHub Actions + Docker | Good for repeatable build, test, and deploy workflows |
| Error monitoring | Sentry | High-value addition for Flask exceptions and frontend runtime issues |
| LLM observability | Langfuse or Helicone | Helpful once prompt quality, fallback frequency, and latency become active tuning concerns |

### LLM and Semantic Ranking Layer

| Goal | Add or augment with | Replace or augment | Notes |
| --- | --- | --- | --- |
| Lower cost and faster turns | Redis-backed semantic cache | Augment | Natural next step beyond the current in-memory request cache |
| Better pre-ranking | Local embeddings with `sentence-transformers` + FAISS / Qdrant / `pgvector` | Augment | Strong fit if the game needs cheaper and more stable semantic ordering before LLM refinement |
| Stronger fallback quality | Embedding-based fallback or BM25 / RapidFuzz hybrid fallback | Augment or replace current fallback | `v0.4` improved fallback quality, but did not add embedding-backed fallback infrastructure |
| Better semantic reranking | Cross-encoder reranker on top of embeddings | Augment | Higher quality, but more compute-heavy and more complex to tune |
| Full orchestration framework | LangChain or LlamaIndex | Usually avoid for now | The current prompt flow is simple enough that these would likely add more abstraction than value |

## Replace Versus Augment: Practical View

| Question | Better answer right now | Reason |
| --- | --- | --- |
| Replace Flask? | Probably no | Flask still matches the project shape well |
| Replace the frontend with a framework? | Probably no | The current frontend is interactive, but not yet complex enough to justify a framework migration |
| Replace `esbuild`? | Maybe later | Vite is the clearest upgrade if frontend iteration becomes a daily pain point |
| Replace test stack? | Not urgent | Playwright and linting now exist, so test-stack replacement is even less urgent |
| Augment data and persistence further? | Maybe later | The local run store exists now; future work is more about scale or richer data than initial adoption |
| Augment the LLM layer further? | Yes | Ranking quality, latency, and observability still matter more than most framework decisions |
| Augment observability and CI? | Yes | Good return on effort as the project matures |

## Remaining Recommended Direction

| Priority | Recommendation | Why |
| --- | --- | --- |
| Highest | Keep Flask + Jinja + TypeScript for now | This stack still matches the current product shape well |
| High | Deepen the semantic ranking layer before considering a major replatform | More advanced retrieval, reranking, or observability is a higher-value next move than a frontend rewrite |
| High | Add CI/CD and observability | The repo now has local commands worth automating and monitoring |
| Medium | Scale the current persistence and cache layers if product scope demands it | The foundations now exist, so future work can build on them rather than reintroducing them |
| Medium | Consider Vite if frontend iteration speed starts hurting | This remains the most natural tooling upgrade without a full frontend rewrite |
| Low for now | Full React, Next.js, Django, or Node replatform | Likely too much cost relative to the repo’s current needs |

## Short Recommendation

After `v0.4`, the current stack is stronger and more rounded than before. The next useful moves are no longer the initial infrastructure pass. The next useful moves are targeted follow-on improvements:

- deepen semantic ranking quality with more advanced local or hybrid infrastructure
- add observability and CI/CD around the now-stable local toolchain
- scale the cache and persistence layers only if product scope actually demands it
- evaluate Vite only if frontend iteration becomes meaningfully painful

If a larger replatform ever becomes necessary, the cleanest triggers would be:

- accounts and persistent progression becoming core product scope
- the frontend becoming significantly more component-heavy and app-like
- a deliberate decision to standardize the whole repo on TypeScript
