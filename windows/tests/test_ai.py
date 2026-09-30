import json
import threading
import time
from types import SimpleNamespace

import pytest

from smart360.ai.anthropic_provider import AnthropicProvider
from smart360.ai.base import ProviderError
from smart360.ai.gemini_provider import GeminiProvider
from smart360.ai.mock_provider import MockProvider
from smart360.ai.openai_provider import OpenAIProvider
from smart360.ai.resilience import AIUnavailable, BreakerState, CircuitBreaker, ResilientSolver
from smart360.ai.schema import SchemaViolation, SolveRequest, parse_solve_response

REQ = SolveRequest("Wer hat Vorfahrt?", ("Der blaue PKW", "Der Radfahrer", "Ich"), image_png=b"\x89PNG-fake")
GOOD = {
    "answers": [1, 3],
    "number_answer": None,
    "confidence": 0.96,
    "reason": "Rechts vor links.",
    "uncertain": False,
    "topic": "Vorfahrt",
}


# ----------------------------------------------------------------------------- schema


def test_schema_ok():
    r = parse_solve_response(json.dumps(GOOD), 3, False)
    assert r.answers == [1, 3] and r.topic == "Vorfahrt"


@pytest.mark.parametrize(
    "mutation",
    [
        {"answers": [4]},  # out of range
        {"answers": [0]},
        {"answers": [1, 1]},
        {"confidence": 1.5},
        {"reason": ""},
        {"extra": "field"},
        {"answers": []},  # no answer but not uncertain
        {"number_answer": "12; DROP TABLE"},
    ],
)
def test_schema_rejects(mutation):
    data = {**GOOD, **mutation}
    with pytest.raises(SchemaViolation):
        parse_solve_response(data, 3, False)


def test_schema_rejects_free_text():
    with pytest.raises(SchemaViolation):
        parse_solve_response("Die Antwort ist 1 und 3", 3, False)


def test_unknown_topic_normalized():
    r = parse_solve_response({**GOOD, "topic": "Quatsch"}, 3, False)
    assert r.topic == "Sonstiges"


def test_number_question():
    r = parse_solve_response({**GOOD, "answers": [], "number_answer": "2,5"}, 0, True)
    assert r.number_answer == "2,5"
    with pytest.raises(SchemaViolation):
        parse_solve_response({**GOOD, "answers": [], "number_answer": None}, 0, True)


def test_uncertain_allows_empty():
    r = parse_solve_response({**GOOD, "answers": [], "uncertain": True}, 3, False)
    assert r.uncertain


# ------------------------------------------------------------------ providers with fake SDK clients


class FakeAnthropic:
    def __init__(self, text, stop_reason="end_turn"):
        self.calls = []
        msg = SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
            stop_reason=stop_reason,
            model="claude-opus-5-5",
            usage=SimpleNamespace(input_tokens=1500, output_tokens=90),
        )
        create = lambda **kw: (self.calls.append(kw), msg)[1]  # noqa: E731
        self.messages = SimpleNamespace(create=create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=create))


def test_anthropic_request_shape_and_parse():
    fake = FakeAnthropic(json.dumps(GOOD))
    p = AnthropicProvider("sk-test", client=fake)
    res = p.solve_question(REQ)
    assert res.response.answers == [1, 3]
    kw = fake.calls[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert kw["output_config"]["effort"] == "low"
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert "temperature" not in kw
    content = kw["messages"][0]["content"]
    assert content[0]["type"] == "image" and content[-1]["type"] == "text"
    assert res.input_tokens == 1500
    assert p.estimate_cost(1_000_000, 0) == 4.0


def test_anthropic_haiku_has_no_effort_or_fallback():
    fake = FakeAnthropic(json.dumps(GOOD))
    p = AnthropicProvider("sk", model="claude-haiku-4-5", client=fake)
    p.solve_question(REQ)
    kw = fake.calls[0]
    assert "effort" not in kw["output_config"] and "fallbacks" not in kw


def test_anthropic_refusal_and_invalid():
    with pytest.raises(ProviderError) as e:
        AnthropicProvider("sk", client=FakeAnthropic("{}", "refusal")).solve_question(REQ)
    assert e.value.kind == "refusal" and not e.value.retryable
    with pytest.raises(ProviderError) as e:
        AnthropicProvider("sk", client=FakeAnthropic("not json")).solve_question(REQ)
    assert e.value.kind == "invalid" and e.value.retryable


def test_anthropic_missing_key():
    with pytest.raises(ProviderError) as e:
        AnthropicProvider(None).solve_question(REQ)
    assert e.value.kind == "config"


def test_anthropic_sdk_errors_are_mapped():
    import anthropic
    import httpx2

    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def boom(**kw):
        raise anthropic.APIConnectionError(request=req)

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=boom)))
    with pytest.raises(ProviderError) as e:
        AnthropicProvider("sk", client=fake).solve_question(REQ)
    assert e.value.kind == "network" and e.value.retryable

    def rate(**kw):
        raise anthropic.RateLimitError(
            "slow down", response=httpx2.Response(429, request=req, headers={"retry-after": "3"}), body=None
        )

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=rate)))
    with pytest.raises(ProviderError) as e:
        AnthropicProvider("sk", client=fake).solve_question(REQ)
    assert e.value.kind == "rate_limit" and e.value.retry_after == 3.0


