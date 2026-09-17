# Options Income Dashboard

Educational options-strategy dashboard. **Not financial advice.** Built with
[Streamlit](https://streamlit.io) + [yfinance](https://pypi.org/project/yfinance/).

## What it does
Enter a ticker, and the app pulls its live option chain from Yahoo Finance and computes,
using Black-Scholes delta and lognormal probability-of-profit (POP) math:

- Bull put spreads at ~0.20 / 0.13 / 0.11 short-leg delta across 7/14/21/30/41 DTE
- Predicted 1-day / 7-day / 14-day / 21-day trading range (from implied volatility), plus
  live news headlines for the ticker
- **Poor Man's Pick** — best ~$200 and ~$100 margin trade at ≥70% POP
- **Iron Condor Candidates** at 1/7/14/42 DTE (Friday expirations preferred), plus a
  "Today's Pick" bull put spread and iron condor (≥80% POP condor)
- **Short Term 0–7 Day Plays** — 4 higher-risk picks at ≥72% POP, color-highlighted, with a
  risk warning and a news/macro check
- **TastyTrade-style picks** — 0.20Δ/0.13Δ bull put spread + ~42 DTE iron condors
  (managed-at-21-DTE), color-highlighted
- **Weekend Play** — a Thursday/Friday-entry, Monday-exit theta play (only appears
  Thu/Fri/weekend; shows "Will start work on Thursday" earlier in the week)
- A second page, **SPY/VIX Predictor**, using the VIX term structure (VIX / VIX9D / VIX3M)
  to gauge near-term expected range and market stress

## Important limitations — read before trusting any number
- Options data comes from Yahoo Finance, which can be **delayed and has wide/stale
  bid-ask quotes on illiquid names**. Greeks/POP are *computed locally* by this app from
  each contract's implied volatility — they are estimates, not exchange-quoted Greeks.
  Always cross-check against your broker's live chain before placing a trade.
- POP is the standard lognormal/Black-Scholes approximation used across the industry,
  not a guarantee.
- This was built without live internet access in the environment it was written in, so it
  has not been run against real market data yet — sanity-check it locally first (see below).
- Very low-priced or thinly-traded tickers may not have strikes tight enough to hit
  a clean $100/$200 margin target; in that case the Poor Man's Pick section will say so.

## Run it locally first
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Hosting (recommended: GitHub → Streamlit Community Cloud, free)
1. Create a new GitHub repo and push this folder's contents (keep `app.py` at the repo
   root and `pages/` as a subfolder — Streamlit's multipage routing depends on that).
2. Go to https://share.streamlit.io, sign in with GitHub.
3. Click "New app," pick the repo/branch, set the main file to `app.py`, deploy.
4. Streamlit Cloud installs `requirements.txt` automatically and gives you a public URL.

Alternatives if you'd rather not use Streamlit Cloud: Render.com, Railway, or Hugging
Face Spaces (Streamlit SDK) all support this exact setup with a similar free tier.

## Disclaimer
This tool is for education/research only. It is not personalized financial advice, and
its output should not be the sole basis for any trade. Options trading involves
substantial risk, including total loss of the amount risked.
