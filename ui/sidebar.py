"""Sidebar panel that lists every symbol currently in the local Parquet cache,
grouped by market, with company names resolved from yfinance.
"""

import streamlit as st
from data import list_cached_symbols
from data.ticker_info import get_ticker_names


def _market_group(symbol: str) -> str:
    """Classify a symbol into a market group by its suffix."""
    upper = symbol.upper()
    if upper.endswith(".T"):
        return "Tokyo (TSE)"
    if upper.endswith(".L"):
        return "London (LSE)"
    if upper.endswith(".HK"):
        return "Hong Kong (HKEX)"
    if upper.endswith(".SS") or upper.endswith(".SZ"):
        return "China (SSE/SZSE)"
    return "US (NYSE/NASDAQ)"


def render_sidebar() -> list[str]:
    """Render the cache browser in the Streamlit sidebar.

    Returns the list of symbols the user has selected (checked), so the
    rest of the app can use them to pre-fill forms or build a Universe.
    """
    with st.sidebar:
        st.header("Cached Symbols")

        symbols = list_cached_symbols()

        if not symbols:
            st.info("No data cached yet. Use **Download Data** to fetch some.")
            return []

        # Resolve names in one batch (reads JSON; only calls yfinance for new ones).
        with st.spinner("Resolving names…"):
            names = get_ticker_names(symbols)

        # Group symbols by market.
        groups: dict[str, list[str]] = {}
        for symbol in symbols:
            group = _market_group(symbol)
            groups.setdefault(group, []).append(symbol)

        selected: list[str] = []

        for group, group_symbols in sorted(groups.items()):
            st.markdown(f"**{group}**")
            for symbol in group_symbols:
                name = names.get(symbol, symbol)
                # Show "3810.T — Cyberstep Inc." as the checkbox label.
                label = f"{symbol} — {name}" if name != symbol else symbol
                if st.checkbox(label, key=f"sidebar_{symbol}"):
                    selected.append(symbol)
            st.divider()

        if selected:
            st.caption(f"{len(selected)} selected")

    return selected
