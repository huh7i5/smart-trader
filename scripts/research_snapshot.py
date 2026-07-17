"""Refresh technical, fundamental, and news evidence for live research.

The report is research evidence only. News discovery never creates a trade
permission, and unavailable sources remain explicit instead of being inferred.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from pre_trade_checklist import DEPTH_URL, KLINES_URL, retail_taker_flow, smart_money_proxy
from trader_runtime import (
    http_headers,
    iso_utc,
    load_config,
    normalize_symbol,
    proxy_dict,
    state_dir,
    symbol_id,
    utc_now,
    write_json_atomic,
)


EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
TICKER_24H_URL = "https://api.binance.com/api/v3/ticker/24hr"
PRODUCTS_URL = (
    "https://www.binance.com/bapi/asset/v2/public/asset-service/product/"
    "get-products?includeEtf=true"
)
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FED_PRESS_FEED_URL = "https://www.federalreserve.gov/feeds/press_all.xml"
GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
MATERIAL_FORMS = {"10-K", "10-Q", "8-K", "20-F", "6-K", "N-CSR", "N-CSRS", "NPORT-P"}


class ResearchDataError(RuntimeError):
    """Raised when a required evidence payload is absent or malformed."""


def _iso_from_millis(value: Any) -> str | None:
    try:
        return iso_utc(datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc))
    except (TypeError, ValueError, OSError):
        return None


def request_json(
    session: requests.Session,
    url: str,
    *,
    timeout: int,
    proxies: dict[str, str] | None,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    response = session.get(url, params=params, timeout=timeout, proxies=proxies, headers=headers)
    response.raise_for_status()
    payload = response.json()
    if payload is None:
        raise ResearchDataError(f"empty JSON response from {url}")
    return payload


def _pct_change(latest: float, earlier: float) -> float:
    if earlier == 0:
        raise ResearchDataError("cannot calculate change from zero")
    return (latest - earlier) / earlier * 100


def _sma(values: list[float], period: int) -> float:
    if len(values) < period:
        raise ResearchDataError(f"fewer than {period} values for SMA")
    return sum(values[-period:]) / period


def _rsi(values: list[float], period: int = 14) -> float:
    if len(values) <= period:
        raise ResearchDataError(f"fewer than {period + 1} values for RSI")
    deltas = [values[index] - values[index - 1] for index in range(1, len(values))]
    recent = deltas[-period:]
    average_gain = sum(max(delta, 0.0) for delta in recent) / period
    average_loss = sum(max(-delta, 0.0) for delta in recent) / period
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def build_technical_snapshot(
    daily: list[list[Any]],
    hourly: list[list[Any]],
    depth: dict[str, Any],
    ticker: dict[str, Any],
    *,
    indicator_closes: list[float] | None = None,
    history_basis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if len(daily) < 8:
        raise ResearchDataError("fewer than eight daily candles")
    binance_closes = [float(row[4]) for row in daily]
    closes = indicator_closes if indicator_closes and len(indicator_closes) >= 8 else binance_closes
    daily_returns = [
        (closes[index] - closes[index - 1]) / closes[index - 1]
        for index in range(1, len(closes))
        if closes[index - 1] != 0
    ]
    if len(daily_returns) < 7:
        raise ResearchDataError("fewer than seven daily returns")
    market_structure = smart_money_proxy(daily[-8:], depth)
    flow = retail_taker_flow(hourly)
    sma_20 = _sma(closes, 20) if len(closes) >= 20 else None
    sma_50 = _sma(closes, 50) if len(closes) >= 50 else None
    rsi_14 = _rsi(closes) if len(closes) >= 15 else None
    volatility_window = daily_returns[-min(20, len(daily_returns)):]
    return {
        "status": "ok" if len(closes) >= 51 else "partial",
        "fetched_at_utc": iso_utc(),
        "daily_last_close_utc": _iso_from_millis(daily[-1][6] if len(daily[-1]) > 6 else None),
        "hourly_last_close_utc": _iso_from_millis(hourly[-1][6] if len(hourly[-1]) > 6 else None),
        "history_days": len(closes),
        "binance_history_days": len(binance_closes),
        "history_basis": history_basis or {
            "type": "binance_market",
            "source": KLINES_URL,
        },
        "last_price": float(ticker["lastPrice"]),
        "change_24h_pct": round(float(ticker["priceChangePercent"]), 4),
        "change_7d_pct": round(_pct_change(closes[-1], closes[-8]), 4),
        "change_30d_pct": round(_pct_change(closes[-1], closes[-31]), 4) if len(closes) >= 31 else None,
        "sma_20": round(sma_20, 8) if sma_20 is not None else None,
        "sma_50": round(sma_50, 8) if sma_50 is not None else None,
        "above_sma_20": closes[-1] > sma_20 if sma_20 is not None else None,
        "above_sma_50": closes[-1] > sma_50 if sma_50 is not None else None,
        "rsi_14": round(rsi_14, 4) if rsi_14 is not None else None,
        "annualized_volatility_20d_pct": round(
            statistics.pstdev(volatility_window) * math.sqrt(365) * 100, 4
        ),
        "market_structure_proxy": market_structure,
        "taker_flow_6h": flow,
        "limitations": (
            "Indicators use Binance price, taker-volume, and visible depth data. "
            "When bStock history is short, longer-horizon indicators use the linked underlying "
            "stock and may diverge from the 24/7 bStock market. Indicators do not identify "
            "institutional traders or predict future returns."
        ),
    }


def extract_yahoo_history(payload: dict[str, Any], *, requested_ticker: str) -> dict[str, Any]:
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise ResearchDataError(f"underlying stock history error: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise ResearchDataError(f"no underlying stock history for {requested_ticker}")
    result = results[0]
    quotes = ((result.get("indicators") or {}).get("quote") or [])
    if not quotes:
        raise ResearchDataError(f"no underlying close data for {requested_ticker}")
    timestamps = result.get("timestamp") or []
    pairs = [
        (timestamp, float(value))
        for timestamp, value in zip(timestamps, quotes[0].get("close") or [])
        if value is not None
    ]
    closes = [value for _, value in pairs]
    if len(closes) < 8:
        raise ResearchDataError(f"fewer than eight underlying closes for {requested_ticker}")
    meta = result.get("meta") or {}
    return {
        "closes": closes,
        "history_basis": {
            "type": "underlying_stock_reference",
            "ticker": str(meta.get("symbol") or requested_ticker).upper(),
            "currency": meta.get("currency"),
            "exchange": meta.get("exchangeName"),
            "records": len(closes),
            "last_observation_utc": (
                iso_utc(datetime.fromtimestamp(pairs[-1][0], tz=timezone.utc)) if pairs else None
            ),
            "source": YAHOO_CHART_URL.format(ticker=requested_ticker),
            "official_exchange_feed": False,
        },
    }


def build_product_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if payload.get("code") != "000000" or not isinstance(payload.get("data"), list):
        raise ResearchDataError("Binance product tags are unavailable")
    return {
        row["s"]: row
        for row in payload["data"]
        if isinstance(row, dict) and isinstance(row.get("s"), str)
    }


def build_sec_ticker_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.values() if isinstance(payload, dict) else []
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("ticker"):
            continue
        result[str(row["ticker"]).upper()] = row
    return result


def extract_recent_filings(payload: dict[str, Any], *, limit: int = 6) -> list[dict[str, Any]]:
    recent = ((payload.get("filings") or {}).get("recent") or {})
    forms = recent.get("form") or []
    filings: list[dict[str, Any]] = []
    cik = int(payload.get("cik") or 0)
    for index, form in enumerate(forms):
        if form not in MATERIAL_FORMS:
            continue
        try:
            accession = recent["accessionNumber"][index]
            primary_document = recent["primaryDocument"][index]
            accession_compact = accession.replace("-", "")
            filings.append(
                {
                    "form": form,
                    "filing_date": recent["filingDate"][index],
                    "report_date": recent["reportDate"][index],
                    "accession_number": accession,
                    "primary_document": primary_document,
                    "url": (
                        f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                        f"{accession_compact}/{primary_document}"
                    ),
                }
            )
        except (IndexError, KeyError, TypeError):
            continue
        if len(filings) >= limit:
            break
    return filings


def _underlying_ticker(base_asset: str, is_bstock: bool) -> str:
    if is_bstock and base_asset.endswith("B") and len(base_asset) > 1:
        return base_asset[:-1]
    return base_asset


def build_market_fundamentals(
    market: dict[str, Any], ticker: dict[str, Any], product: dict[str, Any] | None
) -> dict[str, Any]:
    tags = sorted(product.get("tags") or []) if product else []
    return {
        "fetched_at_utc": iso_utc(),
        "trading_status": market.get("status"),
        "spot_trading_allowed": bool(market.get("isSpotTradingAllowed", True)),
        "base_asset": market.get("baseAsset"),
        "quote_asset": market.get("quoteAsset"),
        "asset_name": product.get("an") if product else None,
        "quote_volume_24h": float(ticker.get("quoteVolume") or 0),
        "trade_count_24h": int(ticker.get("count") or 0),
        "product_tags": tags,
    }


def _sec_user_agent(config: dict[str, Any], override: str | None) -> str | None:
    value = str(override or config.get("sec_user_agent") or "").strip()
    if not value or "YOUR_" in value.upper() or "EXAMPLE.COM" in value.upper():
        return None
    return value


def fetch_sec_fundamentals(
    session: requests.Session,
    *,
    ticker: str,
    ticker_map: dict[str, dict[str, Any]] | None,
    sec_user_agent: str | None,
    timeout: int,
    proxies: dict[str, str] | None,
) -> dict[str, Any]:
    if not sec_user_agent:
        return {
            "status": "configuration_required",
            "reason": "Set sec_user_agent to an app name and real contact email for SEC fair-access requests.",
        }
    if ticker_map is None:
        return {"status": "unavailable", "reason": "SEC ticker map was not fetched"}
    match = ticker_map.get(ticker)
    if not match:
        return {"status": "unavailable", "reason": f"No SEC ticker match for {ticker}"}
    cik = int(match["cik_str"])
    payload = request_json(
        session,
        SEC_SUBMISSIONS_URL.format(cik=cik),
        timeout=timeout,
        proxies=proxies,
        headers={"User-Agent": sec_user_agent, "Accept-Encoding": "gzip, deflate"},
    )
    return {
        "status": "ok",
        "fetched_at_utc": iso_utc(),
        "ticker": ticker,
        "cik": cik,
        "entity_name": payload.get("name") or match.get("title"),
        "sic": payload.get("sic"),
        "sic_description": payload.get("sicDescription"),
        "fiscal_year_end": payload.get("fiscalYearEnd"),
        "latest_material_filings": extract_recent_filings(payload),
        "limitations": "SEC filings are official disclosures, not a valuation or earnings-quality score.",
    }


def parse_rss_items(xml_text: str, *, limit: int) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    items: list[dict[str, Any]] = []
    for item in root.findall("./channel/item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or "").strip()
        source = (item.findtext("source") or "").strip()
        if not title or not link:
            continue
        items.append(
            {"title": title, "published_at": published, "publisher": source, "discovery_url": link}
        )
    return items


def _is_recent(published: str, lookback_hours: int, now: datetime) -> bool:
    try:
        value = parsedate_to_datetime(published).astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return False
    return now - timedelta(hours=lookback_hours) <= value <= now + timedelta(minutes=5)


def verify_article_url(
    session: requests.Session,
    url: str,
    *,
    timeout: int,
    proxies: dict[str, str] | None,
) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return {"url": url, "reachable": False, "reason": "unsupported URL scheme"}
    try:
        with session.get(url, timeout=timeout, proxies=proxies, stream=True) as response:
            return {
                "url": str(response.url),
                "http_status": response.status_code,
                "reachable": 200 <= response.status_code < 400,
            }
    except requests.RequestException as exc:
        return {"url": url, "http_status": None, "reachable": False, "reason": str(exc)}


def decode_google_url(url: str) -> dict[str, Any]:
    try:
        from googlenewsdecoder import new_decoderv1
    except ImportError:
        return {"status": False, "message": "googlenewsdecoder is not installed"}
    try:
        return new_decoderv1(url, interval=0.1)
    except Exception as exc:  # third-party decoder errors vary by Google response
        return {"status": False, "message": str(exc)}


def fetch_symbol_news(
    session: requests.Session,
    *,
    query: str,
    lookback_hours: int,
    limit: int,
    timeout: int,
    proxies: dict[str, str] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or utc_now()).astimezone(timezone.utc)
    days = max(1, math.ceil(lookback_hours / 24))
    params = {"q": f"{query} when:{days}d", "hl": "en-US", "gl": "US", "ceid": "US:en"}
    response = session.get(GOOGLE_NEWS_URL, params=params, timeout=timeout, proxies=proxies)
    response.raise_for_status()
    candidates = [
        item
        for item in parse_rss_items(response.text, limit=max(limit * 3, 15))
        if _is_recent(item["published_at"], lookback_hours, current)
    ][:max(limit * 3, 15)]
    verified: list[dict[str, Any]] = []
    processed: list[dict[str, Any]] = []
    for item in candidates:
        decoded = decode_google_url(item["discovery_url"])
        decoded_url = decoded.get("decoded_url") if decoded.get("status") else None
        if not decoded_url:
            item["verification"] = {"reachable": False, "reason": decoded.get("message", "decode failed")}
            processed.append(item)
            continue
        verification = verify_article_url(
            session, decoded_url, timeout=timeout, proxies=proxies
        )
        item["source_url"] = verification.get("url", decoded_url)
        item["verification"] = verification
        processed.append(item)
        if verification.get("reachable"):
            verified.append(item)
        if len(verified) >= 2 and len(processed) >= limit:
            break
    selected = verified + [item for item in processed if not item["verification"].get("reachable")]
    selected = selected[:limit]
    status = "ok" if len(verified) >= 2 else "partial" if candidates else "unavailable"
    return {
        "status": status,
        "fetched_at_utc": iso_utc(current),
        "query": query,
        "lookback_hours": lookback_hours,
        "discovered_count": len(candidates),
        "checked_source_count": len(processed),
        "verified_source_count": len(verified),
        "items": selected,
        "review_required": True,
        "limitations": (
            "Google News is discovery-only. Reachability does not establish relevance, accuracy, "
            "independence, or positive/negative impact; open and review original sources before trading."
        ),
    }


def fetch_fed_feed(
    session: requests.Session,
    *,
    timeout: int,
    proxies: dict[str, str] | None,
    limit: int = 5,
) -> dict[str, Any]:
    response = session.get(FED_PRESS_FEED_URL, timeout=timeout, proxies=proxies)
    response.raise_for_status()
    return {
        "status": "ok",
        "fetched_at_utc": iso_utc(),
        "source": FED_PRESS_FEED_URL,
        "items": parse_rss_items(response.text, limit=limit),
    }


def _symbol_news_query(underlying: str, asset_type: str, entity_name: str | None) -> str:
    if asset_type == "bstock":
        return f'"{underlying}" {entity_name or "stock"}'
    return f'"{underlying}" cryptocurrency'


def research_symbols(
    symbols: list[str],
    *,
    timeout: int = 20,
    news_lookback_hours: int = 72,
    news_limit: int = 5,
    sec_user_agent_override: str | None = None,
) -> dict[str, Any]:
    normalized_symbols = list(dict.fromkeys(normalize_symbol(symbol) for symbol in symbols))
    if not normalized_symbols:
        raise ValueError("at least one symbol is required")
    config = load_config()
    proxies = proxy_dict(config)
    sec_user_agent = _sec_user_agent(config, sec_user_agent_override)
    global_errors: list[dict[str, str]] = []
    results: list[dict[str, Any]] = []

    with requests.Session() as session:
        session.headers.update(http_headers(config))
        try:
            products = build_product_map(
                request_json(session, PRODUCTS_URL, timeout=timeout, proxies=proxies)
            )
        except (requests.RequestException, ResearchDataError, ValueError) as exc:
            products = {}
            global_errors.append({"scope": "binance_product_tags", "reason": str(exc)})

        try:
            macro = fetch_fed_feed(session, timeout=timeout, proxies=proxies)
        except (requests.RequestException, ET.ParseError) as exc:
            macro = {"status": "unavailable", "reason": str(exc), "source": FED_PRESS_FEED_URL}
            global_errors.append({"scope": "federal_reserve_feed", "reason": str(exc)})

        sec_ticker_map: dict[str, dict[str, Any]] | None = None
        if sec_user_agent:
            try:
                sec_ticker_map = build_sec_ticker_map(
                    request_json(
                        session,
                        SEC_TICKERS_URL,
                        timeout=timeout,
                        proxies=proxies,
                        headers={"User-Agent": sec_user_agent, "Accept-Encoding": "gzip, deflate"},
                    )
                )
            except (requests.RequestException, ResearchDataError, ValueError) as exc:
                global_errors.append({"scope": "sec_ticker_map", "reason": str(exc)})

        for normalized in normalized_symbols:
            api_symbol = symbol_id(normalized)
            product = products.get(api_symbol)
            tags = set(product.get("tags") or []) if product else set()
            is_bstock = "bStocks" in tags
            asset_type = "bstock" if is_bstock else "crypto" if product else "unknown"
            base_asset = normalized.split("/", 1)[0]
            underlying = _underlying_ticker(base_asset, is_bstock)
            row: dict[str, Any] = {
                "symbol": normalized,
                "asset_type": asset_type,
                "underlying": underlying,
            }

            market: dict[str, Any] | None = None
            ticker: dict[str, Any] | None = None
            try:
                exchange_info = request_json(
                    session,
                    EXCHANGE_INFO_URL,
                    params={"symbol": api_symbol},
                    timeout=timeout,
                    proxies=proxies,
                )
                markets = exchange_info.get("symbols") or []
                if not markets:
                    raise ResearchDataError(f"Binance returned no market for {api_symbol}")
                market = markets[0]
                ticker = request_json(
                    session,
                    TICKER_24H_URL,
                    params={"symbol": api_symbol},
                    timeout=timeout,
                    proxies=proxies,
                )
                daily = request_json(
                    session,
                    KLINES_URL,
                    params={"symbol": api_symbol, "interval": "1d", "limit": 60},
                    timeout=timeout,
                    proxies=proxies,
                )
                hourly = request_json(
                    session,
                    KLINES_URL,
                    params={"symbol": api_symbol, "interval": "1h", "limit": 6},
                    timeout=timeout,
                    proxies=proxies,
                )
                depth = request_json(
                    session,
                    DEPTH_URL,
                    params={"symbol": api_symbol, "limit": 100},
                    timeout=timeout,
                    proxies=proxies,
                )
                reference_history = None
                if is_bstock and len(daily) < 51:
                    try:
                        reference_history = extract_yahoo_history(
                            request_json(
                                session,
                                YAHOO_CHART_URL.format(ticker=underlying),
                                params={"range": "3mo", "interval": "1d"},
                                timeout=timeout,
                                proxies=proxies,
                            ),
                            requested_ticker=underlying,
                        )
                    except (requests.RequestException, ResearchDataError, ValueError) as exc:
                        row["underlying_history_error"] = str(exc)
                row["technical"] = build_technical_snapshot(
                    daily,
                    hourly,
                    depth,
                    ticker,
                    indicator_closes=(reference_history or {}).get("closes"),
                    history_basis=(reference_history or {}).get("history_basis"),
                )
            except (requests.RequestException, ResearchDataError, ValueError, KeyError) as exc:
                row["technical"] = {"status": "unavailable", "reason": str(exc)}

            if market and ticker:
                market_fundamentals = build_market_fundamentals(market, ticker, product)
                if is_bstock:
                    try:
                        sec = fetch_sec_fundamentals(
                            session,
                            ticker=underlying,
                            ticker_map=sec_ticker_map,
                            sec_user_agent=sec_user_agent,
                            timeout=timeout,
                            proxies=proxies,
                        )
                    except (requests.RequestException, ResearchDataError, ValueError) as exc:
                        sec = {"status": "unavailable", "reason": str(exc)}
                    row["fundamental"] = {
                        "status": "ok" if sec.get("status") == "ok" else "partial",
                        "market": market_fundamentals,
                        "official_disclosures": sec,
                    }
                else:
                    row["fundamental"] = {
                        "status": "proxy",
                        "market": market_fundamentals,
                        "limitations": (
                            "Binance market metadata is a liquidity/adoption proxy, not on-chain, "
                            "treasury, protocol-revenue, or issuer-fundamental evidence."
                        ),
                    }
            else:
                row["fundamental"] = {"status": "unavailable", "reason": "market metadata unavailable"}

            entity_name = str(product.get("an") or "").replace("(bStocks)", "").strip() if product else None
            disclosures = (row.get("fundamental") or {}).get("official_disclosures") or {}
            if disclosures.get("status") == "ok":
                entity_name = disclosures.get("entity_name")
            try:
                row["news"] = fetch_symbol_news(
                    session,
                    query=_symbol_news_query(underlying, asset_type, entity_name),
                    lookback_hours=news_lookback_hours,
                    limit=news_limit,
                    timeout=timeout,
                    proxies=proxies,
                )
            except (requests.RequestException, ET.ParseError, ValueError) as exc:
                row["news"] = {"status": "unavailable", "reason": str(exc), "review_required": True}
            results.append(row)

    complete = all(
        row["technical"].get("status") == "ok"
        and row["fundamental"].get("status") in {"ok", "proxy"}
        and row["news"].get("status") == "ok"
        for row in results
    ) and macro.get("status") == "ok"
    any_technical = any(
        row["technical"].get("status") in {"ok", "partial"} for row in results
    )
    return {
        "schema_version": 1,
        "status": "ok" if complete else "partial" if any_technical else "unavailable",
        "fetched_at_utc": iso_utc(),
        "record_count": len(results),
        "symbols": normalized_symbols,
        "macro_official": macro,
        "results": results,
        "errors": global_errors,
        "source": {
            "technical": [EXCHANGE_INFO_URL, TICKER_24H_URL, KLINES_URL, DEPTH_URL],
            "product_metadata": PRODUCTS_URL,
            "underlying_stock_history": YAHOO_CHART_URL,
            "fundamental_official": [SEC_TICKERS_URL, "https://data.sec.gov/submissions/"],
            "macro_official": FED_PRESS_FEED_URL,
            "news_discovery": GOOGLE_NEWS_URL,
        },
        "decision_policy": {
            "research_only": True,
            "news_requires_human_or_agent_review": True,
            "trade_permission_requires_separate_all_pass_checklist": True,
            "missing_dimension": "DATA_UNAVAILABLE",
        },
        "pipeline": {
            "universe": "binance_market_scan.py",
            "point_in_time_data_and_features": "research_snapshot.py",
            "signal_gate": "pre_trade_checklist.py",
            "portfolio_and_risk": "position sizing plus order_safety.py",
            "execution": "two-stage order preview and confirmation",
            "reconciliation": "check_portfolio.py after submission",
        },
    }


def print_summary(report: dict[str, Any], evidence_path: Path) -> None:
    print(
        f"RESEARCH SNAPSHOT | status={report['status']} | fetched={report['fetched_at_utc']} | "
        f"records={report['record_count']}"
    )
    for row in report["results"]:
        print(
            f"{row['symbol']:<14} technical={row['technical']['status']:<11} "
            f"fundamental={row['fundamental']['status']:<11} news={row['news']['status']}"
        )
    print(f"Evidence: {evidence_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh technical, fundamental, and news evidence in one snapshot"
    )
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--news-hours", type=int, default=72)
    parser.add_argument("--news-limit", type=int, default=5)
    parser.add_argument("--sec-user-agent", help="SEC-compliant app name and contact email")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = research_symbols(
            args.symbols,
            timeout=max(3, args.timeout),
            news_lookback_hours=max(24, min(args.news_hours, 24 * 30)),
            news_limit=max(1, min(args.news_limit, 10)),
            sec_user_agent_override=args.sec_user_agent,
        )
    except (ValueError, OSError) as exc:
        print(f"DATA_UNAVAILABLE: {exc}", file=sys.stderr)
        return 2

    stamp = report["fetched_at_utc"].replace(":", "").replace("-", "")
    latest = state_dir() / "latest_research_snapshot.json"
    archived = state_dir() / f"research_snapshot_{stamp}.json"
    write_json_atomic(latest, report)
    write_json_atomic(archived, report)
    if args.output:
        write_json_atomic(args.output.resolve(), report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_summary(report, latest)
    return 0 if report["status"] != "unavailable" else 2


if __name__ == "__main__":
    raise SystemExit(main())
