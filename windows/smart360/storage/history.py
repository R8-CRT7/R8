"""History + insights (local SQLite, never uploaded)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from smart360.core.models import Decision, HistoryEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id TEXT NOT NULL,
    question_text TEXT NOT NULL,
    answers_json TEXT NOT NULL,
    recommended_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    decision TEXT NOT NULL,
    topic TEXT NOT NULL,
    source TEXT NOT NULL,
    processing_ms REAL NOT NULL,
    timestamp REAL NOT NULL,
    uncertain INTEGER NOT NULL,
    ocr_confidence REAL NOT NULL,
    model TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_h_ts ON history(timestamp);
CREATE INDEX IF NOT EXISTS idx_h_topic ON history(topic);
"""


@dataclass(frozen=True, slots=True)
class HistoryFilter:
    search: str = ""
    topic: str = ""
    min_confidence: float = 0.0
    max_confidence: float = 1.0
    decision: str = ""  # accepted / rejected / ...
    uncertain_only: bool = False
    limit: int = 500


@dataclass(frozen=True, slots=True)
class TopicStat:
    topic: str
    count: int
    avg_confidence: float
    rejected: int
    uncertain: int
    avg_ms: float

    @property
    def difficulty(self) -> float:
        """0..1 - high when confidence is low and rejections/uncertainty are frequent."""
        if self.count == 0:
            return 0.0
        return min(1.0, (1 - self.avg_confidence) * 1.5 + (self.rejected + self.uncertain) / self.count * 0.6)


class HistoryStore:
    def __init__(self, path: Path | str, store_text: bool = True):
        self.path = Path(path)
        self.store_text = store_text
        self._lock = threading.RLock()
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = self._connect()
        except sqlite3.DatabaseError:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            self.path.replace(self.path.with_name(self.path.name + f".corrupt-{stamp}"))
            self._conn = self._connect()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False, timeout=5)
        try:
            ok = conn.execute("PRAGMA quick_check").fetchone()
            if not ok or ok[0] != "ok":
                raise sqlite3.DatabaseError("quick_check failed")
            conn.executescript(_SCHEMA)
            conn.commit()
        except Exception:
            conn.close()
            raise
        return conn

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def add(self, e: HistoryEntry) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO history(question_id, question_text, answers_json, recommended_json, confidence,"
                " decision, topic, source, processing_ms, timestamp, uncertain, ocr_confidence, model)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    e.question_id,
                    e.question_text if self.store_text else "",
                    json.dumps(list(e.answers) if self.store_text else []),
                    json.dumps(list(e.recommended)),
                    e.confidence,
                    e.decision.value,
                    e.topic,
                    e.source,
                    e.processing_ms,
                    e.timestamp,
                    int(e.uncertain),
                    e.ocr_confidence,
                    e.model,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid or 0)

    def update_decision(self, row_id: int, decision: Decision) -> None:
        with self._lock:
            self._conn.execute("UPDATE history SET decision = ? WHERE id = ?", (decision.value, row_id))
            self._conn.commit()

    def query(self, f: HistoryFilter | None = None) -> list[HistoryEntry]:
        f = f or HistoryFilter()
        sql = "SELECT * FROM history WHERE confidence BETWEEN ? AND ?"
        args: list[object] = [f.min_confidence, f.max_confidence]
        if f.search:
            sql += " AND (question_text LIKE ? ESCAPE '\\' OR answers_json LIKE ? ESCAPE '\\')"
            pat = "%" + f.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            args += [pat, pat]
        if f.topic:
            sql += " AND topic = ?"
            args.append(f.topic)
        if f.decision:
            sql += " AND decision = ?"
            args.append(f.decision)
        if f.uncertain_only:
            sql += " AND uncertain = 1"
        sql += " ORDER BY timestamp DESC LIMIT ?"
        args.append(int(f.limit))
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r: tuple) -> HistoryEntry:
        return HistoryEntry(
            id=r[0],
            question_id=r[1],
            question_text=r[2],
            answers=tuple(json.loads(r[3])),
            recommended=tuple(json.loads(r[4])),
            confidence=r[5],
            decision=Decision(r[6]),
            topic=r[7],
            source=r[8],
            processing_ms=r[9],
            timestamp=r[10],
            uncertain=bool(r[11]),
            ocr_confidence=r[12],
            model=r[13],
        )

    def topics(self) -> list[TopicStat]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT topic, COUNT(*), AVG(confidence), SUM(decision='rejected'), SUM(uncertain),"
                " AVG(processing_ms) FROM history GROUP BY topic ORDER BY COUNT(*) DESC"
            ).fetchall()
        return [
            TopicStat(r[0] or "Sonstiges", r[1], r[2] or 0, r[3] or 0, r[4] or 0, r[5] or 0) for r in rows
        ]

    def problem_questions(self, limit: int = 20) -> list[HistoryEntry]:
        """My problematic questions: rejected, uncertain or low confidence."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM history WHERE decision = 'rejected' OR uncertain = 1 OR confidence < 0.75"
                " ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row(r) for r in rows]

    def low_ocr(self, limit: int = 10) -> list[HistoryEntry]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM history WHERE ocr_confidence < 0.7 ORDER BY ocr_confidence ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row(r) for r in rows]

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM history").fetchone()[0])

    def purge_older_than(self, days: int) -> int:
        cutoff = time.time() - days * 86400
        with self._lock:
            cur = self._conn.execute("DELETE FROM history WHERE timestamp < ?", (cutoff,))
            self._conn.commit()
            return cur.rowcount

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM history")
            self._conn.commit()
