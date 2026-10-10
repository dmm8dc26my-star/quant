"""Scheduled GitHub Actions job. Secrets are read from environment, never committed."""
import os, json
from store import db
from v2_engine import run_cycle

def main():
    url=os.environ['SUPABASE_URL'];key=os.environ['SUPABASE_KEY']
    client=db(url,key)
    trade=os.environ.get('ENABLE_AUTOMATED_PAPER_TRADES','false').lower()=='true'
    limit=int(os.environ.get('V2_UNIVERSE_LIMIT','80'))
    if not 5<=limit<=135:raise ValueError('Universe limit must be 5..135')
    result=run_cycle(client,trade=trade,limit=limit,
                     fetch_fundamentals=os.environ.get('V2_FETCH_FUNDAMENTALS','false').lower()=='true')
    print(json.dumps({k:v for k,v in result.items() if k not in ('targets','orders')},indent=2))
    print('Targets:',[(r['ticker'],r['target_weight']) for r in result['targets']])
    print('Paper orders:',result['orders'])

if __name__=='__main__':main()
