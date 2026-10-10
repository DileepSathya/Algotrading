import unittest

import pandas as pd

from Backtest.Strategies.Strategy_1_higher_high.strategy import HigherHighStrategy


def entry_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "symbol": "ABC",
                "open": 199.0,
                "high": 205.0,
                "low": 190.0,
                "close": 200.0,
                "volume": 1_000,
            },
            {
                "date": "2024-01-02",
                "symbol": "ABC",
                "open": 95.0,
                "high": 101.0,
                "low": 90.0,
                "close": 100.0,
                "volume": 1_000,
            },
            {
                "date": "2024-01-03",
                "symbol": "ABC",
                "open": 105.0,
                "high": 115.0,
                "low": 100.0,
                "close": 112.0,
                "volume": 1_100,
            },
        ]
    )


def rising_ema_fixture() -> pd.DataFrame:
    data = entry_fixture()
    data.loc[0, ["open", "high", "low", "close"]] = [89.0, 95.0, 80.0, 90.0]
    return data


def equal_ema_fixture() -> pd.DataFrame:
    data = entry_fixture()
    data.loc[2, ["open", "high", "low", "close"]] = [120.0, 140.0, 110.0, 133.33]
    return data


def rsi_fixture(closes: list[float]) -> pd.DataFrame:
    rows = []
    for index, close in enumerate(closes):
        rows.append(
            {
                "date": f"2024-01-{index + 1:02d}",
                "symbol": "ABC",
                "open": close - 1.0,
                "high": close + 4.0,
                "low": close - 10.0,
                "close": close,
                "volume": 1_000 + index * 100,
            }
        )
    return pd.DataFrame(rows)


class HigherHighPriceAboveEmaTests(unittest.TestCase):
    def test_enabled_filter_rejects_close_below_configured_ema(self):
        prepared = HigherHighStrategy(
            ema_period=2,
            price_above_ema_period=True,
            ema_filter=False,
            use_rsi=False,
        ).prepare_data(entry_fixture())

        row = prepared.loc[prepared["date"] == pd.Timestamp("2024-01-03")].iloc[0]
        self.assertLess(row["close"], row["2_ema"])
        self.assertFalse(bool(row["trade_signal"]))

    def test_enabled_filter_accepts_close_equal_to_configured_ema(self):
        prepared = HigherHighStrategy(
            ema_period=1,
            price_above_ema_period=True,
            ema_filter=False,
            use_rsi=False,
        ).prepare_data(entry_fixture())

        row = prepared.loc[prepared["date"] == pd.Timestamp("2024-01-03")].iloc[0]
        self.assertEqual(row["close"], row["1_ema"])
        self.assertTrue(bool(row["trade_signal"]))

    def test_disabled_filter_accepts_close_below_configured_ema(self):
        strategy = HigherHighStrategy(
            ema_period=2,
            price_above_ema_period=False,
            ema_filter=False,
            use_rsi=False,
        )
        prepared = strategy.prepare_data(entry_fixture())

        row = prepared.loc[prepared["date"] == pd.Timestamp("2024-01-03")].iloc[0]
        self.assertLess(row["close"], row["2_ema"])
        self.assertTrue(bool(row["trade_signal"]))
        self.assertEqual(strategy.generate_signal(row).sl, 100.0)


class HigherHighEmaFilterTests(unittest.TestCase):
    def test_enabled_filter_accepts_smaller_ema_above_bigger_ema(self):
        prepared = HigherHighStrategy(
            price_above_ema_period=False,
            ema_filter=True,
            smaller_ema_period=2,
            bigger_ema_period=3,
            use_rsi=False,
        ).prepare_data(rising_ema_fixture())

        row = prepared.loc[prepared["date"] == pd.Timestamp("2024-01-03")].iloc[0]
        self.assertGreater(row["2_ema"], row["3_ema"])
        self.assertTrue(bool(row["trade_signal"]))

    def test_enabled_filter_rejects_smaller_ema_below_bigger_ema(self):
        prepared = HigherHighStrategy(
            price_above_ema_period=False,
            ema_filter=True,
            smaller_ema_period=2,
            bigger_ema_period=3,
            use_rsi=False,
        ).prepare_data(entry_fixture())

        row = prepared.loc[prepared["date"] == pd.Timestamp("2024-01-03")].iloc[0]
        self.assertLess(row["2_ema"], row["3_ema"])
        self.assertFalse(bool(row["trade_signal"]))

    def test_enabled_filter_rejects_equal_emas(self):
        prepared = HigherHighStrategy(
            price_above_ema_period=False,
            ema_filter=True,
            smaller_ema_period=1,
            bigger_ema_period=2,
            use_rsi=False,
        ).prepare_data(equal_ema_fixture())

        row = prepared.loc[prepared["date"] == pd.Timestamp("2024-01-03")].iloc[0]
        self.assertEqual(row["1_ema"], row["2_ema"])
        self.assertFalse(bool(row["trade_signal"]))

    def test_disabled_filter_keeps_existing_signal_when_ema_order_fails(self):
        prepared = HigherHighStrategy(
            price_above_ema_period=False,
            ema_filter=False,
            smaller_ema_period=2,
            bigger_ema_period=3,
            use_rsi=False,
        ).prepare_data(entry_fixture())

        row = prepared.loc[prepared["date"] == pd.Timestamp("2024-01-03")].iloc[0]
        self.assertLess(row["2_ema"], row["3_ema"])
        self.assertTrue(bool(row["trade_signal"]))


class HigherHighRsiFilterTests(unittest.TestCase):
    def prepare(self, closes, *, use_rsi=True, minimum=50.0, maximum=70.0):
        return HigherHighStrategy(
            price_above_ema_period=False,
            ema_filter=False,
            use_rsi=use_rsi,
            rsi_period=2,
            rsi_min_value=minimum,
            rsi_max_value=maximum,
        ).prepare_data(rsi_fixture(closes))

    def test_enabled_filter_accepts_rsi_inside_inclusive_range(self):
        prepared = self.prepare([100.0, 110.0, 90.0, 100.0])

        row = prepared.iloc[-1]
        self.assertAlmostEqual(row["rsi_2"], 60.0)
        self.assertTrue(bool(row["trade_signal"]))

    def test_enabled_filter_rejects_rsi_below_minimum(self):
        prepared = self.prepare([100.0, 110.0, 80.0, 85.0])

        row = prepared.iloc[-1]
        self.assertLess(row["rsi_2"], 50.0)
        self.assertFalse(bool(row["trade_signal"]))

    def test_enabled_filter_rejects_rsi_above_maximum(self):
        prepared = self.prepare([80.0, 90.0, 100.0, 110.0])

        row = prepared.iloc[-1]
        self.assertGreater(row["rsi_2"], 70.0)
        self.assertFalse(bool(row["trade_signal"]))

    def test_disabled_filter_keeps_existing_signal_outside_rsi_range(self):
        prepared = self.prepare(
            [80.0, 90.0, 100.0, 110.0],
            use_rsi=False,
        )

        row = prepared.iloc[-1]
        self.assertGreater(row["rsi_2"], 70.0)
        self.assertTrue(bool(row["trade_signal"]))


if __name__ == "__main__":
    unittest.main()
