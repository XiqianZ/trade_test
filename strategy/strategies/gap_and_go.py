"""Gap and Go strategy.

Logic (per symbol, per day)
---------------------------
At the close of day D, two limit orders are placed for day D+1:

  sell_price = close[D] * (1 + sell_pct)   ← short-entry trigger
  buy_price  = sell_price * (1 - buy_pct)  ← cover trigger

On day D+1 the intraday high/low are checked:

  Case 1 — high[D+1] >= sell_price AND low[D+1] <= buy_price
      Same-day round trip: sold at sell_price, covered at buy_price.
      Return = (sell_price - buy_price) / close[D]

  Case 2 — high[D+1] >= sell_price only
      Entered short at sell_price, not yet covered.
      Held short: mark-to-market return = (sell_price / close[D+1]) - 1

  Case 3 — neither threshold hit
      No trade.  Return = 0.

  Case 4 — already in a short from a previous day:
      If low[D+1] <= buy_price: covered at buy_price.
          Return = (entry_price / buy_price) - 1
      Else: still short, mark-to-market return = -(close[D+1] / close[D] - 1)

Why we override run() instead of relying on the standard Backtest
------------------------------------------------------------------
The standard Backtest computes returns as  position × close_to_close_return,
which does not capture intraday entry/exit prices.  For this strategy the
entry and exit prices are known (sell_price, buy_price), so we compute
exact trade P&L here and hand the result directly to BacktestResult.
"""

from __future__ import annotations
import pandas as pd
from strategy.base import Strategy
from strategy.universe import Universe
from strategy.backtest import BacktestResult
from strategy.fees import fee_model_for


class GapAndGo(Strategy):
    """Short-sell into a gap-up, cover on the pull-back.

    Args:
        sell_pct: How far above yesterday's close the sell (short entry) trigger
                  sits, as a fraction.  E.g. 0.02 = 2%.  Must be in [0.01, 0.03].
        buy_pct:  How far below the sell price the cover (buy) trigger sits,
                  as a fraction.  E.g. 0.02 = 2%.  Must be in [0.01, 0.03].
    """

    name = "Gap and Go"

    def __init__(self, sell_pct: float = 0.02, buy_pct: float = 0.02) -> None:
        if not (0.01 <= sell_pct <= 0.03):
            raise ValueError(f"sell_pct must be between 1% and 3%, got {sell_pct:.1%}")
        if not (0.01 <= buy_pct <= 0.03):
            raise ValueError(f"buy_pct must be between 1% and 3%, got {buy_pct:.1%}")
        self.sell_pct = sell_pct
        self.buy_pct = buy_pct

    # ------------------------------------------------------------------
    # Core signal + return computation
    # ------------------------------------------------------------------

    def generate_signals(self, universe: Universe) -> dict[str, pd.Series]:
        """Return signal series only (used when plugged into a generic Backtest)."""
        return {
            symbol: self._signals_and_returns(df)[0]
            for symbol, df in universe.data.items()
        }

    def run(self, universe: Universe) -> BacktestResult:
        """Override: compute exact entry/exit returns instead of position × pct_change."""
        all_signals: dict[str, pd.Series] = {}
        all_returns: dict[str, pd.Series] = {}
        all_fees:    dict[str, pd.Series] = {}

        for symbol, df in universe.data.items():
            signals, returns, fees_series = self._signals_and_returns(
                df, fee_model=fee_model_for(symbol)
            )
            all_signals[symbol] = signals
            all_returns[symbol] = returns
            all_fees[symbol]    = fees_series

        return BacktestResult(
            strategy_name=self.name,
            universe=universe,
            signals=all_signals,
            returns=all_returns,
            fees_paid=all_fees,
        )

    # ------------------------------------------------------------------
    # Per-symbol state machine
    # ------------------------------------------------------------------

    def _signals_and_returns(
        self,
        df: pd.DataFrame,
        fee_model=None,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Walk through each bar with a state machine.

        Returns:
            signal:   Series of {-1, 0}
            returns:  Series of net returns per bar
            fees:     Series of fee costs per bar
        """
        from strategy.fees import ZeroFee
        if fee_model is None:
            fee_model = ZeroFee()

        close = df["Close"]
        high  = df["High"]
        low   = df["Low"]

        # Targets are set from the *previous* day's close.
        sell_price = close.shift(1) * (1 + self.sell_pct)
        buy_price  = sell_price     * (1 - self.buy_pct)

        n = len(df)
        signal_arr  = [0.0] * n
        return_arr  = [0.0] * n
        fee_arr     = [0.0] * n

        in_short    = False
        entry_price = 0.0   # price at which we sold short

        for i in range(n):
            sp = sell_price.iloc[i]
            bp = buy_price.iloc[i]
            hi = high.iloc[i]
            lo = low.iloc[i]
            cl = close.iloc[i]
            prev_cl = close.iloc[i - 1] if i > 0 else cl

            if in_short:
                if lo <= bp:
                    # ── Cover the short at buy_price ──────────────────────
                    # Short return = how much the price fell from entry.
                    # Expressed as a fraction of the entry price.
                    gross = (entry_price - bp) / entry_price
                    fee   = fee_model.cost(1)          # closing a position = Δpos of 1
                    return_arr[i] = gross - fee
                    fee_arr[i]    = fee
                    signal_arr[i] = 0
                    in_short      = False
                else:
                    # ── Still short, mark to market ───────────────────────
                    # Daily short return = -(today's close / yesterday's close - 1)
                    mtm           = -(cl / prev_cl - 1)
                    return_arr[i] = mtm
                    signal_arr[i] = -1

            else:
                if hi >= sp:
                    # ── Sell (enter short) at sell_price ─────────────────
                    entry_price = sp
                    open_fee    = fee_model.cost(1)    # opening a position

                    if lo <= bp:
                        # Same-day round trip: sold at sell_price, covered at buy_price.
                        gross         = (sp - bp) / sp
                        close_fee     = fee_model.cost(1)
                        total_fee     = open_fee + close_fee
                        return_arr[i] = gross - total_fee
                        fee_arr[i]    = total_fee
                        signal_arr[i] = 0
                        # in_short stays False
                    else:
                        # Entered short, not yet covered.
                        # Mark-to-market from entry to today's close.
                        mtm           = (sp - cl) / sp
                        return_arr[i] = mtm - open_fee
                        fee_arr[i]    = open_fee
                        signal_arr[i] = -1
                        in_short      = True
                # else: no trade, all arrays stay 0

        index = df.index
        return (
            pd.Series(signal_arr, index=index, dtype=float),
            pd.Series(return_arr, index=index, dtype=float),
            pd.Series(fee_arr,    index=index, dtype=float),
        )
