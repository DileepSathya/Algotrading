from typing import Any

import pandas as pd

from engines.trade_engine import TradeEngine
from engines.exit_engine import ExitEngine
from engines.position_sizing_engine import PositionSizingEngine
from .models import BacktestResult


class BacktestEngine:
    """Shared chronological backtest orchestrator for daily and intraday strategies."""

    def __init__(self, strategy: Any, trade_engine: TradeEngine, exit_engine: ExitEngine,
                 position_sizing_engine: PositionSizingEngine | None = None,
                 transaction_cost_model=None):
        self.strategy = strategy
        self.trade_engine = trade_engine
        self.exit_engine = exit_engine
        self.position_sizing_engine = position_sizing_engine
        self.transaction_cost_model = transaction_cost_model or (lambda trade, exit_price: 0.0)
        self.completed_trades = []

    def run(self, df: pd.DataFrame) -> BacktestResult:
        self.completed_trades = []
        self.trade_engine.reset()
        if self.position_sizing_engine is not None:
            self.position_sizing_engine.reset()
        if df.empty:
            return BacktestResult(self._empty_trades_dataframe())

        data = self.strategy.prepare_data(self.exit_engine.prepare_data(df))
        intraday = bool(getattr(self.strategy, "intraday", False))
        clock_column = "timestamp" if intraday and "timestamp" in data else "date"
        data[clock_column] = pd.to_datetime(data[clock_column])
        data = data.sort_values([clock_column, "symbol"], kind="stable").reset_index(drop=True)
        last_rows = data.groupby("symbol", sort=False).tail(1).set_index("symbol")

        final_intraday_timestamps = {}
        stop_losses_by_day = {}
        stop_losses_by_symbol_day = {}
        daily_stop_limit = getattr(self.strategy, "max_stop_losses_per_day", None)
        symbol_stop_limit = getattr(self.strategy, "max_stop_losses_per_symbol_per_day", None)
        if intraday:
            trading_days = data[clock_column].dt.normalize()
            final_intraday_timestamps = (
                data.assign(_trading_day=trading_days)
                .groupby(["_trading_day", "symbol"])[clock_column]
                .max().to_dict()
            )
        for timestamp, candles in data.groupby(clock_column, sort=True):
            trading_day = pd.Timestamp(timestamp).normalize()
            candles = candles.sort_values("symbol", kind="stable")

            active_at_start = set(self.trade_engine.get_active_trades())
            for _, row in candles.iterrows():
                symbol = str(row["symbol"])
                if symbol in active_at_start:
                    closed_trade = self._check_exit(symbol, row)
                    if closed_trade is not None and closed_trade.exit_reason == "SL":
                        stop_losses_by_day[trading_day] = stop_losses_by_day.get(trading_day, 0) + 1
                        key = (trading_day, symbol)
                        stop_losses_by_symbol_day[key] = stop_losses_by_symbol_day.get(key, 0) + 1

            for _, row in candles.iterrows():
                symbol = str(row["symbol"])
                if symbol in active_at_start or self.trade_engine.has_active_trade(symbol):
                    continue
                if daily_stop_limit is not None and stop_losses_by_day.get(trading_day, 0) >= daily_stop_limit:
                    continue
                if symbol_stop_limit is not None and stop_losses_by_symbol_day.get((trading_day, symbol), 0) >= symbol_stop_limit:
                    continue
                signal = self.strategy.generate_signal(row)
                if signal is None:
                    continue
                direction = getattr(signal, "direction", "LONG")
                risk_per_unit = getattr(signal, "risk_per_unit", None)
                risk_fraction = getattr(signal, "risk_fraction", None)
                metadata = getattr(signal, "metadata", None)
                equity_before = None
                if self.position_sizing_engine is not None:
                    position = self.position_sizing_engine.size_position(
                        signal.symbol, signal.entry_price, direction=direction,
                        risk_per_unit=risk_per_unit, risk_fraction=risk_fraction)
                    if position is None:
                        continue
                    quantity = position.quantity
                    capital_allocated = position.allocated_capital
                    equity_before = position.equity_before
                else:
                    quantity = 1
                    capital_allocated = signal.entry_price
                self.trade_engine.open_trade(
                    symbol=signal.symbol, entry_date=signal.entry_date,
                    entry_price=signal.entry_price, sl=signal.sl, target=signal.target,
                    quantity=quantity, capital_allocated=capital_allocated,
                    direction=direction, metadata=metadata, equity_before=equity_before)

            if not intraday:
                for symbol, row in candles.set_index("symbol").iterrows():
                    symbol = str(symbol)
                    if (self.trade_engine.has_active_trade(symbol)
                            and pd.Timestamp(last_rows.loc[symbol, clock_column]) == pd.Timestamp(timestamp)):
                        self._close_trade(symbol, timestamp, float(row["close"]), "END_OF_BACKTEST")
            else:
                for _, row in candles.iterrows():
                    symbol = str(row["symbol"])
                    if (self.trade_engine.has_active_trade(symbol)
                            and pd.Timestamp(final_intraday_timestamps[(trading_day, symbol)]) == pd.Timestamp(timestamp)):
                        self._close_trade(symbol, timestamp, float(row["close"]), "END_OF_DAY")

        return BacktestResult(self._build_trades_dataframe())

    def _check_exit(self, symbol, row):
        trade = self.trade_engine.get_active_trade(symbol)
        if trade is None:
            return
        result = self.exit_engine.check(row, trade.entry_price, trade.sl, trade.target,
                                        direction=trade.direction)
        if result is not None:
            exit_date = row.get("timestamp", row["date"])
            return self._close_trade(symbol, exit_date, result.exit_price, result.exit_reason)
        return None

    def _close_trade(self, symbol, exit_date, exit_price, exit_reason):
        active_trade = self.trade_engine.get_active_trade(symbol)
        active_trade.transaction_cost = float(self.transaction_cost_model(active_trade, exit_price))
        if active_trade.transaction_cost < 0:
            raise ValueError("Transaction cost cannot be negative.")
        trade = self.trade_engine.close_trade(symbol, exit_date, exit_price, exit_reason)
        if self.position_sizing_engine is not None:
            self.position_sizing_engine.close_position(symbol, exit_price,
                                                       transaction_cost=trade.transaction_cost)
            trade.equity_after = self.position_sizing_engine.current_equity
        elif trade.equity_before is not None:
            trade.equity_after = trade.equity_before + trade.pnl
        if "entry_timestamp" in trade.metadata:
            trade.metadata["exit_timestamp"] = pd.Timestamp(exit_date)
        self.completed_trades.append(trade.to_dict())
        return trade

    def _build_trades_dataframe(self):
        if not self.completed_trades:
            return self._empty_trades_dataframe()
        trades = pd.DataFrame(self.completed_trades)
        trades["entry_date"] = pd.to_datetime(trades["entry_date"])
        trades["exit_date"] = pd.to_datetime(trades["exit_date"])
        trades["holding_period"] = (trades["exit_date"] - trades["entry_date"]).dt.days
        preferred = ["symbol", "trading_date", "direction", "orb_high", "orb_low", "orb_range",
                     "entry_timestamp", "entry_date", "entry", "sl", "target", "quantity",
                     "capital_allocated", "exit_timestamp", "exit_date", "exit_price", "exit_reason",
                     "equity_before", "equity_after", "gross_pnl", "transaction_cost", "pnl",
                     "pnl_percent", "holding_period", "is_closed"]
        return trades[[c for c in preferred if c in trades] + [c for c in trades if c not in preferred]]

    @staticmethod
    def _empty_trades_dataframe():
        return pd.DataFrame(columns=["symbol", "direction", "entry_date", "exit_date", "entry", "sl",
                                     "target", "quantity", "capital_allocated", "exit_price", "exit_reason",
                                     "gross_pnl", "transaction_cost", "pnl", "pnl_percent", "holding_period",
                                     "equity_before", "equity_after", "is_closed"])
