# Quant Research Lab V2 — browser-only installation

This is a **replacement repository package**. It preserves your existing Supabase tables and research events. No brokerage orders are possible.

## 1. GitHub (browser only)

Open https://github.com/dmm8dc26my-star/quant . Upload/replace the root files from this ZIP using **Add file → Upload files → Commit changes**. To upload a folder such as `.github/workflows`, drag the entire `.github` folder into GitHub's upload page (if hidden, use the browser's file picker or create the file directly at `.github/workflows/paper_daily.yml`). Do not upload ZIP itself as a single file. **Back up your existing files first** (GitHub history can restore them).

If GitHub will not replace existing files by drag-and-drop, open the existing file, click the pencil, paste the new content, and commit. For new files, use **Add file → Create new file** with the indicated path.

## 2. Supabase

In your existing Supabase project → SQL Editor → New query, paste `schema_v2.sql` and click Run. No existing data is deleted.

## 3. Streamlit

Your existing Streamlit app redeploys from `main`. Keep your existing `APP_PASSWORD`, `SUPABASE_URL`, and `SUPABASE_KEY` in Streamlit Secrets. Change the dashboard password if it appeared in screenshots. No new Streamlit secrets are required for the deterministic V2 preview.

Go to **Autonomous V2 → Preview research and allocations**. Start with 10–20 tickers to test. A large Yahoo Finance scan can be slow, rate-limited, or fail. The preview does NOT execute trades.

## 4. Scheduled daily automatic fictional trades (opt-in)

GitHub repo → **Settings → Secrets and variables → Actions**:

- Under **Repository secrets**, add `SUPABASE_URL` and `SUPABASE_KEY` with the same values used in Streamlit. Do not commit these values to code.
- Under **Repository variables**, add `ENABLE_AUTOMATED_PAPER_TRADES` = `true` **only after reviewing the dry-run and understanding the limitations**. With the variable missing/false, the job only previews.
- Open **Actions → Daily fictional portfolio research → Run workflow** to test. The workflow is also scheduled at 22:30 UTC on weekdays; GitHub may delay scheduled runs.

The workflow has a 55-minute timeout and scans at most 80 of the curated 135 stocks. It may not finish on free APIs. On failures it should stop rather than trade from incomplete holdings prices. The first automatic trade uses fictional capital $100,000. Existing manual trades in Supabase will be included in the ledger; if you have already recorded trades with a different initial capital, do not enable automation until reconciled.

## 5. What is and is not implemented

**Implemented:** 6 transparent deterministic research roles, momentum/volatility/quality signals with missing-data penalties, concentration limits, 20% speculative sleeve cap, 8% minimum cash target, buy/sell paper ledger, latest-price valuation, optional scheduled paper trades, idempotent daily event IDs, and basic unit tests.

**Not implemented:** trained ML return forecasts, automated LLM debate with sourced documents, 13F/insider/news ingestion, truly comprehensive worldwide stock coverage, realistic intraday fills, a validated historical point-in-time backtest, guaranteed daily successful runs, or investment alpha. The existing separate four-role document-grounded AI research page remains available when `OPENAI_API_KEY` is set. These are future phases, not features to claim already working.

**Safety:** `SUPABASE_KEY` must be a server-side secret/service-role credential. Do not grant public anon table access, disable RLS, or expose the GitHub Actions secret. Never connect brokerage credentials. No real money is invested.