def test_openai_fake_client():
    calls = []
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(GOOD), refusal=None))],
        model="gpt-6-luna",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )
    fake = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: (calls.append(kw), resp)[1]))
    )
    res = OpenAIProvider("sk", client=fake).solve_question(REQ)
    assert res.response.answers == [1, 3]
    assert calls[0]["response_format"]["json_schema"]["strict"] is True


def test_gemini_fake_client():
    resp = SimpleNamespace(
        text=json.dumps(GOOD), usage_metadata=SimpleNamespace(prompt_token_count=7, candidates_token_count=3)
    )
    calls = []
    fake = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kw: (calls.append(kw), resp)[1]))
    res = GeminiProvider("key", client=fake).solve_question(REQ)
    assert res.response.answers == [1, 3] and res.input_tokens == 7
    assert calls[0]["config"].response_mime_type == "application/json"


# ----------------------------------------------------------------------------- resilience


def solver(provider, **kw):
    kw.setdefault("sleep", lambda s: None)
    return ResilientSolver(provider, **kw)


def test_retry_then_success():
    p = MockProvider(latency_s=0, failures=[ProviderError("net", True, "network")] * 2)
    s = solver(p, max_retries=2)
    assert s.solve(REQ).response.answers == [1]
    assert p.calls == 3


def test_retries_exhausted():
    p = MockProvider(latency_s=0, failures=[ProviderError("net", True, "network")] * 5)
    with pytest.raises(ProviderError):
        solver(p, max_retries=2).solve(REQ)
    assert p.calls == 3


def test_non_retryable_not_retried():
    p = MockProvider(latency_s=0, failures=[ProviderError("bad", False, "invalid")])
    with pytest.raises(ProviderError):
        solver(p).solve(REQ)
    assert p.calls == 1


def test_auth_error_does_not_open_breaker():
    br = CircuitBreaker(failure_threshold=1)
    p = MockProvider(latency_s=0, failures=[ProviderError("auth", False, "auth")])
    with pytest.raises(ProviderError):
        solver(p, breaker=br).solve(REQ)
    assert br.state is BreakerState.CLOSED


def test_timeout():
    p = MockProvider(latency_s=2.0)
    s = solver(p, timeout_s=0.2, max_retries=0)
    t0 = time.perf_counter()
    with pytest.raises(ProviderError) as e:
        s.solve(REQ)
    assert e.value.kind == "timeout"
    assert time.perf_counter() - t0 < 1.0
    s.shutdown()


def test_circuit_breaker_opens_and_half_opens():
    now = [0.0]
    br = CircuitBreaker(failure_threshold=2, cooldown_s=10, clock=lambda: now[0])
    p = MockProvider(latency_s=0, failures=[ProviderError("x", True, "server")] * 3)
    s = solver(p, breaker=br, max_retries=0)
    for _ in range(2):
        with pytest.raises(ProviderError):
            s.solve(REQ)
    assert br.state is BreakerState.OPEN
    with pytest.raises(AIUnavailable):
        s.solve(REQ)
    assert p.calls == 2  # no call while open
    now[0] = 11
    assert br.state is BreakerState.HALF_OPEN
    with pytest.raises(ProviderError):
        s.solve(REQ)  # probe fails -> open again
    assert br.state is BreakerState.OPEN
    now[0] = 22
    assert s.solve(REQ).response.answers == [1]  # probe succeeds
    assert br.state is BreakerState.CLOSED


def test_dedup_concurrent_identical_requests():
    p = MockProvider(latency_s=0.3)
    s = solver(p)
    out = []
    ts = [threading.Thread(target=lambda: out.append(s.solve(REQ))) for _ in range(5)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(out) == 5 and p.calls == 1


def test_provider_crash_is_contained():
    class Crashy(MockProvider):
        def solve_question(self, req):
            raise KeyError("bug")

    with pytest.raises(ProviderError) as e:
        solver(Crashy(latency_s=0), max_retries=1).solve(REQ)
    assert e.value.kind == "server"


def test_cost_tracking():
    s = solver(MockProvider(latency_s=0))
    s.solve(REQ)
    snap = s.costs.snapshot()
    assert snap["requests"] == 1 and snap["input_tokens"] == 800
