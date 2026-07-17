"""Shared, portable runtime helpers for the trading scripts."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config.json"
DEFAULT_STATE_DIR = ROOT_DIR / ".state"

DEFAULT_CONFIG: dict[str, Any] = {
    "proxy": "",
    "allow_live_trading": False,
    "testnet": False,
    "risk_per_trade_pct": 10,
    "min_cash_reserve_pct": 30,
    "proposal_ttl_minutes": 10,
    "checklist_ttl_minutes": 15,
    "macro_evidence_ttl_hours": 6,
    "core_symbols": ["BTC/USDT", "SOL/USDT", "LINK/USDT"],
    "allow_core_full_sell": False,
}


class ConfigurationError(RuntimeError):
    """Raised when required local configuration is missing or invalid."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def config_path() -> Path:
    override = os.environ.get("CRYPTO_SMART_TRADER_CONFIG")
    return Path(override).expanduser().resolve() if override else DEFAULT_CONFIG_PATH


def state_dir() -> Path:
    override = os.environ.get("CRYPTO_SMART_TRADER_STATE_DIR")
    path = Path(override).expanduser().resolve() if override else DEFAULT_STATE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_config(*, require_private: bool = False) -> dict[str, Any]:
    path = config_path()
    config = dict(DEFAULT_CONFIG)
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Cannot read config at {path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ConfigurationError(f"Config at {path} must contain a JSON object")
        config.update(loaded)

    if require_private:
        missing = [
            key
            for key in ("api_key", "api_secret")
            if not config.get(key) or str(config.get(key)).startswith("YOUR_")
        ]
        if missing:
            raise ConfigurationError(
                f"Missing {', '.join(missing)} in {path}. Copy resources/config_template.json first."
            )
    return config


def proxy_dict(config: dict[str, Any]) -> dict[str, str] | None:
    proxy = str(config.get("proxy") or "").strip()
    return {"http": proxy, "https": proxy} if proxy else None


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper().replace("-", "/")
    if "/" not in value:
        value = f"{value}/USDT"
    return value


def symbol_id(symbol: str) -> str:
    return normalize_symbol(symbol).replace("/", "")


def create_exchange(*, private: bool = False):
    """Create a Binance spot client; public clients never receive API credentials."""
    import ccxt

    config = load_config(require_private=private)
    options: dict[str, Any] = {
        "enableRateLimit": True,
        "timeout": 30000,
        "options": {
            "defaultType": "spot",
            "adjustForTimeDifference": True,
            "recvWindow": 60000,
            "fetchOpenOrders": {"warnWithoutSymbol": False},
        },
    }
    if private:
        options.update({"apiKey": config["api_key"], "secret": config["api_secret"]})
    exchange = ccxt.binance(options)
    proxies = proxy_dict(config)
    if proxies:
        exchange.proxies = proxies
    if config.get("testnet"):
        exchange.set_sandbox_mode(True)
    exchange.load_markets()
    return exchange


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
