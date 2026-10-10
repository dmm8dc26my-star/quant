import pandas as pd
from core import rank_stocks, performance, build_orders, WEIGHTS

def test_weights(): assert abs(sum(WEIGHTS.values())-1)<1e-9

def test_missing_not_fabricated():
    d={k:[1.,None] for k in WEIGHTS}
    d['ticker']=['A','B'];d['bucket']=['core','core']
    r=rank_stocks(pd.DataFrame(d))
    assert len(r)==1 and r.iloc[0].ticker=='A'

def test_performance():
    s=pd.Series([100.,110.],index=pd.to_datetime(['2024-01-01','2025-01-01']))
    assert abs(performance(s)['total_return']-.1)<1e-9

def test_no_partial_auto_orders():
    assert build_orders(pd.DataFrame())==[]
