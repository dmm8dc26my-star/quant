"""Optional, source-labelled intelligence. All network calls are best-effort; never fabricate data."""
import io, re, time, math, os, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote
import requests
import numpy as np
import pandas as pd
from market import UNIVERSE

HEADERS={'User-Agent':os.getenv('SEC_USER_AGENT','QuantResearchLab research contact research@example.org'),'Accept-Encoding':'gzip, deflate'}

def discover_universe(max_symbols=1500, include_international=True):
    """Current Wikipedia index constituents (not historical or global-complete); fallback to curated list."""
    sources=[('SP500','https://en.wikipedia.org/wiki/List_of_S%26P_500_companies',0),
             ('SP400','https://en.wikipedia.org/wiki/List_of_S%26P_400_companies',0),
             ('SP600','https://en.wikipedia.org/wiki/List_of_S%26P_600_companies',0)]
    symbols=list(UNIVERSE); origin={t:'curated' for t in symbols}; errors=[]
    for name,url,index in sources:
        try:
            r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (compatible; ResearchEducation/1.0)'},timeout=15);r.raise_for_status()
            tables=pd.read_html(io.StringIO(r.text)); found=[]
            for table in tables:
                cols=[str(c).lower() for c in table.columns]
                col=next((table.columns[i] for i,c in enumerate(cols) if c in ('symbol','ticker symbol','ticker')),None)
                if col is not None:
                    found=[str(x).strip().upper().replace('.','-') for x in table[col].dropna()];break
            if not found:raise ValueError('No ticker column found')
            for t in found:
                if re.fullmatch(r'[A-Z0-9-]{1,12}',t) and t not in origin:
                    symbols.append(t);origin[t]=name
        except Exception as exc:errors.append(name+': '+type(exc).__name__)
    return {'symbols':symbols[:max_symbols],'source_counts':{k:sum(v==k for v in origin.values()) for k in set(origin.values())},
            'errors':errors,'asof':datetime.now(timezone.utc).isoformat(),
            'warning':'Current index constituents only; not historical, survivorship-free or a complete global universe.'}

def _get_json(url,timeout=15):
    r=requests.get(url,headers=HEADERS,timeout=timeout);r.raise_for_status();return r.json()

def sec_insider_filings(ticker,limit=12):
    """SEC Form 4 filing metadata, not a verified buy/sell trade feed."""
    tickers=_get_json('https://www.sec.gov/files/company_tickers.json')
    item=next((v for v in tickers.values() if v.get('ticker','').upper()==ticker.upper()),None)
    if not item:return {'ticker':ticker,'filings':[],'warning':'Ticker not found in SEC mapping'}
    cik=str(item['cik_str']).zfill(10)
    sub=_get_json(f'https://data.sec.gov/submissions/CIK{cik}.json')
    recent=sub.get('filings',{}).get('recent',{})
    forms=recent.get('form',[]);accessions=recent.get('accessionNumber',[]);dates=recent.get('filingDate',[])
    filings=[{'form':f,'filed':dates[i],'accession':accessions[i],
              'url':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accessions[i].replace("-","")}/'}
             for i,f in enumerate(forms) if f in ('4','4/A') and i<len(dates) and i<len(accessions)]
    return {'ticker':ticker,'cik':cik,'filings':filings[:limit],
            'warning':'Form 4 filing metadata only. No claim about direction, amounts or profitability without parsing the filing.'}

