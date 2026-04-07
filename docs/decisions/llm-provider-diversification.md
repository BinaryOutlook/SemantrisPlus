# LLM Provider Diversification Implementation Brief

Date: 2026-03-24

Status: implemented in the repository; retained as the decision brief for the current provider-selection model.

## Executive Summary

Semantris Plus should support two mutually exclusive remote LLM modes:

- `gemini`: use Google Gen AI via `google-genai`
- `openai`: use the `openai` Python client against either OpenAI itself or an OpenAI-compatible endpoint

The active remote provider should be selected through one simple runtime switch visible in `app.py`, with all credentials and provider-specific model/endpoint values stored in `.env`.

The most important behavioral requirement is this:

- when Gemini mode is active, the app must only use the Google Gen AI client
- when OpenAI mode is active, the app must only use the OpenAI Python client
- the app must not mix remote providers inside one run
- the only fallback should remain the existing local heuristic ranker

This brief is written so another AI coding agent can implement the change with minimal ambiguity.

## Why This Change Is Worth Doing

The current architecture is already close to supporting this cleanly:

- `app.py` only depends on a provider-agnostic `RANKER`
- `game_logic.py` does not know anything about providers
- the frontend already consumes a stable JSON turn/state API
- `llm_client.py` already contains a useful provider boundary and fallback logic

That means this is not a game-loop rewrite. It is a provider-expansion and configuration refactor centered mostly in `llm_client.py`, with small wiring changes elsewhere.

## Primary Goals

- Keep Gemini fully supported through `google-genai`
- Add an OpenAI-client-based provider path for OpenAI-compatible endpoints
- Select exactly one remote provider mode at startup
- Keep the existing gameplay API contract stable
- Keep the heuristic fallback behavior
- Make configuration obvious and low-friction
- Keep the code easy to extend later if more providers are added

## Non-Goals

- No multi-provider routing, voting, or load balancing
- No automatic failover from Gemini to OpenAI or OpenAI to Gemini
- No frontend redesign
- No session model redesign
- No streaming support
- No migration to async code
- No attempt to generalize every possible LLM feature beyond this ranking task

## Current Snapshot

As of this brief:

- `app.py` calls `build_ranker_from_env()` and stores the result in `RANKER`
- `llm_client.py` contains:
  - `GeminiRanker`
  - `HeuristicRanker`
  - `ResilientRanker`
  - parsing and validation helpers
  - environment-based Gemini bootstrap
- startup probe messages are Gemini-specific in wording
- `testing/api_latency.py` already contains an ad hoc OpenAI client example, but it is not integrated with the app architecture and uses inconsistent env naming
- `requirements.txt` includes `google-genai` but not the main `openai` dependency for application runtime

## Required End State

After implementation, the runtime model should look like this:

1. `app.py` decides the active provider name once at startup.
2. `build_ranker_from_env(provider_name=...)` builds the correct remote ranker for that provider.
3. `ResilientRanker` wraps that selected remote ranker plus the local heuristic fallback.
4. Every gameplay turn uses only the selected remote provider path.
5. If that selected provider fails, the app falls back to the heuristic ranker and returns a warning in the API payload.
6. Frontend behavior and payload shapes remain unchanged.

## Recommended Configuration Contract

### Provider selector

Add one repo-specific environment variable:

```env
SEMANTRIS_LLM_PROVIDER="gemini"
```

Supported values:

- `gemini`
- `openai`

Use lowercase normalization in code.

Reject any other value at startup with a clear `ValueError`.

### Gemini config block

Keep the current Gemini env structure:

```env
GEMINI_API_KEY="..."
GEMINI_MODEL="gemini-2.5-flash-lite"
```

### OpenAI-compatible config block

Add an OpenAI-client config block:

```env
OPENAI_API_KEY="..."
OPENAI_BASE_URL="https://api.openai.com/v1"
OPENAI_MODEL="gpt-5.2-mini"
```

Notes:

- `OPENAI_BASE_URL` should always be set explicitly in `.env`, even for official OpenAI, so the runtime contract stays obvious.
- In this repo, `openai` mode should mean "use the `openai` Python client" rather than "must target api.openai.com".
- This allows OpenAI-compatible providers such as gateway vendors or self-hosted compatible endpoints to work without changing application code.

### Optional but useful extra env vars

These are not mandatory for v1, but they are reasonable additions if the implementing agent wants a slightly stronger config surface:

```env
OPENAI_TIMEOUT_SECONDS="20"
OPENAI_MAX_RETRIES="2"
```

