-- Run once in Supabase SQL Editor. Preserves research_events and paper_snapshots.
create table if not exists public.stock_universe (
 ticker text primary key, name text not null default '', source text not null default '',
 last_scanned_at timestamptz
);
create index if not exists stock_universe_scan_idx on public.stock_universe(last_scanned_at asc nulls first);
create table if not exists public.stock_scores (
 ticker text primary key references public.stock_universe(ticker) on delete cascade,
 score double precision not null, analyzed_at timestamptz not null, data jsonb not null
);
create index if not exists stock_scores_recent_idx on public.stock_scores(analyzed_at desc);
alter table public.stock_universe enable row level security;
alter table public.stock_scores enable row level security;
grant usage on schema public to service_role;
grant select,insert,update,delete on public.stock_universe,public.stock_scores to service_role;
