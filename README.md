# Options Income Dashboard

Educational options-strategy dashboard. **Not financial advice.** Built with
[Streamlit](https://streamlit.io) + [yfinance](https://pypi.org/project/yfinance/).

## What it does
Enter a ticker, and the app pulls its live option chain from Yahoo Finance and computes,
using Black-Scholes delta and lognormal probability-of-profit (POP) math:

- Bull put spreads at ~0.20 / 0.13 / 0.11 short-leg delta across 7/14/21/30/41 DTE
- Predicted 1-day / 7-day / 14-day / 21-day trading range (from implied volatility), plus
  live news headlines for the ticker
- **Today's Stock Pick** — a separate scan across a watchlist of liquid, optionable names
  (not just the ticker you typed in) for the richest bull put spread premium at ~30-45 DTE,
  short-leg delta under 0.20, plus a higher-delta "high conviction" alternate when one name's
  premium stands out, with the news headlines behind it
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
- A third page, **SPX / SPY Index Tiers** — separate SPX and SPY tabs, each with 0/1/3 DTE
  bull put spreads and iron condors tiered at >70% / >80% / >90% POP, plus an >80%-POP
  Friday-entry weekend theta play for each index (held back until Thursday evening/Friday
  close, same as the main Weekend Play section)

Shared option math (Black-Scholes delta, POP, spread/condor construction, chain fetching)
lives in `optionmath.py` and is imported by `app.py` and both pages, so the logic only
exists in one place.

## Important limitations — read before trusting any number
- Options data comes from Yahoo Finance, which can be **delayed and has wide/stale
  bid-ask quotes on illiquid names**. Greeks/POP are *computed locally* by this app from
  each contract's implied volatility — they are estimates, not exchange-quoted Greeks.
  Always cross-check against your broker's live chain before placing a trade.
- POP is the standard lognormal/Black-Scholes approximation used across the industry,
  not a guarantee.
- **SPX index options are often not available through Yahoo Finance / yfinance** — that
  chain data is licensed separately from CBOE. The SPX tab on the Index Tiers page will
  say so plainly and point you at the SPY tab (or your broker's own SPX chain) instead of
  fabricating numbers. SPY, being a regular exchange-listed ETF, works normally.
- Very low-priced or thinly-traded tickers may not have strikes tight enough to hit
  a clean $100/$200 margin target; in that case the Poor Man's Pick section will say so.
- This was built and revised without live internet access to Yahoo Finance in the
  environment it was written in. The option-math logic (delta targeting, POP tiering,
  spread/condor construction) was verified with `streamlit.testing.v1.AppTest` against a
  synthetic option chain (catching and fixing a real argument-order bug in the process —
  see git history), but the app has not yet been run against a real, live Yahoo Finance
  feed. Sanity-check it against real numbers before trusting it (see below).

## Run it locally first
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Hosting (recommended: GitHub → Streamlit Community Cloud, free)
1. Push this repo's contents as-is — `app.py` stays at the repo root and the two extra
   pages live in `pages/` (`pages/1_SPY_VIX_Predictor.py`, `pages/2_SPX_SPY_Index_Tiers.py`).
   Streamlit's multipage routing auto-discovers any `.py` file in `pages/` and lists it in
   the sidebar in filename order — that's why they're prefixed `1_`, `2_`. `optionmath.py`
   stays at the repo root next to `app.py` so both `app.py` and the `pages/` scripts can
   `import optionmath`.
2. Go to https://share.streamlit.io, sign in with GitHub.
3. Click "New app," pick the repo/branch, set the main file to `app.py`, deploy.
4. Streamlit Cloud installs `requirements.txt` automatically and gives you a public URL.

Alternatives if you'd rather not use Streamlit Cloud: Render.com, Railway, or Hugging
Face Spaces (Streamlit SDK) all support this exact setup with a similar free tier.

## Disclaimer
This tool is for education/research only. It is not personalized financial advice, and
its output should not be the sole basis for any trade. Options trading involves
substantial risk, including total loss of the amount risked.
