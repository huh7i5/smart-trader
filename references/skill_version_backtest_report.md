# Strict vs. Relaxed Skill Gate Backtest

Generated on 2026-07-18. This is a historical proxy comparison, not proof of live skill performance.

## Compared Versions

- `current_strict`: every accumulation and tactical entry requires all available historical checklist proxies.
- `previous_relaxed`: ordinary accumulation remains strict, but tactical RSI/Bollinger entries may bypass trend and retail-flow failures when the macro calendar proxy is not blocked.

This reconstructs the former relaxed behavior described in the repository. The exact deleted implementation and historical live order-book/news evidence do not exist, so the result must not be presented as an exact replay of natural-language skill decisions.

## Reality Model

- BTC/USDT daily OHLCV from Binance.
- Fear & Greed history from Alternative.me.
- Signal after the finalized daily close; fill at the next daily open.
- Entry friction 0.10%; exit friction 0.10%.
- Fixed parameters: F&G low 15, RSI low 25, RSI crossback 30, volatility-entry F&G maximum 35.
- Same starting capital, sizing formula, data, and end price for both versions.

## Results

| Window | Version | Trades | Invested | Average Cost | Deployed ROI | Portfolio Max DD |
|---|---|---:|---:|---:|---:|---:|
| 2022-12-25 to 2026-07-16 | Current strict | 349 | $28,963.51 | $48,917.86 | 30.35% | 6.55% |
| 2022-12-25 to 2026-07-16 | Previous relaxed | 419 | $35,605.97 | $51,930.60 | 22.79% | 7.17% |
| 2025-07-01 to 2026-07-16 | Current strict | 76 | $8,049.55 | $85,156.25 | -25.12% | 0.52% |
| 2025-07-01 to 2026-07-16 | Previous relaxed | 123 | $12,321.40 | $81,832.20 | -22.08% | 0.72% |

Across the full 1,300-day window, the current strict gate improved deployed ROI by 7.56 percentage points, lowered average cost by 5.80%, and reduced portfolio maximum drawdown by 0.61 percentage points.

In the recent 381-day holdout, the strict gate underperformed deployed ROI by 3.04 percentage points and had a 4.06% higher average cost. It still reduced portfolio maximum drawdown by 0.20 percentage points. This is consistent with a confirmation filter entering later during a prolonged decline: it reduces exposure but does not guarantee a better entry price.

## Data Lineage

- Input records: 2,025 daily rows including indicator warm-up.
- Input SHA-256: `786fe9a85bb5ed27e443ac7caab32049fd96f8696dd98534137cd2f0d0ec88b2`.
- Event-level artifact: `.state/latest_skill_version_backtest.json`.
- Reproduce with `python scripts/backtest_skill_versions.py --json`.

## Verdict

The current strict gate is better over the full historical window and controls risk more consistently, but higher return is not stable across regimes. Do not claim that the current skill has universally higher returns. The evidence supports the narrower statement that strict gating reduced overtrading, average cost, and full-period drawdown, while sometimes lagging a relaxed strategy during a specific declining regime.

The next valid test should freeze this implementation and evaluate a genuinely untouched future period or paper-trading ledger. Historical news review, order books, taker flow, bStock tracking differences, taxes, and partial fills remain outside this replay.
