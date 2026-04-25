from __future__ import annotations

import os

import jwt
from jwt import PyJWKClient


class AuthError(Exception):
    """Raised when a bearer token is missing, malformed, or rejected."""


_jwks_cache: dict[str, PyJWKClient] = {}


def _jwks_client() -> PyJWKClient:
    """Return a cached PyJWKClient for the current Supabase project."""
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL is not set.")
    jwks_url = f"{url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    client = _jwks_cache.get(jwks_url)
    if client is None:
        client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
        _jwks_cache[jwks_url] = client
    return client


def user_from_bearer(token: str | None) -> dict | None:
    """Return {id, email} for a valid Supabase access token, else None."""
    if not token:
        return None
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError:
        return None
    user_id = claims.get("sub")
    if not user_id:
        return None
    return {"id": user_id, "email": claims.get("email", "")}
