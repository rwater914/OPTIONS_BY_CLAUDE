"""
Shared option math / data-fetch helpers used by app.py and the pages/ scripts.

Data source: Yahoo Finance via `yfinance` (free, no API key). Yahoo does not
hand out option Greeks directly, so this module computes delta and
probability-of-profit (POP) itself using each contract's implied volatility
(as reported by Yahoo) plugged into the standard Black-Scholes / lognormal
model. This is the same underlying math most retail platforms (thinkorswim,
tastytrade) use.

Nothing here is a recommendation to buy or sell anything. Verify all numbers
with your own broker's live quotes before placing any trade.
"""

import time

import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
from scipy.stats import norm
from datetime import datetime, timedelta

R = 0.045  # rough risk-free rate assumption (3-mo T-bill ballpark)

EMPTY_CHAIN_COLS = ["strike", "impliedVolatility", "bid", "ask", "lastPrice"]


def _with_retries(fn, attempts=3, base_delay=0.6):
    """Run fn() with a few retries + short backoff, then re-raise the last
    error if every attempt failed. Yahoo/yfinance calls are flaky in practice
    (rate limits, transient network errors, especially from cloud-hosted
    IPs) — every live data fetch in this module goes through this instead of
    calling yfinance directly, so a transient hiccup gets a couple of retries
    before the caller falls back to its own "no data" default rather than
    crashing the whole Streamlit page with a raw traceback."""
    last_exc = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any
            # yfinance/network failure should degrade gracefully, not crash.
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(base_delay * (2 ** attempt))
    raise last_exc

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
    try:
        hist = _with_retries(lambda: yf.Ticker(ticker).history(period="5d"))
    except Exception:
        return None
    if hist is None or hist.empty:
        return None
    return float(hist["Close"].iloc[-1])

@st.cache_data(ttl=300)
def get_avg_iv_proxy(ticker):
    """Rough IV proxy from the nearest-to-30-day ATM option, used for the
    predicted-range section."""
    try:
        exps = get_expirations(ticker)
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
    except Exception:
        return None

@st.cache_data(ttl=300)
def get_expirations(ticker):
    try:
        exps = _with_retries(lambda: yf.Ticker(ticker).options)
        return exps or []
    except Exception:
        return []

@st.cache_data(ttl=300)
def get_chain(ticker, expiration):
    try:
        chain = _with_retries(lambda: yf.Ticker(ticker).option_chain(expiration))
        puts = chain.puts if chain is not None else pd.DataFrame(columns=EMPTY_CHAIN_COLS)
        calls = chain.calls if chain is not None else pd.DataFrame(columns=EMPTY_CHAIN_COLS)
        return puts, calls
    except Exception:
        return pd.DataFrame(columns=EMPTY_CHAIN_COLS), pd.DataFrame(columns=EMPTY_CHAIN_COLS)

@st.cache_data(ttl=900)
def get_news(ticker, limit=4):
    try:
        news = _with_retries(lambda: yf.Ticker(ticker).news, attempts=2) or []
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
