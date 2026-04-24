from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer

import pytest

from kne_guards import db, server as server_module
from kne_guards.challenger import challenge_pitch, improve_pitch_expression
from kne_guards.models import ProductSpec


def _spec() -> ProductSpec:
    return ProductSpec(
        name="Test",
        category="study",
        features=["spaced repetition", "LaTeX support"],
        price_monthly=8.0,
        target_segment="undergrad STEM",
        substitutes=["Anki"],
    )


_FAKE_CRITIQUE = {
    "verdict": "Skeptical.",
    "assumption_challenges": [
        {
            "claim": "students will pay",
            "pushback": "free alt exists",
            "severity": "high",
        }
    ],
    "feature_critiques": [
        {"feature": "spaced repetition", "critique": "table stakes"},
        {"feature": "LaTeX support", "critique": "niche"},
    ],
    "substitute_risks": [{"substitute": "Anki", "why_it_wins": "free, established"}],
    "segment_coherence": {"assessment": "broad", "concerns": ["varies by major"]},
    "pricing_risks": {"assessment": "high vs free alt", "concerns": ["anchoring"]},
    "kill_shots": [
        {"risk": "free substitute", "why_it_kills": "no switching incentive"}
    ],
    "steelman": "Could work if bundled with curriculum.",
}

_FAKE_EXPRESSION = {
    "founder_framing": "Test gives undergrad STEM students a simpler way to stay on top of studying.",
    "elevator_pitch": "Test helps undergrad STEM students turn course material into repeatable study sessions without building their own workflow.",
    "pitch_deck_opening": "Students do not need more study tools. They need one that fits the way coursework already piles up.",
    "audience_pains": [
        "Students lose time stitching together fragmented study workflows.",
        "Most tools require setup before they feel useful.",
    ],
    "differentiators": [
        "Combines spaced repetition with LaTeX-friendly study material.",
        "Targets undergrad STEM students directly instead of generic learners.",
    ],
    "story_beats": [
        "The problem is workflow overhead, not lack of content.",
        "The first win has to happen in the first study session.",
    ],
}


class _FakeFunction:
    def __init__(self, arguments: str, name: str = "emit_critique") -> None:
        self.arguments = arguments
        self.name = name


class _FakeToolCall:
    def __init__(self, payload: dict, tool_name: str = "emit_critique") -> None:
        self.function = _FakeFunction(json.dumps(payload), name=tool_name)


class _FakeMessage:
    def __init__(self, payload: dict, tool_name: str = "emit_critique") -> None:
        self.tool_calls = [_FakeToolCall(payload, tool_name=tool_name)]


class _FakeChoice:
    def __init__(self, payload: dict, tool_name: str = "emit_critique") -> None:
        self.message = _FakeMessage(payload, tool_name=tool_name)


class _FakeResponse:
    def __init__(self, payload: dict, tool_name: str = "emit_critique") -> None:
        self.choices = [_FakeChoice(payload, tool_name=tool_name)]


class _FakeCompletions:
    def __init__(self, payload: dict, tool_name: str = "emit_critique") -> None:
        self.payload = payload
        self.tool_name = tool_name
        self.last_call: dict | None = None

    def create(self, **kwargs):
        self.last_call = kwargs
        return _FakeResponse(self.payload, tool_name=self.tool_name)


class _FakeChat:
    def __init__(self, payload: dict, tool_name: str = "emit_critique") -> None:
        self.completions = _FakeCompletions(payload, tool_name=tool_name)


class _FakeClient:
    def __init__(self, payload: dict = _FAKE_CRITIQUE, tool_name: str = "emit_critique") -> None:
        self.chat = _FakeChat(payload, tool_name=tool_name)


def test_challenge_pitch_returns_critique_and_forces_tool():
    fake = _FakeClient()
    result = challenge_pitch(_spec(), pitch_text="our pitch", client=fake)

    assert result == _FAKE_CRITIQUE
    call = fake.chat.completions.last_call
    assert call is not None
    assert call["tool_choice"] == {"type": "function", "function": {"name": "emit_critique"}}
    assert any(t.get("function", {}).get("name") == "emit_critique" for t in call["tools"])
    # Spec fields should make it into the user prompt
    user_content = next(m["content"] for m in call["messages"] if m["role"] == "user")
    assert "Test" in user_content
    assert "$8.00" in user_content
    assert "Anki" in user_content
    assert "our pitch" in user_content


