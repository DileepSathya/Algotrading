import unittest
from datetime import time

import pandas as pd

from Backtest.backtest_engine import BacktestEngine
from Backtest.Strategies.strategy_4_VWAP import VWAPStrategy
from Backtest.Strategies.strategy_4_VWAP.exits import EMACrossExit
from engines.exit_engine import ExitEngine, SLExit, TargetExit, TimeExit
from engines.position_sizing_engine import PositionSizingEngine
from engines.trade_engine import TradeEngine


def bar(day, clock, symbol, open_, high, low, close, volume):
    return {
        "date": day,
        "time": clock,
        "symbol": symbol,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


class VWAPStrategyTests(unittest.TestCase):
    def test_vwap_is_cumulative_and_resets_for_each_symbol_and_day(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 9, 12, 9, 9, 10),
            bar("2024-01-01", "09:30", "A", 15, 18, 15, 15, 30),
            bar("2024-01-01", "09:15", "B", 27, 33, 27, 30, 5),
            bar("2024-01-02", "09:15", "A", 39, 42, 39, 39, 7),
        ])

        prepared = VWAPStrategy().prepare_data(raw).set_index(
            ["trading_date", "symbol", "time"]
        )

        self.assertEqual(
            prepared.loc[(pd.Timestamp("2024-01-01"), "A", time(9, 15)), "vwap"],
            10.0,
        )
        self.assertEqual(
            prepared.loc[(pd.Timestamp("2024-01-01"), "A", time(9, 30)), "vwap"],
            14.5,
        )
        self.assertEqual(
            prepared.loc[(pd.Timestamp("2024-01-01"), "B", time(9, 15)), "vwap"],
            30.0,
        )
        self.assertEqual(
            prepared.loc[(pd.Timestamp("2024-01-02"), "A", time(9, 15)), "vwap"],
            40.0,
        )

    def test_0930_candle_is_eligible_and_long_uses_entry_candle_levels(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 100, 103, 99, 100, 100),
            bar("2024-01-01", "09:30", "A", 100, 111, 99, 110, 200),
        ])
        strategy = VWAPStrategy(target_pct_from_entry=0.5, risk_fraction=0.005)
        prepared = strategy.prepare_data(raw)

        self.assertIsNone(strategy.generate_signal(prepared.iloc[0]))
        signal = strategy.generate_signal(prepared.iloc[1])

        self.assertEqual(signal.direction, "LONG")
        self.assertEqual(signal.entry_price, 110.0)
        self.assertEqual(signal.sl, 99.0)
        self.assertAlmostEqual(signal.target, 110.55)
        self.assertEqual(signal.risk_per_unit, 11.0)
        self.assertEqual(signal.risk_fraction, 0.005)

    def test_short_requires_higher_volume_and_uses_entry_candle_levels(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 99, 102, 98, 100, 100),
            bar("2024-01-01", "09:30", "A", 104, 106, 103, 105, 100),
            bar("2024-01-01", "09:45", "A", 90, 94, 88, 89, 101),
        ])
        strategy = VWAPStrategy(target_pct_from_entry=0.5)
        prepared = strategy.prepare_data(raw)

        self.assertIsNone(strategy.generate_signal(prepared.iloc[1]))
        signal = strategy.generate_signal(prepared.iloc[2])

        self.assertEqual(signal.direction, "SHORT")
        self.assertEqual((signal.entry_price, signal.sl), (89.0, 94.0))
        self.assertAlmostEqual(signal.target, 88.555)
        self.assertEqual(signal.risk_per_unit, 5.0)

    def test_candle_already_on_same_side_of_vwap_is_not_a_breakout(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 100, 100, 98, 100, 100),
            bar("2024-01-01", "09:30", "A", 101, 103, 100, 102, 200),
        ])
        strategy = VWAPStrategy()
        prepared = strategy.prepare_data(raw)

        self.assertGreater(prepared.iloc[0]["close"], prepared.iloc[0]["vwap"])
        self.assertGreater(prepared.iloc[1]["close"], prepared.iloc[1]["vwap"])
        self.assertIsNone(strategy.generate_signal(prepared.iloc[1]))

    def test_entries_at_forced_exit_time_are_ineligible(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "14:15", "A", 99, 101, 98, 100, 100),
            bar("2024-01-01", "14:30", "A", 100, 111, 99, 110, 200),
        ])
        strategy = VWAPStrategy(forced_exit_time=time(14, 30))
        prepared = strategy.prepare_data(raw)
        self.assertIsNone(strategy.generate_signal(prepared.iloc[1]))

    def test_zero_entry_candle_risk_does_not_generate_signal(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 99, 101, 98, 100, 100),
            bar("2024-01-01", "09:30", "A", 110, 110, 110, 110, 200),
        ])
        strategy = VWAPStrategy()
        prepared = strategy.prepare_data(raw)
        self.assertIsNone(strategy.generate_signal(prepared.iloc[1]))


