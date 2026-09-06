import streamlit as st
from data.cache import list_split_events
from ui import render_downloader_form
from ui.strategy_form import render_universe_form
from ui.sidebar import render_sidebar

st.title("Trade Test")

selected_symbols = render_sidebar()

tab_download, tab_strategy = st.tabs(["Download Data", "Strategy"])

with tab_download:
    results = render_downloader_form()

with tab_strategy:
    universe = render_universe_form()

split_events = list_split_events()
if split_events:
    st.markdown("### Split Events")
    for event in split_events:
        st.info(f"{event['symbol']} — {event['date']} — {event['ratio']}x split ({event['interval']})")

if __name__ == "__main__":
    import os, subprocess, sys
    if not os.environ.get("_IN_STREAMLIT"):
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", __file__] + sys.argv[1:],
            env={**os.environ, "_IN_STREAMLIT": "1"},
        )
