# Gemini Migration Evaluation for Semantris Plus

Date: 2026-03-23

Implementation status: completed in the repository after this evaluation.

## Executive Summary

Semantris Plus should migrate from the deprecated `google-generativeai` Python SDK to the current `google-genai` client, but this should be treated as a contained maintenance refactor, not a large platform rewrite.

My recommendation is:

- move now
- keep the scope tight
- use the migration to improve response reliability with structured outputs
- avoid over-investing in advanced features that do not materially help this game yet

Why I recommend moving:

- Google states that support for the legacy Python SDK ended on November 30, 2025.
- As of March 23, 2026, this repo is therefore using an unsupported primary LLM client.
- The codebase is already structured well for this change: the integration is concentrated in `llm_client.py`, with one additional Gemini usage in `testing/api_latency.py`.
- The strongest benefit for this repo is reliability and future support, not a dramatic leap in raw ranking quality.

Expected effort for this repository:

- basic migration: about 0.5 to 1 engineer day
- safer migration with tests, docs, and a short validation pass: about 1 to 2 engineer days

## Current Codebase Snapshot

I reviewed the repo structure, README, main app flow, tests, and Gemini integration points.

### Where Gemini currently lives

| File | Current role | Migration impact |
| --- | --- | --- |
| `llm_client.py` | Main provider integration, prompting, parsing, fallback behavior | Primary migration file |
| `testing/api_latency.py` | Ad hoc Gemini/OpenAI latency comparison script | Secondary migration file |
| `requirements.txt` | Pins `google-generativeai==0.8.6` | Replace dependency |
| `README.md` | Documents Gemini setup and default model | Update install/setup/model guidance |
| `app.py` | Consumes `build_ranker_from_env()` and `RankingResult` | Likely minimal or no change |
| `tests/test_app.py` | API contract coverage with dummy ranker | Probably unchanged |
| `tests/test_game_logic.py` | Game-rule coverage | Unchanged |
| Frontend files and templates | UI only | No Gemini migration work needed |

### What the main integration does today

`llm_client.py` currently:

- imports `google.generativeai`
- configures the SDK with `genai.configure(api_key=...)`
- creates `genai.GenerativeModel(...)`
- sends a plain text prompt with `generate_content`
- reads `response.text`
- manually tries to recover JSON or line-based output
- validates that the model returned a permutation of the board words
- falls back to a local heuristic ranker on any failure

This is actually a good place to be structurally. The provider boundary already exists, so we do not need to rewrite the Flask routes, gameplay engine, or frontend.

### Baseline repo condition

The existing test suite passes locally with:

```bash
python3 -m unittest discover -s tests
```

However, that run emits a `FutureWarning` at import time from `google.generativeai`, stating that all support for the package has ended and that projects should switch to `google.genai`.

## What Has Changed on Google’s Side

Based on Google’s current official documentation:

- the new Python package is `google-genai`
- the old `google-generativeai` package is a legacy SDK
- Google strongly recommends migration to the Google GenAI SDK
- the new SDK is GA
- the new SDK uses a central `Client` object instead of the older implicit `GenerativeModel`-centric pattern
- both the Gemini Developer API and Vertex AI Gemini API are accessible through the same unified SDK

There is also a second repo-specific issue: this project currently defaults to the preview model string `gemini-2.5-flash-lite-preview-09-2025`. Google’s current models documentation says preview model versions can be deprecated with at least two weeks notice, while stable model names are what most production apps should use.

For this repo, that means there are really two modernization tasks:

1. move off the deprecated SDK
2. stop defaulting to a preview model for production-like use

## Overall Migration Steps

This is the practical migration plan I would use for Semantris Plus.

### 1. Replace the Python dependency

Update `requirements.txt` to remove the legacy package and add the new one:

- remove `google-generativeai`
- add `google-genai`

During cleanup, also review whether legacy-support packages such as `google-ai-generativelanguage` are still needed directly by this repo. If they are only transitive leftovers, they should be dropped to reduce dependency noise.

### 2. Refactor `llm_client.py` to use `genai.Client()`

The old pattern is roughly:

```python
import google.generativeai as genai

genai.configure(api_key=api_key)
model = genai.GenerativeModel(model_name=...)
response = model.generate_content(prompt)
```

