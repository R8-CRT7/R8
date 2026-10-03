import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function createProfile(page: Page) {
  await page.goto("/start/");
  await page.getByLabel("Anzeigename").fill("Pilot");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Los geht's" }).click();
  await expect(page.getByRole("heading", { name: "Hallo Pilot" })).toBeVisible();
}

test("E01 Landing zeigt Prototyp-Hinweis und keine Verkaufsversprechen", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Nichtkommerzieller Prototyp").first()).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Learn the skill.");
  await expect(page.locator("body")).not.toContainText(/garantiert(es|e)? (Einkommen|Verdienst)/i);
});

test("E02 Registrierung verlangt Name und Datenschutzbestätigung", async ({ page }) => {
  await page.goto("/start/");
  await page.getByRole("button", { name: "Los geht's" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toContainText("Anzeigenamen");
  await page.getByLabel("Anzeigename").fill("X");
  await page.getByRole("button", { name: "Los geht's" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toContainText("Datenschutzhinweis");
});

test("E03 Geschützte Bereiche ohne Profil zeigen Hinweis statt Absturz", async ({ page }) => {
  await page.goto("/dashboard/");
  await expect(page.getByRole("heading", { name: "Noch kein Lernprofil" })).toBeVisible();
});

test("E04 Lektion: Abrufübung beantworten, abschließen, Fortschritt bleibt nach Reload", async ({ page }) => {
  await createProfile(page);
  await page.goto("/learn/M01/M01-L01/");
  const check = page.locator('article[aria-labelledby="Q-M01-001-prompt"]');
  await check.getByText("Klären, ob ein Bedarf passt").click();
  await check.getByRole("button", { name: "Sicher", exact: true }).click();
  await check.getByRole("button", { name: "Antwort prüfen" }).click();
  await expect(check.getByText("Richtig", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Lektion abschließen/ }).click();
  await expect(page).toHaveURL(/M01-L02/);
  await page.reload();
  await page.goto("/learn/M01/");
  await expect(page.getByText("1 von 8 Lektionen")).toBeVisible();
});

test("E05 Simulator: Nein respektieren → Übergabe → bestandene Auswertung", async ({ page }) => {
  await createProfile(page);
  await page.goto("/simulator/SIM-003/");
  await page.getByRole("button", { name: "Gespräch beginnen" }).click();
  await page.getByRole("button", { name: /danke für die klare Rückmeldung/ }).click();
  await expect(page.getByText("Bitte keine weiteren Nachrichten.")).toBeVisible();
  await page.getByRole("button", { name: /ich habe vermerkt: keine weiteren Nachrichten/ }).click();
  await page.getByLabel("Kontaktwunsch").selectOption("Keine weiteren Werbenachrichten");
  await page.getByLabel("Hintergrund").selectOption("Informiert sich nur, Projekt frühestens in einigen Jahren");
  await page.getByRole("button", { name: /Übergabe abschließen/ }).click();
  await expect(page.getByText(/Bestanden \(≥ 70/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Drei Stärken" })).toBeVisible();
  await page.goto("/dashboard/");
  await expect(page.getByText("Nein heißt Nein")).toBeVisible();
});

test("E06 Simulator: Druck führt zu Grenzverletzung trotz Gesprächsende", async ({ page }) => {
  await createProfile(page);
  await page.goto("/simulator/SIM-003/");
  await page.getByRole("button", { name: "Gespräch beginnen" }).click();
  await page.getByRole("button", { name: /Darf ich fragen, warum nicht/ }).click();
  await page.getByRole("button", { name: /Entschuldigung, das war zu aufdringlich/ }).click();
  await page.getByLabel("Kontaktwunsch").selectOption("Keine weiteren Werbenachrichten");
  await page.getByLabel("Hintergrund").selectOption("Nicht erfragt / unbekannt");
  await page.getByRole("button", { name: /Übergabe abschließen/ }).click();
  await expect(page.getByRole("heading", { name: "Verletzte Grenzen" })).toBeVisible();
  await expect(page.getByText("Nicht bestanden", { exact: true })).toBeVisible();
  await expect(page.getByText(/Erfundene Angaben/)).toHaveCount(0);
});

test("E07 Quiz: Regeln vorab sichtbar, erste Frage beantwortbar", async ({ page }) => {
  await createProfile(page);
  await page.goto("/quiz/M01/");
  await expect(page.getByText("Regeln (vorab festgelegt)")).toBeVisible();
  await page.getByRole("button", { name: "Quiz starten" }).click();
  await expect(page.getByText(/Frage 1 \/ \d+/)).toBeVisible();
});

test("E08 Einstellungen: heller Modus und Datenlöschung", async ({ page }) => {
  await createProfile(page);
  await page.goto("/settings/");
  await page.getByRole("button", { name: "Hell" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Löschen …" }).click();
  await page.getByRole("button", { name: "Ja, endgültig löschen" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/dashboard/");
  await expect(page.getByRole("heading", { name: "Noch kein Lernprofil" })).toBeVisible();
});

test("E09 Mobile Layout: kein horizontales Scrollen auf Kernseiten", async ({ page }) => {
  await createProfile(page);
  for (const url of ["/dashboard/", "/learn/", "/learn/M01/M01-L03/", "/simulator/SIM-001/", "/stats/", "/sources/", "/admin/"]) {
    await page.goto(url);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, url).toBeLessThanOrEqual(1);
  }
});

test("E10 Mobile Tableiste: Ziele ≥ 44 px", async ({ page, isMobile }) => {
  test.skip(!isMobile, "nur mobil");
  await createProfile(page);
  const links = page.getByRole("navigation", { name: "Hauptnavigation mobil" }).getByRole("link");
  await expect(links).toHaveCount(5);
  for (const box of await links.evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height))) expect(box).toBeGreaterThanOrEqual(44);
});

test("E11 Barrierefreiheit (axe, WCAG 2.2 AA) auf Kernseiten – dunkel und hell", async ({ page }) => {
  await createProfile(page);
  for (const theme of ["dark", "light"]) {
    await page.evaluate((t) => {
      const s = JSON.parse(localStorage.getItem("setter-os-academy:v1")!);
      s.settings.theme = t;
      localStorage.setItem("setter-os-academy:v1", JSON.stringify(s));
    }, theme);
    for (const url of ["/", "/dashboard/", "/learn/M01/M01-L04/", "/simulator/SIM-001/", "/review/", "/settings/"]) {
      await page.goto(url);
      await page.waitForTimeout(150);
      const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
      const serious = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(serious.map((v) => `${theme} ${url}: ${v.id} – ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
    }
  }
});

test("E12 Tastaturbedienung: Antwort per Tastatur auswählbar", async ({ page, isMobile }) => {
  test.skip(!!isMobile, "Desktop");
  await createProfile(page);
  await page.goto("/learn/M01/M01-L02/");
  const radio = page.locator("article", { has: page.getByRole("button", { name: "Antwort prüfen" }) }).first().getByRole("radio").first();
  await radio.focus();
  await page.keyboard.press("Space");
  await expect(radio).toBeChecked();
});

test("E13 90-Tage-Plan: starten, Tag 1 bearbeiten und abschließen, Tag 2 öffnet morgen", async ({ page }) => {
  await createProfile(page);
  await page.goto("/plan/");
  await page.getByRole("button", { name: "Plan starten – Tag 1" }).click();
  await expect(page.getByRole("heading", { name: "Tag 1 von 90" })).toBeVisible();
  for (const l of ["M01-L01", "M01-L02", "M01-L03"]) {
    await page.goto(`/learn/M01/${l}/`);
    await page.getByRole("button", { name: /Lektion abschließen/ }).click();
  }
  await page.goto("/plan/");
  await page.getByRole("button", { name: "Tag 1 abschließen" }).click();
  await expect(page.getByText("Öffnet morgen").first()).toBeVisible();
  await page.getByRole("button", { name: "Heute schon weitermachen" }).click();
  await expect(page.getByRole("heading", { name: "Tag 2 von 90" })).toBeVisible();
});

test("E14 Lektion zeigt Kursbuch, Skill-Karte und Mythos-Check", async ({ page }) => {
  await createProfile(page);
  await page.goto("/learn/M02/M02-L02/");
  await expect(page.getByText(/Kursbuch · Kapitel 2\.2/)).toBeVisible();
  await expect(page.getByText("Skill-Karte").first()).toBeVisible();
  await page.goto("/learn/M01/M01-L06/");
  await expect(page.getByText("Mythos-Check")).toBeVisible();
});
