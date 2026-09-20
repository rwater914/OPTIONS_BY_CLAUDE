"""
Options Income Dashboard
=========================
EDUCATIONAL / DECISION-SUPPORT TOOL. NOT FINANCIAL ADVICE.

Data source: Yahoo Finance via `yfinance` (free, no API key). See
optionmath.py for the Black-Scholes / lognormal math used to compute
delta and probability-of-profit (POP) locally, since Yahoo doesn't hand
out option Greeks directly.

Nothing in this app is a recommendation to buy or sell anything. Options
involve substantial risk of loss. Verify all numbers with your own
broker's live quotes before placing any trade.
"""

import streamlit as st
from datetime import datetime
import pandas as pd

from optionmath import (
    get_price, get_avg_iv_proxy, get_expirations, get_chain, get_news,
    pick_expiration, days_to, build_bull_put_spread, build_iron_condor,
    fmt_spread, fmt_condor, color_block, expected_move,
)

st.set_page_config(page_title="Options Income Dashboard", layout="wide")

# ----------------------------------------------------------------------
# UI — HEADER / TICKER
# ----------------------------------------------------------------------

st.title("📈 Options Income Dashboard")
st.caption(
    "Educational tool only — not financial advice. Numbers are computed live "
    "from Yahoo Finance option chains using Black-Scholes delta/POP math. "
    "Always confirm against your broker's live quotes before trading."
)

ticker = st.text_input("Ticker to analyze", value="SPY").upper().strip()

S = get_price(ticker)
if S is None:
    st.error("Couldn't fetch a price for that ticker. Check the symbol and try again.")
    st.stop()

expirations = get_expirations(ticker)
if not expirations:
    st.error("No options chain found for that ticker (it may not have listed options).")
    st.stop()

st.metric(f"{ticker} Last Price", f"${S:,.2f}")

# ----------------------------------------------------------------------
# SECTION: Bull Put Spreads across DTEs / deltas
# ----------------------------------------------------------------------

st.header("Bull Put Spreads — by Target Delta & DTE")
st.caption("Short-leg deltas requested: 0.20, 0.13, 0.11. DTEs: 7, 14, 21, 30, 41 (nearest available expiration, Fridays preferred).")

dte_targets = [7, 14, 21, 30, 41]
delta_targets = [0.20, 0.13, 0.11]

bps_rows = []
for dte in dte_targets:
    exp = pick_expiration(expirations, dte)
    if exp is None:
        continue
    T = days_to(exp) / 365
    puts, calls = get_chain(ticker, exp)
    for dl in delta_targets:
        sp = build_bull_put_spread(puts, S, T, dl)
        bps_rows.append({
            "Target DTE": dte, "Expiration": exp, "Actual DTE": days_to(exp),
            "Target Δ": dl,
            "Short Strike": sp["short_strike"] if sp else "-",
            "Long Strike": sp["long_strike"] if sp else "-",
            "Credit": sp["credit"] if sp else "-",
            "Max Loss": sp["max_loss"] if sp else "-",
            "POP %": sp["pop"] if sp else "-",
        })

if bps_rows:
    st.dataframe(pd.DataFrame(bps_rows), use_container_width=True, hide_index=True)
else:
    st.warning(
        "Couldn't pull any expirations/chain data for this ticker right now — Yahoo Finance may be "
        "rate-limiting or temporarily unreachable (this is more common on cloud-hosted deployments "
        "than running locally). Try again in a minute, or verify locally with `streamlit run app.py`."
    )

# ----------------------------------------------------------------------
# SECTION: Predicted trading range
# ----------------------------------------------------------------------

st.header("Predicted Trading Range")
iv_proxy = get_avg_iv_proxy(ticker)
if iv_proxy:
    horizons = [("Next session", 1), ("7 days", 7), ("14 days", 14), ("21 days", 21)]
    rows = []
    for label, d in horizons:
        mv = expected_move(S, iv_proxy, d)
        rows.append({"Horizon": label, "Low": round(S - mv, 2), "High": round(S + mv, 2),
                      "±1σ Move": round(mv, 2)})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(f"Based on a ~{round(iv_proxy*100,1)}% implied volatility proxy (nearest-to-30-day ATM option). "
               "This is a 1-standard-deviation lognormal range (~68% confidence), not a hard prediction.")
