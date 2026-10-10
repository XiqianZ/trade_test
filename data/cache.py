import json
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

from .downloader import download_ticker, download_ticker_full_history

# Root folder where all cached files live.
# Path(__file__) is this file (cache.py), .parent is the data/ folder,
# so CACHE_DIR ends up at  data/cache/
CACHE_DIR = Path(__file__).parent / "cache"


def _metadata_path(symbol: str, interval: str) -> Path:
    """Return the metadata file path for a symbol+interval cache."""
    folder = CACHE_DIR / symbol.upper()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{interval}.meta.json"


def _parquet_path(symbol: str, interval: str) -> Path:
    """Return the Parquet file path for a given symbol + interval.

    Example: _parquet_path("AAPL", "1d") -> data/cache/AAPL/1d.parquet
    Each symbol gets its own sub-folder so the cache stays tidy.
    """
    folder = CACHE_DIR / symbol.upper()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{interval}.parquet"


def load_cache(symbol: str, interval: str) -> pd.DataFrame | None:
    """Load the full cached DataFrame for a symbol+interval, or None if not cached yet."""
    path = _parquet_path(symbol, interval)
    if not path.exists():
        return None
    return pd.read_parquet(path)


def has_cache(symbol: str, interval: str) -> bool:
    """Return True when a cache parquet exists for symbol+interval.

    This avoids reading large parquet files when callers only need to know
    whether a cache entry exists.
    """
    return _parquet_path(symbol, interval).exists()


def has_current_cache(symbol: str, interval: str) -> bool:
    """Return True when cached data was successfully synchronized today."""
    path = _parquet_path(symbol, interval)
    if not path.exists():
        return False

    last_sync = load_sync_metadata(symbol, interval)
    if last_sync is None:
        return False

    try:
        sync_date = pd.Timestamp(last_sync).date()
    except (TypeError, ValueError):
        return False

    return sync_date >= pd.Timestamp.now().date()


def load_ticker_name_symbols() -> list[str]:
    """Load the symbol list from data/cache/ticker_names.json, if present."""
    path = CACHE_DIR / "ticker_names.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if isinstance(payload, dict):
        symbols = payload.keys()
    elif isinstance(payload, list):
        symbols = payload
    else:
        return []

    return sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})


def list_cached_symbols() -> list[str]:
    """Return every symbol that has at least one Parquet file in the cache."""
    if not CACHE_DIR.exists():
        return []
    return sorted(
        folder.name
        for folder in CACHE_DIR.iterdir()
        if folder.is_dir() and any(folder.glob("*.parquet"))
    )


def load_sync_metadata(symbol: str, interval: str) -> str | None:
    """Return the last synchronized date for a symbol+interval, if known."""
    path = _metadata_path(symbol, interval)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    last_sync = payload.get("last_sync")
    if not last_sync:
        return None
    return str(pd.Timestamp(last_sync).date())


def save_sync_metadata(symbol: str, interval: str, last_sync: str | pd.Timestamp) -> None:
    """Persist the last synced date for this symbol+interval."""
    path = _metadata_path(symbol, interval)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"last_sync": str(pd.Timestamp(last_sync).date())}
    path.write_text(json.dumps(payload), encoding="utf-8")


def save_cache(df: pd.DataFrame, symbol: str, interval: str) -> None:
    """Persist a DataFrame to its Parquet file, replacing whatever was there."""
    path = _parquet_path(symbol, interval)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    if not df.empty:
        save_sync_metadata(symbol, interval, pd.Timestamp.now())


def _split_occurred_since(symbol: str, last_sync: str | None) -> bool:
    """Return True when a stock split occurred after the last sync date."""
    if last_sync is None:
        return False
    try:
        ticker = yf.Ticker(symbol)
        splits = getattr(ticker, "splits", None)
        if splits is None or len(splits) == 0:
            return False
        split_dates = pd.DatetimeIndex(pd.to_datetime(splits.index))
        return bool((split_dates > pd.Timestamp(last_sync)).any())
    except Exception:
        return False


