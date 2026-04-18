from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer

import pytest

from kne_guards import db
from kne_guards import server as server_module

SPEC_PAYLOAD = {
    "name": "Test",
    "category": "study",
    "features": ["a"],
    "price_monthly": 1.0,
    "target_segment": "students",
    "substitutes": [],
}


@pytest.fixture
def running_server(monkeypatch, tmp_path):
    """Start a real Handler on a random port backed by an isolated SQLite file."""
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


def _request(port, method, path, body=None, cookie=None):
    url = f"http://127.0.0.1:{port}{path}"
    headers = {}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if cookie:
        headers["Cookie"] = f"session={cookie}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        res = urllib.request.urlopen(req)
        return res.status, res.headers, json.loads(res.read() or b"null")
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, e.headers, (json.loads(raw) if raw else None)


def _cookie(headers) -> str | None:
    set_cookie = headers.get("Set-Cookie", "")
    if not set_cookie:
        return None
    jar = SimpleCookie(set_cookie)
    return jar["session"].value if "session" in jar else None


def _signup(port, email="a@b.com", password="password1"):
    return _request(
        port, "POST", "/auth/signup", {"email": email, "password": password}
    )


def _login(port, email, password):
    return _request(port, "POST", "/auth/login", {"email": email, "password": password})


def test_signup_returns_session_cookie_and_me_works(running_server):
    port = running_server
    status, headers, body = _signup(port)
    assert status == 200
    assert body == {"email": "a@b.com"}
    token = _cookie(headers)
    assert token

    status, _, body = _request(port, "GET", "/auth/me", cookie=token)
    assert status == 200
    assert body["email"] == "a@b.com"
    assert "challenger_ready" in body
    assert isinstance(body["challenger_ready"], bool)


def test_signup_duplicate_email_rejected(running_server):
    port = running_server
    _signup(port)
    status, _, body = _signup(port)
    assert status == 400
    assert "already registered" in body["error"]


def test_short_password_rejected(running_server):
    port = running_server
    status, _, body = _request(
        port, "POST", "/auth/signup", {"email": "a@b.com", "password": "short"}
    )
    assert status == 400
    assert "at least" in body["error"]


def test_login_wrong_password_returns_generic_error(running_server):
    port = running_server
    _signup(port, email="a@b.com", password="password1")
    status, _, body = _login(port, "a@b.com", "wrong-password")
    assert status == 401
    assert body["error"] == "invalid email or password"


def test_login_unknown_email_returns_same_generic_error(running_server):
    port = running_server
    status, _, body = _login(port, "ghost@nowhere.com", "password1")
    assert status == 401
    assert body["error"] == "invalid email or password"


def test_login_issues_new_session_token(running_server):
    port = running_server
    _, h1, _ = _signup(port)
    signup_token = _cookie(h1)
    status, h2, _ = _login(port, "a@b.com", "password1")
    assert status == 200
    login_token = _cookie(h2)
    assert login_token
    assert login_token != signup_token  # session-fixation defense


def test_simulate_requires_auth(running_server):
    port = running_server
    status, _, body = _request(port, "POST", "/simulate", {"spec": SPEC_PAYLOAD})
    assert status == 401
    assert body["error"] == "not authenticated"


def test_simulate_with_session_saves_run(running_server):
    port = running_server
    _, h, _ = _signup(port)
    token = _cookie(h)

    status, _, body = _request(
        port,
        "POST",
        "/simulate",
        {"spec": SPEC_PAYLOAD, "personas": 10, "days": 5, "seed": 1},
        cookie=token,
    )
    assert status == 200
    assert "_run_id" in body
    assert body["product_name"] == "Test"

    status, _, body = _request(port, "GET", "/runs", cookie=token)
    assert status == 200
    assert len(body["runs"]) == 1
    assert body["runs"][0]["kind"] == "simulation"
    assert body["runs"][0]["product_name"] == "Test"


def test_runs_are_scoped_to_owner(running_server):
    port = running_server
    _, ha, _ = _signup(port, email="a@b.com", password="password1")
    token_a = _cookie(ha)
    _, hb, _ = _signup(port, email="c@d.com", password="password1")
    token_b = _cookie(hb)

    _, _, run_a = _request(
        port,
        "POST",
        "/simulate",
        {"spec": SPEC_PAYLOAD, "personas": 10, "days": 5, "seed": 1},
        cookie=token_a,
    )
    run_a_id = run_a["_run_id"]

    # B cannot see A's run in their list
    status, _, body_b_list = _request(port, "GET", "/runs", cookie=token_b)
    assert status == 200
    assert body_b_list["runs"] == []

    # B cannot fetch A's run by id
    status, _, body = _request(port, "GET", f"/runs/{run_a_id}", cookie=token_b)
    assert status == 404

    # A can still see it
    status, _, body = _request(port, "GET", f"/runs/{run_a_id}", cookie=token_a)
    assert status == 200
    assert body["id"] == run_a_id


def test_logout_invalidates_session(running_server):
    port = running_server
    _, h, _ = _signup(port)
    token = _cookie(h)

    status, _, _ = _request(port, "POST", "/auth/logout", cookie=token)
    assert status == 200

    status, _, body = _request(port, "GET", "/auth/me", cookie=token)
    assert status == 401


def test_save_and_delete_spec_roundtrip(running_server):
    port = running_server
    _, h, _ = _signup(port)
    token = _cookie(h)

    status, _, body = _request(
        port, "POST", "/specs", {"name": "My idea", "spec": SPEC_PAYLOAD}, cookie=token
    )
    assert status == 200
    spec_id = body["id"]

    status, _, body = _request(port, "GET", "/specs", cookie=token)
    assert status == 200
    assert len(body["specs"]) == 1
    assert body["specs"][0]["name"] == "My idea"
    assert body["specs"][0]["spec"]["name"] == "Test"

    status, _, _ = _request(port, "DELETE", f"/specs/{spec_id}", cookie=token)
    assert status == 200

    status, _, body = _request(port, "GET", "/specs", cookie=token)
    assert body["specs"] == []


def test_save_spec_rejects_invalid_shape(running_server):
    port = running_server
    _, h, _ = _signup(port)
    token = _cookie(h)

    status, _, body = _request(
        port,
        "POST",
        "/specs",
        {"name": "bad", "spec": {"name": "no-other-fields"}},
        cookie=token,
    )
    assert status == 400
    assert "invalid spec" in body["error"]
