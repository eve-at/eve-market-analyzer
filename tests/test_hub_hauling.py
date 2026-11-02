"""Tests for hub hauling calculations (SPECS/hub_hauling.md, section 6)"""
import unittest

from src.handlers.hub_hauling_handler import (
    match_order_books,
    apply_limits,
    build_cargo_plan,
    format_multibuy,
    LIMIT_MARKET,
    LIMIT_CARGO,
    LIMIT_BUDGET,
    LIMIT_RISK,
)

TAX = 0.075
ASKS = [(1050, 50), (1000, 100)]
BIDS = [(1100, 100, 1), (1200, 80, 1)]
VOLUME = 10


class MatchOrderBooksTest(unittest.TestCase):

    def test_spec_example_chunks(self):
        chunks = match_order_books(ASKS, BIDS, TAX)
        self.assertEqual([c['qty'] for c in chunks], [80, 20])
        self.assertAlmostEqual(chunks[0]['unit_profit'], 110)
        self.assertAlmostEqual(chunks[1]['unit_profit'], 17.5)

    def test_no_profit(self):
        self.assertEqual(match_order_books([(1000, 10)], [(1050, 10, 1)], TAX), [])

    def test_min_volume_bid_skipped_when_not_enough_asks(self):
        chunks = match_order_books([(1000, 5)], [(1200, 100, 10), (1100, 100, 1)], TAX)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]['qty'], 5)
        self.assertEqual(chunks[0]['sell_price'], 1100)

    def test_min_volume_bid_used_across_several_asks(self):
        chunks = match_order_books([(1000, 5), (1001, 5)], [(1200, 100, 10)], TAX)
        self.assertEqual(sum(c['qty'] for c in chunks), 10)


class ApplyLimitsTest(unittest.TestCase):

    def setUp(self):
        self.chunks = match_order_books(ASKS, BIDS, TAX)

    def test_unlimited(self):
        r = apply_limits(self.chunks, VOLUME, 1_000_000)
        self.assertEqual(r['qty'], 100)
        self.assertAlmostEqual(r['investment'], 100_000)
        self.assertAlmostEqual(r['revenue'], 109_150)
        self.assertAlmostEqual(r['profit'], 9_150)
        self.assertEqual(r['max_buy_price'], 1000)
        self.assertEqual(r['min_sell_price'], 1100)
        self.assertEqual(r['limited_by'], LIMIT_MARKET)

    def test_cargo_limit(self):
        r = apply_limits(self.chunks, VOLUME, 500)
        self.assertEqual(r['qty'], 50)
        self.assertAlmostEqual(r['investment'], 50_000)
        self.assertAlmostEqual(r['profit'], 5_500)
        self.assertEqual(r['limited_by'], LIMIT_CARGO)

    def test_budget_limit(self):
        r = apply_limits(self.chunks, VOLUME, 1_000_000, budget=30_000)
        self.assertEqual(r['qty'], 30)
        self.assertAlmostEqual(r['profit'], 3_300)
        self.assertEqual(r['limited_by'], LIMIT_BUDGET)

    def test_risk_limit(self):
        r = apply_limits(self.chunks, VOLUME, 1_000_000, budget=90_000, max_cargo_value=30_000)
        self.assertEqual(r['qty'], 30)
        self.assertEqual(r['limited_by'], LIMIT_RISK)

    def test_unit_does_not_fit(self):
        r = apply_limits(self.chunks, VOLUME, 5)
        self.assertEqual(r['qty'], 0)
        self.assertEqual(r['limited_by'], LIMIT_CARGO)


class CargoPlanTest(unittest.TestCase):

    def _deal(self, type_id, name, unit_volume, asks, bids):
        return {
            'type_id': type_id,
            'typeName': name,
            'unit_volume': unit_volume,
            'market_chunks': match_order_books(asks, bids, TAX),
        }

    def test_prefers_profit_per_m3_and_respects_cargo(self):
        dense = self._deal(1, "Dense", 1, [(100, 100)], [(200, 100, 1)])     # 85 ISK/m3
        bulky = self._deal(2, "Bulky", 10, [(1000, 100)], [(1200, 100, 1)])  # 11 ISK/m3
        plan = build_cargo_plan([bulky, dense], cargo_m3=150)
        qty = {i['typeName']: i['qty'] for i in plan['items']}
        self.assertEqual(qty, {"Dense": 100, "Bulky": 5})
        self.assertLessEqual(plan['volume'], 150)

    def test_respects_isk_cap(self):
        deal = self._deal(1, "Item", 1, ASKS, BIDS)
        plan = build_cargo_plan([deal], cargo_m3=1_000_000, budget=50_000, max_cargo_value=40_000)
        self.assertEqual(plan['items'][0]['qty'], 40)
        self.assertLessEqual(plan['investment'], 40_000)

    def test_multibuy_format(self):
        self.assertEqual(
            format_multibuy([{'typeName': "Tritanium", 'qty': 1000}, {'typeName': "Pyerite", 'qty': 5}]),
            "Tritanium 1000\nPyerite 5",
        )


if __name__ == "__main__":
    unittest.main()
