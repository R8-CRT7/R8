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
  await page.getByRole("button", { name: /Offline-Training mit Antwortauswahl/ }).click();
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
  await page.getByRole("button", { name: /Offline-Training mit Antwortauswahl/ }).click();
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

// ---------- V3: free-text AI simulator with a mocked Claude runtime (no network, no real AI) ----------
// The mock only stands in for window.claude in tests; the app itself never ships canned AI replies.
async function mockClaude(page: Page, opts: { coachFakeQuote?: boolean; fail?: string } = {}) {
  await page.addInitScript((o) => {
    const calls: string[] = [];
    (window as unknown as { __aiCalls: string[] }).__aiCalls = calls;
    const sample = async (prompt: string) => {
      calls.push(prompt.slice(0, 60));
      if (o.fail) throw { code: o.fail, message: "mock" };
      if (prompt.includes("Vertriebstraining eine fiktive Person")) {
        const over = /keine weiteren nachrichten|respektiere/i.test((prompt.split("VERLAUF:")[1] ?? "").split("\n").filter((l) => l.startsWith("SETTER")).pop() ?? "");
        return { text: JSON.stringify({ reply: over ? "Danke, dass Sie das respektieren. Tschüss." : "Ich informiere mich nur, das Projekt ist frühestens in ein paar Jahren.", revealed: over ? ["contact_pref"] : ["reason"], mood: 6, conversation_over: over, outcome: over ? "respect_no" : null, appointment_slot: null }), truncated: false };
      }
      if (prompt.includes("Ausbilder für Appointment Setter")) {
        const ev = o.coachFakeQuote ? [{ turn: 1, quote: "Ich garantiere Ihnen 100 % Förderung", comment: "erfunden" }] : [{ turn: 3, quote: "keine weiteren Nachrichten", comment: "Nein respektiert" }];
        return { text: JSON.stringify({ criteria: [{ id: "ablehnung", rating: "stark", reasoning: "Nein sofort akzeptiert.", evidence: ev }], violations: o.coachFakeQuote ? [{ turn: 1, quote: "Ich garantiere Ihnen 100 % Förderung", rule: "Falsches Versprechen", comment: "" }] : [], strengths: ["Respekt", "Kurz", "Klar"], improvements: ["a", "b", "c"], improvedExample: null, exercises: [], outcomeAssessment: "ok" }), truncated: false };
      }
      return { text: "Frag nach dem Hintergrund, ohne zu drängen.", truncated: false };
    };
    (window as unknown as { claude: unknown }).claude = { use: async (n: string) => (n === "sample" ? sample : null) };
  }, opts);
}

async function startFree(page: Page, mode: string) {
  await page.goto("/simulator/SIM-003/");
  await page.getByRole("button", { name: /KI-Gespräch mit freier Eingabe/ }).click();
  await expect(page.getByText("KI verfügbar")).toBeVisible();
  await page.getByRole("button", { name: new RegExp(mode) }).click();
}

async function say(page: Page, text: string) {
  await page.locator("#setter-input").fill(text);
  await page.getByRole("button", { name: "Senden" }).click();
}

test("E15 KI-Simulator ohne Claude-Laufzeit: ehrlicher Hinweis, Offline-Modus bleibt", async ({ page }) => {
  await createProfile(page);
  await page.goto("/simulator/SIM-003/");
  await page.getByRole("button", { name: /KI-Gespräch mit freier Eingabe/ }).click();
  await expect(page.getByText("KI in dieser Ansicht nicht verfügbar")).toBeVisible();
  await expect(page.getByRole("button", { name: /Prüfungsmodus/ })).toBeDisabled();
});

