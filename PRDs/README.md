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

Canonical iteration folders should stay directly under `PRDs/`.
Reference-only source material should live under `PRDs/references/` so imported inspiration packs do not get mixed up with the real version packets.

## Recommended workflow

1. Define the iteration scope in the PRD before coding.
2. Create a demo HTML artifact that shows the intended UX and visual direction.
3. Point the coding agent at the version folder so it can read both the PRD and the demo together.
4. After implementation, append a short change log to the bottom of the version PRD.

Reference folders may also exist for imported inspiration material or rough source assets, but the canonical iteration packet should still live under the versioned `vX.Y/` path.

## Current active planning folders

- `PRDs/v0.3.1/`

## Reference-only source folder

- `PRDs/references/v0.3.1-cupertino-source-packet/` contains the imported Cupertino source materials used to draft the `v0.3.1` packet. It is a reference folder, not the canonical iteration packet.

The stable product-wide foundation still lives in `docs/PRD.md`.
This `PRDs/` folder is for version-scoped iteration work.
