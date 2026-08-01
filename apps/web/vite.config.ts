import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  define: {
    __SHADOWGRID_PRODUCTION__: JSON.stringify(mode === "production"),
  },
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  preview: { port: 4173 },
  build: {
    sourcemap: false,
    target: "es2022",
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("cytoscape")) return "graph";
          if (id.includes("i18next")) return "i18n";
          const frameworkPackages = [
            "/@hookform/resolvers/",
            "/@tanstack/react-query/",
            "/react/",
            "/react-dom/",
            "/react-hook-form/",
            "/react-i18next/",
            "/react-router/",
            "/react-router-dom/",
            "/scheduler/",
            "/zustand/",
          ];
          const normalizedId = id.replaceAll("\\", "/");
          if (frameworkPackages.some((name) => normalizedId.includes(name))) {
            return "react";
          }
          return "vendor";
        },
      },
    },
  },
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      include: ["src/components.tsx", "src/format.ts"],
      thresholds: { lines: 60, functions: 55, branches: 50, statements: 60 },
    },
  },
}));
