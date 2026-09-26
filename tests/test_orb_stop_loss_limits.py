import unittest

import pandas as pd

from Backtest.Strategies.strategy_3_ORB.models import ORBSignal
from Backtest.backtest_engine import BacktestEngine
from engines.exit_engine import ExitEngine, SLExit, TargetExit
from engines.position_sizing_engine import PositionSizingEngine
from engines.trade_engine import TradeEngine


class LimitSignalStrategy:
    intraday = True

    def __init__(self, daily_limit, symbol_limit):
        self.max_stop_losses_per_day = daily_limit
        self.max_stop_losses_per_symbol_per_day = symbol_limit

    def prepare_data(self, data):
        prepared = data.copy()
        prepared["timestamp"] = pd.to_datetime(prepared["date"] + " " + prepared["time"])
        prepared["date"] = prepared["timestamp"]
        return prepared

    def generate_signal(self, row):
        if not row["signal"]:
            return None
        return ORBSignal(row["symbol"], row["timestamp"], row["close"], 95, 120,
                         "LONG", 5, 0.0025, {"entry_timestamp": row["timestamp"]})


def candle(time, symbol, close, high, low, signal=False):
    return {"date": "2024-01-01", "time": time, "symbol": symbol, "close": close,
            "high": high, "low": low, "signal": signal}


def run(data, daily_limit, symbol_limit):
    return BacktestEngine(
        LimitSignalStrategy(daily_limit, symbol_limit), TradeEngine(),
        ExitEngine([SLExit(), TargetExit()]), PositionSizingEngine(100_000, 4),
    ).run(pd.DataFrame(data)).to_dataframe()


class ORBStopLossLimitTests(unittest.TestCase):
    def test_daily_stop_limit_blocks_all_later_entries(self):
        trades = run([
            candle("09:30", "A", 100, 100, 100, True),
            candle("09:30", "B", 100, 100, 100, True),
            candle("09:30", "C", 100, 100, 100, True),
            candle("09:35", "A", 96, 100, 94),
            candle("09:35", "B", 96, 100, 94),
            candle("09:35", "C", 100, 100, 100),
            candle("09:40", "A", 100, 100, 100, True),
            candle("09:40", "B", 100, 100, 100, True),
            candle("09:40", "C", 100, 100, 100, True),
        ], daily_limit=2, symbol_limit=1)
        self.assertEqual((trades["entry_timestamp"] == pd.Timestamp("2024-01-01 09:40")).sum(), 0)

    def test_symbol_stop_limit_blocks_only_that_symbol(self):
        trades = run([
            candle("09:30", "A", 100, 100, 100, True),
            candle("09:35", "A", 96, 100, 94),
            candle("09:40", "A", 100, 100, 100, True),
            candle("09:40", "B", 100, 100, 100, True),
        ], daily_limit=10, symbol_limit=1)
        self.assertEqual((trades["symbol"] == "A").sum(), 1)
        self.assertEqual((trades["symbol"] == "B").sum(), 1)


if __name__ == "__main__":
    unittest.main()
