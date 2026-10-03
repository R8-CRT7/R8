// KI-Schicht: Router, Kostenkontrolle, Kundensimulator (freie Eingabe), getrennter Coach, Hinweise, Prüfungsmodus.
// Uses a scripted test provider – NOT used in the product (the product never fakes AI with canned text).
import { describe, expect, it } from "vitest";
import { scenarioById } from "@/lib/content";
import { buildCoachPrompt, coachEvaluate, gates, hint, measuredEvaluation, parseCoachReport, verifyQuote } from "@/lib/ai/coachAI";
import { applySetterMessage, buildCustomerPrompt, CONTEXT_TURNS, customerTurn, parseCustomerReply, startFreeSim } from "@/lib/ai/customerAI";
import { isOpenQuestion, measure } from "@/lib/ai/metrics";
import { createRouter, DEFAULT_ROUTER, estimateCostEur, monthSpend, type SpendLog } from "@/lib/ai/router";
import { AiError, type AiProvider, type CompletionRequest } from "@/lib/ai/types";
import { initialState, migrate, recordAiSimulation } from "@/lib/store/state";

const sc = scenarioById("SIM-001")!;

function scripted(id: string, replies: (req: CompletionRequest) => string, cost: AiProvider["cost"] = { kind: "claude-plan" }, available = true): AiProvider & { calls: CompletionRequest[] } {
  const calls: CompletionRequest[] = [];
  return {
    id,
    label: id,
    cost,
    calls,
    available: async () => available,
    complete: async (req) => {
      calls.push(req);
      const text = replies(req);
      return { text, truncated: false, providerId: id, tierApplied: req.tier, inputChars: req.prompt.length, outputChars: text.length };
    },
  };
}
function router(providers: AiProvider[], cfg: Partial<typeof DEFAULT_ROUTER> = {}, log: SpendLog[] = []) {
  return createRouter({
    config: { ...DEFAULT_ROUTER, ...cfg, routes: { customer: { providers: providers.map((p) => p.id), tier: "quick" }, coach: { providers: providers.map((p) => p.id), tier: "default" }, hint: { providers: providers.map((p) => p.id), tier: "quick" } } },
    providers,
    spendLog: () => log,
    onSpend: (e) => log.push(e),
  });
}
const reply = (o: Record<string, unknown>) => JSON.stringify({ reply: "Okay.", revealed: [], mood: 5, conversation_over: false, outcome: null, appointment_slot: null, ...o });

