// Generates docs/SOURCE_REGISTER.md from content/sources.json + content/knowledge.json (single source of truth).
import { readFileSync, writeFileSync } from "node:fs";
const sources = JSON.parse(readFileSync(new URL("../content/sources.json", import.meta.url)));
const kb = JSON.parse(readFileSync(new URL("../content/knowledge.json", import.meta.url)));
const esc = (s) => String(s ?? "").replace(/\|/g, "\\|").replace(/\n/g, " ");
let md = `# SOURCE_REGISTER – Quellenregister\n\n> Automatisch erzeugt aus \`content/sources.json\` und \`content/knowledge.json\` (\`node scripts/gen-source-register.mjs\`). Nicht von Hand bearbeiten.\n> Stand der Prüfung: 03.10.2026.\n\n`;
md += `## Prüfstatus – Legende\n\n- **verifiziert**: Primärquelle vollständig gelesen.\n- **teilweise_verifiziert**: Kernaussage über Websuche (Snippets) und/oder Sekundärquellen abgeglichen; Primärtext in der Arbeitsumgebung nicht abrufbar (Egress-Sperre).\n- **unverifiziert**: aus Fachwissen eingetragen, in dieser Session nicht online geprüft – darf nicht ungeprüft als gesicherte Tatsache in Lehrinhalte.\n\n`;
const count = (v) => sources.filter((s) => s.verification === v).length;
md += `Gesamt: ${sources.length} Quellen · verifiziert ${count("verifiziert")} · teilweise ${count("teilweise_verifiziert")} · unverifiziert ${count("unverifiziert")}\n\n`;
md += `## Quellen\n\n| ID | Titel | Autor/Herausgeber | Datum | Evidenz | Status | Prüfintervall | Zugriff/Anmerkung |\n|---|---|---|---|---|---|---|---|\n`;
for (const s of sources) md += `| ${s.id} | [${esc(s.title)}](${s.url})${s.doi ? ` (doi:${s.doi})` : ""} | ${esc(s.authorOrPublisher)} | ${esc(s.publishedAt ?? "–")} | ${s.evidence} | ${s.verification} | ${s.reviewIntervalDays} d | ${esc(s.accessNote)} |\n`;
md += `\n## Wissensdatenbank\n\n| ID | Thema › Unterthema | Aussage | Evidenz | Geltungsbereich | Quellen | Lektionen | Fragen | Version | Geprüft | Widerspruch |\n|---|---|---|---|---|---|---|---|---|---|---|\n`;
for (const k of kb) md += `| ${k.id} | ${esc(k.topic)} › ${esc(k.subtopic)} | ${esc(k.statement)} | ${k.evidence} | ${esc(k.scope)} | ${k.sourceIds.join(", ")} | ${k.lessonIds.join(", ") || "–"} | ${k.questionIds.join(", ") || "–"} | ${k.version} | ${k.lastCheckedAt} | ${esc(k.contradictions ?? "–")} |\n`;
writeFileSync(new URL("../docs/SOURCE_REGISTER.md", import.meta.url), md);
console.log("SOURCE_REGISTER.md written:", sources.length, "sources,", kb.length, "entries");
