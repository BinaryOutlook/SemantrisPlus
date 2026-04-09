import { defineConfig } from "@playwright/test";

const port = Number(process.env.PORT ?? "5001");
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL,
    headless: true,
  },
  webServer: {
    command: "./.venv/bin/python app.py",
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    env: {
      PORT: String(port),
      FLASK_DEBUG: "0",
      SEMANTRIS_USE_FAKE_RANKER: "1",
      SEMANTRIS_SKIP_LLM_STARTUP_PROBE: "1",
      SEMANTRIS_PERSISTENCE_BACKEND: "none",
      SEMANTRIS_RUN_STORE_ENABLED: "0",
    },
  },
});
