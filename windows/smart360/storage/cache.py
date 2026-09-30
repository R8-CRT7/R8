"""Question cache (SQLite).

Safety first: a cache hit must never answer a *different* question. A hit requires
ALL of the following:

1. same question type
2. identical numeric tokens in the question (50 km/h vs 70 km/h!)
3. normalized question text similarity  >= text_threshold (default 0.97)
4. same number of answers, each answer matched 1:1 with similarity >= answer_threshold
   (answers may be shuffled - the mapping is done by text, and numbers must match exactly)
5. image agreement: both without image, or both with image and dHash distance <= max_image_distance

The prediction is stored as answer *texts*, then re-mapped onto the indices of the
currently visible answer order.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz

from smart360.core.imaging import hamming
from smart360.core.matching import words_compatible
from smart360.core.models import Question, numeric_tokens

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS questions (
    question_hash   TEXT PRIMARY KEY,
    normalized_text TEXT NOT NULL,
    numbers         TEXT NOT NULL,
    answers_json    TEXT NOT NULL,
    image_hash      TEXT,
    question_type   TEXT NOT NULL,
    correct_json    TEXT NOT NULL,
    number_answer   TEXT,
    confidence      REAL NOT NULL,
    reason          TEXT NOT NULL,
    topic           TEXT NOT NULL DEFAULT '',
    model           TEXT NOT NULL,
    created_at      REAL NOT NULL,
    last_hit        REAL,
    hits            INTEGER NOT NULL DEFAULT 0,
    verified        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_q_type ON questions(question_type);
"""


@dataclass(frozen=True, slots=True)
class CacheHit:
    answers: tuple[int, ...]  # re-mapped onto the CURRENT question's indices
    number_answer: str | None
    confidence: float
    reason: str
    topic: str
    model: str
    similarity: float
    verified: bool


@dataclass(slots=True)
class _Row:
    key: str
    text: str
    numbers: tuple[str, ...]
    answers: tuple[str, ...]
    image_hash: int | None
    qtype: str
    correct: tuple[str, ...]
    number_answer: str | None
    confidence: float
    reason: str
    topic: str
    model: str
    verified: bool