describe("Router & Kosten", () => {
  it("A01 Erster verfügbarer Anbieter gewinnt (Fallback)", async () => {
    const down = scripted("a", () => "", { kind: "claude-plan" }, false);
    const up = scripted("b", () => reply({}));
    const r = router([down, up]);
    expect((await r.status("customer")).provider?.id).toBe("b");
  });
  it("A02 Kostenpflichtige Aufrufe sind standardmäßig gesperrt", async () => {
    const paid = scripted("proxy", () => reply({}), { kind: "per-token", inputPerMTok: 4, outputPerMTok: 20 });
    const r = router([paid]);
    await expect(r.complete({ role: "customer", prompt: "x" })).rejects.toMatchObject({ code: "budget_blocked" });
    expect(paid.calls).toHaveLength(0);
  });
  it("A03 Freigabe ohne Budget bleibt gesperrt; mit Budget erlaubt", async () => {
    const paid = scripted("proxy", () => reply({}), { kind: "per-token", inputPerMTok: 4, outputPerMTok: 20 });
    await expect(router([paid], { paidCallsEnabled: true, monthlyBudgetEur: 0 }).complete({ role: "customer", prompt: "x" })).rejects.toMatchObject({ code: "budget_blocked" });
    const log: SpendLog[] = [];
    const r = await router([paid], { paidCallsEnabled: true, monthlyBudgetEur: 5 }, log).complete({ role: "customer", prompt: "x".repeat(3500) });
    expect(r.costEur).toBeGreaterThan(0);
    expect(log).toHaveLength(1);
  });
  it("A04 Budget-Grenze stoppt weitere Aufrufe", async () => {
    const paid = scripted("proxy", () => reply({}), { kind: "per-token", inputPerMTok: 4, outputPerMTok: 20 });
    const log: SpendLog[] = [{ at: Date.now(), providerId: "proxy", role: "customer", inputChars: 0, outputChars: 0, costEur: 4.999 }];
    await expect(router([paid], { paidCallsEnabled: true, monthlyBudgetEur: 5 }, log).complete({ role: "customer", prompt: "x".repeat(40000) })).rejects.toMatchObject({ code: "budget_blocked" });
  });
  it("A05 Kostenschätzung ist nachvollziehbar (3,5 Zeichen/Token, Preis je 1M Token)", () => {
    const p = scripted("p", () => "", { kind: "per-token", inputPerMTok: 4, outputPerMTok: 20 });
    // 350.000 Zeichen = 100.000 Token Input → 0,40 USD; 35.000 Zeichen = 10.000 Token Output → 0,20 USD; ×0,92
    expect(estimateCostEur(p, 350_000, 35_000)).toBeCloseTo(0.552, 3);
    expect(estimateCostEur(scripted("c", () => ""), 1e6, 1e6)).toBe(0);
  });
  it("A06 Monatssumme zählt nur den laufenden Monat", () => {
    const now = new Date(2026, 9, 15).getTime();
    expect(monthSpend([{ at: new Date(2026, 8, 30).getTime(), providerId: "p", role: "coach", inputChars: 0, outputChars: 0, costEur: 3 }, { at: now, providerId: "p", role: "coach", inputChars: 0, outputChars: 0, costEur: 1 }], now)).toBe(1);
  });
  it("A07 Keine KI verfügbar → klarer Fehler, kein vorgetäuschter Text", async () => {
    await expect(router([scripted("x", () => "", { kind: "claude-plan" }, false)]).complete({ role: "customer", prompt: "x" })).rejects.toMatchObject({ code: "unavailable" });
  });
  it("A08 Modellwechsel: Rolle nutzt die konfigurierte Stufe", async () => {
    const p = scripted("p", () => reply({}));
    const r = router([p]);
    await r.complete({ role: "coach", prompt: "x" });
    await r.complete({ role: "customer", prompt: "y" });
    expect(p.calls.map((c) => c.tier)).toEqual(["default", "quick"]);
  });
});

