import json
import tempfile
import unittest
from pathlib import Path

from Backtest.Strategies.Strategy_1_higher_high.run_backtest import run


class HigherHighReportArtifactTests(unittest.TestCase):
    def test_run_writes_complete_report_artifact_set(self):
        candles = [
            {
                "date": "2024-01-01",
                "symbol": "A",
                "open": 99.0,
                "high": 101.0,
                "low": 98.0,
                "close": 100.0,
                "volume": 1000,
            },
            {
                "date": "2024-01-02",
                "symbol": "A",
                "open": 101.0,
                "high": 105.0,
                "low": 100.0,
                "close": 104.0,
                "volume": 1200,
            },
            {
                "date": "2024-01-03",
                "symbol": "A",
                "open": 104.0,
                "high": 115.0,
                "low": 103.0,
                "close": 114.0,
                "volume": 1300,
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_path = root / "candles.json"
            data_path.write_text(json.dumps(candles), encoding="utf-8")

            result = run(
                data_path=data_path,
                reports_root=root / "reports",
                initial_capital=10_000.0,
                max_open_positions=2,
            )

            self.assertEqual(result["report"].strategy_name, "HigherHighStrategy")
            self.assertEqual(result["report_folder"].parent.name, "HigherHighStrategy")
            self.assertEqual(
                {path.name for path in result["report_folder"].iterdir()},
                {
                    "backtest_report.json",
                    "backtest_report.txt",
                    "direction_performance.csv",
                    "drawdown_curve.png",
                    "equity_curve.png",
                    "exit_reason_performance.csv",
                    "monte_carlo_equity.png",
                    "monthly_performance.csv",
                    "symbol_performance.csv",
                    "trades.csv",
                    "yearly_performance.csv",
                },
            )


if __name__ == "__main__":
    unittest.main()
