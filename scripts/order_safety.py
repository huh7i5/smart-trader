"""Two-step order proposals and code-enforced account risk limits."""

from __future__ import annotations

import re
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Any

from trader_runtime import (
    iso_utc,
    load_config,
    normalize_symbol,
    parse_utc,
    read_json,
    state_dir,
    symbol_id,
    utc_now,
    write_json_atomic,
)


class SafetyError(RuntimeError):
    """Raised when an order violates a hard safety requirement."""


def proposal_path(token: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{12,80}", token):
        raise SafetyError("invalid proposal token")
    return state_dir() / f"proposal_{token}.json"


def validate_checklist(symbol: str, *, max_age_minutes: float) -> dict[str, Any]:
    path = state_dir() / f"latest_checklist_{symbol_id(symbol)}.json"
    if not path.exists():
        raise SafetyError(f"missing checklist evidence: {path}")
    payload = read_json(path)
    if normalize_symbol(payload.get("symbol", "")) != normalize_symbol(symbol):
        raise SafetyError("checklist symbol mismatch")
    if not payload.get("all_pass") or payload.get("verdict") != "trade_allowed":
        raise SafetyError("latest checklist does not allow trading")
    try:
        checked_at = parse_utc(payload["checked_at_utc"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SafetyError("checklist has an invalid timestamp") from exc
    if utc_now() - checked_at > timedelta(minutes=max_age_minutes):
        raise SafetyError("checklist evidence is stale")
    return {"path": str(path), "checked_at_utc": payload["checked_at_utc"]}


def account_snapshot(exchange, symbol: str, cost_usdt: float) -> dict[str, float]:
    balance = exchange.fetch_balance()
    usdt_free = float(balance.get("USDT", {}).get("free", 0) or 0)
    usdt_total = float(balance.get("USDT", {}).get("total", 0) or 0)
    account_value = usdt_total
    totals = balance.get("total") or {}
    for asset, raw_amount in totals.items():
        amount = float(raw_amount or 0)
        if amount <= 0 or asset == "USDT":
            continue
        pair = f"{asset}/USDT"
        if pair not in exchange.markets:
            continue
        try:
            ticker = exchange.fetch_ticker(pair)
            account_value += amount * float(ticker["last"])
        except Exception:
            continue
    if account_value <= 0:
        raise SafetyError("could not calculate a positive account value")
    return {
        "account_value_usdt": account_value,
        "usdt_free": usdt_free,
        "usdt_after_order": usdt_free - cost_usdt,
    }


def validate_buy_risk(exchange, symbol: str, cost_usdt: float) -> dict[str, float]:
    if cost_usdt <= 0:
        raise SafetyError("order cost must be positive")
    config = load_config(require_private=True)
    snapshot = account_snapshot(exchange, symbol, cost_usdt)
    max_trade = snapshot["account_value_usdt"] * float(config["risk_per_trade_pct"]) / 100
    minimum_cash = snapshot["account_value_usdt"] * float(config["min_cash_reserve_pct"]) / 100
    if cost_usdt > snapshot["usdt_free"]:
        raise SafetyError(
            f"insufficient USDT: requested {cost_usdt:.2f}, free {snapshot['usdt_free']:.2f}"
        )
    if cost_usdt > max_trade:
        raise SafetyError(
            f"trade exceeds {config['risk_per_trade_pct']}% cap: {cost_usdt:.2f} > {max_trade:.2f}"
        )
    if snapshot["usdt_after_order"] < minimum_cash:
        raise SafetyError(
            f"trade would break {config['min_cash_reserve_pct']}% cash reserve: "
            f"remaining {snapshot['usdt_after_order']:.2f} < required {minimum_cash:.2f}"
        )
    snapshot.update({"max_trade_usdt": max_trade, "minimum_cash_usdt": minimum_cash})
    return snapshot


def create_proposal(
    *, action: str, params: dict[str, Any], checklist: dict[str, Any] | None, snapshot: dict[str, Any]
) -> dict[str, Any]:
    config = load_config(require_private=True)
    token = secrets.token_urlsafe(18)
    created = utc_now()
    payload = {
        "schema_version": 1,
        "token": token,
        "action": action,
        "params": params,
        "created_at_utc": iso_utc(created),
        "expires_at_utc": iso_utc(
            created + timedelta(minutes=float(config.get("proposal_ttl_minutes", 10)))
        ),
        "checklist": checklist,
        "account_snapshot": snapshot,
        "consumed": False,
    }
    write_json_atomic(proposal_path(token), payload)
    return payload


def load_proposal(token: str, *, action: str, params: dict[str, Any]) -> dict[str, Any]:
    path = proposal_path(token)
    if not path.exists():
        raise SafetyError("proposal token not found")
    payload = read_json(path)
    if payload.get("consumed"):
        raise SafetyError("proposal token has already been consumed")
    if payload.get("action") != action or payload.get("params") != params:
        raise SafetyError("proposal does not match this exact order")
    try:
        expires = parse_utc(payload["expires_at_utc"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SafetyError("proposal has an invalid expiry") from exc
    if utc_now() >= expires:
        raise SafetyError("proposal token has expired")
    return payload


def assert_order_execution_enabled() -> dict[str, Any]:
    config = load_config(require_private=True)
    if not config.get("testnet") and not config.get("allow_live_trading"):
        raise SafetyError(
            "live trading is disabled; set allow_live_trading=true only after reviewing the proposal"
        )
    return config


def consume_proposal(payload: dict[str, Any], order_id: str | None) -> None:
    payload["consumed"] = True
    payload["consumed_at_utc"] = iso_utc()
    payload["submission_state"] = "submitted"
    payload["order_id"] = order_id
    write_json_atomic(proposal_path(payload["token"]), payload)


def lock_proposal_for_submission(payload: dict[str, Any]) -> None:
    """Make retries impossible before the network request enters an unknown state."""
    payload["consumed"] = True
    payload["submission_state"] = "submitting"
    payload["submission_started_at_utc"] = iso_utc()
    write_json_atomic(proposal_path(payload["token"]), payload)


def checklist_for_buy(symbol: str, mode: str) -> dict[str, Any] | None:
    config = load_config(require_private=True)
    if mode == "baseline":
        return None
    return validate_checklist(
        symbol,
        max_age_minutes=float(config.get("checklist_ttl_minutes", 15)),
    )
