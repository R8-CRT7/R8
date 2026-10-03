// Builds a single self-contained page for a private claude.ai artifact (no server, no install).
import { defineConfig } from "vite";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: path.resolve(__dirname, "src/spa"),
  base: "./",
  resolve: {
    alias: [
      { find: /^next\/link$/, replacement: path.resolve(__dirname, "src/spa/shims/link.tsx") },
      { find: /^next\/navigation$/, replacement: path.resolve(__dirname, "src/spa/shims/navigation.ts") },
      { find: /^@\//, replacement: path.resolve(__dirname, "src") + "/" },
      { find: /^@content\//, replacement: path.resolve(__dirname, "content") + "/" },
    ],
  },
  oxc: { jsx: { runtime: "automatic" } },
  define: { "process.env.NODE_ENV": JSON.stringify("production"), "process.env.NEXT_PUBLIC_ARTIFACT": JSON.stringify("1") },
  build: {
    outDir: path.resolve(__dirname, "artifact-dist"),
    emptyOutDir: true,
    assetsInlineLimit: 100_000_000,
    cssCodeSplit: false,
    modulePreload: false,
    rollupOptions: { output: { codeSplitting: false } },
  },
});