describe("Kundensimulator – freie Eingabe", () => {
  it("K01 Prompt enthält Persona, Regeln und den Verlauf – aber keinen Bewertungsmaßstab", () => {
    const st = applySetterMessage(startFreeSim(sc, "praxis"), "Hallo Frau Kaya, passt es kurz?");
    const p = buildCustomerPrompt(sc, st);
    expect(p).toContain("Selin Kaya");
    expect(p).toContain("SETTER: Hallo Frau Kaya, passt es kurz?");
    expect(p).toContain("Arbeite NICHT auf einen Termin hin");
    expect(p).not.toMatch(/Gewicht|Rubrik|Gate/);
  });
  it("K02 Freitext wird übernommen, Antwort und Offenlegungen werden angewendet", async () => {
    const p = scripted("p", () => reply({ reply: "Unsere Gasheizung ist 24 Jahre alt.", revealed: ["need", "erfunden"], mood: 6 }));
    const { state } = await customerTurn(router([p]), sc, startFreeSim(sc, "praxis"), "Was hat Sie dazu gebracht, sich jetzt zu melden?");
    expect(state.transcript.at(-2)).toEqual({ role: "setter", text: "Was hat Sie dazu gebracht, sich jetzt zu melden?" });
    expect(state.transcript.at(-1)!.text).toContain("24 Jahre");
    expect(state.revealed).toEqual(["need"]); // unknown keys are discarded
    expect(state.mood).toBe(6);
  });
  it("K03 Ungültiges Format → Fehler, kein Zustandswechsel", async () => {
    const p = scripted("p", () => "Ich bin ein Kunde und antworte ohne JSON");
    const st = startFreeSim(sc, "praxis");
    await expect(customerTurn(router([p]), sc, st, "Hallo")).rejects.toMatchObject({ code: "invalid_output" });
    expect(st.transcript).toHaveLength(1);
  });
  it("K04 Gesprächskontext wird gekürzt, Instruktionen bleiben", () => {
    let st = startFreeSim(sc, "praxis");
    for (let i = 0; i < 40; i++) st = { ...st, transcript: [...st.transcript, { role: i % 2 ? "customer" : "setter", text: `Nachricht ${i}` }] };
    const p = buildCustomerPrompt(sc, st);
    expect(p).toContain("frühere Nachrichten gekürzt");
    expect(p).not.toContain("Nachricht 0\n");
    expect(p).toContain("Nachricht 39");
    expect(p.split("\n").filter((l) => l.startsWith("SETTER:") || l.startsWith("KUNDE:")).length).toBe(CONTEXT_TURNS);
  });
  it("K05 Bereits preisgegebene Fakten werden im nächsten Prompt markiert (Konsistenz)", () => {
    const st = { ...startFreeSim(sc, "praxis"), revealed: ["need"] };
    expect(buildCustomerPrompt(sc, st)).toMatch(/need \|.*BEREITS PREISGEGEBEN/);
  });
  it("K06 Gesprächsende mit Ergebnis wird übernommen; Ende ohne Ergebnis = lost", () => {
    expect(parseCustomerReply(reply({ conversation_over: true, outcome: "respect_no" }), sc).outcome).toBe("respect_no");
    expect(parseCustomerReply(reply({ conversation_over: true, outcome: "quatsch" }), sc).outcome).toBe("lost");
    expect(parseCustomerReply(reply({ conversation_over: false, outcome: "book" }), sc).outcome).toBeNull();
  });
  it("K07 Leere oder zu lange Setter-Nachricht wird behandelt", () => {
    expect(() => applySetterMessage(startFreeSim(sc, "praxis"), "   ")).toThrow(AiError);
    const long = applySetterMessage(startFreeSim(sc, "praxis"), "a".repeat(5000));
    expect(long.transcript.at(-1)!.text.length).toBe(800);
  });
  it("K08 API-Fehler wird als Fehler gemeldet, nicht als Kundentext", async () => {
    const failing: AiProvider = { id: "f", label: "f", cost: { kind: "claude-plan" }, available: async () => true, complete: async () => { throw new AiError("rate_limited", "Limit"); } };
    await expect(customerTurn(router([failing]), sc, startFreeSim(sc, "praxis"), "Hallo")).rejects.toMatchObject({ code: "rate_limited" });
  });
});