def test_improve_pitch_expression_returns_structured_output_and_forces_tool():
    fake = _FakeClient(_FAKE_EXPRESSION, tool_name="emit_expression_help")
    result = improve_pitch_expression(_spec(), pitch_text="our pitch", client=fake)

    assert result == _FAKE_EXPRESSION
    call = fake.chat.completions.last_call
    assert call is not None
    assert call["tool_choice"] == {"type": "function", "function": {"name": "emit_expression_help"}}
    assert any(t.get("function", {}).get("name") == "emit_expression_help" for t in call["tools"])
    user_content = next(m["content"] for m in call["messages"] if m["role"] == "user")
    assert "Test" in user_content
    assert "$8.00" in user_content
    assert "Anki" in user_content
    assert "our pitch" in user_content


@pytest.fixture
def running_server(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("KNE_DB_PATH", str(db_file))
    db.init_db()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server_module.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def _spec_payload() -> dict:
    return {
        "name": "Test",
        "category": "study",
        "features": ["a"],
        "price_monthly": 1.0,
        "target_segment": "students",
        "substitutes": [],
    }


def _signup(port: int) -> str:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/auth/signup",
        data=json.dumps({"email": "a@b.com", "password": "password1"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as res:
        set_cookie = res.headers.get("Set-Cookie", "")
    return SimpleCookie(set_cookie)["session"].value


def _post(port: int, path: str, body: dict, cookie: str | None = None):
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = f"session={cookie}"
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def test_challenge_endpoint_error_when_key_missing(monkeypatch, running_server):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    port = running_server
    cookie = _signup(port)
    status, data = _post(port, "/challenge", {"spec": _spec_payload()}, cookie=cookie)
    assert status == 200
    assert data == {"error": "OPENAI_API_KEY not set"}


def test_challenge_endpoint_requires_auth(running_server):
    port = running_server
    status, data = _post(port, "/challenge", {"spec": _spec_payload()})
    assert status == 401


def test_express_idea_endpoint_error_when_key_missing(monkeypatch, running_server):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    port = running_server
    cookie = _signup(port)
    status, data = _post(port, "/express-idea", {"spec": _spec_payload()}, cookie=cookie)
    assert status == 200
    assert data == {"error": "OPENAI_API_KEY not set"}


def test_express_idea_endpoint_requires_auth(running_server):
    port = running_server
    status, data = _post(port, "/express-idea", {"spec": _spec_payload()})
    assert status == 401


def test_challenge_endpoint_wires_through_to_challenger(monkeypatch, running_server):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    captured: dict = {}

    def fake_challenge_pitch(spec, *, pitch_text=None, model=None):
        captured["spec"] = spec
        captured["pitch_text"] = pitch_text
        captured["model"] = model
        return dict(_FAKE_CRITIQUE)

    monkeypatch.setattr(server_module, "challenge_pitch", fake_challenge_pitch)

    port = running_server
    cookie = _signup(port)
    status, data = _post(
        port,
        "/challenge",
        {"spec": _spec_payload(), "pitch_text": "my pitch"},
        cookie=cookie,
    )
    assert status == 200
    assert "_run_id" in data
    assert {k: v for k, v in data.items() if k != "_run_id"} == _FAKE_CRITIQUE
    assert captured["spec"].name == "Test"
    assert captured["pitch_text"] == "my pitch"


def test_express_idea_endpoint_wires_through(monkeypatch, running_server):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    captured: dict = {}

    def fake_improve_pitch_expression(spec, *, pitch_text=None, model=None):
        captured["spec"] = spec
        captured["pitch_text"] = pitch_text
        captured["model"] = model
        return dict(_FAKE_EXPRESSION)

    monkeypatch.setattr(server_module, "improve_pitch_expression", fake_improve_pitch_expression)

    port = running_server
    cookie = _signup(port)
    status, data = _post(
        port,
        "/express-idea",
        {"spec": _spec_payload(), "pitch_text": "my pitch"},
        cookie=cookie,
    )
    assert status == 200
    assert data == _FAKE_EXPRESSION
    assert captured["spec"].name == "Test"
    assert captured["pitch_text"] == "my pitch"
