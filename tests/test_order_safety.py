import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from order_safety import (
    SafetyError,
    create_proposal,
    load_proposal,
    lock_proposal_for_submission,
    validate_buy_risk,
    validate_checklist,
)
from trader_runtime import iso_utc, write_json_atomic


class FakeExchange:
    markets = {"BTC/USDT": {}}

    def fetch_balance(self):
        return {
            "USDT": {"free": 600, "total": 600},
            "total": {"USDT": 600, "BTC": 0.01},
        }

    def fetch_ticker(self, symbol):
        if symbol != "BTC/USDT":
            raise KeyError(symbol)
        return {"last": 40000}


class LowCashExchange(FakeExchange):
    def fetch_balance(self):
        return {
            "USDT": {"free": 350, "total": 350},
            "total": {"USDT": 350, "BTC": 0.01625},
        }


class OrderSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.config = root / "config.json"
        self.state = root / "state"
        self.config.write_text(
            json.dumps(
                {
                    "api_key": "test",
                    "api_secret": "test",
                    "risk_per_trade_pct": 10,
                    "min_cash_reserve_pct": 30,
                    "proposal_ttl_minutes": 10,
                }
            ),
            encoding="utf-8",
        )
        self.env = patch.dict(
            os.environ,
            {
                "CRYPTO_SMART_TRADER_CONFIG": str(self.config),
                "CRYPTO_SMART_TRADER_STATE_DIR": str(self.state),
            },
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_buy_risk_enforces_trade_cap(self):
        snapshot = validate_buy_risk(FakeExchange(), "BTC/USDT", 50)
        self.assertEqual(snapshot["account_value_usdt"], 1000)
        with self.assertRaises(SafetyError):
            validate_buy_risk(FakeExchange(), "BTC/USDT", 150)
        with self.assertRaises(SafetyError):
            validate_buy_risk(LowCashExchange(), "BTC/USDT", 60)

    def test_checklist_must_match_and_be_recent(self):
        path = self.state / "latest_checklist_BTCUSDT.json"
        write_json_atomic(
            path,
            {
                "symbol": "BTC/USDT",
                "all_pass": True,
                "verdict": "trade_allowed",
                "checked_at_utc": iso_utc(),
            },
        )
        result = validate_checklist("BTC", max_age_minutes=15)
        self.assertEqual(result["path"], str(path))
        with self.assertRaises(SafetyError):
            validate_checklist("SOL", max_age_minutes=15)

    def test_proposal_is_bound_to_exact_order(self):
        proposal = create_proposal(
            action="limit_buy",
            params={"symbol": "BTC/USDT", "price": 50000.0},
            checklist=None,
            snapshot={},
        )
        loaded = load_proposal(
            proposal["token"],
            action="limit_buy",
            params={"symbol": "BTC/USDT", "price": 50000.0},
        )
        self.assertEqual(loaded["token"], proposal["token"])
        with self.assertRaises(SafetyError):
            load_proposal(
                proposal["token"],
                action="limit_buy",
                params={"symbol": "BTC/USDT", "price": 49000.0},
            )
        lock_proposal_for_submission(proposal)
        with self.assertRaises(SafetyError):
            load_proposal(
                proposal["token"],
                action="limit_buy",
                params={"symbol": "BTC/USDT", "price": 50000.0},
            )


if __name__ == "__main__":
    unittest.main()