If these are added, default them in code so the app still works when they are absent.

## How Provider Selection Should Work In `app.py`

The user asked for easy config in `app.py`, but credentials should still live in `.env`.

The cleanest implementation is:

```python
ACTIVE_LLM_PROVIDER = os.getenv("SEMANTRIS_LLM_PROVIDER", "gemini").strip().lower()
RANKER = build_ranker_from_env(provider_name=ACTIVE_LLM_PROVIDER)
```

That gives:

- one obvious switch in `app.py`
- no provider-specific logic in route handlers
- no secrets in source code

Do not scatter provider branching throughout the request flow. The branch should happen once at ranker construction time.

## Why OpenAI Mode Should Use `chat.completions.create`

Official OpenAI guidance now treats the Responses API as the primary OpenAI API, while Chat Completions remains supported. For this repository, the first implementation should still use `client.chat.completions.create(...)` in the OpenAI-provider path.

Reason:

- the requirement is not only "support OpenAI"
- the requirement is "support many LLM providers that expose an OpenAI-compatible API surface"
- in practice, the broadest compatibility across third-party OpenAI-style endpoints is usually on the chat-completions shape

So the design choice for this repo should be:

- Gemini mode: `google-genai`
- OpenAI mode: `openai.OpenAI(...).chat.completions.create(...)`

This is a compatibility decision, not a statement that Chat Completions is more modern than Responses.

## Prompt and Output Contract

The prompt contract should stay semantically identical across providers.

The model should receive:

- one clue
- the visible board words
- instructions to rank every word from most related to least related
- instructions to preserve exact spelling
- instructions to return ranking only

The output contract should remain:

```json
{"ranked_words": ["word1", "word2", "..."]}
```

### Gemini mode

Gemini can keep using structured JSON output with schema enforcement, because the current code already does this well.

### OpenAI-compatible mode

For the first implementation, do not depend on advanced structured-output features in the OpenAI path.

Instead:

- ask for JSON in the prompt
- read `completion.choices[0].message.content`
- parse with the existing JSON/text fallback parser
- validate the permutation strictly afterward

Reason:

- this is more portable across OpenAI-compatible providers
- semantic validation already exists in this repo
- strict provider-side schema enforcement can be revisited later if needed

## Critical Behavioral Rules

These rules should be treated as implementation requirements.

### Rule 1: single remote provider per process

If `SEMANTRIS_LLM_PROVIDER="gemini"`, the OpenAI client must not be constructed or used for ranking.

If `SEMANTRIS_LLM_PROVIDER="openai"`, the Gemini client must not be constructed or used for ranking.

### Rule 2: local heuristic fallback still applies

If the selected remote provider fails:

- invalid credentials
- timeout
- malformed output
- unknown words
- duplicate words
- empty content

then the app should fall back to the existing `HeuristicRanker`.

### Rule 3: remote-provider failover is out of scope

Do not implement behavior like:

- "Gemini failed, so try OpenAI"
- "OpenAI failed, so try Gemini"

That would make runtime behavior harder to reason about and would violate the user's request for a mode that uses only one remote API path at a time.

### Rule 4: frontend payload shape should not change

The frontend should continue receiving:

- `message`
- `resolution`
- `ranked_board`
- `new_board`
- `words_removed`
- `spawned_words`
- `target_word_before`
- `state`

Any provider diversification should stay behind the backend boundary.

## Recommended Code Design

### Keep The Refactor Tight

The best implementation path is to keep the provider expansion mostly inside `llm_client.py` instead of introducing many new modules.

That keeps the diff smaller and easier for an AI coding agent to land correctly.

Recommended approach:

- keep `llm_client.py` as the main provider boundary
- add one OpenAI-compatible provider class there
- generalize the builder and startup probe wording
- keep `app.py` wiring minimal

Do not over-refactor this into a large provider framework unless the implementing agent is explicitly asked to do more.

### Proposed Internal Types In `llm_client.py`

Keep or adapt the current structures:

- `RankingError`
- `RankingResult`
- `StartupProbeResult`
- `ResilientRanker`
- `HeuristicRanker`

Add:

- `OpenAICompatibleRanker`

Recommended small internal cleanup:

- make `ResilientRanker.primary` typed generically instead of `GeminiRanker | None`
- use either a `Protocol` or a lightweight common interface expectation:
  - `.provider`
  - `.model_name`
  - `.rank_words(clue, words)`

This can be done without adding a separate abstract base class file.

## File-By-File Implementation Plan

### 1. `requirements.txt`

Add the main OpenAI Python dependency.

