import json
import logging
import time

import pytest

from smart360.core.models import Decision, HistoryEntry
from smart360.health.diagnostics import build_report, check_state_machine, export_report, run_self_test
from smart360.health.monitor import Health, HealthMonitor, PerformanceWatchdog
from smart360.services import Services
from smart360.storage.config import AppConfig, ConfigStore
from smart360.storage.history import HistoryFilter, HistoryStore
from smart360.storage.secrets import RedactingFilter, SecretStore, redact

# ----------------------------------------------------------------------------- config


def test_config_roundtrip(tmp_path):
    s = ConfigStore(tmp_path / "config.json")
    s.update(ai={"provider": "openai", "confidence_threshold": 0.8})
    s2 = ConfigStore(tmp_path / "config.json")
    assert s2.config.ai.provider == "openai" and s2.config.ai.confidence_threshold == 0.8


def test_config_invalid_value_rejected(tmp_path):
    s = ConfigStore(tmp_path / "config.json")
    with pytest.raises(Exception):
        s.update(ai={"confidence_threshold": 5})
    assert s.config.ai.confidence_threshold == 0.75


def test_corrupted_config_falls_back_to_backup(tmp_path):
    p = tmp_path / "config.json"
    s = ConfigStore(p)
    s.update(ai={"provider": "gemini"})
    s.update(first_run_done=True)  # creates .bak of the previous good file
    p.write_text("{ this is broken", encoding="utf-8")
    s2 = ConfigStore(p)
    assert s2.recovered and s2.config.ai.provider == "gemini"


def test_corrupted_config_and_backup_uses_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("\x00\x01garbage", encoding="utf-8")
    s = ConfigStore(p)
    assert s.recovered and s.config == AppConfig()
    assert any(x.name.startswith("config.json.corrupt-") for x in tmp_path.iterdir())


def test_unknown_keys_ignored(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"ai": {"provider": "anthropic", "legacy": 1}, "foo": 2}), encoding="utf-8")
    assert ConfigStore(p).config.ai.provider == "anthropic"


# ----------------------------------------------------------------------------- secrets


def test_redaction():
    text = "key sk-ant-api03-abcdefghijklmnop and AIzaSyA1234567890abcdefghijk x-api-key: secret123"
    red = redact(text)
    assert "sk-ant" not in red and "AIza" not in red and "secret123" not in red


def test_logging_filter_redacts(caplog):
    logger = logging.getLogger("t")
    logger.addFilter(RedactingFilter())
    with caplog.at_level(logging.INFO):
        logger.info("using %s", "sk-ant-api03-SECRETSECRETSECRET")
    assert "SECRET" not in caplog.text


def test_secret_store_env_and_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-value-12345")
    s = SecretStore(dotenv=tmp_path / ".env", use_keyring=False)
    assert s.get("ANTHROPIC_API_KEY") == "sk-ant-env-value-12345"
    s.set("OPENAI_API_KEY", " sk-mem ")
    assert s.get("OPENAI_API_KEY") == "sk-mem"
    (tmp_path / ".env").write_text('GEMINI_API_KEY="AIza-dotenv"\n', encoding="utf-8")
    assert s.get("GEMINI_API_KEY") == "AIza-dotenv"
    assert SecretStore.mask("sk-ant-1234567890abcdef") == "sk-ant…cdef"


# ----------------------------------------------------------------------------- history


def entry(i, decision=Decision.ACCEPTED, conf=0.9, topic="Vorfahrt", unc=False):
    return HistoryEntry(
        f"q{i}",
        f"Frage {i} über 100% Vorfahrt_x",
        ("a", "b"),
        (1,),
        conf,
        decision,
        topic,
        "ai",
        1200,
        time.time() - i,
        unc,
        0.9,
    )