describe("Coach – getrennt und belegt", () => {
  const st = {
    ...startFreeSim(sc, "pruefung"),
    transcript: [
      { role: "customer" as const, text: sc.openingMessage },
      { role: "setter" as const, text: "Hallo Frau Kaya, hier ist WärmeWerk Nord. Passt es kurz?" },
      { role: "customer" as const, text: "Ja." },
      { role: "setter" as const, text: "Die Förderung ist Ihnen sicher, buchen Sie nur heute!" },
      { role: "customer" as const, text: "Hm, nein danke." },
    ],
    finished: true,
    outcome: "lost" as const,
  };
  const note = { fields: Object.fromEntries(sc.handoverFields.map((k) => [k, "Nicht erfragt / unbekannt"])) };
  it("C01 Coach-Prompt enthält Rubrik und Verlauf, aber nicht das Kunden-Persona-Prompt", () => {
    const p = buildCoachPrompt(sc, st, note, measure(st.transcript), ["Q-M01-014"]);
    expect(p).toContain("KEINE Punktzahlen");
    expect(p).toContain("[3] SETTER: Die Förderung ist Ihnen sicher");
    expect(p).not.toContain(sc.ai!.personality);
  });
  it("C02 Zitate werden gegen den Verlauf geprüft; erfundene Zitate werden verworfen", () => {
    expect(verifyQuote(st.transcript, 3, "Förderung ist Ihnen sicher")).toBe(3);
    expect(verifyQuote(st.transcript, 1, "Förderung ist Ihnen sicher")).toBe(3); // wrong turn number is corrected
    expect(verifyQuote(st.transcript, 1, "Ich garantiere 50 % Ersparnis")).toBeNull();
    const raw = JSON.stringify({
      criteria: [
        { id: "eroeffnung", rating: "stark", reasoning: "gut", evidence: [{ turn: 1, quote: "Passt es kurz?", comment: "Erlaubnis" }] },
        { id: "fragetechnik", rating: "kritisch", reasoning: "erfunden", evidence: [{ turn: 1, quote: "Wann kaufen Sie endlich", comment: "x" }] },
      ],
      violations: [{ turn: 3, quote: "buchen Sie nur heute", rule: "Künstliche Verknappung" }, { turn: 3, quote: "Sie Idiot", rule: "erfunden" }],
      strengths: ["a", "b", "c", "d"],
      improvements: ["x", "y", "z"],
      improvedExample: { original: "Die Förderung ist Ihnen sicher", better: "Das prüft unser Berater.", why: "Rolle" },
      exercises: ["Q-M01-014", "BOGUS"],
      outcomeAssessment: "abgebrochen",
    });
    const r = parseCoachReport(raw, st.transcript, ["Q-M01-014"]);
    expect(r.criteria.find((c) => c.id === "eroeffnung")!.rating).toBe("stark");
    expect(r.criteria.find((c) => c.id === "fragetechnik")!.rating).toBe("nicht_beobachtet"); // no valid evidence → no judgement
    expect(r.violations).toHaveLength(1);
    expect(r.droppedUnverified).toBe(2);
    expect(r.strengths).toHaveLength(3);
    expect(r.exercises).toEqual(["Q-M01-014"]);
  });
  it("C03 Gemessene Werte sind deterministisch und unabhängig vom Coach", () => {
    const m = measure(st.transcript);
    expect(m.setterMessages).toBe(2);
    expect(m.redFlags.map((x) => x.label)).toEqual(expect.arrayContaining(["Künstliche Verknappung („nur heute“)", "Ungeprüfte Förderzusage"]));
    expect(isOpenQuestion("Was hat Sie dazu gebracht?")).toBe(true);
    expect(isOpenQuestion("Sind Sie Eigentümer?")).toBe(false);
  });
  it("C04 Prüfungsmodus: Warnsätze lösen G1 aus, auch wenn der Coach nichts meldet", async () => {
    const coach = scripted("c", () => JSON.stringify({ criteria: [], violations: [], strengths: [], improvements: [], exercises: [], outcomeAssessment: "" }));
    const ev = await coachEvaluate(router([coach]), sc, st, note);
    expect(ev.gates.find((g) => g.id === "G1")!.triggered).toBe(true);
    expect(ev.passed).toBe(false);
  });
  it("C05 Prüfungsmodus ohne erreichbaren Coach: keine Bestehensentscheidung", async () => {
    const ev = await coachEvaluate(router([scripted("x", () => "", { kind: "claude-plan" }, false)]), sc, st, note);
    expect(ev.passed).toBeNull();
    expect(ev.measured.setterMessages).toBe(2);
  });
  it("C06 Praxismodus trifft keine Bestehensentscheidung", async () => {
    const ev = await coachEvaluate(null, sc, { ...st, mode: "praxis" }, note);
    expect(ev.passed).toBeNull();
  });
  it("C07 Termin ohne Pflichtkriterien → G2", () => {
    const m = measuredEvaluation(sc, { ...st, outcome: "book", revealed: ["need"] }, note);
    expect(gates(sc, m, null).find((g) => g.id === "G2")!.triggered).toBe(true);
  });
  it("C08 Sauberer Prüfungsdurchlauf besteht nur mit verifizierten, unkritischen Bewertungen", async () => {
    const good = {
      ...startFreeSim(scenarioById("SIM-003")!, "pruefung"),
      transcript: [
        { role: "customer" as const, text: "Ich möchte keinen Termin, danke." },
        { role: "setter" as const, text: "Alles klar, kein Termin. Möchten Sie überhaupt noch Nachrichten von uns?" },
        { role: "customer" as const, text: "Bitte keine Nachrichten mehr." },
        { role: "setter" as const, text: "Verstanden, ich vermerke das. Alles Gute!" },
        { role: "customer" as const, text: "Danke." },
      ],
      revealed: ["contact_pref"],
      finished: true,
      outcome: "respect_no" as const,
    };
    const s3 = scenarioById("SIM-003")!;
    const coach = scripted("c", () => JSON.stringify({ criteria: [{ id: "ablehnung", rating: "stark", reasoning: "Nein sofort akzeptiert", evidence: [{ turn: 1, quote: "Alles klar, kein Termin", comment: "ok" }] }], violations: [], strengths: ["a", "b", "c"], improvements: ["x", "y", "z"], exercises: [], outcomeAssessment: "gut" }));
    const ev = await coachEvaluate(router([coach]), s3, good, { fields: { contact_pref: "Keine weiteren Werbenachrichten", reason: "Nicht erfragt / unbekannt" } });
    expect(ev.gates.filter((g) => g.triggered)).toEqual([]);
    expect(ev.passed).toBe(true);
  });
});

