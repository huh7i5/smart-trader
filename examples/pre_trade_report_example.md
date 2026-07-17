# Pre-Trade Report Example

```text
PRE-TRADE CHECKLIST | BTC/USDT | 2026-07-17T03:15:22Z

1. Market structure proxy: CAUTION
   7-day change: -1.82%
   Visible bid/ask notional ratio: 1.24
   Limitation: trend and order-book depth do not identify institutional traders.

2. Retail taker flow: PASS
   Taker-buy ratio: 53.10%
   Six-hour price change: +0.28%
   Source: Binance Kline total and taker-buy base volume fields.

3. Macro and company news: UNKNOWN
   Reason: no recent URL-backed evidence file for BTC/USDT.

VERDICT: DO_NOT_TRADE
```

The report must not turn `UNKNOWN` into a green light. Gather real sources, create fresh macro/news evidence, and rerun the checklist. Even when all three checks pass, the next step is an order preview, not immediate execution.

```text
DATA PROVENANCE
Fetched: 2026-07-17T03:15:22Z
Sources: Binance /api/v3/klines and /api/v3/depth
Records: 8 daily candles, 6 hourly candles, 100 order-book levels
Evidence: .state/latest_checklist_BTCUSDT.json
Limitations: market-structure proxy; macro/news unavailable
```
