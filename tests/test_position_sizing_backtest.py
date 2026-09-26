import unittest

import pandas as pd

from Backtest.backtest_engine import BacktestEngine
from Backtest.Strategies.Strategy_1_higher_high.models import StrategySignal
from engines.backtest_report_engine import BacktestReportEngine
from engines.exit_engine import ExitEngine, SLExit, TargetExit
from engines.position_sizing_engine import PositionSizingEngine
from engines.trade_engine import TradeEngine


class SignalColumnStrategy:
    def prepare_data(self, data):
        return data.copy()

    def generate_signal(self, row):
        if not row["entry_signal"]:
            return None
        return StrategySignal(
            symbol=row["symbol"],
            entry_date=row["date"],
            entry_price=row["close"],
            sl=row["close"] * 0.9,
            target=row["close"] * 1.1,
        )


def candle(day, symbol, close, high, low, entry_signal=False):
    return {
        "date": pd.Timestamp(day),
        "symbol": symbol,
        "close": close,
        "high": high,
        "low": low,
        "entry_signal": entry_signal,
    }


def backtest(capital=1000, slots=1):
    sizing = PositionSizingEngine(capital, slots)
    engine = BacktestEngine(
        strategy=SignalColumnStrategy(),
        trade_engine=TradeEngine(),
        exit_engine=ExitEngine([TargetExit(), SLExit()]),
        position_sizing_engine=sizing,
    )
    return engine, sizing


class PositionSizingBacktestTests(unittest.TestCase):
    def test_exit_frees_slot_before_same_day_close_entry(self):
        engine, _ = backtest()
        data = pd.DataFrame([
            candle("2024-01-01", "Z", 100, 100, 100, True),
            candle("2024-01-02", "A", 50, 50, 50, True),
            candle("2024-01-02", "Z", 110, 111, 100),
        ])

        trades = engine.run(data).to_dataframe()

        self.assertEqual(set(trades["symbol"]), {"A", "Z"})
        self.assertEqual(trades.loc[trades.symbol == "A", "exit_reason"].iloc[0], "END_OF_BACKTEST")

    def test_realized_loss_reduces_next_position_quantity(self):
        sizing = PositionSizingEngine(1000, 2)
        first = sizing.size_position("A", 100)
        self.assertEqual(first.quantity, 5)

        sizing.close_position("A", exit_price=80)
        second = sizing.size_position("B", 100)

        self.assertEqual(sizing.get_available_capital(), 500)
        self.assertEqual(second.quantity, 4)

    def test_open_position_is_settled_at_final_close_for_report(self):
        engine, sizing = backtest()
        data = pd.DataFrame([
            candle("2024-01-01", "A", 100, 100, 100, True),
            candle("2024-01-02", "A", 95, 99, 95),
        ])

        trades = engine.run(data).to_dataframe()
        report = BacktestReportEngine(
            trades,
            capital=1000,
            strategy_name="SignalColumnStrategy",
        ).generate()

        self.assertEqual(trades.iloc[0]["exit_reason"], "END_OF_BACKTEST")
        self.assertEqual(trades.iloc[0]["pnl"], -50)
        self.assertEqual(report.ending_capital, 950)
        self.assertEqual(sizing.get_open_positions(), 0)

    def test_symbol_final_close_releases_cash_for_later_dates(self):
        engine, _ = backtest()
        data = pd.DataFrame([
            candle("2024-01-01", "A", 100, 100, 100, True),
            candle("2024-01-02", "A", 95, 99, 95),
            candle("2024-01-03", "B", 50, 50, 50, True),
        ])

        trades = engine.run(data).to_dataframe()

        self.assertEqual(set(trades["symbol"]), {"A", "B"})

    def test_repeating_backtest_starts_with_original_capital(self):
        engine, sizing = backtest()
        data = pd.DataFrame([
            candle("2024-01-01", "A", 100, 100, 100, True),
            candle("2024-01-02", "A", 95, 99, 95),
        ])

        first = engine.run(data).to_dataframe()
        second = engine.run(data).to_dataframe()

        self.assertTrue(first.equals(second))
        self.assertEqual(sizing.get_available_capital(), 950)


if __name__ == "__main__":
    unittest.main()