describe("Hilfestellungen & Persistenz", () => {
  it("H01 Hinweise nur im Lernmodus", async () => {
    const p = scripted("p", () => "Frag nach dem Mitentscheider.");
    await expect(hint(router([p]), sc, startFreeSim(sc, "praxis"), false)).rejects.toBeInstanceOf(AiError);
    await expect(hint(router([p]), sc, startFreeSim(sc, "pruefung"), true)).rejects.toBeInstanceOf(AiError);
    expect(await hint(router([p]), sc, startFreeSim(sc, "lern"), false)).toContain("Mitentscheider");
  });
  it("H02 Hinweis-Prompt verrät keine Faktenwerte", () => {
    const p = scripted("p", () => "x");
    hint(router([p]), sc, startFreeSim(sc, "lern"), true);
    return new Promise<void>((r) => setTimeout(() => {
      const prompt = p.calls[0]!.prompt;
      expect(prompt).toContain("Entscheider");
      expect(prompt).not.toContain("Tom");
      r();
    }, 0));
  });
  it("H03 Migration v3 → v4 erhält Fortschritt und sperrt Bezahl-KI", () => {
    const s = migrate({ ...initialState(), schemaVersion: 3, aiSimulations: undefined, ai: undefined, reader: undefined, lessonsCompleted: { "M01-L01": { at: 1, courseVersion: "x" } } });
    expect(s.lessonsCompleted["M01-L01"]).toBeDefined();
    expect(s.ai.paidCallsEnabled).toBe(false);
    expect(s.aiSimulations).toEqual([]);
  });
  it("H04 KI-Simulationen werden gespeichert und begrenzt", () => {
    let s = initialState();
    const ev = { measured: measuredEvaluation(sc, startFreeSim(sc, "praxis"), { fields: {} }), coach: null, gates: [], passed: null, mode: "praxis" as const };
    for (let i = 0; i < 35; i++) s = recordAiSimulation(s, { id: `x${i}`, scenarioId: sc.id, scenarioVersion: 1, mode: "praxis", at: i, transcript: [], handover: { fields: {} }, revealed: [], outcome: null, evaluation: ev, providerId: "p" });
    expect(s.aiSimulations).toHaveLength(30);
  });
});
