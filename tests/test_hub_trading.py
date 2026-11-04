"""Tests for hub trading calculations (SPECS/hub_trading.md, section 8.2)"""
import unittest

from src.handlers.hub_hauling_handler import (
    apply_limits,
    build_cargo_plan,
    trip_hours,
    isk_per_hour,
    LIMIT_MARKET,
    LIMIT_DEMAND,
)
from src.handlers.hub_trading_handler import (
    sell_order_net_price,
    build_sell_order_chunks,
    demand_quantity,
    days_to_sell,
    fair_market_share,
    apply_min_broker_fee,
)
from src.handlers.fees import relist_rate
from src.utils.price_calculator import get_next_sell_tick

TAX = 0.04
BROKER_FEE = 0.02
ASKS = [(1050, 50), (1000, 100)]
BEST_ASK_DST = 1300
VOLUME = 10


class SellOrderChunksTest(unittest.TestCase):

    def setUp(self):
        self.sell_price = get_next_sell_tick(BEST_ASK_DST)
        self.net = sell_order_net_price(self.sell_price, TAX, BROKER_FEE, 0, 0)
        self.chunks = build_sell_order_chunks(ASKS, self.sell_price, self.net)

    def test_sell_price_one_tick_below(self):
        self.assertEqual(self.sell_price, 1299)
        self.assertAlmostEqual(self.net, 1221.06)

    def test_chunks(self):
        self.assertEqual([c['qty'] for c in self.chunks], [100, 50])
        self.assertAlmostEqual(self.chunks[0]['unit_profit'] * 100, 22_106)
        self.assertAlmostEqual(self.chunks[1]['unit_profit'] * 50, 8_553)

    def test_unlimited(self):
        r = apply_limits(self.chunks, VOLUME, 1_000_000)
        self.assertEqual(r['qty'], 150)
        self.assertAlmostEqual(r['investment'], 152_500)
        self.assertAlmostEqual(r['profit'], 30_659)
        self.assertEqual(r['limited_by'], LIMIT_MARKET)

    def test_demand_limit(self):
        max_qty = demand_quantity(20, 25, 7)
        self.assertEqual(max_qty, 35)
        r = apply_limits(self.chunks, VOLUME, 1_000_000, max_qty=max_qty)
        self.assertEqual(r['qty'], 35)
        self.assertAlmostEqual(r['profit'], 7_737.10)
        self.assertEqual(r['limited_by'], LIMIT_DEMAND)
        self.assertAlmostEqual(days_to_sell(r['qty'], 20, 25), 7.0)

    def test_relists(self):
        net = sell_order_net_price(self.sell_price, TAX, BROKER_FEE, relist_rate(2.0, 4), 2)
        self.assertAlmostEqual(net, 1207.5504)

    def test_unprofitable_asks_are_skipped(self):
        self.assertEqual(build_sell_order_chunks([(1300, 10)], 1299, 1221.06), [])

    def test_min_broker_fee(self):
        r = apply_limits(self.chunks, VOLUME, 1_000_000, max_qty=1)
        profit_before = r['profit']
        apply_min_broker_fee(r, self.sell_price, BROKER_FEE)
        # Broker fee of 1 unit is 25.98 ISK, so 74.02 ISK surcharge up to the 100 ISK minimum
        self.assertAlmostEqual(profit_before - r['profit'], 100 - 1299 * BROKER_FEE)


class CargoPlanDemandTest(unittest.TestCase):

    def test_plan_respects_max_qty(self):
        sell_price = 1299
        net = sell_order_net_price(sell_price, TAX, BROKER_FEE, 0, 0)
        deal = {
            'type_id': 1,
            'typeName': "Item",
            'unit_volume': VOLUME,
            'market_chunks': build_sell_order_chunks(ASKS, sell_price, net),
            'max_qty': 35,
        }
        plan = build_cargo_plan([deal], cargo_m3=1_000_000)
        self.assertEqual(plan['items'][0]['qty'], 35)

    def test_plan_drops_items_with_zero_max_qty(self):
        deal = {
            'type_id': 1,
            'typeName': "Item",
            'unit_volume': VOLUME,
            'market_chunks': build_sell_order_chunks(ASKS, 1299, 1221.06),
            'max_qty': 0,
        }
        self.assertEqual(build_cargo_plan([deal], cargo_m3=1_000_000)['items'], [])


class FairShareTest(unittest.TestCase):

    def test_user_share_without_competitors(self):
        self.assertEqual(fair_market_share(20, 0), 20)

    def test_equal_split_with_many_competitors(self):
        # 13 competitors: 1/14 of the market instead of 20%
        self.assertAlmostEqual(fair_market_share(20, 13), 100 / 14)

    def test_user_share_lower_than_split(self):
        self.assertEqual(fair_market_share(20, 2), 20)


class CargoPlanLimitsTest(unittest.TestCase):

    def _deal(self, type_id, unit_volume, price, qty, unit_profit):
        return {
            'type_id': type_id,
            'typeName': f"Item {type_id}",
            'unit_volume': unit_volume,
            'market_chunks': [{'qty': qty, 'buy_price': price, 'sell_price': price + unit_profit,
                               'net_sell_price': price + unit_profit, 'unit_profit': unit_profit}],
        }

    def test_min_investment_drops_cheap_items(self):
        # Rocket: 4 ISK, only 1 unit available - very dense but worth 4 ISK of investment
        rocket = self._deal(1, 0.05, 4, 1, 10)
        skin = self._deal(2, 0.01, 20_000_000, 1, 5_000_000)
        plan = build_cargo_plan([rocket, skin], cargo_m3=100, min_investment=1_000_000)
        self.assertEqual([i['type_id'] for i in plan['items']], [2])

    def test_item_cut_below_min_investment_frees_space_for_others(self):
        # Greedy order is A, B, C. A fills 90 m3; B gets only the remaining 10 units
        # (1,000 ISK) and is dropped; its space goes to C which reaches the minimum
        a = self._deal(1, 1, 1_000, 90, 1_000)
        b = self._deal(2, 1, 100, 1_000, 50)
        c = self._deal(3, 1, 10_000, 10, 40)
        plan = build_cargo_plan([a, b, c], cargo_m3=100, min_investment=50_000)
        qty = {i['type_id']: i['qty'] for i in plan['items']}
        self.assertEqual(qty, {1: 90, 3: 10})

    def test_max_items(self):
        deals = [self._deal(i, 1, 1_000, 10, 100 + i) for i in range(10)]
        plan = build_cargo_plan(deals, cargo_m3=1_000, max_items=3)
        self.assertEqual(len(plan['items']), 3)
        self.assertEqual({i['type_id'] for i in plan['items']}, {9, 8, 7})


class TripTest(unittest.TestCase):

    def test_isk_per_hour(self):
        hours = trip_hours(45, 60, 10)
        self.assertAlmostEqual(hours, 0.75 + 10 / 60)
        self.assertAlmostEqual(isk_per_hour(100_000_000, hours), 109_090_909.09, places=1)

    def test_unknown_duration(self):
        self.assertIsNone(isk_per_hour(100, 0))


if __name__ == "__main__":
    unittest.main()
