"""Fast mastery: choose the next task by expected mastery gain per minute - not 'as many questions as possible'.

Priority classes (lower = earlier), then gain per minute inside a class:
  1 important knowledge gaps   (never practised or mastery < 40 on an exam-critical subtopic)
  2 recurring mistakes          (>= 2 of the last 5 attempts wrong)
  3 almost forgotten rules       (retention < 0.5 although once learned)
  4 new / updated rules          (knowledge object version newer than the last practice)
  5 uncertain topics             (often answered 'unsure' or mastery 40-79)
  6 exam simulation              (when most subtopics are >= 80)
  7 mastered topics (control)    (only when due)
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from smart360.tutor.mastery import MasteryState

MINUTES_PER_ITEM = {"learn": 1.5, "review": 0.8}


@dataclass(frozen=True)
class SubtopicInfo:
    subtopic: str
    topic: str
    exam_relevance: int  # 1..3
    version: int = 1
    updated_at: float = 0.0  # when the newest knowledge version was verified


@dataclass(frozen=True)
class NextTask:
    kind: str  # learn | review | exam
    subtopic: str | None
    priority_class: int
    gain_per_minute: float
    reason: str


def plan(infos: list[SubtopicInfo], states: dict[str, MasteryState], now: float | None = None,
         limit: int = 5) -> list[NextTask]:
    now = now or time.time()
    tasks: list[NextTask] = []
    mastered = 0
    for info in infos:
        st = states.get(info.subtopic)
        importance = 0.34 + info.exam_relevance / 3
        if st is None or st.attempts == 0:
            gain = importance * 1.0 / MINUTES_PER_ITEM["learn"]
            cls = 1 if info.exam_relevance >= 2 else 5
            tasks.append(NextTask("learn", info.subtopic, cls, gain, "noch nie geübt"))
            continue
        if st.mastered:
            mastered += 1
        gap = (100 - st.score) / 100
        forget = 1 - st.retention
        err = 1 + 0.5 * st.recent_mistakes
        minutes = MINUTES_PER_ITEM["review" if st.score >= 60 else "learn"]
        gain = gap * importance * (1 + forget) * err / minutes
        if st.score < 40 and info.exam_relevance >= 2:
            cls, why = 1, f"Wissenslücke (Mastery {st.score:.0f})"
        elif st.recent_mistakes >= 2:
            cls, why = 2, f"wiederkehrende Fehler ({st.recent_mistakes} der letzten 5)"
        elif st.retention < 0.5 and st.score >= 40:
            cls, why = 3, f"fast vergessen (Retention {st.retention:.0%})"
        elif info.updated_at and st.last_seen and info.updated_at > st.last_seen:
            cls, why = 4, "Regel neu/aktualisiert seit der letzten Übung"
        elif st.unsure_rate > 0.3 or st.score < 80:
            cls, why = 5, f"unsicher (Mastery {st.score:.0f})"
        elif st.due_at and st.due_at <= now:
            cls, why = 7, "Kontrolle (fällig)"
        else:
            continue  # mastered and not due
        tasks.append(NextTask("learn" if st.score < 60 else "review", info.subtopic, cls, gain, why))
    if infos and mastered / len(infos) >= 0.8:
        tasks.append(NextTask("exam", None, 6, 0.5, "die meisten Themen sicher - Prüfungssimulation"))
    tasks.sort(key=lambda t: (t.priority_class, -t.gain_per_minute))
    return tasks[:limit]
