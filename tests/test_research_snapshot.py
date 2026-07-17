import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from research_snapshot import (
    ResearchDataError,
    build_sec_ticker_map,
    build_technical_snapshot,
    extract_yahoo_history,
    extract_recent_filings,
    parse_rss_items,
)
from research_snapshot import _is_recent


def kline(index: int, *, taker_ratio: float = 0.6):
    open_price = 100 + index
    close = open_price + 1
    volume = 100
    return [
        index,
        open_price,
        close + 2,
        open_price - 2,
        close,
        volume,
        0,
        0,
        0,
        volume * taker_ratio,
        0,
        0,
    ]


class ResearchSnapshotTests(unittest.TestCase):
    def test_technical_snapshot_contains_all_required_indicators(self):
        daily = [kline(index) for index in range(60)]
        hourly = [kline(index) for index in range(6)]
        depth = {"bids": [[159, 20]], "asks": [[160, 10]]}
        ticker = {
            "lastPrice": "160",
            "priceChangePercent": "2.5",
            "quoteVolume": "1000000",
            "count": 200,
        }

        result = build_technical_snapshot(daily, hourly, depth, ticker)

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["above_sma_20"])
        self.assertTrue(result["above_sma_50"])
        self.assertEqual(result["rsi_14"], 100.0)
        self.assertTrue(result["market_structure_proxy"]["passed"])
        self.assertTrue(result["taker_flow_6h"]["passed"])

    def test_technical_snapshot_rejects_short_history(self):
        with self.assertRaises(ResearchDataError):
            build_technical_snapshot(
                [kline(index) for index in range(7)],
                [kline(index) for index in range(6)],
                {"bids": [[100, 1]], "asks": [[101, 1]]},
                {"lastPrice": "100", "priceChangePercent": "0"},
            )

    def test_technical_snapshot_marks_new_listing_partial(self):
        result = build_technical_snapshot(
            [kline(index) for index in range(20)],
            [kline(index) for index in range(6)],
            {"bids": [[119, 2]], "asks": [[120, 1]]},
            {"lastPrice": "120", "priceChangePercent": "1"},
        )

        self.assertEqual(result["status"], "partial")
        self.assertIsNotNone(result["sma_20"])
        self.assertIsNone(result["sma_50"])
        self.assertIsNone(result["change_30d_pct"])

    def test_underlying_stock_history_completes_new_bstock_indicators(self):
        history = extract_yahoo_history(
            {
                "chart": {
                    "result": [
                        {
                            "meta": {"symbol": "NVDA", "currency": "USD", "exchangeName": "NMS"},
                            "timestamp": [1_700_000_000 + 86_400 * i for i in range(60)],
                            "indicators": {"quote": [{"close": [100 + i for i in range(60)]}]},
                        }
                    ],
                    "error": None,
                }
            },
            requested_ticker="NVDA",
        )
        result = build_technical_snapshot(
            [kline(index) for index in range(20)],
            [kline(index) for index in range(6)],
            {"bids": [[119, 2]], "asks": [[120, 1]]},
            {"lastPrice": "120", "priceChangePercent": "1"},
            indicator_closes=history["closes"],
            history_basis=history["history_basis"],
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["history_days"], 60)
        self.assertEqual(result["history_basis"]["ticker"], "NVDA")
        self.assertIsNotNone(result["sma_50"])

    def test_news_filter_rejects_future_items(self):
        now = datetime(2026, 7, 17, 4, 0, tzinfo=timezone.utc)
        self.assertTrue(_is_recent("Fri, 17 Jul 2026 03:00:00 GMT", 72, now))
        self.assertFalse(_is_recent("Fri, 17 Jul 2026 06:00:00 GMT", 72, now))

    def test_sec_ticker_map_and_filing_urls_use_official_fields(self):
        ticker_map = build_sec_ticker_map(
            {"0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"}}
        )
        self.assertEqual(ticker_map["NVDA"]["cik_str"], 1045810)

        filings = extract_recent_filings(
            {
                "cik": 1045810,
                "filings": {
                    "recent": {
                        "form": ["8-K", "4", "10-Q"],
                        "filingDate": ["2026-07-16", "2026-07-15", "2026-05-20"],
                        "reportDate": ["2026-07-16", "2026-07-15", "2026-04-30"],
                        "accessionNumber": [
                            "0001045810-26-000001",
                            "0001045810-26-000002",
                            "0001045810-26-000003",
                        ],
                        "primaryDocument": ["nvda-8k.htm", "form4.xml", "nvda-10q.htm"],
                    }
                },
            }
        )

        self.assertEqual([row["form"] for row in filings], ["8-K", "10-Q"])
        self.assertIn("000104581026000001/nvda-8k.htm", filings[0]["url"])

    def test_rss_parser_preserves_source_and_timestamp(self):
        xml = """<?xml version="1.0"?>
        <rss><channel><item>
          <title>Verified headline</title>
          <link>https://example.com/article</link>
          <pubDate>Fri, 17 Jul 2026 04:00:00 GMT</pubDate>
          <source>Example Publisher</source>
        </item></channel></rss>"""

        items = parse_rss_items(xml, limit=5)

        self.assertEqual(items[0]["publisher"], "Example Publisher")
        self.assertEqual(items[0]["published_at"], "Fri, 17 Jul 2026 04:00:00 GMT")
        self.assertEqual(items[0]["discovery_url"], "https://example.com/article")


if __name__ == "__main__":
    unittest.main()
