"""Deterministic, auditable multi-agent paper portfolio. No broker integrations."""
import math, uuid
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from market import UNIVERSE, price_history, info_snapshot
from store import save_record, records

CAPITAL=100000.0
MAX_POSITION=.12
SPEC_MAX=.20
CASH_RESERVE=.08
MAX_NAMES=16
FEE_BPS=10  # conservative proxy for friction; includes slippage/fees

def now(): return datetime.now(timezone.utc).isoformat()
def finite(x):
    try:
        y=float(x);return y if math.isfinite(y) else None
    except (TypeError,ValueError): return None

def price_features(series):
    s=pd.Series(series,dtype=float).dropna()
    if len(s)<253 or s.iloc[-1]<=0: return None
    r=s.pct_change().dropna()
    v=finite(r.tail(63).std()*np.sqrt(252))
    if v is None or v<=0:return None
    return {'price':float(s.iloc[-1]),'momentum_12_1':float(s.iloc[-22]/s.iloc[-253]-1),
            'momentum_6m':float(s.iloc[-1]/s.iloc[-127]-1),
            'volatility':v,'drawdown':float(s.iloc[-1]/s.tail(253).max()-1),
            'asof':str(s.index[-1].date()) if hasattr(s.index[-1],'date') else str(s.index[-1])}

def analyze(ticker, history, fundamentals=None):
    """Six distinct evidence-based roles. No pretend LLM calls or forecasts."""
    p=price_features(history)
    if not p:return None
    f=fundamentals or {}
    roic=finite(f.get('roic')); leverage=finite(f.get('debt_ebitda'))
    cash=finite(f.get('fcf_assets')); ey=finite(f.get('earnings_yield'))
    quality=np.mean([min(1,max(0,(x+0.1)/0.4)) for x in [roic,cash] if x is not None]) if any(x is not None for x in [roic,cash]) else None
    value=min(1,max(0,(ey+0.05)/0.20)) if ey is not None else None
    momentum=np.clip(.6*p['momentum_12_1']+.4*p['momentum_6m'],-.7,1.5)
    trend=float(np.clip(.5+momentum,0,1))
    risk=float(np.clip(1-p['volatility']/1.2,0,1))
    downside=float(np.clip(1+2*p['drawdown'],0,1))
    financial=float(np.clip(1-leverage/8,0,1)) if leverage is not None and leverage>=0 else None
    # Missing fundamentals lower confidence; never impute as zero financial metrics.
    available=sum(x is not None for x in [roic,cash,ey,leverage])
    confidence=.45+.55*available/4
    agents={
      'trend':{'score':trend,'evidence':'12-1 and six-month price momentum'},
      'fundamental':{'score':quality,'evidence':'ROIC and FCF/assets where reported'},
      'valuation':{'score':value,'evidence':'earnings yield where reported'},
      'risk':{'score':risk,'evidence':'63-day annualized realized volatility'},
      'skeptic':{'score':downside,'evidence':'one-year peak-to-current drawdown'},
      'balance_sheet':{'score':financial,'evidence':'debt/EBITDA when reported'}}
    available_scores=[(k,v['score']) for k,v in agents.items() if v['score'] is not None]
    score=sum({'trend':.38,'fundamental':.20,'valuation':.10,'risk':.14,'skeptic':.10,'balance_sheet':.08}[k]*v for k,v in available_scores)
    denominator=sum({'trend':.38,'fundamental':.20,'valuation':.10,'risk':.14,'skeptic':.10,'balance_sheet':.08}[k] for k,_ in available_scores)
    score=score/denominator*confidence
    return {'ticker':ticker,'score':round(float(score),5),'confidence':round(confidence,3),
            'price':p['price'],'asof':p['asof'],'volatility':p['volatility'],
            'drawdown':p['drawdown'],'momentum_12_1':p['momentum_12_1'],
            'momentum_6m':p['momentum_6m'],'agents':agents,
            'fundamental_fields':available,'speculative':bool(p['volatility']>.65)}

def select_targets(candidates):
    """Aggressive but unlevered, diversified, with capped speculative sleeve."""
    unique={r['ticker']:r for r in candidates if r and r['score']>0 and r['price']>0}
    ranked=sorted(unique.values(),key=lambda r:r['score'],reverse=True)
    chosen=[];spec_count=0
    for r in ranked:
        if len(chosen)>=MAX_NAMES:break
        if r['speculative'] and spec_count>=3:continue
        chosen.append(r)
        if r['speculative']:spec_count+=1
    if len(chosen)<5: return []  # fail closed on thin universes
    raw=np.array([max(.01,r['score'])/max(.20,r['volatility']) for r in chosen])
    weights=raw/raw.sum()*(1-CASH_RESERVE)
    # Iteratively cap concentration and speculative exposure, leaving excess as cash.
    weights=np.minimum(weights,MAX_POSITION)
    spec_idx=[i for i,r in enumerate(chosen) if r['speculative']]
    if spec_idx and sum(weights[spec_idx])>SPEC_MAX:
        weights[spec_idx]*=SPEC_MAX/sum(weights[spec_idx])
    return [{**r,'target_weight':round(float(w),6)} for r,w in zip(chosen,weights) if w>0]

def ledger(events,initial=CAPITAL):
    """Reconstruct from durable append-only paper trades; no mutable holdings state."""
    cash=float(initial); positions={}; seen=set()
    for e in sorted((x for x in events if x['event_type']=='paper_trade'),key=lambda x:(x['created_at'],x['id'])):
        if e['id'] in seen:continue
        seen.add(e['id']);p=e['payload'];t=e['ticker'];q=float(p['shares']);price=float(p['execution_price']);fee=float(p.get('fee',0))
        if q<=0 or price<=0 or fee<0:raise ValueError('Invalid historical trade')
        if p['side']=='BUY':
            if q*price+fee>cash+.02:raise ValueError('Historical paper trade overspends cash')
            cash-=q*price+fee;positions[t]=positions.get(t,0)+q
        elif p['side']=='SELL':
            if q>positions.get(t,0)+1e-6:raise ValueError('Historical paper trade oversells')
            cash+=q*price-fee;positions[t]=positions.get(t,0)-q
        else:raise ValueError('Unknown side')
    return cash,{t:q for t,q in positions.items() if q>1e-7}

