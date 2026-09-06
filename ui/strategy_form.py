import streamlit as st
from datetime import date, timedelta
from strategy import Universe
from ui.downloader_form import _parse_symbols


def render_universe_form() -> Universe | None:
    """Render the universe selection form.

    The user picks symbols, a date range, and an interval.  On submit,
    a Universe is loaded (using the local Parquet cache) and returned.
    """
    st.subheader("Build Universe")

    col1, col2 = st.columns(2)
    with col1:
        symbols_raw = st.text_input(
            "Symbols",
            value="AAPL, TSLA",
            placeholder='e.g.  AAPL, "TSLA", GOOGL',
            key="universe_symbols",
        )
    with col2:
        interval = st.selectbox(
            "Interval",
            options=["1d", "1wk", "1mo", "1h", "30m", "15m", "5m", "1m"],
            index=0,
            key="universe_interval",
        )

    today = date.today()
    col3, col4 = st.columns(2)
    with col3:
        start = st.date_input(
            "Start date",
            value=today - timedelta(days=365),
            min_value=date(2000, 1, 1),
            max_value=today,
            key="universe_start",
        )
    with col4:
        end = st.date_input(
            "End date",
            value=today,
            min_value=date(2000, 1, 1),
            max_value=today,
            key="universe_end",
        )

    if st.button("Load Universe", type="primary"):
        symbols = _parse_symbols(symbols_raw)
        if not symbols:
            st.error("Enter at least one symbol.")
            return None
        if start >= end:
            st.error("Start date must be before end date.")
            return None

        progress_bar = st.progress(0.0, text="Loading…")
        loaded_so_far = [0]

        def on_progress(symbol, ok, total):
            loaded_so_far[0] += 1
            frac = loaded_so_far[0] / total
            label = f"{'✓' if ok else '✗'} {symbol}  ({loaded_so_far[0]}/{total})"
            progress_bar.progress(frac, text=label)

        universe = Universe.load(
            symbols=symbols,
            start=str(start),
            end=str(end),
            interval=interval,
            progress_callback=on_progress,
        )

        progress_bar.empty()

        if universe.failed:
            st.warning(f"Could not load: {', '.join(universe.failed)}")
        if not universe.data:
            st.error("No data loaded. Check your symbols and date range.")
            return None

        st.success(
            f"Loaded **{len(universe)}** symbol(s): {', '.join(universe.loaded_symbols)}"
        )
        _show_universe_preview(universe)
        return universe

    return None


def _show_universe_preview(universe: Universe) -> None:
    """Show a quick preview of the loaded universe data."""
    close = universe.close()

    st.markdown("**Closing prices preview**")
    st.dataframe(close.tail(10), use_container_width=True)

    st.markdown("**Coverage**")
    rows = [
        {
            "Symbol": symbol,
            "Rows": len(df),
            "From": str(df.index.min().date()),
            "To": str(df.index.max().date()),
        }
        for symbol, df in universe.data.items()
    ]
    import pandas as pd
    st.dataframe(pd.DataFrame(rows).set_index("Symbol"), use_container_width=True)
