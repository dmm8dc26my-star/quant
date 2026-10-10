"""Real Yahoo Finance price/fundamental retrieval. Incomplete data is not fabricated."""
import time
import numpy as np
import pandas as pd
import yfinance as yf

# Editable research universe, not exhaustive or survivorship-free.
UNIVERSE=['AAPL','MSFT','GOOGL','AMZN','META','NVDA','AVGO','AMD','INTC','QCOM','TXN','ADBE','CRM','NOW','PANW','CRWD','DDOG','NET','SNOW','MDB','SHOP','PLTR','UBER','ABNB','PYPL','SQ','SOFI','HOOD','RBLX','DUOL','HIMS','RKLB','ASTS','IONQ','SOUN','JOBY','ACHR','LUNR','RDW','OKLO','SMR','NNE','BE','ENPH','FSLR','SEDG','RUN','ALB','LAC','MP','CCJ','UUUU','LEU','VRT','ETN','PWR','GEV','CEG','VST','NEE','TSLA','RIVN','LCID','NIO','F','GM','CAT','DE','URI','AXON','CW','KTOS','AVAV','LMT','RTX','NOC','BA','HII','ISRG','TMDX','RXRX','TEM','EXAS','ILMN','VRTX','REGN','MRNA','BNTX','NVO','LLY','UNH','HCA','COST','WMT','TGT','HD','LOW','MCD','SBUX','CMG','NKE','LULU','ONON','CELH','CAVA','KO','PEP','PG','CL','V','MA','JPM','BAC','GS','MS','BRK-B','BX','BLK','SPGI','ICE','CME','O','PLD','AMT','EQIX','DLR','DIS','NFLX','SPOT','TTD','ROKU','PINS','RDDT','COIN','MSTR']

def price_history(ticker,period='5y'):
    data=yf.Ticker(ticker).history(period=period,auto_adjust=True)
    if data is None or data.empty: return pd.Series(dtype=float)
    s=data['Close'].dropna().copy(); s.index=pd.to_datetime(s.index).tz_localize(None) if s.index.tz is not None else pd.to_datetime(s.index)
    return s

def info_snapshot(ticker):
    t=yf.Ticker(ticker)
    info=t.info or {}
    h=t.history(period='2y',auto_adjust=True)
    if len(h)<260: return None
    close=h['Close'].dropna()
    if len(close)<260: return None
    cap=info.get('marketCap'); ev=info.get('enterpriseValue'); debt=info.get('totalDebt')
    ebitda=info.get('ebitda'); ebit=info.get('ebit'); fcf=info.get('freeCashflow')
    assets=info.get('totalAssets'); earnings=info.get('netIncomeToCommon')
    # Yahoo metadata fields are sparse; missing data -> missing scores, not zero.
    def ratio(a,b):
        try: return float(a)/float(b) if a is not None and b is not None and float(b)>0 else np.nan
        except (TypeError,ValueError,ZeroDivisionError): return np.nan
    # ROIC proxy is NOT used when unsupported; earnings stability needs historic earnings.
    roic=info.get('returnOnInvestedCapital')
    if roic is None: roic=np.nan
    earnings_stability=np.nan
    try:
        inc=t.income_stmt
        if not inc.empty:
            row=next((x for x in ['Net Income','Net Income Common Stockholders'] if x in inc.index),None)
            if row:
                vals=pd.to_numeric(inc.loc[row],errors='coerce').dropna()
                if len(vals)>=3 and abs(vals.mean())>0: earnings_stability=float(vals.std()/abs(vals.mean()))
    except Exception: pass
    return {'ticker':ticker,'company':info.get('shortName',ticker),'sector':info.get('sector','Unknown'),
            'market_cap':cap,'price':float(close.iloc[-1]),'asof':str(close.index[-1].date()),
            'roic':roic,'fcf_assets':ratio(fcf,assets),'debt_ebitda':ratio(debt,ebitda),
            'fcf_ev':ratio(fcf,ev),'ebit_ev':ratio(ebit,ev),'earnings_yield':ratio(earnings,cap),
            'momentum_12_1':float(close.iloc[-22]/close.iloc[-253]-1),
            'momentum_6m':float(close.iloc[-1]/close.iloc[-127]-1),
            'earnings_stability':earnings_stability,
            'bucket':'speculative' if (cap is not None and cap<3e9) else 'core',
            'data_source':'Yahoo Finance (indicative; not point-in-time audited)'}

def screen_live(tickers):
    rows=[]; errors=[]
    for ticker in tickers:
        try:
            r=info_snapshot(ticker)
            if r: rows.append(r)
            else: errors.append(f'{ticker}: insufficient price history')
        except Exception as exc: errors.append(f'{ticker}: {str(exc)[:100]}')
    return pd.DataFrame(rows),errors
