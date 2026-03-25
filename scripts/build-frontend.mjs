import { build } from "esbuild";

await build({
  entryPoints: {
    game: "frontend/src/game.ts",
    restriction: "frontend/src/restriction.ts",
    blocks: "frontend/src/blocks.ts",
    theme: "frontend/src/theme.ts",
  },
  outdir: "static/js",
  entryNames: "[name].bundle",
  bundle: true,
  format: "iife",
  target: "es2020",
  sourcemap: true,
  logLevel: "info",
});
