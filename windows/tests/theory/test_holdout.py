"""Holdout enforcement: golden sets (internal and external) never feed training/optimisation.

* read tracer: loading the KB, its OCR vocabulary and generating train/validation items never reads a golden file
* static check: only splits.py (loader) and tools/theory_eval.py (evaluation) reference the external set
* near-duplicate check: no golden question/answer appears (almost) verbatim in claims, lexicon or keywords
* the external loader refuses any purpose other than evaluation and validates the import format
"""

import builtins
import json
import pathlib
import re

import pytest

from smart360.theory import splits
from smart360.theory.kb import KnowledgeBase, knowledge_dir
from smart360.theory.text import content

SRC = pathlib.Path(__file__).resolve().parents[2]  # windows/


def _golden_texts() -> list[str]:
    texts = []
    for it in splits.load_golden_internal() + splits.load_golden_external(purpose="evaluation"):
        texts.append(it.question.text)
        texts += it.question.answers
    return texts


def test_training_never_reads_golden_files(monkeypatch):
    reads: list[str] = []
    real_open, real_read_text, real_read_bytes = builtins.open, pathlib.Path.read_text, pathlib.Path.read_bytes

    def rec_open(file, *a, **k):  # type: ignore[no-untyped-def]
        reads.append(str(file))
        return real_open(file, *a, **k)

    def rec_read_text(self, *a, **k):  # type: ignore[no-untyped-def]
        reads.append(str(self))
        return real_read_text(self, *a, **k)

    def rec_read_bytes(self, *a, **k):  # type: ignore[no-untyped-def]
        reads.append(str(self))
        return real_read_bytes(self, *a, **k)

    monkeypatch.setattr(builtins, "open", rec_open)
    monkeypatch.setattr(pathlib.Path, "read_text", rec_read_text)
    monkeypatch.setattr(pathlib.Path, "read_bytes", rec_read_bytes)
    from smart360.theory import generator

    kb = KnowledgeBase.load()
    _ = kb.vocabulary
    generator.all_items(kb)
    if hasattr(generator, "validation_items"):
        generator.validation_items(kb)
    bad = [r for r in reads if "golden" in r.replace("\\", "/").split("tests/theory/")[-1]]
    assert reads, "tracer did not see any reads"
    assert bad == [], bad


def test_only_the_loader_and_the_evaluator_reference_the_external_set():
    allowed = {"smart360/theory/splits.py", "tools/theory_eval.py", "tools/external_import.py"}
    hits = []
    for p in list((SRC / "smart360").rglob("*.py")) + list((SRC / "tools").rglob("*.py")):
        rel = p.relative_to(SRC).as_posix()
        if re.search(r"golden_external|EXTERNAL_DIR|load_golden_external", p.read_text(encoding="utf-8")) and rel not in allowed:
            hits.append(rel)
    assert hits == []


def test_external_loader_is_evaluation_only():
    with pytest.raises(PermissionError):
        splits.load_golden_external(purpose="training")  # type: ignore[arg-type]
    with pytest.raises(PermissionError):
        splits.load_external_records(purpose="tuning")  # type: ignore[arg-type]


def test_external_import_format_is_validated():
    ok = {"id": "E1", "topic": "05_priority", "question": "Wer hat Vorfahrt?", "answers": ["A", "B"],
          "correct": [1], "source": "external-human-authored", "author": "Tester"}
    splits.ExternalItem.model_validate(ok).to_item()
    with pytest.raises(ValueError):
        splits.ExternalItem.model_validate({**ok, "source": "ai-generated"})
    with pytest.raises(ValueError):
        splits.ExternalItem.model_validate({**ok, "correct": [3]}).to_item()
    with pytest.raises(ValueError):
        splits.ExternalItem.model_validate({**ok, "topic": "99_unknown"})
    with pytest.raises(ValueError):
        splits.ExternalItem.model_validate({**ok, "author": ""})


def _near(a: set[str], b: set[str]) -> bool:
    return len(a) >= 4 and len(b) >= 4 and len(a & b) / len(a | b) >= 0.75


def test_no_golden_text_is_memorised_in_the_knowledge_base():
    """No claim, keyword, lexicon pattern or rule text is a (near-)copy of a golden question or answer."""
    goldens = [content(t) for t in _golden_texts()]
    kb_texts = []
    for p in knowledge_dir().rglob("*.json"):
        if "sources" in p.parts:
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for s in re.findall(r'"(?:statement|rule|title|meaning|pattern|patterns)":\s*"([^"]+)"', json.dumps(data, ensure_ascii=False)):
            kb_texts.append(s)
        for lst in re.findall(r'"(?:keywords|context|patterns)":\s*\[([^\]]*)\]', json.dumps(data, ensure_ascii=False)):
            kb_texts += re.findall(r'"([^"]+)"', lst)
    texts = _golden_texts()
    official = {sg.name.lower() for sg in KnowledgeBase.load().signs.values()}  # names from the law text itself
    hits = []
    for k in set(kb_texts) - {x for x in kb_texts if x.lower().rstrip(".") in official}:
        ck = content(k)
        if len(ck) >= 4:
            hits += [(t, k) for t, g in zip(texts, goldens) if _near(g, ck)]
    assert hits == [], hits[:5]


def test_ai_prompts_contain_no_golden_text():
    goldens = [content(t) for t in _golden_texts()]
    for p in (SRC / "smart360" / "ai").rglob("*.py"):
        for s in re.findall(r'"([^"]{20,})"', p.read_text(encoding="utf-8")):
            assert not any(_near(g, content(s)) for g in goldens), (p, s)
