import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pre_trade_checklist import macro_check, retail_taker_flow, smart_money_proxy


def kline(open_price, high, low, close, volume, taker_buy):
    return [0, open_price, high, low, close, volume, 0, 0, 0, taker_buy, 0, 0]


class ChecklistLogicTests(unittest.TestCase):
    def test_retail_flow_uses_real_taker_buy_field(self):
        rows = [
            kline(100, 110, 90, 91, 100, 60),
            kline(91, 100, 90, 95, 100, 60),
        ]
        result = retail_taker_flow(rows)
        self.assertAlmostEqual(result["taker_buy_ratio"], 0.6)
        self.assertTrue(result["passed"])

    def test_market_structure_is_explicitly_a_proxy(self):
        daily = [kline(100 + i, 105 + i, 95 + i, 100 + i, 10, 5) for i in range(7)]
        depth = {"bids": [[100, 20]], "asks": [[101, 10]]}
        result = smart_money_proxy(daily, depth)
        self.assertTrue(result["passed"])
        self.assertIn("not ETF flow", result["limitations"])

    def test_negative_trend_cannot_be_overridden_by_order_book_depth(self):
        daily = [kline(100 - i, 105 - i, 95 - i, 100 - i, 10, 5) for i in range(7)]
        depth = {"bids": [[100, 100]], "asks": [[101, 1]]}
        result = smart_money_proxy(daily, depth)
        self.assertGreater(result["visible_bid_ask_notional_ratio"], 1.0)
        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "caution")

    def test_missing_macro_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"CRYPTO_SMART_TRADER_STATE_DIR": temp}):
                result = macro_check("BTC/USDT", {"macro_evidence_ttl_hours": 6})
        self.assertEqual(result["status"], "unknown")
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
