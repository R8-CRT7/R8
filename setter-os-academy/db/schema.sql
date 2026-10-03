-- SETTER OS ACADEMY – PostgreSQL schema (target: Supabase/Postgres ≥ 15)
-- Status: designed + validated against an embedded Postgres (PGlite) in tests/schema.test.ts.
-- NOT deployed. The prototype persists locally in the browser; this schema is the migration target.
--
-- Principles
--  * Content is versioned: every attempt references the exact content version it was graded against.
--  * Published content versions are immutable (trigger) → old results can never be silently changed.
--  * Data minimisation: simulation messages are optional; default storage is move ids.
--  * Auth users live in auth.users (Supabase). Here a local `users` table stands in for portability.

-- gen_random_uuid() is built into PostgreSQL ≥ 13 (no extension required).

-- ---------- Identity ----------
create table users (
  id uuid primary key default gen_random_uuid(),
  email text unique,                       -- null for local/anonymous prototype users
  created_at timestamptz not null default now(),
  deleted_at timestamptz                   -- soft delete → hard delete job after retention period
);

create type app_role as enum ('learner', 'editor', 'reviewer', 'admin');

create table profiles (
  user_id uuid primary key references users(id) on delete cascade,
  display_name text not null check (char_length(display_name) between 1 and 40),
  locale text not null default 'de' check (locale in ('de','en','es')),
  role app_role not null default 'learner',
  settings jsonb not null default '{}'::jsonb,
  leaderboard_opt_in boolean not null default false,  -- voluntary only
  updated_at timestamptz not null default now()
);

create table consent_records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  purpose text not null,                   -- e.g. 'privacy_notice', 'ai_simulation', 'product_emails'
  document_version text not null,
  granted boolean not null,
  recorded_at timestamptz not null default now(),
  source text not null                     -- 'web', 'import', …
);
create index on consent_records (user_id, purpose, recorded_at desc);

-- ---------- Course & versioning ----------
create table courses (
  id text primary key,                     -- 'setter-os'
  title text not null,
  created_at timestamptz not null default now()
);

create type version_status as enum ('draft', 'in_review', 'published', 'retired');

create table course_versions (
  id uuid primary key default gen_random_uuid(),
  course_id text not null references courses(id),
  semver text not null,
  status version_status not null default 'draft',
  changelog text not null default '',
  created_by uuid references users(id) on delete set null,
  reviewed_by uuid references users(id),   -- staff accounts are pseudonymised, not deleted (audit trail)
  published_at timestamptz,
  unique (course_id, semver),
  check (status <> 'published' or (reviewed_by is not null and published_at is not null)),
  check (reviewed_by is null or reviewed_by <> created_by)   -- four-eyes principle
);

create table modules (
  id text not null,                        -- 'M01'
  course_version_id uuid not null references course_versions(id),
  number int not null,
  title text not null,
  subtitle text not null default '',
  pass_threshold numeric(4,3) not null default 0.8 check (pass_threshold between 0 and 1),
  primary key (course_version_id, id)
);

create table lessons (
  id text not null,                        -- 'M01-L01'
  course_version_id uuid not null,
  module_id text not null,
  title text not null,
  minutes int not null check (minutes > 0),
  blocks jsonb not null,                   -- typed blocks, validated in app (LessonBlock)
  summary jsonb not null default '[]',
  primary key (course_version_id, id),
  foreign key (course_version_id, module_id) references modules(course_version_id, id)
);

create table learning_objectives (
  id text not null,
  course_version_id uuid not null,
  module_id text not null,
  text text not null,
  bloom text not null,
  primary key (course_version_id, id),
  foreign key (course_version_id, module_id) references modules(course_version_id, id)
);

create table knowledge_sources (
  id text primary key,                     -- 'SRC-001'
  title text not null,
  author_or_publisher text not null,
  url text not null check (url ~ '^https?://'),
  doi text,
  published_at text,
  last_checked_at date not null,
  review_interval_days int not null check (review_interval_days > 0),
  evidence text not null,
  verification text not null check (verification in ('verifiziert','teilweise_verifiziert','unverifiziert')),
  access_note text not null default ''
);

