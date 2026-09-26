import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from Backtest.backtest_engine import BacktestEngine
from Backtest.Strategies.strategy_4_VWAP.reporting import (
    build_vwap_analysis,
    save_vwap_artifacts,
)


def trades():
    return pd.DataFrame([
        {"symbol": "A", "direction": "LONG", "risk_per_unit": 4.0, "vwap": 101.0,
         "entry_timestamp": "2024-01-02 09:30", "exit_timestamp": "2024-01-02 10:00",
         "exit_reason": "TARGET", "gross_pnl": 100, "transaction_cost": 0, "pnl": 100},
        {"symbol": "A", "direction": "LONG", "risk_per_unit": 6.0, "vwap": 102.0,
         "entry_timestamp": "2024-02-02 09:45", "exit_timestamp": "2024-02-02 14:30",
         "exit_reason": "TIME", "gross_pnl": -50, "transaction_cost": 0, "pnl": -50},
        {"symbol": "B", "direction": "SHORT", "risk_per_unit": 5.0, "vwap": 201.0,
         "entry_timestamp": "2025-01-02 10:00", "exit_timestamp": "2025-01-02 10:15",
         "exit_reason": "SL", "gross_pnl": -25, "transaction_cost": 0, "pnl": -25},
        {"symbol": "B", "direction": "SHORT", "risk_per_unit": 9.0, "vwap": 202.0,
         "entry_timestamp": "2025-02-02 10:00", "exit_timestamp": "2025-02-02 10:15",
         "exit_reason": "9_EMA_CROSS", "gross_pnl": 75, "transaction_cost": 0, "pnl": 75},
    ])


class VWAPReportTests(unittest.TestCase):
    def test_empty_run_still_writes_vwap_artifacts(self):
        empty = BacktestEngine._empty_trades_dataframe()
        with tempfile.TemporaryDirectory() as folder:
            analysis = save_vwap_artifacts(empty, folder)
            self.assertEqual(analysis["total_trades"], 0)
            self.assertTrue((Path(folder) / "trades.csv").is_file())

    def test_analysis_contains_strategy_breakdowns_and_risk_statistics(self):
        analysis, _ = build_vwap_analysis(trades())
        self.assertEqual(analysis["direction"]["LONG"]["win_rate"], 50.0)
        self.assertEqual(analysis["direction"]["SHORT"]["net_pnl"], 50.0)
        self.assertEqual(analysis["exit_reason"]["9_EMA_CROSS"]["trades"], 1)
        self.assertEqual(analysis["risk_per_unit"]["mean"], 6.0)

    def test_save_writes_trade_and_analysis_tables(self):
        with tempfile.TemporaryDirectory() as folder:
            save_vwap_artifacts(trades(), folder)
            names = {path.name for path in Path(folder).iterdir()}
            expected = {
                "trades.csv", "vwap_analysis.json", "direction_performance.csv",
                "symbol_performance.csv", "exit_reason_performance.csv",
                "monthly_performance.csv", "yearly_performance.csv",
                "risk_per_unit_statistics.csv", "vwap_statistics.csv",
            }
            self.assertTrue(expected <= names)
            saved = json.loads((Path(folder) / "vwap_analysis.json").read_text())
            self.assertEqual(saved["total_trades"], 4)


if __name__ == "__main__":
    unittest.main()
