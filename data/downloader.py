import yfinance as yf
import pandas as pd
from datetime import date, timedelta

# yfinance maximum lookback in days per interval
MAX_LOOKBACK_DAYS: dict[str, int] = {
    "1m": 7,
    "2m": 60,
    "5m": 60,
    "15m": 60,
    "30m": 60,
    "60m": 60,
    "1h": 60,
    "90m": 60,
}


def _validate_range(start: str, end: str, interval: str) -> None:
    max_days = MAX_LOOKBACK_DAYS.get(interval)
    if max_days is None:
        return
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    if (end_date - start_date).days > max_days:
        raise ValueError(
            f"Interval '{interval}' only supports up to {max_days} days of history. "
            f"Requested range is {(end_date - start_date).days} days. "
            f"Set start to {end_date - timedelta(days=max_days)} or earlier."
        )


def download_ticker(
    symbol: str,
    start: str,
    end: str,
    interval: str = "1d",
) -> pd.DataFrame:
    """Download OHLCV data for a single ticker.

    Args:
        symbol: Ticker symbol, e.g. "AAPL".
        start: Start date string "YYYY-MM-DD".
        end: End date string "YYYY-MM-DD".
        interval: Bar interval — "1m","5m","1h","1d","1wk","1mo", etc.

    Returns:
        DataFrame with columns [Open, High, Low, Close, Volume] indexed by datetime.
    """
    _validate_range(start, end, interval)
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end, interval=interval, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data returned for {symbol!r} ({start} → {end}, interval={interval})")
    df.index = df.index.tz_localize(None) if df.index.tzinfo is not None else df.index
    return df[["Open", "High", "Low", "Close", "Volume"]]


def download_tickers(
    symbols: list[str],
    start: str,
    end: str,
    interval: str = "1d",
) -> dict[str, pd.DataFrame]:
    """Download OHLCV data for multiple tickers.

    Returns a dict mapping each symbol to its DataFrame.
    Symbols that return no data are skipped with a warning.
    """
    result: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        try:
            result[symbol] = download_ticker(symbol, start=start, end=end, interval=interval)
        except ValueError as exc:
            print(f"[downloader] warning: {exc}")
    return result
