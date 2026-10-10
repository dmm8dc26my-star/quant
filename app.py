import os, json, uuid, hmac
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
from core import rank_stocks, performance, build_orders, timestamp
from market import UNIVERSE, screen_live, price_history
from agents import run_team
from store import db, save_record, records

st.set_page_config(page_title='Quant Research Lab',page_icon='📊',layout='wide')
st.title('📊 Quant Research Lab')
st.caption('Real market observations • Research hypotheses • Fictional-money portfolio • No live brokerage orders')

def secret(k):
    try: return st.secrets.get(k,os.getenv(k,''))
    except Exception: return os.getenv(k,'')

pw=secret('APP_PASSWORD')
if not pw:
    st.error('Set APP_PASSWORD in Streamlit Cloud secrets before opening this private research dashboard.');st.stop()
entered=st.sidebar.text_input('Dashboard password',type='password')
if not hmac.compare_digest(entered,pw): st.info('Enter your dashboard password in the sidebar.');st.stop()

try: client=db(secret('SUPABASE_URL'),secret('SUPABASE_KEY'))
except Exception as exc:
    st.error('Persistent Supabase database required. '+str(exc));st.stop()

@st.cache_data(ttl=3600,show_spinner=False)
def cached_screen(tickers): return screen_live(list(tickers))
@st.cache_data(ttl=1800,show_spinner=False)
def cached_price(ticker,period='5y'): return price_history(ticker,period)

def event(ticker,typ,payload):
    save_record(client,'research_events',{'id':str(uuid.uuid4()),'created_at':timestamp(),'ticker':ticker,'event_type':typ,'payload':payload})

def load_events(): return records(client,'research_events',1000)

page=st.sidebar.radio('Navigation',['Overview','Live stock screener','Company research agents','Paper portfolio','Historical price backtest','Research journal','Settings & methodology'])
st.sidebar.warning('Educational paper-trading research. No verified alpha or 1000× predictions.')

if page=='Overview':
    ev=load_events()
    orders=[x for x in ev if x['event_type']=='proposal']
    research=[x for x in ev if x['event_type']=='ai_report']
    c1,c2,c3=st.columns(3)
    c1.metric('Saved proposals',len(orders));c2.metric('AI research reports',len(research));c3.metric('Research universe',len(UNIVERSE))
    st.subheader('Recent proposals')
    if orders: st.dataframe(pd.DataFrame([{'date':x['created_at'],'ticker':x['ticker'],**x['payload']} for x in orders]),use_container_width=True)
    else: st.info('No proposals saved yet. Start with Live stock screener.')
    st.subheader('Project status')
    st.write('Live prices: Yahoo Finance (best effort). Fundamental scores: only when complete. AI agents: real API calls when provided documents. Paper tracking: durable database, no broker. Historical benchmark: price-only, not validated factor alpha.')

elif page=='Live stock screener':
    st.subheader('Screen real companies')
    st.warning('This is a curated, current ticker list, not a historical or comprehensive universe. Yahoo fundamentals are often incomplete. Missing fields are NOT fabricated.')
    tickers=st.text_area('Tickers, separated by commas',value=','.join(UNIVERSE[:18]),height=110)
    if st.button('Fetch real financial snapshots',type='primary'):
        selected=tuple(dict.fromkeys(t.strip().upper() for t in tickers.split(',') if t.strip()))[:60]
        if not selected: st.warning('Enter at least one ticker.')
        else:
            with st.spinner('Downloading price and financial metadata; this can take a minute...'):
                df,errors=cached_screen(selected)
            st.session_state['screen']=df
            st.session_state['screen_errors']=errors
    if 'screen' in st.session_state:
        df=st.session_state['screen']
        if df.empty: st.warning('No usable company records returned.')
        else:
            ranked=rank_stocks(df)
            st.metric('Fetched company snapshots',len(df));st.metric('Complete nine-factor scores',len(ranked))
            st.dataframe(df,use_container_width=True)
            if not ranked.empty:
                st.subheader('Quant rankings (exploratory)')
                st.dataframe(ranked[['ticker','company','sector','bucket','price','score','asof']],use_container_width=True)
                chosen=st.selectbox('Save a research proposal',ranked['ticker'].tolist())
                if st.button('Save proposal to database'):
                    r=ranked.loc[ranked.ticker==chosen].iloc[0]
                    event(chosen,'proposal',{'score':round(float(r.score),2),'price_at_proposal':float(r.price),'asof':r.asof,'bucket':r.bucket,'note':'Unvalidated nine-factor rank; not a buy signal'})
                    st.success('Saved with timestamp. No fictional shares purchased.')
            else: st.info('No companies have all nine metrics. This is expected with free Yahoo data. Use the raw table for research; do not substitute made-up values.')
            st.download_button('Download snapshots CSV',df.to_csv(index=False),'company_snapshots.csv')
        if st.session_state.get('screen_errors'): st.expander('Fetch issues').write(st.session_state['screen_errors'])