def make_orders(targets,cash,holdings,prices,initial_nav=None):
    """Plan sales before buys, no shorting; whole-share orders; reserve liquidity."""
    if not targets:return []
    if any(finite(prices.get(t)) is None or prices[t]<=0 for t in holdings):return []
    nav=cash+sum(q*prices[t] for t,q in holdings.items())
    if nav<=0:return []
    desired={r['ticker']:math.floor(nav*r['target_weight']/r['price']) for r in targets}
    orders=[]
    for t,q in holdings.items():
        delta=desired.get(t,0)-q
        if delta<-.5:orders.append({'ticker':t,'side':'SELL','shares':float(min(q,math.floor(-delta))),'price':prices[t]})
    available=cash+sum(o['shares']*o['price']*(1-FEE_BPS/10000) for o in orders)
    for r in targets:
        t=r['ticker'];price=r['price'];need=max(0,desired[t]-holdings.get(t,0))
        if need<1:continue
        qty=min(math.floor(need),math.floor(max(0,available-nav*CASH_RESERVE)/(price*(1+FEE_BPS/10000))))
        if qty>=1:
            orders.append({'ticker':t,'side':'BUY','shares':float(qty),'price':price})
            available-=qty*price*(1+FEE_BPS/10000)
    return orders

def write_event(client,ticker,typ,payload,event_id=None):
    save_record(client,'research_events',{'id':event_id or str(uuid.uuid4()),'created_at':now(),
        'ticker':ticker,'event_type':typ,'payload':payload})

def execute_paper_orders(client,orders,run_id):
    """Idempotent IDs permit safe retries; all trades are fictional."""
    for i,o in enumerate(orders):
        fee=round(o['shares']*o['price']*FEE_BPS/10000,4)
        write_event(client,o['ticker'],'paper_trade',{'side':o['side'],'shares':o['shares'],
            'execution_price':o['price'],'fee':fee,'note':'AUTOMATED PAPER ONLY; indicative closing price; not executable',
            'run_id':run_id},event_id=str(uuid.uuid5(uuid.NAMESPACE_URL,run_id+':'+str(i))))

def latest_prices(tickers):
    prices={};failures=[]
    for t in tickers:
        try:
            s=price_history(t,'1mo')
            if len(s):prices[t]=float(s.iloc[-1])
            else:failures.append(t)
        except Exception:failures.append(t)
    return prices,failures

def run_cycle(client,universe=None,trade=False,limit=80,fetch_fundamentals=False):
    """Daily batch; default dry-run. Must explicitly enable automated fictional trades."""
    names=list(dict.fromkeys(universe or UNIVERSE))[:limit]
    if len(names)<5:raise ValueError('At least five stocks required')
    candidates=[];errors=[]
    for t in names:
        try:
            s=price_history(t,'2y')
            f=info_snapshot(t) if fetch_fundamentals else None
            r=analyze(t,s,f)
            if r:candidates.append(r)
            else:errors.append(t+': insufficient history')
        except Exception as exc:errors.append(t+': '+type(exc).__name__)
    targets=select_targets(candidates)
    events=records(client,'research_events',10000)
    cash,holdings=ledger(events)
    prices,missing=latest_prices(list(set(holdings)|{r['ticker'] for r in targets}))
    # Fail closed if any existing position cannot be marked to market.
    orders=[]
    if not missing and targets:
        for r in targets:r['price']=prices.get(r['ticker'],r['price'])
        orders=make_orders(targets,cash,holdings,prices)
    today=datetime.now(timezone.utc).strftime('%Y-%m-%d')
    run_id='v2:'+today  # one paper execution per UTC day, retries idempotent
    summary={'date':today,'scanned':len(names),'qualified':len(candidates),'targets':targets,
        'orders':orders,'errors':errors[:30],'missing_prices':missing,'mode':'paper' if trade else 'dry-run'}
    if trade:
        if not targets or missing:raise RuntimeError('Safety stop: insufficient candidates or missing prices')
        # Check if already completed today; avoid a second daily rebalance.
        if any(e['event_type']=='v2_run' and e['payload'].get('run_id')==run_id for e in events):
            summary['status']='already completed';return summary
        execute_paper_orders(client,orders,run_id)
        write_event(client,'PORTFOLIO','v2_run',{'run_id':run_id,'qualified':len(candidates),
            'targets':[{'ticker':r['ticker'],'weight':r['target_weight']} for r in targets]},
            event_id=str(uuid.uuid5(uuid.NAMESPACE_URL,run_id+':complete')))
        summary['status']='executed paper orders'
    else:summary['status']='preview only'
    # Refresh ledger and mark NAV, but never invent a price.
    events=records(client,'research_events',10000)
    cash,holdings=ledger(events)
    prices2,missing2=latest_prices(list(holdings))
    if not missing2:
        nav=cash+sum(q*prices2[t] for t,q in holdings.items())
        summary['nav']=round(nav,2);summary['cash']=round(cash,2)
        if trade:write_event(client,'PORTFOLIO','nav_snapshot',{'nav':nav,'cash':cash,'initial':CAPITAL,'run_id':run_id},event_id=str(uuid.uuid5(uuid.NAMESPACE_URL,run_id+':nav')))
    return summary
