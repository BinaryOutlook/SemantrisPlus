import { build } from "esbuild";

await build({
  entryPoints: ["frontend/src/game.ts"],
  outfile: "static/js/game.bundle.js",
  bundle: true,
  format: "iife",
  target: "es2020",
  sourcemap: true,
  logLevel: "info",
});
