import unittest
from datetime import time

import pandas as pd

from Backtest.Strategies.strategy_3_ORB import ORBStrategy
from Backtest.backtest_engine import BacktestEngine
from engines.exit_engine import ExitEngine, SLExit, TargetExit, TimeExit
from engines.position_sizing_engine import PositionSizingEngine
from engines.trade_engine import TradeEngine


def bar(clock, high, low, close, volume=1):
    return {"date": "2024-01-01", "time": clock, "symbol": "A", "open": close,
            "high": high, "low": low, "close": close, "volume": volume}


def engine():
    return BacktestEngine(ORBStrategy(), TradeEngine(),
                          ExitEngine([SLExit(), TargetExit(), TimeExit("14:30")]),
                          PositionSizingEngine(100_000, 4))


class ORBBacktestTests(unittest.TestCase):
    def test_symbol_end_of_day_close_releases_slot_for_later_symbol(self):
        rows = [
            {**bar("09:15", 105, 95, 100), "symbol": "A"},
            {**bar("09:15", 205, 195, 200), "symbol": "B"},
            {**bar("10:00", 108, 105, 106, 2), "symbol": "A"},
            {**bar("14:00", 108, 105, 107, 3), "symbol": "A"},
            {**bar("14:25", 210, 205, 206, 2), "symbol": "B"},
        ]
        one_slot = BacktestEngine(ORBStrategy(entry_end_time=time(14, 30)), TradeEngine(),
                                  ExitEngine([SLExit(), TargetExit(), TimeExit("14:30")]),
                                  PositionSizingEngine(100_000, 1))
        trades = one_slot.run(pd.DataFrame(rows)).to_dataframe()
        self.assertEqual(trades["symbol"].tolist(), ["A", "B"])
        self.assertEqual(trades.iloc[0].exit_timestamp, pd.Timestamp("2024-01-01 14:00"))

    def test_configurable_transaction_cost_reduces_trade_and_equity(self):
        cost_engine = BacktestEngine(ORBStrategy(), TradeEngine(),
                                     ExitEngine([SLExit(), TargetExit(), TimeExit("14:30")]),
                                     PositionSizingEngine(100_000, 4),
                                     transaction_cost_model=lambda trade, exit_price: 7.5)
        data = pd.DataFrame([bar("09:15", 105, 95, 100), bar("10:00", 108, 105, 106, 2),
                             bar("10:05", 125, 110, 124, 3)])
        trade = cost_engine.run(data).to_dataframe().iloc[0]
        self.assertEqual(trade.transaction_cost, 7.5)
        self.assertEqual(trade.pnl, trade.gross_pnl - 7.5)
        self.assertEqual(trade.equity_after, 100_000 + trade.pnl)

    def test_entry_candle_does_not_trigger_target(self):
        data = pd.DataFrame([
            bar("09:15", 105, 95, 100),
            bar("10:00", 130, 94, 106, 2),
            bar("10:05", 120, 100, 110, 3),
            bar("14:30", 121, 109, 110, 4),
        ])
        trade = engine().run(data).to_dataframe().iloc[0]
        self.assertEqual(trade.exit_reason, "TIME")
        self.assertEqual(trade.exit_price, 110)
        self.assertEqual(trade.entry_timestamp, pd.Timestamp("2024-01-01 10:00"))

    def test_short_target_and_audit_fields(self):
        data = pd.DataFrame([
            bar("09:15", 105, 95, 100),
            bar("10:00", 96, 93, 94, 2),
            bar("10:05", 93, 75, 85, 3),
        ])
        trade = engine().run(data).to_dataframe().iloc[0]
        self.assertEqual((trade.direction, trade.exit_reason, trade.exit_price), ("SHORT", "TARGET", 76.5))
        self.assertEqual((trade.orb_high, trade.orb_low, trade.orb_range), (105, 95, 10))
        self.assertEqual((trade.quantity, trade.gross_pnl, trade.pnl), (25, 437.5, 437.5))
        self.assertEqual(trade.equity_after, 100_437.5)

    def test_missing_1430_candle_forces_same_day_close(self):
        data = pd.DataFrame([
            bar("09:15", 105, 95, 100),
            bar("10:00", 108, 105, 106, 2),
            bar("14:25", 110, 106, 108, 3),
        ])
        trade = engine().run(data).to_dataframe().iloc[0]
        self.assertEqual(trade.exit_reason, "END_OF_DAY")
        self.assertEqual(trade.exit_timestamp, pd.Timestamp("2024-01-01 14:25"))


if __name__ == "__main__":
    unittest.main()