Required change:

- add `openai==...`

Guidance:

- pin a specific known-good version
- do not leave it floating
- keep `google-genai`

No other dependency changes are strictly required for the first pass.

### 2. `app.py`

This file should remain mostly unchanged.

Required changes:

- add `ACTIVE_LLM_PROVIDER = os.getenv("SEMANTRIS_LLM_PROVIDER", "gemini").strip().lower()`
- change:

```python
RANKER = build_ranker_from_env()
```

to:

```python
RANKER = build_ranker_from_env(provider_name=ACTIVE_LLM_PROVIDER)
```

- keep route logic unchanged
- keep API payload shape unchanged

Optional improvement:

- if desired, print the selected provider during startup before the probe message

Do not add per-request branching inside `/api/game/turn`.

### 3. `llm_client.py`

This is the main implementation file.

### Required changes

#### A. Import and dependency wiring

Add safe import handling for `openai` similar to the current safe import for `google.genai`.

Example shape:

```python
try:
    from openai import OpenAI
except Exception:
    OpenAI = None
```

#### B. Add `OpenAICompatibleRanker`

This class should:

- expose `provider = "openai"`
- store `model_name`
- initialize `OpenAI(api_key=..., base_url=...)`
- call `client.chat.completions.create(...)`
- build a prompt equivalent to the Gemini prompt
- read `completion.choices[0].message.content`
- raise `RankingError` on empty output
- parse/validate using the existing parsing helpers

Recommended request shape:

```python
completion = self._client.chat.completions.create(
    model=self._model_name,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": rendered_user_prompt},
    ],
    temperature=0.0,
    max_tokens=512,
)
```

Use `system` rather than `developer` for wider third-party compatibility.

#### C. Reuse parsing and validation helpers

Do not create a second parsing stack just for OpenAI mode.

The following helpers should remain the shared output-validation layer:

- `_strip_code_fences`
- `_extract_json_candidate`
- `_parse_ranked_words_payload`
- `parse_ranked_words`
- `validate_ranked_words`

This is important because business correctness matters more than provider-specific response shape.

#### D. Generalize `ResilientRanker`

Change `ResilientRanker` so `primary` can be either:

- `GeminiRanker`
- `OpenAICompatibleRanker`
- `None`

The fallback behavior should remain exactly one layer:

- selected remote provider
- otherwise local heuristic fallback

#### E. Generalize `build_ranker_from_env`

Change the builder signature to:

```python
def build_ranker_from_env(provider_name: str) -> ResilientRanker:
```

Behavior:

- if `provider_name == "gemini"`, validate Gemini env and build `GeminiRanker`
- if `provider_name == "openai"`, validate OpenAI env and build `OpenAICompatibleRanker`
- else raise `ValueError`

Recommended builder helpers:

- `_build_gemini_ranker_from_env()`
- `_build_openai_ranker_from_env()`

These helpers are optional but will make the code easier to read and test.

#### F. Generalize startup probe wording

Current startup-probe messages are Gemini-specific.

Update them so the wording is provider-agnostic.

Examples of desired wording:

- `[Startup Probe] Provider reachable via gemini (gemini-2.5-flash-lite) in 412 ms. Primary provider responded successfully to the startup probe.`
- `[Startup Probe] Provider reachable via openai (gpt-5.2-mini) in 680 ms. Primary provider responded successfully to the startup probe.`
- `[Startup Probe] Provider probe skipped. OpenAI mode is not configured because OPENAI_API_KEY is missing, so the local fallback ranker was used.`

Do not hard-code "Gemini" into generic messages anymore.

#### G. Improve warning text

Warnings should identify the selected provider path clearly.

Examples:

- `Primary ranking provider failed: ...`
- `OpenAI mode is not configured because OPENAI_API_KEY is missing, so the local fallback ranker was used.`
- `OpenAI initialization failed, so the local fallback ranker was used: ...`

### Strong recommendation for prompt constants

It would be cleaner to split the current prompt into:

- a provider-neutral system instruction string
- a rendered user payload string containing the clue and word list

This is optional, but recommended because Gemini and OpenAI message formats are slightly different.

Suggested shape:

```python
SYSTEM_PROMPT = """
You are the ranking engine for an arcade word association game.
Rank the provided words from MOST related to LEAST related to the clue.

Rules:
- Use every input word exactly once.
- Preserve the original spelling of each word.
- Return the ranking result only.
""".strip()
```

and:

```python
def render_ranking_input(clue: str, words: Sequence[str]) -> str:
    ...
```