def manager_13f_filings(cik,limit=8):
    """Fetch public 13F-HR filing metadata for a supplied institutional manager CIK."""
    cik=str(cik).strip().zfill(10)
    if not cik.isdigit() or len(cik)!=10:raise ValueError('CIK must contain digits')
    sub=_get_json(f'https://data.sec.gov/submissions/CIK{cik}.json')
    recent=sub.get('filings',{}).get('recent',{})
    out=[]
    for i,f in enumerate(recent.get('form',[])):
        if f not in ('13F-HR','13F-HR/A'):continue
        a=recent['accessionNumber'][i]
        out.append({'form':f,'filed':recent['filingDate'][i], 'report_date':recent.get('reportDate',['']*len(recent['form']))[i],
                    'url':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{a.replace("-","")}/'})
        if len(out)>=limit:break
    return {'manager':sub.get('name','Unknown'),'cik':cik,'filings':out,
            'warning':'13F reports are delayed snapshots of reportable long holdings; this is filing metadata, not parsed positions or real-time trades.'}

POS={'beat','growth','profit','surge','approval','contract','record','upgrade','breakthrough'}
NEG={'miss','loss','lawsuit','fraud','downgrade','recall','investigation','cut','bankruptcy'}

def news_headlines(ticker,limit=12):
    """Google News RSS headline sample with simple lexicon scoring; not full-article sentiment."""
    url='https://news.google.com/rss/search?q='+quote(ticker+' stock when:7d')+'&hl=en-US&gl=US&ceid=US:en'
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=15);r.raise_for_status()
    root=ET.fromstring(r.content);items=[]
    for item in root.findall('.//channel/item')[:limit]:
        title=(item.findtext('title') or '').strip();words=set(re.findall(r'[a-z]+',title.lower()))
        score=(len(words&POS)-len(words&NEG))/max(1,len(words&POS)+len(words&NEG))
        items.append({'title':title,'date':item.findtext('pubDate'),'url':item.findtext('link'),
                      'lexicon_score':score})
    return {'ticker':ticker,'headlines':items,'mean_headline_lexicon_score':round(float(np.mean([x['lexicon_score'] for x in items])),3) if items else None,
            'warning':'Headline-only keyword heuristic; may be irrelevant, duplicated, stale, or misclassified. Not a trained sentiment model.'}

def _features(prices,idx):
    s=prices
    if idx<252 or idx>=len(s):return None
    window=s.iloc[:idx+1];rets=window.pct_change().dropna()
    if len(rets)<252:return None
    vol=rets.iloc[-63:].std()*np.sqrt(252)
    if not np.isfinite(vol) or vol<=0:return None
    return [float(np.clip(window.iloc[-1]/window.iloc[-22]-1,-1,2)),
            float(np.clip(window.iloc[-22]/window.iloc[-253]-1,-1,3)),
            float(np.clip(vol,0,4)),
            float(np.clip(window.iloc[-1]/window.iloc[-253:].max()-1,-1,0))]

def train_price_model(price_histories, horizon=21, min_training=150):
    """Pooled ridge model; chronological 70/30 holdout with horizon embargo.

    Price-only 1-month forward return baseline. No fundamental look-ahead, no claimed alpha.
    Price histories are adjusted daily closes, supplied as ticker -> Series.
    """
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import Ridge
    X=[];y=[];dates=[]
    for ticker,series in price_histories.items():
        s=pd.Series(series,dtype=float).dropna().sort_index()
        for idx in range(252,len(s)-horizon,21):
            feat=_features(s,idx)
            if feat is None:continue
            future=s.iloc[idx+horizon]/s.iloc[idx]-1
            if not np.isfinite(future):continue
            X.append(feat);y.append(float(np.clip(future,-.9,3)));dates.append(pd.Timestamp(s.index[idx]))
    if len(X)<min_training:return {'status':'insufficient_samples','samples':len(X),'minimum':min_training}
    dates=np.array(dates);X=np.asarray(X);y=np.asarray(y)
    unique=sorted(set(dates));cut=unique[int(len(unique)*.7)]
    train=dates < cut-pd.Timedelta(days=horizon*2)
    test=dates>=cut
    if train.sum()<max(60,min_training//2) or test.sum()<20:return {'status':'insufficient_chronological_split','samples':len(X)}
    model=make_pipeline(StandardScaler(),Ridge(alpha=50.0));model.fit(X[train],y[train])
    pred=model.predict(X[test]);baseline=float(np.mean(y[train]));mae=float(np.mean(np.abs(pred-y[test])));base_mae=float(np.mean(np.abs(baseline-y[test])))
    latest={}
    for ticker,series in price_histories.items():
        s=pd.Series(series,dtype=float).dropna().sort_index();f=_features(s,len(s)-1)
        if f is not None:latest[ticker]=float(model.predict(np.asarray(f).reshape(1,-1))[0])
    return {'status':'trained','samples':int(train.sum()),'holdout_samples':int(test.sum()),
            'holdout_mae':round(mae,5),'constant_baseline_mae':round(base_mae,5),
            'outperformed_constant_baseline':bool(mae<base_mae),'predicted_21d_returns':latest,
            'warning':'Exploratory price-only ML. Index constituents may have survivorship bias; not a point-in-time validated backtest. Never interpret predictions as guaranteed returns.'}
