"""Transparent research scoring and paper-portfolio math. Not investment advice."""
from datetime import datetime, timezone
import numpy as np
import pandas as pd

WEIGHTS = {'roic':.15,'fcf_assets':.10,'debt_ebitda':.10,'fcf_ev':.15,'ebit_ev':.10,'earnings_yield':.05,'momentum_12_1':.15,'momentum_6m':.10,'earnings_stability':.10}
LOWER = {'debt_ebitda','earnings_stability'}


def rank_stocks(frame):
    """Ranks only stocks with full metric coverage; never imputes unavailable financials."""
    df=frame.copy()
    for k in WEIGHTS:
        df[k]=pd.to_numeric(df[k],errors='coerce')
    df=df.replace([np.inf,-np.inf],np.nan).dropna(subset=list(WEIGHTS))
    if df.empty: return df.assign(score=pd.Series(dtype=float))
    df['score']=0.
    for k,w in WEIGHTS.items():
        pct=df[k].rank(pct=True,method='average')
        df['score']+=100*w*(1-pct if k in LOWER else pct)
    return df.sort_values('score',ascending=False).reset_index(drop=True)


def performance(nav):
    """NAV: date-indexed series; reports actual observed CAGR only when >= 2 dates."""
    s=pd.Series(nav,dtype=float).dropna().sort_index()
    if len(s)<2 or s.iloc[0]<=0: return {}
    days=(pd.Timestamp(s.index[-1])-pd.Timestamp(s.index[0])).days
    if days<=0: return {}
    r=s.pct_change().dropna()
    return {'total_return':s.iloc[-1]/s.iloc[0]-1,
            'cagr':(s.iloc[-1]/s.iloc[0])**(365.25/days)-1,
            'max_drawdown':(s/s.cummax()-1).min(),
            'volatility':r.std()*np.sqrt(252) if len(r)>1 else np.nan,
            'observed_days':days}


def build_orders(ranked,core_slots=18,spec_slots=2,capital=10000):
    """Proposal only. Satellite candidates selected by speculative proxy, NOT 1000x prediction."""
    if ranked.empty: return []
    core=ranked[ranked['bucket']=='core'].head(core_slots)
    sat=ranked[ranked['bucket']=='speculative'].head(spec_slots)
    if len(core)<core_slots or len(sat)<spec_slots: return []
    # 90% core, 10% satellite. No borrowing, no live orders.
    orders=[]
    for _,r in core.iterrows(): orders.append({'ticker':r.ticker,'bucket':'core','target_weight':.90/core_slots})
    for _,r in sat.iterrows(): orders.append({'ticker':r.ticker,'bucket':'speculative','target_weight':.10/spec_slots})
    return orders


def timestamp(): return datetime.now(timezone.utc).isoformat()
