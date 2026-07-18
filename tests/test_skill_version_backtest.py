import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backtest_skill_versions import signal_amount, simulate_version


def comparison_frame() -> pd.DataFrame:
    rows = 80
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=rows).date,
            "open": [100.0] * rows,
            "high": [101.0] * rows,
            "low": [99.0] * rows,
            "close": [100.0] * rows,
            "volume": [1000.0] * rows,
            "fng": [50.0] * rows,
            "rsi_14": [50.0] * rows,
            "bb_lower": [90.0] * rows,
            "bar_sigma_rel": [1.0] * rows,
            "sigma_rel": [1.0] * rows,
            "checklist_passed": [False] * rows,
            "macro_passed": [True] * rows,
        }
    )
    return frame


class SkillVersionBacktestTests(unittest.TestCase):
    def test_relaxed_tactical_gate_can_bypass_failed_checklist(self):
        frame = comparison_frame()
        frame.loc[20, ["fng", "low"]] = [10.0, 80.0]
        self.assertEqual(signal_amount(frame, 20, relaxed_tactical_gate=False), 0.0)
        self.assertGreater(signal_amount(frame, 20, relaxed_tactical_gate=True), 0.0)

    def test_signal_fills_at_next_open(self):
        frame = comparison_frame()
        frame.loc[20, ["fng", "low"]] = [10.0, 80.0]
        frame.loc[21, "open"] = 75.0
        result = simulate_version(frame, list(frame.index), relaxed_tactical_gate=True)
        entry = result["entries"][0]
        self.assertEqual(entry["signal_date"], "2025-01-21")
        self.assertEqual(entry["entry_date"], "2025-01-22")
        self.assertGreater(entry["effective_entry_price"], 75.0)


if __name__ == "__main__":
    unittest.main()
