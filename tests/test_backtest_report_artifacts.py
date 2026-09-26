import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from engines.backtest_report_engine import BacktestReportEngine


def completed_trades() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "entry_date": "2024-01-01",
                "exit_date": "2024-01-02",
                "entry": 100.0,
                "exit_price": 110.0,
                "pnl": 100.0,
                "pnl_percent": 10.0,
                "exit_reason": "TARGET",
            },
            {
                "entry_date": "2024-01-03",
                "exit_date": "2024-01-04",
                "entry": 110.0,
                "exit_price": 88.0,
                "pnl": -200.0,
                "pnl_percent": -20.0,
                "exit_reason": "STOP_LOSS",
            },
        ]
    )


class BacktestReportArtifactTests(unittest.TestCase):
    def test_report_contains_strategy_name(self):
        report = BacktestReportEngine(
            completed_trades(),
            capital=1_000.0,
            strategy_name="Higher High",
        ).generate()

        self.assertEqual(report.strategy_name, "Higher High")
        self.assertEqual(report.to_dict()["strategy_name"], "Higher High")
        self.assertIn("Strategy Name         : Higher High", str(report))

    def test_curve_data_starts_at_initial_capital_and_calculates_drawdown(self):
        engine = BacktestReportEngine(
            completed_trades(),
            capital=1_000.0,
            strategy_name="Higher High",
        )

        curves = engine.curve_data()

        self.assertEqual(curves["equity"].tolist(), [1000.0, 1100.0, 900.0])
        self.assertEqual(curves["drawdown"].round(2).tolist(), [0.0, 0.0, -18.18])
        self.assertEqual(
            curves["date"].dt.strftime("%Y-%m-%d").tolist(),
            ["2024-01-01", "2024-01-02", "2024-01-04"],
        )

    def test_generate_and_save_creates_named_run_folder_and_all_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report, run_folder = BacktestReportEngine(
                completed_trades(),
                capital=1_000.0,
                strategy_name="Higher High / NSE",
                reports_root=temp_dir,
            ).generate_and_save()

            self.assertEqual(report.strategy_name, "Higher High / NSE")
            self.assertRegex(
                run_folder.name,
                r"^\d{8}-\d{6}(?:-\d{6})?$",
            )
            self.assertEqual(run_folder.parent.name, "Higher-High-NSE")
            self.assertEqual(run_folder.parent.parent, Path(temp_dir))

            expected_files = {
                "backtest_report.txt",
                "backtest_report.json",
                "equity_curve.png",
                "drawdown_curve.png",
                "monte_carlo_equity.png",
            }
            self.assertEqual(
                {path.name for path in run_folder.iterdir()},
                expected_files,
            )
            self.assertGreater((run_folder / "equity_curve.png").stat().st_size, 0)
            self.assertGreater((run_folder / "drawdown_curve.png").stat().st_size, 0)
            self.assertIn("Higher High / NSE", (run_folder / "backtest_report.txt").read_text())
            saved_json = json.loads((run_folder / "backtest_report.json").read_text())
            self.assertEqual(saved_json["strategy_name"], "Higher High / NSE")

    def test_empty_backtest_still_saves_flat_curves(self):
        empty_trades = pd.DataFrame(
            columns=[
                "entry_date",
                "exit_date",
                "entry",
                "exit_price",
                "pnl",
                "pnl_percent",
                "exit_reason",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = BacktestReportEngine(
                empty_trades,
                capital=1_000.0,
                strategy_name="No Trades",
                reports_root=temp_dir,
            )
            curves = engine.curve_data()
            report, run_folder = engine.generate_and_save()

            self.assertEqual(curves["equity"].tolist(), [1000.0])
            self.assertEqual(curves["drawdown"].tolist(), [0.0])
            self.assertEqual(report.total_trades, 0)
            self.assertTrue((run_folder / "equity_curve.png").is_file())
            self.assertTrue((run_folder / "drawdown_curve.png").is_file())


if __name__ == "__main__":
    unittest.main()
