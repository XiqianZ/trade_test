import streamlit as st
from data import cache as data_cache
from ui import render_downloader_form
from ui.strategy_form import render_universe_form

st.title("Trade Test")

tab_download, tab_strategy = st.tabs(["Download Data", "Strategy"])

with tab_download:
    results = render_downloader_form()

with tab_strategy:
    universe = render_universe_form()

list_split_events = getattr(data_cache, "list_split_events", None)
split_events = list_split_events() if callable(list_split_events) else []
if not isinstance(split_events, list):
    split_events = []
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
