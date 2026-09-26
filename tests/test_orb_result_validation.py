import json
import unittest

import pandas as pd

from Backtest.Strategies.strategy_3_ORB.validate_results import audit_trade, validate_trade_invariants


class ORBResultValidationTests(unittest.TestCase):
    def test_manual_audit_values_are_json_serializable(self):
        raw = pd.DataFrame([
            {"date": "2024-01-01", "time": "09:15", "symbol": "A", "high": 105, "low": 95, "close": 100},
            {"date": "2024-01-01", "time": "10:00", "symbol": "A", "high": 108, "low": 105, "close": 106},
            {"date": "2024-01-01", "time": "10:05", "symbol": "A", "high": 117, "low": 110, "close": 116},
        ])
        trade = {"entry_timestamp": "2024-01-01 10:00", "exit_timestamp": "2024-01-01 10:05",
                 "symbol": "A", "entry": 106, "exit_price": 116, "exit_reason": "TARGET",
                 "quantity": 5, "equity_before": 100_000, "sl": 101, "target": 116,
                 "direction": "LONG", "gross_pnl": 50, "transaction_cost": 0, "pnl": 50,
                 "orb_high": 105, "orb_low": 95, "orb_range": 10}
        result = audit_trade(raw, trade, sl_range_multiplier=0.5,
                             target_range_multiplier=1.0)
        json.dumps(result)
        self.assertEqual(set(result), {"orb", "entry", "same_day", "levels", "sizing", "exit", "pnl"})
        self.assertTrue(all(result.values()))

    def test_audit_respects_custom_half_range_target(self):
        raw = pd.DataFrame([
            {"date": "2024-01-01", "time": "09:15", "symbol": "A", "high": 105, "low": 95, "close": 100},
            {"date": "2024-01-01", "time": "09:30", "symbol": "A", "high": 108, "low": 105, "close": 106},
            {"date": "2024-01-01", "time": "09:35", "symbol": "A", "high": 111, "low": 106, "close": 110},
        ])
        trade = {"entry_timestamp": "2024-01-01 09:30", "exit_timestamp": "2024-01-01 09:35",
                 "symbol": "A", "entry": 106, "exit_price": 111, "exit_reason": "TARGET",
                 "quantity": 5, "equity_before": 100_000, "sl": 101, "target": 111,
                 "direction": "LONG", "gross_pnl": 25, "transaction_cost": 0, "pnl": 25,
                 "orb_high": 105, "orb_low": 95, "orb_range": 10}
        result = audit_trade(raw, trade, orb_end=pd.Timestamp("09:30").time(),
                             sl_range_multiplier=0.5,
                             target_range_multiplier=0.5)
        self.assertTrue(result["levels"])
        self.assertTrue(result["exit"])

    def test_rejects_entry_before_orb_is_complete(self):
        trades = pd.DataFrame([{"entry_timestamp": "2024-01-01 09:55", "exit_timestamp": "2024-01-01 10:05",
                                "entry": 100, "exit_price": 101, "quantity": 1, "direction": "LONG",
                                "gross_pnl": 1, "transaction_cost": 0, "pnl": 1,
                                "orb_high": 99, "orb_low": 90, "orb_range": 9}])
        with self.assertRaisesRegex(AssertionError, "before 10:00"):
            validate_trade_invariants(trades, orb_end=pd.Timestamp("10:00").time())

    def test_custom_orb_end_controls_earliest_valid_entry(self):
        trades = pd.DataFrame([{"entry_timestamp": "2024-01-01 09:30", "exit_timestamp": "2024-01-01 10:05",
                                "entry": 100, "exit_price": 101, "quantity": 1, "direction": "LONG",
                                "gross_pnl": 1, "transaction_cost": 0, "pnl": 1,
                                "orb_high": 99, "orb_low": 90, "orb_range": 9}])
        result = validate_trade_invariants(trades, orb_end=pd.Timestamp("09:30").time())
        self.assertEqual(result["pre_orb_entries"], 0)

    def test_rejects_overnight_trade(self):
        trades = pd.DataFrame([{"entry_timestamp": "2024-01-01 10:00", "exit_timestamp": "2024-01-02 10:05",
                                "entry": 100, "exit_price": 101, "quantity": 1, "direction": "LONG",
                                "gross_pnl": 1, "transaction_cost": 0, "pnl": 1,
                                "orb_high": 99, "orb_low": 90, "orb_range": 9}])
        with self.assertRaisesRegex(AssertionError, "overnight"):
            validate_trade_invariants(trades)

    def test_accepts_consistent_short_trade(self):
        trades = pd.DataFrame([{"entry_timestamp": "2024-01-01 10:00", "exit_timestamp": "2024-01-01 10:05",
                                "entry": 94, "exit_price": 84, "quantity": 5, "direction": "SHORT",
                                "gross_pnl": 50, "transaction_cost": 2, "pnl": 48,
                                "orb_high": 105, "orb_low": 95, "orb_range": 10}])
        result = validate_trade_invariants(trades)
        self.assertEqual(result["overnight_trades"], 0)


if __name__ == "__main__":
    unittest.main()
