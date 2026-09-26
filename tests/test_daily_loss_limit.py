import unittest

import pandas as pd

from Backtest.Strategies.strategy_3_ORB.strategy import ORBStrategy
from Backtest.Strategies.strategy_4_VWAP import VWAPStrategy
from Backtest.Strategies.strategy_4_VWAP.config import MAX_DAILY_LOSS_PCT
from Backtest.Strategies.strategy_3_ORB.models import ORBSignal
from Backtest.backtest_engine import BacktestEngine
from engines.exit_engine import ExitEngine, TimeExit
from engines.position_sizing_engine import PositionSizingEngine
from engines.trade_engine import TradeEngine


class DailyLossLimitStrategy:
    intraday = True
    allow_same_candle_reentry = True

    def __init__(self, max_daily_loss_pct, fixed_quantity=10):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.fixed_quantity = fixed_quantity

    def prepare_data(self, data):
        prepared = data.copy()
        prepared["timestamp"] = pd.to_datetime(prepared["date"] + " " + prepared["time"])
        prepared["date"] = prepared["timestamp"]
        return prepared

    def generate_signal(self, row):
        if not row["signal"]:
            return None
        return ORBSignal(
            row["symbol"],
            row["timestamp"],
            float(row["close"]),
            float(row.get("sl", 90)),
            float(row.get("target", 120)),
            str(row.get("direction", "LONG")),
            float(row.get("risk", 10)),
            0.005,
            {"entry_timestamp": row["timestamp"]},
        )


def candle(day, clock, symbol, close, signal=False, **extra):
    row = {
        "date": day,
        "time": clock,
        "symbol": symbol,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 100,
        "signal": signal,
    }
    row.update(extra)
    return row


class FixedQuantitySizing(PositionSizingEngine):
    """Sizing engine that opens a fixed share count for predictable daily P&L."""

    def __init__(self, initial_capital, max_open_positions, quantity):
        super().__init__(initial_capital, max_open_positions)
        self.fixed_quantity = int(quantity)

    def size_position(self, symbol, entry_price, direction="LONG", risk_per_unit=None, risk_fraction=None):
        if symbol in self.active_positions or not self.can_open_position():
            return None
        from engines.position_sizing_engine.models import Position

        actual_capital = self.fixed_quantity * float(entry_price)
        if self.available_capital < actual_capital:
            return None
        position = Position(
            symbol=str(symbol),
            entry_price=float(entry_price),
            quantity=self.fixed_quantity,
            allocated_capital=actual_capital,
            direction=str(direction).upper(),
            equity_before=self.current_equity,
        )
        self.active_positions[position.symbol] = position
        self.allocated_capital += actual_capital
        return position


def run(rows, *, initial_capital=10_000, max_daily_loss_pct=1.0, quantity=10, transaction_cost=0.0):
    strategy = DailyLossLimitStrategy(max_daily_loss_pct)
    sizing = FixedQuantitySizing(initial_capital, 4, quantity)
    cost_model = (lambda _trade, _exit: float(transaction_cost)) if transaction_cost else None
    engine = BacktestEngine(
        strategy,
        TradeEngine(),
        ExitEngine([TimeExit("09:35"), TimeExit("09:40"), TimeExit("09:45"), TimeExit("09:50")]),
        sizing,
        transaction_cost_model=cost_model,
    )
    return engine.run(pd.DataFrame(rows)).to_dataframe(), sizing


