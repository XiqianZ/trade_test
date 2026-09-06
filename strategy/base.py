from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd
from strategy.universe import Universe


class Strategy(ABC):
    """Abstract base class for all trading strategies.

    To create a strategy, subclass this and implement `generate_signals`.

    Example:
        class BuyAndHold(Strategy):
            name = "Buy and Hold"

            def generate_signals(self, universe):
                # Always long every symbol — signal of 1 the whole time.
                return {
                    symbol: pd.Series(1, index=df.index)
                    for symbol, df in universe.data.items()
                }

    Signal convention:
        +1  → long (hold / buy)
         0  → flat (no position)
        -1  → short (sell / short-sell)
    """

    #: Human-readable name shown in the UI — override in subclasses.
    name: str = "Unnamed Strategy"

    @abstractmethod
    def generate_signals(self, universe: Universe) -> dict[str, pd.Series]:
        """Compute a signal series for every symbol in the universe.

        Args:
            universe: The loaded Universe to compute signals for.

        Returns:
            Dict mapping each symbol to a Series of {-1, 0, 1} indexed by
            the same DatetimeIndex as the symbol's OHLCV data.
        """
        ...

    def run(self, universe: Universe) -> BacktestResult:
        """Convenience method: generate signals then hand off to Backtest.

        Imported lazily to avoid a circular import (Backtest imports Strategy).
        """
        from strategy.backtest import Backtest
        return Backtest(strategy=self, universe=universe).run()
