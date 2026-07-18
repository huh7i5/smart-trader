"""Event study for direct versus confirmed entries after deep blue-chip declines.

This is a research-only backtest. It uses finalized daily bars, executes signals
at the next session open, and never changes live trade permissions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from trader_runtime import iso_utc, load_config, proxy_dict, state_dir, write_json_atomic


BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
ROUND_TRIP_COST = 0.002
HORIZONS = (5, 20, 60)


class BacktestDataError(RuntimeError):
    """Raised when historical input is missing or malformed."""


def _finalized_daily_cutoff_ms() -> int:
    now = datetime.now(timezone.utc)
    today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return int(today.timestamp() * 1000)


def fetch_binance_btc(session: requests.Session, years: int, timeout: int, proxies=None) -> pd.DataFrame:
    start = datetime.now(timezone.utc) - timedelta(days=366 * years + 90)
    since = int(start.timestamp() * 1000)
    cutoff = _finalized_daily_cutoff_ms()
    rows: list[list[Any]] = []
    while since < cutoff:
        response = session.get(
            BINANCE_KLINES_URL,
            params={"symbol": "BTCUSDT", "interval": "1d", "startTime": since, "limit": 1000},
            timeout=timeout,
            proxies=proxies,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        rows.extend(batch)
        next_since = int(batch[-1][0]) + 86_400_000
        if next_since <= since:
            raise BacktestDataError("Binance pagination did not advance")
        since = next_since
        if len(batch) < 1000:
            break
    records = [
        {
            "date": pd.to_datetime(int(row[0]), unit="ms", utc=True),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        }
        for row in rows
        if int(row[0]) < cutoff
    ]
    return _validate_frame(pd.DataFrame(records), "BTC")


def fetch_yahoo_equity(
    session: requests.Session, ticker: str, years: int, timeout: int, proxies=None
) -> pd.DataFrame:
    period2 = int(datetime.now(timezone.utc).timestamp())
    period1 = int((datetime.now(timezone.utc) - timedelta(days=366 * years + 90)).timestamp())
    response = session.get(
        YAHOO_CHART_URL.format(ticker=ticker),
        params={"interval": "1d", "period1": period1, "period2": period2, "events": "history"},
        headers={"User-Agent": "crypto-smart-trader research backtest"},
        timeout=timeout,
        proxies=proxies,
    )
    response.raise_for_status()
    result = (response.json().get("chart", {}).get("result") or [None])[0]
    if not result:
        raise BacktestDataError(f"Yahoo returned no chart data for {ticker}")
    quote = result["indicators"]["quote"][0]
    records = []
    for index, timestamp in enumerate(result.get("timestamp", [])):
        values = {name: quote.get(name, [None] * (index + 1))[index] for name in ("open", "high", "low", "close", "volume")}
        if any(values[name] is None for name in ("open", "high", "low", "close")):
            continue
        records.append(
            {
                "date": pd.to_datetime(timestamp, unit="s", utc=True).normalize(),
                **{name: float(value or 0.0) for name, value in values.items()},
            }
        )
    return _validate_frame(pd.DataFrame(records), ticker)


def _validate_frame(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    required = {"date", "open", "high", "low", "close", "volume"}
    if df.empty or not required.issubset(df.columns):
        raise BacktestDataError(f"insufficient OHLCV data for {symbol}")
    today_utc = pd.Timestamp(datetime.now(timezone.utc).date(), tz="UTC")
    result = df[df["date"] < today_utc].drop_duplicates("date").sort_values("date").reset_index(drop=True)
    result = result[(result["open"] > 0) & (result["high"] > 0) & (result["low"] > 0) & (result["close"] > 0)]
    if len(result) < 252:
        raise BacktestDataError(f"fewer than 252 finalized bars for {symbol}")
    return result.reset_index(drop=True)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    previous_close = result["close"].shift(1)
    true_range = pd.concat(
        [
            result["high"] - result["low"],
            (result["high"] - previous_close).abs(),
            (result["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    result["atr14"] = true_range.ewm(alpha=1 / 14, adjust=False).mean()

    delta = result["close"].diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    result["rsi14"] = 100 - 100 / (1 + avg_gain / avg_loss.replace(0, np.nan))

    result["prior_high20"] = result["high"].shift(1).rolling(20).max()
    result["drawdown20_pct"] = (result["close"] / result["prior_high20"] - 1) * 100
    result["atr_from_high"] = (result["prior_high20"] - result["close"]) / result["atr14"]
    result["deep_decline"] = (result["drawdown20_pct"] <= -8.0) | (result["atr_from_high"] >= 2.0)

    up_volume = result["volume"].where(delta > 0, 0.0)
    down_volume = result["volume"].where(delta <= 0, 0.0)
    down_sum = down_volume.rolling(5).sum()
    result["volume_ratio5"] = up_volume.rolling(5).sum() / down_sum.replace(0, np.nan)
    spread = (result["high"] - result["low"]).replace(0, np.nan)
    result["close_location"] = (2 * result["close"] - result["high"] - result["low"]) / spread
    result["retail_proxy_passed"] = (result["close_location"] > 0) | (result["close"].pct_change() > -0.01)
    result["strict_confirm"] = (
        (result["close"].pct_change(7) > 0)
        & (result["volume_ratio5"] > 1.0)
        & result["retail_proxy_passed"]
    )

    recent_oversold = result["rsi14"].shift(1).rolling(10).min() < 30
    crossback = (result["rsi14"].shift(1) <= 30) & (result["rsi14"] > 30)
    structure_turn = (result["low"] > result["low"].shift(1)) | (result["close"] > result["high"].shift(1))
    result["reversal_confirm"] = crossback & recent_oversold & structure_turn & result["retail_proxy_passed"]
    return result


def decline_episodes(df: pd.DataFrame, max_days: int = 60) -> list[tuple[int, int]]:
    episodes: list[tuple[int, int]] = []
    active = False
    start = 0
    for index, row in df.iterrows():
        if not active and bool(row["deep_decline"]):
            active = True
            start = int(index)
            continue
        if not active:
            continue
        recovered = row["drawdown20_pct"] > -4.0 and row["atr_from_high"] < 1.0
        expired = int(index) - start >= max_days
        if recovered or expired:
            episodes.append((start, int(index)))
            active = False
    if active:
        episodes.append((start, min(len(df) - 1, start + max_days)))
    return episodes


def _first_signal(df: pd.DataFrame, start: int, end: int, column: str) -> int | None:
    candidates = df.loc[start:end]
    matches = candidates.index[candidates[column].fillna(False)].tolist()
    return int(matches[0]) if matches else None


def evaluate_entry(df: pd.DataFrame, signal_index: int, horizons: tuple[int, ...] = HORIZONS) -> dict[str, Any] | None:
    entry_index = signal_index + 1
    if entry_index >= len(df):
        return None
    entry_price = float(df.loc[entry_index, "open"]) * (1 + ROUND_TRIP_COST / 2)
    result: dict[str, Any] = {
        "signal_date": df.loc[signal_index, "date"].date().isoformat(),
        "entry_date": df.loc[entry_index, "date"].date().isoformat(),
        "entry_price": round(entry_price, 6),
    }
    for horizon in horizons:
        exit_index = entry_index + horizon
        if exit_index >= len(df):
            result[f"return_{horizon}d_pct"] = None
            result[f"mae_{horizon}d_pct"] = None
            continue
        exit_price = float(df.loc[exit_index, "close"]) * (1 - ROUND_TRIP_COST / 2)
        lows = df.loc[entry_index:exit_index, "low"]
        result[f"return_{horizon}d_pct"] = round((exit_price / entry_price - 1) * 100, 4)
        result[f"mae_{horizon}d_pct"] = round((float(lows.min()) / entry_price - 1) * 100, 4)
    return result


def summarize(entries: list[dict[str, Any]], episode_count: int) -> dict[str, Any]:
    summary: dict[str, Any] = {"entries": len(entries), "episode_coverage_pct": round(len(entries) / episode_count * 100, 2) if episode_count else 0.0}
    for horizon in HORIZONS:
        returns = [entry[f"return_{horizon}d_pct"] for entry in entries if entry.get(f"return_{horizon}d_pct") is not None]
        maes = [entry[f"mae_{horizon}d_pct"] for entry in entries if entry.get(f"mae_{horizon}d_pct") is not None]
        summary[f"{horizon}d"] = {
            "observations": len(returns),
            "mean_return_pct": round(float(np.mean(returns)), 3) if returns else None,
            "median_return_pct": round(float(np.median(returns)), 3) if returns else None,
            "win_rate_pct": round(sum(value > 0 for value in returns) / len(returns) * 100, 2) if returns else None,
            "mean_mae_pct": round(float(np.mean(maes)), 3) if maes else None,
            "worst_mae_pct": round(float(np.min(maes)), 3) if maes else None,
        }
    return summary


def paired_vs_direct(
    candidate_entries: list[dict[str, Any]], direct_entries: list[dict[str, Any]]
) -> dict[str, Any]:
    direct_by_episode = {entry["episode_start"]: entry for entry in direct_entries}
    result: dict[str, Any] = {"paired_events": 0}
    pairs = [
        (candidate, direct_by_episode[candidate["episode_start"]])
        for candidate in candidate_entries
        if candidate["episode_start"] in direct_by_episode
    ]
    result["paired_events"] = len(pairs)
    for horizon in HORIZONS:
        deltas = []
        mae_deltas = []
        for candidate, direct in pairs:
            candidate_return = candidate.get(f"return_{horizon}d_pct")
            direct_return = direct.get(f"return_{horizon}d_pct")
            candidate_mae = candidate.get(f"mae_{horizon}d_pct")
            direct_mae = direct.get(f"mae_{horizon}d_pct")
            if candidate_return is not None and direct_return is not None:
                deltas.append(candidate_return - direct_return)
            if candidate_mae is not None and direct_mae is not None:
                mae_deltas.append(candidate_mae - direct_mae)
        result[f"{horizon}d"] = {
            "observations": len(deltas),
            "mean_return_delta_pct": round(float(np.mean(deltas)), 3) if deltas else None,
            "median_return_delta_pct": round(float(np.median(deltas)), 3) if deltas else None,
            "better_return_rate_pct": round(sum(delta > 0 for delta in deltas) / len(deltas) * 100, 2) if deltas else None,
            "mean_mae_improvement_pct": round(float(np.mean(mae_deltas)), 3) if mae_deltas else None,
        }
    return result


def frame_hash(df: pd.DataFrame) -> str:
    payload = df[["date", "open", "high", "low", "close", "volume"]].to_csv(index=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_symbol(symbol: str, raw: pd.DataFrame, years: int) -> dict[str, Any]:
    cutoff = raw["date"].max() - pd.Timedelta(days=365 * years)
    warm = raw[raw["date"] >= cutoff - pd.Timedelta(days=90)].reset_index(drop=True)
    df = add_features(warm)
    test_start = cutoff
    episodes = [(start, end) for start, end in decline_episodes(df) if df.loc[start, "date"] >= test_start]
    strategies: dict[str, list[dict[str, Any]]] = {
        "direct_knife": [],
        "reversal_confirmed": [],
        "technical_strict_confirmed": [],
    }
    for start, end in episodes:
        signals = {
            "direct_knife": start,
            "reversal_confirmed": _first_signal(df, start, end, "reversal_confirm"),
            "technical_strict_confirmed": _first_signal(df, start, end, "strict_confirm"),
        }
        for name, signal in signals.items():
            if signal is None:
                continue
            entry = evaluate_entry(df, signal)
            if entry:
                entry["episode_start"] = df.loc[start, "date"].date().isoformat()
                strategies[name].append(entry)
    return {
        "symbol": symbol,
        "source_records": len(raw),
        "test_start": test_start.date().isoformat(),
        "test_end": raw["date"].max().date().isoformat(),
        "input_sha256": frame_hash(raw),
        "decline_episodes": len(episodes),
        "strategies": {
            name: {
                "summary": summarize(entries, len(episodes)),
                "paired_vs_direct": paired_vs_direct(entries, strategies["direct_knife"]) if name != "direct_knife" else None,
                "entries": entries,
            }
            for name, entries in strategies.items()
        },
    }


def run_backtest(symbols: list[str], years: int, timeout: int) -> dict[str, Any]:
    config = load_config()
    proxies = proxy_dict(config)
    results = []
    sources: dict[str, str] = {}
    with requests.Session() as session:
        for symbol in symbols:
            normalized = symbol.upper()
            if normalized == "BTC":
                raw = fetch_binance_btc(session, years, timeout, proxies)
                sources[normalized] = BINANCE_KLINES_URL
            elif normalized in {"NVDA", "MSFT"}:
                raw = fetch_yahoo_equity(session, normalized, years, timeout, proxies)
                sources[normalized] = YAHOO_CHART_URL.format(ticker=normalized)
            else:
                raise BacktestDataError(f"unsupported research symbol: {symbol}")
            results.append(run_symbol(normalized, raw, years))
    return {
        "schema_version": 1,
        "status": "ok",
        "research_only": True,
        "generated_at_utc": iso_utc(),
        "parameters": {
            "years": years,
            "deep_decline": "20d high drawdown <= -8% OR distance from 20d high >= 2 ATR14",
            "episode_exit": "recovery inside -4% and 1 ATR, or 60 trading days",
            "reversal": "RSI14 crosses above 30 after recent oversold, daily structure turns, retail proxy passes",
            "technical_strict": "7d return > 0, 5d up/down volume ratio > 1, retail proxy passes",
            "execution": "next finalized daily bar open",
            "round_trip_fee_and_slippage_pct": ROUND_TRIP_COST * 100,
            "horizons_trading_days": list(HORIZONS),
        },
        "sources": sources,
        "limitations": [
            "Technical event study only; historical news, fundamentals, order books, and taker flow are not replayed.",
            "Yahoo equity data is a public reference feed, not an official exchange feed.",
            "No parameter search was performed; thresholds were fixed before observing these results.",
        ],
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest blue-chip falling-knife reversal confirmation")
    parser.add_argument("--symbols", nargs="+", default=["BTC", "NVDA", "MSFT"])
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = run_backtest(args.symbols, max(2, args.years), max(3, args.timeout))
    except (BacktestDataError, requests.RequestException, ValueError, KeyError) as exc:
        print(f"BACKTEST_UNAVAILABLE: {exc}")
        return 3
    latest = state_dir() / "latest_bluechip_reversal_backtest.json"
    period_latest = state_dir() / f"latest_bluechip_reversal_backtest_{report['parameters']['years']}y.json"
    archive = state_dir() / f"bluechip_reversal_backtest_{report['generated_at_utc'].replace(':', '').replace('-', '')}.json"
    write_json_atomic(archive, report)
    write_json_atomic(latest, report)
    write_json_atomic(period_latest, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"BLUECHIP REVERSAL BACKTEST | {report['generated_at_utc']}")
        for result in report["results"]:
            print(f"{result['symbol']}: {result['decline_episodes']} decline episodes")
            for name, payload in result["strategies"].items():
                summary = payload["summary"]
                print(f"  {name:<20} entries={summary['entries']:<3} 20d={summary['20d']['mean_return_pct']}% win={summary['20d']['win_rate_pct']}%")
        print(f"Evidence: {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
