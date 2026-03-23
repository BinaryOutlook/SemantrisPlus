import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["frontend/src/__tests__/**/*.test.ts"],
  },
});
