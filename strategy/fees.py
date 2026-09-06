"""Trading fee models.

Architecture
------------
FeeModel is the abstract base.  Subclass it and override `rate` to create
a concrete fee schedule.  `Backtest` calls `fee_model_for(symbol)` to pick
the right model for each ticker automatically.

Fee mechanics
-------------
In a signal-based backtest, the position at each bar is -1, 0, or 1.
A trade fires whenever the position changes.  The cost is:

    fee_cost[t] = rate × |position[t] - position[t-1]|

  - Hold (no change):      |Δ| = 0  →  cost = 0
  - Open / close:          |Δ| = 1  →  cost = rate × 1
  - Flip (long → short):   |Δ| = 2  →  cost = rate × 2

This cost is subtracted from the gross return on that bar:

    net_return[t] = position[t] × price_return[t] − fee_cost[t]

Adding a new market
-------------------
Register it in _MARKET_FEE_REGISTRY at the bottom of this file.
"""

from __future__ import annotations
from abc import ABC, abstractmethod


class FeeModel(ABC):
    """Abstract fee model.  Every subclass must declare a `rate`."""

    @property
    @abstractmethod
    def rate(self) -> float:
        """One-way fee as a fraction of trade value (e.g. 0.001 = 0.1%)."""
        ...

    def cost(self, position_delta: float) -> float:
        """Return the fee for a given change in position size.

        Args:
            position_delta: Absolute change in position (0, 1, or 2 in a
                            -1/0/+1 signal model).
        """
        return self.rate * abs(position_delta)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(rate={self.rate:.4%})"


# ---------------------------------------------------------------------------
# Concrete fee models
# ---------------------------------------------------------------------------

class ZeroFee(FeeModel):
    """No transaction costs — useful as a baseline or for testing."""

    @property
    def rate(self) -> float:
        return 0.0


class PercentageFee(FeeModel):
    """Flat percentage of the traded notional, charged each way.

    Example:
        PercentageFee(0.001)  →  0.1% per trade (buy costs 0.1%, sell costs 0.1%)
    """

    def __init__(self, rate: float) -> None:
        if rate < 0:
            raise ValueError(f"Fee rate must be >= 0, got {rate}")
        self._rate = rate

    @property
    def rate(self) -> float:
        return self._rate


# ---------------------------------------------------------------------------
# Market registry — maps symbol suffix → fee model
# ---------------------------------------------------------------------------
# All fees are ZeroFee for now.  To activate real fees later, replace the
# ZeroFee() instance with e.g. PercentageFee(0.001).

_MARKET_FEE_REGISTRY: dict[str, FeeModel] = {
    ".T":   ZeroFee(),   # Tokyo Stock Exchange
    ".L":   ZeroFee(),   # London Stock Exchange
    ".HK":  ZeroFee(),   # Hong Kong Stock Exchange
    ".SS":  ZeroFee(),   # Shanghai Stock Exchange
    ".SZ":  ZeroFee(),   # Shenzhen Stock Exchange
    "":     ZeroFee(),   # US markets (NYSE / NASDAQ — no suffix)
}

_DEFAULT_FEE = ZeroFee()


def fee_model_for(symbol: str) -> FeeModel:
    """Return the registered FeeModel for a given ticker symbol.

    Matching is done on the longest suffix that appears in the registry,
    so ".HK" is preferred over a hypothetical single-character key.

    Examples:
        fee_model_for("3810.T")  →  _MARKET_FEE_REGISTRY[".T"]   (ZeroFee)
        fee_model_for("AAPL")    →  _MARKET_FEE_REGISTRY[""]      (ZeroFee)
    """
    upper = symbol.upper()
    # Sort by length descending so longer suffixes match first.
    for suffix in sorted(_MARKET_FEE_REGISTRY, key=len, reverse=True):
        if suffix and upper.endswith(suffix):
            return _MARKET_FEE_REGISTRY[suffix]
    return _MARKET_FEE_REGISTRY.get("", _DEFAULT_FEE)
