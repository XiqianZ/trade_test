"""Diagnostic tests for yfinance download capability.

Run with:
    .venv/bin/python tests/test_downloader.py
"""

import json
import sys
import traceback
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

import data.cache as cache_mod

SYMBOL = "AAPL"

# (label, kwargs) — all should succeed if yfinance is working
CASES = [
    ("daily  | 1 year  | period shorthand", dict(period="1y", interval="1d")),
    ("daily  | 30 days | explicit dates",   dict(
        start=str(date.today() - timedelta(days=30)),
        end=str(date.today()),
        interval="1d",
    )),
    ("1h     | 60 days | explicit dates",   dict(
        start=str(date.today() - timedelta(days=60)),
        end=str(date.today()),
        interval="1h",
    )),
    ("5m     | 30 days | explicit dates",   dict(
        start=str(date.today() - timedelta(days=30)),
        end=str(date.today()),
        interval="5m",
    )),
    ("5m     | 7 days  | period shorthand", dict(period="5d", interval="5m")),
    ("1m     | 7 days  | period shorthand", dict(period="5d", interval="1m")),
]


def run_case(label: str, kwargs: dict) -> bool:
    ticker = yf.Ticker(SYMBOL)
    try:
        df = ticker.history(**kwargs, auto_adjust=True)
        if df.empty:
            print(f"  FAIL  {label}")
            print(f"        → empty DataFrame (kwargs={kwargs})")
            return False
        print(f"  OK    {label}")
        print(f"        → {len(df)} rows  {df.index[0].date()} … {df.index[-1].date()}")
        return True
    except Exception:
        print(f"  ERROR {label}")
        traceback.print_exc()
        return False


def main() -> None:
    print(f"yfinance {yf.__version__}  |  Python {sys.version.split()[0]}\n")
    results = [run_case(label, kwargs) for label, kwargs in CASES]
    passed = sum(results)
    print(f"\n{passed}/{len(results)} cases passed")
    sys.exit(0 if passed == len(results) else 1)


def test_cached_download_reloads_full_history_after_split(monkeypatch, tmp_path):
    symbol = "TEST"
    interval = "1d"
    cache_dir = tmp_path / "cache"
    cache_mod.CACHE_DIR = cache_dir

    cached = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [110.0],
            "Low": [95.0],
            "Close": [105.0],
            "Volume": [1000],
        },
        index=[pd.Timestamp("2024-01-01")],
    )
    cache_mod.save_cache(cached, symbol, interval)
    cache_mod.save_sync_metadata(symbol, interval, "2024-01-01")

    full_history = pd.DataFrame(
        {
            "Open": [50.0],
            "High": [60.0],
            "Low": [45.0],
            "Close": [55.0],
            "Volume": [2000],
        },
        index=[pd.Timestamp("2024-02-01")],
    )
    calls = []

    def fake_full_download(sym: str, interval: str = "1d"):
        calls.append((sym, interval))
        cache_mod.save_cache(full_history, sym, interval)
        cache_mod.save_sync_metadata(sym, interval, "2024-02-15")
        return full_history

    class FakeTicker:
        splits = pd.Series([2.0], index=[pd.Timestamp("2024-02-10")])

    monkeypatch.setattr(cache_mod, "download_ticker_full_history", fake_full_download)
    monkeypatch.setattr(yf, "Ticker", lambda _symbol: FakeTicker())

    result = cache_mod.cached_download_ticker(symbol, "2024-02-01", "2024-02-02", interval=interval)

    assert result.equals(full_history)
    assert calls == [(symbol, interval)]
    metadata = json.loads((cache_mod._metadata_path(symbol, interval)).read_text())
    assert metadata["last_sync"] == "2024-02-15"


if __name__ == "__main__":
    main()
