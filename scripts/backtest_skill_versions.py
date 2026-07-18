"""Compare the former relaxed tactical gate with the current strict gate.

This research backtest replays only historically available daily proxies. It
cannot replay the skill's original news review, order book, or taker-flow data.
Signals are executed at the next daily open with explicit friction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backtest_wfa import (
    check_bullish_divergence,
    check_rsi_crossback,
    f_fng,
    f_rsi,
    load_btc_data,
    load_fng_data,
    prepare_dataframe,
)
from trader_runtime import iso_utc, state_dir, write_json_atomic


ENTRY_FRICTION = 0.001
EXIT_FRICTION = 0.001
BASE_AMOUNT = 100.0
INITIAL_CAPITAL = 500_000.0
FNG_LOW = 15
RSI_LOW = 25
RSI_CROSS = 30
M3_FNG_MAX = 35
HORIZONS = (20, 60)


class VersionBacktestError(RuntimeError):
    """Raised when the historical comparison cannot be completed."""


def signal_amount(df: pd.DataFrame, index: int, *, relaxed_tactical_gate: bool) -> float:
    row = df.loc[index]
    checklist_passed = bool(row["checklist_passed"])
    macro_passed = bool(row["macro_passed"])
    amount = 0.0

    if checklist_passed:
        multiplier = max(0.5, min(3.0, f_fng(row["fng"], FNG_LOW) * f_rsi(row["rsi_14"], RSI_LOW)))
        amount += multiplier * BASE_AMOUNT

    tactical_gate = macro_passed if relaxed_tactical_gate else checklist_passed
    if not tactical_gate:
        return amount

    if check_rsi_crossback(index, df, RSI_CROSS) or check_bullish_divergence(index, df):
        amount += BASE_AMOUNT

    if row["fng"] <= M3_FNG_MAX and row["low"] <= row["bb_lower"]:
        relative_volatility = row["bar_sigma_rel"] / row["sigma_rel"] if row["sigma_rel"] > 0 else 1.0
        amount += max(0.5, min(3.0, relative_volatility)) * BASE_AMOUNT
    return float(amount)


def _forward_trade_metrics(df: pd.DataFrame, entry: dict[str, Any], end_index: int) -> dict[str, Any]:
    result = dict(entry)
    entry_index = int(entry["entry_index"])
    entry_price = float(entry["effective_entry_price"])
    for horizon in HORIZONS:
        exit_index = entry_index + horizon
        if exit_index > end_index:
            result[f"return_{horizon}d_pct"] = None
            result[f"mae_{horizon}d_pct"] = None
            continue
        exit_price = float(df.loc[exit_index, "close"]) * (1 - EXIT_FRICTION)
        lowest = float(df.loc[entry_index:exit_index, "low"].min())
        result[f"return_{horizon}d_pct"] = round((exit_price / entry_price - 1) * 100, 4)
        result[f"mae_{horizon}d_pct"] = round((lowest / entry_price - 1) * 100, 4)
    result.pop("entry_index", None)
    return result


def _summarize_forward(entries: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for horizon in HORIZONS:
        returns = [entry[f"return_{horizon}d_pct"] for entry in entries if entry[f"return_{horizon}d_pct"] is not None]
        maes = [entry[f"mae_{horizon}d_pct"] for entry in entries if entry[f"mae_{horizon}d_pct"] is not None]
        result[f"{horizon}d"] = {
            "observations": len(returns),
            "mean_return_pct": round(float(np.mean(returns)), 3) if returns else None,
            "median_return_pct": round(float(np.median(returns)), 3) if returns else None,
            "win_rate_pct": round(sum(value > 0 for value in returns) / len(returns) * 100, 2) if returns else None,
            "mean_mae_pct": round(float(np.mean(maes)), 3) if maes else None,
            "worst_mae_pct": round(float(np.min(maes)), 3) if maes else None,
        }
    return result


def simulate_version(
    df: pd.DataFrame,
    indices: list[int],
    *,
    relaxed_tactical_gate: bool,
    initial_capital: float = INITIAL_CAPITAL,
) -> dict[str, Any]:
    if len(indices) < 62:
        raise VersionBacktestError("comparison window needs at least 62 daily bars")
    cash = initial_capital
    quantity = 0.0
    invested = 0.0
    pending: tuple[int, float] | None = None
    equity: list[float] = []
    raw_entries: list[dict[str, Any]] = []
    index_set = set(indices)

    for index in indices:
        if pending is not None:
            signal_index, amount = pending
            effective_price = float(df.loc[index, "open"]) * (1 + ENTRY_FRICTION)
            if amount <= cash:
                quantity += amount / effective_price
                cash -= amount
                invested += amount
                raw_entries.append(
                    {
                        "signal_date": df.loc[signal_index, "date"].isoformat(),
                        "entry_date": df.loc[index, "date"].isoformat(),
                        "entry_index": index,
                        "amount": round(amount, 6),
                        "effective_entry_price": round(effective_price, 6),
                    }
                )
            pending = None

        equity.append(cash + quantity * float(df.loc[index, "close"]))
        next_index = index + 1
        if next_index not in index_set:
            continue
        amount = signal_amount(df, index, relaxed_tactical_gate=relaxed_tactical_gate)
        if amount > 0:
            pending = (index, amount)

    final_close = float(df.loc[indices[-1], "close"]) * (1 - EXIT_FRICTION)
    final_asset_value = quantity * final_close
    deployed_roi = (final_asset_value - invested) / invested * 100 if invested else 0.0
    average_cost = invested / quantity if quantity else 0.0
    equity_array = np.asarray(equity, dtype=float)
    peaks = np.maximum.accumulate(equity_array)
    max_drawdown = float(np.max((peaks - equity_array) / peaks) * 100)
    entries = [_forward_trade_metrics(df, entry, indices[-1]) for entry in raw_entries]
    return {
        "trades": len(entries),
        "total_invested": round(invested, 2),
        "asset_quantity": round(quantity, 8),
        "average_effective_cost": round(average_cost, 2),
        "final_asset_value": round(final_asset_value, 2),
        "deployed_roi_pct": round(deployed_roi, 3),
        "portfolio_max_drawdown_pct": round(max_drawdown, 3),
        "forward": _summarize_forward(entries),
        "entries": entries,
    }


def _input_hash(df: pd.DataFrame) -> str:
    columns = ["date", "open", "high", "low", "close", "volume", "fng"]
    return hashlib.sha256(df[columns].to_csv(index=False).encode("utf-8")).hexdigest()


def _window(df: pd.DataFrame, start: date, end: date) -> list[int]:
    indices = df[(df["date"] >= start) & (df["date"] <= end)].index.tolist()
    if not indices:
        raise VersionBacktestError(f"no records in comparison window {start} to {end}")
    return indices


def compare_window(df: pd.DataFrame, name: str, start: date, end: date) -> dict[str, Any]:
    indices = _window(df, start, end)
    current = simulate_version(df, indices, relaxed_tactical_gate=False)
    previous = simulate_version(df, indices, relaxed_tactical_gate=True)
    return {
        "name": name,
        "start": df.loc[indices[0], "date"].isoformat(),
        "end": df.loc[indices[-1], "date"].isoformat(),
        "records": len(indices),
        "current_strict": current,
        "previous_relaxed": previous,
        "delta": {
            "deployed_roi_pct_points": round(current["deployed_roi_pct"] - previous["deployed_roi_pct"], 3),
            "average_cost_pct": round((current["average_effective_cost"] / previous["average_effective_cost"] - 1) * 100, 3),
            "portfolio_max_drawdown_pct_points": round(
                current["portfolio_max_drawdown_pct"] - previous["portfolio_max_drawdown_pct"], 3
            ),
        },
    }


def run_comparison() -> dict[str, Any]:
    candles = load_btc_data()
    fear_greed = load_fng_data()
    if not candles or not fear_greed:
        raise VersionBacktestError("BTC or Fear & Greed history is unavailable")
    df = prepare_dataframe(candles, fear_greed)
    full_start = date(2022, 12, 25)
    holdout_start = date(2025, 7, 1)
    end = min(date(2026, 7, 16), max(df["date"]))
    return {
        "schema_version": 1,
        "status": "ok",
        "research_only": True,
        "generated_at_utc": iso_utc(),
        "asset": "BTC/USDT",
        "input_records": len(df),
        "input_sha256": _input_hash(df),
        "parameters": {
            "current_strict": "all accumulation and tactical entries require historical checklist proxies",
            "previous_relaxed": "baseline accumulation stays strict; tactical RSI/Bollinger entries require macro proxy only",
            "execution": "signal after daily close, fill at next daily open",
            "entry_friction_pct": ENTRY_FRICTION * 100,
            "exit_friction_pct": EXIT_FRICTION * 100,
            "fixed": {"fng_low": FNG_LOW, "rsi_low": RSI_LOW, "rsi_cross": RSI_CROSS, "m3_fng_max": M3_FNG_MAX},
        },
        "sources": {
            "ohlcv": "https://api.binance.com/api/v3/klines",
            "fear_greed": "https://api.alternative.me/fng/",
        },
        "windows": [
            compare_window(df, "full", full_start, end),
            compare_window(df, "recent_holdout", holdout_start, end),
        ],
        "limitations": [
            "This compares daily historical proxies, not the full natural-language skill or live execution performance.",
            "Historical original-news review, order-book depth, and taker-buy flow are unavailable and are not replayed.",
            "The macro proxy uses repository event dates and does not reproduce every historical announcement.",
            "The recent holdout was not used to change parameters in this comparison, but prior repository research overlaps part of it.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare current strict and previous relaxed skill gates")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = run_comparison()
    except (VersionBacktestError, KeyError, ValueError) as exc:
        print(f"VERSION_BACKTEST_UNAVAILABLE: {exc}")
        return 3
    latest = state_dir() / "latest_skill_version_backtest.json"
    archive = state_dir() / f"skill_version_backtest_{report['generated_at_utc'].replace(':', '').replace('-', '')}.json"
    write_json_atomic(archive, report)
    write_json_atomic(latest, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"SKILL VERSION BACKTEST | {report['generated_at_utc']}")
        for window in report["windows"]:
            current = window["current_strict"]
            previous = window["previous_relaxed"]
            print(
                f"{window['name']}: current={current['deployed_roi_pct']}% "
                f"previous={previous['deployed_roi_pct']}% delta={window['delta']['deployed_roi_pct_points']}pp"
            )
        print(f"Evidence: {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
