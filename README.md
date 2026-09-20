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
- **Short Term 0–7 Day Plays** — up to 4 higher-risk picks, color-highlighted, with a
  risk warning and a news/macro check
- **TastyTrade-style picks** — 0.20Δ/0.13Δ bull put spread + ~42 DTE iron condors
  (managed-at-21-DTE), color-highlighted
- **Weekend Play** — a Thursday/Friday-entry, Monday-exit theta play (only appears
  Thu/Fri/weekend; shows "Will start work on Thursday" earlier in the week)
- A second page, **SPY/VIX Predictor**, using the VIX term structure (VIX / VIX9D / VIX3M)
  to gauge near-term expected range and market stress

### POP floor and color coding
Every trade the app shows anywhere — tables and highlighted picks alike — is pre-filtered
to **POP ≥ 70%** (the `MIN_POP` constant near the top of `app.py`); anything that doesn't
clear that bar is left off the page rather than shown greyed out. What does clear it is
color-coded:

- 🟢 **Green** — POP ≥ 90%
- 🟡 **Yellow** — POP 70–89%

Change the bar by editing `MIN_POP` in `app.py`; the color thresholds live in `pop_colors()`
right below it.

### Dark mode
The app ships with `.streamlit/config.toml` set to Streamlit's built-in dark theme, so it
opens in dark mode by default for every viewer — no per-user toggle needed. Adjust the
`[theme]` colors in that file if you want a different palette.

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

## Repository layout
Streamlit cares about *exactly* where each file sits, so keep this structure whether you're
running locally or pushing to GitHub:

```
options_by_claude/                 <- repo root
├── app.py                         <- main page (multipage nav entry point) — MUST be at root
├── requirements.txt                <- installed automatically by Streamlit Cloud
├── .streamlit/
│   └── config.toml                <- forces dark theme; must be named exactly this
├── pages/                          <- extra pages for multipage nav — folder name is fixed
│   └── 1_SPY_VIX_Predictor.py     <- leading "1_" controls its position in the sidebar
└── README.md
```

Rules that matter:
- `app.py` stays at the **repo root**, never inside a subfolder — that's the file you point
  Streamlit at.
- Extra pages go in a folder literally named `pages/`, also at the repo root, one `.py` file
  per page. Streamlit auto-adds them to the sidebar nav in filename order, which is why the
  VIX predictor page is prefixed `1_`.
- `.streamlit/config.toml` must keep that exact path (dot-folder named `.streamlit`) —
  that's the only file controlling the dark theme.
- `requirements.txt` also stays at the repo root; Streamlit Cloud reads it from there to
  install dependencies before first run.

## Run it locally first
```bash
pip install -r requirements.txt
streamlit run app.py
```
(The `.streamlit/config.toml` theme applies locally too — no extra flag needed.)

## Push to GitHub
```bash
cd options_by_claude
git init                                   # skip if already a git repo
git add .
git commit -m "Options income dashboard"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```
Make sure the layout above survived the push (check on github.com that `app.py`,
`requirements.txt`, `.streamlit/config.toml`, and `pages/1_SPY_VIX_Predictor.py` are all
there at the paths shown) — a misplaced file is the #1 cause of Streamlit Cloud deploys
that "work" but show a blank sidebar or a plain white (light-mode) page.

## Hosting on Streamlit Community Cloud (free)
1. Push the repo to GitHub using the layout above.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **"New app,"** pick your repo and branch, and set **Main file path** to `app.py`.
4. Click **Deploy**. Streamlit Cloud installs `requirements.txt` automatically, picks up
   `.streamlit/config.toml` for the dark theme, and finds `pages/1_SPY_VIX_Predictor.py`
   for the sidebar — no extra config needed. You'll get a public `*.streamlit.app` URL.
5. Any future `git push` to the deployed branch auto-redeploys the app.

Alternatives if you'd rather not use Streamlit Cloud: Render.com, Railway, or Hugging
Face Spaces (Streamlit SDK) all support this exact folder layout with a similar free tier.

## Disclaimer
This tool is for education/research only. It is not personalized financial advice, and
its output should not be the sole basis for any trade. Options trading involves
substantial risk, including total loss of the amount risked.