else:
    st.info("Couldn't derive an IV proxy for this ticker right now.")

st.subheader("Rationale / Recent News")
news = get_news(ticker)
if news:
    for n in news:
        st.write(f"• {n}")
else:
    st.write("No recent headlines pulled for this ticker. Check your broker/news terminal directly.")
st.caption("Headlines are pulled live from Yahoo Finance's news feed for this ticker — cross-check anything "
           "market-moving (Fed meetings, CPI, earnings, geopolitical events) against a primary news source.")

# ----------------------------------------------------------------------
# SECTION: Today's Stock Pick (cross-ticker scan, not just the ticker above)
# ----------------------------------------------------------------------

st.header("🔎 Today's Stock Pick — Best Bull Put Spread Premium")
st.caption(
    "This is Claude's own pick, scanned across a watchlist of liquid, optionable names — not "
    "necessarily the ticker entered above. Looking for decent premium at ~30-45 DTE with the "
    "short-leg delta under 0.20. A separate, higher-delta 'high conviction' alternate is also "
    "shown when a name stands out with unusually rich premium — that one needs real conviction "
    "from the news/rationale, not just a bigger credit."
)

WATCHLIST = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMD", "TSLA", "META",
             "F", "INTC", "SOFI", "XOM"]

@st.cache_data(ttl=600)
def scan_watchlist_for_pick(tickers, dte_lo=28, dte_hi=45):
    candidates = []
    for t in tickers:
        try:
            px = get_price(t)
            exps = get_expirations(t)
            if px is None or not exps:
                continue
            exp = pick_expiration(exps, 35)
            if exp is None:
                continue
            dte = days_to(exp)
            if dte < dte_lo or dte > dte_hi:
                continue
            T = dte / 365
            puts, _ = get_chain(t, exp)
            for dl in [0.20, 0.18, 0.16, 0.13, 0.11, 0.10, 0.08]:
                sp = build_bull_put_spread(puts, px, T, dl)
                if sp is None or sp["max_loss"] <= 0:
                    continue
                ror = sp["credit"] * 100 / sp["max_loss"]
                candidates.append({"ticker": t, "exp": exp, "dte": dte, "ror": ror, **sp})
        except Exception:
            continue
    return candidates

with st.spinner("Scanning watchlist for the best bull put spread premium..."):
    pick_candidates = scan_watchlist_for_pick(WATCHLIST)

if not pick_candidates:
    st.warning(
        "Couldn't pull live chain data for any watchlist ticker right now — Yahoo Finance may be "
        "rate-limiting or temporarily unreachable (this is more common on cloud-hosted deployments "
        "than running locally). Try again shortly, or verify locally with `streamlit run app.py`."
    )

under20 = [c for c in pick_candidates if c["short_delta"] < 0.20 and c["pop"] >= 65]
if under20:
    best_pick = max(under20, key=lambda c: c["ror"])
    st.subheader(f"Pick: {best_pick['ticker']}")
    st.write(
        f"**{best_pick['ticker']} Bull Put Spread** — Exp {best_pick['exp']} ({best_pick['dte']} DTE)  \n"
        f"{fmt_spread(best_pick)}  \n"
        f"Return on margin ≈ {best_pick['ror']:.1f}%"
    )
    pick_news = get_news(best_pick["ticker"], limit=3)
    if pick_news:
        st.write("Rationale / recent news:")
        for h in pick_news:
            st.write(f"• {h}")
else:
    st.write("No watchlist name cleared a clean sub-0.20Δ setup with decent premium right now.")

high_conv = [c for c in pick_candidates if 0.20 <= c["short_delta"] <= 0.32 and c["pop"] >= 60]
if high_conv:
    alt_pick = max(high_conv, key=lambda c: c["ror"])
    st.subheader(f"Alternate (higher delta, richer premium): {alt_pick['ticker']}")
    st.write(
        f"**{alt_pick['ticker']} Bull Put Spread** — Exp {alt_pick['exp']} ({alt_pick['dte']} DTE)  \n"
        f"{fmt_spread(alt_pick)}  \n"
        f"Return on margin ≈ {alt_pick['ror']:.1f}%"
    )
    st.caption("Delta is above the usual 0.20 ceiling — only take this if the news/rationale below "
               "gives real conviction, not just because the premium is bigger.")
    alt_news = get_news(alt_pick["ticker"], limit=3)
    if alt_news:
        for h in alt_news:
            st.write(f"• {h}")

