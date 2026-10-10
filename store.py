"""Durable Supabase storage; fail closed if not configured."""
from supabase import create_client

def db(url,key):
    if not url or not key: raise RuntimeError('Configure SUPABASE_URL and SUPABASE_KEY to persist research')
    return create_client(url,key)

def save_record(client,table,record):
    return client.table(table).upsert(record,on_conflict='id').execute()

def records(client,table,limit=500):
    return client.table(table).select('*').order('created_at',desc=True).limit(limit).execute().data or []
