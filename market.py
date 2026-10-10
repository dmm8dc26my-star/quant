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

def _number(value):
    """Convert provider values to finite floats without inventing missing values."""
    try:
        x = float(value)
        return x if np.isfinite(x) else np.nan
    except (TypeError, ValueError, OverflowError):
        return np.nan


def _row(statement, *names):
    """Read latest nonmissing value from a Yahoo financial statement."""
    if statement is None or statement.empty:
        return np.nan
    for name in names:
        if name in statement.index:
            values = pd.to_numeric(statement.loc[name], errors='coerce').dropna()
            if len(values):
                # Yahoo columns normally sorted newest first; sort dates explicitly.
                try:
                    values = values.sort_index(ascending=False)
                except Exception:
                    pass
                return _number(values.iloc[0])
    return np.nan


def _first(*values):
    for value in values:
        x = _number(value)
        if np.isfinite(x):
            return x
    return np.nan


def _ratio(numerator, denominator, positive=True):
    n, d = _number(numerator), _number(denominator)
    if not np.isfinite(n) or not np.isfinite(d) or (d <= 0 if positive else d == 0):
        return np.nan
    return n / d


def info_snapshot(ticker):
    """Current Yahoo fundamentals + annual statements; NOT point-in-time history.

    Ratios use reported financial statement fields where available. The ROIC
    calculation is an approximation based on EBIT, tax rate, debt and equity.
    """
    t = yf.Ticker(ticker)
    info = t.info or {}
    h = t.history(period='2y', auto_adjust=True)
    if h is None or h.empty:
        return None
    close = h['Close'].dropna()
    if len(close) < 260:
        return None
    close.index = pd.to_datetime(close.index)
    # Statement retrieval is best-effort; a missing statement is not a zero.
    def statement(attr):
        try:
            return getattr(t, attr)
        except Exception:
            return pd.DataFrame()
    inc, bal, cash = statement('income_stmt'), statement('balance_sheet'), statement('cashflow')

    cap = _first(info.get('marketCap'))
    ev = _first(info.get('enterpriseValue'))
    assets = _first(_row(bal, 'Total Assets'), info.get('totalAssets'))
    debt = _first(_row(bal, 'Total Debt'), info.get('totalDebt'))
    equity = _row(bal, 'Stockholders Equity', 'Total Equity Gross Minority Interest', 'Common Stock Equity')
    cash_balance = _row(bal, 'Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments')
    if not np.isfinite(ev) and np.isfinite(cap) and np.isfinite(debt) and np.isfinite(cash_balance):
        ev = cap + debt - cash_balance  # Simplified EV; excludes preferred/minority interests.
    ebit = _first(_row(inc, 'EBIT', 'Operating Income'), info.get('ebit'))
    ebitda = _first(_row(inc, 'EBITDA', 'Normalized EBITDA'), info.get('ebitda'))
    fcf = _first(_row(cash, 'Free Cash Flow'), info.get('freeCashflow'))
    if not np.isfinite(fcf):
        ocf = _row(cash, 'Operating Cash Flow', 'Cash Flow From Continuing Operating Activities')
        capex = _row(cash, 'Capital Expenditure')
        if np.isfinite(ocf) and np.isfinite(capex):
            fcf = ocf + capex if capex < 0 else ocf - capex
    earnings = _first(_row(inc, 'Net Income', 'Net Income Common Stockholders'), info.get('netIncomeToCommon'))

    tax = _row(inc, 'Tax Rate For Calcs')
    if not np.isfinite(tax):
        tax_expense = _row(inc, 'Tax Provision')
        pretax = _row(inc, 'Pretax Income')
        tax = _ratio(tax_expense, pretax)
    if not np.isfinite(tax) or not 0 <= tax <= 0.6:
        tax = np.nan
    invested_capital = _row(bal, 'Invested Capital')
    if not np.isfinite(invested_capital) and np.isfinite(debt) and np.isfinite(equity):
        invested_capital = debt + equity  # Simplified invested capital.
    roic = _ratio(ebit * (1-tax), invested_capital) if np.isfinite(ebit) and np.isfinite(tax) else np.nan
    if not np.isfinite(roic):
        roic = _first(info.get('returnOnInvestedCapital'))

    earnings_stability = np.nan
    for name in ('Net Income', 'Net Income Common Stockholders'):
        if not inc.empty and name in inc.index:
            vals = pd.to_numeric(inc.loc[name], errors='coerce').dropna()
            if len(vals) >= 3 and abs(vals.mean()) > 0:
                earnings_stability = float(vals.std(ddof=0) / abs(vals.mean()))
            break

    result = {'ticker': ticker, 'company': info.get('shortName') or ticker,
        'sector': info.get('sector') or 'Unknown', 'market_cap': cap,
        'price': float(close.iloc[-1]), 'asof': str(close.index[-1].date()),
        'roic': roic, 'fcf_assets': _ratio(fcf, assets),
        'debt_ebitda': _ratio(debt, ebitda), 'fcf_ev': _ratio(fcf, ev),
        'ebit_ev': _ratio(ebit, ev), 'earnings_yield': _ratio(earnings, cap),
        'momentum_12_1': float(close.iloc[-22] / close.iloc[-253] - 1),
        'momentum_6m': float(close.iloc[-1] / close.iloc[-127] - 1),
        'earnings_stability': earnings_stability,
        'bucket': 'speculative' if np.isfinite(cap) and cap < 3e9 else 'core',
        'data_source': 'Yahoo Finance latest statements/metadata (not point-in-time; unaudited)'}
    from core import WEIGHTS
    result['metrics_available'] = sum(np.isfinite(_number(result[k])) for k in WEIGHTS)
    result['missing_metrics'] = ', '.join(k for k in WEIGHTS if not np.isfinite(_number(result[k])))
    return result

def screen_live(tickers):
    rows=[]; errors=[]
    for ticker in tickers:
        try:
            r=info_snapshot(ticker)
            if r: rows.append(r)
            else: errors.append(f'{ticker}: insufficient price history')
        except Exception as exc: errors.append(f'{ticker}: {str(exc)[:100]}')
    return pd.DataFrame(rows),errors