# ----------------------------------------------------------------------
# SECTION: Poor Man's Pick ($200 and $100 margin)
# ----------------------------------------------------------------------

st.header("💡 Poor Man's Pick")
st.caption("Best available defined-risk trade for a low-AUM account, targeting ≥70% POP. "
           "DTE and structure chosen for best fit — this deliberately isn't limited to bull put "
           "spreads; an iron condor is considered too when it lands closer to the target margin "
           "at the same POP bar.")

def scan_for_margin_target(ticker, expirations, target_margin, min_pop=70):
    """Scan several DTEs/deltas/widths across BOTH bull put spreads and iron
    condors for whichever structure's max loss lands closest to the target
    margin while clearing min_pop. Bull put spreads aren't the only option
    for a low-AUM account — a condor can sometimes fit a tight margin target
    better for a similar POP."""
    best = None
    best_score = 1e9
    for dte in [7, 14, 21, 30, 41]:
        exp = pick_expiration(expirations, dte)
        if exp is None:
            continue
        T = days_to(exp) / 365
        puts, calls = get_chain(ticker, exp)

        for dl in [0.30, 0.25, 0.20, 0.16, 0.13, 0.11, 0.10]:
            for width in [1, 2, 2.5, 5]:
                sp = build_bull_put_spread(puts, S, T, dl, width=width)
                if sp is None or sp["pop"] < min_pop or sp["max_loss"] <= 0:
                    continue
                score = abs(sp["max_loss"] - target_margin)
                if score < best_score:
                    best_score = score
                    best = {**sp, "dte": days_to(exp), "expiration": exp}

        for dl in [0.20, 0.16, 0.13, 0.11, 0.10, 0.08]:
            for width in [1, 2, 2.5, 5]:
                ic = build_iron_condor(puts, calls, S, T, dl, width=width)
                if ic is None or ic["pop"] < min_pop or ic["max_loss"] <= 0:
                    continue
                score = abs(ic["max_loss"] - target_margin)
                if score < best_score:
                    best_score = score
                    best = {**ic, "dte": days_to(exp), "expiration": exp}
    return best

for margin in (200, 100):
    pick = scan_for_margin_target(ticker, expirations, margin)
    st.subheader(f"${margin} Margin Pick")
    if pick:
        detail = fmt_spread(pick) if pick["type"] == "Bull Put Spread" else fmt_condor(pick)
        st.write(f"**{ticker} {pick['type']}** — Exp {pick['expiration']} ({pick['dte']} DTE)  \n{detail}")
        if pick["type"] == "Iron Condor":
            st.caption("An iron condor was picked over a bull put spread here — it landed closer to the "
                       "target margin at the required POP by collecting premium on both sides.")
    else:
        st.write(f"No bull put spread or iron condor near ${margin} margin cleared 70% POP with this chain. "
                 "Consider a further-OTM single cash-secured put or a smaller-width spread on a lower-priced ticker instead.")

st.caption("If nothing in the chain meaningfully fits the $100–$200 margin bucket at ≥70% POP, a cash-secured put "
           "on a lower-priced, liquid ticker (or a narrower-width spread) is usually the better fit than forcing a bad structure.")

# ----------------------------------------------------------------------
# SECTION: Iron Condor Candidates
# ----------------------------------------------------------------------

st.header("Iron Condor Candidates")
st.caption("Same ticker. DTEs: 1, 7, 14, 42 (Friday expirations preferred where available). Short-leg delta ≈ 0.16 both sides.")