elif page=='Company research agents':
    st.subheader('Four AI research roles')
    st.info('Paste authentic SEC filing excerpts, earnings transcripts or source text. Agents cite only the material supplied. API usage may incur charges.')
    ticker=st.text_input('Company ticker','MSFT').strip().upper()
    docs=st.text_area('Source documents (include URL, publication date and excerpt)',height=280,placeholder='Source: SEC 10-K, URL..., filing date...\nExcerpt...')
    key=secret('OPENAI_API_KEY')
    if st.button('Run all four agents',type='primary'):
        if not key: st.error('Set OPENAI_API_KEY in cloud secrets first.')
        else:
            try:
                with st.spinner('Running real AI research calls...'):
                    reports=run_team(ticker,docs,key)
                event(ticker,'ai_report',{'reports':reports,'source_excerpt':docs[:3000],'source_length':len(docs)})
                st.success('AI report saved persistently.')
                for name,report in reports.items():
                    with st.expander(name,expanded=True): st.markdown(report)
            except Exception as exc: st.error(f'Agent run failed: {exc}')

elif page=='Paper portfolio':
    st.subheader('Fictional-money ledger')
    st.info('Trades are entered manually and timestamped in Supabase. The portfolio does not execute trades automatically. Market prices update when this page is visited.')
    initial=st.number_input('Initial fictional cash (USD)',min_value=100.,value=10000.,step=1000.)
    ev=load_events(); trades=sorted([x for x in ev if x['event_type']=='paper_trade'],key=lambda x:x['created_at'])
    holdings={}; cash=initial
    for t in trades:
        p=t['payload']; qty=float(p['shares']); price=float(p['execution_price']); fee=float(p.get('fee',0))
        if p['side']=='BUY': cash-=qty*price+fee;holdings[t['ticker']]=holdings.get(t['ticker'],0)+qty
        else: cash+=qty*price-fee;holdings[t['ticker']]=holdings.get(t['ticker'],0)-qty
    holdings={k:v for k,v in holdings.items() if v>1e-9}
    if cash<0: st.error('Ledger has negative cash: check prior trades and initial capital.')
    st.write(f'Cash balance: **${cash:,.2f}**')
    with st.form('trade'):
        c1,c2,c3=st.columns(3)
        ticker=c1.text_input('Ticker','MSFT').strip().upper()
        side=c2.selectbox('Paper trade',['BUY','SELL'])
        shares=c3.number_input('Shares',min_value=.001,value=1.,step=1.,format='%.3f')
        price=st.number_input('Fictional execution price (USD)',min_value=.01,value=100.,step=1.)
        fee=st.number_input('Fee (USD)',min_value=0.,value=0.)
        note=st.text_input('Reason / thesis','')
        submit=st.form_submit_button('Record fictional trade')
    if submit:
        if side=='BUY' and shares*price+fee>cash: st.error('Insufficient fictional cash.')
        elif side=='SELL' and shares>holdings.get(ticker,0): st.error('Not enough fictional shares.')
        elif not ticker.isascii() or not ticker: st.error('Invalid ticker')
        else:
            event(ticker,'paper_trade',{'side':side,'shares':shares,'execution_price':price,'fee':fee,'note':note})
            st.success('Saved. Refresh page to recalculate holdings.')
    if holdings:
        rows=[]
        for ticker,qty in holdings.items():
            try:
                hist=cached_price(ticker,'1mo');last=float(hist.iloc[-1]) if len(hist) else np.nan
            except Exception: last=np.nan
            rows.append({'ticker':ticker,'shares':qty,'latest_price':last,'market_value':qty*last})
        frame=pd.DataFrame(rows)
        st.dataframe(frame,use_container_width=True)
        nav=cash+frame['market_value'].sum() if frame.latest_price.notna().all() else np.nan
        if np.isfinite(nav):
            st.metric('Current fictional portfolio value',f'${nav:,.2f}',delta=f'{(nav/initial-1)*100:+.2f}% vs initial cash')
            if st.button('Save today’s NAV snapshot'):
                event('PORTFOLIO','nav_snapshot',{'nav':float(nav),'cash':float(cash),'initial':float(initial)})
                st.success('NAV snapshot saved.')
        else: st.warning('At least one market price is unavailable; NAV cannot be calculated accurately.')
    snapshots=sorted([x for x in ev if x['event_type']=='nav_snapshot'],key=lambda x:x['created_at'])
    if snapshots:
        n=pd.Series({pd.Timestamp(x['created_at']):float(x['payload']['nav']) for x in snapshots}).sort_index()
        st.plotly_chart(px.line(n,title='Saved paper NAV observations'),use_container_width=True)
        st.json(performance(n))
    if trades: st.dataframe(pd.DataFrame([{'date':x['created_at'],'ticker':x['ticker'],**x['payload']} for x in trades]),use_container_width=True)

