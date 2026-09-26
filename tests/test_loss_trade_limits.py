import unittest

import pandas as pd

from Backtest.Strategies.strategy_3_ORB.models import ORBSignal
from Backtest.Strategies.strategy_4_VWAP import VWAPStrategy
from Backtest.backtest_engine import BacktestEngine
from engines.exit_engine import ExitEngine, TimeExit
from engines.trade_engine import TradeEngine


class LossLimitStrategy:
    intraday = True
    allow_same_candle_reentry = True

    def __init__(self, daily_limit, symbol_limit):
        self.max_loss_trades_per_day = daily_limit
        self.max_loss_trades_per_symbol_per_day = symbol_limit

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


def candle(day, clock, symbol, close, signal=False):
    return {
        "date": day,
        "time": clock,
        "symbol": symbol,
        "close": close,
        "high": close,
        "low": close,
        "signal": signal,
    }


def run(rows, daily_limit, symbol_limit):
    engine = BacktestEngine(
        LossLimitStrategy(daily_limit, symbol_limit),
        TradeEngine(),
        ExitEngine([TimeExit("09:35")]),
    )
    return engine.run(pd.DataFrame(rows)).to_dataframe()


class LossTradeLimitTests(unittest.TestCase):
    def test_strategy_4_exposes_configured_loss_limits(self):
        strategy = VWAPStrategy()
        self.assertEqual(strategy.max_loss_trades_per_day, 4)
        self.assertEqual(strategy.max_loss_trades_per_symbol_per_day, 2)

    def test_symbol_limit_blocks_only_losing_symbol_after_two_losses(self):
        trades = run([
            candle("2024-01-01", "09:30", "A", 100, True),
            candle("2024-01-01", "09:35", "A", 99, True),
            candle("2024-01-01", "09:40", "A", 98, True),
            candle("2024-01-01", "09:40", "B", 100, True),
        ], daily_limit=10, symbol_limit=2)

        self.assertEqual((trades["symbol"] == "A").sum(), 2)
        self.assertEqual((trades["symbol"] == "B").sum(), 1)

    def test_daily_limit_blocks_all_entries_after_four_losses(self):
        trades = run([
            candle("2024-01-01", "09:30", "A", 100, True),
            candle("2024-01-01", "09:30", "B", 100, True),
            candle("2024-01-01", "09:30", "C", 100, True),
            candle("2024-01-01", "09:30", "D", 100, True),
            candle("2024-01-01", "09:35", "A", 99),
            candle("2024-01-01", "09:35", "B", 99),
            candle("2024-01-01", "09:35", "C", 99),
            candle("2024-01-01", "09:35", "D", 99),
            candle("2024-01-01", "09:35", "E", 100, True),
        ], daily_limit=4, symbol_limit=10)

        self.assertNotIn("E", set(trades["symbol"]))

    def test_loss_counts_reset_on_next_trading_day(self):
        trades = run([
            candle("2024-01-01", "09:30", "A", 100, True),
            candle("2024-01-01", "09:35", "A", 99),
            candle("2024-01-01", "09:40", "B", 100, True),
            candle("2024-01-02", "09:30", "B", 100, True),
            candle("2024-01-02", "09:35", "B", 99),
        ], daily_limit=1, symbol_limit=10)

        entries = pd.to_datetime(trades["entry_timestamp"])
        self.assertEqual((entries.dt.date == pd.Timestamp("2024-01-01").date()).sum(), 1)
        self.assertEqual((entries.dt.date == pd.Timestamp("2024-01-02").date()).sum(), 1)


if __name__ == "__main__":
    unittest.main()