ic_rows = []
for dte in [1, 7, 14, 42]:
    exp = pick_expiration(expirations, dte)
    if exp is None:
        continue
    T = days_to(exp) / 365
    puts, calls = get_chain(ticker, exp)
    ic = build_iron_condor(puts, calls, S, T, 0.16)
    ic_rows.append({
        "Target DTE": dte, "Expiration": exp, "Actual DTE": days_to(exp),
        "Put Short/Long": f"{ic['put_short']}/{ic['put_long']}" if ic else "-",
        "Call Short/Long": f"{ic['call_short']}/{ic['call_long']}" if ic else "-",
        "Credit": ic["credit"] if ic else "-",
        "Max Loss": ic["max_loss"] if ic else "-",
        "POP %": ic["pop"] if ic else "-",
    })
st.dataframe(pd.DataFrame(ic_rows), use_container_width=True, hide_index=True)

st.subheader("🎯 Today's Pick — Best Iron Condor (≥80% POP)")
best_condor, best_condor_meta = None, None
for dte in [1, 7, 14, 21, 30, 41, 42]:
    exp = pick_expiration(expirations, dte)
    if exp is None:
        continue
    T = days_to(exp) / 365
    puts, calls = get_chain(ticker, exp)
    for dl in [0.10, 0.08, 0.06]:
        ic = build_iron_condor(puts, calls, S, T, dl)
        if ic and ic["pop"] >= 80:
            if best_condor is None or ic["max_gain"] > best_condor["max_gain"]:
                best_condor, best_condor_meta = ic, {"exp": exp, "dte": days_to(exp), "delta": dl}
if best_condor:
    st.write(f"**{ticker} Iron Condor** — Exp {best_condor_meta['exp']} ({best_condor_meta['dte']} DTE)  \n"
             + fmt_condor(best_condor))
else:
    st.write("No condor cleared 80% POP across scanned deltas/DTEs on this chain — market may be too volatile "
             "for an 80% structure right now.")

st.subheader("🎯 Today's Pick — Bull Put Spread")
bps_pick_exp = pick_expiration(expirations, 30)
bps_pick_puts, _ = get_chain(ticker, bps_pick_exp)
bps_pick = build_bull_put_spread(bps_pick_puts, S, days_to(bps_pick_exp) / 365, 0.20)
st.write(f"**{ticker} Bull Put Spread** (30 DTE, ~0.20Δ) — " + fmt_spread(bps_pick))

# ----------------------------------------------------------------------
# SECTION: Short Term 0-7 Day Plays
# ----------------------------------------------------------------------

st.header("⚠️ Short Term 0–7 Day Plays")
color_block(
    "<b>RISK WARNING:</b> 0DTE–7DTE trades are high gamma-risk — small underlying moves can "
    "swing P/L fast, and these are far more sensitive to headline/news risk than the longer-dated "
    "picks above. Size these smaller.",
    "#3a1f1f", "#e05252"
)

st_rows_html = []
count = 0
for dte in [0, 1, 2, 3, 5, 7]:
    if count >= 4:
        break
    exp = pick_expiration(expirations, dte, prefer_friday=False)
    if exp is None:
        continue
    T = max(days_to(exp), 0.3) / 365
    puts, calls = get_chain(ticker, exp)
    sp = build_bull_put_spread(puts, S, T, 0.15)  # ~0.15Δ short -> targeting >72% POP
    if sp and sp["pop"] >= 72:
        color_block(
            f"<b>Pick {count+1} — Bull Put Spread</b><br>Exp {exp} ({days_to(exp)} DTE)<br>"
            f"{fmt_spread(sp)}",
            "#1f2e3a", "#4a90d9"
        )
        count += 1

if count == 0:
    st.write("No 0–7 DTE structure cleared the 72% POP bar on this chain right now.")

news_short = get_news(ticker, limit=3)
st.markdown("**News/macro check for these short-dated picks:**")
if news_short:
    for n in news_short:
        st.write(f"• {n}")
st.caption("Also check the economic calendar (CPI/PCE, FOMC, jobs report) and any major geopolitical headlines "
           "for the specific expiration dates above — a single headline can blow through a 0–7DTE spread.")

# ----------------------------------------------------------------------
# SECTION: TastyTrade
# ----------------------------------------------------------------------

