import pandas as pd
import sys, types
if 'market' not in sys.modules:
    m=types.ModuleType('market');m.UNIVERSE=[];m.price_history=lambda *a,**k: None;m.info_snapshot=lambda *a,**k: None;sys.modules['market']=m
m2=types.ModuleType('store');m2.save_record=lambda *a,**k:None;m2.records=lambda *a,**k:[];sys.modules['store']=m2
from v2_engine import price_features, analyze, select_targets, ledger, make_orders

def hist():
    return pd.Series([100+i*.15 for i in range(300)],index=pd.bdate_range('2025-01-01',periods=300))

def test_features_and_six_roles():
    r=analyze('TEST',hist())
    assert r and len(r['agents'])==6 and r['fundamental_fields']==0
    assert 0<r['confidence']<1

def test_thin_universe_no_trades():
    assert select_targets([analyze('TEST',hist())])==[]

def test_ledger_and_cash_limit():
    e=[{'id':'1','created_at':'2026-01-01','ticker':'AAA','event_type':'paper_trade','payload':{'side':'BUY','shares':10,'execution_price':100,'fee':1}}]
    cash,holdings=ledger(e)
    assert cash==98999 and holdings=={'AAA':10}
    assert make_orders([],cash,holdings,{'AAA':100})==[]
