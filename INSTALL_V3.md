# Quant Research Lab V3 — browser-only upgrade

This is a **full replacement repository package** based on V2, not an add-on ZIP. It preserves your existing Streamlit app and Supabase tables.

1. Download and extract the ZIP. In your GitHub repository `https://github.com/dmm8dc26my-star/quant`, back up the current code (GitHub history also retains previous commits). Upload the extracted files and replace matching files. **Do not upload the ZIP itself.** In particular add `v3_intelligence.py`, replace `app.py` and `requirements.txt`, and preserve the `.github/workflows/paper_daily.yml` path. GitHub's browser editor can create nested paths with **Add file → Create new file**.
2. Commit to `main` and wait for Streamlit Cloud to redeploy. Your existing `APP_PASSWORD`, `SUPABASE_URL`, `SUPABASE_KEY` remain in Streamlit Secrets; do not put them in GitHub code. No new database tables are required for V3 intelligence diagnostics. If you did not run V2 SQL previously, run `schema_v2.sql` in Supabase SQL Editor.
3. Open `https://quant-research-labb.streamlit.app/`, enter your password, and select **Intelligence V3**. Test **Discover expanded US stock universe**, **Read recent news headlines**, **Find SEC Form 4 filings**, and **Train ML and inspect out-of-sample error** separately. API providers may reject or throttle requests.
4. For SEC access, set a truthful `SEC_USER_AGENT` environment variable identifying your application and a real contact email. You may add it to Streamlit Secrets and, if later scheduling SEC jobs, GitHub Actions secrets. The default placeholder is not suitable for production SEC access.
5. Keep `ENABLE_AUTOMATED_PAPER_TRADES=false` until the V2 paper portfolio has been checked. V3 diagnostics **do not** automatically alter portfolio trades.

## Precisely what is implemented
- Exploratory trained scikit-learn ridge regression for 21-trading-day **price-only** forward returns, with chronological holdout and embargo, and comparison to a constant baseline. No validated alpha or point-in-time fundamentals.
- SEC Form 4 **filing metadata** by ticker and institutional 13F **filing metadata** by manager CIK. It does not parse transaction quantities, identify celebrity investors automatically, or copy trades.
- Google News RSS **headlines** with a simple disclosed keyword-lexicon sentiment heuristic, not an LLM or full-article classifier.
- Best-effort current S&P 500/400/600 constituent discovery, merged with the existing curated watchlist; this is **US-focused**, not a comprehensive worldwide universe, and not historical membership.
- Existing six deterministic V2 roles and $100,000 aggressive **paper-only** portfolio remain intact.

## Known limitations
Data feeds may be rate-limited or unavailable. ML results are exploratory and vulnerable to survivorship bias and regime changes. News may be stale or misclassified. 13F filings are delayed and incomplete representations of portfolios. This upgrade does not claim a global all-stock feed, full 13F position parsing, real-time investor trades, automated ML retraining, or live broker integration. No real money is traded.
