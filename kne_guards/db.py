from __future__ import annotations

import os

import psycopg
from psycopg.rows import dict_row


def _db_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError(
            "SUPABASE_DB_URL is not set. Add it to .env "
            "(Supabase → Settings → Database → Connection string)."
        )
    return url


def get_connection() -> psycopg.Connection:
    """Open a psycopg connection that yields dict-like rows."""
    return psycopg.connect(_db_url(), row_factory=dict_row)
