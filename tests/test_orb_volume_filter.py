import unittest

import pandas as pd

from Backtest.Strategies.strategy_3_ORB.strategy import ORBStrategy
from Backtest.Strategies.strategy_3_ORB.volume import calculate_historical_volume_filter


def daily_volumes(symbol, values):
    return [
        {"trading_date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=offset),
         "symbol": symbol, "volume": volume}
        for offset, volume in enumerate(values)
    ]


def bar(day, clock, high, low, close, volume):
    return {"date": day, "time": clock, "symbol": "A", "open": close,
            "high": high, "low": low, "close": close, "volume": volume}


class ORBVolumeFilterTests(unittest.TestCase):
    def test_previous_day_volume_equal_to_average_is_eligible(self):
        daily = pd.DataFrame(daily_volumes("A", [100, 100, 1]))

        result = calculate_historical_volume_filter(daily, period=1)

        self.assertEqual(result.loc[2, "previous_day_volume"], 100)
        self.assertEqual(result.loc[2, "previous_volume_average"], 100)
        self.assertTrue(result.loc[2, "volume_eligible"])

    def test_previous_day_volume_below_average_is_ineligible(self):
        daily = pd.DataFrame(daily_volumes("A", [100, 90, 1]))

        result = calculate_historical_volume_filter(daily, period=1)

        self.assertFalse(result.loc[2, "volume_eligible"])

    def test_current_day_volume_does_not_affect_current_day_filter(self):
        low_current = pd.DataFrame(daily_volumes("A", [80, 120, 100, 1]))
        high_current = pd.DataFrame(daily_volumes("A", [80, 120, 100, 9_000_000]))

        low_result = calculate_historical_volume_filter(low_current, period=2).iloc[-1]
        high_result = calculate_historical_volume_filter(high_current, period=2).iloc[-1]

        self.assertEqual(low_result["previous_day_volume"], 100)
        self.assertEqual(low_result["previous_volume_average"], 100)
        self.assertEqual(low_result["volume_eligible"], high_result["volume_eligible"])

    def test_insufficient_history_keeps_average_null_and_is_ineligible(self):
        daily = pd.DataFrame(daily_volumes("A", [100, 120, 140]))

        result = calculate_historical_volume_filter(daily, period=2)

        self.assertTrue(pd.isna(result.iloc[-1]["previous_volume_average"]))
        self.assertFalse(result.iloc[-1]["volume_eligible"])

    def test_volume_history_is_isolated_per_symbol(self):
        daily = pd.DataFrame(
            daily_volumes("A", [100, 150, 1])
            + daily_volumes("B", [200, 100, 1])
        )

        result = calculate_historical_volume_filter(daily, period=1)
        latest = result.groupby("symbol", sort=False).tail(1).set_index("symbol")

        self.assertTrue(latest.loc["A", "volume_eligible"])
        self.assertFalse(latest.loc["B", "volume_eligible"])

    def test_strategy_combines_daily_volume_filter_with_atr_filter(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", 105, 95, 100, 100),
            bar("2024-01-02", "09:15", 105, 95, 100, 100),
            bar("2024-01-03", "09:15", 104, 96, 100, 1),
            bar("2024-01-03", "09:30", 106, 103, 105, 2),
        ])
        strategy = ORBStrategy(atr_period=1, volume_period=1)

        prepared = strategy.prepare_data(raw)
        entry = prepared.iloc[-1]

        self.assertEqual(entry["previous_day_volume"], 100)
        self.assertEqual(entry["previous_volume_average"], 100)
        self.assertTrue(entry["entry_eligible"])
        self.assertIsNotNone(strategy.generate_signal(entry))


if __name__ == "__main__":
    unittest.main()
