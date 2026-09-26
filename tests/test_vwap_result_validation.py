import json
import tempfile
import unittest

import pandas as pd

from Backtest.Strategies.strategy_4_VWAP.validate_results import (
    audit_trade,
    validate_and_save,
    validate_trade_invariants,
)


def raw_candles():
    return pd.DataFrame([
        {"date": "2024-01-01", "time": "09:15", "symbol": "A", "open": 100,
         "high": 103, "low": 99, "close": 100, "volume": 100},
        {"date": "2024-01-01", "time": "09:30", "symbol": "A", "open": 100,
         "high": 110, "low": 100, "close": 108, "volume": 200},
        {"date": "2024-01-01", "time": "09:45", "symbol": "A", "open": 108,
         "high": 121, "low": 107, "close": 120, "volume": 150},
    ])


def valid_trade():
    return {
        "entry_timestamp": "2024-01-01 09:30", "exit_timestamp": "2024-01-01 09:45",
        "symbol": "A", "entry": 108.0, "exit_price": 108.54, "exit_reason": "TARGET",
        "quantity": 62, "equity_before": 100_000.0, "sl": 100.0, "target": 108.54,
        "direction": "LONG", "gross_pnl": 33.48, "transaction_cost": 0.0, "pnl": 33.48,
        "vwap": 104.22222222222223, "risk_per_unit": 8.0,
    }


class VWAPResultValidationTests(unittest.TestCase):
    def test_audit_checks_vwap_volume_levels_sizing_exit_and_pnl(self):
        checks = audit_trade(
            raw_candles(), valid_trade(), target_pct_from_entry=0.5, risk_fraction=0.005,
            ema_period=9,
        )
        self.assertEqual(
            set(checks),
            {"vwap", "cross", "volume", "entry", "same_day", "levels", "sizing", "exit", "pnl"},
        )
        json.dumps(checks)
        self.assertTrue(all(checks.values()))

    def test_validation_accepts_0930_entry_and_writes_json(self):
        trades = pd.DataFrame([valid_trade()] * 3)
        with tempfile.TemporaryDirectory() as folder:
            result = validate_and_save(
                raw_candles(), trades, folder, sample_each_direction=1,
                target_pct_from_entry=0.5, risk_fraction=0.005, ema_period=9,
            )
            saved = json.loads(open(f"{folder}/validation.json", encoding="utf-8").read())
        self.assertEqual(result["trades_checked"], 3)
        self.assertEqual(result["source_candle_audits"], 1)
        self.assertEqual(saved["manual_audits"][0]["direction"], "LONG")

    def test_invariants_reject_entry_before_configured_start(self):
        trade = valid_trade()
        trade["entry_timestamp"] = "2024-01-01 09:29"
        with self.assertRaisesRegex(AssertionError, "before 09:30"):
            validate_trade_invariants(pd.DataFrame([trade]), signal_start_time=pd.Timestamp("09:30").time())

    def test_invariants_reject_overnight_trade(self):
        trade = valid_trade()
        trade["exit_timestamp"] = "2024-01-02 09:45"
        with self.assertRaisesRegex(AssertionError, "overnight"):
            validate_trade_invariants(pd.DataFrame([trade]))


if __name__ == "__main__":
    unittest.main()
