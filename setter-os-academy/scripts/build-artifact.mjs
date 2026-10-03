// Builds artifact-dist/ with Vite, then inlines CSS + JS into one page body for a private claude.ai artifact.
import { execSync } from "node:child_process";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
execSync("npx vite build --config vite.artifact.config.mts --logLevel error", { stdio: "inherit" });
const dir = new URL("../artifact-dist/assets/", import.meta.url);
const files = readdirSync(dir);
const css = readFileSync(new URL(files.find((f) => f.endsWith(".css")), dir), "utf8");
const js = readFileSync(new URL(files.find((f) => f.endsWith(".js")), dir), "utf8").replace(/<\/script/gi, "<\\/script");
const page = `<title>SETTER OS ACADEMY</title>
<meta name="robots" content="noindex">
<style>${css.replace(/<\/style/gi, "<\\/style")}</style>
<div id="root"></div>
<script type="module">${js}</script>
`;
writeFileSync(new URL("../artifact-dist/setter-os-academy.html", import.meta.url), page);
// Local preview with a document skeleton similar to the artifact host.
writeFileSync(new URL("../artifact-dist/preview.html", import.meta.url), `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light;padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}body{margin:0;font:14px system-ui;background:#fafafa}img{max-width:100%}[hidden]{display:none!important}</style></head><body>${page}</body></html>`);
console.log("artifact page:", (page.length / 1024).toFixed(0), "KB");
