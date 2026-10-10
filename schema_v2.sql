-- Existing research_events table stores v2_run, paper_trade and nav_snapshot.
-- Keep RLS enabled and grant access only to the server-side service_role.
create table if not exists public.research_events (
 id text primary key, created_at timestamptz not null default now(),
 ticker text not null, event_type text not null, payload jsonb not null
);
create index if not exists research_events_type_time_idx
 on public.research_events(event_type, created_at desc);
alter table public.research_events enable row level security;
grant usage on schema public to service_role;
grant select, insert, update, delete on public.research_events to service_role;
-- Existing paper_snapshots table is preserved unchanged.