def test_history_query_and_filters(tmp_path):
    h = HistoryStore(tmp_path / "h.db")
    for i in range(10):
        h.add(
            entry(
                i,
                Decision.REJECTED if i % 3 == 0 else Decision.ACCEPTED,
                conf=0.5 + i * 0.05,
                topic="Technik" if i % 2 else "Vorfahrt",
                unc=i == 4,
            )
        )
    assert len(h.query()) == 10
    assert all(e.decision is Decision.REJECTED for e in h.query(HistoryFilter(decision="rejected")))
    assert len(h.query(HistoryFilter(topic="Technik"))) == 5
    assert len(h.query(HistoryFilter(uncertain_only=True))) == 1
    assert len(h.query(HistoryFilter(search="Frage 3"))) == 1
    # LIKE wildcards are escaped
    assert len(h.query(HistoryFilter(search="100%"))) == 10
    assert len(h.query(HistoryFilter(search="_x"))) == 10
    assert len(h.query(HistoryFilter(search="%%%nope"))) == 0
    stats = {t.topic: t for t in h.topics()}
    assert stats["Technik"].count == 5
    assert h.problem_questions()
    h.close()


def test_history_privacy_mode(tmp_path):
    h = HistoryStore(tmp_path / "h.db", store_text=False)
    h.add(entry(1))
    e = h.query()[0]
    assert e.question_text == "" and e.answers == ()
    h.close()


def test_history_retention(tmp_path):
    h = HistoryStore(tmp_path / "h.db")
    from dataclasses import replace

    h.add(replace(entry(1), timestamp=time.time() - 100 * 86400))
    h.add(entry(2))
    assert h.purge_older_than(90) == 1
    assert h.count() == 1
    h.close()


def test_corrupted_history_recovers(tmp_path):
    p = tmp_path / "h.db"
    p.write_bytes(b"garbage" * 500)
    h = HistoryStore(p)
    h.add(entry(1))
    assert h.count() == 1
    h.close()


# ----------------------------------------------------------------------------- health


def test_health_states():
    hm = HealthMonitor()
    hm.ok("Capture")
    assert hm.failure("AI", "x") is Health.DEGRADED
    assert hm.failure("AI", "x") is Health.RECOVERING
    for _ in range(3):
        hm.failure("AI", "x")
    assert hm.components["AI"].state is Health.FAILED
    assert hm.overall() is Health.FAILED
    hm.ok("AI")
    assert hm.components["AI"].consecutive_failures == 0


def test_watchdog_sample_and_leak_slope():
    hm = HealthMonitor()
    wd = PerformanceWatchdog(hm)
    data = wd.sample()
    assert data["threads"] >= 1 and "rss_mb" in data
    wd.rss_history.clear()
    for i in range(60):
        wd.rss_history.append((i * 30.0, 100 + i * 0.5))  # +1 MB/min
    assert 55 < wd.leak_slope_mb_per_h() < 65


# ----------------------------------------------------------------------------- services + diagnostics


def test_services_demo_selftest_and_report(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-VERYSECRETKEY123456")
    svc = Services.create(tmp_path, demo=True)
    try:
        svc.build_engine(None)
        results = run_self_test(svc)
        by = {r.name: r for r in results}
        assert by["State machine"].status == "ok"
        assert by["Storage"].status == "ok"
        assert by["AI"].status == "ok"
        svc.history.add(entry(1))
        report = build_report(svc, results)
        text = json.dumps(report)
        assert "VERYSECRET" not in text
        assert "Frage 1" not in text  # no question texts in diagnostics
        out = export_report(svc, tmp_path / "diag.json", results)
        assert "VERYSECRET" not in out.read_text()
    finally:
        svc.shutdown()


def test_services_missing_key_degrades(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    svc = Services.create(tmp_path, demo=False)
    svc.secrets.use_keyring = False
    try:
        assert svc.build_provider() is None
        assert svc.health.components["AI"].state is Health.DEGRADED
    finally:
        svc.shutdown()


def test_state_machine_self_check():
    assert check_state_machine()[0] == "ok"
