import unittest

import pandas as pd

from Backtest.Strategies.strategy_3_ORB.atr import (
    aggregate_daily_ohlc,
    calculate_historical_atr,
    wilder_atr,
)
from Backtest.Strategies.strategy_3_ORB.strategy import ORBStrategy


def bar(day, clock, high, low, close, volume=1, symbol="A", open_=None):
    return {
        "date": day,
        "time": clock,
        "symbol": symbol,
        "open": close if open_ is None else open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


class ORBATRFilterTests(unittest.TestCase):
    def test_aggregates_daily_ohlc_per_symbol_in_timestamp_order(self):
        intraday = pd.DataFrame([
            {"trading_date": pd.Timestamp("2024-01-02"), "timestamp": pd.Timestamp("2024-01-02 09:20"),
             "symbol": "A", "open": 12, "high": 16, "low": 11, "close": 15, "volume": 30},
            {"trading_date": pd.Timestamp("2024-01-02"), "timestamp": pd.Timestamp("2024-01-02 09:15"),
             "symbol": "A", "open": 10, "high": 13, "low": 9, "close": 12, "volume": 20},
            {"trading_date": pd.Timestamp("2024-01-02"), "timestamp": pd.Timestamp("2024-01-02 09:15"),
             "symbol": "B", "open": 20, "high": 22, "low": 18, "close": 21, "volume": 40},
        ])

        daily = aggregate_daily_ohlc(intraday).set_index("symbol")

        self.assertEqual(tuple(daily.loc["A", ["open", "high", "low", "close"]]), (10, 16, 9, 15))
        self.assertEqual(tuple(daily.loc["B", ["open", "high", "low", "close"]]), (20, 22, 18, 21))
        self.assertEqual(daily.loc["A", "volume"], 50)

    def test_wilder_atr_uses_simple_average_seed_then_wilder_smoothing(self):
        result = wilder_atr(pd.Series([2.0, 3.0, 6.0, 3.0]), period=3)

        self.assertTrue(pd.isna(result.iloc[0]))
        self.assertTrue(pd.isna(result.iloc[1]))
        self.assertAlmostEqual(result.iloc[2], 11 / 3)
        self.assertAlmostEqual(result.iloc[3], 31 / 9)

    def test_historical_atr_is_shifted_to_the_next_trading_day_per_symbol(self):
        daily = pd.DataFrame([
            {"trading_date": "2024-01-01", "symbol": "A", "open": 9, "high": 10, "low": 8, "close": 9},
            {"trading_date": "2024-01-02", "symbol": "A", "open": 9, "high": 12, "low": 9, "close": 11},
            {"trading_date": "2024-01-03", "symbol": "A", "open": 11, "high": 15, "low": 12, "close": 14},
            {"trading_date": "2024-01-04", "symbol": "A", "open": 14, "high": 16, "low": 13, "close": 15},
        ])

        aligned = calculate_historical_atr(daily, period=3)

        self.assertTrue(pd.isna(aligned.loc[2, "atr"]))
        self.assertAlmostEqual(aligned.loc[3, "atr"], 3.0)

    def test_orb_range_less_than_atr_allows_signal(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", 105, 95, 100),
            bar("2024-01-02", "09:15", 104, 96, 100),
            bar("2024-01-02", "09:30", 106, 103, 105, volume=2),
        ])
        strategy = ORBStrategy(atr_period=1, volume_period=None)

        prepared = strategy.prepare_data(raw)

        self.assertEqual(prepared.iloc[-1]["atr"], 10)
        self.assertTrue(prepared.iloc[-1]["entry_eligible"])
        self.assertIsNotNone(strategy.generate_signal(prepared.iloc[-1]))

    def test_orb_range_equal_to_atr_blocks_signal_but_retains_rows(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", 105, 95, 100),
            bar("2024-01-02", "09:15", 105, 95, 100),
            bar("2024-01-02", "09:30", 108, 105, 107, volume=2),
        ])
        strategy = ORBStrategy(atr_period=1, volume_period=None)

        prepared = strategy.prepare_data(raw)

        self.assertEqual(len(prepared), 3)
        self.assertFalse(prepared.iloc[-1]["entry_eligible"])
        self.assertIsNone(strategy.generate_signal(prepared.iloc[-1]))

    def test_orb_range_greater_than_atr_blocks_signal(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", 105, 95, 100),
            bar("2024-01-02", "09:15", 106, 94, 100),
            bar("2024-01-02", "09:30", 108, 105, 107, volume=2),
        ])
        strategy = ORBStrategy(atr_period=1, volume_period=None)

        prepared = strategy.prepare_data(raw)

        self.assertFalse(prepared.iloc[-1]["entry_eligible"])
        self.assertIsNone(strategy.generate_signal(prepared.iloc[-1]))

    def test_insufficient_history_keeps_null_atr_and_blocks_signal(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", 105, 95, 100),
            bar("2024-01-01", "09:30", 108, 105, 107, volume=2),
        ])
        strategy = ORBStrategy(volume_period=None)

        prepared = strategy.prepare_data(raw)

        self.assertTrue(pd.isna(prepared.iloc[-1]["atr"]))
        self.assertFalse(prepared.iloc[-1]["entry_eligible"])
        self.assertIsNone(strategy.generate_signal(prepared.iloc[-1]))


if __name__ == "__main__":
    unittest.main()
