import unittest

import pandas as pd

from Backtest.Strategies.Strategy_1_higher_high.exits import TrailingStopExit


class HigherHighTrailingStopTests(unittest.TestCase):
    def test_rolling_stop_uses_only_the_two_previous_candles(self):
        candles = pd.DataFrame(
            {
                "symbol": ["A", "A", "A", "A"],
                "date": pd.to_datetime(
                    ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
                ),
                "low": [10.0, 12.0, 14.0, 11.0],
            }
        )

        prepared = TrailingStopExit(2).prepare_data(candles)

        self.assertTrue(pd.isna(prepared.loc[0, "trailing_stop_2"]))
        self.assertTrue(pd.isna(prepared.loc[1, "trailing_stop_2"]))
        self.assertEqual(prepared.loc[2, "trailing_stop_2"], 10.0)
        self.assertEqual(prepared.loc[3, "trailing_stop_2"], 12.0)

    def test_exits_at_trailing_level_when_daily_low_crosses_it(self):
        rule = TrailingStopExit(2)

        result = rule.check(
            row={"low": 11.0, "trailing_stop_2": 12.0},
            entry_price=15.0,
            sl=9.0,
            target=20.0,
        )

        self.assertEqual(result.exit_price, 12.0)
        self.assertEqual(result.exit_reason, "TRAILING_SL")

    def test_disabled_or_unavailable_trailing_stop_does_not_exit(self):
        rule = TrailingStopExit(2)

        self.assertIsNone(
            rule.check(
                row={"low": 8.0, "trailing_stop_2": float("nan")},
                entry_price=15.0,
                sl=9.0,
                target=20.0,
            )
        )

    def test_rejects_non_positive_candle_count(self):
        with self.assertRaises(ValueError):
            TrailingStopExit(0)


if __name__ == "__main__":
    unittest.main()
