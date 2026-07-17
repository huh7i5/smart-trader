"""Create and validate URL-backed macro/news evidence for the checklist."""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from trader_runtime import (
    iso_utc,
    load_config,
    normalize_symbol,
    parse_utc,
    proxy_dict,
    read_json,
    state_dir,
    symbol_id,
    utc_now,
    write_json_atomic,
)


VALID_STATUSES = {"clear", "caution", "blocked"}


def evidence_path(symbol: str) -> Path:
    return state_dir() / f"macro_evidence_{symbol_id(symbol)}.json"


def validate_evidence(
    payload: dict[str, Any], *, symbol: str, max_age_hours: float
) -> tuple[bool, str]:
    if payload.get("status") not in VALID_STATUSES:
        return False, "invalid status"
    if normalize_symbol(payload.get("symbol", "")) != normalize_symbol(symbol):
        return False, "symbol mismatch"
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        return False, "no verified sources"
    if payload["status"] == "clear" and len(sources) < 2:
        return False, "clear status requires at least two independent sources"
    for source in sources:
        url = source.get("url", "") if isinstance(source, dict) else ""
        if urlparse(url).scheme not in {"http", "https"} or not source.get("reachable"):
            return False, "source URL was not verified as reachable"
    try:
        checked_at = parse_utc(payload["checked_at_utc"])
    except (KeyError, TypeError, ValueError):
        return False, "invalid checked_at_utc"
    if utc_now() - checked_at > timedelta(hours=max_age_hours):
        return False, "evidence is stale"
    return True, "ok"


def create_evidence(symbol: str, status: str, urls: list[str], note: str, timeout: int) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
    if status == "clear" and len(urls) < 2:
        raise ValueError("clear status requires at least two independent source URLs")
    config = load_config()
    proxies = proxy_dict(config)
    checked: list[dict[str, Any]] = []
    with requests.Session() as session:
        for url in urls:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                raise ValueError(f"Unsupported source URL: {url}")
            try:
                response = session.get(url, timeout=timeout, proxies=proxies, stream=True)
                reachable = 200 <= response.status_code < 400
                checked.append(
                    {"url": url, "http_status": response.status_code, "reachable": reachable}
                )
            except requests.RequestException as exc:
                checked.append({"url": url, "http_status": None, "reachable": False, "error": str(exc)})
    payload = {
        "schema_version": 1,
        "symbol": normalize_symbol(symbol),
        "status": status,
        "checked_at_utc": iso_utc(),
        "note": note,
        "sources": checked,
    }
    valid, reason = validate_evidence(
        payload,
        symbol=symbol,
        max_age_hours=float(config.get("macro_evidence_ttl_hours", 6)),
    )
    if not valid:
        raise ValueError(reason)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Create URL-backed macro/news evidence")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--status", choices=sorted(VALID_STATUSES), required=True)
    parser.add_argument("--source", action="append", default=[], help="Verified source URL; repeatable")
    parser.add_argument("--note", default="")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--validate", type=Path, help="Validate an existing evidence JSON instead")
    args = parser.parse_args()

    try:
        if args.validate:
            payload = read_json(args.validate)
            config = load_config()
            valid, reason = validate_evidence(
                payload,
                symbol=args.symbol,
                max_age_hours=float(config.get("macro_evidence_ttl_hours", 6)),
            )
            print(f"{'VALID' if valid else 'INVALID'}: {reason}")
            return 0 if valid else 2
        payload = create_evidence(
            args.symbol, args.status, args.source, args.note, max(3, args.timeout)
        )
        path = evidence_path(args.symbol)
        write_json_atomic(path, payload)
        print(f"Evidence saved: {path}")
        print(f"Status: {payload['status']} | sources: {len(payload['sources'])}")
        return 0
    except (ValueError, OSError) as exc:
        print(f"EVIDENCE_REJECTED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
