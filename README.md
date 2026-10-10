# Quant Research Lab — cloud edition

A deployable, **private** Streamlit research website using real Yahoo Finance snapshots, four OpenAI research roles, Supabase persistence, fictional trades and a price-only historical illustration.

## Deploy from your browser (no Windows Python)

1. Create a **private** GitHub repository. Upload the *contents* of this folder to its root (including `app.py`, `core.py`, `market.py`, `agents.py`, `store.py`, `requirements.txt`, `schema.sql`). Do not upload secrets.
2. Create a free [Supabase](https://supabase.com/) project. Open SQL Editor and run `schema.sql`. Find Project URL and service-role API key in your project settings. **Never put the service-role key in GitHub, public code, or browser JavaScript.**
3. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) with GitHub; deploy repository, branch `main`, entrypoint `app.py`, Python 3.12.
4. In **Advanced settings → Secrets** paste (replace placeholders):

```toml
APP_PASSWORD = "a-long-unique-random-password"
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-server-side-service-role-key"
OPENAI_API_KEY = "your-optional-openai-api-key"
```

5. Restrict Streamlit viewer access to your own account if supported; do not rely solely on the in-app password. The app must remain private because it uses a service-role key server-side.
6. Open your deployed `.streamlit.app` URL. Enter the app password in the sidebar. Start with Live stock screener, save proposals, optionally run AI agents with real source excerpts, and record fictional trades in Paper portfolio.

## Important limitations

- **Not deployed for you**: You must connect your own GitHub, Streamlit and Supabase accounts. The downloadable ZIP is the deployable source.
- **No automated buys**: Portfolio is a manual fictional ledger. Record fictional trades at a stated execution price. Saving a proposal does not buy shares.
- **No automatic daily snapshot**: On visits, live market prices refresh and you can save NAV snapshots. Automatic unattended updates would require a separately configured scheduler and protected backend.
- **Not a full historical fundamental backtest**: Yahoo snapshot fields are not historical point-in-time. The included historical backtest is **price-only**, biased by present-day ticker selection, and not proof of alpha.
- **Sparse fundamental data**: The strict nine-factor screener may score zero companies when Yahoo omits ROIC, assets, EBIT or earnings variability. That is a correct limitation, not a bug. Upgrade to licensed historical fundamentals before claiming a systematic strategy.
- **Speculative**: Small-cap satellite bucket is for research, not predictions of 1,000× gains. It is not automatically bought.
- **Cloud API costs**: Yahoo may throttle, OpenAI charges for requests, Supabase and Streamlit free tiers have quotas.
- **Privacy**: Supabase service-role keys bypass row-level security. Never expose them client-side. Use a private repository and restricted dashboard. For multi-user deployment implement Supabase Auth and per-user RLS instead.
- **Initial capital**: Set fictional initial capital once; do not change it after recording trades, or calculations become inconsistent.

## Files

- `app.py` Streamlit dashboard
- `core.py` factor ranking, metrics and proposed allocation helper
- `market.py` real Yahoo Finance price/fundamental access
- `agents.py` four real OpenAI research calls
- `store.py` Supabase database wrapper
- `schema.sql` persistent tables
- `tests/test_core.py` reproducible unit tests

## Local optional test

```bash
pip install -r requirements.txt
pytest -q
streamlit run app.py
```

## What is required for actual historical factor validation

Obtain a survivorship-free point-in-time fundamentals dataset with filing publication timestamps, delistings, corporate actions, prices and costs. Define universe and factors ex ante, test out of sample, compare against factor-matched benchmarks, and record prospective results. The included price-only chart cannot substitute for this.