create table knowledge_entries (
  id text not null,
  version int not null,
  topic text not null,
  subtopic text not null,
  statement text not null,
  explanation text not null,
  evidence text not null,
  scope text not null,
  contradictions text,
  last_checked_at date not null,
  primary key (id, version)
);
create table knowledge_entry_sources (
  entry_id text not null, entry_version int not null, source_id text not null references knowledge_sources(id),
  primary key (entry_id, entry_version, source_id),
  foreign key (entry_id, entry_version) references knowledge_entries(id, version)
);

create type question_type as enum ('single','multi','truefalse','matching','ordering','cloze','freetext','situation','errorspot','calculation','crm');

-- Questions are versioned rows: (id, version). Attempts reference the exact version.
create table questions (
  id text not null,                        -- 'Q-M01-001'
  version int not null check (version > 0),
  course_version_id uuid not null references course_versions(id),
  module_id text not null,
  objective_id text not null,
  type question_type not null,
  difficulty int not null check (difficulty between 1 and 5),
  prompt text not null,
  explanation text not null check (char_length(explanation) >= 20),
  negation boolean not null default false,
  payload jsonb not null,                  -- type-specific data (pairs, gaps, rubric, given values …)
  status version_status not null default 'draft',
  ai_generated boolean not null default false,
  reviewed_by uuid references users(id),
  primary key (id, version),
  check (not ai_generated or status <> 'published' or reviewed_by is not null)  -- no unreviewed AI text in production
);
create index on questions (module_id, objective_id);

create table answer_options (
  question_id text not null,
  question_version int not null,
  id text not null,
  text text not null,
  is_correct boolean not null default false,
  quality text check (quality in ('best','acceptable','poor','unacceptable')),
  misconception text,
  error_category text,
  primary key (question_id, question_version, id),
  foreign key (question_id, question_version) references questions(id, version),
  check (is_correct or quality in ('best','acceptable') or misconception is not null or quality is not null)
);

create table question_sources (
  question_id text not null, question_version int not null, source_id text not null references knowledge_sources(id),
  primary key (question_id, question_version, source_id),
  foreign key (question_id, question_version) references questions(id, version)
);

create table mistake_types (
  id text primary key,                     -- 'rollenverwechslung' …
  label text not null,
  description text not null
);

-- ---------- Attempts ----------
create table quiz_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  course_version_id uuid not null references course_versions(id),
  module_id text not null,
  kind text not null check (kind in ('lesson','practice','review','module-exam')),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  percent numeric(5,2),
  passed boolean,
  pending_manual_review int not null default 0
);

create table quiz_answers (
  id uuid primary key default gen_random_uuid(),
  attempt_id uuid not null references quiz_attempts(id) on delete cascade,
  question_id text not null,
  question_version int not null,
  answer jsonb not null,
  score numeric(4,3) not null check (score between 0 and 1),
  needs_manual_review boolean not null default false,
  manual_score numeric(4,3) check (manual_score between 0 and 1),
  manual_reviewed_by uuid references users(id),
  confidence smallint check (confidence between 1 and 3),
  duration_ms int check (duration_ms >= 0),
  error_categories text[] not null default '{}',
  answered_at timestamptz not null default now(),
  foreign key (question_id, question_version) references questions(id, version)
);
create index on quiz_answers (attempt_id);

create table review_schedules (
  user_id uuid not null references users(id) on delete cascade,
  question_id text not null,
  objective_id text not null,
  box smallint not null check (box between 1 and 5),
  attempts int not null default 0,
  correct int not null default 0,
  wrong int not null default 0,
  last_score numeric(4,3),
  last_at timestamptz,
  next_due_at timestamptz not null,
  primary key (user_id, question_id)
);
create index on review_schedules (user_id, next_due_at);

create table learning_progress (
  user_id uuid not null references users(id) on delete cascade,
  lesson_id text not null,
  course_version_id uuid not null references course_versions(id),
  completed_at timestamptz not null default now(),
  primary key (user_id, lesson_id, course_version_id)
);

create table skill_scores (
  user_id uuid not null references users(id) on delete cascade,
  objective_id text not null,
  measured_performance numeric(5,2),       -- measured
  mastery text not null check (mastery in ('nicht_geprueft','im_aufbau','gefestigt','gesichert')),  -- estimated
  mastery_reason text not null,
  simulation_score numeric(5,2),
  computed_at timestamptz not null default now(),
  primary key (user_id, objective_id)
);

