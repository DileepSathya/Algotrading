import unittest

import pandas as pd

from engines.exit_engine import ExitEngine, SLExit, TargetExit, TimeExit
from engines.trade_engine.models import Trade


class ShortTradeSupportTests(unittest.TestCase):
    def test_short_trade_profit_and_cost_are_direction_aware(self):
        trade = Trade("A", pd.Timestamp("2024-01-01 10:00"), 100, 105, 90, 10, 1000,
                      direction="SHORT", transaction_cost=4)
        trade.close(pd.Timestamp("2024-01-01 10:05"), 90, "TARGET")
        self.assertEqual(trade.gross_pnl, 100)
        self.assertEqual(trade.pnl, 96)
        self.assertEqual(trade.pnl_percent, 9.6)

    def test_short_stop_and_target_reverse_long_thresholds(self):
        stop = SLExit().check(pd.Series({"high": 106, "low": 99}), 100, 105, 90, direction="SHORT")
        target = TargetExit().check(pd.Series({"high": 99, "low": 89}), 100, 105, 90, direction="SHORT")
        self.assertEqual((stop.exit_price, stop.exit_reason), (105, "SL"))
        self.assertEqual((target.exit_price, target.exit_reason), (90, "TARGET"))

    def test_rule_order_makes_ambiguous_short_bar_stop_first(self):
        engine = ExitEngine([SLExit(), TargetExit()])
        result = engine.check(pd.Series({"high": 106, "low": 89}), 100, 105, 90, direction="SHORT")
        self.assertEqual((result.exit_price, result.exit_reason), (105, "SL"))

    def test_time_exit_uses_candle_close(self):
        rule = TimeExit("14:30")
        result = rule.check(pd.Series({"time": "14:30:00", "close": 101}), 100, 105, 90,
                            direction="SHORT")
        self.assertEqual((result.exit_price, result.exit_reason), (101, "TIME"))


if __name__ == "__main__":
    unittest.main()
