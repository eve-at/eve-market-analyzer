"""Tests for market fee calculations (SPECS/hub_trading.md, section 8.1)"""
import unittest

from src.handlers.fees import broker_fee_percent, sales_tax_percent, relist_rate


class FeesTest(unittest.TestCase):

    def test_broker_fee_positive_standings(self):
        self.assertAlmostEqual(broker_fee_percent(5, 2.0, 3.0), 1.38)

    def test_broker_fee_negative_faction_standing(self):
        self.assertAlmostEqual(broker_fee_percent(4, -1.0, 0), 1.83)

    def test_broker_fee_max_standings(self):
        self.assertAlmostEqual(broker_fee_percent(5, 10, 10), 1.0)

    def test_broker_fee_missing_standings(self):
        self.assertAlmostEqual(broker_fee_percent(0, None, None), 3.0)

    def test_sales_tax_accounting_5(self):
        self.assertAlmostEqual(sales_tax_percent(5), 3.375)

    def test_relist_rate(self):
        self.assertAlmostEqual(relist_rate(2.0, 4), 0.0052)


if __name__ == "__main__":
    unittest.main()
