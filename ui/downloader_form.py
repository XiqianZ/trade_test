import streamlit as st
import pandas as pd
from datetime import date, timedelta
from data import download_ticker
from data.downloader import MAX_LOOKBACK_DAYS


_INTERVALS = ["1d", "1wk", "1mo", "1h", "30m", "15m", "5m", "1m"]


def render_downloader_form() -> pd.DataFrame | None:
    """Render the stock downloader form.

    Returns the downloaded DataFrame when the user submits, otherwise None.
    """
    st.subheader("Download Stock Data")

    col1, col2 = st.columns(2)
    with col1:
        symbol = st.text_input("Ticker symbol", value="AAPL", placeholder="e.g. AAPL, TSLA")
    with col2:
        interval = st.selectbox("Interval", options=_INTERVALS, index=0)

    max_days = MAX_LOOKBACK_DAYS.get(interval)
    today = date.today()
    if max_days is not None:
        st.info(f"**{interval}** interval supports at most **{max_days} days** of history (yfinance limit).")
        default_start = today - timedelta(days=max_days)
        min_start = today - timedelta(days=max_days)
    else:
        default_start = today - timedelta(days=365)
        min_start = date(2000, 1, 1)

    col3, col4 = st.columns(2)
    with col3:
        start = st.date_input("Start date", value=default_start, min_value=min_start, max_value=today)
    with col4:
        end = st.date_input("End date", value=today, min_value=min_start, max_value=today)

    if st.button("Download", type="primary"):
        symbol = symbol.strip().upper()
        if not symbol:
            st.error("Please enter a ticker symbol.")
            return None
        if start >= end:
            st.error("Start date must be before end date.")
            return None
        with st.spinner(f"Downloading {symbol}…"):
            try:
                df = download_ticker(
                    symbol,
                    start=str(start),
                    end=str(end),
                    interval=interval,
                )
            except ValueError as exc:
                st.error(str(exc))
                return None

        st.success(f"Downloaded {len(df):,} rows for **{symbol}**.")
        st.dataframe(df, use_container_width=True)
        return df

    return None
