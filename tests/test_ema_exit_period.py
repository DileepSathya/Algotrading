import unittest

import pandas as pd

from Backtest.backtest_engine import BacktestEngine
from Backtest.Strategies.Strategy_1_higher_high.models import StrategySignal
from engines.exit_engine import EMAExit, ExitEngine, TargetExit
from engines.trade_engine import TradeEngine


class EntryOnSecondDay:
    def prepare_data(self, data):
        # Entry selection can discard candles; exit EMA still needs the full history.
        return data[data["date"] >= pd.Timestamp("2024-01-02")].copy()

    def generate_signal(self, row):
        if row["date"] != pd.Timestamp("2024-01-02"):
            return None
        return StrategySignal(
            symbol=row["symbol"],
            entry_date=row["date"],
            entry_price=row["close"],
            sl=1.0,
            target=1000.0,
        )


def candles():
    return pd.DataFrame([
        {"date": "2024-01-03", "symbol": "A", "close": 105.0},
        {"date": "2024-01-01", "symbol": "B", "close": 200.0},
        {"date": "2024-01-02", "symbol": "A", "close": 110.0},
        {"date": "2024-01-01", "symbol": "A", "close": 100.0},
        {"date": "2024-01-03", "symbol": "B", "close": 205.0},
        {"date": "2024-01-02", "symbol": "B", "close": 210.0},
    ]).assign(date=lambda frame: pd.to_datetime(frame["date"]))


class EMAExitPeriodTests(unittest.TestCase):
    def test_unpadded_date_strings_are_sorted_chronologically(self):
        data = pd.DataFrame([
            {"date": "2024-1-10", "symbol": "A", "close": 100.0},
            {"date": "2024-1-2", "symbol": "A", "close": 110.0},
        ])
        prepared = ExitEngine([EMAExit(2)]).prepare_data(data)
        self.assertAlmostEqual(prepared.loc[0, "exit_ema_2"], 103.33, places=2)

    def test_requested_period_is_calculated_per_symbol_in_date_order(self):
        prepared = ExitEngine([EMAExit(2), EMAExit(3)]).prepare_data(candles())
        values = prepared.set_index(["symbol", "date"])

        self.assertAlmostEqual(values.loc[("A", pd.Timestamp("2024-01-03")), "exit_ema_2"], 105.56, places=2)
        self.assertEqual(values.loc[("A", pd.Timestamp("2024-01-03")), "exit_ema_3"], 105.0)
        self.assertEqual(values.loc[("B", pd.Timestamp("2024-01-03")), "exit_ema_3"], 205.0)
        self.assertEqual(prepared[["date", "symbol"]].values.tolist(), candles()[["date", "symbol"]].values.tolist())

    def test_selected_period_changes_real_backtest_exit(self):
        data = candles().query("symbol == 'A'").copy()
        for period, expected_reason in ((2, "2_EMA"), (3, "END_OF_BACKTEST")):
            with self.subTest(period=period):
                engine = BacktestEngine(
                    strategy=EntryOnSecondDay(),
                    trade_engine=TradeEngine(),
                    exit_engine=ExitEngine([EMAExit(period)]),
                )
                trades = engine.run(data).to_dataframe()
                self.assertEqual(trades.iloc[0]["exit_reason"], expected_reason)
                self.assertEqual(trades.iloc[0]["exit_price"], 105.0)

    def test_period_must_be_positive_integer(self):
        for period in (0, -1, 2.5, True, "9"):
            with self.subTest(period=period), self.assertRaises(ValueError):
                EMAExit(period)

    def test_target_rule_keeps_priority_over_ema(self):
        rules = ExitEngine([TargetExit(), EMAExit(2)])
        row = pd.Series({"high": 120.0, "close": 95.0, "exit_ema_2": 100.0})
        result = rules.check(row=row, entry_price=100.0, sl=80.0, target=110.0)
        self.assertEqual(result.exit_reason, "TARGET")
        self.assertEqual(result.exit_price, 110.0)


if __name__ == "__main__":
    unittest.main()
