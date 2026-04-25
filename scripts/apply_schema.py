"""One-off: apply the Supabase Postgres schema for KNE-Guards.

Idempotent — safe to re-run. Reads SUPABASE_DB_URL from env.
"""

from __future__ import annotations

import os

import psycopg

SCHEMA = """
create table if not exists public.saved_specs (
    id         bigserial primary key,
    user_id    uuid        not null references auth.users(id) on delete cascade,
    name       text        not null,
    spec_json  jsonb       not null,
    created_at timestamptz not null default now()
);
create index if not exists idx_specs_user on public.saved_specs(user_id);

create table if not exists public.saved_runs (
    id           bigserial primary key,
    user_id      uuid        not null references auth.users(id) on delete cascade,
    spec_id      bigint      references public.saved_specs(id) on delete set null,
    kind         text        not null check (kind in ('simulation','challenge')),
    product_name text,
    result_json  jsonb       not null,
    created_at   timestamptz not null default now()
);
create index if not exists idx_runs_user on public.saved_runs(user_id, created_at desc);

alter table public.saved_specs enable row level security;
alter table public.saved_runs  enable row level security;

drop policy if exists "own specs select" on public.saved_specs;
drop policy if exists "own specs insert" on public.saved_specs;
drop policy if exists "own specs update" on public.saved_specs;
drop policy if exists "own specs delete" on public.saved_specs;
create policy "own specs select" on public.saved_specs for select using (auth.uid() = user_id);
create policy "own specs insert" on public.saved_specs for insert with check (auth.uid() = user_id);
create policy "own specs update" on public.saved_specs for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own specs delete" on public.saved_specs for delete using (auth.uid() = user_id);

drop policy if exists "own runs select" on public.saved_runs;
drop policy if exists "own runs insert" on public.saved_runs;
drop policy if exists "own runs update" on public.saved_runs;
drop policy if exists "own runs delete" on public.saved_runs;
create policy "own runs select" on public.saved_runs for select using (auth.uid() = user_id);
create policy "own runs insert" on public.saved_runs for insert with check (auth.uid() = user_id);
create policy "own runs update" on public.saved_runs for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own runs delete" on public.saved_runs for delete using (auth.uid() = user_id);
"""


def main() -> None:
    url = os.environ["SUPABASE_DB_URL"]
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
        conn.commit()
    print("schema applied.")


if __name__ == "__main__":
    main()