The new pattern should become:

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model=model_name,
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=512,
    ),
)
```

This is the center of the migration.

### 3. Switch ranking output to structured JSON instead of best-effort text parsing

This is the single biggest quality improvement we can capture while touching the integration.

Right now the app asks for JSON in the prompt, then manually strips code fences, hunts for JSON fragments, falls back to line parsing, and only then validates the result. That works, but it is defensive plumbing around an unreliable output contract.

With the new SDK, we should define a schema for:

```json
{"ranked_words": ["..."]}
```

and request structured output using:

- `response_mime_type="application/json"`
- `response_schema=...` or `response_json_schema=...`

For this repo, the cleanest approach is probably a tiny Pydantic model, because `pydantic` is already present in the dependency set.

### 4. Keep semantic validation even after adopting structured outputs

This part is important: structured outputs improve syntax and shape, but they do not guarantee business correctness.

We should still validate that:

- every board word appears exactly once
- there are no duplicates
- there are no unknown words
- canonical casing is preserved

So the migration should simplify the parser, not remove validation discipline.

### 5. Update the default model choice

The current default model is:

- `gemini-2.5-flash-lite-preview-09-2025`

I would recommend changing the default to a stable model name. The best choices for this project are:

- `gemini-2.5-flash-lite` if cost and latency are the priority
- `gemini-2.5-flash` if ranking quality is more important than minimal cost

For continuity with the current intent of the project, `gemini-2.5-flash-lite` is the natural stable replacement.

### 6. Migrate the latency helper script too

`testing/api_latency.py` also imports `google.generativeai` and constructs a legacy `GenerativeModel`.

That script should be migrated at the same time so the repo does not keep a second stale SDK path around. Otherwise the main app would be modernized while the benchmark script still teaches the old pattern.

### 7. Add direct tests for the LLM client boundary

Right now the test suite covers:

- game rules
- route behavior

It does not directly cover:

- structured response parsing
- primary-ranker failure behavior
- fallback warnings
- invalid ranking permutations

This migration is a good time to add focused unit tests for `llm_client.py`, especially because that file is where the whole change is concentrated.

### 8. Update docs and setup instructions

The README should be refreshed to:

- reference the current `google-genai` client
- document the updated default model
- explain that the old SDK has been retired
- keep the same `GEMINI_API_KEY` environment variable unless we intentionally redesign config naming

I would also update the run instructions to mention `python3` if that is the expected interpreter in the target environment, since local test execution on this machine required `python3` rather than `python`.

### 9. Do a short rollout verification pass

After migration:

- run unit tests
- run one or two manual turns against the live app
- confirm that valid rankings still reach gameplay correctly
- confirm that fallback still works when the provider path is broken
- optionally run the latency script once to compare old expectations against the new client

## What We Do Not Need to Change

This is where I think we can save unnecessary effort.

We do not need to:

- rewrite `app.py`
- rewrite `game_logic.py`
- change the frontend architecture
- redesign session state
- adopt Vertex AI immediately
- introduce streaming, files, tools, chats, or multimodal features just because the new SDK supports them

This repo was already refactored to isolate provider logic. We should use that design advantage instead of turning a focused SDK swap into a generalized platform project.

## Benefits of Moving

### 1. The biggest benefit is supportability, not novelty

This is the strongest reason to move.

Remaining on `google-generativeai` means the project’s primary ranking path depends on a library whose support ended on November 30, 2025. That creates avoidable risk around:

- future compatibility issues
- unresolved bugs
- stale examples and docs
- onboarding friction for future contributors

For a repo whose core mechanic depends on one provider call per turn, this matters a lot. If the provider path becomes brittle, the game silently degrades toward the local heuristic fallback, which is explicitly weaker than Gemini.

### 2. Structured outputs are genuinely useful for this game

This is the most important technical upside for Semantris Plus specifically.

The current app asks the model for JSON but still has to defensively scrape text. The new SDK’s structured output support lets us request a JSON object that conforms to a schema. That should reduce:

- malformed responses
- code-fence cleanup hacks
- accidental prose around the JSON
- fallback usage caused by formatting errors

This does not guarantee better semantic ranking, but it should improve ranking-path reliability.

### 3. The new client architecture is cleaner for future maintainers

The new SDK centers everything around one `Client` object and returns typed response objects. That is easier to reason about than mixing global configuration and ad hoc model instances.

For a contractor-friendly repo, this helps. Someone opening the project later will see a modern, officially documented client pattern instead of a retired one.

### 4. It keeps the door open to Vertex AI with less future churn

Even if this project stays on the Gemini Developer API for now, the new SDK makes future migration to Vertex AI much smaller because the same client library supports both modes.

That is not an immediate gameplay benefit, but it is a strategic architecture benefit.

### 5. It gives access to newer platform capabilities if the project expands

The new SDK exposes features such as:

- structured outputs
- async clients
- streaming
- files
- caching
- token counting
- built-in tools

Most of those are not mandatory for the current arcade loop, but they are useful if Semantris Plus later grows into:

- themed runs backed by large documents
- richer analytics or token budgeting
- multimodal packs
- agentic content tooling

### 6. It encourages a more production-safe model selection policy

The migration is a natural time to move from a preview model default to a stable model default. That reduces the chance of avoidable breakage from preview-model turnover.

## Benefits That Are Real but Limited for This Repo

To avoid overselling the project:

- The SDK migration alone will not make the game dramatically smarter.
- Ranking quality is influenced more by model selection, prompt design, and validation than by the client library itself.
- Context caching is probably not a major win right now because turn prompts are short and highly variable.
- Streaming is not essential for a short ranking response unless we want more visible “thinking” UX later.
- Advanced tool use is not needed for the current core loop.

So the decision case is not “migrate because it unlocks everything.” The better case is:

- migrate because the current SDK is retired
- capture structured-output reliability while we are there
- keep the rest of the system stable

## Risks and Costs of Migration

The real costs are modest, but they are not zero.

### Expected risks

- subtle response-shape differences between old and new client objects
- schema design mistakes during the first structured-output implementation
- possible model-behavior differences if we also switch from preview to stable model names
- missing test coverage if we migrate without adding `llm_client.py` tests

### Expected engineering cost

For this repository, the work is concentrated enough that I would not classify it as “many resources.”

I would classify it as:

- small maintenance project
- medium confidence
- low blast radius

The largest practical risk is not the code change itself. It is under-testing the provider boundary after the code change.

## If We Choose Not to Move

If the repo stays on the old SDK, the likely outcome is not immediate catastrophic failure. The likely outcome is a slow accumulation of maintenance risk:

- the primary provider path remains unsupported
- future contributors learn from outdated patterns
- preview-model drift remains in the default configuration
- any future Gemini-side incompatibility could push the app onto fallback ranking more often

Because the game has a heuristic fallback, the app may continue to “work,” but the experience would degrade in exactly the area that makes the project special: semantic ranking quality.

## Recommendation

My final recommendation is:

- yes, migrate
- do it now rather than later
- keep it scoped as a focused provider modernization task

If I were coordinating the work, I would approve the migration on this basis:

- it is now operationally justified because the old SDK is already out of support
- it is technically low-risk because the provider boundary is isolated
- it brings one high-value improvement for this repo: structured response reliability
- it does not require a broader architecture rewrite

## Suggested Implementation Plan

### Phase 1: Must-do

- swap `google-generativeai` for `google-genai`
- refactor `llm_client.py`
- add structured output schema for ranked words
- keep permutation validation
- change default model to a stable model
- migrate `testing/api_latency.py`
- update README

### Phase 2: Strongly recommended

- add `llm_client.py` unit tests
- improve startup/error visibility if the primary Gemini client fails to initialize
- run a short manual ranking and latency verification pass

### Phase 3: Optional follow-up

- evaluate whether `gemini-2.5-flash` feels better than `gemini-2.5-flash-lite` for ranking quality
- consider token-count instrumentation if cost monitoring becomes important
- consider Vertex-ready configuration only if enterprise deployment becomes a real target

## Bottom Line

This repo should migrate, but not because the new SDK is fashionable.

It should migrate because:

- the current SDK is already retired
- the app’s core mechanic depends on that SDK
- the migration scope is small in this codebase
- the new SDK gives us a cleaner and more reliable output contract right where this game needs it most

That makes this a good investment, but a contained one.

## Source Links

- Google migration guide: [Migrate to the Google GenAI SDK](https://ai.google.dev/gemini-api/docs/migrate)
- Google Python SDK docs: [Google Gen AI SDK documentation](https://googleapis.github.io/python-genai/)
- Google structured outputs guide: [Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output)
- Google model docs: [Gemini models](https://ai.google.dev/gemini-api/docs/models)
- Google Developer API vs Vertex AI guidance: [Gemini Developer API vs. Vertex AI](https://ai.google.dev/gemini-api/docs/migrate-to-cloud)
- Legacy Python SDK archive notice: [Deprecated Google AI Python SDK for the Gemini API](https://github.com/google-gemini/deprecated-generative-ai-python)
