// Captures reference screenshots (desktop + iPhone viewport) into docs/screenshots.
// Usage: npm run build && npx serve out -l 4173 & node e2e/screenshots.mjs
import { chromium, devices } from "@playwright/test";
const base = process.env.BASE ?? "http://127.0.0.1:4173";
const shots = [
  ["landing", "/"], ["dashboard", "/dashboard/"], ["lernpfad", "/learn/"], ["lektion", "/learn/M01/M01-L04/"],
  ["quiz", "/quiz/M01/"], ["simulator", "/simulator/SIM-001/"], ["statistik", "/stats/"], ["quellen", "/sources/"], ["admin", "/admin/"],
];
const browser = await chromium.launch();
for (const [kind, ctxOpts] of [["desktop", { viewport: { width: 1440, height: 900 } }], ["iphone", { ...devices["iPhone 13"], deviceScaleFactor: 2 }]]) {
  const ctx = await browser.newContext(ctxOpts);
  const page = await ctx.newPage();
  await page.goto(base + "/start/");
  await page.getByLabel("Anzeigename").fill("Emi");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Los geht's" }).click();
  await page.waitForURL(/dashboard/);
  for (const [name, url] of shots) {
    await page.goto(base + url);
    if (name === "simulator") {
      await page.getByRole("button", { name: /Offline-Training mit Antwortauswahl/ }).click();
      await page.getByRole("button", { name: "Gespräch beginnen" }).click();
      await page.getByRole("button", { name: /hier ist Ihr Ansprechpartner/ }).click();
      await page.waitForTimeout(900);
      await page.getByRole("button", { name: /gerade jetzt mit einer Wärmepumpe/ }).click();
      await page.waitForTimeout(900);
    }
    if (name === "quiz") await page.getByRole("button", { name: "Quiz starten" }).click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: `docs/screenshots/${kind}-${name}.jpg`, type: "jpeg", quality: 72, fullPage: kind === "desktop" && name !== "simulator" });
  }
  await ctx.close();
}
await browser.close();
