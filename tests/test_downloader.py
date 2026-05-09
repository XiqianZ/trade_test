"""Diagnostic tests for yfinance download capability.

Run with:
    .venv/bin/python tests/test_downloader.py
"""

import sys
import traceback
from datetime import date, timedelta

import yfinance as yf

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


if __name__ == "__main__":
    main()
