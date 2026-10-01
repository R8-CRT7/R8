"""Learner profile store (SQLite, local, per user). One row per attempt; everything else is derived."""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Attempt:
    ts: float
    item_id: str
    topic: str
    subtopic: str
    variant: str
    correct: bool
    chosen: str = ""
    expected: str = ""
    response_ms: int = 0
    difficulty: int = 2
    mistake_type: str = ""
    mode: str = "learn"  # learn | exam | review
    unsure: bool = False


SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL, item_id TEXT NOT NULL, topic TEXT NOT NULL, subtopic TEXT NOT NULL, variant TEXT NOT NULL,
  correct INTEGER NOT NULL, chosen TEXT, expected TEXT, response_ms INTEGER, difficulty INTEGER,
  mistake_type TEXT, mode TEXT, unsure INTEGER
);
CREATE INDEX IF NOT EXISTS ix_attempts_sub ON attempts(subtopic, ts);
"""


class LearnerStore:
    def __init__(self, path: Path | str = ":memory:"):
        self._lock = threading.Lock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.executescript(SCHEMA)

    def add(self, a: Attempt) -> None:
        with self._lock:
            self.db.execute(
                "INSERT INTO attempts(ts,item_id,topic,subtopic,variant,correct,chosen,expected,response_ms,"
                "difficulty,mistake_type,mode,unsure) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (a.ts or time.time(), a.item_id, a.topic, a.subtopic, a.variant, int(a.correct), a.chosen,
                 a.expected, a.response_ms, a.difficulty, a.mistake_type, a.mode, int(a.unsure)),
            )
            self.db.commit()

    def attempts(self, subtopic: str | None = None) -> list[Attempt]:
        q = "SELECT ts,item_id,topic,subtopic,variant,correct,chosen,expected,response_ms,difficulty,mistake_type,mode,unsure FROM attempts"
        args: tuple = ()
        if subtopic:
            q += " WHERE subtopic=?"
            args = (subtopic,)
        with self._lock:
            rows = self.db.execute(q + " ORDER BY ts", args).fetchall()
        return [Attempt(r[0], r[1], r[2], r[3], r[4], bool(r[5]), r[6] or "", r[7] or "", r[8] or 0, r[9] or 2,
                        r[10] or "", r[11] or "learn", bool(r[12])) for r in rows]

    def subtopics(self) -> list[str]:
        with self._lock:
            return [r[0] for r in self.db.execute("SELECT DISTINCT subtopic FROM attempts ORDER BY subtopic")]

    def close(self) -> None:
        self.db.close()