elif page=='Historical price backtest':
    st.subheader('Historical price-only momentum strategy vs S&P 500')
    st.warning('This is NOT a historical fundamental-factor backtest. It uses today’s selected tickers, so it has survivorship/selection bias. It cannot verify alpha.')
    raw=st.text_input('Historical symbols','MSFT,AAPL,AMZN,GOOGL,META,NVDA,AMD,ADBE,CRM,INTC')
    start=st.selectbox('Price history',['5y','10y'],index=0)
    if st.button('Run historical price-only illustration'):
        names=list(dict.fromkeys(x.strip().upper() for x in raw.split(',') if x.strip()))[:20]
        series={}
        with st.spinner('Fetching adjusted historical prices...'):
            for t in names+['SPY']:
                try:
                    s=cached_price(t,start)
                    if len(s)>260: series[t]=s
                except Exception: pass
        if 'SPY' not in series or len(series)<3: st.error('Not enough data returned.');st.stop()
        prices=pd.concat(series,axis=1).ffill().dropna()
        if len(prices)<260: st.error('Not enough overlapping history.');st.stop()
        daily=prices.pct_change().fillna(0)
        # Monthly rebalance; 12-1 momentum signal measured at prior month-end.
        weights=pd.DataFrame(0.,index=prices.index,columns=prices.columns)
        rebalance=prices.resample('ME').last().index
        rebalance=[prices.index[prices.index<=d][-1] for d in rebalance if any(prices.index<=d)]
        holdings=[]
        for d in rebalance:
            loc=prices.index.get_loc(d)
            if loc<253: continue
            signal=prices.iloc[loc-21]/prices.iloc[loc-252]-1
            picks=signal.drop(labels=['SPY'],errors='ignore').nlargest(3).index.tolist()
            if picks: holdings.append((d,picks))
        if not holdings: st.error('Insufficient history for momentum signal.');st.stop()
        for i,(d,picks) in enumerate(holdings):
            start_i=prices.index.get_loc(d)+1
            end_i=prices.index.get_loc(holdings[i+1][0])+1 if i+1<len(holdings) else len(prices)
            if start_i<end_i: weights.loc[prices.index[start_i:end_i],picks]=1/len(picks)
        strategy_ret=(daily*weights).sum(axis=1)
        # Cost proxy 10 bps per unit of turnover on rebalance days.
        turnover=weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
        strategy_ret=strategy_ret-.001*turnover
        valid=weights.sum(axis=1)>0
        strat=(1+strategy_ret.loc[valid]).cumprod()*10000
        bench=(1+daily.loc[valid,'SPY']).cumprod()*10000
        fig=pd.DataFrame({'Momentum illustration':strat,'SPY benchmark':bench})
        st.plotly_chart(px.line(fig,title='$10,000 hypothetical growth; 10 bps turnover cost proxy'),use_container_width=True)
        st.dataframe(pd.DataFrame({'Strategy':performance(strat),'SPY':performance(bench)}),use_container_width=True)
        st.caption('No taxes, financing costs or bid-ask slippage beyond stated proxy; data source may revise history. No historical AI/fundamental screening. For research only.')

elif page=='Research journal':
    ev=load_events()
    if not ev: st.info('No research saved yet.')
    else:
        types=sorted(set(x['event_type'] for x in ev))
        chosen=st.multiselect('Event types',types,default=types)
        for x in ev:
            if x['event_type'] not in chosen: continue
            with st.expander(f"{x['created_at'][:16]} · {x['ticker']} · {x['event_type']}"):
                st.json(x['payload'])
        st.download_button('Export research journal JSON',json.dumps(ev,indent=2,default=str),'research_journal.json')

else:
    st.markdown('''### Methodology and limitations
- **Source**: Yahoo Finance prices and indicative company metadata. Data can be delayed, incomplete, revised, or unavailable.
- **Screen**: Nine-factor rank requires all nine metrics. No imputation, and no claim of point-in-time fundamentals.
- **Satellite ideas**: Small, speculative companies can be researched separately. A 1,000× return in 12 months is extraordinarily unlikely; the app never asserts such predictions.
- **AI**: Four roles use a paid API and supplied documents. Their conclusions are hypotheses, not audited valuations.
- **Persistence**: Supabase stores proposals, research and fictional transactions. Cloud filesystem is not used for durable state.
- **Historical**: Momentum illustration uses today's tickers and cannot establish alpha. Full point-in-time historical fundamentals and delisted securities require a better licensed dataset.
- **Automation**: No unattended trading or guaranteed scheduled updates. Paper prices refresh on visit; manually save NAV snapshots.
- **Privacy**: Keep your GitHub repository private, your Streamlit app access restricted, and service keys in server-side secrets only.
''')