class DailyLossLimitTests(unittest.TestCase):
    def test_strategy_4_exposes_configured_max_daily_loss_pct(self):
        strategy = VWAPStrategy()
        self.assertEqual(strategy.max_daily_loss_pct, MAX_DAILY_LOSS_PCT)

    def test_daily_loss_limit_rupees_use_start_of_day_equity(self):
        _, sizing = run(
            [
                candle("2024-01-01", "09:30", "A", 100, True),
                candle("2024-01-01", "09:35", "A", 99),
            ],
            initial_capital=10_000,
            max_daily_loss_pct=1.0,
            quantity=10,
        )
        # One point loss per share * 10 shares = -10, well above -100 limit.
        self.assertEqual(sizing.current_equity, 9_990)

        trades, _ = run(
            [
                candle("2024-01-01", "09:30", "A", 100, True),
                candle("2024-01-01", "09:35", "A", 90),
            ],
            initial_capital=10_000,
            max_daily_loss_pct=1.0,
            quantity=10,
        )
        # -100 realized P&L should trigger the lock (exactly at 1% of 10,000).
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades.iloc[0]["pnl"], -100.0)

    def test_trading_continues_while_daily_pnl_above_threshold(self):
        trades, _ = run(
            [
                candle("2024-01-01", "09:30", "A", 100, True),
                candle("2024-01-01", "09:35", "A", 99),
                candle("2024-01-01", "09:35", "B", 100, True),
                candle("2024-01-01", "09:40", "B", 99),
            ],
            initial_capital=10_000,
            max_daily_loss_pct=1.0,
            quantity=10,
        )
        self.assertEqual(len(trades), 2)
        self.assertEqual(set(trades["symbol"]), {"A", "B"})

    def test_exact_threshold_triggers_lock(self):
        trades, _ = run(
            [
                candle("2024-01-01", "09:30", "A", 100, True),
                candle("2024-01-01", "09:35", "A", 90),
                candle("2024-01-01", "09:35", "B", 100, True),
            ],
            initial_capital=10_000,
            max_daily_loss_pct=1.0,
            quantity=10,
        )
        self.assertEqual(len(trades), 1)
        self.assertNotIn("B", set(trades["symbol"]))

    def test_crossing_below_threshold_triggers_lock(self):
        trades, _ = run(
            [
                candle("2024-01-01", "09:30", "A", 100, True),
                candle("2024-01-01", "09:35", "A", 89),
                candle("2024-01-01", "09:35", "B", 100, True),
            ],
            initial_capital=10_000,
            max_daily_loss_pct=1.0,
            quantity=10,
        )
        self.assertEqual(len(trades), 1)
        self.assertLess(trades.iloc[0]["pnl"], -100.0)

    def test_open_positions_closed_at_trigger_candle_close(self):
        trades, _ = run(
            [
                candle("2024-01-01", "09:30", "A", 100, True),
                candle("2024-01-01", "09:30", "B", 200, True),
                candle("2024-01-01", "09:35", "A", 90),
                candle("2024-01-01", "09:35", "B", 150),
            ],
            initial_capital=10_000,
            max_daily_loss_pct=1.0,
            quantity=10,
        )
        forced = trades[trades["exit_reason"] == "DAILY_LOSS_LIMIT"]
        self.assertEqual(len(forced), 1)
        self.assertEqual(forced.iloc[0]["symbol"], "B")
        self.assertEqual(forced.iloc[0]["exit_price"], 150.0)
        self.assertEqual(pd.Timestamp(forced.iloc[0]["exit_date"]), pd.Timestamp("2024-01-01 09:35"))

    def test_same_candle_reentry_blocked_after_limit(self):
        strategy = DailyLossLimitStrategy(1.0)
        sizing = FixedQuantitySizing(10_000, 4, 10)
        engine = BacktestEngine(
            strategy,
            TradeEngine(),
            ExitEngine([TimeExit("09:35"), TimeExit("09:40")]),
            sizing,
        )
        rows = pd.DataFrame([
            candle("2024-01-01", "09:30", "A", 100, True),
            candle("2024-01-01", "09:35", "A", 90),
            candle("2024-01-01", "09:35", "A", 90, True),
        ])
        trades = engine.run(rows).to_dataframe()
        self.assertEqual(len(trades), 1)

    def test_later_entries_same_day_blocked_after_limit(self):
        trades, _ = run(
            [
                candle("2024-01-01", "09:30", "A", 100, True),
                candle("2024-01-01", "09:35", "A", 90),
                candle("2024-01-01", "09:40", "C", 100, True),
            ],
            initial_capital=10_000,
            max_daily_loss_pct=1.0,
            quantity=10,
        )
        self.assertNotIn("C", set(trades["symbol"]))

    def test_symbol_without_trigger_candle_closes_on_next_available_candle(self):
        trades, _ = run(
            [
                candle("2024-01-01", "09:30", "A", 100, True),
                candle("2024-01-01", "09:30", "B", 200, True),
                candle("2024-01-01", "09:35", "A", 90),
                candle("2024-01-01", "09:40", "B", 180),
            ],
            initial_capital=10_000,
            max_daily_loss_pct=1.0,
            quantity=10,
        )
        forced = trades[trades["exit_reason"] == "DAILY_LOSS_LIMIT"]
        self.assertEqual(len(forced), 1)
        self.assertEqual(forced.iloc[0]["symbol"], "B")
        self.assertEqual(forced.iloc[0]["exit_price"], 180.0)
        self.assertEqual(pd.Timestamp(forced.iloc[0]["exit_date"]), pd.Timestamp("2024-01-01 09:40"))

    def test_lock_resets_next_trading_day(self):
        trades, _ = run(
            [
                candle("2024-01-01", "09:30", "A", 100, True),
                candle("2024-01-01", "09:35", "A", 90),
                candle("2024-01-02", "09:30", "B", 100, True),
                candle("2024-01-02", "09:35", "B", 99),
            ],
            initial_capital=10_000,
            max_daily_loss_pct=1.0,
            quantity=10,
        )
        self.assertIn("B", set(trades["symbol"]))

    def test_next_day_limit_uses_updated_start_of_day_equity(self):
        trades, sizing = run(
            [
                candle("2024-01-01", "09:30", "A", 100, True),
                candle("2024-01-01", "09:35", "A", 90),
                candle("2024-01-02", "09:30", "B", 100, True),
                candle("2024-01-02", "09:35", "B", 91),
            ],
            initial_capital=10_000,
            max_daily_loss_pct=1.0,
            quantity=10,
        )
        self.assertEqual(sizing.current_equity, 9_810)
        day_two = trades[trades["symbol"] == "B"]
        # 1% of 9,900 is 99; 9 points * 10 shares = -90 should not lock.
        self.assertEqual(len(day_two), 1)
        self.assertEqual(day_two.iloc[0]["pnl"], -90.0)

    def test_strategies_without_setting_keep_existing_behavior(self):
        class LossLimitStrategy:
            intraday = True
            allow_same_candle_reentry = True
            max_loss_trades_per_day = 10
            max_loss_trades_per_symbol_per_day = 10

            def prepare_data(self, data):
                prepared = data.copy()
                prepared["timestamp"] = pd.to_datetime(prepared["date"] + " " + prepared["time"])
                prepared["date"] = prepared["timestamp"]
                return prepared

            def generate_signal(self, row):
                if not row["signal"]:
                    return None
                return ORBSignal(
                    row["symbol"], row["timestamp"], row["close"], 90, 120,
                    "LONG", 10, 0.005, {"entry_timestamp": row["timestamp"]},
                )

        engine = BacktestEngine(
            LossLimitStrategy(),
            TradeEngine(),
            ExitEngine([TimeExit("09:35")]),
            FixedQuantitySizing(10_000, 4, 10),
        )
        trades = engine.run(pd.DataFrame([
            candle("2024-01-01", "09:30", "A", 100, True),
            candle("2024-01-01", "09:35", "A", 50),
            candle("2024-01-01", "09:35", "B", 100, True),
        ])).to_dataframe()
        self.assertIn("B", set(trades["symbol"]))

    def test_strategy_3_has_no_max_daily_loss_pct(self):
        self.assertIsNone(getattr(ORBStrategy(), "max_daily_loss_pct", None))

    def test_daily_pnl_includes_transaction_costs(self):
        trades, _ = run(
            [
                candle("2024-01-01", "09:30", "A", 100, True),
                candle("2024-01-01", "09:35", "A", 91),
                candle("2024-01-01", "09:35", "B", 100, True),
            ],
            initial_capital=10_000,
            max_daily_loss_pct=1.0,
            quantity=10,
            transaction_cost=10.0,
        )
        # Gross -90 minus 10 cost = -100 net triggers lock; B must not enter.
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades.iloc[0]["pnl"], -100.0)


if __name__ == "__main__":
    unittest.main()