Gemini can still pass the fully rendered text prompt if desired. The key point is to keep both providers semantically aligned.

### 4. `tests/test_llm_client.py`

This file should be expanded.

Required new coverage:

- OpenAI-compatible ranker returns validated ranked words when content is valid JSON
- OpenAI-compatible ranker rejects empty content
- OpenAI-compatible ranker falls back to parser when content is plain text lines
- `build_ranker_from_env("openai")` warns correctly when `OPENAI_API_KEY` is missing
- `build_ranker_from_env("openai")` warns correctly when `OPENAI_BASE_URL` is missing, if base URL is made required
- `build_ranker_from_env("openai")` warns correctly when initialization fails
- `build_ranker_from_env("gemini")` still works
- invalid provider name raises `ValueError`
- startup probe messages no longer say "Gemini" unconditionally

Recommended fake objects:

- `FakeOpenAIChatCompletions`
- `FakeOpenAIClient`
- fake completion response with `choices[0].message.content`

Important behavioral test:

- in OpenAI mode, patch Gemini construction so the test proves it is not used
- in Gemini mode, patch OpenAI construction so the test proves it is not used

That enforces the single-provider-at-a-time rule.

### 5. `tests/test_app.py`

This file may need only small changes.

Existing route tests should continue to pass because payloads should not change.

Optional additions:

- one small test that patches `app_module.RANKER` with a dummy ranker and confirms the API still returns `last_provider`
- if the implementing agent changes startup bootstrapping meaningfully, add a focused test around provider selection initialization

Do not overcomplicate this file. Most provider logic belongs in `tests/test_llm_client.py`.

### 6. `testing/api_latency.py`

This script should be aligned with the new runtime config model.

Required cleanup:

- replace `SiliconFlow_API_KEY` with `OPENAI_API_KEY`
- replace the hard-coded SiliconFlow base URL with `OPENAI_BASE_URL`
- replace ad hoc provider naming with the same `SEMANTRIS_LLM_PROVIDER` values or at minimum document the mapping

Recommended direction:

- keep the script simple
- keep it as a manual experiment tool
- make its env names match the application env names

Do not let this script teach a different config contract than the main app.

### 7. `README.md`

This file should be updated after the code work is done.

Required updates:

- document `SEMANTRIS_LLM_PROVIDER`
- document both provider config blocks
- explain that `openai` mode means OpenAI Python client mode and may target OpenAI-compatible endpoints
- state clearly that only one remote provider is active per process
- state clearly that the heuristic fallback still exists

Recommended `.env` example section:

```env
SEMANTRIS_LLM_PROVIDER="gemini"

GEMINI_API_KEY="..."
GEMINI_MODEL="gemini-2.5-flash-lite"

OPENAI_API_KEY="..."
OPENAI_BASE_URL="https://api.openai.com/v1"
OPENAI_MODEL="gpt-5.2-mini"
```

### 8. New file: `.env.example`

This repo currently has `.env` but not an example template.

I strongly recommend adding `.env.example`.

Why:

- makes onboarding safer
- avoids people inferring config from docs only
- lets future AI agents patch config docs with less ambiguity

Contents should include:

- `SEMANTRIS_LLM_PROVIDER`
- Gemini keys/model
- OpenAI key/base URL/model
- existing app envs like `FLASK_SECRET_KEY`, `PORT`, `FLASK_DEBUG`, and `SEMANTRIS_VOCAB_FILE`

Do not put real secrets in it.

## Suggested Implementation Order

Implement in this order:

1. add `openai` to `requirements.txt`
2. refactor `llm_client.py` to support both providers behind one builder
3. wire provider selection through `app.py`
4. expand `tests/test_llm_client.py`
5. run the Python test suite
6. update `testing/api_latency.py`
7. update `README.md`
8. add `.env.example`

This order keeps the highest-risk logic under test before the docs cleanup.

## Detailed Runtime Contract

### App startup

At startup:

1. load `.env`
2. resolve `ACTIVE_LLM_PROVIDER`
3. call `build_ranker_from_env(provider_name=ACTIVE_LLM_PROVIDER)`
4. build a `ResilientRanker`
5. optionally run the startup probe using the selected provider only

If configuration is incomplete for the selected provider:

- do not crash if the existing design prefers fallback bootstrap
- instead build `ResilientRanker(primary=None, initial_warning=...)`
- allow the app to stay playable via local heuristic fallback

If the implementing agent prefers fail-fast for invalid provider names, that is good and recommended.

### During a turn

The turn flow should remain:

