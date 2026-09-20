"""
SPX / SPY Index Tiers page.
0 / 1 / 3 DTE bull put spreads & iron condors on the two big index proxies,
tiered at >70% / >80% / >90% POP, plus a Friday-entry weekend theta play
for each index.
EDUCATIONAL ONLY — this is not financial advice.
"""

import streamlit as st
from datetime import datetime
import pandas as pd

from optionmath import (
    get_price, get_expirations, get_chain, get_news,
    pick_expiration, days_to, build_bull_put_spread, build_iron_condor,
    fmt_spread, fmt_condor, color_block,
)

st.set_page_config(page_title="SPX / SPY Index Tiers", layout="wide")
st.title("🏛️ SPX / SPY — 0/1/3 DTE Tiered Plays")
st.caption(
    "Short-dated bull put spreads and iron condors on the two big index proxies, tiered by "
    "probability of profit: >70%, >80%, >90%. Higher tiers use farther-out-of-the-money "
    "(lower-delta) strikes and therefore collect less premium. Educational only — not "
    "financial advice."
)

DELTA_SCAN = [0.35, 0.30, 0.25, 0.20, 0.16, 0.13, 0.11, 0.10, 0.08,
              0.06, 0.05, 0.04, 0.03, 0.025, 0.02, 0.015, 0.01]
TIERS = [70, 80, 90]
DTE_TARGETS = [0, 1, 3]


def best_for_tier(build_fn, min_pop):
    """Among all scanned deltas, the highest-credit structure that still
    clears the min_pop bar."""
    best = None
    for dl in DELTA_SCAN:
        s = build_fn(dl)
        if s is None or s["pop"] < min_pop:
            continue
        if best is None or s["credit"] > best["credit"]:
            best = s
    return best


def render_index_tab(ticker, label):
    S = get_price(ticker)
    if S is None:
        st.error(f"Couldn't fetch a live price for {ticker}. Yahoo Finance may not carry this symbol.")
        return
    st.metric(f"{label} Last", f"${S:,.2f}")

    expirations = get_expirations(ticker)
    if not expirations:
        st.warning(
            f"No options chain came back for **{ticker}** from Yahoo Finance / yfinance. This is a "
            "known gap for cash-settled index options — SPX (and XSP/NDX-style index products) "
            "aren't reliably served by this free data source, since that chain data is licensed "
            "separately from CBOE. If you're on the SPX tab, check your broker's own SPX chain "
            "directly, or use the SPY tab here as a liquid, exchange-listed proxy instead."
        )
        return

    for dte in DTE_TARGETS:
        exp = pick_expiration(expirations, dte, prefer_friday=False)
        if exp is None:
            st.write(f"**{dte} DTE target** — no expiration found near this horizon.")
            continue
        actual_dte = days_to(exp)
        T = max(actual_dte, 0.3) / 365
        puts, calls = get_chain(ticker, exp)

        st.subheader(f"{dte} DTE target — Exp {exp} ({actual_dte} calendar days out)")
        bps_rows, ic_rows = [], []
        for tier in TIERS:
            sp = best_for_tier(lambda dl, p=puts, t=T: build_bull_put_spread(p, S, t, dl), tier)
            bps_rows.append({
                "POP Tier": f">{tier}%",
                "Strikes": f"{sp['short_strike']}P/{sp['long_strike']}P" if sp else "-",
                "Credit": sp["credit"] if sp else "-",
                "Max Loss": sp["max_loss"] if sp else "-",
                "Actual POP %": sp["pop"] if sp else "-",
            })
            ic = best_for_tier(lambda dl, p=puts, c=calls, t=T: build_iron_condor(p, c, S, t, dl), tier)
            ic_rows.append({
                "POP Tier": f">{tier}%",
                "Puts": f"{ic['put_short']}/{ic['put_long']}" if ic else "-",
                "Calls": f"{ic['call_short']}/{ic['call_long']}" if ic else "-",
                "Credit": ic["credit"] if ic else "-",
                "Max Loss": ic["max_loss"] if ic else "-",
                "Actual POP %": ic["pop"] if ic else "-",
            })
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Bull Put Spread**")
            st.dataframe(pd.DataFrame(bps_rows), use_container_width=True, hide_index=True)
        with col2:
            st.markdown("**Iron Condor**")
            st.dataframe(pd.DataFrame(ic_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader(f"🌙 {label} Weekend Theta Play (>80% POP)")
    today_wd = datetime.now().weekday()  # Mon=0 ... Sun=6
    if today_wd < 3:  # Mon, Tue, Wed
        st.write(
            "**Will start work on Thursday evening.** This pick is deliberately held back until "
            "Thursday evening or the last 1-2 hours of Friday's session, so it reflects the most "
            "current pricing and news heading into the weekend."
        )
    else:
        exp = pick_expiration(expirations, 4, prefer_friday=True)  # nearest weekly Friday
        if exp:
            actual_dte = days_to(exp)
            T = max(actual_dte, 0.3) / 365
            puts, calls = get_chain(ticker, exp)
            sp80 = best_for_tier(lambda dl: build_bull_put_spread(puts, S, T, dl), 80)
            ic80 = best_for_tier(lambda dl: build_iron_condor(puts, calls, S, T, dl), 80)
            candidates = []
            if sp80:
                candidates.append(("Bull Put Spread", sp80, fmt_spread(sp80)))
            if ic80:
                candidates.append(("Iron Condor", ic80, fmt_condor(ic80)))
            if candidates:
                best_type, best_struct, best_text = max(candidates, key=lambda c: c[1]["credit"])
                color_block(
                    f"<b>{label} Weekend Play — {best_type}</b><br>Exp {exp} ({actual_dte} DTE)<br>"
                    f"{best_text}<br><i>Plan: open Thursday/Friday, close Monday morning/afternoon to "
                    "capture weekend theta decay while the index is untraded.</i>",
                    "#1f2e3a", "#4a90d9",
                )
            else:
                st.write("No structure cleared 80% POP for the weekend play on this chain.")
        else:
            st.write("No near-term Friday expiration available.")

    news = get_news("SPY", limit=4)
    st.markdown("**Market/macro news to weigh before a weekend entry:**")
    if news:
        for n in news:
            st.write(f"• {n}")
    else:
        st.write("No headlines pulled right now — check a primary news/economic-calendar source directly.")
    st.caption(
        "Check the economic calendar (CPI/PCE, FOMC, NFP) and any weekend-risk geopolitical headlines "
        "before holding an index spread over Saturday/Sunday — a Monday gap can blow through even an "
        "80%-POP structure."
    )


tab_spx, tab_spy = st.tabs(["SPX", "SPY"])
with tab_spx:
    render_index_tab("^SPX", "SPX")
with tab_spy:
    render_index_tab("SPY", "SPY")

st.markdown("---")
st.caption(
    "⚠️ Disclaimer: Educational/research tool only, not personalized financial advice. SPX is a "
    "cash-settled, European-style index option — its chain may not be available through this free "
    "data source; always confirm strikes/pricing with your own broker before trading. Options involve "
    "substantial risk, including total loss of the amount risked."
)
