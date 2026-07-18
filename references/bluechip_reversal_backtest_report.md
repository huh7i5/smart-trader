# Blue-Chip Reversal Entry Event Study

Generated on 2026-07-18. This is a technical research result, not live-deployment approval.

## Question

Does waiting for a reversal after a deep blue-chip decline improve entry quality compared with buying the decline immediately?

## Fixed Method

- Arm an episode when price is at least 8% below the prior 20-day high or at least 2 ATR14 below it.
- `direct_knife`: signal immediately when the episode starts.
- `reversal_confirmed`: RSI14 crosses back above 30 after a recent oversold reading, daily price structure turns, and the daily retail-flow proxy passes.
- `technical_strict_confirmed`: seven-day return is positive, five-day up/down-volume ratio is above 1, and the daily retail-flow proxy passes.
- Execute every signal at the next finalized daily bar's open.
- Deduct 0.20% total for entry/exit fees and slippage.
- Measure 5-, 20-, and 60-trading-day returns and maximum adverse excursion.
- Parameters were fixed before results were observed. No grid search was used.

`technical_strict_confirmed` is not the live three-point checklist because historical news, fundamentals, order books, and taker flow were not replayed.

## Five-Year Results

Period: 2021-07-18 through 2026-07-17.

| Asset | Strategy | Entries / Episodes | 20d Mean | 20d Win Rate | 60d Mean | 60d Win Rate | 60d Mean MAE |
|---|---|---:|---:|---:|---:|---:|---:|
| BTC | Direct | 54 / 54 | 1.19% | 53.70% | 5.31% | 50.00% | -15.38% |
| BTC | Reversal | 12 / 54 | 1.49% | 25.00% | 8.00% | 81.82% | -11.14% |
| BTC | Technical strict | 50 / 54 | 0.22% | 46.00% | 4.47% | 46.94% | -16.06% |
| NVDA | Direct | 46 / 46 | 2.69% | 56.52% | 11.78% | 56.82% | -15.45% |
| NVDA | Reversal | 2 / 46 | 0.23% | 50.00% | 7.43% | 50.00% | -20.29% |
| NVDA | Technical strict | 32 / 46 | 4.79% | 61.29% | 15.65% | 67.74% | -14.20% |
| MSFT | Direct | 37 / 37 | 0.54% | 56.76% | 1.43% | 51.43% | -9.43% |
| MSFT | Reversal | 8 / 37 | -1.46% | 42.86% | -0.03% | 42.86% | -13.43% |
| MSFT | Technical strict | 31 / 37 | -1.12% | 48.39% | 0.83% | 48.28% | -9.49% |

On matched decline episodes, reversal confirmation improved the 60-day return relative to direct entry by 19.76 percentage points for BTC, 30.75 points for NVDA, and 10.78 points for MSFT. The NVDA comparison contains only two events. MSFT's relative improvement still left its absolute reversal return near zero.

## Recent Three-Year Check

Period: 2023-07-18 through 2026-07-17, using unchanged parameters.

| Asset | Strategy | Entries / Episodes | 20d Mean | 60d Mean |
|---|---|---:|---:|---:|
| BTC | Direct | 31 / 31 | 4.26% | 11.06% |
| BTC | Reversal | 7 / 31 | -0.14% | 10.18% |
| BTC | Technical strict | 28 / 31 | 2.26% | 11.24% |
| NVDA | Direct | 28 / 28 | 3.79% | 14.14% |
| NVDA | Reversal | 0 / 28 | N/A | N/A |
| NVDA | Technical strict | 19 / 28 | 3.03% | 18.38% |
| MSFT | Direct | 22 / 22 | 0.18% | 1.09% |
| MSFT | Reversal | 6 / 22 | -0.78% | 1.68% |
| MSFT | Technical strict | 20 / 22 | -2.31% | -0.14% |

## Data Lineage

- BTC: Binance `api/v3/klines`; five-year input SHA-256 `10e27611982eb507b30cf513565904917e76e44420529225ca81c50cba0ff479`.
- NVDA: Yahoo public chart reference; five-year input SHA-256 `8f89319ced4a8c004bded4a67566c7aa1e2411bacac75c418bf6011b496b83b7`.
- MSFT: Yahoo public chart reference; five-year input SHA-256 `30e468acc18bedbcb5d5a7aab91502c97c12d8870e733e4e4cdec9e6025b8f9b`.
- Full event-level artifacts: `.state/latest_bluechip_reversal_backtest_3y.json` and `.state/latest_bluechip_reversal_backtest_5y.json`.

## Verdict

The fixed reversal rule is useful as a delay/filter for some BTC decline episodes, but it is not a robust universal blue-chip entry rule. NVDA has too few reversal signals, and MSFT does not show positive absolute performance. Keep the live one-red-stop gate unchanged. The next research iteration should use walk-forward parameter selection, an untouched holdout, official equity data, and historical four-hour structure/flow data before any live integration.
