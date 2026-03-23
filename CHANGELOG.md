# Changelog

All notable changes to Semantris Plus will be documented in this file.

This changelog is intentionally curated. It records meaningful project milestones rather than every small prototype iteration or internal tweak.

The format is inspired by Keep a Changelog, adapted for this repo's pace and scope.

## [Unreleased]

- No unreleased entries yet.

## [0.2.0] - 2026-03-24

### Added

- Added a TypeScript frontend source tree under `frontend/src/`.
- Added a frontend build and validation toolchain with `package.json`, `tsconfig.json`, `esbuild`, and Vitest.
- Added frontend-oriented tests for utility logic and DOM binding behavior.
- Added [`docs/V0.2.md`](/Users/leoliang/StudyMain/SemantrisPlus/docs/V0.2.md) to document the frontend migration and the new development workflow.

### Changed

- Migrated the interactive browser client from the old `static/js/game.js` path into typed TypeScript modules compiled into `static/js/game.bundle.js`.
- Updated the Flask game shell to load the compiled TypeScript bundle instead of the handwritten browser script.
- Updated project documentation so setup, architecture, and development instructions reflect the TypeScript-based frontend workflow.

### Why

- The frontend had grown beyond simple template glue and now relies on a real API contract, richer UI state, and more animation sequencing than untyped JavaScript handled comfortably.
- Moving to TypeScript was a technical necessity for safer frontend changes, clearer client-server contracts, and a more maintainable path for future UI work.

## [0.1.2] - 2026-03-24

### Changed

- Reworked the visual direction of the game UI from a retro neon HUD style to a flatter, more contemporary puzzle-product look.
- Replaced the display typography and surface language with a calmer, cleaner design system built around modern rounded panels, restrained accents, and stronger whitespace.
- Simplified the main play screen so the board is the dominant focus, with a more compact top bar, quieter support rails, and a more direct clue entry area.
- Rewrote game-facing copy to sound more human and puzzle-oriented instead of technical or sci-fi themed.

### Improved

- Made the target word more prominent by moving it closer to the board instead of burying it inside a support panel.
- Simplified the clear-zone treatment and word-chip styling so movement and ranking are easier to read at a glance.
- Refined motion and status messaging so turn resolution feels more precise and less theatrical.
- Improved mobile behavior by making the clue composer more accessible and better positioned for smaller screens.

## [0.1.0] - 2026-03-23

### Added

- Established the first maintainable project baseline for Semantris Plus.
- Added dedicated frontend asset files with `static/css/app.css` and `static/js/game.js` instead of keeping the whole frontend inside one template.
- Added automated tests for core gameplay behavior and API responses.
- Added stronger project documentation with `README.md`, `brief.md`, and [`docs/V0.1.md`](/Users/leoliang/StudyMain/SemantrisPlus/docs/V0.1.md).

### Changed

- Refactored the app away from a more tightly coupled prototype structure into clearer module boundaries.
- Moved gameplay rules into `game_logic.py` so board behavior can be tested and evolved independently of Flask routes.
- Isolated provider integration in `llm_client.py` so ranking, validation, and future provider changes are easier to manage.
- Expanded session state into a more stable frontend contract with score, turns, elapsed time, clue metadata, provider information, and vocabulary progress.
- Rebuilt the interface around clearer play areas: HUD, board, clue input, progress, and metadata.

### Fixed

- Improved word reuse handling so words do not repeat within a run until the unseen vocabulary pool is exhausted.
- Added fallback behavior and validation safeguards so malformed or failed provider output does not immediately break play.
- Improved the sequencing of reorder, removal, and word drop-in behavior to create a more stable run loop.

## Notes

- Earlier tiny prototype iterations are intentionally omitted.
- Future entries should be added under `Unreleased` first, then grouped into a versioned section when a release milestone is reached.
