import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from engines.backtest_report_engine import BacktestReportEngine


def trades_with_pnl(values):
    return pd.DataFrame([
        {
            "entry_date": f"2024-01-{index:02d}",
            "exit_date": f"2024-01-{index:02d}",
            "entry": 100.0,
            "exit_price": 100.0,
            "pnl": value,
            "pnl_percent": value / 10,
            "exit_reason": "TEST",
        }
        for index, value in enumerate(values, 1)
    ], columns=["entry_date", "exit_date", "entry", "exit_price", "pnl", "pnl_percent", "exit_reason"])


class MonteCarloReportTests(unittest.TestCase):
    def test_bootstrap_changes_ending_outcomes_not_just_trade_order(self):
        summary = BacktestReportEngine(
            trades_with_pnl([-100.0, 100.0]),
            capital=1000.0,
            strategy_name="Mixed",
            monte_carlo_simulations=1000,
            monte_carlo_seed=3,
        ).generate().to_dict()["monte_carlo"]

        self.assertEqual(summary["ending_capital_5th_percentile"], 800.0)
        self.assertEqual(summary["ending_capital_95th_percentile"], 1200.0)
        self.assertGreater(summary["probability_of_loss_percent"], 20.0)
        self.assertLess(summary["probability_of_loss_percent"], 30.0)

    def test_constant_trade_pnl_gives_exact_summary(self):
        report = BacktestReportEngine(
            trades_with_pnl([-100.0, -100.0]),
            capital=1000.0,
            strategy_name="Losses",
            monte_carlo_simulations=100,
            monte_carlo_seed=17,
        ).generate()

        summary = report.to_dict()["monte_carlo"]
        self.assertEqual(summary["status"], "available")
        self.assertEqual(summary["method"], "trade_bootstrap_with_replacement")
        self.assertEqual(summary["simulations"], 100)
        self.assertEqual(summary["seed"], 17)
        self.assertEqual(summary["median_ending_capital"], 800.0)
        self.assertEqual(summary["ending_capital_5th_percentile"], 800.0)
        self.assertEqual(summary["ending_capital_95th_percentile"], 800.0)
        self.assertEqual(summary["median_max_drawdown_percent"], 20.0)
        self.assertEqual(summary["max_drawdown_95th_percentile"], 20.0)
        self.assertEqual(summary["probability_of_loss_percent"], 100.0)
        self.assertIn("Monte Carlo Analysis", str(report))
        self.assertIn("100.00% of simulated runs ended below initial capital", str(report))

    def test_seed_reproduces_summary_and_saves_chart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = BacktestReportEngine(
                trades_with_pnl([100.0, -200.0, 50.0]),
                capital=1000.0,
                strategy_name="Mixed",
                reports_root=temp_dir,
                monte_carlo_simulations=200,
                monte_carlo_seed=9,
            )
            report, folder = engine.generate_and_save()
            summary = report.to_dict()["monte_carlo"]

            self.assertEqual(summary, engine.generate().to_dict()["monte_carlo"])
            self.assertGreater((folder / "monte_carlo_equity.png").stat().st_size, 0)
            self.assertEqual(
                json.loads((folder / "backtest_report.json").read_text())["monte_carlo"],
                summary,
            )
            self.assertIn("Monte Carlo Analysis", (folder / "backtest_report.txt").read_text())

    def test_short_history_marks_analysis_unavailable(self):
        for values in ([], [100.0]):
            with self.subTest(values=values), tempfile.TemporaryDirectory() as temp_dir:
                report, folder = BacktestReportEngine(
                    trades_with_pnl(values),
                    capital=1000.0,
                    strategy_name="Short",
                    reports_root=temp_dir,
                ).generate_and_save()
                self.assertEqual(report.to_dict()["monte_carlo"]["status"], "insufficient_trades")
                self.assertFalse((folder / "monte_carlo_equity.png").exists())
                self.assertIn("at least 2 completed trades", str(report))


if __name__ == "__main__":
    unittest.main()
