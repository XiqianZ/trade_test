from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd
from strategy.universe import Universe
from strategy.base import Strategy
from strategy.fees import FeeModel, fee_model_for


@dataclass
class BacktestResult:
    """Holds the raw output of a single backtest run.

    Attributes:
        strategy_name: Name of the strategy that was run.
        universe:      The Universe the strategy was run on.
        signals:       Dict of signal Series per symbol.
        returns:       Dict of net return Series (after fees) per symbol.
        fees_paid:     Dict of fee-cost Series per symbol (inspect to see
                       how much each trade cost).
    """

    strategy_name: str
    universe: Universe
    signals: dict[str, pd.Series]
    returns: dict[str, pd.Series]
    fees_paid: dict[str, pd.Series] = field(default_factory=dict)

    def equity_curve(self, symbol: str) -> pd.Series:
        """Cumulative growth of $1 invested, for a single symbol."""
        return (1 + self.returns[symbol]).cumprod()

    def combined_equity_curve(self) -> pd.Series:
        """Equal-weighted portfolio equity curve across all symbols."""
        portfolio_return = pd.DataFrame(self.returns).mean(axis=1)
        return (1 + portfolio_return).cumprod()

    def summary(self) -> pd.DataFrame:
        """One-row-per-symbol table: total return, trade count, total fees paid."""
        rows = []
        for symbol, ret in self.returns.items():
            total_return = (1 + ret).prod() - 1
            signal = self.signals[symbol]
            num_trades = int((signal.diff().fillna(0) != 0).sum())
            total_fees = float(self.fees_paid.get(symbol, pd.Series(0.0)).sum())
            rows.append({
                "Symbol": symbol,
                "Total Return": f"{total_return:.2%}",
                "Num Trades": num_trades,
                "Total Fees": f"{total_fees:.4%}",
            })
        return pd.DataFrame(rows).set_index("Symbol")


class Backtest:
    """Runs a Strategy on a Universe and produces a BacktestResult.

    Execution model:
      - Signal on bar N is acted on at the open of bar N+1 (no look-ahead bias).
      - Returns are close-to-close percentage changes.
      - Fees are charged on every bar where the position changes.

    Args:
        strategy:   The Strategy to run.
        universe:   The Universe to run it on.
        fee_models: Optional override dict mapping symbol → FeeModel.
                    Symbols not in this dict fall back to fee_model_for(symbol).
    """

    def __init__(
        self,
        strategy: Strategy,
        universe: Universe,
        fee_models: dict[str, FeeModel] | None = None,
    ) -> None:
        self.strategy = strategy
        self.universe = universe
        self._fee_overrides = fee_models or {}

    def _fee_model(self, symbol: str) -> FeeModel:
        return self._fee_overrides.get(symbol) or fee_model_for(symbol)

    def run(self) -> BacktestResult:
        signals = self.strategy.generate_signals(self.universe)
        returns: dict[str, pd.Series] = {}
        fees_paid: dict[str, pd.Series] = {}

        for symbol, df in self.universe.data.items():
            if symbol not in signals:
                continue

            fee_model = self._fee_model(symbol)

            # Shift signal by 1 bar so today's signal executes at tomorrow's open.
            position = signals[symbol].shift(1).fillna(0)

            # |Δposition| on each bar — non-zero only when a trade fires.
            position_delta = position.diff().fillna(position).abs()

            # Fee cost per bar (fraction of notional traded).
            fee_cost = position_delta.apply(fee_model.cost)

            price_return = df["Close"].pct_change().fillna(0)

            # Net return = gross return minus fee cost.
            returns[symbol] = position * price_return - fee_cost
            fees_paid[symbol] = fee_cost

        return BacktestResult(
            strategy_name=self.strategy.name,
            universe=self.universe,
            signals=signals,
            returns=returns,
            fees_paid=fees_paid,
        )