class QuestionCache:
    def __init__(
        self,
        path: Path | str,
        text_threshold: float = 0.97,
        answer_threshold: float = 0.95,
        max_image_distance: int = 6,
        max_entries: int = 20000,
    ) -> None:
        self.path = Path(path)
        self.text_threshold = text_threshold
        self.answer_threshold = answer_threshold
        self.max_image_distance = max_image_distance
        self.max_entries = max_entries
        self._lock = threading.RLock()
        self._rows: dict[str, _Row] = {}
        self._conn: sqlite3.Connection | None = None
        self.recovered_from_corruption = False
        self.lookups = 0
        self.hits = 0
        self._open()

    # ------------------------------------------------------------------ lifecycle
    def _open(self) -> None:
        with self._lock:
            if str(self.path) != ":memory:":
                self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self._connect_and_load()
            except sqlite3.DatabaseError as exc:
                log.warning("cache database corrupted (%s) - starting a fresh cache", exc)
                self._quarantine()
                self._connect_and_load()
                self.recovered_from_corruption = True

    def _connect_and_load(self) -> None:
        if self._conn is not None:
            self._conn.close()
        conn = sqlite3.connect(str(self.path), check_same_thread=False, timeout=5)
        try:
            ok = conn.execute("PRAGMA quick_check").fetchone()
            if not ok or ok[0] != "ok":
                raise sqlite3.DatabaseError(f"quick_check: {ok}")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('schema', ?)", (str(SCHEMA_VERSION),)
            )
            conn.commit()
            rows = conn.execute(
                "SELECT question_hash, normalized_text, numbers, answers_json, image_hash, question_type,"
                " correct_json, number_answer, confidence, reason, topic, model, verified FROM questions"
            ).fetchall()
        except Exception:
            conn.close()
            raise
        self._conn = conn
        self._rows = {}
        for r in rows:
            try:
                self._rows[r[0]] = _Row(
                    key=r[0],
                    text=r[1],
                    numbers=tuple(json.loads(r[2])),
                    answers=tuple(json.loads(r[3])),
                    image_hash=int(r[4], 16) if r[4] else None,
                    qtype=r[5],
                    correct=tuple(json.loads(r[6])),
                    number_answer=r[7],
                    confidence=float(r[8]),
                    reason=r[9],
                    topic=r[10],
                    model=r[11],
                    verified=bool(r[12]),
                )
            except (ValueError, TypeError, json.JSONDecodeError):
                log.warning("skipping malformed cache row %s", r[0])

    def _quarantine(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None
        if str(self.path) == ":memory:":
            return
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(self.path) + suffix)
            if p.exists():
                p.replace(p.with_name(p.name + f".corrupt-{stamp}"))

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def clear(self) -> None:
        with self._lock:
            assert self._conn is not None
            self._conn.execute("DELETE FROM questions")
            self._conn.commit()
            self._rows.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._rows)

    @property
    def hit_rate(self) -> float:
        return self.hits / self.lookups if self.lookups else 0.0

    # ------------------------------------------------------------------ keys
    @staticmethod
    def key_for(q: Question) -> str:
        return q.fingerprint

    # ------------------------------------------------------------------ write
    def store(
        self,
        q: Question,
        correct: tuple[int, ...],
        confidence: float,
        reason: str,
        model: str,
        topic: str = "",
        number_answer: str | None = None,
        verified: bool = False,
    ) -> None:
        answer_texts = q.normalized_answers
        correct_texts = tuple(answer_texts[i - 1] for i in correct if 1 <= i <= len(answer_texts))
        if len(correct_texts) != len(correct) and number_answer is None:
            raise ValueError("correct indices out of range")
        row = _Row(
            key=self.key_for(q),
            text=q.normalized_text,
            numbers=numeric_tokens(q.text),
            answers=answer_texts,
            image_hash=q.image_hash,
            qtype=q.question_type.value,
            correct=correct_texts,
            number_answer=number_answer,
            confidence=confidence,
            reason=reason,
            topic=topic,
            model=model,
            verified=verified,
        )
        with self._lock:
            assert self._conn is not None
            self._conn.execute(
                "INSERT OR REPLACE INTO questions(question_hash, normalized_text, numbers, answers_json,"
                " image_hash, question_type, correct_json, number_answer, confidence, reason, topic, model,"
                " created_at, verified) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row.key,
                    row.text,
                    json.dumps(list(row.numbers)),
                    json.dumps(list(row.answers)),
                    f"{row.image_hash:016x}" if row.image_hash is not None else None,
                    row.qtype,
                    json.dumps(list(row.correct)),
                    row.number_answer,
                    row.confidence,
                    row.reason,
                    row.topic,
                    row.model,
                    time.time(),
                    int(row.verified),
                ),
            )
            self._conn.commit()
            self._rows[row.key] = row
            self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        if len(self._rows) <= self.max_entries:
            return
        assert self._conn is not None
        excess = len(self._rows) - self.max_entries
        victims = self._conn.execute(
            "SELECT question_hash FROM questions WHERE verified = 0"
            " ORDER BY COALESCE(last_hit, created_at) ASC LIMIT ?",
            (excess,),
        ).fetchall()
        for (k,) in victims:
            self._rows.pop(k, None)
        self._conn.executemany("DELETE FROM questions WHERE question_hash = ?", victims)
        self._conn.commit()

    def forget(self, q: Question) -> None:
        with self._lock:
            assert self._conn is not None
            key = self.key_for(q)
            self._rows.pop(key, None)
            self._conn.execute("DELETE FROM questions WHERE question_hash = ?", (key,))
            self._conn.commit()

    # ------------------------------------------------------------------ read
    def lookup(self, q: Question) -> CacheHit | None:
        with self._lock:
            self.lookups += 1
            exact = self._rows.get(self.key_for(q))
            candidates = [exact] if exact else list(self._rows.values())
            best: tuple[float, _Row, tuple[int, ...]] | None = None
            for row in candidates:
                scored = self._match(q, row)
                if scored is None:
                    continue
                sim, mapping = scored
                if best is None or sim > best[0]:
                    best = (sim, row, mapping)
            if best is None:
                return None
            sim, row, mapping = best
            self.hits += 1
            if self._conn is not None:
                self._conn.execute(
                    "UPDATE questions SET hits = hits + 1, last_hit = ? WHERE question_hash = ?",
                    (time.time(), row.key),
                )
                self._conn.commit()
            return CacheHit(
                answers=mapping,
                number_answer=row.number_answer,
                confidence=row.confidence,
                reason=row.reason,
                topic=row.topic,
                model=row.model,
                similarity=sim,
                verified=row.verified,
            )

    def _match(self, q: Question, row: _Row) -> tuple[float, tuple[int, ...]] | None:
        if row.qtype != q.question_type.value:
            return None
        if numeric_tokens(q.text) != row.numbers:
            return None
        # image agreement
        if (q.image_hash is None) != (row.image_hash is None):
            return None
        if (
            q.image_hash is not None
            and row.image_hash is not None
            and hamming(q.image_hash, row.image_hash) > self.max_image_distance
        ):
            return None
        text_sim = fuzz.ratio(q.normalized_text, row.text) / 100.0
        if text_sim < self.text_threshold:
            return None
        if not words_compatible(q.normalized_text, row.text):
            return None
        cur = q.normalized_answers
        if len(cur) != len(row.answers):
            return None
        # 1:1 answer mapping by text (answers may be shuffled)
        mapping_cur_for_row: dict[int, int] = {}
        used: set[int] = set()
        answer_sims: list[float] = []
        for ri, rtext in enumerate(row.answers):
            best_j, best_s = -1, 0.0
            for j, ctext in enumerate(cur):
                if j in used or numeric_tokens(ctext) != numeric_tokens(rtext):
                    continue
                s = fuzz.ratio(ctext, rtext) / 100.0
                if s > best_s:
                    best_j, best_s = j, s
            if best_j < 0 or best_s < self.answer_threshold:
                return None
            used.add(best_j)
            mapping_cur_for_row[ri] = best_j
            answer_sims.append(best_s)
        # map stored correct answer texts -> current 1-based indices
        answers: list[int] = []
        for ctext in row.correct:
            try:
                ri = row.answers.index(ctext)
            except ValueError:
                return None
            answers.append(mapping_cur_for_row[ri] + 1)
        if not answers and row.number_answer is None:
            return None
        sim = min([text_sim, *answer_sims])
        return sim, tuple(sorted(answers))
