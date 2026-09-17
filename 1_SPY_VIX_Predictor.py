"""
SPY / VIX Predictor page.
EDUCATIONAL ONLY — this is a heuristic volatility/range model, not a crystal ball.
"""

import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="SPY-VIX Predictor", layout="wide")
st.title("📊 SPY / VIX Predictor")
st.caption(
    "Heuristic tool combining SPY price action with the VIX term structure "
    "(spot VIX vs. 9-day and 3-month VIX) to gauge near-term expected range and "
    "whether the market is pricing calm (contango) or stress (backwardation). "
    "Not a prediction of direction — educational only."
)

@st.cache_data(ttl=300)
def get_hist(ticker, period="6mo"):
    return yf.Ticker(ticker).history(period=period)

@st.cache_data(ttl=300)
def get_last(ticker):
    h = yf.Ticker(ticker).history(period="5d")
    return float(h["Close"].iloc[-1]) if not h.empty else None

spy = get_last("SPY")
vix = get_last("^VIX")
vix9d = get_last("^VIX9D")
vix3m = get_last("^VIX3M")

col1, col2, col3, col4 = st.columns(4)
col1.metric("SPY", f"${spy:,.2f}" if spy else "N/A")
col2.metric("VIX (spot)", f"{vix:.2f}" if vix else "N/A")
col3.metric("VIX9D", f"{vix9d:.2f}" if vix9d else "N/A")
col4.metric("VIX3M", f"{vix3m:.2f}" if vix3m else "N/A")

if vix and vix9d and vix3m:
    st.subheader("Term Structure Read")
    if vix9d > vix > vix3m * 0.98:
        st.warning("Short-term VIX9D is elevated relative to spot/3-month — the market is pricing near-term "
                   "event risk (earnings, Fed, data release, or geopolitical headline) higher than the medium term.")
    elif vix < vix9d < vix3m:
        st.success("Classic contango (VIX < VIX9D < VIX3M) — market is pricing a relatively calm near-term backdrop.")
    else:
        st.info("Mixed term structure — no strong signal either way.")

    if spy:
        st.subheader("Expected SPY Range (from VIX)")
        rows = []
        for label, days in [("1 day", 1), ("7 days", 7), ("14 days", 14), ("21 days", 21), ("30 days", 30)]:
            sigma = vix / 100
            move = spy * sigma * np.sqrt(days / 365)
            rows.append({"Horizon": label, "Low": round(spy - move, 2), "High": round(spy + move, 2),
                         "±1σ Move": round(move, 2)})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("1-standard-deviation lognormal range implied by spot VIX (~68% confidence band).")
else:
    st.info("Couldn't pull full VIX term structure data right now.")

st.subheader("Recent SPY Price Action")
hist = get_hist("SPY", "3mo")
if not hist.empty:
    st.line_chart(hist["Close"])

st.markdown("---")
st.caption(
    "⚠️ This page is a simplified volatility heuristic, not a validated forecasting model. "
    "It should not be used as the sole basis for any trading decision."
)