class EMACrossExitTests(unittest.TestCase):
    def test_directional_cross_requires_previous_price_on_other_side(self):
        rule = EMACrossExit(3)

        long_cross = pd.Series({
            "close": 99.0, "exit_ema_3": 100.0,
            "previous_close": 101.0, "previous_exit_ema_3": 100.0,
        })
        short_cross = pd.Series({
            "close": 101.0, "exit_ema_3": 100.0,
            "previous_close": 99.0, "previous_exit_ema_3": 100.0,
        })
        already_below = pd.Series({
            "close": 98.0, "exit_ema_3": 100.0,
            "previous_close": 99.0, "previous_exit_ema_3": 100.0,
        })

        self.assertEqual(rule.check(long_cross, 105, 90, 120, "LONG").exit_price, 99.0)
        self.assertEqual(rule.check(short_cross, 95, 110, 80, "SHORT").exit_price, 101.0)
        self.assertIsNone(rule.check(already_below, 105, 90, 120, "LONG"))

    def test_ema_is_calculated_in_chronological_symbol_order_without_lookahead(self):
        raw = pd.DataFrame([
            {"date": "2024-01-01", "time": "09:45", "symbol": "A", "close": 90.0},
            {"date": "2024-01-01", "time": "09:15", "symbol": "A", "close": 100.0},
            {"date": "2024-01-01", "time": "09:30", "symbol": "A", "close": 110.0},
        ])
        prepared = EMACrossExit(2).prepare_data(raw)
        values = prepared.set_index(prepared["time"])

        self.assertAlmostEqual(values.loc["09:30", "exit_ema_2"], 106.67, places=2)
        self.assertEqual(values.loc["09:30", "previous_close"], 100.0)
        self.assertEqual(values.loc["09:30", "previous_exit_ema_2"], 100.0)


class VWAPBacktestIntegrationTests(unittest.TestCase):
    def test_ema_exit_can_reverse_to_short_on_same_candle(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 100, 103, 99, 100, 100),
            bar("2024-01-01", "09:30", "A", 100, 111, 90, 110, 200),
            bar("2024-01-01", "09:45", "A", 100, 101, 99, 100, 300),
        ])
        strategy = VWAPStrategy(ema_period=2, target_pct_from_entry=10.0)
        engine = BacktestEngine(
            strategy,
            TradeEngine(),
            ExitEngine([SLExit(), TargetExit(), EMACrossExit(2), TimeExit("14:30")]),
        )

        trades = engine.run(raw).to_dataframe()

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades.iloc[0]["direction"], "LONG")
        self.assertEqual(trades.iloc[0]["exit_reason"], "2_EMA_CROSS")
        self.assertEqual(trades.iloc[1]["direction"], "SHORT")
        self.assertEqual(trades.iloc[0]["exit_date"], trades.iloc[1]["entry_date"])

    def test_risk_sizing_and_forced_exit_follow_shared_engines(self):
        raw = pd.DataFrame([
            bar("2024-01-01", "09:15", "A", 100, 103, 99, 100, 100),
            bar("2024-01-01", "09:30", "A", 100, 110, 100, 108, 200),
            bar("2024-01-01", "14:30", "A", 108, 109, 105, 106, 150),
        ])
        strategy = VWAPStrategy(ema_period=2, target_pct_from_entry=10.0, risk_fraction=0.005)
        sizing = PositionSizingEngine(initial_capital=100_000, max_open_positions=4)
        engine = BacktestEngine(
            strategy,
            TradeEngine(),
            ExitEngine([SLExit(), TargetExit(), EMACrossExit(2), TimeExit("14:30")]),
            sizing,
        )

        trade = engine.run(raw).to_dataframe().iloc[0]

        self.assertEqual(trade["entry"], 108.0)
        self.assertEqual(trade["risk_per_unit"], 8.0)
        self.assertEqual(trade["quantity"], 62)
        self.assertEqual(trade["exit_reason"], "TIME")
        self.assertEqual(trade["exit_price"], 106.0)


if __name__ == "__main__":
    unittest.main()
