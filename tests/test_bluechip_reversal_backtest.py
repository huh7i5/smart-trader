import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backtest_bluechip_reversal import add_features, evaluate_entry, fetch_yahoo_equity, paired_vs_direct


class BluechipReversalBacktestTests(unittest.TestCase):
    def test_yahoo_ohlc_is_adjusted_for_corporate_actions(self):
        timestamps = [int(value.timestamp()) for value in pd.date_range("2024-01-01", periods=300, tz="UTC")]
        payload = {
            "chart": {
                "result": [
                    {
                        "timestamp": timestamps,
                        "indicators": {
                            "quote": [{
                                "open": [100.0] * 300,
                                "high": [110.0] * 300,
                                "low": [90.0] * 300,
                                "close": [100.0] * 300,
                                "volume": [1000.0] * 300,
                            }],
                            "adjclose": [{"adjclose": [50.0] * 300}],
                        },
                    }
                ]
            }
        }

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return payload

        class Session:
            def get(self, *args, **kwargs):
                return Response()

        frame = fetch_yahoo_equity(Session(), "WDC", 5, 3)
        self.assertEqual(frame.iloc[0]["open"], 50.0)
        self.assertEqual(frame.iloc[0]["high"], 55.0)
        self.assertEqual(frame.iloc[0]["low"], 45.0)
        self.assertEqual(frame.iloc[0]["close"], 50.0)

    def test_entry_executes_at_next_bar_open(self):
        dates = pd.date_range("2026-01-01", periods=70, tz="UTC")
        frame = pd.DataFrame(
            {
                "date": dates,
                "open": [100.0] * 70,
                "high": [105.0] * 70,
                "low": [95.0] * 70,
                "close": [100.0] * 70,
                "volume": [1000.0] * 70,
            }
        )
        frame.loc[31, "open"] = 80.0
        result = evaluate_entry(frame, 30)
        self.assertEqual(result["signal_date"], "2026-01-31")
        self.assertEqual(result["entry_date"], "2026-02-01")
        self.assertGreater(result["entry_price"], 80.0)

    def test_deep_decline_is_an_alert_not_a_reversal(self):
        dates = pd.date_range("2026-01-01", periods=40, tz="UTC")
        closes = [100.0] * 25 + [98.0, 95.0, 92.0, 89.0, 86.0] + [86.0] * 10
        frame = pd.DataFrame(
            {
                "date": dates,
                "open": closes,
                "high": [value + 1 for value in closes],
                "low": [value - 1 for value in closes],
                "close": closes,
                "volume": [1000.0] * 40,
            }
        )
        featured = add_features(frame)
        row = featured.iloc[29]
        self.assertTrue(bool(row["deep_decline"]))
        self.assertFalse(bool(row["reversal_confirm"]))

    def test_paired_comparison_uses_the_same_decline_episode(self):
        direct = [{"episode_start": "2026-01-01", "return_5d_pct": -5.0, "mae_5d_pct": -8.0}]
        candidate = [{"episode_start": "2026-01-01", "return_5d_pct": 2.0, "mae_5d_pct": -3.0}]
        result = paired_vs_direct(candidate, direct)
        self.assertEqual(result["paired_events"], 1)
        self.assertEqual(result["5d"]["mean_return_delta_pct"], 7.0)
        self.assertEqual(result["5d"]["mean_mae_improvement_pct"], 5.0)


if __name__ == "__main__":
    unittest.main()
