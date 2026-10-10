"""GitHub Actions: refresh listing directory and scan a rotating batch. Never trades."""
import json,os
from store import db
from universe_v4 import refresh_universe,scan_batch,cached_targets

def main():
    client=db(os.environ['SUPABASE_URL'],os.environ['SUPABASE_KEY'])
    # Refresh listing directory only in the designated daily job.
    if os.getenv('REFRESH_UNIVERSE','false').lower()=='true':
        print('Discovery:',json.dumps(refresh_universe(client)))
    batch=max(1,min(250,int(os.getenv('V4_BATCH_SIZE','60'))))
    print('Scan:',json.dumps(scan_batch(client,batch)))
    summary=cached_targets(client)
    print('Coverage:',json.dumps({k:v for k,v in summary.items() if k!='targets'}))
    print('Leading candidates:',[(x['ticker'],x['score']) for x in summary['targets']])
if __name__=='__main__':main()
