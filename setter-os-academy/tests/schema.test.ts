// Validates db/schema.sql against a real (embedded, WASM) Postgres – no server needed.
import { readFileSync } from "node:fs";
import path from "node:path";
import { PGlite } from "@electric-sql/pglite";
import { beforeAll, describe, expect, it } from "vitest";

const sql = readFileSync(path.resolve(__dirname, "../db/schema.sql"), "utf8");
let db: PGlite;

beforeAll(async () => {
  db = new PGlite();
  await db.exec(sql);
}, 60_000);

async function seed() {
  const u = await db.query<{ id: string }>("insert into users default values returning id");
  const r = await db.query<{ id: string }>("insert into users default values returning id");
  const author = u.rows[0]!.id;
  const reviewer = r.rows[0]!.id;
  await db.query("insert into courses (id, title) values ('setter-os','SETTER OS') on conflict do nothing");
  const cv = await db.query<{ id: string }>(
    "insert into course_versions (course_id, semver, status, created_by, reviewed_by, published_at) values ('setter-os', $1, 'published', $2, $3, now()) returning id",
    [`0.1.${Math.floor(Math.random() * 1e6)}`, author, reviewer],
  );
  return { author, reviewer, cv: cv.rows[0]!.id };
}

describe("Datenbankschema (PGlite)", () => {
  it("D01 Schema lässt sich vollständig anlegen", async () => {
    const t = await db.query<{ n: number }>("select count(*)::int as n from information_schema.tables where table_schema='public'");
    expect(t.rows[0]!.n).toBeGreaterThanOrEqual(30);
  });
  it("D02 Veröffentlichung ohne Reviewer wird abgelehnt (Vier-Augen-Prinzip)", async () => {
    const { author } = await seed();
    await expect(
      db.query("insert into course_versions (course_id, semver, status, created_by, published_at) values ('setter-os','9.9.9','published',$1, now())", [author]),
    ).rejects.toThrow();
  });
  it("D03 Veröffentlichte Fragen sind unveränderlich, neue Version möglich", async () => {
    const { cv, reviewer } = await seed();
    await db.query(
      "insert into questions (id, version, course_version_id, module_id, objective_id, type, difficulty, prompt, explanation, payload, status, reviewed_by) values ('Q-T-1',1,$1,'M01','LO-M01-01','single',1,'Frage?','Ausreichend lange Erklärung.', '{}'::jsonb,'published',$2)",
      [cv, reviewer],
    );
    await expect(db.query("update questions set prompt='geändert' where id='Q-T-1' and version=1")).rejects.toThrow(/unveränderlich/);
    await db.query(
      "insert into questions (id, version, course_version_id, module_id, objective_id, type, difficulty, prompt, explanation, payload) values ('Q-T-1',2,$1,'M01','LO-M01-01','single',1,'Frage neu?','Ausreichend lange Erklärung.', '{}'::jsonb)",
      [cv],
    );
    const n = await db.query<{ n: number }>("select count(*)::int as n from questions where id='Q-T-1'");
    expect(n.rows[0]!.n).toBe(2);
  });
  it("D04 KI-generierte Frage kann ohne Review nicht veröffentlicht werden", async () => {
    const { cv } = await seed();
    await expect(
      db.query(
        "insert into questions (id, version, course_version_id, module_id, objective_id, type, difficulty, prompt, explanation, payload, status, ai_generated) values ('Q-AI',1,$1,'M01','LO','single',1,'?','Ausreichend lange Erklärung.','{}'::jsonb,'published',true)",
        [cv],
      ),
    ).rejects.toThrow();
  });
  it("D05 XP können nicht negativ sein (nichts wird weggenommen)", async () => {
    const { author } = await seed();
    await expect(db.query("insert into xp_events (user_id, reason, amount, ref) values ($1,'x',-10,'r')", [author])).rejects.toThrow();
  });
  it("D06 Bewertung nach Gates kann nicht über Rohwert liegen", async () => {
    const { author, cv } = await seed();
    await db.query("insert into scenarios (id, version, course_version_id, title, archetype, market, direction, definition) values ('SIM-T',1,$1,'t','a','B2C','inbound','{}') on conflict do nothing", [cv]);
    const s = await db.query<{ id: string }>("insert into simulation_sessions (user_id, scenario_id, scenario_version) values ($1,'SIM-T',1) returning id", [author]);
    await expect(
      db.query("insert into simulation_evaluations (session_id, rubric_version, total, raw_total, passed, competencies, gates, handover) values ($1,'1.0.0',90,40,true,'[]','[]','{}')", [s.rows[0]!.id]),
    ).rejects.toThrow();
  });
  it("D07 Löschen eines Nutzers entfernt seine Lerndaten (Löschkonzept)", async () => {
    const { cv } = await seed();
    const learner = (await db.query<{ id: string }>("insert into users default values returning id")).rows[0]!.id;
    await db.query("insert into profiles (user_id, display_name) values ($1,'Test')", [learner]);
    await db.query("insert into quiz_attempts (user_id, course_version_id, module_id, kind) values ($1,$2,'M01','practice')", [learner, cv]);
    await db.query("insert into consent_records (user_id, purpose, document_version, granted, source) values ($1,'privacy_notice','draft',true,'web')", [learner]);
    await db.query("delete from users where id=$1", [learner]);
    const n = await db.query<{ n: number }>("select (select count(*) from quiz_attempts where user_id=$1) + (select count(*) from profiles where user_id=$1) + (select count(*) from consent_records where user_id=$1) as n", [learner]);
    expect(n.rows[0]!.n).toBe(0);
  });
});
