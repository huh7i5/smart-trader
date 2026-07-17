import sys
import unittest
from datetime import timedelta
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from macro_evidence import validate_evidence
from trader_runtime import iso_utc, utc_now


class MacroEvidenceTests(unittest.TestCase):
    def payload(self):
        return {
            "symbol": "BTC/USDT",
            "status": "clear",
            "checked_at_utc": iso_utc(),
            "sources": [
                {"url": "https://example.com/one", "reachable": True},
                {"url": "https://example.com/two", "reachable": True},
            ],
        }

    def test_clear_requires_two_reachable_sources(self):
        valid, reason = validate_evidence(self.payload(), symbol="BTC", max_age_hours=6)
        self.assertTrue(valid, reason)
        payload = self.payload()
        payload["sources"] = payload["sources"][:1]
        valid, reason = validate_evidence(payload, symbol="BTC", max_age_hours=6)
        self.assertFalse(valid)
        self.assertIn("two", reason)

    def test_stale_evidence_is_rejected(self):
        payload = self.payload()
        payload["checked_at_utc"] = iso_utc(utc_now() - timedelta(hours=7))
        valid, reason = validate_evidence(payload, symbol="BTC", max_age_hours=6)
        self.assertFalse(valid)
        self.assertEqual(reason, "evidence is stale")

    def test_symbol_mismatch_is_rejected(self):
        valid, reason = validate_evidence(self.payload(), symbol="SOL", max_age_hours=6)
        self.assertFalse(valid)
        self.assertEqual(reason, "symbol mismatch")


if __name__ == "__main__":
    unittest.main()