def missing_range(
    cached: pd.DataFrame,
    start: str,
    end: str,
) -> tuple[str, str] | None:
    """Given a cached DataFrame and a requested [start, end) range, return
    the sub-range that is NOT yet in the cache, or None if fully covered.

    We only handle the case where the missing data is a prefix of the
    requested range (i.e. the user is asking further back than we have).
    Appending new dates at the end is handled separately by always
    re-fetching from the last cached date onward.
    """
    # The index is a DatetimeIndex — .min() and .max() give us the coverage.
    cached_start = cached.index.min().date()
    cached_end = cached.index.max().date()

    req_start = pd.Timestamp(start).date()
    req_end = pd.Timestamp(end).date()

    # Cache already covers the full requested range.
    if cached_start <= req_start and cached_end >= req_end:
        return None

    # Need data before what we have (backfill gap).
    if req_start < cached_start:
        return (start, str(cached_start))

    # Need data after what we have (forward gap) — fetch from last cached date.
    if req_end > cached_end:
        return (str(cached_end), end)

    return None


def cached_download_ticker(
    symbol: str,
    start: str,
    end: str,
    interval: str = "1d",
) -> pd.DataFrame:
    """Download OHLCV data, using a local Parquet cache to avoid redundant requests.

    Flow:
      1. Load whatever we already have for this symbol+interval.
      2. Compute what date range is still missing.
      3. Download only the missing slice (or everything if cache is empty).
      4. Merge new data into the cache and persist it.
      5. Return only the rows within [start, end].
    """
    cached = load_cache(symbol, interval)
    last_sync = load_sync_metadata(symbol, interval)

    if cached is not None and _split_occurred_since(symbol, last_sync):
        full_history = download_ticker_full_history(symbol, interval=interval)
        return full_history.loc[start:end]

    if cached is None:
        # Cold start — nothing cached yet, download the full range.
        fresh = download_ticker(symbol, start=start, end=end, interval=interval)
        save_cache(fresh, symbol, interval)
        return fresh

    gap = missing_range(cached, start, end)

    if gap is None:
        # Cache fully covers the request — slice and return, no network call.
        return cached.loc[start:end]

    # Download only the missing slice, then merge with the cache.
    gap_start, gap_end = gap
    fresh = download_ticker(symbol, start=gap_start, end=gap_end, interval=interval)

    # pd.concat stacks the two DataFrames, sort_index orders by datetime,
    # and ~duplicated removes any overlapping rows at the seam.
    merged = pd.concat([cached, fresh])
    merged = merged.sort_index()
    merged = merged[~merged.index.duplicated(keep="last")]

    save_cache(merged, symbol, interval)
    return merged.loc[start:end]


def cached_download_ticker_full_history(
    symbol: str,
    interval: str = "1d",
    overwrite: bool = False,
) -> pd.DataFrame:
    """Download and cache the maximum history for one symbol.

    If the Parquet cache already exists and overwrite is False, the cached
    data is returned immediately without hitting yfinance.
    """
    cached = None if overwrite else load_cache(symbol, interval)
    if cached is not None:
        return cached

    fresh = download_ticker_full_history(symbol, interval=interval)
    save_cache(fresh, symbol, interval)
    return fresh


def cached_download_ticker_full_history_batch(
    symbols: list[str] | None = None,
    interval: str = "1d",
    pause_seconds: float = 1.5,
    overwrite: bool = False,
) -> dict[str, pd.DataFrame]:
    """Download full history for many symbols with throttling.

    When symbols is None, the list is loaded from data/cache/ticker_names.json.
    The pause between requests keeps the request rate low enough to reduce the
    chance of yfinance throttling or temporary blocking.
    """
    targets = symbols if symbols is not None else load_ticker_name_symbols()
    result: dict[str, pd.DataFrame] = {}

    for index, symbol in enumerate(targets, 1):
        result[symbol] = cached_download_ticker_full_history(
            symbol,
            interval=interval,
            overwrite=overwrite,
        )
        if pause_seconds > 0 and index < len(targets):
            time.sleep(pause_seconds)

    return result
