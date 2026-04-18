from __future__ import annotations

import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from . import db

SESSION_TTL = timedelta(days=30)
MIN_PASSWORD_LEN = 8
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_ph = PasswordHasher()
# Pre-computed dummy hash used to equalize timing on missing-email logins,
# defending against account-enumeration via response-time side-channel.
_DUMMY_HASH = _ph.hash("dummy-password-for-timing-equalization")


class AuthError(Exception):
    """Raised when a signup or login request cannot be fulfilled."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expiry_iso() -> str:
    return (datetime.now(timezone.utc) + SESSION_TTL).isoformat()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate(email: str, password: str) -> tuple[str, str]:
    email = _normalize_email(email)
    if not EMAIL_RE.match(email):
        raise AuthError("invalid email")
    if len(password) < MIN_PASSWORD_LEN:
        raise AuthError(f"password must be at least {MIN_PASSWORD_LEN} characters")
    return email, password


def _issue_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, _expiry_iso()),
    )
    return token


def signup(email: str, password: str) -> str:
    """Create a user and return a fresh session token. Auto-logs-in on success."""
    email, password = _validate(email, password)
    password_hash = _ph.hash(password)
    conn = db.get_connection()
    try:
        try:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, password_hash),
            )
        except sqlite3.IntegrityError as exc:
            raise AuthError("email already registered") from exc
        token = _issue_session(conn, cur.lastrowid)
        conn.commit()
        return token
    finally:
        conn.close()


def login(email: str, password: str) -> str:
    """Return a fresh session token. Generic error on any failure (no enumeration)."""
    email = _normalize_email(email)
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
        if row is None:
            # Still run a verify on the dummy hash so missing-email and
            # wrong-password paths take roughly the same wall-clock time.
            try:
                _ph.verify(_DUMMY_HASH, password)
            except VerifyMismatchError:
                pass
            raise AuthError("invalid email or password")
        try:
            _ph.verify(row["password_hash"], password)
        except VerifyMismatchError as exc:
            raise AuthError("invalid email or password") from exc
        token = _issue_session(conn, row["id"])
        conn.commit()
        return token
    finally:
        conn.close()


def logout(token: str | None) -> None:
    if not token:
        return
    conn = db.get_connection()
    try:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()


def get_user_from_token(token: str | None) -> dict | None:
    if not token:
        return None
    conn = db.get_connection()
    try:
        row = conn.execute(
            """
            SELECT u.id AS id, u.email AS email, s.expires_at AS expires_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
        if row is None:
            return None
        try:
            expires_at = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            return None
        if expires_at < datetime.now(timezone.utc):
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            return None
        return {"id": row["id"], "email": row["email"]}
    finally:
        conn.close()
