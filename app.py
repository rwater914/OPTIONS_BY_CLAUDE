"""
Options Income Dashboard
=========================
EDUCATIONAL / DECISION-SUPPORT TOOL. NOT FINANCIAL ADVICE.

Data source: Yahoo Finance via `yfinance` (free, no API key).
Yahoo does not hand out option Greeks directly, so this app computes
delta and probability-of-profit (POP) itself using each contract's
implied volatility (as reported by Yahoo) plugged into the standard
Black-Scholes / lognormal model. This is the same underlying math
most retail platforms (thinkorswim, tastytrade) use.

Nothing in this app is a recommendation to buy or sell anything.
Options involve substantial risk of loss. Verify all numbers with
your own broker's live quotes before placing any trade.
"""

import streamlit as st
import yfinance as yf
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta
import pandas as pd

st.set_page_config(page_title="Options Income Dashboard", layout="wide")

R = 0.045  # rough risk-free rate assumption (3-mo T-bill ballpark)

# ----------------------------------------------------------------------
# MATH
# ----------------------------------------------------------------------

def bs_put_delta(S, K, T, sigma):
    if T <= 0 or sigma <= 0:
        return -1.0 if S < K else 0.0
    d1 = (np.log(S / K) + (R + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1) - 1

def bs_call_delta(S, K, T, sigma):
    if T <= 0 or sigma <= 0:
        return 1.0 if S > K else 0.0
    d1 = (np.log(S / K) + (R + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1)

def prob_above(S, K, T, sigma):
    """Risk-neutral probability price finishes above K at expiration."""
    if T <= 0 or sigma <= 0:
        return 1.0 if S > K else 0.0
    d2 = (np.log(S / K) + (R - 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return norm.cdf(d2)

def prob_below(S, K, T, sigma):
    return 1 - prob_above(S, K, T, sigma)

def expected_move(S, sigma, days):
    T = days / 365
    return S * sigma * np.sqrt(T)

# ----------------------------------------------------------------------
# DATA
# ----------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_price(ticker):
    hist = yf.Ticker(ticker).history(period="5d")
    if hist.empty:
        return None
    return float(hist["Close"].iloc[-1])

@st.cache_data(ttl=300)
def get_avg_iv_proxy(ticker):
    """Rough IV proxy from the nearest-to-30-day ATM option, used for the
    predicted-range section."""
    tk = yf.Ticker(ticker)
    exps = tk.options
    if not exps:
        return None
    target = pick_expiration(exps, 30)
    if target is None:
        return None
    puts, calls = get_chain(ticker, target)
    S = get_price(ticker)
    if S is None or calls.empty:
        return None
    calls = calls.copy()
    calls["diff"] = (calls["strike"] - S).abs()
    atm = calls.sort_values("diff").iloc[0]
    iv = atm.get("impliedVolatility", None)
    return float(iv) if iv and iv > 0 else None

@st.cache_data(ttl=300)
def get_expirations(ticker):
    try:
        return yf.Ticker(ticker).options
    except Exception:
        return []

@st.cache_data(ttl=300)
def get_chain(ticker, expiration):
    chain = yf.Ticker(ticker).option_chain(expiration)
    return chain.puts, chain.calls

@st.cache_data(ttl=900)
def get_news(ticker, limit=4):
    try:
        news = yf.Ticker(ticker).news
        out = []
        for n in news[:limit]:
            title = n.get("title") or (n.get("content") or {}).get("title")
            if title:
                out.append(title)
        return out
    except Exception:
        return []

def pick_expiration(expirations, target_days, prefer_friday=True):
    if not expirations:
        return None
    today = datetime.now().date()
    target = today + timedelta(days=target_days)
    valid = [e for e in expirations if datetime.strptime(e, "%Y-%m-%d").date() >= today]
    if not valid:
        return None
    def score(e):
        d = datetime.strptime(e, "%Y-%m-%d").date()
        s = abs((d - target).days)
        if prefer_friday and d.weekday() != 4:
            s += 1.5
        return s
    return sorted(valid, key=score)[0]

def days_to(expiration):
    d = datetime.strptime(expiration, "%Y-%m-%d").date()
    return max((d - datetime.now().date()).days, 0)

def find_put_by_delta(puts, S, T, target_delta):
    best, best_diff = None, 999
    for _, row in puts.iterrows():
        iv = row.get("impliedVolatility", 0)
        if not iv or iv <= 0:
            continue
        d = bs_put_delta(S, row["strike"], T, iv)
        diff = abs(abs(d) - target_delta)
        if diff < best_diff:
            best_diff, best = diff, row
    return best

def find_call_by_delta(calls, S, T, target_delta):
    best, best_diff = None, 999
    for _, row in calls.iterrows():
        iv = row.get("impliedVolatility", 0)
        if not iv or iv <= 0:
            continue
        d = bs_call_delta(S, row["strike"], T, iv)
        diff = abs(d - target_delta)
        if diff < best_diff:
            best_diff, best = diff, row
    return best

def mid_credit(short_row, long_row):
    s_bid = short_row.get("bid", 0) or 0
    l_ask = long_row.get("ask", 0) or 0
    credit = s_bid - l_ask
    if credit <= 0:
        credit = max(0.05, (short_row.get("lastPrice", 0) or 0) - (long_row.get("lastPrice", 0) or 0))
    return round(credit, 2)

def build_bull_put_spread(puts, S, T, short_delta, long_delta=None, width=None):
    short_leg = find_put_by_delta(puts, S, T, short_delta)
    if short_leg is None:
        return None
    if long_delta is not None:
        long_leg = find_put_by_delta(puts, S, T, long_delta)
    else:
        target_strike = short_leg["strike"] - (width or max(1, round(S * 0.01)))
        cands = puts[puts["strike"] < short_leg["strike"]]
        if cands.empty:
            return None
        long_leg = cands.iloc[(cands["strike"] - target_strike).abs().argsort().iloc[0]]
    if long_leg is None or long_leg["strike"] >= short_leg["strike"]:
        return None
    credit = mid_credit(short_leg, long_leg)
    spread_width = round(short_leg["strike"] - long_leg["strike"], 2)
    max_loss = round(max(spread_width - credit, 0.01) * 100, 2)
    iv = short_leg.get("impliedVolatility", 0.3)
    breakeven = short_leg["strike"] - credit
    pop = round(prob_above(S, breakeven, T, iv) * 100, 1)
    return {
        "type": "Bull Put Spread",
        "short_strike": short_leg["strike"], "long_strike": long_leg["strike"],
        "credit": credit, "width": spread_width, "max_loss": max_loss,
        "max_gain": round(credit * 100, 2), "pop": pop,
        "short_delta": round(abs(bs_put_delta(S, short_leg["strike"], T, iv)), 3),
        "breakeven": round(breakeven, 2),
    }

def build_iron_condor(puts, calls, S, T, put_delta, call_delta=None, width=None):
    call_delta = call_delta or put_delta
    put_short = find_put_by_delta(puts, S, T, put_delta)
    call_short = find_call_by_delta(calls, S, T, call_delta)
    if put_short is None or call_short is None:
        return None
    w = width or max(1, round(S * 0.01))
    put_cands = puts[puts["strike"] < put_short["strike"]]
    call_cands = calls[calls["strike"] > call_short["strike"]]
    if put_cands.empty or call_cands.empty:
        return None
    put_long = put_cands.iloc[(put_cands["strike"] - (put_short["strike"] - w)).abs().argsort().iloc[0]]
    call_long = call_cands.iloc[(call_cands["strike"] - (call_short["strike"] + w)).abs().argsort().iloc[0]]
    put_credit = mid_credit(put_short, put_long)
    call_credit = mid_credit(call_short, call_long)
    total_credit = round(put_credit + call_credit, 2)
    put_width = round(put_short["strike"] - put_long["strike"], 2)
    call_width = round(call_long["strike"] - call_short["strike"], 2)
    max_loss = round((max(put_width, call_width) - total_credit) * 100, 2)
    iv_p = put_short.get("impliedVolatility", 0.3)
    iv_c = call_short.get("impliedVolatility", 0.3)
    lower_be = put_short["strike"] - total_credit
    upper_be = call_short["strike"] + total_credit
    pop = round((prob_above(S, lower_be, T, iv_p) - prob_above(S, upper_be, T, iv_c)) * 100, 1)
    return {
        "type": "Iron Condor",
        "put_short": put_short["strike"], "put_long": put_long["strike"],
        "call_short": call_short["strike"], "call_long": call_long["strike"],
        "credit": total_credit, "max_loss": max(max_loss, 1),
        "max_gain": round(total_credit * 100, 2), "pop": pop,
        "lower_be": round(lower_be, 2), "upper_be": round(upper_be, 2),
    }

def fmt_spread(sp):
    if sp is None:
        return "No valid contracts found for this expiration/delta combo."
    return (f"Sell {sp['short_strike']}P / Buy {sp['long_strike']}P — "
            f"Credit ${sp['credit']} | Max Loss ${sp['max_loss']} | "
            f"Max Gain ${sp['max_gain']} | POP ≈ {sp['pop']}% | Δshort ≈ {sp['short_delta']}")

def fmt_condor(c):
    if c is None:
        return "No valid contracts found for this expiration/delta combo."
    return (f"Puts: Sell {c['put_short']}/Buy {c['put_long']} · "
            f"Calls: Sell {c['call_short']}/Buy {c['call_long']} — "
            f"Credit ${c['credit']} | Max Loss ${c['max_loss']} | "
            f"Max Gain ${c['max_gain']} | POP ≈ {c['pop']}%")

def color_block(html, bg, border):
    st.markdown(
        f"""<div style="background-color:{bg};border-left:6px solid {border};
        padding:14px 18px;border-radius:8px;margin-bottom:10px;">{html}</div>""",
        unsafe_allow_html=True,
    )

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

st.dataframe(pd.DataFrame(bps_rows), use_container_width=True, hide_index=True)

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
# SECTION: Poor Man's Pick ($200 and $100 margin)
# ----------------------------------------------------------------------

st.header("💡 Poor Man's Pick")
st.caption("Best available defined-risk trade for a low-AUM account, targeting ≥70% POP. "
           "DTE and structure (spread vs. condor) chosen for best fit.")

def scan_for_margin_target(ticker, expirations, target_margin, min_pop=70):
    """Scan several DTEs/deltas for a bull put spread whose max loss lands
    near the target margin with POP above the threshold."""
    best = None
    best_score = 1e9
    for dte in [7, 14, 21, 30, 41]:
        exp = pick_expiration(expirations, dte)
        if exp is None:
            continue
        T = days_to(exp) / 365
        puts, _ = get_chain(ticker, exp)
        for dl in [0.30, 0.25, 0.20, 0.16, 0.13, 0.11, 0.10]:
            for width in [1, 2, 2.5, 5]:
                sp = build_bull_put_spread(puts, S, T, dl, width=width)
                if sp is None or sp["pop"] < min_pop:
                    continue
                score = abs(sp["max_loss"] - target_margin)
                if score < best_score:
                    best_score = score
                    best = {**sp, "dte": days_to(exp), "expiration": exp, "delta_target": dl}
    return best

for margin in (200, 100):
    pick = scan_for_margin_target(ticker, expirations, margin)
    st.subheader(f"${margin} Margin Pick")
    if pick:
        st.write(
            f"**{ticker} Bull Put Spread** — Exp {pick['expiration']} ({pick['dte']} DTE)  \n"
            f"Sell {pick['short_strike']}P / Buy {pick['long_strike']}P  \n"
            f"Credit: ${pick['credit']} | Max Loss: ${pick['max_loss']} | POP ≈ {pick['pop']}%"
        )
    else:
        st.write(f"No bull put spread near ${margin} margin cleared 70% POP with this chain. "
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
bps_pick = build_bull_put_spread(*get_chain(ticker, pick_expiration(expirations, 30)), S,
                                  days_to(pick_expiration(expirations, 30)) / 365, 0.20)
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
st.caption(
    "⚠️ Disclaimer: This tool is for education/research only. It is not personalized financial advice, "
    "and Anthropic/Claude is not a registered investment advisor or broker-dealer. Options trading involves "
    "substantial risk, including total loss of the amount risked. Data is delayed/approximate — verify all "
    "strikes, credits, and Greeks with your broker before placing any trade."
)
