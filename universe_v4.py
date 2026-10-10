"""Durable, rotating US equity research universe. Educational paper-only."""
import io, re, time
from datetime import datetime, timezone, timedelta
import requests
import pandas as pd

CAPACITY=10000
FEEDS={
    'nasdaq':'https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt',
    'other':'https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt',
}

def parse_directory(text,kind):
    lines=[x for x in text.splitlines() if x.strip() and not x.startswith('File Creation Time')]
    if not lines:return []
    data=pd.read_csv(io.StringIO('\n'.join(lines)),sep='|',dtype=str,keep_default_na=False)
    symbol_col='Symbol' if kind=='nasdaq' else 'ACT Symbol'
    if symbol_col not in data:return []
    results=[]
    for _,r in data.iterrows():
        symbol=str(r[symbol_col]).strip().upper().replace('.','-')
        name=str(r.get('Security Name','')).strip()
        if not re.fullmatch(r'[A-Z][A-Z0-9-]{0,13}',symbol):continue
        if str(r.get('Test Issue','N')).upper()=='Y':continue
        if str(r.get('ETF','N')).upper()=='Y':continue
        if str(r.get('NextShares','N')).upper()=='Y':continue
        # Exclude obvious non-common-stock instruments; other share classes may still require validation.
        if re.search(r'\b(warrant|rights|unit|preferred|depositary|note|bond|etf|etn|fund|trust|debenture)\b',name,re.I):continue
        results.append((symbol,name))
    return results

def discover():
    from market import UNIVERSE
    result={t:(t,'curated') for t in UNIVERSE};errors=[]
    for kind,url in FEEDS.items():
        try:
            resp=requests.get(url,timeout=25,headers={'User-Agent':'QuantResearchLab/4.0 (educational research)'})
            resp.raise_for_status()
            found=parse_directory(resp.text,kind)
            if not found:raise ValueError('empty directory')
            for ticker,name in found:result[ticker]=(name,kind)
        except Exception as exc:errors.append(f'{kind}: {type(exc).__name__}: {exc}')
    return result,errors

def refresh_universe(client,capacity=CAPACITY):
    found,errors=discover()
    if len(found)<200:raise RuntimeError('Discovery produced too few symbols; existing universe preserved')
    # Never drop existing symbols when refreshing. Capacity limits newly stored symbols.
    existing=all_rows(client,'stock_universe','ticker,name,source,last_scanned_at',order='ticker')
    existing_ids={r['ticker'] for r in existing}
    free=max(0,capacity-len(existing_ids))
    # Deterministic ticker ordering, not market-cap ordering.
    additions=[{'ticker':t,'name':name[:250],'source':source} for t,(name,source) in sorted(found.items()) if t not in existing_ids][:free]
    for i in range(0,len(additions),250):client.table('stock_universe').upsert(additions[i:i+250],on_conflict='ticker').execute()
    return {'discovered':len(found),'previously_stored':len(existing_ids),'added':len(additions),'total':len(existing_ids)+len(additions),'errors':errors}

def all_rows(client,table,columns='*',order='ticker',max_rows=12000):
    out=[]
    for start in range(0,max_rows,500):
        chunk=client.table(table).select(columns).order(order).range(start,start+499).execute().data or []
        out.extend(chunk)
        if len(chunk)<500:break
    return out

def next_batch(client,size=80):
    rows=all_rows(client,'stock_universe','ticker,last_scanned_at',order='ticker')
    if not rows:return []
    # Oldest scan first, alphabetical tie-breaker. Unscanned stocks have priority.
    rows.sort(key=lambda r:(r.get('last_scanned_at') or '',r['ticker']))
    return [r['ticker'] for r in rows[:size]]

def scan_batch(client,size=80):
    from market import price_history
    from v2_engine import analyze
    tickers=next_batch(client,size)
    if not tickers:raise RuntimeError('Empty universe; run discovery first')
    success=0;errors=[]
    for ticker in tickers:
        stamp=datetime.now(timezone.utc).isoformat()
        try:
            hist=price_history(ticker,'2y')
            result=analyze(ticker,hist)
            if result:
                # Existing cached score is overwritten only after a successful analysis.
                client.table('stock_scores').upsert({'ticker':ticker,'score':result['score'],'analyzed_at':stamp,'data':result},on_conflict='ticker').execute()
                success+=1
            else:errors.append(ticker+': insufficient price history')
        except Exception as exc:errors.append(ticker+': '+type(exc).__name__)
        # Attempted symbols rotate even when provider returns no data.
        client.table('stock_universe').update({'last_scanned_at':stamp}).eq('ticker',ticker).execute()
    return {'attempted':len(tickers),'qualified':success,'errors':errors[:30]}

def cached_targets(client,max_age_days=21,min_coverage=200):
    from v2_engine import select_targets
    universe=all_rows(client,'stock_universe','ticker,last_scanned_at')
    scores=all_rows(client,'stock_scores','ticker,score,analyzed_at,data')
    cutoff=datetime.now(timezone.utc)-timedelta(days=max_age_days)
    fresh=[]
    for row in scores:
        try:
            ts=datetime.fromisoformat(row['analyzed_at'].replace('Z','+00:00'))
            if ts>=cutoff and isinstance(row.get('data'),dict):fresh.append(row['data'])
        except (TypeError,ValueError,KeyError):continue
    # A handful of large names cannot determine the whole portfolio while universe is warming up.
    ready=len(fresh)>=min_coverage
    return {'stored_universe':len(universe),'fresh_scores':len(fresh),'ready':ready,
            'targets':select_targets(fresh) if ready else [],'reason':None if ready else f'Need {min_coverage} recent valid stock scores before portfolio selection'}
