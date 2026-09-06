"""Resolve ticker symbols to human-readable company names.

Names are fetched once from yfinance and persisted to a local JSON file
(data/cache/ticker_names.json) so future runs never need a network call
for a symbol we already know.
"""

from __future__ import annotations
import json
from pathlib import Path
import yfinance as yf
from data.cache import CACHE_DIR

_NAMES_FILE = CACHE_DIR / "ticker_names.json"


def _load_name_store() -> dict[str, str]:
    if _NAMES_FILE.exists():
        return json.loads(_NAMES_FILE.read_text(encoding="utf-8"))
    return {}


def _save_name_store(store: dict[str, str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _NAMES_FILE.write_text(
        json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _fetch_name(symbol: str) -> str:
    """Ask yfinance for the company name.  Returns the symbol itself on failure."""
    try:
        info = yf.Ticker(symbol).info
        # yfinance may return "longName", "shortName", or neither.
        return info.get("longName") or info.get("shortName") or symbol
    except Exception:
        return symbol


def get_ticker_name(symbol: str) -> str:
    """Return the display name for a symbol, fetching it if not yet cached."""
    store = _load_name_store()
    if symbol not in store:
        store[symbol] = _fetch_name(symbol)
        _save_name_store(store)
    return store[symbol]


def get_ticker_names(symbols: list[str]) -> dict[str, str]:
    """Return a display-name mapping for a batch of symbols.

    Only symbols not already in the local JSON are fetched from yfinance,
    then the full store is written once at the end.
    """
    store = _load_name_store()
    missing = [s for s in symbols if s not in store]
    for symbol in missing:
        store[symbol] = _fetch_name(symbol)
    if missing:
        _save_name_store(store)
    return {s: store[s] for s in symbols}
