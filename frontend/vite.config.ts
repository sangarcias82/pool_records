/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: the SPA runs on :5173 and proxies /api to FastAPI so the session cookie stays same-origin.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
    // `npm run test:cov` (used by ../for_testing --cov): the shared logic in src/lib must stay >= 90% covered.
    // Pages are React components without component tests; they are checked in the browser (see README).
    coverage: {
      provider: "v8",
      include: ["src/lib/**/*.ts"],
      exclude: ["src/lib/**/*.test.ts"],
      reporter: ["text"],
      thresholds: { lines: 90, branches: 90, functions: 90, statements: 90 },
    },
  },
});
