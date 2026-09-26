import unittest

from engines.position_sizing_engine import PositionSizingEngine


class RiskPositionSizingTests(unittest.TestCase):
    def test_risk_quantity_uses_quarter_percent_equity_and_stop_distance(self):
        sizing = PositionSizingEngine(100_000, 4)
        position = sizing.size_position("A", 100, risk_per_unit=2.5, risk_fraction=0.0025)
        self.assertEqual(position.quantity, 100)
        self.assertEqual(position.equity_before, 100_000)

    def test_profitable_short_increases_equity_and_next_risk_budget(self):
        sizing = PositionSizingEngine(100_000, 4)
        first = sizing.size_position("A", 100, direction="SHORT", risk_per_unit=5,
                                     risk_fraction=0.0025)
        self.assertEqual(first.quantity, 50)
        sizing.close_position("A", 90)
        second = sizing.size_position("B", 100, risk_per_unit=5, risk_fraction=0.0025)
        self.assertEqual(sizing.current_equity, 100_500)
        self.assertEqual(second.quantity, 50)

    def test_cost_reduces_realized_equity(self):
        sizing = PositionSizingEngine(10_000, 1)
        sizing.size_position("A", 100, direction="SHORT", risk_per_unit=5, risk_fraction=0.0025)
        sizing.close_position("A", 90, transaction_cost=2)
        self.assertEqual(sizing.current_equity, 10_048)

    def test_non_positive_risk_is_rejected(self):
        sizing = PositionSizingEngine(10_000, 1)
        with self.assertRaises(ValueError):
            sizing.size_position("A", 100, risk_per_unit=0, risk_fraction=0.0025)


if __name__ == "__main__":
    unittest.main()
