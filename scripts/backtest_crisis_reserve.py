"""Research-only backtest for deploying the final 30% cash reserve.

The simulation starts each rolling window with 70% invested and 30% cash.
Signals use finalized daily bars and orders execute at the next session open.
Historical AMDB/WDCB coverage is represented by the linked AMD/WDC stocks and
is therefore reference evidence, not an official Binance bStock replay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import requests

from backtest_bluechip_reversal import add_features, fetch_yahoo_equity
from trader_runtime import iso_utc, load_config, proxy_dict, state_dir, write_json_atomic


INITIAL_CAPITAL = 10_000.0
ONE_WAY_COST = 0.001
TRADING_DAYS_PER_YEAR = 252
TIERS = (-20.0, -30.0, -40.0)


@dataclass(frozen=True)
class Policy:
    name: str
    floors: tuple[float, float, float]
    confirmed: bool
    spend_all_on_first_trigger: bool = False


POLICIES = (
    Policy("hard_30", (0.30, 0.30, 0.30), True),
    Policy("staged_20_10_5", (0.20, 0.10, 0.05), True),
    Policy("full_30_at_first_drop", (0.0, 0.0, 0.0), False, True),
)


def _input_hash(frames: dict[str, pd.DataFrame]) -> str:
    digest = hashlib.sha256()
    for symbol in sorted(frames):
        digest.update(symbol.encode("utf-8"))
        digest.update(frames[symbol][["date", "open", "high", "low", "close", "volume"]].to_csv(index=False).encode("utf-8"))
    return digest.hexdigest()


def _prepare(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    prepared = []
    for symbol, raw in frames.items():
        featured = add_features(raw)
        featured["high252"] = featured["high"].shift(1).rolling(252, min_periods=126).max()
        featured["drawdown252_pct"] = (featured["close"] / featured["high252"] - 1) * 100
        columns = ["date", "open", "high", "low", "close", "rsi14", "drawdown252_pct"]
        prepared.append(featured[columns].rename(columns={column: f"{symbol}_{column}" for column in columns if column != "date"}))
    aligned = prepared[0]
    for frame in prepared[1:]:
        aligned = aligned.merge(frame, on="date", how="inner")
    return aligned.dropna().sort_values("date").reset_index(drop=True)


def _confirmed_turn(frame: pd.DataFrame, index: int, symbol: str) -> bool:
    if index < 1:
        return False
    rsi = frame[f"{symbol}_rsi14"]
    crossed = rsi.iloc[index - 1] <= 30 < rsi.iloc[index]
    structure = (
        frame[f"{symbol}_low"].iloc[index] > frame[f"{symbol}_low"].iloc[index - 1]
        or frame[f"{symbol}_close"].iloc[index] > frame[f"{symbol}_high"].iloc[index - 1]
    )
    return bool(crossed and structure)


def _simulate(frame: pd.DataFrame, symbols: list[str], policy: Policy) -> dict[str, Any]:
    cash = INITIAL_CAPITAL * 0.30
    allocation = INITIAL_CAPITAL * 0.70 / len(symbols)
    units = {
        symbol: allocation * (1 - ONE_WAY_COST) / float(frame[f"{symbol}_open"].iloc[0])
        for symbol in symbols
    }
    armed = {symbol: [False, False, False] for symbol in symbols}
    used = [False, False, False]
    pending: list[tuple[int, list[str]]] = []
    equity_curve: list[float] = []
    reserve_deployed = 0.0
    trade_count = 0

    for index in range(len(frame)):
        opens = {symbol: float(frame[f"{symbol}_open"].iloc[index]) for symbol in symbols}
        closes = {symbol: float(frame[f"{symbol}_close"].iloc[index]) for symbol in symbols}

        for tier_index, candidates in pending:
            equity_at_open = cash + sum(units[symbol] * opens[symbol] for symbol in symbols)
            if policy.spend_all_on_first_trigger:
                spend = cash
            else:
                target = equity_at_open * 0.10
                floor_cash = equity_at_open * policy.floors[tier_index]
                spend = min(target, max(0.0, cash - floor_cash))
            if spend > equity_at_open * 0.001:
                each = spend / len(candidates)
                for symbol in candidates:
                    units[symbol] += each * (1 - ONE_WAY_COST) / opens[symbol]
                cash -= spend
                reserve_deployed += spend
                trade_count += len(candidates)
            used[tier_index] = True
        pending = []

        equity = cash + sum(units[symbol] * closes[symbol] for symbol in symbols)
        equity_curve.append(equity)
        if index == len(frame) - 1:
            continue

        for symbol in symbols:
            drawdown = float(frame[f"{symbol}_drawdown252_pct"].iloc[index])
            for tier_index, threshold in enumerate(TIERS):
                if drawdown <= threshold:
                    armed[symbol][tier_index] = True

        if policy.spend_all_on_first_trigger and not used[0]:
            candidates = [symbol for symbol in symbols if armed[symbol][0]]
            if candidates:
                pending.append((0, candidates))
                used = [True, True, True]
            continue

        for tier_index in range(3):
            if used[tier_index]:
                continue
            candidates = [
                symbol
                for symbol in symbols
                if armed[symbol][tier_index] and _confirmed_turn(frame, index, symbol)
            ]
            if candidates:
                pending.append((tier_index, candidates))
                # A single reversal event can release only one tranche. Deeper
                # reserve tiers require a later, independent oversold cycle.
                break

    curve = pd.Series(equity_curve, dtype=float)
    running_peak = curve.cummax()
    max_drawdown = float((curve / running_peak - 1).min() * 100)
    years = max((frame["date"].iloc[-1] - frame["date"].iloc[0]).days / 365.25, 1 / 365.25)
    final_equity = float(curve.iloc[-1])
    return {
        "total_return_pct": (final_equity / INITIAL_CAPITAL - 1) * 100,
        "cagr_pct": ((final_equity / INITIAL_CAPITAL) ** (1 / years) - 1) * 100,
        "max_drawdown_pct": max_drawdown,
        "reserve_deployed_pct_initial": reserve_deployed / INITIAL_CAPITAL * 100,
        "ending_cash_pct": cash / final_equity * 100,
        "trade_count": trade_count,
    }


def _rolling_windows(frame: pd.DataFrame, horizon_years: int, step_days: int) -> list[pd.DataFrame]:
    horizon = horizon_years * TRADING_DAYS_PER_YEAR
    return [frame.iloc[start : start + horizon].reset_index(drop=True) for start in range(0, len(frame) - horizon + 1, step_days)]


def _summarize(rows: list[dict[str, Any]], baseline: list[dict[str, Any]]) -> dict[str, Any]:
    returns = np.array([row["total_return_pct"] for row in rows])
    cagrs = np.array([row["cagr_pct"] for row in rows])
    drawdowns = np.array([row["max_drawdown_pct"] for row in rows])
    deployed = np.array([row["reserve_deployed_pct_initial"] for row in rows])
    base_returns = np.array([row["total_return_pct"] for row in baseline])
    deltas = returns - base_returns
    return {
        "windows": len(rows),
        "median_total_return_pct": round(float(np.median(returns)), 3),
        "mean_total_return_pct": round(float(np.mean(returns)), 3),
        "median_cagr_pct": round(float(np.median(cagrs)), 3),
        "median_max_drawdown_pct": round(float(np.median(drawdowns)), 3),
        "worst_max_drawdown_pct": round(float(np.min(drawdowns)), 3),
        "worst_total_return_pct": round(float(np.min(returns)), 3),
        "median_reserve_deployed_pct_initial": round(float(np.median(deployed)), 3),
        "outperform_hard_30_windows_pct": round(float(np.mean(returns > base_returns) * 100), 2),
        "median_return_delta_vs_hard_30_pct_points": round(float(np.median(deltas)), 3),
        "mean_return_delta_vs_hard_30_pct_points": round(float(np.mean(deltas)), 3),
    }


def run_backtest(years: int, horizon_years: int, step_days: int, timeout: int) -> dict[str, Any]:
    config = load_config()
    proxies = proxy_dict(config)
    with requests.Session() as session:
        frames = {
            ticker: fetch_yahoo_equity(session, ticker, years, timeout, proxies)
            for ticker in ("AMD", "WDC")
        }
    datasets = {"AMD": _prepare({"AMD": frames["AMD"]}), "WDC": _prepare({"WDC": frames["WDC"]}), "AMD_WDC_equal": _prepare(frames)}
    latest_reference_state = {}
    for ticker in ("AMD", "WDC"):
        latest_frame = datasets[ticker]
        latest_index = len(latest_frame) - 1
        drawdown = float(latest_frame[f"{ticker}_drawdown252_pct"].iloc[latest_index])
        latest_reference_state[ticker] = {
            "date": latest_frame["date"].iloc[latest_index].date().isoformat(),
            "close": round(float(latest_frame[f"{ticker}_close"].iloc[latest_index]), 6),
            "rsi14": round(float(latest_frame[f"{ticker}_rsi14"].iloc[latest_index]), 4),
            "drawdown252_pct": round(drawdown, 4),
            "armed_tiers_pct": [threshold for threshold in TIERS if drawdown <= threshold],
            "reversal_confirmed": _confirmed_turn(latest_frame, latest_index, ticker),
        }
    results: dict[str, Any] = {}
    for name, frame in datasets.items():
        symbols = ["AMD", "WDC"] if name == "AMD_WDC_equal" else [name]
        windows = _rolling_windows(frame, horizon_years, step_days)
        raw = {policy.name: [_simulate(window, symbols, policy) for window in windows] for policy in POLICIES}
        baseline = raw["hard_30"]
        results[name] = {
            "first_window_start": windows[0]["date"].iloc[0].date().isoformat(),
            "last_window_end": windows[-1]["date"].iloc[-1].date().isoformat(),
            "policies": {name_: _summarize(rows, baseline) for name_, rows in raw.items()},
        }
    return {
        "schema_version": 1,
        "status": "ok",
        "research_only": True,
        "generated_at_utc": iso_utc(),
        "parameters": {
            "history_years": years,
            "rolling_horizon_years": horizon_years,
            "rolling_step_trading_days": step_days,
            "initial_invested_pct": 70,
            "initial_cash_pct": 30,
            "crisis_drawdown_tiers_pct_from_prior_252d_high": list(TIERS),
            "confirmation": "RSI14 crosses above 30 and daily price structure turns",
            "execution": "next session open using finalized daily bars",
            "one_way_fee_and_slippage_pct": ONE_WAY_COST * 100,
            "policies": {policy.name: {"cash_floors": list(policy.floors), "confirmed": policy.confirmed} for policy in POLICIES},
        },
        "sources": {ticker: f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}" for ticker in frames},
        "input_sha256": _input_hash(frames),
        "latest_reference_state": latest_reference_state,
        "limitations": [
            "AMD and WDC are linked-underlying public reference feeds, not official Binance AMDB/WDCB history.",
            "Historical fundamentals, news, Binance order books, taker flow, bStock tracking error, taxes, and FX are not replayed.",
            "The test isolates reserve policy; it is not a forecast and does not authorize a live order.",
            "Thresholds were fixed before this run; no parameter search was performed.",
        ],
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest conditional deployment of the final 30% reserve")
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--horizon-years", type=int, default=3)
    parser.add_argument("--step-days", type=int, default=63)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = run_backtest(max(5, args.years), max(1, args.horizon_years), max(21, args.step_days), max(3, args.timeout))
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        print(f"BACKTEST_UNAVAILABLE: {exc}")
        return 3
    latest = state_dir() / "latest_crisis_reserve_backtest.json"
    archive = state_dir() / f"crisis_reserve_backtest_{report['generated_at_utc'].replace(':', '').replace('-', '')}.json"
    write_json_atomic(archive, report)
    write_json_atomic(latest, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"CRISIS RESERVE BACKTEST | {report['generated_at_utc']}")
        for dataset, payload in report["results"].items():
            print(dataset)
            for policy, summary in payload["policies"].items():
                print(f"  {policy:<22} median_return={summary['median_total_return_pct']:>8.3f}% median_MDD={summary['median_max_drawdown_pct']:>8.3f}%")
        print(f"Evidence: {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
