import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from binance_market_scan import MarketDataError, build_rankings


class MarketScanTests(unittest.TestCase):
    def setUp(self):
        self.exchange_info = {
            "symbols": [
                {"symbol": "NVDABUSDT", "status": "TRADING", "isSpotTradingAllowed": True, "baseAsset": "NVDAB", "quoteAsset": "USDT"},
                {"symbol": "BTCUSDT", "status": "TRADING", "isSpotTradingAllowed": True, "baseAsset": "BTC", "quoteAsset": "USDT"},
                {"symbol": "OLDBUSDT", "status": "BREAK", "isSpotTradingAllowed": True, "baseAsset": "OLDB", "quoteAsset": "USDT"},
            ]
        }
        self.tickers = [
            {"symbol": "NVDABUSDT", "lastPrice": "200", "priceChangePercent": "-3", "quoteVolume": "500000", "count": 100},
            {"symbol": "BTCUSDT", "lastPrice": "60000", "priceChangePercent": "2", "quoteVolume": "1000000", "count": 200},
            {"symbol": "OLDBUSDT", "lastPrice": "1", "priceChangePercent": "100", "quoteVolume": "900000", "count": 50},
        ]
        self.products = {
            "data": [
                {"s": "NVDABUSDT", "tags": ["bStocks"]},
                {"s": "BTCUSDT", "tags": ["pow"]},
                {"s": "OLDBUSDT", "tags": ["bStocks"]},
            ]
        }

    def test_discovers_bstock_from_live_tag_and_trading_status(self):
        report = build_rankings(
            self.exchange_info,
            self.tickers,
            self.products,
            category="bstock",
            quote="USDT",
            limit=10,
            min_quote_volume=0,
        )
        self.assertEqual(report["market_count"], 1)
        self.assertEqual(report["volume"][0]["symbol"], "NVDABUSDT")
        self.assertEqual(report["volume"][0]["asset_type"], "bstock")

    def test_crypto_category_excludes_bstocks(self):
        report = build_rankings(
            self.exchange_info,
            self.tickers,
            self.products,
            category="crypto",
            quote="USDT",
            limit=10,
            min_quote_volume=0,
        )
        self.assertEqual([row["symbol"] for row in report["volume"]], ["BTCUSDT"])

    def test_empty_result_fails_instead_of_inventing_rankings(self):
        with self.assertRaises(MarketDataError):
            build_rankings(
                self.exchange_info,
                self.tickers,
                self.products,
                category="bstock",
                quote="USDT",
                limit=10,
                min_quote_volume=999999999,
            )


if __name__ == "__main__":
    unittest.main()
