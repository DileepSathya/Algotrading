import unittest
from datetime import time

import pandas as pd

from Backtest.Strategies.strategy_3_ORB import ORBStrategy


def bar(day, clock, symbol, high, low, close, volume=1):
    return {"date": day, "time": clock, "symbol": symbol, "open": close,
            "high": high, "low": low, "close": close, "volume": volume}


class ORBStrategyTests(unittest.TestCase):
    def test_opening_range_is_isolated_by_symbol_and_day(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 105, 98, 100),
            bar("2024-01-01", "09:20", "A", 103, 95, 100),
            bar("2024-01-01", "09:15", "B", 210, 195, 200),
            bar("2024-01-01", "09:20", "B", 205, 190, 200),
            bar("2024-01-02", "09:15", "A", 120, 110, 115),
            bar("2024-01-01", "10:00", "A", 106, 100, 106),
            bar("2024-01-01", "10:00", "B", 211, 200, 211),
            bar("2024-01-02", "10:00", "A", 121, 115, 121),
        ])
        prepared = ORBStrategy().prepare_data(raw)
        values = prepared.set_index(["trading_date", "symbol", "time"])
        a1 = values.loc[(pd.Timestamp("2024-01-01"), "A", pd.Timestamp("10:00").time())]
        b1 = values.loc[(pd.Timestamp("2024-01-01"), "B", pd.Timestamp("10:00").time())]
        a2 = values.loc[(pd.Timestamp("2024-01-02"), "A", pd.Timestamp("10:00").time())]
        self.assertEqual((a1.orb_high, a1.orb_low), (105, 95))
        self.assertEqual((b1.orb_high, b1.orb_low), (210, 190))
        self.assertEqual((a2.orb_high, a2.orb_low), (120, 110))

    def test_pre_window_breakout_is_ineligible_and_1000_breakout_is_long(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 101, 99, 100),
            bar("2024-01-01", "09:55", "A", 110, 99, 110),
            bar("2024-01-01", "10:00", "A", 112, 105, 111, 2),
        ])
        strategy = ORBStrategy(orb_end=time(10, 0), sl_range_multiplier=0.5,
                               target_range_multiplier=1.0)
        prepared = strategy.prepare_data(raw)
        self.assertIsNone(strategy.generate_signal(prepared.iloc[1]))
        signal = strategy.generate_signal(prepared.iloc[2])
        self.assertEqual(signal.direction, "LONG")
        self.assertEqual((signal.entry_price, signal.sl, signal.target), (111, 105.5, 122))

    def test_short_signal_uses_half_range_stop_and_full_range_target(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 105, 95, 100),
            bar("2024-01-01", "10:00", "A", 96, 93, 94, 2),
        ])
        strategy = ORBStrategy()
        signal = strategy.generate_signal(strategy.prepare_data(raw).iloc[-1])
        self.assertEqual(signal.direction, "SHORT")
        self.assertEqual((signal.entry_price, signal.sl, signal.target), (94, 104, 76.5))
        self.assertEqual(signal.risk_per_unit, 10)

    def test_zero_range_opening_has_no_signal(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 100, 100, 100),
            bar("2024-01-01", "10:00", "A", 101, 100, 101, 2),
        ])
        strategy = ORBStrategy()
        self.assertIsNone(strategy.generate_signal(strategy.prepare_data(raw).iloc[-1]))

    def test_breakouts_at_or_after_forced_exit_time_are_ineligible(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 105, 95, 100),
            bar("2024-01-01", "14:30", "A", 110, 105, 109, 2),
            bar("2024-01-01", "15:00", "A", 112, 108, 111, 3),
        ])
        strategy = ORBStrategy()
        prepared = strategy.prepare_data(raw)
        self.assertIsNone(strategy.generate_signal(prepared.iloc[1]))
        self.assertIsNone(strategy.generate_signal(prepared.iloc[2]))

    def test_configured_entry_window_ends_at_1130(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 105, 95, 100),
            bar("2024-01-01", "09:30", "A", 108, 105, 106, 2),
            bar("2024-01-01", "11:29", "A", 110, 105, 108, 3),
            bar("2024-01-01", "11:30", "A", 111, 105, 109, 4),
        ])
        prepared = ORBStrategy().prepare_data(raw)
        self.assertTrue(prepared.iloc[2]["entry_eligible"])
        self.assertFalse(prepared.iloc[3]["entry_eligible"])


if __name__ == "__main__":
    unittest.main()
