import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from Backtest.backtest_engine import BacktestEngine
from Backtest.Strategies.strategy_3_ORB.reporting import build_orb_analysis, save_orb_artifacts


def trades():
    return pd.DataFrame([
        {"symbol": "A", "direction": "LONG", "orb_range": 10, "entry_timestamp": "2024-01-02 10:00",
         "exit_timestamp": "2024-01-02 10:10", "exit_reason": "TARGET", "gross_pnl": 100,
         "transaction_cost": 0, "pnl": 100},
        {"symbol": "A", "direction": "LONG", "orb_range": 20, "entry_timestamp": "2024-02-02 10:00",
         "exit_timestamp": "2024-02-02 14:30", "exit_reason": "TIME", "gross_pnl": -50,
         "transaction_cost": 0, "pnl": -50},
        {"symbol": "B", "direction": "SHORT", "orb_range": 15, "entry_timestamp": "2025-01-02 10:00",
         "exit_timestamp": "2025-01-02 10:10", "exit_reason": "SL", "gross_pnl": -25,
         "transaction_cost": 0, "pnl": -25},
        {"symbol": "B", "direction": "SHORT", "orb_range": 12, "entry_timestamp": "2025-02-02 10:00",
         "exit_timestamp": "2025-02-02 10:10", "exit_reason": "TARGET", "gross_pnl": 75,
         "transaction_cost": 0, "pnl": 75},
    ])


class ORBReportTests(unittest.TestCase):
    def test_empty_run_still_writes_orb_artifacts(self):
        empty = BacktestEngine._empty_trades_dataframe()
        with tempfile.TemporaryDirectory() as folder:
            analysis = save_orb_artifacts(empty, folder)
            self.assertEqual(analysis["total_trades"], 0)
            self.assertTrue((Path(folder) / "trades.csv").is_file())

    def test_analysis_contains_direction_win_rate_and_exit_counts(self):
        analysis, _ = build_orb_analysis(trades())
        self.assertEqual(analysis["direction"]["LONG"]["win_rate"], 50.0)
        self.assertEqual(analysis["direction"]["SHORT"]["net_pnl"], 50.0)
        self.assertEqual(analysis["exit_reason"]["TIME"]["trades"], 1)
        self.assertEqual(analysis["orb_range"]["mean"], 14.25)

    def test_save_writes_trade_and_analysis_tables(self):
        with tempfile.TemporaryDirectory() as folder:
            save_orb_artifacts(trades(), folder)
            names = {p.name for p in Path(folder).iterdir()}
            expected = {"trades.csv", "orb_analysis.json", "direction_performance.csv",
                        "symbol_performance.csv", "exit_reason_performance.csv",
                        "monthly_performance.csv", "yearly_performance.csv",
                        "orb_range_statistics.csv"}
            self.assertTrue(expected <= names)
            saved = json.loads((Path(folder) / "orb_analysis.json").read_text())
            self.assertEqual(saved["total_trades"], 4)


if __name__ == "__main__":
    unittest.main()
