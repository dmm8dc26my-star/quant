-- Run in Supabase SQL Editor. This is a PRIVATE single-owner research app.
-- NEVER publish the service-role key or expose the dashboard publicly.
create table if not exists research_events (
 id text primary key, created_at timestamptz not null default now(),
 ticker text not null, event_type text not null, payload jsonb not null
);
create table if not exists paper_snapshots (
 id text primary key, created_at timestamptz not null default now(),
 ticker text not null, shares numeric not null, price numeric not null,
 cash numeric not null default 0, note text
);
-- Service-role key bypasses RLS; only use in server-side Streamlit secrets.
alter table research_events enable row level security;
alter table paper_snapshots enable row level security;
