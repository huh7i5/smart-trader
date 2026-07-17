# Live Data Sources and Limits

## Binance Ranking Evidence

The market scanner joins three live Binance responses:

| Purpose | Endpoint | Required validation |
|---|---|---|
| Trading status and Spot eligibility | `https://api.binance.com/api/v3/exchangeInfo` | `status=TRADING`, Spot allowed, requested quote asset |
| 24-hour price, quote volume, trade count | `https://api.binance.com/api/v3/ticker/24hr` | Positive last price and parseable numeric fields |
| Product category | `https://www.binance.com/bapi/asset/v2/public/asset-service/product/get-products?includeEtf=true` | Product symbol contains the `bStocks` tag |

The product endpoint is on Binance's official domain but is not part of the stable Spot API contract. If its schema changes or returns no bStocks, fail closed rather than falling back to ticker-name guessing.

## Taker Flow

`https://api.binance.com/api/v3/klines` returns total base volume at index 5 and taker-buy base volume at index 9. Calculate:

```text
taker_sell_base_volume = total_base_volume - taker_buy_base_volume
taker_buy_ratio = taker_buy_base_volume / total_base_volume
```

Do not estimate taker flow from candle shape when the real field is available.

## Order Book and Smart-Money Language

`https://api.binance.com/api/v3/depth` is a visible, short-lived order-book snapshot. It can be cancelled, spoofed, or moved immediately. Combining it with a seven-day price trend is a market-structure proxy only. It is not evidence of ETF flows, whale wallets, exchange reserves, or institutional intent.

Use external, attributable sources for those claims. If such sources were not actually opened, omit the claim.

## Macro and Company News

The checklist accepts only recent URL-backed evidence created by `macro_evidence.py`. A clear result requires at least two reachable sources. Reachability does not prove relevance, so the response must still show the URLs and summarize what each source establishes.

When evidence cannot be obtained, report `unknown` and block active trading.

## Research Snapshot

On 2026-07-17, the official live product response contained 36 trading USDT products tagged `bStocks`, while the previous repository hardcoded 33. This demonstrates why live discovery is mandatory and manual counts must not be quoted as current facts.