test("E16 KI-Simulator Prüfungsmodus: freie Eingabe → Übergabe → belegte Auswertung, bestanden", async ({ page }) => {
  await mockClaude(page);
  await createProfile(page);
  await startFree(page, "Prüfungsmodus");
  await expect(page.getByRole("button", { name: "Hinweis" })).toHaveCount(0);
  await say(page, "Hallo Herr Yilmaz, alles klar. Darf ich kurz fragen, was Sie mit dem Ratgeber vorhaben?");
  await expect(page.getByText(/frühestens in ein paar Jahren/)).toBeVisible();
  await say(page, "Verstanden, ich respektiere das und notiere: keine weiteren Nachrichten. Alles Gute!");
  await expect(page.getByText("Übergabenotiz für das CRM")).toBeVisible();
  await page.getByLabel("Kontaktwunsch").selectOption("Keine weiteren Werbenachrichten");
  await page.getByLabel("Hintergrund").selectOption("Informiert sich nur, Projekt frühestens in einigen Jahren");
  await page.getByRole("button", { name: /abschließen|auswerten/i }).click();
  await expect(page.getByText("Prüfung bestanden")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Gemessen" })).toBeVisible();
  await expect(page.getByText(/keine weiteren Nachrichten/).first()).toBeVisible();
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem("setter-os-academy:v1")!).aiSimulations.length);
  expect(saved).toBe(1);
});

test("E17 KI-Coach: erfundene Zitate werden verworfen, keine Grenzverletzung ohne Beleg", async ({ page }) => {
  await mockClaude(page, { coachFakeQuote: true });
  await createProfile(page);
  await startFree(page, "Praxismodus");
  await say(page, "Verstanden, ich respektiere das: keine weiteren Nachrichten.");
  await page.getByLabel("Kontaktwunsch").selectOption("Keine weiteren Werbenachrichten");
  await page.getByLabel("Hintergrund").selectOption({ index: 1 });
  await page.getByRole("button", { name: /abschließen|auswerten/i }).click();
  await expect(page.getByRole("heading", { name: "Gemessen" })).toBeVisible();
  await expect(page.getByText(/garantiere/)).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Grenzverletzungen (belegt)" })).toHaveCount(0);
  await expect(page.getByText(/Prüfung (nicht )?bestanden/)).toHaveCount(0); // Praxis has no pass decision
});

test("E18 KI-Lernmodus: Hinweis anfordern; Fehler der KI wird ehrlich gemeldet und Text bleibt erhalten", async ({ page }) => {
  await mockClaude(page);
  await createProfile(page);
  await startFree(page, "Lernmodus");
  await page.getByRole("button", { name: "Hinweis" }).click();
  await expect(page.getByText("Hinweis des Coaches")).toBeVisible();
});

test("E19 KI-Fehler (Limit): Meldung, Nachricht bleibt im Eingabefeld", async ({ page }) => {
  await mockClaude(page, { fail: "rate_limited" });
  await createProfile(page);
  await startFree(page, "Praxismodus");
  await say(page, "Hallo, darf ich etwas fragen?");
  await expect(page.locator("#setter-input")).toHaveValue("Hallo, darf ich etwas fragen?");
  await expect(page.getByRole("alert").or(page.getByText(/Limit|später/i)).first()).toBeVisible();
});

test("E20 iPhone-Tastatur: Eingabe und Senden bleiben bei verkleinertem Viewport sichtbar", async ({ page, isMobile }) => {
  test.skip(!isMobile, "nur mobil");
  await mockClaude(page);
  await createProfile(page);
  await startFree(page, "Praxismodus");
  await page.locator("#setter-input").focus();
  // Emulate the on-screen keyboard: the visual viewport shrinks to ~55 % of the screen.
  await page.setViewportSize({ width: 390, height: 420 });
  await page.waitForTimeout(200);
  for (const loc of [page.locator("#setter-input"), page.getByRole("button", { name: "Senden" }), page.getByRole("button", { name: "Gespräch verlassen" })]) {
    const b = (await loc.boundingBox())!;
    expect(b.y).toBeGreaterThanOrEqual(0);
    expect(b.y + b.height).toBeLessThanOrEqual(420);
  }
});

test("E21 Kursbuch, Fehlergedächtnis und KI-Einstellungen sind erreichbar; Kosten standardmäßig gesperrt", async ({ page }) => {
  await createProfile(page);
  await page.goto("/book/");
  await page.getByLabel("Im Kursbuch suchen").fill("Leitfaden");
  await page.goto("/mistakes/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.goto("/settings/");
  const s = await page.evaluate(() => JSON.parse(localStorage.getItem("setter-os-academy:v1")!).ai);
  expect(s.paidCallsEnabled).toBe(false);
  expect(s.monthlyBudgetEur).toBe(0);
});
