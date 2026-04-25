"""One-off: copy rows from local kne_guards.db into the Supabase Postgres.

Usage:
    1. Boot the new Supabase-backed server.
    2. Click "Start now" in the browser to create an anonymous session.
    3. Open the browser console on the app and copy your UUID:
           (await window._sb.auth.getSession()).data.session.user.id
    4. Run this script with that UUID:
           python scripts/migrate_sqlite_to_supabase.py --user-id <uuid>

    (You can also pass --email if the target user has one.)

Idempotent via a flag in the SQLite DB — rows are marked migrated=1 after
insert and skipped on re-run.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import psycopg

SQLITE_PATH = Path(__file__).resolve().parent.parent / "kne_guards.db"


def _ensure_migrated_column(conn: sqlite3.Connection, table: str) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if "migrated" not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN migrated INTEGER DEFAULT 0")
        conn.commit()


def _lookup_uuid(pg: psycopg.Connection, email: str) -> str | None:
    row = pg.execute(
        "SELECT id FROM auth.users WHERE email = %s", (email.lower(),)
    ).fetchone()
    return row[0] if row else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", dest="user_id", help="Supabase auth.users.id (UUID)")
    ap.add_argument(
        "--email", help="Email registered on Supabase (alternative to --user-id)"
    )
    ap.add_argument("--sqlite", default=str(SQLITE_PATH))
    args = ap.parse_args()
    if not args.user_id and not args.email:
        print("provide --user-id <uuid> or --email <addr>", file=sys.stderr)
        return 1

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("SUPABASE_DB_URL not set", file=sys.stderr)
        return 1

    lite = sqlite3.connect(args.sqlite)
    lite.row_factory = sqlite3.Row
    _ensure_migrated_column(lite, "saved_specs")
    _ensure_migrated_column(lite, "saved_runs")

    with psycopg.connect(db_url) as pg:
        if args.user_id:
            exists = pg.execute(
                "SELECT 1 FROM auth.users WHERE id = %s", (args.user_id,)
            ).fetchone()
            if not exists:
                print(
                    f"no Supabase user with id {args.user_id}. "
                    "Click 'Start now' on the app first, then re-run.",
                    file=sys.stderr,
                )
                return 2
            new_uid = args.user_id
        else:
            new_uid = _lookup_uuid(pg, args.email)
            if not new_uid:
                print(
                    f"no Supabase user found for {args.email}.",
                    file=sys.stderr,
                )
                return 2
        print(f"target Supabase user_id = {new_uid}")

        # specs: old_id -> new_id (so we can remap saved_runs.spec_id)
        spec_map: dict[int, int] = {}
        specs = lite.execute(
            "SELECT id, name, spec_json FROM saved_specs WHERE COALESCE(migrated, 0) = 0"
        ).fetchall()
        for row in specs:
            try:
                payload = json.loads(row["spec_json"])
            except json.JSONDecodeError:
                print(f"  spec {row['id']}: invalid JSON, skipping")
                continue
            new_row = pg.execute(
                """
                INSERT INTO saved_specs (user_id, name, spec_json)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (new_uid, row["name"], json.dumps(payload)),
            ).fetchone()
            spec_map[row["id"]] = new_row[0]
            lite.execute("UPDATE saved_specs SET migrated=1 WHERE id=?", (row["id"],))
        pg.commit()
        lite.commit()
        print(f"specs migrated: {len(spec_map)}")

        runs = lite.execute(
            """
            SELECT id, spec_id, kind, product_name, result_json
            FROM saved_runs
            WHERE COALESCE(migrated, 0) = 0
            """
        ).fetchall()
        inserted_runs = 0
        for row in runs:
            try:
                payload = json.loads(row["result_json"])
            except json.JSONDecodeError:
                print(f"  run {row['id']}: invalid JSON, skipping")
                continue
            new_spec_id = spec_map.get(row["spec_id"]) if row["spec_id"] else None
            pg.execute(
                """
                INSERT INTO saved_runs (user_id, spec_id, kind, product_name, result_json)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    new_uid,
                    new_spec_id,
                    row["kind"],
                    row["product_name"],
                    json.dumps(payload),
                ),
            )
            lite.execute("UPDATE saved_runs SET migrated=1 WHERE id=?", (row["id"],))
            inserted_runs += 1
        pg.commit()
        lite.commit()
        print(f"runs migrated:  {inserted_runs}")

    lite.close()
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