1. frontend sends clue
2. backend loads current board words
3. selected provider ranks words
4. parser validates the result
5. game logic resolves hit or miss
6. response JSON is returned to the frontend

No provider branching should exist in turn resolution or frontend code.

### Error Handling Expectations

The implementation should handle these cases cleanly:

- missing Gemini API key in Gemini mode
- missing OpenAI API key in OpenAI mode
- missing OpenAI base URL in OpenAI mode, if base URL is required by the implementation
- provider SDK import unavailable
- empty provider response
- JSON parse failure
- duplicate ranked words
- missing ranked words
- unknown ranked words
- client initialization failure
- API exception during request

In all of these cases, the app should still return a usable turn via heuristic fallback unless the failure happens before the request flow and the agent intentionally chooses a hard startup failure for invalid provider names.

### Recommended Naming Conventions

To keep the codebase understandable, use these provider names consistently:

- `gemini`
- `openai`
- `heuristic-fallback`

Avoid inconsistent names like:

- `OPENAI_COMPAT`
- `siliconflow`
- `gpt`
- `google`

Those may be true at the endpoint level, but the application should reason in terms of provider mode, not vendor nickname.

If a user points `OPENAI_BASE_URL` to SiliconFlow or another gateway, `last_provider` can still remain `openai`. That is fine. The API client mode is what matters here.

### Implementation Guidance For The OpenAI-Compatible Ranker

These details matter for reliability.

### Use the constructor shape supported by the OpenAI Python client

Expected client init shape:

```python
client = OpenAI(
    api_key=api_key,
    base_url=base_url,
)
```

### Keep generation parameters conservative

Recommended defaults:

- `temperature=0.0`
- `max_tokens=512`

Do not introduce aggressive creativity settings for a ranking task.

### Message structure

Recommended:

- one `system` message with the rules
- one `user` message containing clue plus word list

This is simple and portable.

### Response extraction

Assume the response path is:

```python
completion.choices[0].message.content
```

Validate that:

- `choices` exists
- there is at least one choice
- content is not empty after stripping

If content is missing or empty, raise `RankingError`.

## Acceptance Criteria

The implementation should be considered complete when all of the following are true.

### Functional acceptance

- Setting `SEMANTRIS_LLM_PROVIDER=gemini` uses Gemini only
- Setting `SEMANTRIS_LLM_PROVIDER=openai` uses OpenAI client mode only
- In both modes, the app still resolves turns correctly
- In both modes, invalid provider output falls back to the heuristic ranker
- The frontend turn flow works unchanged
- Startup probe messages are provider-generic

### Testing acceptance

- `python3 -m unittest discover -s tests` passes
- existing app-route tests still pass
- new OpenAI-provider tests pass

### Documentation acceptance

- `README.md` documents the new provider switch
- `.env.example` exists
- config names are consistent across app code, docs, and scripts

## Nice-To-Have Improvements, But Not Required For V1

- add a tiny `ProviderConfig` dataclass if config parsing grows
- add optional timeout/retry env support for the OpenAI client
- add a second OpenAI-mode parser path for future structured-output support
- surface the selected provider mode on the home page or diagnostics UI
- reuse shared config helpers inside `testing/api_latency.py`

These are reasonable follow-ups, but they should not block the first implementation.

## Explicit Instructions For A Future Coding Agent

If another coding agent implements this brief, it should optimize for:

- minimal surface-area changes
- keeping frontend payloads stable
- keeping `game_logic.py` untouched unless absolutely necessary
- concentrating most logic in `llm_client.py`
- adding tests before broad doc cleanup

It should avoid:

- inventing a heavy provider plugin framework
- changing the route payload contract
- adding remote-provider auto-failover
- forcing all providers onto one library

## Suggested Deliverables From The Coding Pass

The implementation PR or patch should include:

- updated `requirements.txt`
- updated `app.py`
- updated `llm_client.py`
- updated `tests/test_llm_client.py`
- any necessary small updates to `tests/test_app.py`
- updated `testing/api_latency.py`
- updated `README.md`
- new `.env.example`

## References

These references informed the OpenAI-client integration guidance:

- OpenAI Python library README: [https://github.com/openai/openai-python](https://github.com/openai/openai-python)
- OpenAI Chat Completions API reference: [https://platform.openai.com/docs/api-reference/chat/create](https://platform.openai.com/docs/api-reference/chat/create)

The decision to use `chat.completions.create` in OpenAI mode is an implementation recommendation for compatibility with OpenAI-style providers, not a claim that the Responses API is unavailable.
