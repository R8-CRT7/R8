# DATABASE_SCHEMA

Ziel-Schema für PostgreSQL/Supabase: [`db/schema.sql`](../db/schema.sql). **Nicht deployt.** Validiert in `tests/schema.test.ts` gegen eine eingebettete Postgres-Engine (PGlite, WASM) – 7 Tests.

## Entitäten (Brief §12)

| Brief | Tabelle | Anmerkung |
|---|---|---|
| Users / Profiles | `users`, `profiles` | Rolle `learner/editor/reviewer/admin`; Ranglisten nur `leaderboard_opt_in` |
| ConsentRecords | `consent_records` | Zweck, Dokumentversion, erteilt/widerrufen, Zeitpunkt |
| Courses / CourseVersions | `courses`, `course_versions` | Status `draft → in_review → published → retired`; **Vier-Augen-Prinzip per CHECK** (`reviewed_by <> created_by`) |
| Modules / Lessons / LearningObjectives | `modules`, `lessons`, `learning_objectives` | Schlüssel `(course_version_id, id)` – Inhalte pro Version |
| KnowledgeSources | `knowledge_sources` (+ `knowledge_entries`, `knowledge_entry_sources`) | Prüfintervall, Verifikationsstatus |
| Questions / AnswerOptions | `questions (id, version)`, `answer_options`, `question_sources` | typspezifische Daten als `payload jsonb`; `ai_generated` darf nur mit Reviewer veröffentlicht werden (CHECK) |
| MistakeTypes | `mistake_types` | Fehlerkategorien |
| QuizAttempts / QuizAnswers | `quiz_attempts`, `quiz_answers` | Antwort referenziert **(question_id, question_version)**; `manual_score` für Freitext |
| ReviewSchedules | `review_schedules` | Leitner-Box, Fälligkeit (Index) |
| LearningProgress | `learning_progress` | pro Kursversion |
| SkillScores | `skill_scores` | gemessen (`measured_performance`) **getrennt** von geschätzt (`mastery`) |
| Scenarios / SimulationSessions / SimulationMessages / SimulationEvaluations | gleichnamig | Session speichert `move_ids`; Nachrichten nur im KI-Modus, `retain_until`; Bewertung `total <= raw_total` (CHECK) |
| Exams / ExamAttempts | `exams`, `exam_attempts` | Regeln vor dem Versuch (`rules jsonb`), `variant_seed`, `tested_competencies` |
| Achievements / UserAchievements | gleichnamig + `xp_events` | `amount > 0` – nichts wird entzogen |
| AuditLogs / AdminActions | gleichnamig + `content_feedback` | Nutzerfeedback zu Inhalten (unklar/fehler/veraltet) |
| Products, Orders, Payments, Refunds, Subscriptions, Certificates | **nicht angelegt** | erst nach Legal-Gate |

## Versionierung – warum alte Ergebnisse stabil bleiben

1. Inhalte haben zusammengesetzte Schlüssel `(id, version)`.
2. Ein Trigger verhindert `UPDATE` auf veröffentlichte Fragen/Szenarien → Änderung = neue Version (Test D03).
3. Versuche speichern die exakte Version; Bewertungen speichern `rubric_version`.
4. Im lokalen Prototyp gilt dasselbe Prinzip: `QuizAttemptRecord.questionVersions`, `SimulationRecord.scenarioVersion/rubricVersion` (Test P05).

## Löschkonzept

`delete from users` kaskadiert auf Profil, Einwilligungen, Versuche, Antworten, Wiederholung, Fortschritt, Simulationen, Erfolge, XP (Test D07). Staff-Konten, die Inhalte reviewt haben, werden pseudonymisiert statt gelöscht (Audit-Trail). Prototyp: „Alle Daten löschen“ in den Einstellungen entfernt den localStorage-Eintrag vollständig (E2E E08).

## Migration lokal → Cloud (geplant)

`AcademyState` (Schema v2) wird beim ersten Login als Import übertragen: `attempts → quiz_answers` (Kontext „lesson/review“ als eigene `quiz_attempts`), `reviews → review_schedules`, `simulations → simulation_sessions + simulation_evaluations`. Migrationsskript + Test sind offen (TEST_PLAN „ungeprüft“).