st.header("TastyTrade-Style Picks")
color_block(
    "Rules used: Bull Put Spread — sell ~0.20Δ put / buy ~0.13Δ put. "
    "Iron Condor — 40–44 DTE (target 42), managed toward closing at 21 DTE.",
    "#1f3a2e", "#4ad991"
)

tt_exp = pick_expiration(expirations, 42)
tt_count = 0
if tt_exp:
    T = days_to(tt_exp) / 365
    puts, calls = get_chain(ticker, tt_exp)
    tt_bps = build_bull_put_spread(puts, S, T, 0.20, long_delta=0.13)
    if tt_bps:
        color_block(f"<b>TastyTrade Pick 1 — Bull Put Spread</b><br>Exp {tt_exp} ({days_to(tt_exp)} DTE, target 42)<br>"
                     f"{fmt_spread(tt_bps)}<br><i>Plan: manage/close at 21 DTE.</i>", "#1f3a2e", "#4ad991")
        tt_count += 1
    tt_ic = build_iron_condor(puts, calls, S, T, 0.16)
    if tt_ic:
        color_block(f"<b>TastyTrade Pick 2 — Iron Condor</b><br>Exp {tt_exp} ({days_to(tt_exp)} DTE, target 42)<br>"
                     f"{fmt_condor(tt_ic)}<br><i>Plan: manage/close at 21 DTE.</i>", "#1f3a2e", "#4ad991")
        tt_count += 1

# two more: a slightly tighter and a slightly wider condor as alternates
for dl, label in [(0.20, "TastyTrade Pick 3 — Wider Iron Condor (0.20Δ)"),
                   (0.10, "TastyTrade Pick 4 — Tighter Iron Condor (0.10Δ)")]:
    if tt_exp:
        ic = build_iron_condor(puts, calls, S, T, dl)
        if ic:
            color_block(f"<b>{label}</b><br>Exp {tt_exp} ({days_to(tt_exp)} DTE)<br>{fmt_condor(ic)}",
                         "#1f3a2e", "#4ad991")

# ----------------------------------------------------------------------
# SECTION: Weekend Play
# ----------------------------------------------------------------------

st.header("🌙 Weekend Play (Theta Decay Over the Weekend)")
today_wd = datetime.now().weekday()  # Mon=0 ... Sun=6
if today_wd < 3:  # Mon, Tue, Wed
    st.write("**Will start work on Thursday.**")
else:
    # Thu (3) or Fri (4) -> build a play; weekend/Sat/Sun show last computed Fri play
    exp = pick_expiration(expirations, 4, prefer_friday=True)  # nearest weekly Friday-ish
    if exp:
        T = max(days_to(exp), 0.5) / 365
        puts, calls = get_chain(ticker, exp)
        wk_sp = build_bull_put_spread(puts, S, T, 0.15)
        if wk_sp:
            st.write(f"**{ticker} Weekend Bull Put Spread** — Exp {exp} ({days_to(exp)} DTE)  \n"
                     f"{fmt_spread(wk_sp)}  \n"
                     "Plan: open Thursday/Friday, close Monday morning/afternoon to capture weekend theta decay "
                     "while the underlying is untraded.")
        else:
            st.write("No qualifying spread found for the weekend play on this chain.")
    else:
        st.write("No near-term Friday expiration available for this ticker.")

st.caption("Weekend plays rely on time decay accruing over Sat/Sun with no offsetting price movement — they can "
           "still lose if the stock gaps on Monday's open (earnings, news, macro data due over the weekend).")

st.markdown("---")
st.info(
    "📊 Want SPX/SPY-specific 0/1/3 DTE tiered plays (>70%/>80%/>90% POP) and a broad-market SPY/VIX "
    "range read? See the **SPY / VIX Predictor** and **SPX / SPY Index Tiers** pages in the sidebar."
)

st.markdown("---")
st.caption(
    "⚠️ Disclaimer: This tool is for education/research only. It is not personalized financial advice, "
    "and Anthropic/Claude is not a registered investment advisor or broker-dealer. Options trading involves "
    "substantial risk, including total loss of the amount risked. Data is delayed/approximate — verify all "
    "strikes, credits, and Greeks with your broker before placing any trade."
)
