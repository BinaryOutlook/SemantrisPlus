# Documentation Map

This repository keeps Markdown files grouped by purpose so the repo root stays clean and future contributors can tell where a new document belongs.

## Start Here

- `README.md`: repo overview, setup, commands, and current structure
- `docs/PRD.md`: stable product direction, scope, and engineering guardrails
- `PRDs/README.md`: versioned iteration workflow for major product passes
- `CHANGELOG.md`: curated shipped milestones

## Documentation Layout

- `docs/briefs/`: orientation briefs for future helpers and contractors
- `docs/decisions/`: durable architectural decisions, migration records, and implementation outcomes worth preserving
- `docs/proposals/`: exploratory or implementation-planning documents that are not the canonical product foundation
- `docs/history/releases/`: completed milestone notes and release-era writeups
- `PRDs/vX.Y/`: canonical iteration packets for major planned work
- `PRDs/references/`: reference-only source material that informs a PRD packet but is not itself the canonical version folder

## Placement Rules

- Update `docs/PRD.md` when durable product direction, scope, or maintainability guardrails change.
- Use `PRDs/vX.Y/` when defining a major iteration with goals, acceptance criteria, and a paired demo artifact.
- Put completed milestone notes in `docs/history/releases/`.
- Put durable migration or architecture decisions in `docs/decisions/`.
- Put exploratory briefs, assessments, or future-facing implementation notes in `docs/proposals/`.
- Keep the repo root limited to entry-point docs such as `README.md`, `CHANGELOG.md`, `AGENTS.md`, and required tooling/config files.

## Practical Rule Of Thumb

If a Markdown file does not need to be the first thing someone sees when opening the repo, it probably belongs under `docs/` or `PRDs/`, not at the root.