-- ---------- Simulations ----------
create table scenarios (
  id text not null,
  version int not null,
  course_version_id uuid not null references course_versions(id),
  title text not null,
  archetype text not null,
  market text not null check (market in ('B2B','B2C')),
  direction text not null check (direction in ('inbound','outbound')),
  definition jsonb not null,               -- facts, moves, replies (see Scenario type)
  status version_status not null default 'draft',
  primary key (id, version)
);

create table simulation_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  scenario_id text not null,
  scenario_version int not null,
  mode text not null default 'deterministic' check (mode in ('deterministic','ai')),
  move_ids text[] not null default '{}',   -- minimal record, transcript reproducible
  outcome text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  retain_until timestamptz,                -- deletion concept
  foreign key (scenario_id, scenario_version) references scenarios(id, version)
);

-- Only filled in AI mode (free text). Purged by retention job.
create table simulation_messages (
  id bigserial primary key,
  session_id uuid not null references simulation_sessions(id) on delete cascade,
  turn int not null,
  role text not null check (role in ('setter','customer','system')),
  text text not null check (char_length(text) <= 2000),
  created_at timestamptz not null default now()
);

create table simulation_evaluations (
  session_id uuid primary key references simulation_sessions(id) on delete cascade,
  rubric_version text not null,
  total smallint not null check (total between 0 and 100),
  raw_total smallint not null check (raw_total between 0 and 100),
  passed boolean not null,
  competencies jsonb not null,
  gates jsonb not null,
  handover jsonb not null,
  evaluator text not null default 'deterministic-coach',
  created_at timestamptz not null default now(),
  check (total <= raw_total)
);

-- ---------- Exams ----------
create table exams (
  id text not null,
  course_version_id uuid not null references course_versions(id),
  title text not null,
  rules jsonb not null,                    -- pass rules defined BEFORE the attempt
  primary key (course_version_id, id)
);
create table exam_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  exam_id text not null,
  course_version_id uuid not null,
  variant_seed int not null,               -- varying tasks on repeat
  parts jsonb not null default '{}',
  tested_competencies text[] not null default '{}',
  passed boolean,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  foreign key (course_version_id, exam_id) references exams(course_version_id, id)
);

-- ---------- Gamification ----------
create table achievements (
  id text primary key,
  title text not null,
  description text not null
);
create table user_achievements (
  user_id uuid not null references users(id) on delete cascade,
  achievement_id text not null references achievements(id),
  unlocked_at timestamptz not null default now(),
  primary key (user_id, achievement_id)            -- never revoked
);
create table xp_events (
  id bigserial primary key,
  user_id uuid not null references users(id) on delete cascade,
  reason text not null,
  amount int not null check (amount > 0),          -- only positive: nothing is taken away
  ref text not null,
  created_at timestamptz not null default now()
);

-- ---------- Admin & audit ----------
create table admin_actions (
  id bigserial primary key,
  actor uuid not null references users(id),
  action text not null,                    -- 'edit_question', 'publish_version' …
  target text not null,
  diff jsonb,
  created_at timestamptz not null default now()
);
create table audit_logs (
  id bigserial primary key,
  actor uuid references users(id),
  event text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create table content_feedback (
  id bigserial primary key,
  user_id uuid references users(id) on delete set null,
  target text not null,                    -- question/lesson id
  kind text not null check (kind in ('unklar','fehler','veraltet','sonstiges')),
  message text not null check (char_length(message) <= 2000),
  status text not null default 'offen' check (status in ('offen','in_arbeit','erledigt','abgelehnt')),
  created_at timestamptz not null default now()
);

-- Published content is immutable.
create function forbid_published_change() returns trigger language plpgsql as $$
begin
  if old.status = 'published' then
    raise exception 'Veröffentlichte Inhalte sind unveränderlich – neue Version anlegen (%).', old.id;
  end if;
  return new;
end $$;
create trigger questions_immutable before update on questions for each row execute function forbid_published_change();
create trigger scenarios_immutable before update on scenarios for each row execute function forbid_published_change();

-- ---------- Later (after legal gate) ----------
-- products, orders, payments, refunds, subscriptions, certificates – intentionally NOT created yet.
