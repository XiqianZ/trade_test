import re
import time
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from data import (
    cached_download_ticker as download_ticker,
    cached_download_ticker_full_history,
    load_ticker_name_symbols,
)
from data.cache import load_cache
from data.downloader import MAX_LOOKBACK_DAYS


_INTERVALS = ["1d", "1wk", "1mo", "1h", "30m", "15m", "5m", "1m"]


def _parse_symbols(raw: str) -> list[str]:
    """Parse a symbol string into a list of uppercase tickers.

    Delimiters: commas and/or whitespace (any mix).
    Each token may optionally be surrounded by double quotes.

        AAPL TSLA "GOOGL"        →  ["AAPL", "TSLA", "GOOGL"]
        AAPL, "TSLA", GOOGL      →  ["AAPL", "TSLA", "GOOGL"]
        AAPL  TSLA,GOOGL "MSFT"  →  ["AAPL", "TSLA", "GOOGL", "MSFT"]
    """
    symbols = []
    for token in re.split(r'[\s,]+', raw):
        symbol = token.strip('"').upper()
        if symbol:
            symbols.append(symbol)
    return symbols


def render_downloader_form() -> dict[str, pd.DataFrame] | None:
    """Render the stock downloader form.

    Returns a dict mapping each symbol to its DataFrame when the user submits,
    otherwise None.
    """
    st.subheader("Download Stock Data")

    col1, col2 = st.columns(2)
    with col1:
        symbols_raw = st.text_input(
            "Ticker symbols",
            value="AAPL",
            placeholder='e.g.  AAPL, "TSLA", GOOGL',
        )
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
        symbols = _parse_symbols(symbols_raw)
        if not symbols:
            st.error("Please enter at least one ticker symbol.")
            return None
        if start >= end:
            st.error("Start date must be before end date.")
            return None

        results: dict[str, pd.DataFrame] = {}
        errors: list[str] = []

        with st.spinner(f"Downloading {', '.join(symbols)}…"):
            for symbol in symbols:
                try:
                    results[symbol] = download_ticker(
                        symbol,
                        start=str(start),
                        end=str(end),
                        interval=interval,
                    )
                except ValueError as exc:
                    errors.append(str(exc))

        for msg in errors:
            st.error(msg)

        if not results:
            return None

        # Show each symbol in its own tab.
        tabs = st.tabs(list(results.keys()))
        for tab, (symbol, df) in zip(tabs, results.items()):
            with tab:
                st.caption(f"{len(df):,} rows · {interval}")
                st.dataframe(df, use_container_width=True)

        return results

    st.divider()
    st.caption("Bulk full-history download uses the cached ticker-name list in data/cache/ticker_names.json.")

    pause_seconds = st.number_input(
        "Pause between tickers",
        min_value=0.0,
        max_value=10.0,
        value=1.5,
        step=0.5,
        help="Keeps the request rate low so yfinance is less likely to throttle the batch.",
    )

    if st.button("Download full history for all cached ticker names"):
        symbols = load_ticker_name_symbols()
        if not symbols:
            st.error("No ticker names found in data/cache/ticker_names.json.")
            return None

        progress = st.progress(0)
        status = st.empty()
        downloaded = 0
        skipped = 0
        failed: list[str] = []
        need_pause = False

        with st.spinner(f"Downloading full history for {len(symbols)} tickers…"):
            for index, symbol in enumerate(symbols, 1):
                if load_cache(symbol, interval) is not None:
                    skipped += 1
                    status.text(f"{index}/{len(symbols)}: {symbol} already cached")
                    progress.progress(index / len(symbols))
                    continue

                if need_pause and pause_seconds > 0:
                    time.sleep(float(pause_seconds))

                status.text(f"{index}/{len(symbols)}: {symbol}")
                try:
                    cached_download_ticker_full_history(symbol, interval=interval)
                    downloaded += 1
                except ValueError as exc:
                    failed.append(f"{symbol}: {exc}")
                need_pause = True
                progress.progress(index / len(symbols))

        status.text(f"Finished: cached {downloaded} tickers, skipped {skipped} cached tickers.")
        st.success(f"Finished caching {downloaded} tickers; skipped {skipped} already cached.")
        if failed:
            st.warning(f"{len(failed)} tickers could not be downloaded.")
            for message in failed:
                st.error(message)
        return None

    return None
