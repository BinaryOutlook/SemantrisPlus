# PRD Iterations

This folder stores versioned iteration packets for Semantris Plus.

Each major iteration should get its own subfolder:

```text
PRDs/
└── vX.Y/
    ├── vX.Y.md
    └── vX.Y-demo.html
```

## Required files

- `vX.Y.md`: the iteration PRD
- `vX.Y-demo.html`: a static design reference for the iteration

## Recommended workflow

1. Define the iteration scope in the PRD before coding.
2. Create a demo HTML artifact that shows the intended UX and visual direction.
3. Point the coding agent at the version folder so it can read both the PRD and the demo together.
4. After implementation, append a short change log to the bottom of the version PRD.

## Current active planning folder

- `PRDs/v0.3/`

The stable product-wide foundation still lives in `docs/PRD.md`.
This `PRDs/` folder is for version-scoped iteration work.
