from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd
from data import cached_download_ticker


@dataclass
class Universe:
    """A snapshot of market data for a fixed set of symbols and time window.

    Think of it as the "table of ingredients" that every strategy reads from.
    It is intentionally read-only after construction — strategies must never
    modify the underlying DataFrames so that the same Universe can be reused
    across multiple strategy runs.

    Attributes:
        symbols:  Ordered list of ticker symbols that were requested.
        start:    ISO date string for the start of the window (inclusive).
        end:      ISO date string for the end of the window (exclusive).
        interval: Bar size, e.g. "1d", "1h".
        data:     Maps each symbol that loaded successfully to its OHLCV DataFrame.
        failed:   Symbols that could not be loaded (network error, bad ticker, etc.).
    """

    symbols: list[str]
    start: str
    end: str
    interval: str
    data: dict[str, pd.DataFrame] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def load(
        cls,
        symbols: list[str],
        start: str,
        end: str,
        interval: str = "1d",
        progress_callback=None,
    ) -> Universe:
        """Download (or cache-hit) data for every symbol and return a Universe.

        Args:
            symbols:           List of ticker strings, e.g. ["AAPL", "TSLA"].
            start:             Start date "YYYY-MM-DD".
            end:               End date "YYYY-MM-DD".
            interval:          Bar interval.
            progress_callback: Optional callable(symbol, ok, total) called after
                               each symbol so the UI can update a progress bar.
        """
        universe = cls(symbols=symbols, start=start, end=end, interval=interval)

        for i, symbol in enumerate(symbols, 1):
            try:
                universe.data[symbol] = cached_download_ticker(
                    symbol, start=start, end=end, interval=interval
                )
            except ValueError as exc:
                universe.failed.append(symbol)
                print(f"[universe] skipped {symbol}: {exc}")

            if progress_callback is not None:
                progress_callback(symbol, symbol not in universe.failed, len(symbols))

        return universe

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def loaded_symbols(self) -> list[str]:
        """Symbols that loaded successfully."""
        return list(self.data.keys())

    def close(self) -> pd.DataFrame:
        """Return a DataFrame of closing prices with symbols as columns.

        This is the most common view strategies need — one column per ticker,
        one row per timestamp.

            AAPL    TSLA
        2024-01-02  185.2   248.4
        2024-01-03  184.1   ...
        """
        return pd.DataFrame(
            {symbol: df["Close"] for symbol, df in self.data.items()}
        )

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        return (
            f"Universe(symbols={self.loaded_symbols}, "
            f"start={self.start!r}, end={self.end!r}, interval={self.interval!r})"
        )
