import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backtest_crisis_reserve import POLICIES, _simulate


class CrisisReserveBacktestTests(unittest.TestCase):
    def _confirmed_crisis_frame(self):
        return pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=5, tz="UTC"),
                "AMD_open": [100.0] * 5,
                "AMD_high": [101.0, 101.0, 101.0, 101.0, 101.0],
                "AMD_low": [99.0, 98.0, 99.0, 99.0, 99.0],
                "AMD_close": [100.0] * 5,
                "AMD_rsi14": [40.0, 25.0, 35.0, 40.0, 45.0],
                "AMD_drawdown252_pct": [0.0, -25.0, -24.0, -10.0, -5.0],
            }
        )

    def test_hard_floor_does_not_spend_the_reserved_thirty_percent(self):
        result = _simulate(self._confirmed_crisis_frame(), ["AMD"], POLICIES[0])
        self.assertEqual(result["reserve_deployed_pct_initial"], 0.0)

    def test_staged_policy_waits_for_confirmation_then_uses_one_tranche(self):
        result = _simulate(self._confirmed_crisis_frame(), ["AMD"], POLICIES[1])
        self.assertAlmostEqual(result["reserve_deployed_pct_initial"], 9.993, places=6)
        self.assertEqual(result["trade_count"], 1)

    def test_aggressive_policy_deploys_all_cash_after_first_drop(self):
        result = _simulate(self._confirmed_crisis_frame(), ["AMD"], POLICIES[2])
        self.assertAlmostEqual(result["reserve_deployed_pct_initial"], 30.0, places=6)
        self.assertEqual(result["trade_count"], 1)


if __name__ == "__main__":
    unittest.main()
