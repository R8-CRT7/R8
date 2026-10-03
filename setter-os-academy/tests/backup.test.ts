// Datensicherheit: beschädigte oder fremde Sicherungen dürfen den Lernstand nie zerstören.
import { beforeEach, describe, expect, it } from "vitest";
import { checkBackup, completeLesson, initialState, migrate, newProfile, SCHEMA_VERSION } from "@/lib/store/state";

function realState() {
  let s: ReturnType<typeof initialState> = { ...initialState(), profile: newProfile("Emi", 1) };
  s = completeLesson(s, "M01-L01", "t", 2);
  return s;
}

describe("Sicherung prüfen (checkBackup)", () => {
  it("D01 gültige Sicherung wird mit Zusammenfassung akzeptiert", () => {
    const c = checkBackup(JSON.stringify(realState()));
    expect(c.ok).toBe(true);
    expect(c.summary).toMatchObject({ name: "Emi", lessons: 1, schemaVersion: SCHEMA_VERSION });
  });
  it.each([
    ["abgeschnitten", JSON.stringify(realState()).slice(0, 200)],
    ["leer", ""],
    ["leeres Objekt", "{}"],
    ["Array", "[]"],
    ["Zahl", "42"],
    ["null", "null"],
    ["fremdes JSON", JSON.stringify({ foo: 1 })],
    ["ohne Profil", JSON.stringify({ schemaVersion: 4, lessonsCompleted: {} })],
    ["neuere Version", JSON.stringify({ ...realState(), schemaVersion: SCHEMA_VERSION + 1 })],
  ])("D02 abgelehnt: %s", (_n, text) => {
    expect(checkBackup(text).ok).toBe(false);
  });
});

describe("Migration robust gegen falsche Typen", () => {
  it("D03 falsche Feldtypen fallen auf Standardwerte zurück statt abzustürzen", () => {
    const s = migrate({ ...realState(), attempts: null, simulations: "x", reviews: [], settings: 5, reader: null });
    expect(Array.isArray(s.attempts)).toBe(true);
    expect(Array.isArray(s.simulations)).toBe(true);
    expect(typeof s.reviews).toBe("object");
    expect(s.settings.theme).toBeDefined();
    expect(s.reader.bookmarks).toEqual([]);
    expect(s.lessonsCompleted["M01-L01"]).toBeTruthy(); // valid parts survive
  });
  it("D04 Einträge ohne Zeitstempel werden verworfen, gültige bleiben", () => {
    const s = migrate({ ...realState(), attempts: [{ at: 5, questionId: "Q" }, { questionId: "kaputt" }, 7] });
    expect(s.attempts).toHaveLength(1);
  });
  it("D05 unbekannte Felder werden entfernt", () => {
    const s = migrate({ ...realState(), evil: "<script>" }) as unknown as Record<string, unknown>;
    expect("evil" in s).toBe(false);
  });
  it("D06 Teilobjekte werden mit Standardwerten ergänzt (z. B. alte KI-Einstellungen)", () => {
    const s = migrate({ ...realState(), ai: { paidCallsEnabled: false } });
    expect(s.ai.spendLog).toEqual([]);
    expect(s.ai.monthlyBudgetEur).toBe(0);
  });
  it("D07 Stand v3 (ohne KI-Felder) wird verlustfrei auf die aktuelle Version gehoben", () => {
    const v3 = { ...realState(), schemaVersion: 3 } as Record<string, unknown>;
    delete v3.aiSimulations; delete v3.ai; delete v3.reader;
    const s = migrate(v3);
    expect(s.schemaVersion).toBe(SCHEMA_VERSION);
    expect(s.profile?.displayName).toBe("Emi");
    expect(s.ai.paidCallsEnabled).toBe(false);
  });
});

describe("Import im Speicher-Adapter", () => {
  beforeEach(() => {
    const mem = new Map<string, string>();
    (globalThis as unknown as { window: unknown }).window = {
      localStorage: { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v), removeItem: (k: string) => void mem.delete(k) },
      addEventListener() {}, removeEventListener() {},
    };
  });
  it("D08 fehlerhafter Import verändert den Stand nicht; gültiger Import legt Sicherheitskopie an; Rückgängig stellt her", async () => {
    const st = await import("@/lib/store/storage");
    st.update(() => realState());
    expect(() => st.importJson("{}")).toThrow();
    expect(() => st.importJson("{kaputt")).toThrow();
    expect(st.getState().profile?.displayName).toBe("Emi");
    const other = { ...realState(), profile: newProfile("Neu", 3) };
    st.importJson(JSON.stringify(other));
    expect(st.getState().profile?.displayName).toBe("Neu");
    expect(st.restoreSafetyCopy()).toBe(true);
    expect(st.getState().profile?.displayName).toBe("Emi");
  });
});
